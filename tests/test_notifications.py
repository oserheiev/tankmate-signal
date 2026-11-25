import contextlib
import io
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch, mock_open


SOURCE = Path(__file__).resolve().parents[1] / "probe" / "mod_tankmate_signal.py"


def load_mod(test_alert=False):
    modules = {}

    def stub(name, **attributes):
        module = modules.setdefault(name, ModuleType(name))
        module.__dict__.update(attributes)
        if "." in name:
            parent, child = name.rsplit(".", 1)
            setattr(stub(parent), child, module)
        return module

    window = stub("BigWorld", time=Mock(return_value=0.0), callback=Mock(),
                  isWindowVisible=Mock(return_value=True))
    stub("BattleReplay", isPlaying=Mock(return_value=False))
    stub("GUI")
    stub("game", handleKeyEvent=Mock(return_value=False))
    stub("Keys", KEY_LEFTMOUSE=1, KEY_BACKSPACE=14, KEY_DELETE=211, KEY_RETURN=28, KEY_SPACE=57,
         KEY_ESCAPE=27, KEY_F8=119, KEY_F9=120, KEY_F10=121, KEY_LCONTROL=29, KEY_RCONTROL=157,
         KEY_T=20, KEY_LALT=56, KEY_RALT=184, KEY_LSHIFT=42, KEY_RSHIFT=54)
    stub("ResMgr", isFile=Mock(), openSection=Mock(return_value=SimpleNamespace(
        asBinary=(SOURCE.parent / "whisper-labels.json").read_bytes())))
    stub("SoundGroups")
    stub("PlayerEvents", g_playerEvents=Mock())
    stub("gui.app_loader.settings", APP_NAME_SPACE=Mock())
    stub("gui.Scaleform.daapi.view.battle.shared.page", SharedPage=Mock())
    stub("gui.Scaleform.genConsts.PLAYERS_PANEL_STATE", PLAYERS_PANEL_STATE=Mock())
    stub("gui.Scaleform.Waiting", Waiting=Mock())
    stub("gui.shared.personality", ServicesLocator=Mock())
    stub("gui.shared.utils", flashObject2Dict=lambda value: value)
    stub("gui.shared.utils.key_mapping", getBigworldKey=lambda code: {84: 20, 8: 14, 27: 27}.get(code, code))
    stub("gui.SystemMessages", pushMessage=Mock(), SM_TYPE=Mock())
    stub("helpers", getClientLanguage=Mock(return_value="en"),
         dependency=SimpleNamespace(instance=Mock(return_value=SimpleNamespace(
             isPrivateMessagesForbidden=False))))
    stub("helpers.gui_utils", setPixMode=Mock())
    stub("messenger.m_constants", PROTO_TYPE=Mock(), USER_TAG=Mock(),
         USER_ACTION_ID=SimpleNamespace(FRIEND_ADDED=1, FRIEND_REMOVED=2,
                                        IGNORED_ADDED=3, TMP_IGNORED_ADDED=4))
    stub("messenger.proto.events", g_messengerEvents=Mock())
    stub("messenger.proto", proto_getter=Mock())
    stub("messenger.proto.interfaces", ISearchHandler=object)
    stub("messenger.proto.xmpp.xmpp_search_processors", SearchUsersProcessor=Mock())
    stub("messenger.proto.xmpp.jid", makeContactJID=Mock())
    stub("messenger.proto.shared_find_criteria", FriendsFindCriteria=Mock())
    stub("messenger.storage", MessengerStorageDescriptor=Mock(return_value=Mock()),
         UsersStorage=Mock())
    stub("skeletons.gui.app_loader", ApplicationStateID=Mock(), GuiGlobalSpaceID=Mock())
    stub("skeletons.gui.game_control", IGameSessionController=Mock())

    source = SOURCE.read_bytes()
    if test_alert:
        source = source.replace(b"_SHOW_TEST_NOTIFICATION = False", b"_SHOW_TEST_NOTIFICATION = True")
    mod = ModuleType("tankmate_under_test")
    with patch.dict(sys.modules, modules):
        exec(compile(source, str(SOURCE), "exec"), mod.__dict__)
    mod._log = Mock()
    return mod, window


