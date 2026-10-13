#!/usr/bin/env python3

import subprocess
import sys

TESTS = [
    ("Client → Router", "lvc-client", "10.10.1.1"),
    ("Client → Server", "lvc-client", "10.10.2.10"),
    ("Router → Kali host", "lvc-router", "10.10.99.1"),
    ("Client → Internet", "lvc-client", "1.1.1.1"),
]

def run_test(name, namespace, destination):
    command = [
        "ip", "netns", "exec", namespace,
        "ping", "-c", "2", "-W", "1", destination
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    if result.returncode == 0:
        print(f"[PASS] {name}")
        return True

    print(f"[FAIL] {name}")
    return False

def main():
    print("Running Linux virtual network tests...\n")

    results = [
        run_test(name, namespace, destination)
        for name, namespace, destination in TESTS
    ]

    print()

    if all(results):
        print("All network tests passed.")
        sys.exit(0)

    print("One or more network tests failed.")
    sys.exit(1)

if __name__ == "__main__":
    main()
