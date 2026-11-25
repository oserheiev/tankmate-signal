"""Display World of Tanks friend presence changes in the hangar and battle HUD."""

import json
import os
import traceback
import weakref
from collections import OrderedDict, deque

import BattleReplay
import BigWorld
import GUI
import Keys
import game
import ResMgr
import SoundGroups
from PlayerEvents import g_playerEvents

from gui.app_loader.settings import APP_NAME_SPACE
from gui.Scaleform.daapi.view.battle.shared.page import SharedPage
from gui.Scaleform.genConsts.PLAYERS_PANEL_STATE import PLAYERS_PANEL_STATE
from gui.Scaleform.Waiting import Waiting
from gui.shared.personality import ServicesLocator
from gui.shared.utils import flashObject2Dict
from gui.shared.utils.key_mapping import getBigworldKey
from gui import SystemMessages
from helpers import dependency, getClientLanguage
from helpers.gui_utils import setPixMode
from messenger.m_constants import PROTO_TYPE, USER_ACTION_ID, USER_TAG
from messenger.proto import proto_getter
from messenger.proto.events import g_messengerEvents
from messenger.proto.interfaces import ISearchHandler
from messenger.proto.shared_find_criteria import FriendsFindCriteria
from messenger.proto.xmpp.jid import makeContactJID
from messenger.proto.xmpp.xmpp_search_processors import SearchUsersProcessor
from messenger.storage import MessengerStorageDescriptor, UsersStorage
from skeletons.gui.app_loader import ApplicationStateID, GuiGlobalSpaceID
from skeletons.gui.game_control import IGameSessionController


# Enable this before building to show a sample alert once when the HUD is ready.
_SHOW_TEST_NOTIFICATION = False

_PREFIX = '[TankmateSignal]'
_HANGAR_POSITION = (-0.96, -0.06, 0.0)
_BATTLE_FALLBACK_POSITION = (-0.95, -0.2, 0.0)
_BATTLE_LEFT_INSET = 0.025
_BATTLE_ANCHOR_COMPONENTS = ('playersPanel', 'battleMessenger', 'damagePanel')
_PLATE_TEXTURE_ROOT = 'gui/maps/icons/tankmate_signal/'
_PLATE_WIDTH = 256.0
_PLATE_HEIGHT = 84.0
_TEXT_INSET = 76.0
_TEXT_RIGHT_PADDING = 20.0
_STATUS_WIDTH = 160.0
_STATUS_HEIGHT = 22.0
_STACK_LIMIT = 3
_SHOW_DURATION = 5.0
_ROSTER_QUIET_TIME = 1.5
_ENTER_DURATION = 0.38
_EXIT_DURATION = 0.32
_MAX_ENTRY_STEP = 0.05
_NOTIFICATION_CHIME = 'gui_pbs_reward_item'
_WHISPER_WIDTH = 156.0
_ACTION_SLANT = 24.0
_CONFIG_PATH = 'mods/configs/tankmate_signal.json'
_DEFAULT_WHISPER_HOTKEY = 'CTRL+T'
_MODIFIER_KEYS = {
    'CTRL': (Keys.KEY_LCONTROL, Keys.KEY_RCONTROL),
    'ALT': (Keys.KEY_LALT, Keys.KEY_RALT),
    'SHIFT': (Keys.KEY_LSHIFT, Keys.KEY_RSHIFT),
}
_TEST_FRIEND_NAME = 'Sauzer_'
_TEST_HOTKEYS = {Keys.KEY_F9: True, Keys.KEY_F10: False}
_battle_page_ref = None
_original_register_component = None
_callback = None
_visible_popups = []
_scene = None
_test_notification_pending = _SHOW_TEST_NOTIFICATION
_original_handle_key_event = None
_pressed_whisper = None
_test_hotkey_down = set()
_test_friend_pending = deque()
_test_friend_lookup = None
_whisper_catalog = None
_whisper_hotkey = None
_whisper_hotkey_label = 'Ctrl+T'
_whisper_hotkey_down = False
_MODS_SETTINGS_LINK = 'tankmate.signal'
_SETTINGS_UI = 'tankmateSettings.swf'
_dev_mode = False
_view_settings_class = None
_view_settings_original = None
_view_settings_hook = None
_settings_window_class = None
_settings_hooks = {}
_settings_panel = None
_settings_open = False