def contact(name, online, friend=True, clan=""):
    return SimpleNamespace(getStorageKey=lambda: (name, "xmpp"), getName=lambda: name,
                           isOnline=lambda: online, isFriend=lambda: friend,
                           getClanInfo=lambda: SimpleNamespace(abbrev=clan))


def battle_contact(name):
    return SimpleNamespace(getStorageKey=lambda: (name, "battle"), getName=lambda: name,
                           isFriend=lambda: True)


class LifecycleTests(unittest.TestCase):
    def test_startup_and_shutdown_without_optional_packages_or_config(self):
        with patch.dict(sys.modules, {"gui.aslainMenu": None, "gui.modsSettingsApi": None}):
            mod, window = load_mod()
            window.cancelCallback = Mock()
            original_key_handler = mod.game.handleKeyEvent
            original_register_component = mod.SharedPage._onRegisterFlashComponent
            with patch.multiple(mod, g_messengerEvents=MagicMock(),
                                g_playerEvents=MagicMock(), ServicesLocator=MagicMock()):
                with patch("builtins.open", side_effect=FileNotFoundError):
                    mod.init()

                self.assertIsNone(mod._settings_panel)
                self.assertEqual(mod._whisper_hotkey, (mod.Keys.KEY_T, {"CTRL"}))
                self.assertIs(mod.game.handleKeyEvent, mod._handle_key_event)
                window.callback.assert_called_once_with(0.5, mod._tick)

                mod.fini()

            self.assertIs(mod.game.handleKeyEvent, original_key_handler)
            self.assertIs(mod.SharedPage._onRegisterFlashComponent, original_register_component)
            window.cancelCallback.assert_called_once_with(window.callback.return_value)


class PresenceTests(unittest.TestCase):
    def setUp(self):
        self.mod, self.window = load_mod()
        self.presence = self.mod._presence
        self.presence.users_storage.getList.return_value = [
            contact("Alice", False), contact("Bob", False)
        ]

    def initialize_roster(self, now):
        self.presence.roster_loaded(now)
        self.presence.initialize(now + self.mod._ROSTER_QUIET_TIME)

    def test_initial_roster_and_reconnect_load_silently(self):
        self.presence.roster_loaded(0)
        self.presence.update(contact("Alice", True), 1)
        self.presence.initialize(2)
        self.assertIsNone(self.presence.online)
        self.presence.initialize(3)
        self.assertFalse(self.presence.pending)

        self.presence.update(contact("Alice", True), 4)
        self.assertEqual(list(self.presence.pending.values()), [("Alice", True)])
        self.presence.reset()
        self.presence.users_storage.getList.return_value = [contact("Alice", True)]
        self.initialize_roster(5)
        self.assertFalse(self.presence.pending)

    def test_visible_updates_keep_latest_change_per_friend_in_order(self):
        self.initialize_roster(0)
        for update in (contact("Alice", True), contact("Bob", True),
                       contact("Alice", False), contact("Alice", False),
                       contact("Stranger", True, friend=False)):
            self.presence.update(update, 2)
        self.assertEqual(list(self.presence.pending.values()), [("Bob", True), ("Alice", False)])

    def test_battle_entities_do_not_interrupt_contact_presence_tracking(self):
        battle_user = battle_contact("Alice")
        self.presence.users_storage.getList.return_value = [battle_user, contact("Alice", False)]

        self.initialize_roster(0)
        self.presence.update(battle_user, 2)
        self.presence.update_membership(self.mod.USER_ACTION_ID.FRIEND_ADDED, battle_user)

        self.assertEqual(self.presence.online, {("Alice", "xmpp"): False})
        self.assertFalse(self.presence.pending)
        self.presence.update(contact("Alice", True), 3)
        self.assertEqual(list(self.presence.pending.values()), [("Alice", True)])

    def test_minimized_updates_keep_each_transition_and_removal_clears_them(self):
        self.initialize_roster(0)
        self.window.isWindowVisible.return_value = False
        for update in (contact("Alice", True), contact("Bob", True), contact("Alice", False),
                       contact("Alice", True), contact("Alice", True)):
            self.presence.update(update, 2)
        self.assertEqual(list(self.presence.pending.values()),
                         [("Alice", True), ("Bob", True), ("Alice", False), ("Alice", True)])
        self.presence.update_membership(self.mod.USER_ACTION_ID.FRIEND_REMOVED, contact("Alice", True))
        self.assertEqual(list(self.presence.pending.values()), [("Bob", True)])
        self.assertNotIn(("Alice", "xmpp"), self.presence.online)


