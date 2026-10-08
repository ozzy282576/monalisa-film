#!/usr/bin/env python3
"""Tiny static file server with HTTP Range support.

``python -m http.server`` ignores the ``Range`` header, which breaks video: a
browser cannot seek, and Chrome will often refuse to play at all because it
cannot fetch the moov atom or resume a partial download. This adds just enough
range handling to make an ``<video>`` element behave normally.

Serves the repository root, binds 0.0.0.0 so the sandbox preview proxy can reach
it, and sets no origin restrictions.
"""

from __future__ import annotations

import argparse
import email.utils
import functools
import mimetypes
import os
import re
import socketserver
import sys
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler

_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)\s*$")
# Big enough to cover a seek without hammering the socket, small enough that the
# first frame arrives fast on a slow link.
_CHUNK = 512 * 1024


class RangeHandler(SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler plus byte ranges, caching and no directory HTML."""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:  # quieter logs
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def guess_type(self, path):  # noqa: D102 - inherited contract
        base, ext = os.path.splitext(path)
        if ext.lower() == ".mp4":
            return "video/mp4"
        return mimetypes.guess_type(path)[0] or "application/octet-stream"

    def end_headers(self) -> None:
        # Same-origin preview: allow embedding in the Arena proxy iframe.
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "public, max-age=300")
        super().end_headers()

    def send_head(self):  # noqa: C901 - straightforward branch on range header
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            for index in ("index.html", "index.htm"):
                candidate = os.path.join(path, index)
                if os.path.exists(candidate):
                    path = candidate
                    break
            else:
                return self.list_directory(path)

        if not os.path.exists(path):
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        size = os.path.getsize(path)
        range_header = self.headers.get("Range")
        match = _RANGE_RE.match(range_header) if range_header else None

        try:
            handle = open(path, "rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return None

        if match is None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Length", str(size))
            self.send_header("Last-Modified", self.date_time_string(os.path.getmtime(path)))
            self.end_headers()
            return handle

        # -- partial content --
        start_s, end_s = match.group(1), match.group(2)
        if start_s == "" and end_s == "":
            handle.close()
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE, "Empty range")
            return None

        if start_s == "":                       # suffix range: last N bytes
            length = min(int(end_s), size)
            start = size - length
            end = size - 1
        else:
            start = int(start_s)
            end = int(end_s) if end_s else size - 1
            end = min(end, size - 1)

        if start >= size or start > end:
            handle.close()
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None

        handle.seek(start)
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Last-Modified", self.date_time_string(os.path.getmtime(path)))
        self.end_headers()
        self._range_remaining = end - start + 1
        return handle

    def copyfile(self, source, outputfile) -> None:
        """Copy at most the number of bytes promised in the Content-Range."""
        remaining = getattr(self, "_range_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        self._range_remaining = None
        while remaining > 0:
            chunk = source.read(min(_CHUNK, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--bind", default="0.0.0.0")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)
    handler = functools.partial(RangeHandler, directory=root)
    with ThreadingHTTPServer((args.bind, args.port), handler) as httpd:
        print(f"serving {root} on http://{args.bind}:{args.port}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
