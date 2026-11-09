"""Small CDP renderer using an installed Chromium and a disposable profile.

No browser runtime is distributed and no user profile is opened. The connection
is restricted to the loopback endpoint published in our own temporary directory.
"""

import base64
import json
import os
import subprocess
import tempfile
import time
from collections import deque
from pathlib import Path

from .browser import find_browser


class BrowserPage:
    def __init__(self, channel=None, *, executable=None, timeout=45):
        self.executable = executable
        self.channel = channel
        self.timeout = timeout
        self.process = self.socket = self.connection = self.temporary = None
        self.profile = None
        self.sequence = 0
        self.session = None
        self.events = deque(maxlen=256)

    def __enter__(self):
        from websockets.sync.client import connect

        self.temporary = tempfile.TemporaryDirectory(prefix="hdm-render-")
        self.profile = Path(self.temporary.name)
        try:
            executable = self.executable
            if not executable:
                preferred = {"msedge": "edge", "chrome": "chrome"}.get(self.channel, "edge")
                executable = next((path for browser in dict.fromkeys((preferred, "chrome", "edge", "brave", "vivaldi", "coccoc", "opera", "opera-gx"))
                                   if (path := find_browser(browser))), None)
            if not executable:
                raise FileNotFoundError("Install a Chromium browser to save web pages or invoices.")
            self.process = subprocess.Popen([
                str(executable), "--headless=new", "--no-first-run", "--no-default-browser-check",
                "--disable-background-networking", "--disable-component-update", "--disable-sync",
                "--disable-extensions", "--disable-default-apps", "--metrics-recording-only", "--hide-scrollbars",
                "--remote-debugging-address=127.0.0.1", "--remote-debugging-port=0",
                f"--user-data-dir={self.profile}", "about:blank"],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=0x08000000 if os.name == "nt" else 0)
            deadline = time.monotonic()+self.timeout
            endpoint = self.profile/"DevToolsActivePort"
            while True:
                if self.process.poll() is not None:
                    raise RuntimeError("Headless browser exited before becoming ready.")
                try:
                    port, resource = endpoint.read_text(encoding="utf-8").splitlines()[:2]
                    if not 0 < int(port) < 65536 or not resource.startswith("/devtools/browser/"):
                        raise ValueError("Invalid browser endpoint")
                    break
                except (OSError, ValueError):
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Headless browser did not become ready.") from None
                    time.sleep(.05)
            self.connection = connect(f"ws://127.0.0.1:{int(port)}{resource}", open_timeout=self.timeout,
                                      max_size=128*1024*1024, proxy=None)
            self.socket = self.connection.__enter__()
            target = self.call("Target.createTarget", {"url": "about:blank"})["targetId"]
            self.session = self.call("Target.attachToTarget", {"targetId": target, "flatten": True})["sessionId"]
            self.call("Page.enable")
            self.call("Emulation.setDeviceMetricsOverride", {
                "width": 1280, "height": 900, "deviceScaleFactor": 1, "mobile": False})
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def call(self, method, params=None):
        self.sequence += 1
        message = {"id": self.sequence, "method": method, "params": params or {}}
        if self.session:
            message["sessionId"] = self.session
        self.socket.send(json.dumps(message))
        deadline = time.monotonic()+self.timeout
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Browser command timed out: {method}")
            reply = json.loads(self.socket.recv(timeout=remaining))
            if reply.get("id") == self.sequence:
                if "error" in reply:
                    raise RuntimeError(f"Browser {method}: {reply['error']['message']}")
                return reply.get("result", {})
            if "method" in reply:
                self.events.append(reply)

    def navigate(self, url):
        self.events.clear()
        result = self.call("Page.navigate", {"url": url})
        if result.get("errorText"):
            raise RuntimeError(result["errorText"])
        deadline = time.monotonic()+self.timeout
        while not any(event.get("method") == "Page.domContentEventFired" and
                      event.get("sessionId") == self.session for event in self.events):
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Web page navigation timed out.")
            self.events.append(json.loads(self.socket.recv(timeout=remaining)))

    def evaluate(self, expression):
        result = self.call("Runtime.evaluate", {
            "expression": expression, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in result:
            raise RuntimeError("Web page script failed.")
        return result.get("result", {}).get("value")

    def set_content(self, document, *, isolated=False):
        if isolated:
            self.call("Emulation.setScriptExecutionDisabled", {"value": True})
            self.call("Network.enable")
            self.call("Network.setBlockedURLs", {"urls": ["*"]})
            self.call("Network.setBypassServiceWorker", {"bypass": True})
        frame = self.call("Page.getFrameTree")["frameTree"]["frame"]["id"]
        self.call("Page.setDocumentContent", {"frameId": frame, "html": document})

    def pdf(self, destination, *, header=None, a4=False, margins=None):
        settings = {"printBackground": True, "preferCSSPageSize": True}
        if a4:
            settings.update(paperWidth=210/25.4, paperHeight=297/25.4)
        if margins:
            settings.update({"margin"+side.title(): value for side, value in margins.items()})
        if header:
            settings.update(displayHeaderFooter=True, headerTemplate=header, footerTemplate="<span></span>")
        data = self.call("Page.printToPDF", settings)["data"]
        Path(destination).write_bytes(base64.b64decode(data, validate=True))

    def screenshot(self, destination):
        size = self.call("Page.getLayoutMetrics")["cssContentSize"]
        data = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True,
            "clip": {"x": 0, "y": 0, "width": size["width"], "height": size["height"], "scale": 1}})["data"]
        Path(destination).write_bytes(base64.b64decode(data, validate=True))

    def __exit__(self, *_args):
        from websockets.exceptions import ConnectionClosed

        if self.socket:
            try:
                self.socket.send(json.dumps({"id": self.sequence+1, "method": "Browser.close"}))
            except (OSError, ConnectionClosed):
                pass
            finally:
                self.connection.__exit__(None, None, None)
                self.socket = None
        if self.process:
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=5)
        if self.temporary:
            self.temporary.cleanup()
            self.temporary = None