class NotificationTests(unittest.TestCase):
    def configure(self, test_alert=False):
        self.mod, self.window = load_mod(test_alert)
        self.mod._visible_scene = Mock(return_value="other")
        self.mod._battle_popup_anchor = Mock(return_value=(None, "hud-hidden"))
        self.mod._layout_notifications = Mock()
        self.mod._show_notification = Mock(side_effect=self.record_popup)

    def record_popup(self, name, online, scene, now, position, anchor, friend_key=None):
        self.mod._visible_popups.append(Mock(expires_at=now + 5, paused_at=None, entry_elapsed=1.0))

    def tick(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.mod._tick()
        self.assertEqual(errors.getvalue(), "")

    def test_pending_waits_through_loading_and_minimization_and_uses_three_slots(self):
        self.configure()
        for name in ("A", "B", "C", "D"):
            self.mod._presence.pending[((name, "shared"), None)] = (name, True)
        self.tick()
        self.window.isWindowVisible.return_value = False
        self.mod._visible_scene.return_value = "hangar"
        self.tick()
        self.mod._show_notification.assert_not_called()

        self.window.isWindowVisible.return_value = True
        self.tick()
        self.assertEqual([call.args[0] for call in self.mod._show_notification.call_args_list],
                         ["A", "B", "C"])
        self.window.time.return_value = 5.0
        self.tick()
        self.assertEqual(self.mod._show_notification.call_args.args[0], "D")

    def test_sample_is_disabled_by_default(self):
        self.configure()
        self.mod._visible_scene.return_value = "hangar"
        self.tick()
        self.mod._show_notification.assert_not_called()

    def test_status_uses_bundled_locale_with_english_fallback(self):
        self.configure()
        self.mod.ResMgr.isFile.side_effect = lambda name: name.endswith(
            ("status-uk-online.png", "status-zh-tw-offline.png")
        )
        for language, online, filename in (
            ("uk-UA", True, "status-uk-online.png"),
            ("zh_Hant", False, "status-zh-tw-offline.png"),
            ("invalid", False, "status-en-offline.png"),
        ):
            with self.subTest(language=language):
                self.mod.getClientLanguage.return_value = language
                self.assertEqual(self.mod._status_texture(online),
                                 self.mod._PLATE_TEXTURE_ROOT + filename)

    def test_sample_fires_once_on_the_ready_battle_hud(self):
        self.configure(test_alert=True)
        self.tick()
        self.mod._visible_scene.return_value = "battle"
        self.tick()
        self.mod._show_notification.assert_not_called()
        position = (-0.95, 0.0, 0.0)
        self.mod._battle_popup_anchor.return_value = (position, "left-team-panel")
        self.tick()
        self.mod._visible_scene.return_value = "hangar"
        self.tick()
        self.mod._show_notification.assert_called_once_with(
            "Test notification", True, "battle", 0.0, position, "left-team-panel"
        )

    def test_battle_notification_keeps_friend_identity(self):
        self.configure()
        self.mod._visible_scene.return_value = "battle"
        position = (-0.95, 0.0, 0.0)
        self.mod._battle_popup_anchor.return_value = (position, "left-team-panel")
        friend_key = (42, "shared")
        self.mod._presence.pending[(friend_key, None)] = ("Alice", True)

        self.tick()

        self.mod._show_notification.assert_called_once_with(
            "Alice", True, "battle", 0.0, position, "left-team-panel", friend_key
        )

    def test_hotkey_shows_offline_friend_with_whisper_target_once(self):
        self.configure()
        self.mod._dev_mode = True
        self.mod._visible_scene.return_value = "battle"
        position = (-0.95, 0.0, 0.0)
        self.mod._battle_popup_anchor.return_value = (position, "left-team-panel")
        self.mod._presence.users_storage.getList.return_value = [
            battle_contact("Sauzer_"), contact("Sauzer_", False)
        ]
        self.window.isKeyDown = lambda key: key == self.mod.Keys.KEY_LCONTROL
        event = SimpleNamespace(key=self.mod.Keys.KEY_F9, isKeyDown=lambda: True)

        self.assertTrue(self.mod._handle_key_event(event))
        self.tick()
        self.assertTrue(self.mod._handle_key_event(event))
        self.tick()

        self.mod._show_notification.assert_called_once_with(
            "Sauzer_", True, "battle", 0.0, position, "left-team-panel", ("Sauzer_", "xmpp")
        )

    def test_popup_reads_real_clan_tag_from_contact(self):
        mod, _ = load_mod()
        mod._presence.users_storage.getUser.return_value = contact("Sauzer_", True, clan="TAG")
        mod.NotificationPlate = Mock()
        mod.SoundGroups.g_instance = Mock()

        mod._show_notification("Sauzer_", True, "hangar", 0, (0, 0, 0), "hangar", (42, "shared"))

        mod.NotificationPlate.assert_called_once_with("Sauzer_", True, 0, (42, "shared"), "TAG")

    def test_online_and_offline_test_hotkeys_queue_distinct_popups(self):
        self.configure()
        self.mod._dev_mode = True
        self.mod._visible_scene.return_value = "hangar"
        self.mod._presence.users_storage.getList.return_value = [contact("Sauzer_", True)]
        self.window.isKeyDown = lambda key: key == self.mod.Keys.KEY_LCONTROL
        for key in (self.mod.Keys.KEY_F9, self.mod.Keys.KEY_F10):
            down = SimpleNamespace(key=key, isKeyDown=lambda: True)
            self.assertTrue(self.mod._handle_key_event(down))
            self.assertTrue(self.mod._handle_key_event(down))
            self.assertTrue(self.mod._handle_key_event(SimpleNamespace(key=key, isKeyDown=lambda: False)))

        self.tick()

        self.assertEqual([call.args[1] for call in self.mod._show_notification.call_args_list], [True, False])


class WhisperTests(unittest.TestCase):
    def setUp(self):
        self.mod, _ = load_mod()
        self.mod._visible_scene = Mock(return_value="battle")
        self.friend_key = (42, "shared")
        self.user = contact("Alice", True)
        self.mod._presence.users_storage.getUser.return_value = self.user
        proto = self.mod.proto_getter.return_value.get.return_value
        proto.isConnected.return_value = True
        self.messages = proto.messages
        self.messages.isInCooldown.return_value = False
        self.messages.startChatSession.return_value = True

    def test_one_whisper_to_the_friend_on_click(self):
        button = self.mod.WhisperButton(self.friend_key)
        self.messages.sendChatMessage.assert_not_called()


        button.handleMouseClickEvent(Mock())
        button.handleMouseClickEvent(Mock())

        self.mod._presence.users_storage.getUser.assert_called_once_with(
            42, self.mod.PROTO_TYPE.XMPP, "shared"
        )
        self.messages.startChatSession.assert_called_once_with(42, "Alice")
        self.messages.sendChatMessage.assert_called_once_with(
            self.mod.makeContactJID.return_value, "Want to platoon? I'm in battle now."
        )

    def test_offline_friend_message_is_handed_to_private_chat(self):
        self.mod._presence.users_storage.getUser.return_value = contact("Alice", False)
        button = self.mod.WhisperButton(self.friend_key)

        button.handleMouseClickEvent(Mock())

        self.messages.startChatSession.assert_called_once_with(42, "Alice")
        self.messages.sendChatMessage.assert_called_once_with(
            self.mod.makeContactJID.return_value, "Want to platoon? I'm in battle now."
        )

    def test_private_message_restriction_property_blocks_send(self):
        self.mod.dependency.instance.return_value.isPrivateMessagesForbidden = True
        button = self.mod.WhisperButton(self.friend_key)

        button.handleMouseClickEvent(Mock())

        self.messages.startChatSession.assert_not_called()
        self.messages.sendChatMessage.assert_not_called()

    def test_message_follows_game_language_and_scene(self):
        self.mod.getClientLanguage.return_value = "uk-UA"
        self.mod._visible_scene.return_value = "hangar"
        button = self.mod.WhisperButton(self.friend_key)

        button.handleMouseClickEvent(Mock())

        self.messages.sendChatMessage.assert_called_once_with(
            self.mod.makeContactJID.return_value, "Хочеш зіграти взводом?"
        )
        self.assertEqual(button.state, "sent")

    def test_unknown_language_uses_english_message(self):
        self.mod.getClientLanguage.return_value = "unknown"
        self.assertEqual(self.mod._whisper_strings()["ready"], "Whisper")

    def test_translations_cover_the_presence_languages(self):
        catalog = json.loads((SOURCE.parent / "whisper-labels.json").read_text(encoding="utf-8"))
        languages = json.loads((SOURCE.parent / "status-labels.json").read_text(encoding="utf-8"))
        self.assertEqual(set(catalog), set(languages))
        required = {"ready", "sent", "retry", "pending", "unavailable", "message", "message_hangar",
                    "settings_hotkey", "settings_disabled", "settings_invalid", "settings_save_error",
                    "settings_dev_mode", "settings_dev_description"}
        for language, strings in catalog.items():
            with self.subTest(language=language):
                self.assertTrue(required.issubset(strings))
                self.assertTrue(all(isinstance(value, str) and value.strip() for value in strings.values()))


class NotificationStackTests(unittest.TestCase):
    def test_newest_notification_is_positioned_above_older_notifications(self):
        mod, _ = load_mod()
        mod.GUI.screenResolution = Mock(return_value=(1920, 1080))
        oldest, middle, newest = [Mock(scale=1.0, height=84.0) for _ in range(3)]
        mod._visible_popups[:] = [oldest, middle, newest]

        mod._layout_notifications("battle", (-0.95, 0, 0), 0)

        self.assertEqual(newest.update_position.call_args.args[2], 0)
        self.assertGreaterEqual(middle.update_position.call_args.args[2], newest.height)
        self.assertGreaterEqual(oldest.update_position.call_args.args[2],
                                middle.update_position.call_args.args[2] + middle.height)

class WhisperInputTests(unittest.TestCase):
    def setUp(self):
        self.mod, _ = load_mod()
        self.mod._visible_scene = Mock(return_value="battle")
        self.mod.GUI.screenResolution = Mock(return_value=(1920, 1080))
        self.cursor = SimpleNamespace(active=True, visible=True, position=(0.0, 0.0))
        self.mod.GUI.mcursor = Mock(return_value=self.cursor)
        self.original = Mock(return_value=False)
        self.mod._original_handle_key_event = self.original
        self.popup = SimpleNamespace(whisper=Mock(), whisper_action=Mock(),
                                     whisper_bounds=(900, 500, 1020, 580),
                                     paused_at=None, expires_at=5.0)
        self.mod._visible_popups.append(self.popup)

    def event(self, down):
        return SimpleNamespace(key=1, isKeyDown=lambda: down)

    def test_click_uses_visible_button_bounds_before_game_dispatch(self):
        for scene in ("hangar", "battle"):
            with self.subTest(scene=scene):
                self.mod._visible_scene.return_value = scene
                self.popup.whisper_action.reset_mock()
                self.assertTrue(self.mod._handle_key_event(self.event(True)))
                self.popup.whisper_action.handleMouseClickEvent.assert_not_called()
                self.assertTrue(self.mod._handle_key_event(self.event(False)))
                self.popup.whisper_action.handleMouseClickEvent.assert_called_once_with(self.popup.whisper)
                self.original.assert_not_called()

    def test_release_outside_consumes_click_without_sending(self):
        self.assertTrue(self.mod._handle_key_event(self.event(True)))
        self.cursor.position = (0.9, 0.9)
        self.assertTrue(self.mod._handle_key_event(self.event(False)))
        self.popup.whisper_action.handleMouseClickEvent.assert_not_called()

    def test_inactive_cursor_preserves_battle_input(self):
        self.cursor.active = False
        event = self.event(True)
        self.assertFalse(self.mod._handle_key_event(event))
        self.original.assert_called_once_with(event)

    def test_slanted_corner_passes_click_through_to_game(self):
        self.cursor.position = (901 / 960 - 1, 1 - 501 / 540)
        event = self.event(True)

        self.assertFalse(self.mod._handle_key_event(event))

        self.original.assert_called_once_with(event)
        self.popup.whisper_action.handleMouseClickEvent.assert_not_called()

    def test_name_lookup_connects_visible_test_button_to_exact_recipient(self):
        self.popup.whisper_action.friend_key = (None, None)
        lookup = self.mod.TestFriendLookup()
        lookup.onSearchComplete([contact("Sauzer_other", False), contact("Sauzer_", False)])
        self.assertEqual(self.popup.whisper_action.friend_key, ("Sauzer_", "xmpp"))

    def test_send_shortcut_targets_latest_visible_popup_once_while_held(self):
        self.mod._load_settings = Mock()
        self.mod._whisper_hotkey = (20, {"CTRL"})
        self.mod.BigWorld.isKeyDown = lambda key: key == self.mod.Keys.KEY_LCONTROL
        latest = SimpleNamespace(whisper=Mock(), whisper_action=Mock(), paused_at=None, expires_at=5.0)
        self.mod._visible_popups.append(latest)
        down = SimpleNamespace(key=20, isKeyDown=lambda: True)
        up = SimpleNamespace(key=20, isKeyDown=lambda: False)

        self.assertTrue(self.mod._handle_key_event(down))
        self.assertTrue(self.mod._handle_key_event(down))
        self.assertTrue(self.mod._handle_key_event(up))

        latest.whisper_action.handleMouseClickEvent.assert_called_once_with(latest.whisper)
        self.popup.whisper_action.handleMouseClickEvent.assert_not_called()

    def test_test_shortcuts_require_dev_mode(self):
        self.mod.BigWorld.isKeyDown = lambda key: key == self.mod.Keys.KEY_LCONTROL
        event = SimpleNamespace(key=self.mod.Keys.KEY_F9, isKeyDown=lambda: True)
        self.assertFalse(self.mod._handle_key_event(event))
        self.assertFalse(self.mod._test_friend_pending)
        self.mod._dev_mode = True
        self.assertTrue(self.mod._handle_key_event(event))
        self.assertEqual(list(self.mod._test_friend_pending), [True])

    def test_send_shortcut_does_not_target_expired_popup(self):
        self.mod._whisper_hotkey = (20, {"CTRL"})
        self.mod.BigWorld.isKeyDown = lambda key: key == self.mod.Keys.KEY_LCONTROL
        self.popup.expires_at = 0
        event = SimpleNamespace(key=20, isKeyDown=lambda: True)

        self.assertFalse(self.mod._handle_key_event(event))

        self.popup.whisper_action.handleMouseClickEvent.assert_not_called()

    def test_configured_shortcut_and_invalid_config_fallback(self):
        for setting, expected in (("ALT+T", (20, {"ALT"})), ("CTRL+F9", (20, {"CTRL"})),
                                  ("CTRL+F10", (20, {"CTRL"})), ("CTRL+F8", (119, {"CTRL"})),
                                  ("CTRL+CTRL+T", (20, {"CTRL"})), (None, (20, {"CTRL"}))):
            with self.subTest(setting=setting):
                with patch("builtins.open", mock_open(read_data=json.dumps({"whisper_hotkey": setting}))):
                    self.mod._load_settings()
                self.assertEqual(self.mod._whisper_hotkey, expected)

    def test_menu_key_capture_does_not_send_a_message(self):
        self.mod._whisper_hotkey = (20, {"CTRL"})
        self.mod._settings_open = True
        self.mod.BigWorld.isKeyDown = lambda key: key == self.mod.Keys.KEY_LCONTROL
        event = SimpleNamespace(key=20, isKeyDown=lambda: True)

        self.assertFalse(self.mod._handle_key_event(event))

        self.original.assert_called_once_with(event)
        self.popup.whisper_action.handleMouseClickEvent.assert_not_called()
