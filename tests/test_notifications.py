import contextlib
import io
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch


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
    stub("GUI")
    stub("ResMgr", isFile=Mock())
    stub("SoundGroups")
    stub("PlayerEvents", g_playerEvents=Mock())
    stub("gui.app_loader.settings", APP_NAME_SPACE=Mock())
    stub("gui.Scaleform.daapi.view.battle.shared.page", SharedPage=Mock())
    stub("gui.Scaleform.genConsts.PLAYERS_PANEL_STATE", PLAYERS_PANEL_STATE=Mock())
    stub("gui.Scaleform.Waiting", Waiting=Mock())
    stub("gui.shared.personality", ServicesLocator=Mock())
    stub("helpers", getClientLanguage=Mock(return_value="en"))
    stub("helpers.gui_utils", setPixMode=Mock())
    stub("messenger.m_constants", PROTO_TYPE=Mock(), USER_TAG=Mock(),
         USER_ACTION_ID=SimpleNamespace(FRIEND_ADDED=1, FRIEND_REMOVED=2,
                                        IGNORED_ADDED=3, TMP_IGNORED_ADDED=4))
    stub("messenger.proto.events", g_messengerEvents=Mock())
    stub("messenger.proto.shared_find_criteria", FriendsFindCriteria=Mock())
    stub("messenger.storage", MessengerStorageDescriptor=Mock(return_value=Mock()),
         UsersStorage=Mock())
    stub("skeletons.gui.app_loader", ApplicationStateID=Mock(), GuiGlobalSpaceID=Mock())

    source = SOURCE.read_bytes()
    if test_alert:
        source = source.replace(b"_SHOW_TEST_NOTIFICATION = False", b"_SHOW_TEST_NOTIFICATION = True")
    mod = ModuleType("tankmate_under_test")
    with patch.dict(sys.modules, modules):
        exec(compile(source, str(SOURCE), "exec"), mod.__dict__)
    mod._log = Mock()
    return mod, window


def contact(name, online, friend=True):
    return SimpleNamespace(getStorageKey=lambda: (name, "xmpp"), getName=lambda: name,
                           isOnline=lambda: online, isFriend=lambda: friend)


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

    def record_popup(self, name, online, scene, now, position, anchor):
        self.mod._visible_popups.append(Mock(expires_at=now + 5, paused_at=None, entry_elapsed=1.0))

    def tick(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            self.mod._tick()
        self.assertEqual(errors.getvalue(), "")

    def test_pending_waits_through_loading_and_minimization_and_uses_three_slots(self):
        self.configure()
        for name in ("A", "B", "C", "D"):
            self.mod._presence.pending[name] = (name, True)
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
