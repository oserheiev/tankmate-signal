"""Display World of Tanks friend presence changes in the hangar and battle HUD."""

import traceback
import weakref
from collections import OrderedDict

import BigWorld
import GUI
import SoundGroups
from PlayerEvents import g_playerEvents

from gui.app_loader.settings import APP_NAME_SPACE
from gui.Scaleform.daapi.view.battle.shared.page import SharedPage
from gui.Scaleform.genConsts.PLAYERS_PANEL_STATE import PLAYERS_PANEL_STATE
from gui.Scaleform.Waiting import Waiting
from gui.shared.personality import ServicesLocator
from helpers.gui_utils import setPixMode
from messenger.m_constants import PROTO_TYPE, USER_ACTION_ID, USER_TAG
from messenger.proto.events import g_messengerEvents
from messenger.proto.shared_find_criteria import FriendsFindCriteria
from messenger.storage import MessengerStorageDescriptor, UsersStorage
from skeletons.gui.app_loader import ApplicationStateID, GuiGlobalSpaceID


# Enable this before building to show a sample alert once when the HUD is ready.
_SHOW_TEST_NOTIFICATION = False

_PREFIX = '[TankmateSignal]'
_HANGAR_POSITION = (-0.96, -0.06, 0.0)
_BATTLE_FALLBACK_POSITION = (-0.95, -0.2, 0.0)
_BATTLE_LEFT_INSET = 0.025
_BATTLE_ANCHOR_COMPONENTS = ('playersPanel', 'battleMessenger', 'damagePanel')
_PLATE_TEXTURE_ROOT = 'gui/maps/icons/tankmate_signal/'
_PLATE_WIDTH = 222.0
_PLATE_HEIGHT = 52.0
_TEXT_INSET = 54.0
_TEXT_RIGHT_PADDING = 13.0
_STATUS_WIDTH = 160.0
_STATUS_HEIGHT = 22.0
_STACK_LIMIT = 3
_SHOW_DURATION = 5.0
_ROSTER_QUIET_TIME = 1.5
_ENTER_DURATION = 0.38
_EXIT_DURATION = 0.32
_MAX_ENTRY_STEP = 0.05
_NOTIFICATION_CHIME = 'gui_pbs_reward_item'
_battle_page_ref = None
_original_register_component = None
_callback = None
_visible_popups = []
_scene = None
_test_notification_pending = _SHOW_TEST_NOTIFICATION


class FriendPresence(object):
    users_storage = MessengerStorageDescriptor(UsersStorage)

    def __init__(self):
        self.online = None
        self.ready_at = None
        self.pending = OrderedDict()

    def reset(self):
        self.online = None
        self.ready_at = None
        self.pending.clear()

    def roster_loaded(self, now):
        if self.online is None:
            self.ready_at = now + _ROSTER_QUIET_TIME

    def initialize(self, now):
        if self.online is None and self.ready_at is not None and now >= self.ready_at:
            self.online = {user.getStorageKey(): bool(user.isOnline())
                           for user in self.users_storage.getList(FriendsFindCriteria())}
            self.ready_at = None
            _log('friends list ready (%d)' % len(self.online))

    def update(self, user, now):
        if not user.isFriend():
            return
        if self.online is None:
            if self.ready_at is not None:
                self.ready_at = now + _ROSTER_QUIET_TIME
            return

        friend_id = user.getStorageKey()
        online = bool(user.isOnline())
        previous = self.online.get(friend_id)
        self.online[friend_id] = online
        if previous is not None and previous != online:
            # A minimized session preserves every transition, including repeat friends.
            key = (friend_id, None if BigWorld.isWindowVisible() else object())
            self.pending.pop(key, None)
            self.pending[key] = (user.getName(), online)
            _log('friend status changed: %s' % ('online' if online else 'offline'))

    def update_membership(self, action, user):
        if self.online is None:
            return
        if action == USER_ACTION_ID.FRIEND_ADDED:
            self.online[user.getStorageKey()] = bool(user.isOnline())
        elif action in (USER_ACTION_ID.FRIEND_REMOVED, USER_ACTION_ID.IGNORED_ADDED,
                        USER_ACTION_ID.TMP_IGNORED_ADDED):
            friend_id = user.getStorageKey()
            self.online.pop(friend_id, None)
            for key in self.pending.keys():
                if key[0] == friend_id:
                    del self.pending[key]


_presence = FriendPresence()


