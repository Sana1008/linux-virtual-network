#!/usr/bin/env python3

import os
import subprocess
import sys

NAMESPACES = ["lvc-client", "lvc-router", "lvc-server"]
BRIDGES = ["lvc-br0", "lvc-br1"]

def run(*args, check=True):
    print("+", " ".join(args))
    subprocess.run(args, check=check)

def ns(namespace, *args):
    run("ip", "netns", "exec", namespace, *args)

def cleanup_existing():
    for namespace in NAMESPACES:
        run("ip", "netns", "delete", namespace, check=False)

    for interface in [
        "lvc-c-host",
        "lvc-r0-host",
        "lvc-r1-host",
        "lvc-s-host",
    ]:
        run("ip", "link", "delete", interface, check=False)

    for bridge in BRIDGES:
        run("ip", "link", "delete", bridge, check=False)

def main():
    if os.geteuid() != 0:
        print("Run this script with sudo.")
        sys.exit(1)

    cleanup_existing()

    # Create namespaces
    for namespace in NAMESPACES:
        run("ip", "netns", "add", namespace)

    # Create bridges
    for bridge in BRIDGES:
        run("ip", "link", "add", bridge, "type", "bridge")
        run("ip", "link", "set", bridge, "up")

    # Create client-to-bridge veth pair
    run(
        "ip", "link", "add",
        "lvc-c-host", "type", "veth",
        "peer", "name", "lvc-c-ns"
    )
    run("ip", "link", "set", "lvc-c-ns", "netns", "lvc-client")
    run("ip", "link", "set", "lvc-c-host", "master", "lvc-br0")
    run("ip", "link", "set", "lvc-c-host", "up")

    # Create router-left-to-bridge veth pair
    run(
        "ip", "link", "add",
        "lvc-r0-host", "type", "veth",
        "peer", "name", "lvc-r0-ns"
    )
    run("ip", "link", "set", "lvc-r0-ns", "netns", "lvc-router")
    run("ip", "link", "set", "lvc-r0-host", "master", "lvc-br0")
    run("ip", "link", "set", "lvc-r0-host", "up")

    # Create router-right-to-bridge veth pair
    run(
        "ip", "link", "add",
        "lvc-r1-host", "type", "veth",
        "peer", "name", "lvc-r1-ns"
    )
    run("ip", "link", "set", "lvc-r1-ns", "netns", "lvc-router")
    run("ip", "link", "set", "lvc-r1-host", "master", "lvc-br1")
    run("ip", "link", "set", "lvc-r1-host", "up")

    # Create server-to-bridge veth pair
    run(
        "ip", "link", "add",
        "lvc-s-host", "type", "veth",
        "peer", "name", "lvc-s-ns"
    )
    run("ip", "link", "set", "lvc-s-ns", "netns", "lvc-server")
    run("ip", "link", "set", "lvc-s-host", "master", "lvc-br1")
    run("ip", "link", "set", "lvc-s-host", "up")

    # Rename interfaces inside namespaces
    ns("lvc-client", "ip", "link", "set", "lvc-c-ns", "name", "eth0")
    ns("lvc-router", "ip", "link", "set", "lvc-r0-ns", "name", "eth0")
    ns("lvc-router", "ip", "link", "set", "lvc-r1-ns", "name", "eth1")
    ns("lvc-server", "ip", "link", "set", "lvc-s-ns", "name", "eth0")

    # Bring loopback and interfaces up
    for namespace, interfaces in {
        "lvc-client": ["lo", "eth0"],
        "lvc-router": ["lo", "eth0", "eth1"],
        "lvc-server": ["lo", "eth0"],
    }.items():
        for interface in interfaces:
            ns(namespace, "ip", "link", "set", interface, "up")

    # Assign IP addresses
    ns("lvc-client", "ip", "addr", "add", "10.10.1.10/24", "dev", "eth0")
    ns("lvc-router", "ip", "addr", "add", "10.10.1.1/24", "dev", "eth0")
    ns("lvc-router", "ip", "addr", "add", "10.10.2.1/24", "dev", "eth1")
    ns("lvc-server", "ip", "addr", "add", "10.10.2.10/24", "dev", "eth0")

    # Add default routes
    ns("lvc-client", "ip", "route", "add", "default", "via", "10.10.1.1")
    ns("lvc-server", "ip", "route", "add", "default", "via", "10.10.2.1")

    # Enable routing only inside the router namespace
    ns(
        "lvc-router",
        "sysctl",
        "-w",
        "net.ipv4.ip_forward=1"
    )

    print("\nNetwork created successfully.")
    print("Client: 10.10.1.10")
    print("Router: 10.10.1.1 and 10.10.2.1")
    print("Server: 10.10.2.10")

if __name__ == "__main__":
    main()
