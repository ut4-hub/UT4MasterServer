#!/usr/bin/env python3
"""
ejabberd external-auth "yes-man": accept every auth/isuser/setpass/tryregister
query unconditionally. Use ONLY on a local, throwaway smoke stack.

Protocol (ejabberd "extauth"):
  Server sends:  uint16-be length, then `length` bytes of UTF-8 "cmd:args..."
  Script replies: uint16-be 2, then 2 bytes (\\x00\\x01 = yes, \\x00\\x00 = no)

Commands:
  auth:User:Server:Password
  isuser:User:Server
  setpass:User:Server:Password
  tryregister:User:Server:Password
  removeuser:User:Server
  removeuser3:User:Server:Password
"""
import struct
import sys
import os

LOGFILE = "/home/ejabberd/database/yesman.log"

def log(msg):
    try:
        with open(LOGFILE, "a") as f:
            f.write(f"[{os.getpid()}] {msg}\n")
    except Exception:
        pass

def main():
    log("yesman starting")
    while True:
        hdr = sys.stdin.buffer.read(2)
        if len(hdr) < 2:
            log("EOF on header")
            return
        (length,) = struct.unpack(">H", hdr)
        if length <= 0:
            log(f"zero length, exit")
            return
        payload = sys.stdin.buffer.read(length)
        if len(payload) < length:
            log(f"short payload ({len(payload)}/{length})")
            return
        try:
            cmd = payload.decode("utf-8", errors="replace")
        except Exception:
            cmd = repr(payload)
        log(f"cmd: {cmd}")
        # Always say yes.
        sys.stdout.buffer.write(struct.pack(">HH", 2, 1))
        sys.stdout.buffer.flush()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log(f"fatal: {e}")
        raise