def _has_presence(user):
    # BattleUserEntity can carry friend tags but has no global online status.
    return callable(getattr(user, 'isOnline', None))


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

    def friends(self):
        return (user for user in self.users_storage.getList(FriendsFindCriteria())
                if _has_presence(user))

    def initialize(self, now):
        if self.online is None and self.ready_at is not None and now >= self.ready_at:
            self.online = {user.getStorageKey(): bool(user.isOnline())
                           for user in self.friends()}
            self.ready_at = None
            _log('friends list ready (%d)' % len(self.online))

    def update(self, user, now):
        if not _has_presence(user) or not user.isFriend():
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
            if _has_presence(user):
                self.online[user.getStorageKey()] = bool(user.isOnline())
        elif action in (USER_ACTION_ID.FRIEND_REMOVED, USER_ACTION_ID.IGNORED_ADDED,
                        USER_ACTION_ID.TMP_IGNORED_ADDED):
            friend_id = user.getStorageKey()
            self.online.pop(friend_id, None)
            for key in list(self.pending):
                if key[0] == friend_id:
                    del self.pending[key]


_presence = FriendPresence()
_xmpp = proto_getter(PROTO_TYPE.XMPP)


class TestFriendLookup(ISearchHandler):
    def __init__(self):
        self.processor = SearchUsersProcessor()
        self.processor.addHandler(self)

    def onSearchComplete(self, users):
        for user in users:
            if user.getName().lower() == _TEST_FRIEND_NAME.lower():
                for popup in _visible_popups:
                    if popup.whisper_action is not None and popup.whisper_action.friend_key == (None, None):
                        popup.whisper_action.friend_key = user.getStorageKey()
                        popup.whisper_action.state = 'ready'
                _log('test whisper recipient resolved')
                return
        _log('test whisper recipient not found: ' + _TEST_FRIEND_NAME)
        self._mark_unavailable()

    def onSearchFailed(self, reason):
        _log('test whisper recipient lookup failed: %s' % reason)
        self._mark_unavailable()

    @staticmethod
    def _mark_unavailable():
        for popup in _visible_popups:
            if popup.whisper_action is not None and popup.whisper_action.friend_key == (None, None):
                popup.whisper_action.state = 'unavailable'


class WhisperButton(object):
    def __init__(self, friend_key):
        self.friend_key = friend_key
        self.used = False
        self.state = 'pending' if friend_key == (None, None) else 'ready'

    def handleMouseClickEvent(self, component, _position=None):
        if not self.used and self.state not in ('pending', 'unavailable'):
            _log('whisper button clicked')
            try:
                self.used = self._send_whisper()
                self.state = 'sent' if self.used else 'retry'
            except Exception:
                self.state = 'retry'
                _log('whisper attempt failed')
                traceback.print_exc()
            component.textureName = _whisper_texture(self.state)
        return True

    def _send_whisper(self):
        if (not BigWorld.isWindowVisible() or _visible_scene() not in ('hangar', 'battle')
                or BattleReplay.isPlaying()):
            return False
        db_id, scope = self.friend_key
        if db_id is None:
            _log('whisper skipped: recipient lookup has not completed')
            return False
        user = _presence.users_storage.getUser(db_id, PROTO_TYPE.XMPP, scope)
        if user is None:
            _log('whisper skipped: friend unavailable')
            return False
        xmpp = _xmpp.get()
        if not xmpp.isConnected() or xmpp.messages.isInCooldown():
            _log('whisper skipped: chat disconnected or cooling down')
            return False
        if dependency.instance(IGameSessionController).isPrivateMessagesForbidden:
            _log('whisper skipped: private messages restricted')
            return False
        # The XMPP sender requires an existing private chat session.
        opened = xmpp.messages.startChatSession(db_id, user.getName())
        if not opened or (isinstance(opened, tuple) and not opened[0]):
            _log('whisper skipped: could not open a private chat session')
            return False
        message_key = 'message' if _visible_scene() == 'battle' else 'message_hangar'
        xmpp.messages.sendChatMessage(makeContactJID(db_id), _whisper_strings()[message_key])
        _log('whisper handed to private chat')
        return True


def _language_candidates():
    locale = (getClientLanguage() or 'en').lower().replace('_', '-')
    if locale in ('zh', 'zh-hans', 'zh-sg', 'zh-cn-sg'):
        locale = 'zh-cn'
    elif locale in ('zh-hant', 'zh-hk', 'zh-mo'):
        locale = 'zh-tw'
    if locale.replace('-', '').isalnum():
        return (locale, locale.split('-', 1)[0], 'en')
    return ('en',)