class NotificationPlate(object):
    def __init__(self, name, online, shown_at):
        screen_width, screen_height = GUI.screenResolution()
        self.scale = max(0.75, min(screen_height / 1080.0, 1.75))
        self.frame_time = shown_at
        self.entry_elapsed = 0.0
        self.expires_at = shown_at + _SHOW_DURATION
        self.sound = None
        self.paused_at = None

        self.name = GUI.Text(name)
        self._set_pixel_layout(self.name)
        self.name.font = 'default_medium.font'
        self.name.colour = (238, 237, 233, 255)
        name_width, self.name_height = self.name.stringDimensions(name)
        status_image = 'status-online.png' if online else 'status-offline.png'
        self.status = GUI.Simple(_PLATE_TEXTURE_ROOT + status_image)
        self._set_pixel_layout(self.status)
        self.status.materialFX = GUI.Simple.eMaterialFX.BLEND
        status_width = round(_STATUS_WIDTH * self.scale)
        status_height = round(_STATUS_HEIGHT * self.scale)
        self.status.size = (status_width, status_height)
        self.line_gap = round(1.0 * self.scale)
        self.text_height = self.name_height + self.line_gap + status_height
        self.height = max(_PLATE_HEIGHT * self.scale, self.text_height + 10.0 * self.scale)
        text_padding = (_TEXT_INSET + _TEXT_RIGHT_PADDING) * self.scale
        self.width = max(_PLATE_WIDTH * self.scale, max(name_width, status_width) + text_padding)
        if self.width >= screen_width / 2.0 or self.height >= screen_height / 8.0:
            raise ValueError('Notification plate exceeds the viewport limits')

        backdrop_image = 'tankmate-plate.dds' if online else 'tankmate-plate-offline.dds'
        self.backdrop = GUI.Simple(_PLATE_TEXTURE_ROOT + backdrop_image)
        self._set_pixel_layout(self.backdrop)
        self.backdrop.materialFX = GUI.Simple.eMaterialFX.BLEND
        self.backdrop.size = (self.width, self.height)
        if (abs(self.backdrop.width - self.width) > 1.0
                or abs(self.backdrop.height - self.height) > 1.0):
            raise ValueError('The game did not apply the notification plate dimensions')
        self.backdrop.addChild(self.name, 'friendName')
        self.backdrop.addChild(self.status, 'friendStatus')

    @staticmethod
    def _set_pixel_layout(component):
        setPixMode(component)
        component.horizontalAnchor = GUI.Simple.eHAnchor.LEFT
        component.verticalAnchor = GUI.Simple.eVAnchor.TOP

    def move(self, position, visible_fraction, stack_offset=0.0):
        screen_width, screen_height = GUI.screenResolution()
        resting_x = (position[0] + 1.0) * screen_width / 2.0
        resting_x = max(0.0, min(resting_x, screen_width - self.width))
        hidden_x = -self.width - 2.0
        x = round(hidden_x + (resting_x - hidden_x) * visible_fraction)
        y = (1.0 - position[1]) * screen_height / 2.0 + stack_offset
        y = round(max(0.0, min(y, screen_height - self.height)))
        self.backdrop.position = (x, y, 0.3)
        text_x = x + round(_TEXT_INSET * self.scale)
        text_y = y + round((self.height - self.text_height) / 2.0)
        self.name.position = (text_x, text_y, 0.1)
        self.status.position = (text_x, text_y + self.name_height + self.line_gap, 0.1)

    def show(self):
        GUI.addRoot(self.backdrop)

    def update_position(self, position, now, stack_offset):
        frame_delta = max(0.0, now - self.frame_time)
        self.frame_time = now
        self.entry_elapsed = min(_ENTER_DURATION,
                                 self.entry_elapsed + min(frame_delta, _MAX_ENTRY_STEP))
        enter = self.entry_elapsed / _ENTER_DURATION
        exit_progress = min(1.0, max(0.0, 1.0 - (self.expires_at - now) / _EXIT_DURATION))
        ease_in = 1.0 - (1.0 - enter) ** 3
        ease_out = exit_progress ** 2
        self.move(position, ease_in * (1.0 - ease_out), stack_offset)

    def hide(self):
        if self.paused_at is not None:
            return
        GUI.delRoot(self.backdrop)

    def pause(self, now):
        if self.paused_at is not None:
            return
        self.hide()
        self.paused_at = now
        if self.sound is not None:
            try:
                self.sound.stop()
            except Exception:
                _log('notification chime could not be stopped')
                traceback.print_exc()

    def resume(self, now):
        if self.paused_at is None:
            return
        self.show()
        self.expires_at += now - self.paused_at
        self.frame_time = now
        self.paused_at = None


def _log(message):
    print('%s %s' % (_PREFIX, message))


