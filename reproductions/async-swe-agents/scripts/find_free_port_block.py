#!/usr/bin/env python3
"""Find a consecutive block of bindable host TCP ports."""

from __future__ import annotations

import argparse
import socket


def block_is_available(base: int, count: int, host: str = "0.0.0.0") -> bool:
    sockets: list[socket.socket] = []
    try:
        for port in range(base, base + count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((host, port))
            sockets.append(sock)
    except OSError:
        return False
    finally:
        for sock in sockets:
            sock.close()
    return True


def find_free_port_block(start: int, end: int, count: int) -> int:
    if count < 1:
        raise ValueError("count must be positive")
    if not 1 <= start <= 65535 or not 1 <= end <= 65535:
        raise ValueError("port range must be within 1..65535")
    if start > end or end - start + 1 < count:
        raise ValueError("port range is smaller than the requested block")

    for base in range(start, end - count + 2):
        if block_is_available(base, count):
            return base
    raise RuntimeError(f"no free block of {count} ports in {start}..{end}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=20000)
    parser.add_argument("--end", type=int, default=60000)
    parser.add_argument("--count", type=int, default=4)
    args = parser.parse_args()
    print(find_free_port_block(args.start, args.end, args.count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