def _status_texture(online):
    suffix = 'online.png' if online else 'offline.png'
    for candidate in _language_candidates():
        texture = _PLATE_TEXTURE_ROOT + 'status-' + candidate + '-' + suffix
        if ResMgr.isFile(texture):
            return texture
    return _PLATE_TEXTURE_ROOT + 'status-en-' + suffix


def _whisper_strings():
    global _whisper_catalog
    if _whisper_catalog is None:
        section = ResMgr.openSection(_PLATE_TEXTURE_ROOT + 'whisper-labels.json')
        _whisper_catalog = json.loads(section.asBinary)
    for candidate in _language_candidates():
        if candidate in _whisper_catalog:
            return _whisper_catalog[candidate]
    return _whisper_catalog['en']


def _whisper_texture(state, hovered=False):
    suffix = state + '-hover' if state in ('ready', 'retry') and hovered else state
    for candidate in _language_candidates():
        texture = _PLATE_TEXTURE_ROOT + 'whisper-' + candidate + '-' + suffix + '.png'
        if ResMgr.isFile(texture):
            return texture
    return _PLATE_TEXTURE_ROOT + 'whisper-en-' + suffix + '.png'


def _load_settings():
    global _dev_mode
    _dev_mode = False
    shortcut = _DEFAULT_WHISPER_HOTKEY
    try:
        with open(_CONFIG_PATH, 'rb') as settings_file:
            settings = json.load(settings_file)
            shortcut = settings.get('whisper_hotkey', shortcut)
            _dev_mode = settings.get('dev_mode', False) is True
    except IOError:
        pass
    except (ValueError, AttributeError):
        _log('invalid settings file; using Ctrl+T')
    if not _set_whisper_hotkey(shortcut):
        _log('invalid whisper hotkey; using Ctrl+T')
        _set_whisper_hotkey(_DEFAULT_WHISPER_HOTKEY)


def _parse_whisper_hotkey(shortcut):
    if shortcut == '':
        return None, ''
    parts = shortcut.upper().replace(' ', '').split('+')
    modifiers, key_name = parts[:-1], parts[-1]
    if (not key_name or any(item not in _MODIFIER_KEYS for item in modifiers)
            or len(set(modifiers)) != len(modifiers)
            or not key_name.replace('_', '').isalnum()
            or (key_name in ('F9', 'F10') and set(modifiers) == {'CTRL'})):
        raise ValueError('invalid or reserved shortcut')
    key = getattr(Keys, 'KEY_' + key_name)
    excluded = set(value for pair in _MODIFIER_KEYS.values() for value in pair)
    excluded.update(getattr(Keys, name, None) for name in (
        'KEY_NONE', 'KEY_LEFTMOUSE', 'KEY_RIGHTMOUSE', 'KEY_MIDDLEMOUSE', 'KEY_RETURN', 'KEY_ESCAPE'))
    if key in excluded:
        raise ValueError('invalid shortcut key')
    return (key, set(modifiers)), '+'.join([item.title() for item in modifiers] + [key_name])


def _set_whisper_hotkey(shortcut):
    global _whisper_hotkey, _whisper_hotkey_label, _whisper_hotkey_down
    try:
        binding, label = _parse_whisper_hotkey(shortcut)
    except (ValueError, AttributeError, TypeError):
        return False
    _whisper_hotkey, _whisper_hotkey_label = binding, label
    _whisper_hotkey_down = False
    return True


def _save_settings(shortcut, dev_mode):
    try:
        with open(_CONFIG_PATH, 'rb') as stream:
            settings = json.load(stream)
        if not isinstance(settings, dict):
            settings = {}
    except (IOError, ValueError):
        settings = {}
    settings['whisper_hotkey'] = shortcut
    settings['dev_mode'] = dev_mode
    directory = os.path.dirname(_CONFIG_PATH)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    temporary, backup = _CONFIG_PATH + '.tmp', _CONFIG_PATH + '.bak'
    try:
        with open(temporary, 'wb') as stream:
            stream.write((json.dumps(settings, indent=2) + '\n').encode('utf-8'))
        had_original = os.path.isfile(_CONFIG_PATH)
        if had_original:
            # Python 2.7 on Windows cannot rename over an existing file.
            if os.path.exists(backup):
                os.remove(backup)
            os.rename(_CONFIG_PATH, backup)
        try:
            os.rename(temporary, _CONFIG_PATH)
        except OSError:
            if had_original:
                os.rename(backup, _CONFIG_PATH)
            raise
        if had_original:
            try:
                os.remove(backup)
            except OSError:
                pass
    finally:
        if os.path.isfile(temporary):
            os.remove(temporary)


