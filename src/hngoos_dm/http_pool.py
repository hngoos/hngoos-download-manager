"""Bounded direct HTTP/1.1 connections; incomplete responses never return to the pool."""

import http.client
import socket
import ssl
import threading
import time
import urllib.error
from urllib.parse import urljoin, urlsplit

from .safety import validate_url


class Response:
    def __init__(self, pool, key, connection, response, url):
        self.pool, self.key, self.connection = pool, key, connection
        self.response, self.url = response, url
        self.headers, self.status = response.headers, response.status
        self.complete, self.closed = response.length == 0, False

    def geturl(self):
        return self.url

    def read(self, amount=None):
        try:
            data = self.response.read(amount)
            self.complete = self.response.length == 0 or (self.response.chunked and self.response.isclosed())
            return data
        except (http.client.HTTPException, OSError) as error:
            self.close()
            raise urllib.error.URLError(error) from error

    def close(self):
        if not self.closed:
            self.closed = True
            reusable = self.complete and not self.response.will_close
            self.response.close()
            self.pool.release(self.key, self.connection, reusable)

    def __enter__(self):
        return self

    def __exit__(self, kind, *_args):
        if kind:
            self.complete = False
        self.close()


class HTTPPool:
    def __init__(self, max_idle=64, idle_seconds=30):
        self.max_idle, self.idle_seconds = max_idle, idle_seconds
        self.idle, self.connections = {}, set()
        self.lock, self.closed = threading.Lock(), False
        self.tls = ssl.create_default_context()

    def acquire(self, key):
        with self.lock:
            if self.closed:
                raise OSError("Download connections are closed")
            slots = self.idle.setdefault(key, [])
            while slots:
                connection, saved = slots.pop()
                if time.monotonic()-saved <= self.idle_seconds:
                    return connection, True
                connection.close()
                self.connections.discard(connection)
            scheme, host, port = key
            connection = (http.client.HTTPSConnection(host, port, timeout=15, context=self.tls)
                          if scheme == "https" else http.client.HTTPConnection(host, port, timeout=15))
            original_connect = connection.connect
            def connect():
                if self.closed:
                    raise OSError("Download connections are closed")
                original_connect()
                if self.closed:
                    connection.close()
                    raise OSError("Download connections are closed")
            connection.connect = connect
            self.connections.add(connection)
            return connection, False

    def release(self, key, connection, reusable):
        with self.lock:
            if not self.closed and reusable and sum(map(len, self.idle.values())) < self.max_idle:
                self.idle.setdefault(key, []).append((connection, time.monotonic()))
            else:
                connection.close()
                self.connections.discard(connection)

    def request(self, url, headers=None):
        headers = {"User-Agent": "HDM/0.1", "Accept-Encoding": "identity", **(headers or {})}
        for _hop in range(11):
            parsed = urlsplit(validate_url(url))
            key = parsed.scheme.lower(), parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
            target = (parsed.path or "/")+("?"+parsed.query if parsed.query else "")
            for attempt in range(2):
                connection, reused = self.acquire(key)
                try:
                    connection.request("GET", target, headers=headers)
                    response = Response(self, key, connection, connection.getresponse(), url)
                    break
                except (http.client.HTTPException, OSError) as error:
                    self.release(key, connection, False)
                    if not reused or attempt or isinstance(error, ssl.SSLError):
                        raise urllib.error.URLError(error) from error
            if response.status in {301, 302, 303, 307, 308} and response.headers.get("Location"):
                destination = urljoin(url, response.headers["Location"])
                with response:
                    response.read(65536)
                next_url = urlsplit(validate_url(destination))
                if parsed.scheme == "https" and next_url.scheme != "https":
                    raise ValueError("Không chuyển lượt tải HTTPS sang HTTP không mã hóa.")
                if (parsed.scheme, parsed.netloc) != (next_url.scheme, next_url.netloc):
                    headers = {key: value for key, value in headers.items()
                               if key.lower() not in {"authorization", "cookie", "proxy-authorization", "referer"}}
                url = destination
                continue
            if response.status >= 400:
                status, reason, result_headers = response.status, response.response.reason, response.headers
                response.close()
                raise urllib.error.HTTPError(url, status, reason, result_headers, None)
            return response
        raise urllib.error.HTTPError(url, 302, "Too many redirects", None, None)

    def close(self):
        with self.lock:
            self.closed = True
            connections = list(self.connections)
            idle = {connection for slots in self.idle.values() for connection, _saved in slots}
            self.connections.clear()
            self.idle.clear()
        for connection in connections:
            active_socket = connection.sock
            if active_socket:
                try:
                    active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass  # A concurrently completed response may already have closed its socket.
                active_socket.close()
            if connection in idle:
                connection.close()
            # Active responses close their HTTPConnection in release(). Closing an HTTPResponse
            # from another thread can wait for its buffered read and race with read() cleanup.
