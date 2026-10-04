#!/usr/bin/env python3
"""Run a trusted Python check with network calls rejected by an audit hook.

This is an accidental-network guard, not a sandbox for untrusted corpus code.
Use python -I; only the target's directory is added to the import path.
"""
import atexit
from pathlib import Path
import runpy
import socket
import sys


def main():
    attempts = []

    def guard(event, args):
        if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto",
                     "socket.sendmsg", "socket.bind", "socket.gethostbyname",
                     "socket.gethostbyaddr", "socket.getnameinfo"}:
            attempts.append(event)
            raise PermissionError("offline check: network operation blocked")

    sys.addaudithook(guard)
    atexit.register(lambda: print(f"SYCO_NETWORK_ATTEMPTS={len(attempts)}"))
    if sys.argv[1:] == ["--probe"]:
        def connect_probe():
            with socket.socket() as connection:
                connection.connect(("127.0.0.1", 9))

        for call in (lambda: socket.getaddrinfo("example.invalid", 443),
                     connect_probe):
            try:
                call()
            except PermissionError:
                continue
            raise SystemExit("network guard did not reject the probe")
        print("DNS and connection probes blocked")
        return
    if len(sys.argv) < 2:
        raise SystemExit("usage: offline_guard.py SCRIPT [ARGS] | --probe")
    target = Path(sys.argv[1]).resolve(strict=True)
    sys.argv = [str(target), *sys.argv[2:]]
    sys.path.insert(0, str(target.parent))
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