def _on_settings_opened():
    global _settings_open, _pressed_whisper, _whisper_hotkey_down
    _settings_open = True
    _pressed_whisper = None
    _whisper_hotkey_down = False
    _hide_popups()


def _on_settings_closed():
    global _settings_open
    _settings_open = False


def _install_settings_hooks(window_class, view_settings_class):
    global _settings_window_class, _view_settings_class, _view_settings_original, _view_settings_hook
    if _settings_window_class is not None:
        return
    originals = dict((name, getattr(window_class, name)) for name in (
        '_populate', '_dispose', '_SettingsWindow__apply', 'onSettingsChange'))
    original_view_settings = view_settings_class.getDAAPIObject

    def view_settings(settings):
        result = original_view_settings(settings)
        if settings.alias == 'settingsWindow':
            result = dict(result)
            result['url'] = _SETTINGS_UI
        return result

    def populate(window, *args, **kwargs):
        global _settings_panel
        result = originals['_populate'](window, *args, **kwargs)
        _on_settings_opened()
        _settings_panel = ModsSettings(window)
        _settings_panel.sync_ui()
        _log('Mods / Tankmate Signal settings ready')
        return result

    def dispose(window, *args, **kwargs):
        global _settings_panel
        if _settings_panel is not None and _settings_panel.window is window:
            _settings_panel.close()
            _settings_panel = None
            _on_settings_closed()
        return originals['_dispose'](window, *args, **kwargs)

    def apply(window, settings, *args, **kwargs):
        if _settings_panel is not None and _settings_panel.window is window:
            # Flash confirms its stock changes after this callback even if a
            # mod save fails. Never prevent the native settings from applying.
            _settings_panel.apply()
        return originals['_SettingsWindow__apply'](window, settings, *args, **kwargs)

    def preview(window, setting_name, value):
        if setting_name == _MODS_SETTINGS_LINK:
            if _settings_panel is not None and _settings_panel.window is window:
                _settings_panel.on_change(flashObject2Dict(value))
            return
        return originals['onSettingsChange'](window, setting_name, value)

    for name, hook in (('_populate', populate), ('_dispose', dispose),
                       ('_SettingsWindow__apply', apply), ('onSettingsChange', preview)):
        _settings_hooks[name] = (originals[name], hook)
        setattr(window_class, name, hook)
    _view_settings_class = view_settings_class
    _view_settings_original, _view_settings_hook = original_view_settings, view_settings
    view_settings_class.getDAAPIObject = view_settings
    _settings_window_class = window_class


def _register_settings():
    if _settings_window_class is not None:
        return
    try:
        from gui.Scaleform.daapi.view.common.settings.SettingsWindow import SettingsWindow
        from gui.Scaleform.framework import GroupedViewSettings
        _install_settings_hooks(SettingsWindow, GroupedViewSettings)
        _log('native Mods tab registered')
    except (ImportError, AttributeError):
        _log('built-in settings integration unavailable; using JSON configuration')


def _unregister_settings():
    global _settings_window_class, _settings_panel, _view_settings_class
    global _view_settings_original, _view_settings_hook
    if _settings_panel is not None:
        _settings_panel.close()
        _settings_panel = None
    if _settings_window_class is not None:
        for name, (original, hook) in _settings_hooks.items():
            current = getattr(_settings_window_class, name)
            if getattr(current, 'im_func', current) is hook:
                setattr(_settings_window_class, name, original)
    if _view_settings_class is not None:
        current = _view_settings_class.getDAAPIObject
        if getattr(current, 'im_func', current) is _view_settings_hook:
            _view_settings_class.getDAAPIObject = _view_settings_original
    _view_settings_class = _view_settings_original = _view_settings_hook = None
    _settings_hooks.clear()
    _settings_window_class = None
    _on_settings_closed()


