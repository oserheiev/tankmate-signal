"""Temporary diagnostics for friend presence and popup placement."""

import traceback
import weakref

import BigWorld
import GUI
import SoundGroups

from gui.app_loader.settings import APP_NAME_SPACE
from gui.Scaleform.daapi.view.battle.shared.page import SharedPage
from gui.Scaleform.genConsts.PLAYERS_PANEL_STATE import PLAYERS_PANEL_STATE
from gui.Scaleform.Waiting import Waiting
from gui.shared.personality import ServicesLocator
from helpers.gui_utils import setPixMode
from messenger.proto.events import g_messengerEvents
from skeletons.gui.app_loader import ApplicationStateID, GuiGlobalSpaceID


_PREFIX = '[TankmateSignal]'
_HANGAR_POSITION = (-0.96, -0.06, 0.0)
_BATTLE_FALLBACK_POSITION = (-0.95, -0.2, 0.0)
_BATTLE_LEFT_INSET = 0.025
_BATTLE_ANCHOR_COMPONENTS = ('playersPanel', 'battleMessenger', 'damagePanel')
_PLATE_TEXTURE = 'gui/maps/icons/tankmate_signal/tankmate-plate.dds'
_PLATE_WIDTH = 222.0
_PLATE_HEIGHT = 52.0
_ENTER_DURATION = 0.38
_EXIT_DURATION = 0.32
_MAX_ENTRY_STEP = 0.05
_NOTIFICATION_CHIME = 'gui_pbs_reward_item'
_battle_page_ref = None
_original_register_component = None
_callback = None
_popup = None
_popup_until = 0
_scene = None
_sampled_scenes = set()


class NotificationPlate(object):
    def __init__(self, name, status, scene, shown_at):
        screen_width, screen_height = GUI.screenResolution()
        self.scale = max(0.75, min(screen_height / 1080.0, 1.75))
        self.scene = scene
        self.frame_time = shown_at
        self.entry_elapsed = 0.0
        self.sound = None

        self.name = self._text(name, 'default_medium.font', (238, 237, 233, 255))
        self.status = self._text(status, 'default_smaller.font', (100, 186, 33, 255))
        name_width, self.name_height = self.name.stringDimensions(name)
        status_width, status_height = self.status.stringDimensions(status)
        self.line_gap = round(1.0 * self.scale)
        self.text_height = self.name_height + self.line_gap + status_height
        self.height = max(_PLATE_HEIGHT * self.scale, self.text_height + 10.0 * self.scale)
        self.width = max(_PLATE_WIDTH * self.scale, max(name_width, status_width) + 67.0 * self.scale)
        if self.width >= screen_width / 2.0 or self.height >= screen_height / 8.0:
            raise ValueError('Notification plate exceeds the viewport limits')

        self.backdrop = GUI.Simple(_PLATE_TEXTURE)
        self._set_pixel_layout(self.backdrop)
        self.backdrop.materialFX = GUI.Simple.eMaterialFX.BLEND
        self.backdrop.size = (self.width, self.height)
        if (abs(self.backdrop.width - self.width) > 1.0
                or abs(self.backdrop.height - self.height) > 1.0):
            raise ValueError('The game did not apply the notification plate dimensions')
        self.components = (self.backdrop, self.name, self.status)

    def _text(self, value, font, colour):
        label = GUI.Text(value)
        self._set_pixel_layout(label)
        label.font = font
        label.colour = colour
        return label

    @staticmethod
    def _set_pixel_layout(component):
        setPixMode(component)
        component.horizontalAnchor = GUI.Simple.eHAnchor.LEFT
        component.verticalAnchor = GUI.Simple.eVAnchor.TOP

    def move(self, position, visible_fraction=1.0):
        screen_width, screen_height = GUI.screenResolution()
        resting_x = (position[0] + 1.0) * screen_width / 2.0
        resting_x = max(0.0, min(resting_x, screen_width - self.width))
        hidden_x = -self.width - 2.0
        x = round(hidden_x + (resting_x - hidden_x) * visible_fraction)
        y = (1.0 - position[1]) * screen_height / 2.0
        if self.scene == 'hangar':
            y -= self.height / 2.0
        y = round(max(0.0, min(y, screen_height - self.height)))
        self.backdrop.position = (x, y, 0.3)
        text_x = x + round(58.0 * self.width / 240.0)
        text_y = y + round((self.height - self.text_height) / 2.0)
        self.name.position = (text_x, text_y, 0.1)
        self.status.position = (text_x, text_y + self.name_height + self.line_gap, 0.1)

    def show(self):
        added = []
        try:
            for component in self.components:
                GUI.addRoot(component)
                added.append(component)
        except Exception:
            for component in reversed(added):
                GUI.delRoot(component)
            raise

    def update_position(self, position, now, expires_at):
        frame_delta = max(0.0, now - self.frame_time)
        self.frame_time = now
        self.entry_elapsed = min(_ENTER_DURATION,
                                 self.entry_elapsed + min(frame_delta, _MAX_ENTRY_STEP))
        enter = self.entry_elapsed / _ENTER_DURATION
        exit_progress = min(1.0, max(0.0, 1.0 - (expires_at - now) / _EXIT_DURATION))
        ease_in = 1.0 - (1.0 - enter) ** 3
        ease_out = exit_progress ** 2
        self.move(position, ease_in * (1.0 - ease_out))

    def hide(self):
        for component in reversed(self.components):
            GUI.delRoot(component)


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
        if user.isFriend():
            status = 'online' if user.isOnline() else 'offline'
            _log('status scene=%s friend=%r state=%s' %
                 (_visible_scene(), user.getName(), status))
    except Exception:
        _log('status handler failed')
        traceback.print_exc()


