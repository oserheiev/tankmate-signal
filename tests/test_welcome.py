import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from test_notifications import load_mod


class WelcomeTests(unittest.TestCase):
    def setUp(self):
        self.mod, _ = load_mod()
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'config.json'
        self.mod._CONFIG_PATH = str(self.path)

    def test_only_explicit_true_skips_the_welcome_on_future_launches(self):
        for value, expected in ((None, False), ('true', False), (False, False), (True, True)):
            with self.subTest(value=value):
                self.path.write_text(json.dumps({'welcome_read': value}))
                self.mod._load_settings()
                self.assertIs(self.mod._welcome_read, expected)

    def test_acknowledgement_preserves_other_config_and_reloads(self):
        self.path.write_text(json.dumps({'whisper_hotkey': 'ALT+T', 'dev_mode': True, 'other': 42}))
        self.assertTrue(self.mod._acknowledge_welcome())
        self.assertEqual(json.loads(self.path.read_text()), {
            'whisper_hotkey': 'ALT+T', 'dev_mode': True, 'other': 42, 'welcome_read': True})
        self.mod._welcome_read = False
        self.mod._load_settings()
        self.assertTrue(self.mod._welcome_read)

    def test_failed_acknowledgement_does_not_mark_read(self):
        with patch.object(self.mod, '_save_config', side_effect=OSError('read only')):
            self.assertFalse(self.mod._acknowledge_welcome())
        self.assertFalse(self.mod._welcome_read)
        self.mod.SystemMessages.pushMessage.assert_called_once()

    def test_shown_only_once_in_a_garage_session_without_implicitly_acknowledging(self):
        self.mod._open_welcome = Mock(return_value=True)
        self.mod._maybe_show_welcome('battle')
        self.mod._maybe_show_welcome('other')
        self.mod._open_welcome.assert_not_called()
        self.mod._maybe_show_welcome('hangar')
        self.mod._on_disconnected()
        self.mod._maybe_show_welcome('hangar')
        self.mod._open_welcome.assert_called_once()
        self.assertFalse(self.mod._welcome_read)
        self.assertFalse(self.path.exists())

    def test_unavailable_or_blocked_dialog_is_deferred(self):
        self.mod._open_welcome = Mock(side_effect=[False, True])
        self.mod._settings_open = True
        self.mod._maybe_show_welcome('hangar')
        self.mod._open_welcome.assert_not_called()
        self.mod._settings_open = False
        self.mod._maybe_show_welcome('hangar')
        self.assertFalse(self.mod._welcome_shown)
        self.mod._maybe_show_welcome('hangar')
        self.assertTrue(self.mod._welcome_shown)

    def test_acknowledged_installation_does_not_open_dialog(self):
        self.mod._welcome_read = True
        self.mod._open_welcome = Mock()
        self.mod._maybe_show_welcome('hangar')
        self.mod._open_welcome.assert_not_called()

    def test_open_waits_for_focused_garage_without_another_modal(self):
        focus = Mock(return_value=True)
        app = self.mod.ServicesLocator.appLoader.getApp.return_value
        app.isModalViewShown.return_value = False
        view = SimpleNamespace(alias='store')
        app.containerManager.getView.return_value = view
        self.mod._register_welcome = Mock()
        modules = {
            'Windowing': SimpleNamespace(isWindowAccessible=focus),
            'frameworks.wulf': SimpleNamespace(WindowLayer=SimpleNamespace(SUB_VIEW=2)),
            'gui.Scaleform.daapi.settings.views': SimpleNamespace(VIEW_ALIAS=SimpleNamespace(
                LOBBY_HANGAR='hangar', LEGACY_LOBBY_HANGAR='legacyHangar')),
            'gui.Scaleform.framework.managers.loaders': SimpleNamespace(SFViewLoadParams=Mock()),
        }
        with patch.dict('sys.modules', modules):
            self.assertFalse(self.mod._open_welcome())
            view.alias = 'hangar'
            focus.return_value = False
            self.assertFalse(self.mod._open_welcome())
            focus.return_value = True
            app.isModalViewShown.return_value = True
            self.assertFalse(self.mod._open_welcome())
            app.isModalViewShown.return_value = False
            for alias in ('hangar', 'legacyHangar'):
                view.alias = alias
                self.assertTrue(self.mod._open_welcome())
        self.assertEqual(app.loadView.call_count, 2)
        app.containerManager.getView.assert_called_with(2)

    def test_minimized_client_defers_welcome(self):
        self.mod._visible_scene = Mock(return_value='hangar')
        self.mod._open_welcome = Mock(return_value=True)
        self.mod.BigWorld.isWindowVisible.return_value = False
        self.mod._tick()
        self.mod._open_welcome.assert_not_called()
        self.assertFalse(self.mod._welcome_shown)

    def test_native_submit_keeps_dialog_open_on_save_failure_and_disposes_cleanly(self):
        class NativeDialog(object):
            def __init__(self, *args, **kwargs):
                self.destroy = Mock()
                self.flashObject = Mock()

            def _populate(self):
                pass

            def _dispose(self):
                pass

        factory = Mock()
        self.mod.dependency.instance.return_value = SimpleNamespace(entitiesFactory=factory)
        modules = {
            'frameworks.wulf': SimpleNamespace(WindowLayer=SimpleNamespace(TOP_WINDOW=10)),
            'gui.Scaleform.framework': SimpleNamespace(GroupedViewSettings=lambda *args, **kw: args,
                ScopeTemplates=SimpleNamespace(DEFAULT_SCOPE='default', DYNAMIC_SCOPE='dynamic')),
            'gui.Scaleform.daapi.view.dialogs.SimpleDialog': SimpleNamespace(SimpleDialog=NativeDialog),
            'skeletons.gui.impl': SimpleNamespace(IGuiLoader=object),
        }
        with patch.dict('sys.modules', modules):
            self.mod._register_welcome()
            dialog_class = factory.addSettings.call_args.args[0][1]
            dialog = dialog_class()
            dialog._populate()
            self.assertIs(self.mod._welcome_view, dialog)
            with patch.object(self.mod, '_acknowledge_welcome', side_effect=[False, True]):
                dialog.onButtonClick('submit')
                dialog.destroy.assert_not_called()
                dialog.onButtonClick('submit')
                dialog.destroy.assert_called_once()
            dialog._dispose()
            self.assertIsNone(self.mod._welcome_view)
            self.mod._unregister_welcome()
            factory.removeSettings.assert_called_once_with(self.mod._WELCOME_ALIAS)

    def test_preview_uses_current_or_disabled_binding_and_locale_fallback(self):
        self.mod.getClientLanguage.return_value = 'unknown'
        self.mod.ResMgr.isFile.side_effect = lambda path: '-en-' in path
        self.mod._set_whisper_hotkey('ALT+T')
        payload = self.mod._welcome_payload()
        self.assertIn('Alt+T', payload['message'])
        self.assertEqual(payload['shortcut'], 'Alt+T')
        self.assertEqual(payload['intro'], 'Know when your friends are ready to play.')
        self.assertTrue(payload['buttonImage'].endswith('whisper-en-ready.png'))
        self.mod._set_whisper_hotkey('')
        payload = self.mod._welcome_payload()
        self.assertEqual(payload['shortcut'], '')
        self.assertNotIn('press', payload['message'])
