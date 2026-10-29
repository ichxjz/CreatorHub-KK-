"""Native workbench navigation, controller dispatch and shutdown behavior."""
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from desktop.controller import Controller
from desktop.launcher import prepare_home
from desktop.workbench_window import WorkbenchWindow


class Event:
    def __init__(self):
        self.handlers = []

    def __iadd__(self, handler):
        self.handlers.append(handler)
        return self


def window():
    value = Mock()
    value.events.loaded = Event()
    value.events.closing = Event()
    return value


class WorkbenchTests(unittest.TestCase):
    def setUp(self):
        self.webview = Mock()
        self.webview.create_window.return_value = window()
        self.controller = Mock(url="http://127.0.0.1:39001", phase="ready")
        self.manager = window()
        self.closing = Mock(return_value=False)
        self.allow = threading.Event()
        self.workspace = WorkbenchWindow(self.webview, self.controller, self.manager, self.closing, self.allow)

    def test_open_reuses_window_without_resetting_current_workbench_state(self):
        self.workspace.open(self.controller.url)
        self.workspace.show_manager()
        self.workspace.open(self.controller.url)
        self.webview.create_window.assert_called_once()
        options = self.webview.create_window.call_args.kwargs
        self.assertNotIn("js_api", options)
        self.assertEqual(self.webview.create_window.call_args.args[1], self.controller.url + "/#collections")
        self.workspace.window.load_url.assert_not_called()
        self.assertIn(self.closing, self.workspace.window.events.closing.handlers)

    def test_service_restart_navigates_to_new_owned_port(self):
        self.workspace.open(self.controller.url)
        self.controller.url = "http://127.0.0.1:39002"
        self.workspace.restore()
        self.workspace.window.load_url.assert_called_once_with(self.controller.url + "/#collections")
        self.assertEqual(self.webview.create_window.call_count, 1)

    def test_external_or_unowned_origin_never_becomes_client_workbench(self):
        for url in ("https://example.com", "http://127.0.0.1:39002", self.controller.url + "/api", "http://user@127.0.0.1:39001"):
            with self.assertRaises(ValueError):
                self.workspace.open(url)
        self.webview.create_window.assert_not_called()

    def test_stopped_service_restores_manager_and_exit_destroys_both_windows(self):
        self.workspace.open(self.controller.url)
        self.controller.phase = "error"
        self.workspace.restore()
        self.manager.show.assert_called()
        self.workspace.hide()
        self.workspace.window.hide.assert_called_once()
        self.allow.set()
        self.workspace.destroy()
        self.workspace.window.destroy.assert_called_once()
        self.manager.destroy.assert_called_once()
        self.workspace.open(self.controller.url)
        self.assertEqual(self.webview.create_window.call_count, 1)

    def test_controller_uses_native_workbench_and_browser_source_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            prepare_home(home)
            controller = Controller(home, install_browser=False)
            with self.assertRaises(ValueError):
                controller.open_panel()
            controller.url, controller.phase = "http://127.0.0.1:39001", "ready"
            controller.open_workbench = Mock()
            with patch("desktop.controller.webbrowser.open") as external:
                controller.action("open_panel", {})
                controller.open_workbench.assert_called_once_with(controller.url)
                external.assert_not_called()
                controller.open_workbench = None
                controller.action("open_panel", {})
                external.assert_called_once_with(controller.url)


if __name__ == "__main__":
    unittest.main()
