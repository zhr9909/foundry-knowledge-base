#!/usr/bin/env python3
"""Launch both services: RAG Agent (:8001) → Orchestrator (:8000)"""

import subprocess, sys, time, os, urllib.request, json
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
SERVICES = {
    "rag":  {"script": "agent_rag.py", "port": 8001},
    "gate": {"script": "gateway.py",   "port": 8000},
}

def start(name, cfg):
    log = open(SCRIPTS / f"{name}.log", "w", buffering=1)
    p = subprocess.Popen(
        [sys.executable, str(SCRIPTS / cfg["script"])],
        cwd=str(SCRIPTS), stdout=log, stderr=subprocess.STDOUT
    )
    return p

def wait_for(port, timeout_s=60):
    for i in range(timeout_s):
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            return True
        except:
            if i % 5 == 0:
                print(f"  Waiting :{port}... ({i}s)")
            time.sleep(1)
    return False

def main():
    print("=" * 50)
    print("Foundry KB - Starting Services")
    print("=" * 50)
    procs = {}
    for name in ["rag", "gate"]:
        cfg = SERVICES[name]
        procs[name] = start(name, cfg)
        print(f"  [{procs[name].pid}] {name} ({cfg['script']})")
    print("\nWaiting for RAG Agent (:8001)...")
    if wait_for(8001, 90):
        print("  [OK] RAG Agent READY")
    print("Waiting for Orchestrator (:8000)...")
    if wait_for(8000, 60):
        print("  [OK] Orchestrator READY")
    print("\n[OK] Both services running!")
    print("  http://127.0.0.1:8000")
    print("\nKeep this window open. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        pass
    finally:
        for name, p in list(procs.items()):
            if p and p.poll() is None:
                p.terminate()
                try: p.wait(3)
                except: p.kill()
                print(f"  Stopped {name}")
        print("All stopped.")

if __name__ == "__main__":
    # Legacy globals - kept for compatibility
    sp = gp = None
    main()