class ModsSettings(object):
    def __init__(self, window):
        self.window = window
        self.shortcut = self.saved_shortcut = _whisper_hotkey_label
        self.dev_mode = self.saved_dev_mode = _dev_mode
        self.capturing = False
        self.error = False

    @property
    def dirty(self):
        return self.shortcut != self.saved_shortcut or self.dev_mode != self.saved_dev_mode

    def stage(self, shortcut):
        try:
            _, label = _parse_whisper_hotkey(shortcut)
        except (ValueError, AttributeError, TypeError):
            self.error = 'invalid'
            return False
        self.shortcut = label
        self.error = False
        return True

    def apply(self):
        global _dev_mode
        self.capturing = False
        if not self.dirty:
            self.sync_ui()
            return True
        try:
            _save_settings(self.shortcut, self.dev_mode)
        except (IOError, OSError):
            self.error = 'save'
            _log('could not save mod settings')
            SystemMessages.pushMessage(_whisper_strings()['settings_save_error'], type=SystemMessages.SM_TYPE.Warning)
            self.sync_ui()
            return False
        _set_whisper_hotkey(self.shortcut)
        _dev_mode = self.dev_mode
        if not _dev_mode:
            _test_friend_pending.clear()
            _test_hotkey_down.clear()
        self.saved_shortcut, self.saved_dev_mode = self.shortcut, self.dev_mode
        self.error = False
        self.sync_ui()
        return True

    def close(self):
        self.capturing = False

    def sync_ui(self):
        strings = _whisper_strings()
        caption = '...' if self.capturing else (self.shortcut or strings['settings_disabled'])
        if self.capturing and self.error == 'invalid':
            caption = strings['settings_invalid']
        self.window.flashObject.as_setTankmateSettings({
            'hotkeyLabel': strings['settings_hotkey'], 'shortcutLabel': caption,
            'devLabel': strings['settings_dev_mode'], 'devDescription': strings['settings_dev_description'],
            'dev_mode': self.dev_mode, 'capturing': self.capturing, 'dirty': self.dirty})

    def on_change(self, value):
        action = value.get('action')
        if action == 'dev_mode' and isinstance(value.get('value'), bool):
            self.dev_mode = value['value']
        elif action == 'capture':
            self.capturing = True
            self.error = False
        elif action == 'cancel_capture':
            self.capturing = False
        elif action == 'key' and self.capturing:
            self._capture_key(getBigworldKey(value.get('code')))
        self.sync_ui()

    def _capture_key(self, key):
        if key == Keys.KEY_ESCAPE:
            self.capturing = False
        elif key in (Keys.KEY_BACKSPACE, Keys.KEY_DELETE):
            self.stage('')
            self.capturing = False
        elif not any(key in keys for keys in _MODIFIER_KEYS.values()):
            names = [name[4:] for name in dir(Keys) if name.startswith('KEY_') and getattr(Keys, name) == key]
            modifiers = [name for name in ('CTRL', 'ALT', 'SHIFT')
                         if any(BigWorld.isKeyDown(code) for code in _MODIFIER_KEYS[name])]
            if names and self.stage('+'.join(modifiers + [min(names, key=len)])):
                self.capturing = False


