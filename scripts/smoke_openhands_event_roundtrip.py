#!/usr/bin/env python3
"""Live HTTP round-trip for locked-server to host-client event compatibility."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SDK_SOURCE = ROOT / "reproductions" / "software-agent-sdk" / "openhands-sdk"

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")


def event_json() -> bytes:
    from openhands.sdk.event import SystemPromptEvent
    from openhands.sdk.llm import TextContent

    event = SystemPromptEvent(
        system_prompt=TextContent(text="static prompt"),
        dynamic_context=TextContent(text="live dynamic context"),
        tools=[],
    )
    return event.model_dump_json().encode("utf-8")


def serve_once(port: int) -> int:
    payload = event_json()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_args):
            return

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.handle_request()
    return 0


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def roundtrip() -> int:
    from openhands.sdk.event import SystemPromptEvent

    port = free_port()
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(SDK_SOURCE), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    process = subprocess.Popen(
        [sys.executable, __file__, "--serve-once", str(port)],
        env=env,
    )
    try:
        payload = None
        for _ in range(50):
            try:
                with urlopen(f"http://127.0.0.1:{port}/event", timeout=1) as response:
                    payload = response.read()
                break
            except OSError:
                time.sleep(0.1)
        if payload is None:
            raise RuntimeError("locked SDK event server did not become ready")
        event = SystemPromptEvent.model_validate_json(payload)
        if event.dynamic_context is None:
            raise RuntimeError("dynamic_context was lost during event round-trip")
        print(
            json.dumps(
                {
                    "valid": True,
                    "event_type": type(event).__name__,
                    "dynamic_context": event.dynamic_context.text,
                },
                sort_keys=True,
            )
        )
    finally:
        process.wait(timeout=10)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve-once", type=int)
    args = parser.parse_args()
    return serve_once(args.serve_once) if args.serve_once else roundtrip()


if __name__ == "__main__":
    raise SystemExit(main())
