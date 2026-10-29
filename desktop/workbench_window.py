"""Native workbench window using the same served UI as the browser edition."""
import threading
from urllib.parse import urlsplit


class WorkbenchWindow:
    def __init__(self, webview, controller, manager, request_close, allow_close):
        self.webview = webview
        self.controller = controller
        self.manager = manager
        self.request_close = request_close
        self.allow_close = allow_close
        self.window = None
        self.origin = None
        self.lock = threading.RLock()

    def open(self, url):
        # The privileged service manager stays on its own origin. The workbench
        # receives no Python bridge or service-control token.
        parts = urlsplit(url)
        if (parts.scheme != "http" or parts.hostname != "127.0.0.1"
                or not parts.port or parts.username or parts.password
                or parts.path not in {"", "/"} or parts.query or parts.fragment
                or url != self.controller.url):
            raise ValueError("工作台地址与本次本地服务不一致。")
        with self.lock:
            if self.allow_close.is_set():
                return
            if self.window is None:
                self.window = self.webview.create_window(
                    "CreatorHub · 多平台内容工作台 · 开发：KK-Tiong_Pavelio",
                    url.rstrip("/") + "/#collections", width=1440, height=960,
                    min_size=(860, 640), background_color="#10141c", text_select=True)
                self.window.events.closing += self.request_close
                self.window.events.loaded += self._loaded
            elif self.origin != url:
                self.window.load_url(url.rstrip("/") + "/#collections")
            self.origin = url
            self.window.show()
            self.window.restore()
            self.manager.hide()

    def _loaded(self):
        if self.controller.phase == "ready" and not self.allow_close.is_set():
            self.manager.hide()

    def show_manager(self):
        if not self.allow_close.is_set():
            self.manager.show()
            self.manager.restore()

    def restore(self):
        if self.controller.phase == "ready" and self.controller.url:
            self.open(self.controller.url)
        else:
            self.show_manager()

    def hide(self):
        if self.window:
            self.window.hide()
        self.manager.hide()

    def destroy(self):
        if self.window:
            self.window.destroy()
        self.manager.destroy()
