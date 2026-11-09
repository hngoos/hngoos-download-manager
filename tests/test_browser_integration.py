"""Opt-in Chromium acceptance tests; no access to an existing browser profile."""

import os
import tempfile
import time
import unittest
from pathlib import Path


@unittest.skipUnless(os.environ.get("HNGOOS_BROWSER_TESTS") == "1", "Set HNGOOS_BROWSER_TESTS=1")
class BrowserIntegrationTests(unittest.TestCase):
    def test_popup_is_usable_without_native_host_in_both_languages_and_themes(self):
        import json
        import shutil

        from playwright.sync_api import sync_playwright

        source_extension = Path(__file__).resolve().parents[1]/"browser-extension"
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as playwright:
            extension = Path(folder)/"extension"
            shutil.copytree(source_extension, extension)
            manifest = json.loads((extension/"manifest.json").read_text(encoding="utf-8"))
            manifest["host_permissions"] = ["https://example.com/*"]
            (extension/"manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            context = playwright.chromium.launch_persistent_context(str(Path(folder)/"profile"), headless=True, channel="chromium",
                args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"])
            try:
                worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                extension_id = worker.url.split("/")[2]
                for language in ("en", "vi"):
                    for theme in ("light", "dark"):
                        worker.evaluate("settings => chrome.storage.local.set(settings)", {"language": language, "theme": theme})
                        page = context.new_page()
                        page.set_viewport_size({"width": 360, "height": 580})
                        errors = []
                        page.on("pageerror", lambda error, errors=errors: errors.append(str(error)))
                        if theme == "light":
                            page.add_init_script("chrome.runtime.sendNativeMessage = () => new Promise(() => {});")
                        else:
                            page.add_init_script("chrome.runtime.sendNativeMessage = async () => "
                                f"({json.dumps({'ok': True, 'language': language, 'theme': theme})});")
                        page.goto(f"chrome-extension://{extension_id}/popup.html")
                        page.locator("#download svg").wait_for()
                        self.assertEqual(page.locator("#ping").count(), 0)
                        self.assertTrue(page.locator("#download").is_disabled())
                        self.assertTrue(page.locator("#session").is_disabled())
                        self.assertEqual(page.locator("html").get_attribute("lang"), language)
                        self.assertEqual(page.locator("html").get_attribute("data-theme"), theme)
                        self.assertTrue(page.evaluate("document.documentElement.scrollWidth <= innerWidth && document.documentElement.scrollHeight <= innerHeight"))
                        self.assertTrue(page.locator(".brand img").evaluate("image => image.complete && image.naturalWidth >= 44"))
                        self.assertEqual(page.locator("#download svg, #video svg").count(), 2)
                        artifacts = os.environ.get("HNGOOS_BROWSER_ARTIFACTS")
                        if artifacts:
                            Path(artifacts).mkdir(parents=True, exist_ok=True)
                            page.screenshot(path=str(Path(artifacts)/f"popup-{language}-{theme}.png"))
                        self.assertEqual(errors, [])
                        page.close()
                # The popup keeps a real source tab for page/video downloads.
                context.route("https://example.com/hdm-fixture", lambda route: route.fulfill(body="HDM source page"))
                source = context.new_page()
                source.goto("https://example.com/hdm-fixture")
                tab = worker.evaluate("async () => (await chrome.tabs.query({url:'https://example.com/hdm-fixture'}))[0]")
                page = context.new_page()
                page.add_init_script("chrome.runtime.sendNativeMessage = () => new Promise(() => {});"
                    "chrome.permissions.contains = async () => false;"
                    "chrome.permissions.request = async () => false;"
                    "const queryTabs = chrome.tabs.query.bind(chrome.tabs);"
                    f"chrome.tabs.query = async query => query.active ? [{json.dumps(tab)}] : queryTabs(query);")
                page.goto(f"chrome-extension://{extension_id}/popup.html")
                page.locator("#download").wait_for()
                self.assertTrue(page.locator("#download").is_enabled())
                page.locator("#takeover").click()
                page.wait_for_function("!document.getElementById('takeover').checked")
                self.assertEqual(page.locator("#status").inner_text(), "Chưa được cấp quyền.")
                page.locator("#settings").click()
                deadline = time.monotonic()+5
                while not any(p.url.endswith("/options.html") for p in context.pages):
                    self.assertLess(time.monotonic(), deadline)
                    page.wait_for_timeout(50)
                options = next(p for p in context.pages if p.url.endswith("/options.html"))
                options.locator("#status").wait_for()
                self.assertEqual(options.locator("button").count(), 0)
                self.assertEqual(worker.evaluate("async () => (await chrome.storage.session.get('optionsTabId')).optionsTabId"), tab["id"])
            finally:
                context.close()

    def test_insert_bypass_registers_in_chromium_and_tracks_trusted_keyboard_input(self):
        import json
        import shutil
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        from playwright.sync_api import sync_playwright
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                data = b"<!doctype html><h1>HDM capture keyboard fixture</h1>"
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as folder, sync_playwright() as playwright:
                extension = Path(folder)/"extension"
                source = Path(__file__).resolve().parents[1]/"browser-extension"
                shutil.copytree(source, extension, ignore=shutil.ignore_patterns("node_modules", "test"))
                manifest = json.loads((extension/"manifest.json").read_text(encoding="utf-8"))
                manifest["host_permissions"] = ["<all_urls>"]
                (extension/"manifest.json").write_text(json.dumps(manifest))
                if os.name == "nt":
                    import ctypes
                    from ctypes import wintypes
                    short_path = ctypes.windll.kernel32.GetShortPathNameW
                    short_path.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
                    buffer = ctypes.create_unicode_buffer(32768)
                    length = short_path(str(extension), buffer, len(buffer))
                    self.assertGreater(length, 0)
                    extension = Path(buffer.value)
                context = playwright.chromium.launch_persistent_context(str(Path(folder)/"profile"),
                    headless=True, channel="chromium", args=[f"--load-extension={extension}",
                    f"--disable-extensions-except={extension}"])
                try:
                    worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                    from hngoos_dm.browser import unpacked_extension_id
                    self.assertEqual(worker.url.split("/")[2], unpacked_extension_id(extension))
                    panel = context.new_page()
                    panel.goto(f"chrome-extension://{worker.url.split('/')[2]}/options.html")
                    panel.evaluate("async()=>{const module=await import(chrome.runtime.getURL('capture-settings.js'));"
                                   "await module.syncInsertCapture(chrome,true);}")
                    page = context.new_page()
                    page.goto(f"http://127.0.0.1:{server.server_port}/")
                    page.keyboard.down("Insert")
                    page.wait_for_timeout(150)
                    value = worker.evaluate("async()=> (await chrome.storage.local.get('insertBypass')).insertBypass")
                    self.assertIsNotNone(value)
                    self.assertGreater(value["until"], time.time()*1000)
                    # Headless Chromium may keep the options tab active even
                    # while Playwright sends trusted keys to the fixture page.
                    tab_id = worker.evaluate("async url => (await chrome.tabs.query({url}))[0].id", page.url)
                    self.assertEqual(value["tabId"], tab_id)
                    page.keyboard.up("Insert")
                    page.wait_for_timeout(650)
                    after = worker.evaluate("async()=> (await chrome.storage.local.get('insertBypass')).insertBypass")
                    self.assertLess(after["until"], time.time()*1000)
                finally:
                    context.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_detected_stream_preserves_page_contents_and_normal_popups(self):
        import json
        import shutil
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        from playwright.sync_api import sync_playwright

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                if self.path.startswith("/stream"):
                    data, content_type = b"#EXTM3U\n#EXT-X-ENDLIST", "application/vnd.apple.mpegurl"
                else:
                    data = (b'<h1 id="headline">Keep this heading</h1><main>Keep this article</main>'
                            b'<div id="promotion">Optional promotion</div><video></video>'
                            b'<button onclick="window.open(\'http://localhost:'+str(self.server.server_port).encode()
                            +b'/ad\')">Open ad</button>')
                    content_type = "text/html"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as directory, sync_playwright() as playwright:
                root = Path(directory)
                extension = root/"extension"
                source = Path(__file__).resolve().parents[1]/"browser-extension"
                shutil.copytree(source, extension, ignore=shutil.ignore_patterns("node_modules", "test"))
                manifest = json.loads((extension/"manifest.json").read_text(encoding="utf-8"))
                manifest["host_permissions"] = ["<all_urls>"]
                (extension/"manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
                context = playwright.chromium.launch_persistent_context(str(root/"profile"),
                    headless=True, channel="chromium", args=[f"--disable-extensions-except={extension}",
                    f"--load-extension={extension}"])
                try:
                    worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                    panel = context.new_page()
                    panel.goto(f"chrome-extension://{worker.url.split('/')[2]}/options.html")
                    page = context.new_page()
                    url = f"http://127.0.0.1:{server.server_port}/page"
                    page.goto(url)
                    tab_id = panel.evaluate("async url => (await chrome.tabs.query({url}))[0].id", url)
                    page.evaluate("fetch('/stream?token=fixture').then(r=>r.text())")
                    panel.wait_for_function("async id => (await chrome.runtime.sendMessage({action:'media-candidates',tabId:id})).items.length === 1", arg=tab_id)
                    stream = panel.evaluate("id => chrome.runtime.sendMessage({action:'media-candidates',tabId:id})", tab_id)
                    self.assertEqual(stream["items"][0]["kind"], "HLS")
                    for action in ('pick-element', 'reset-site', 'stats', 'invoice-enable'):
                        panel.evaluate("action=>chrome.runtime.sendMessage({action}).catch(()=>null)", action)
                    self.assertTrue(page.locator("#headline").is_visible())
                    self.assertTrue(page.locator("#promotion").is_visible())
                    with context.expect_page() as opened:
                        page.get_by_role("button", name="Open ad").click()
                    popup = opened.value
                    popup.wait_for_load_state()
                    self.assertTrue(popup.url.endswith("/ad"))
                    self.assertFalse(popup.is_closed())
                    self.assertTrue(page.locator("video").is_visible())
                finally:
                    context.close()
        finally:
            server.shutdown()
            server.server_close()

    def test_website_capture_includes_source_timestamp_and_real_page(self):
        import threading
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        import pypdfium2 as pdfium

        from hngoos_dm.capture import capture_page
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                data = b"<!doctype html><title>Receipt</title><h1>ORDER-TEST-001</h1><p>Capture acceptance fixture</p>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                url = f"http://127.0.0.1:{server.server_port}/receipt"
                output = capture_page(url, Path(folder)/"receipt.pdf", channel=None)
                with pdfium.PdfDocument(output) as pdf:
                    page = pdf[0]
                    text = page.get_textpage()
                    value = text.get_text_range()
                    text.close()
                    page.close()
                    self.assertIn("ORDER-TEST-001", value)
                    self.assertIn("127.0.0.1", value)
                image = capture_page(url, Path(folder)/"receipt.png", image=True, channel=None)
                self.assertGreater(image.stat().st_size, 1000)
        finally:
            server.shutdown()
            server.server_close()

    def test_extension_loads_options_page_and_renders_video_button_outside_video(self):
        from playwright.sync_api import sync_playwright
        extension = Path(__file__).resolve().parents[1]/"browser-extension"
        with tempfile.TemporaryDirectory() as profile, sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(profile, headless=True, channel="chromium",
                args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"])
            try:
                worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                extension_id = worker.url.split("/")[2]
                page = context.new_page()
                page.goto(f"chrome-extension://{extension_id}/options.html")
                self.assertEqual(page.locator("button").count(), 0)
                page.wait_for_function("() => document.querySelector('#status').textContent.length > 0")
                self.assertTrue(page.locator("#status").inner_text())
                page = context.new_page()
                page.set_content("<html><body><video src='https://example.com/video.mp4'></video></body></html>")
                # Execute the same isolated-world button insertion script, with a safe local mock for transport.
                page.evaluate("globalThis.__hngoosMessages=0;globalThis.chrome={runtime:{sendMessage:async()=>{globalThis.__hngoosMessages++;return {ok:true}}}}")
                page.add_script_tag(path=str(extension/"video.js"))
                button = page.locator("button")
                self.assertEqual(button.count(), 1)
                self.assertTrue(page.evaluate("document.querySelector('video').previousElementSibling.tagName==='BUTTON'"))
                page.evaluate("document.querySelector('button').click()")
                self.assertEqual(page.evaluate("globalThis.__hngoosMessages"), 0)
                button.click()
                page.wait_for_function("() => document.querySelector('button').textContent.includes('Đã gửi')")
                self.assertEqual(page.evaluate("globalThis.__hngoosMessages"), 1)
            finally:
                context.close()

    @unittest.skipUnless(os.name == "nt" and os.environ.get("HNGOOS_BRIDGE_EXE"), "Requires packaged native host")
    def test_native_host_receives_download_from_chromium(self):
        import gc
        import json
        import shutil
        import threading
        import time
        import winreg
        from contextlib import ExitStack
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

        from playwright.sync_api import sync_playwright

        from hngoos_dm.instance import InstanceLock
        from hngoos_dm.store import Store
        source_extension = Path(__file__).resolve().parents[1]/"browser-extension"
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass
            def do_GET(self):
                if self.path == "/page":
                    data = b'<a href="/fixture.bin" download>Download fixture</a>'
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                size = 4*1024*1024
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Disposition", 'attachment; filename="fixture.bin"')
                self.send_header("Content-Length", str(size))
                self.end_headers()
                try:
                    for _ in range(size//65536):
                        self.wfile.write(b"x"*65536)
                        self.wfile.flush()
                        time.sleep(0.01)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        selected_browser = os.environ.get("HNGOOS_TEST_BROWSER", "chromium")
        executable = None
        if selected_browser != "chromium":
            from hngoos_dm.browser import find_browser
            self.assertEqual(selected_browser, "opera-gx")
            executable = find_browser(selected_browser)
            self.assertIsNotNone(executable)
        vendor = "Chromium" if selected_browser == "chromium" else r"Google\Chrome"
        registry_path = rf"Software\{vendor}\NativeMessagingHosts\com.hngoos.download_manager"
        registration_paths = [registry_path]
        previous = None
        existed = False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
                previous = winreg.QueryValueEx(key, "")[0]
                existed = True
        except FileNotFoundError:
            pass
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as playwright, ExitStack() as cleanup:
            folder = Path(folder)
            # The live development EXE may have a sidecar targeting its own database.
            # Copy only the standalone host so this fixture never uses that session.
            packaged_host = folder/"HDMBridge.exe"
            shutil.copy2(Path(os.environ["HNGOOS_BRIDGE_EXE"]).resolve(), packaged_host)
            extension = folder/"extension"
            extension.mkdir()
            # Grant the optional downloads capability in this isolated test profile.
            # It exercises the real event pipeline without interacting with a browser permission dialog.
            for path in source_extension.iterdir():
                if path.is_file() and path.suffix in {".js", ".html", ".css", ".json"}:
                    shutil.copy2(path, extension/path.name)
            shutil.copytree(source_extension/"assets", extension/"assets")
            extension_manifest = json.loads((extension/"manifest.json").read_text(encoding="utf-8"))
            (extension/"manifest.json").write_text(json.dumps(extension_manifest), encoding="utf-8")
            data_dir = folder/"data"
            lock = InstanceLock(data_dir/"instance.lock")
            cleanup.callback(lock.close)
            cleanup.callback(server.shutdown)
            cleanup.callback(server.server_close)
            store = Store(data_dir/"downloads.sqlite3")
            context = playwright.chromium.launch_persistent_context(str(folder/"profile"), headless=True,
                channel="chromium" if executable is None else None,
                executable_path=str(executable) if executable else None,
                ignore_default_args=["--disable-extensions"],
                env={**os.environ, "HDM_DATA_DIR": str(data_dir), "HNGOOS_DATA_DIR": str(data_dir)},
                downloads_path=str(folder/"browser-downloads"),
                args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"])
            try:
                worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                extension_id = worker.url.split("/")[2]
                manifest = folder/"host.json"
                manifest.write_text(json.dumps({"name": "com.hngoos.download_manager", "description": "Test host",
                    "type": "stdio", "path": str(packaged_host),
                    "allowed_origins": [f"chrome-extension://{extension_id}/"]}), encoding="utf-8")
                if selected_browser == "opera-gx":
                    # Opera builds can prefer either their own registration or Chrome's.
                    for other_vendor in ("Opera Software", "Chromium"):
                        other_key = rf"Software\{other_vendor}\NativeMessagingHosts\com.hngoos.download_manager"
                        registration_paths.append(other_key)
                        try:
                            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, other_key) as key:
                                saved = winreg.QueryValueEx(key, "")[0]
                        except FileNotFoundError:
                            saved = None
                        def restore(key_path=other_key, value=saved):
                            if value is None:
                                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
                            else:
                                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, value)
                        cleanup.callback(restore)
                        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, other_key) as key:
                            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest))
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
                    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest))
                page = context.new_page()
                page.goto(f"chrome-extension://{extension_id}/options.html")
                result = page.evaluate("chrome.runtime.sendNativeMessage('com.hngoos.download_manager', {action:'ping'})")
                self.assertTrue(result["ok"])
                store.set_setting("language", "vi")
                store.set_setting("theme", "light")
                result = page.evaluate("chrome.runtime.sendNativeMessage('com.hngoos.download_manager', {action:'browser-settings'})")
                self.assertEqual((result["language"], result["theme"]), ("vi", "light"))
                result = page.evaluate("chrome.runtime.sendNativeMessage('com.hngoos.download_manager', {action:'download',id:'real-browser',kind:'file',url:'https://example.com/test.bin',filename:'test.bin'})")
                self.assertTrue(result["ok"])
                self.assertEqual(store.inbox()[0][0], "real-browser")
                self.assertEqual(store.inbox()[0][1]["filename"], "test.bin")
                # Real Chromium event → pause → native EXE URL probe → durable inbox → cancellation.
                page.evaluate("chrome.storage.local.set({takeover:true})")
                url = f"http://127.0.0.1:{server.server_port}/fixture.bin"
                web = context.new_page()
                web.goto(f"http://127.0.0.1:{server.server_port}/page")
                page.evaluate("() => {globalThis.created = new Promise(resolve => chrome.downloads.onCreated.addListener(item => {globalThis.createdItem=item;resolve(item.id)}))}")
                web.get_by_role("link").click()
                download_id = page.evaluate("globalThis.created")
                deadline = time.monotonic()+20
                while not page.evaluate("async () => !!(await chrome.storage.local.get('lastTakeover')).lastTakeover"):
                    if time.monotonic() >= deadline:
                        self.fail("Native takeover was not acknowledged: "+str(page.evaluate("chrome.storage.local.get('lastError')"))
                                  +str(page.evaluate("globalThis.createdItem")))
                    time.sleep(0.05)
                item = page.evaluate("async id => (await chrome.downloads.search({id}))[0]", download_id)
                self.assertEqual(item["state"], "interrupted", repr(item))
                inbox = [entry for _, entry in store.inbox() if entry.get("url") == url]
                self.assertEqual(len(inbox), 1)
                self.assertEqual(inbox[0]["filename"], "fixture.bin")
                # An unreachable native host must leave the browser download usable.
                for key_path in registration_paths:
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(folder/"missing-host.json"))
                page.evaluate("() => {globalThis.created = new Promise(resolve => chrome.downloads.onCreated.addListener(item => resolve(item.id)))}")
                web.get_by_role("link").click()
                fallback_id = page.evaluate("globalThis.created")
                deadline = time.monotonic()+20
                while page.evaluate("async id => (await chrome.downloads.search({id}))[0]?.state", fallback_id) != "complete":
                    if time.monotonic() >= deadline:
                        self.fail("Browser fallback did not complete")
                    time.sleep(0.05)
                self.assertEqual(len([entry for _, entry in store.inbox() if entry.get("url") == url]), 1)
                # Complete the handoff through the actual native GUI and HTTP engine.
                import tkinter as tk

                from hngoos_dm.app import App
                for request_id, _ in store.inbox():
                    store.acknowledge(request_id, "cancelled")
                store.set_setting("browser_preferences", {"capture": True, "auto_start": True, "resume_on_cancel": True})
                store.set_setting("auto_defender", False)
                for key_path in registration_paths:
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(manifest))
                result = page.evaluate("async () => (await import(chrome.runtime.getURL('capture-settings.js'))).setCaptureEnabled(chrome,true)")
                self.assertTrue(result)
                # This harness pumps update(), not mainloop(). Prevent a worker
                # from collecting retired Tk controls while Tcl cannot marshal
                # their finalizers back to this thread (production uses mainloop).
                automatic_gc = gc.isenabled()
                gc.disable()
                if automatic_gc:
                    cleanup.callback(gc.enable)
                root = tk.Tk()
                app = App(root, data_dir)
                app.directory.set(str(folder/"hdm-downloads"))
                root.update()
                root.withdraw()
                errors = []
                root.report_callback_exception = lambda *args: errors.append(str(args[1]))
                try:
                    page.evaluate("() => {globalThis.created = new Promise(resolve => chrome.downloads.onCreated.addListener(item => resolve(item.id)))}")
                    web.get_by_role("link").click()
                    accepted_id = page.evaluate("globalThis.created")
                    deadline = time.monotonic()+30
                    while time.monotonic() < deadline:
                        root.update()
                        jobs = store.all()
                        browser_state = page.evaluate("async id => (await chrome.downloads.search({id}))[0]?.state", accepted_id)
                        if jobs and jobs[0]["state"] == "complete" and browser_state == "interrupted":
                            break
                        time.sleep(.03)
                    self.assertFalse(errors)
                    self.assertNotEqual(root.state(), "withdrawn")
                    self.assertTrue(jobs, "Native UI must accept the web download")
                    self.assertEqual(jobs[0]["state"], "complete", repr(jobs[0]))
                    self.assertEqual(browser_state, "interrupted")
                    self.assertEqual((folder/"hdm-downloads/fixture.bin").read_bytes(), b"x"*(4*1024*1024))
                    # Manual mode must use HDM's inline editor and saved folder.
                    # Keep the original browser task paused while a user reviews it.
                    from unittest.mock import patch
                    store.set_setting("browser_preferences", {"capture": True, "auto_start": False, "resume_on_cancel": True})
                    page.evaluate("async () => (await import(chrome.runtime.getURL('capture-settings.js'))).setCaptureEnabled(chrome,true)")
                    with patch("hngoos_dm.app.filedialog.asksaveasfilename", side_effect=AssertionError("Unexpected save dialog")):
                        for accept in (True, False):
                            count = len(store.all())
                            page.evaluate("() => {globalThis.created = new Promise(resolve => chrome.downloads.onCreated.addListener(item => resolve(item.id)))}")
                            web.get_by_role("link").click()
                            manual_id = page.evaluate("globalThis.created")
                            deadline = time.monotonic()+20
                            while not getattr(app, "browser_request", None) and time.monotonic() < deadline:
                                root.update()
                                time.sleep(.03)
                            self.assertIsNotNone(getattr(app, "browser_request", None))
                            self.assertEqual(app.url.get(), url)
                            self.assertEqual(app.download_editor.directory.get(), str(folder/"hdm-downloads"))
                            initial = page.evaluate("async id => (await chrome.downloads.search({id}))[0]", manual_id)
                            self.assertTrue(initial["paused"], repr(initial))
                            self.assertEqual(len(store.all()), count)
                            until = time.monotonic()+2
                            while time.monotonic() < until:
                                root.update()
                                time.sleep(.03)
                            held = page.evaluate("async id => (await chrome.downloads.search({id}))[0]", manual_id)
                            self.assertTrue(held["paused"], repr(held))
                            self.assertEqual(held["bytesReceived"], initial["bytesReceived"])
                            if accept:
                                app.download_editor.name.set("confirmed")
                                app.submit_download()
                            else:
                                app.cancel_download()
                            deadline = time.monotonic()+20
                            while time.monotonic() < deadline:
                                root.update()
                                state = page.evaluate("async id => (await chrome.downloads.search({id}))[0]?.state", manual_id)
                                if state == ("interrupted" if accept else "complete") and not getattr(app, "browser_request", None):
                                    break
                                time.sleep(.03)
                            self.assertEqual(state, "interrupted" if accept else "complete")
                            self.assertEqual(len(store.all()), count+int(accept))
                        deadline = time.monotonic()+20
                        while time.monotonic() < deadline and not (folder/"hdm-downloads/confirmed.bin").is_file():
                            root.update()
                            time.sleep(.03)
                        self.assertEqual((folder/"hdm-downloads/confirmed.bin").read_bytes(), b"x"*(4*1024*1024))
                        self.assertFalse(errors)
                finally:
                    app.close()
                    app.manager.pool.shutdown(wait=True)
                    app.manager.safety_pool.shutdown(wait=True)
                    for variable in gc.get_objects():
                        if isinstance(variable, tk.Variable) and variable._tk is root.tk:
                            for modes, command in variable.trace_info():
                                variable.trace_remove(modes, command)
                    del variable, app, root
                    gc.collect()
            finally:
                context.close()
                lock.close()
                server.shutdown()
                server.server_close()
                if existed:
                    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, registry_path) as key:
                        winreg.SetValueEx(key, "", 0, winreg.REG_SZ, previous)
                else:
                    try:
                        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, registry_path)
                    except FileNotFoundError:
                        pass
