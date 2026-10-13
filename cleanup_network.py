#!/usr/bin/env python3

import subprocess

NAMESPACES = [
    "lvc-client",
    "lvc-router",
    "lvc-server",
]

ROOT_LINKS = [
    "lvc-c-host",
    "lvc-r0-host",
    "lvc-r1-host",
    "lvc-s-host",
    "lvc-up-h",
]

BRIDGES = [
    "lvc-br0",
    "lvc-br1",
]

def run(*args):
    print("+", " ".join(args))
    subprocess.run(args, check=False)

def main():
    print("Removing project NAT rules...")
    run("nft", "delete", "table", "ip", "lvc_nat")

    print("Removing namespaces...")
    for namespace in NAMESPACES:
        run("ip", "netns", "delete", namespace)

    print("Removing virtual interfaces...")
    for link in ROOT_LINKS:
        run("ip", "link", "delete", link)

    print("Removing bridges...")
    for bridge in BRIDGES:
        run("ip", "link", "delete", bridge)

    print("Linux virtual network cleaned up.")

if __name__ == "__main__":
    main()
