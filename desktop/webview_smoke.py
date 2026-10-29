"""Exercise both native renderers and the real isolated workbench service."""
import tempfile
import threading
import time
from pathlib import Path


def smoke():
    import webview
    from desktop.controller import Controller
    from desktop.launcher import prepare_home
    from desktop.web_shell import ShellServer
    from desktop.workbench_window import WorkbenchWindow

    failures = []
    with tempfile.TemporaryDirectory(prefix="creatorhub-webview-") as temp:
        home = Path(temp)
        prepare_home(home)
        controller = Controller(home, install_browser=False)
        server = ShellServer(controller)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        window = webview.create_window("CreatorHub renderer test", server.origin, hidden=True)
        allow_close = threading.Event()
        workspace = WorkbenchWindow(webview, controller, window, lambda: False, allow_close)
        controller.open_workbench = workspace.open
        controller.show_manager = workspace.show_manager

        def verify():
            try:
                deadline = time.monotonic() + 45
                while time.monotonic() < deadline:
                    result = window.evaluate_js("document.body.innerText") or ""
                    if "启动本地服务" in result:
                        break
                    time.sleep(.3)
                else:
                    raise AssertionError("Desktop renderer did not load real stopped state: " + result)
                window.evaluate_js("location.hash = '#/settings'")
                time.sleep(1)
                assert "跟随系统" in window.evaluate_js("document.body.innerText")
                assert "检查更新" in window.evaluate_js("document.body.innerText")
                assert window.evaluate_js("document.querySelectorAll('main').length") == 1
                # Start exactly as the EXE does: the real controller opens the
                # owned service inside a second native window, not a browser.
                controller.preferences["open_on_ready"] = False
                controller.start()
                deadline = time.monotonic() + 60
                while time.monotonic() < deadline:
                    if workspace.window:
                        text = workspace.window.evaluate_js("document.body.innerText") or ""
                        if "KK-Tiong_Pavelio" in text and "洞察工作台" in text:
                            break
                    time.sleep(.25)
                else:
                    raise AssertionError("Native modified workbench did not load: " + controller.phase)
                client = workspace.window
                client.evaluate_js("document.querySelector('[aria-label=\"关闭新手向导\"]')?.click()")
                assert client.evaluate_js("typeof window.openInsightWorkspace") == "function"
                client.evaluate_js("window.openInsightWorkspace()")
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    if "返回采集任务" in (client.evaluate_js("document.body.innerText") or ""):
                        break
                    time.sleep(.2)
                else:
                    raise AssertionError("Native insights entry did not open")
                workspace.show_manager()
                controller.action("open_panel", {})
                assert workspace.window is client
                controller.stop()
                controller.worker.join(timeout=40)
                assert controller.phase == "stopped", controller.phase
            except Exception as exc:
                failures.append(str(exc))
            finally:
                controller.stop()
                if controller.worker:
                    controller.worker.join(timeout=40)
                allow_close.set()
                workspace.destroy()

        try:
            webview.start(verify, gui="edgechromium")
        finally:
            server.shutdown()
            server.server_close()
    if failures:
        raise AssertionError("; ".join(failures))
    print("PASS native WebView2 workbench, insights, manager return and service shutdown")
    return 0