class NotificationPlate(object):
    def __init__(self, name, online, shown_at, whisper_to=None, clan_tag=''):
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
        self.clan = None
        if clan_tag:
            self.clan = GUI.Text('[' + clan_tag + ']')
            self._set_pixel_layout(self.clan)
            self.clan.font = self.name.font
            self.clan.colour = (178, 170, 152, 255)
            self.clan_offset = name_width + round(8.0 * self.scale)
            clan_width, self.clan_height = self.clan.stringDimensions('[' + clan_tag + ']')
            name_width = self.clan_offset + clan_width
        self.profile = GUI.Simple(_PLATE_TEXTURE_ROOT + ('profile-online.png' if online else 'profile-offline.png'))
        self._set_pixel_layout(self.profile)
        self.profile.materialFX = GUI.Simple.eMaterialFX.BLEND
        self.profile.size = (round(48.0 * self.scale), round(48.0 * self.scale))
        self.rule = GUI.Simple(_PLATE_TEXTURE_ROOT + 'status-rule.png')
        self._set_pixel_layout(self.rule)
        self.rule.materialFX = GUI.Simple.eMaterialFX.BLEND
        self.rule.size = (round(136.0 * self.scale), round(2.0 * self.scale))
        self.rule.colour = (156, 194, 128, 255) if online else (225, 109, 93, 255)
        self.status = GUI.Simple(_status_texture(online))
        self._set_pixel_layout(self.status)
        self.status.materialFX = GUI.Simple.eMaterialFX.BLEND
        status_width = round(_STATUS_WIDTH * self.scale)
        status_height = round(_STATUS_HEIGHT * self.scale)
        self.status.size = (status_width, status_height)
        self.line_gap = round(14.0 * self.scale)
        self.text_height = self.name_height + self.line_gap + status_height
        self.whisper = None
        self.whisper_hint = None
        self.keycap = None
        self.whisper_action = None
        self.whisper_bounds = None
        self.whisper_width = self.whisper_height = 0
        if whisper_to is not None:
            self.whisper_action = WhisperButton(whisper_to)
            self.whisper = GUI.Simple(_whisper_texture(self.whisper_action.state))
            self._set_pixel_layout(self.whisper)
            self.whisper.materialFX = GUI.Simple.eMaterialFX.BLEND
            self.whisper_width = round(_WHISPER_WIDTH * self.scale)
            self.whisper_hint = GUI.Text(_whisper_hotkey_label)
            self._set_pixel_layout(self.whisper_hint)
            self.whisper_hint.font = 'default_small.font'
            self.whisper_hint.colour = (241, 234, 219, 255)
            self.hint_width, self.hint_height = self.whisper_hint.stringDimensions(_whisper_hotkey_label)
            self.keycap = GUI.Simple(_PLATE_TEXTURE_ROOT + 'shortcut-keycap.png')
            self._set_pixel_layout(self.keycap)
            self.keycap.materialFX = GUI.Simple.eMaterialFX.BLEND
            self.keycap_width = max(round(78.0 * self.scale), self.hint_width + round(16.0 * self.scale))
            self.keycap_height = self.hint_height + round(8.0 * self.scale)
            self.keycap.size = (self.keycap_width, self.keycap_height)
            self.keycap.visible = self.whisper_hint.visible = bool(_whisper_hotkey_label)
            self.whisper_width = max(self.whisper_width, self.keycap_width + round(36.0 * self.scale))
        self.height = max(_PLATE_HEIGHT * self.scale, self.text_height + 20.0 * self.scale)
        if self.whisper is not None:
            self.height = max(self.height, self.keycap_height + 48.0 * self.scale)
            self.whisper_height = self.height
            self.whisper.size = (self.whisper_width, self.whisper_height)
        text_padding = (_TEXT_INSET + _TEXT_RIGHT_PADDING) * self.scale
        content_width = max(name_width, status_width)
        self.width = max(_PLATE_WIDTH * self.scale, content_width + text_padding)
        if self.whisper is not None:
            self.width = content_width + text_padding + self.whisper_width
        if self.width >= screen_width / 2.0 or self.height >= screen_height / 8.0:
            raise ValueError('Notification plate exceeds the viewport limits')

        self.backdrop = GUI.Simple(_PLATE_TEXTURE_ROOT + 'plate.png')
        self._set_pixel_layout(self.backdrop)
        self.backdrop.materialFX = GUI.Simple.eMaterialFX.BLEND
        self.backdrop.size = (self.width, self.height)
        if (abs(self.backdrop.width - self.width) > 1.0
                or abs(self.backdrop.height - self.height) > 1.0):
            raise ValueError('The game did not apply the notification plate dimensions')
        self.backdrop.addChild(self.name, 'friendName')
        self.backdrop.addChild(self.status, 'friendStatus')
        self.backdrop.addChild(self.profile, 'profile')
        self.backdrop.addChild(self.rule, 'statusRule')
        if self.clan is not None:
            self.backdrop.addChild(self.clan, 'clanTag')
        if self.whisper is not None:
            self.backdrop.addChild(self.whisper, 'whisper')
            self.backdrop.addChild(self.keycap, 'shortcutKeycap')
            self.backdrop.addChild(self.whisper_hint, 'whisperHotkey')

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
        if self.clan is not None:
            self.clan.position = (text_x + self.clan_offset,
                                  text_y + round((self.name_height - self.clan_height) / 2.0), 0.1)
        self.status.position = (text_x, text_y + self.name_height + self.line_gap, 0.1)
        self.rule.position = (text_x, text_y + self.name_height + round(7.0 * self.scale), 0.1)
        self.profile.position = (x + round(14.0 * self.scale), y + round((self.height - self.profile.size[1]) / 2.0), 0.1)
        if self.whisper is not None:
            button_x = x + self.width - self.whisper_width
            button_y = y
            self.whisper.position = (button_x, button_y, 0.1)
            center_x = button_x + (self.whisper_width + _ACTION_SLANT * self.scale) / 2.0
            keycap_y = y + round(self.height * 0.58)
            self.keycap.position = (round(center_x - self.keycap_width / 2.0), keycap_y, 0.05)
            self.whisper_hint.position = (round(center_x - self.hint_width / 2.0),
                                          keycap_y + round((self.keycap_height - self.hint_height) / 2.0), 0.0)
            self.whisper_bounds = (button_x, button_y,
                                   button_x + self.whisper_width, button_y + self.whisper_height)

    def show(self):
        GUI.addRoot(self.backdrop)

    def update_position(self, position, now, stack_offset):
        frame_delta = max(0.0, now - self.frame_time)
        self.frame_time = now
        if self.whisper is not None:
            hovered = _whisper_under_cursor() is self
            self.whisper.textureName = _whisper_texture(self.whisper_action.state, hovered)
            self.whisper_hint.visible = bool(_whisper_hotkey_label) and self.whisper_action.state in ('ready', 'retry')
            self.keycap.visible = self.whisper_hint.visible
            if hovered and not self.whisper_action.used:
                self.expires_at += frame_delta
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