def _hide_popup():
    global _popup
    if _popup is not None:
        _popup.hide()
        _popup = None


def _on_gui_space_left(_space_id):
    _hide_popup()


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


def _show_sample(scene, now, position, anchor):
    global _popup, _popup_until
    popup = NotificationPlate('Sample friend', 'Online', scene, now)
    popup.move(position, 0.0)
    popup.show()
    _popup = popup
    _popup_until = now + 5.0
    _log('sample added scene=%s anchor=%s position=%r size=%dx%d' %
         (scene, anchor, popup.backdrop.position, popup.width, popup.height))
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


def _tick():
    global _callback, _scene
    try:
        scene = _visible_scene()
        now = BigWorld.time()
        if scene != _scene:
            _hide_popup()
            _scene = scene
            _log('scene=%s' % scene)
        elif _popup is not None and now >= _popup_until:
            _hide_popup()
        if scene in ('hangar', 'battle') and (_popup is not None or scene not in _sampled_scenes):
            position, anchor = (_battle_popup_anchor() if scene == 'battle'
                                else (_HANGAR_POSITION, 'hangar'))
            if position is None:
                _hide_popup()
            elif _popup is not None:
                _popup.update_position(position, now, _popup_until)
            else:
                _show_sample(scene, now, position, anchor)
                _sampled_scenes.add(scene)
    except Exception:
        _log('display check failed')
        traceback.print_exc()
    finally:
        delay = 0.5
        if _popup is not None:
            now = BigWorld.time()
            remaining = _popup_until - now
            if _popup.entry_elapsed < _ENTER_DURATION or remaining <= _EXIT_DURATION:
                delay = 1.0 / 60.0
            else:
                delay = max(0.01, min(delay, remaining - _EXIT_DURATION))
        _callback = BigWorld.callback(delay, _tick)


def init():
    global _callback, _original_register_component
    _original_register_component = SharedPage._onRegisterFlashComponent
    SharedPage._onRegisterFlashComponent = _register_battle_component
    g_messengerEvents.users.onUserStatusUpdated += _on_status_updated
    ServicesLocator.appLoader.onGUISpaceLeft += _on_gui_space_left
    _callback = BigWorld.callback(0.5, _tick)
    _log('loaded')


def fini():
    global _battle_page_ref, _callback, _scene
    if SharedPage._onRegisterFlashComponent is _register_battle_component:
        SharedPage._onRegisterFlashComponent = _original_register_component
    _battle_page_ref = None
    g_messengerEvents.users.onUserStatusUpdated -= _on_status_updated
    ServicesLocator.appLoader.onGUISpaceLeft -= _on_gui_space_left
    if _callback is not None:
        BigWorld.cancelCallback(_callback)
        _callback = None
    _hide_popup()
    _scene = None
    _sampled_scenes.clear()