def _visible_scene():
    app_loader = ServicesLocator.appLoader
    space_id = app_loader.getSpaceID()
    if space_id == GuiGlobalSpaceID.LOBBY:
        hangar = ServicesLocator.hangarSpace
        if (app_loader.getAppStateID(APP_NAME_SPACE.SF_LOBBY) == ApplicationStateID.INITIALIZED
                and hangar.spaceInited and not hangar.spaceLoading()
                and not Waiting.isVisible()):
            return 'hangar'
    elif space_id == GuiGlobalSpaceID.BATTLE:
        if (app_loader.getAppStateID(APP_NAME_SPACE.SF_BATTLE) == ApplicationStateID.INITIALIZED
                and not Waiting.isVisible()):
            return 'battle'
    return 'other'


def _on_status_updated(user):
    try:
        _presence.update(user, BigWorld.time())
    except Exception:
        _log('status handler failed')
        traceback.print_exc()


def _on_roster_loaded(tags):
    if USER_TAG.FRIEND in tags:
        _presence.roster_loaded(BigWorld.time())


def _on_membership_changed(action, user, *unused):
    if user is not None:
        _presence.update_membership(action, user)


def _subscribe_to_user_events(*unused):
    events = g_messengerEvents.users
    events.onUsersListReceived += _on_roster_loaded
    events.onUserStatusUpdated += _on_status_updated
    events.onUserActionReceived += _on_membership_changed


def _on_plugin_connected(proto_type, *unused):
    if proto_type == PROTO_TYPE.XMPP:
        _subscribe_to_user_events()


def _on_disconnected(*unused):
    _presence.reset()
    _hide_popups()


def _on_plugin_disconnected(proto_type, *unused):
    if proto_type == PROTO_TYPE.XMPP:
        _on_disconnected()


def _hide_popups():
    while _visible_popups:
        _visible_popups.pop().hide()


def _on_gui_space_left(_space_id):
    _hide_popups()


def _register_battle_component(page, component, alias):
    global _battle_page_ref
    result = _original_register_component(page, component, alias)
    if alias in _BATTLE_ANCHOR_COMPONENTS:
        _battle_page_ref = weakref.ref(page)
    return result


def _hud_bounds(display):
    if display is None or not display.visible:
        return None
    stage = getattr(display, 'stage', None)
    if stage is None or stage.stageWidth <= 0 or stage.stageHeight <= 0:
        return None
    rect = display.getBounds(stage)
    if rect.width > 0 and rect.height > 0:
        return rect, float(stage.stageWidth), float(stage.stageHeight)
    return None


def _clip_position(x, y, width, height):
    return (2.0 * x / width - 1.0, 1.0 - 2.0 * y / height, 0.0)


def _battle_popup_anchor():
    page = _battle_page_ref() if _battle_page_ref is not None else None
    if page is None:
        return _BATTLE_FALLBACK_POSITION, 'screen'
    if not page.isGuiVisible():
        return None, 'hud-hidden'

    panel = page.getComponent('playersPanel')
    if panel is not None and getattr(panel, '_mode', None) not in (
            PLAYERS_PANEL_STATE.NONE, PLAYERS_PANEL_STATE.HIDDEN):
        left = getattr(panel.flashObject, 'listLeft', None)
        geometry = _hud_bounds(left)
        if geometry is not None:
            rect, width, height = geometry
            scale = height / 1080.0
            top = rect.y + rect.height + 12.0 * scale
            if 0.0 <= top <= height - _PLATE_HEIGHT * scale:
                return _clip_position(width * _BATTLE_LEFT_INSET, top, width, height), 'left-team-panel'

    chat = page.getComponent('battleMessenger')
    if chat is not None:
        flash = chat.flashObject
        geometry = _hud_bounds(flash)
        input_geometry = _hud_bounds(getattr(flash, 'messageInputField', None))
        if geometry is not None and input_geometry is not None:
            rect, width, height = geometry
            scale = height / 1080.0
            x = rect.x + rect.width + 12.0 * scale
            y = input_geometry[0].y - _PLATE_HEIGHT * scale
            if 0.0 <= x <= width * 0.5 and 0.0 <= y <= height - _PLATE_HEIGHT * scale:
                return _clip_position(x, y, width, height), 'chat-side'

    damage = page.getComponent('damagePanel')
    if damage is not None:
        geometry = _hud_bounds(damage.flashObject)
        if geometry is not None:
            rect, width, height = geometry
            scale = height / 1080.0
            y = rect.y - _PLATE_HEIGHT * scale
            if 0.0 <= y <= height - _PLATE_HEIGHT * scale:
                return _clip_position(width * _BATTLE_LEFT_INSET, y, width, height), 'vehicle-panel'
    return _BATTLE_FALLBACK_POSITION, 'screen'


