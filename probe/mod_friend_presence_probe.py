"""Temporary diagnostics for friend presence and popup placement."""

import traceback
import weakref

import BigWorld
import GUI
import SoundGroups

from constants import ARENA_PERIOD
from gui.app_loader.settings import APP_NAME_SPACE
from gui.Scaleform.daapi.view.battle.shared.page import SharedPage
from gui.Scaleform.genConsts.PLAYERS_PANEL_STATE import PLAYERS_PANEL_STATE
from gui.Scaleform.Waiting import Waiting
from gui.shared.personality import ServicesLocator
from messenger.proto.events import g_messengerEvents
from skeletons.gui.app_loader import ApplicationStateID, GuiGlobalSpaceID


_PREFIX = '[FriendPresenceProbe]'
_HANGAR_POSITION = (-0.87, -0.06, 0.0)
_BATTLE_FALLBACK_POSITION = (-0.84, -0.2, 0.0)
_BATTLE_LEFT_INSET = 0.065
_BATTLE_ANCHOR_COMPONENTS = ('playersPanel', 'battleMessenger', 'damagePanel')
_NOTIFICATION_CHIME = 'gui_pbs_notification_bubble'
_battle_page_ref = None
_original_register_component = None
_callback = None
_popup = None
_popup_until = 0
_scene = None
_sampled_scenes = set()


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
        GUI.delRoot(_popup)
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
            if 0.0 <= top <= height - 36.0 * scale:
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
            y = input_geometry[0].y - 32.0 * scale
            if 0.0 <= x <= width * 0.5 and 0.0 <= y <= height - 36.0 * scale:
                return _clip_position(x, y, width, height), 'chat-side'

    damage = page.getComponent('damagePanel')
    if damage is not None:
        geometry = _hud_bounds(damage.flashObject)
        if geometry is not None:
            rect, width, height = geometry
            scale = height / 1080.0
            y = rect.y - 36.0 * scale
            if 0.0 <= y <= height - 36.0 * scale:
                return _clip_position(width * _BATTLE_LEFT_INSET, y, width, height), 'vehicle-panel'
    return _BATTLE_FALLBACK_POSITION, 'screen'


def _can_show_sample(scene):
    if scene == 'hangar':
        return True
    if scene == 'battle':
        arena = getattr(BigWorld.player(), 'arena', None)
        return arena is not None and arena.period == ARENA_PERIOD.BATTLE
    return False


def _show_sample(scene, now, position, anchor):
    global _popup, _popup_until
    label = GUI.Text('Sample friend is online')
    label.horizontalPositionMode = 'CLIP'
    label.verticalPositionMode = 'CLIP'
    label.horizontalAnchor = 'LEFT'
    label.verticalAnchor = 'TOP' if scene == 'battle' else 'CENTER'
    label.colour = (245, 239, 221, 255)
    label.position = position
    GUI.addRoot(label)
    _popup = label
    _popup_until = now + 5.0
    _log('sample added scene=%s anchor=%s position=%r' % (scene, anchor, position))
    try:
        SoundGroups.g_instance.playSound2D(_NOTIFICATION_CHIME)
        _log('notification chime requested: %s' % _NOTIFICATION_CHIME)
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
        if _popup is not None or (scene not in _sampled_scenes and _can_show_sample(scene)):
            position, anchor = (_battle_popup_anchor() if scene == 'battle'
                                else (_HANGAR_POSITION, 'hangar'))
            if position is None:
                _hide_popup()
            elif _popup is not None:
                _popup.position = position
            else:
                _show_sample(scene, now, position, anchor)
                _sampled_scenes.add(scene)
    except Exception:
        _log('display check failed')
        traceback.print_exc()
    finally:
        _callback = BigWorld.callback(0.5, _tick)


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