def _whisper_under_cursor():
    if not _visible_popups or not BigWorld.isWindowVisible() or _visible_scene() not in ('hangar', 'battle'):
        return None
    cursor = GUI.mcursor()
    if not cursor.active or not cursor.visible:
        return None
    width, height = GUI.screenResolution()
    cursor_x, cursor_y = cursor.position
    x = (cursor_x + 1.0) * width / 2.0
    y = (1.0 - cursor_y) * height / 2.0
    now = BigWorld.time()
    for popup in reversed(_visible_popups):
        if popup.whisper_bounds is None or popup.paused_at is not None or now >= popup.expires_at:
            continue
        left, top, right, bottom = popup.whisper_bounds
        slant = _ACTION_SLANT / _WHISPER_WIDTH * (right - left) * (bottom - y) / (bottom - top)
        if left + slant <= x <= right and top <= y <= bottom:
            return popup
    return None


def _handle_key_event(event):
    global _pressed_whisper, _test_hotkey_down, _test_friend_pending, _whisper_hotkey_down
    if _settings_open:
        return _original_handle_key_event(event)
    if _whisper_hotkey is not None and event.key == _whisper_hotkey[0]:
        if not event.isKeyDown():
            was_down = _whisper_hotkey_down
            _whisper_hotkey_down = False
            if was_down:
                return True
        elif _whisper_hotkey_down:
            return True
        else:
            modifiers = set(name for name, keys in _MODIFIER_KEYS.items()
                            if any(BigWorld.isKeyDown(key) for key in keys))
            if (modifiers == _whisper_hotkey[1] and BigWorld.isWindowVisible()
                    and _visible_scene() in ('hangar', 'battle') and not BattleReplay.isPlaying()):
                now = BigWorld.time()
                for popup in reversed(_visible_popups):
                    if popup.whisper_action is not None and popup.paused_at is None and now < popup.expires_at:
                        _whisper_hotkey_down = True
                        popup.whisper_action.handleMouseClickEvent(popup.whisper)
                        popup.expires_at = max(popup.expires_at, now + 2.0)
                        return True
    if _dev_mode and event.key in _TEST_HOTKEYS:
        if not event.isKeyDown():
            was_down = event.key in _test_hotkey_down
            _test_hotkey_down.discard(event.key)
            if was_down:
                return True
        elif event.key in _test_hotkey_down:
            return True
        elif ((BigWorld.isKeyDown(Keys.KEY_LCONTROL) or BigWorld.isKeyDown(Keys.KEY_RCONTROL))
              and not any(BigWorld.isKeyDown(key) for name in ('ALT', 'SHIFT') for key in _MODIFIER_KEYS[name])):
            _test_hotkey_down.add(event.key)
            _test_friend_pending.append(_TEST_HOTKEYS[event.key])
            _log('test popup requested for ' + _TEST_FRIEND_NAME)
            return True
    if event.key == Keys.KEY_LEFTMOUSE:
        try:
            if event.isKeyDown():
                _pressed_whisper = _whisper_under_cursor()
                if _pressed_whisper is not None:
                    return True
            elif _pressed_whisper is not None:
                pressed = _pressed_whisper
                _pressed_whisper = None
                if _whisper_under_cursor() is pressed:
                    pressed.whisper_action.handleMouseClickEvent(pressed.whisper)
                    pressed.expires_at = max(pressed.expires_at, BigWorld.time() + 2.0)
                return True
        except Exception:
            _pressed_whisper = None
            _log('whisper input handler failed')
            traceback.print_exc()
    return _original_handle_key_event(event)