def _show_notification(name, online, scene, now, position, anchor):
    popup = NotificationPlate(name, online, now)
    popup.move(position, 0.0)
    popup.show()
    _visible_popups.append(popup)
    _log('notification shown: scene=%s anchor=%s state=%s' %
         (scene, anchor, 'online' if online else 'offline'))
    try:
        popup.sound = SoundGroups.g_instance.getSound2D(_NOTIFICATION_CHIME)
        if popup.sound is None:
            _log('notification chime unavailable: %s' % _NOTIFICATION_CHIME)
        else:
            popup.sound.play()
            _log('notification chime started: %s (%s)' %
                 (_NOTIFICATION_CHIME, 'playing' if popup.sound.isPlaying else 'pending'))
    except Exception:
        _log('notification chime failed')
        traceback.print_exc()


def _layout_notifications(scene, position, now):
    if not _visible_popups:
        return

    screen_height = GUI.screenResolution()[1]
    first = _visible_popups[0]
    gap = round(6.0 * first.scale)
    height = sum(popup.height for popup in _visible_popups) + gap * (len(_visible_popups) - 1)
    top = (1.0 - position[1]) * screen_height / 2.0
    if scene == 'hangar':
        top -= first.height / 2.0
    top = max(0.0, min(top, screen_height - height))
    stack_position = (position[0], 1.0 - 2.0 * top / screen_height, position[2])
    offset = 0.0
    for popup in _visible_popups:
        popup.update_position(stack_position, now, offset)
        offset += popup.height + gap


def _tick():
    global _callback, _scene, _test_notification_pending
    try:
        scene = _visible_scene()
        now = BigWorld.time()
        if scene in ('hangar', 'battle'):
            _presence.initialize(now)
        if scene != _scene:
            _hide_popups()
            _scene = scene
            _log('scene=%s' % scene)
        if not BigWorld.isWindowVisible():
            for popup in _visible_popups:
                popup.pause(now)
            return
        for popup in _visible_popups[:]:
            popup.resume(now)
            if now >= popup.expires_at:
                popup.hide()
                _visible_popups.remove(popup)
        if scene in ('hangar', 'battle') and (
                _visible_popups or _presence.pending or _test_notification_pending):
            position, anchor = (_battle_popup_anchor() if scene == 'battle'
                                else (_HANGAR_POSITION, 'hangar'))
            if position is None:
                _hide_popups()
            else:
                while len(_visible_popups) < _STACK_LIMIT and _presence.pending:
                    _, (name, online) = _presence.pending.popitem(last=False)
                    _show_notification(name, online, scene, now, position, anchor)
                if _test_notification_pending and len(_visible_popups) < _STACK_LIMIT:
                    _test_notification_pending = False
                    _show_notification('Test notification', True, scene, now, position, anchor)
                _layout_notifications(scene, position, now)
    except Exception:
        _log('display check failed')
        traceback.print_exc()
    finally:
        delay = 0.5
        if _visible_popups:
            now = BigWorld.time()
            for popup in _visible_popups:
                if popup.paused_at is not None:
                    continue
                remaining = popup.expires_at - now
                if popup.entry_elapsed < _ENTER_DURATION or remaining <= _EXIT_DURATION:
                    delay = min(delay, 1.0 / 60.0)
                else:
                    delay = max(0.01, min(delay, remaining - _EXIT_DURATION))
        _callback = BigWorld.callback(delay, _tick)


def init():
    global _callback, _original_register_component
    _original_register_component = SharedPage._onRegisterFlashComponent
    SharedPage._onRegisterFlashComponent = _register_battle_component
    _subscribe_to_user_events()
    g_messengerEvents.onPluginConnected += _on_plugin_connected
    g_messengerEvents.onPluginDisconnected += _on_plugin_disconnected
    g_playerEvents.onDisconnected += _on_disconnected
    g_playerEvents.onAccountShowGUI += _subscribe_to_user_events
    ServicesLocator.appLoader.onGUISpaceLeft += _on_gui_space_left
    _callback = BigWorld.callback(0.5, _tick)
    _log('loaded')


def fini():
    global _battle_page_ref, _callback, _scene
    if SharedPage._onRegisterFlashComponent is _register_battle_component:
        SharedPage._onRegisterFlashComponent = _original_register_component
    _battle_page_ref = None
    events = g_messengerEvents.users
    events.onUsersListReceived -= _on_roster_loaded
    events.onUserStatusUpdated -= _on_status_updated
    events.onUserActionReceived -= _on_membership_changed
    g_messengerEvents.onPluginConnected -= _on_plugin_connected
    g_messengerEvents.onPluginDisconnected -= _on_plugin_disconnected
    g_playerEvents.onDisconnected -= _on_disconnected
    g_playerEvents.onAccountShowGUI -= _subscribe_to_user_events
    ServicesLocator.appLoader.onGUISpaceLeft -= _on_gui_space_left
    if _callback is not None:
        BigWorld.cancelCallback(_callback)
        _callback = None
    _on_disconnected()
    _scene = None
