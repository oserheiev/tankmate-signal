import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_notifications import load_mod


class ModsSettingsTests(unittest.TestCase):
    def setUp(self):
        self.mod, _ = load_mod()
        self.mod._set_whisper_hotkey("CTRL+T")
        self.window = SimpleNamespace(flashObject=Mock())
        self.panel = self.mod.ModsSettings(self.window)
        self.mod._settings_panel = self.panel
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "configs" / "tankmate_signal.json"
        self.mod._CONFIG_PATH = str(self.path)

    def test_apply_persists_both_settings_without_losing_other_config(self):
        self.path.parent.mkdir()
        self.path.write_text(json.dumps({"whisper_hotkey": "CTRL+T", "other": 42}))
        self.panel.stage("ALT+T")
        self.panel.on_change({"action": "dev_mode", "value": True})
        self.assertFalse(self.mod._dev_mode)
        self.assertEqual(self.mod._whisper_hotkey_label, "Ctrl+T")

        self.assertTrue(self.panel.apply())

        self.assertEqual(json.loads(self.path.read_text()),
                         {"whisper_hotkey": "Alt+T", "dev_mode": True, "other": 42})
        self.assertEqual(self.mod._whisper_hotkey, (20, {"ALT"}))
        self.assertTrue(self.mod._dev_mode)
        self.mod._dev_mode = False
        self.mod._load_settings()
        self.assertTrue(self.mod._dev_mode)
        self.assertFalse(self.panel.dirty)

    def test_dev_mode_defaults_off_and_accepts_only_boolean_config(self):
        self.path.parent.mkdir()
        for value, expected in ((None, False), ("true", False), (False, False), (True, True)):
            with self.subTest(value=value):
                data = {} if value is None else {"dev_mode": value}
                self.path.write_text(json.dumps(data))
                self.mod._load_settings()
                self.assertIs(self.mod._dev_mode, expected)

    def test_clear_binding_is_staged_until_apply(self):
        self.panel.stage("")
        self.assertEqual(self.mod._whisper_hotkey_label, "Ctrl+T")
        self.assertTrue(self.panel.apply())
        self.assertIsNone(self.mod._whisper_hotkey)

    def test_flash_key_capture_keeps_modifiers_and_rejects_reserved_shortcuts(self):
        self.panel.on_change({"action": "capture"})
        self.mod.BigWorld.isKeyDown = lambda key: key == self.mod.Keys.KEY_LCONTROL
        self.panel.on_change({"action": "key", "code": 120})
        self.assertTrue(self.panel.capturing)
        self.assertFalse(self.panel.dirty)
        self.mod.BigWorld.isKeyDown = lambda key: key in (self.mod.Keys.KEY_LALT, self.mod.Keys.KEY_LSHIFT)
        self.panel.on_change({"action": "key", "code": 84})
        self.assertEqual(self.panel.shortcut, "Alt+Shift+T")
        self.assertFalse(self.panel.capturing)

    def test_escape_cancels_capture_and_backspace_clears_binding(self):
        self.panel.on_change({"action": "capture"})
        self.panel.on_change({"action": "key", "code": 27})
        self.assertFalse(self.panel.capturing)
        self.assertFalse(self.panel.dirty)
        self.panel.on_change({"action": "capture"})
        self.panel.on_change({"action": "key", "code": 8})
        self.assertEqual(self.panel.shortcut, "")
        self.assertFalse(self.panel.capturing)

    def test_failed_replace_restores_config_and_preserves_both_active_values(self):
        self.path.parent.mkdir()
        original = '{"whisper_hotkey": "CTRL+T", "dev_mode": false}'
        self.path.write_text(original)
        rename = self.mod.os.rename

        def fail_new_file(source, destination):
            if str(source).endswith(".tmp"):
                raise OSError("replace failed")
            return rename(source, destination)

        self.panel.stage("ALT+T")
        self.panel.on_change({"action": "dev_mode", "value": True})
        with patch.object(self.mod.os, "rename", side_effect=fail_new_file):
            self.assertFalse(self.panel.apply())
        self.assertEqual(self.path.read_text(), original)
        self.assertEqual(self.mod._whisper_hotkey_label, "Ctrl+T")
        self.assertFalse(self.mod._dev_mode)
        self.assertTrue(self.panel.dirty)


class ModsSettingsHookTests(unittest.TestCase):
    def setUp(self):
        self.mod, _ = load_mod()
        self.cls = type("SettingsWindow", (), {
            "_populate": Mock(), "_dispose": Mock(), "_SettingsWindow__apply": Mock(return_value="applied"),
            "onSettingsChange": Mock()})
        self.view_settings = type("ViewSettings", (), {
            "getDAAPIObject": lambda value: {"alias": value.alias, "url": "settingsWindow.swf"}})
        self.mod._install_settings_hooks(self.cls, self.view_settings)
        self.window = self.cls()
        self.window.flashObject = Mock()

    def test_only_settings_view_uses_bundled_ui_and_cleanup_restores_loader(self):
        settings = self.view_settings()
        settings.alias = "settingsWindow"
        other = self.view_settings()
        other.alias = "simpleDialog"
        self.assertEqual(settings.getDAAPIObject()["url"], "tankmateSettings.swf")
        self.assertEqual(other.getDAAPIObject()["url"], "settingsWindow.swf")
        self.mod._unregister_settings()
        self.assertEqual(settings.getDAAPIObject()["url"], "settingsWindow.swf")

    def test_cancel_discards_pending_hotkey_and_dev_mode(self):
        self.mod._set_whisper_hotkey("CTRL+T")
        self.window._populate()
        self.assertTrue(self.mod._settings_open)
        self.mod._settings_panel.stage("ALT+T")
        self.mod._settings_panel.on_change({"action": "dev_mode", "value": True})
        self.window._dispose()
        self.assertFalse(self.mod._settings_open)
        self.assertIsNone(self.mod._settings_panel)
        self.assertEqual(self.mod._whisper_hotkey_label, "Ctrl+T")
        self.assertFalse(self.mod._dev_mode)

    def test_mod_callbacks_do_not_preview_stock_settings(self):
        self.window._populate()
        original = self.mod._settings_hooks["onSettingsChange"][0]
        self.window.onSettingsChange("tankmate.signal", {"action": "dev_mode", "value": True})
        original.assert_not_called()
        self.window.onSettingsChange("keyboard", {"forward": 87})
        original.assert_called_once_with(self.window, "keyboard", {"forward": 87})

    def test_failed_mod_save_still_applies_native_settings(self):
        self.window._populate()
        original = self.mod._settings_hooks["_SettingsWindow__apply"][0]
        with patch.object(self.mod._settings_panel, "apply", return_value=False):
            result = self.window._SettingsWindow__apply({"native_setting": True}, False, True)
        original.assert_called_once_with(self.window, {"native_setting": True}, False, True)
        self.assertEqual(result, "applied")


if __name__ == "__main__":
    unittest.main()