def _visible_scene():
    if _settings_open:
        return 'other'
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
    _register_settings()
    events = g_messengerEvents.users
    events.onUsersListReceived += _on_roster_loaded
    events.onUserStatusUpdated += _on_status_updated
    events.onUserActionReceived += _on_membership_changed


def _on_plugin_connected(proto_type, *unused):
    if proto_type == PROTO_TYPE.XMPP:
        _subscribe_to_user_events()


def _on_disconnected(*unused):
    global _test_hotkey_down, _test_friend_pending, _whisper_hotkey_down
    _test_hotkey_down.clear()
    _test_friend_pending.clear()
    _whisper_hotkey_down = False
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


def _show_notification(name, online, scene, now, position, anchor, friend_key=None):
    whisper_to = friend_key if online and not BattleReplay.isPlaying() else None
    clan_tag = ''
    if friend_key is not None and friend_key[0] is not None:
        user = _presence.users_storage.getUser(friend_key[0], PROTO_TYPE.XMPP, friend_key[1])
        if user is not None:
            info = user.getClanInfo()
            clan_tag = getattr(info, 'abbrev', '') or ''
    popup = NotificationPlate(name, online, now, whisper_to, clan_tag)
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
    first = _visible_popups[-1]
    gap = round(6.0 * first.scale)
    height = sum(popup.height for popup in _visible_popups) + gap * (len(_visible_popups) - 1)
    top = (1.0 - position[1]) * screen_height / 2.0
    if scene == 'hangar':
        top -= first.height / 2.0
    top = max(0.0, min(top, screen_height - height))
    stack_position = (position[0], 1.0 - 2.0 * top / screen_height, position[2])
    offset = 0.0
    for popup in reversed(_visible_popups):
        popup.update_position(stack_position, now, offset)
        offset += popup.height + gap


def _tick():
    global _callback, _scene, _test_notification_pending, _test_friend_pending, _test_friend_lookup
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
                _visible_popups or _presence.pending or _test_notification_pending or _test_friend_pending):
            position, anchor = (_battle_popup_anchor() if scene == 'battle'
                                else (_HANGAR_POSITION, 'hangar'))
            if position is None:
                _hide_popups()
            else:
                while _test_friend_pending and len(_visible_popups) < _STACK_LIMIT:
                    test_online = _test_friend_pending[0]
                    friend_key = None
                    for user in _presence.friends():
                        if user.getName().lower() == _TEST_FRIEND_NAME.lower():
                            friend_key = user.getStorageKey()
                            break
                    _show_notification(_TEST_FRIEND_NAME, test_online, scene, now, position, anchor,
                                       friend_key if friend_key is not None else (None, None))
                    _test_friend_pending.popleft()
                    if friend_key is None and test_online:
                        if _test_friend_lookup is None:
                            _test_friend_lookup = TestFriendLookup()
                        _test_friend_lookup.processor.find(_TEST_FRIEND_NAME)
                        _log('looking up test whisper recipient by name')
                while len(_visible_popups) < _STACK_LIMIT and _presence.pending:
                    (friend_key, _), (name, online) = _presence.pending.popitem(last=False)
                    _show_notification(name, online, scene, now, position, anchor, friend_key)
                if _test_notification_pending and len(_visible_popups) < _STACK_LIMIT:
                    _test_notification_pending = False
                    _show_notification('Test notification', True, scene, now, position, anchor)
                _layout_notifications(scene, position, now)
    except Exception:
        _log('display check failed')
        traceback.print_exc()
    finally:
        delay = 0.05 if _settings_open else 0.5
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
                if popup.whisper_action is not None:
                    delay = min(delay, 0.05)
        _callback = BigWorld.callback(delay, _tick)


def init():
    global _callback, _original_register_component, _original_handle_key_event
    _load_settings()
    _original_handle_key_event = game.handleKeyEvent
    game.handleKeyEvent = _handle_key_event
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
    global _battle_page_ref, _callback, _scene, _pressed_whisper, _test_friend_lookup
    _unregister_settings()
    if _test_friend_lookup is not None:
        _test_friend_lookup.processor.removeHandler(_test_friend_lookup)
        _test_friend_lookup.processor.fini()
        _test_friend_lookup = None
    if game.handleKeyEvent is _handle_key_event:
        game.handleKeyEvent = _original_handle_key_event
    _pressed_whisper = None
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
