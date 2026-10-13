#!/usr/bin/env python3

import os
import subprocess
import sys

NAMESPACES = ["lvc-client", "lvc-router", "lvc-server"]
BRIDGES = ["lvc-br0", "lvc-br1"]

ROOT_LINKS = [
    "lvc-c-host",
    "lvc-r0-host",
    "lvc-r1-host",
    "lvc-s-host",
    "lvc-up-h",
]

def run(*args, check=True):
    print("+", " ".join(args))
    subprocess.run(args, check=check)

def ns(namespace, *args):
    run("ip", "netns", "exec", namespace, *args)

def cleanup():
    run("nft", "delete", "table", "ip", "lvc_nat", check=False)

    for namespace in NAMESPACES:
        run("ip", "netns", "delete", namespace, check=False)

    for link in ROOT_LINKS:
        run("ip", "link", "delete", link, check=False)

    for bridge in BRIDGES:
        run("ip", "link", "delete", bridge, check=False)

def external_interface():
    output = subprocess.check_output(
        ["ip", "-o", "route", "show", "default"],
        text=True
    ).split()

    if "dev" not in output:
        raise RuntimeError("Could not find the external network interface.")

    return output[output.index("dev") + 1]

def create_veth(host_name, namespace, namespace_name):
    run(
        "ip", "link", "add",
        host_name,
        "type", "veth",
        "peer", "name", namespace_name
    )
    run("ip", "link", "set", namespace_name, "netns", namespace)

def main():
    if os.geteuid() != 0:
        print("Run with sudo.")
        sys.exit(1)

    print("Cleaning previous project state...")
    cleanup()

    ext_if = external_interface()
    print(f"External interface: {ext_if}")

    # Namespaces
    for namespace in NAMESPACES:
        run("ip", "netns", "add", namespace)

    # Bridges
    for bridge in BRIDGES:
        run("ip", "link", "add", bridge, "type", "bridge")
        run("ip", "link", "set", bridge, "up")

    # Client and router on br0
    create_veth("lvc-c-host", "lvc-client", "lvc-c-ns")
    create_veth("lvc-r0-host", "lvc-router", "lvc-r0-ns")

    run("ip", "link", "set", "lvc-c-host", "master", "lvc-br0")
    run("ip", "link", "set", "lvc-r0-host", "master", "lvc-br0")
    run("ip", "link", "set", "lvc-c-host", "up")
    run("ip", "link", "set", "lvc-r0-host", "up")

    # Router and server on br1
    create_veth("lvc-r1-host", "lvc-router", "lvc-r1-ns")
    create_veth("lvc-s-host", "lvc-server", "lvc-s-ns")

    run("ip", "link", "set", "lvc-r1-host", "master", "lvc-br1")
    run("ip", "link", "set", "lvc-s-host", "master", "lvc-br1")
    run("ip", "link", "set", "lvc-r1-host", "up")
    run("ip", "link", "set", "lvc-s-host", "up")

    # Namespace interfaces
    ns("lvc-client", "ip", "link", "set", "lvc-c-ns", "name", "eth0")
    ns("lvc-router", "ip", "link", "set", "lvc-r0-ns", "name", "eth0")
    ns("lvc-router", "ip", "link", "set", "lvc-r1-ns", "name", "eth1")
    ns("lvc-server", "ip", "link", "set", "lvc-s-ns", "name", "eth0")

    # Router uplink
    run(
        "ip", "link", "add",
        "lvc-up-h",
        "type", "veth",
        "peer", "name", "lvc-up-r"
    )
    run("ip", "link", "set", "lvc-up-r", "netns", "lvc-router")

    run("ip", "addr", "add", "10.10.99.1/24", "dev", "lvc-up-h")
    run("ip", "link", "set", "lvc-up-h", "up")

    ns("lvc-router", "ip", "link", "set", "lvc-up-r", "up")
    ns("lvc-router", "ip", "addr", "add", "10.10.99.2/24", "dev", "lvc-up-r")

    # Bring interfaces up
    for namespace, interfaces in {
        "lvc-client": ["lo", "eth0"],
        "lvc-router": ["lo", "eth0", "eth1", "lvc-up-r"],
        "lvc-server": ["lo", "eth0"],
    }.items():
        for interface in interfaces:
            ns(namespace, "ip", "link", "set", interface, "up")

    # IP addresses
    ns("lvc-client", "ip", "addr", "add", "10.10.1.10/24", "dev", "eth0")
    ns("lvc-router", "ip", "addr", "add", "10.10.1.1/24", "dev", "eth0")
    ns("lvc-router", "ip", "addr", "add", "10.10.2.1/24", "dev", "eth1")
    ns("lvc-server", "ip", "addr", "add", "10.10.2.10/24", "dev", "eth0")

    # Routes
    ns("lvc-client", "ip", "route", "add", "default", "via", "10.10.1.1")
    ns("lvc-server", "ip", "route", "add", "default", "via", "10.10.2.1")
    ns("lvc-router", "ip", "route", "add", "default", "via", "10.10.99.1")

    run("ip", "route", "add", "10.10.1.0/24", "via", "10.10.99.2", "dev", "lvc-up-h")
    run("ip", "route", "add", "10.10.2.0/24", "via", "10.10.99.2", "dev", "lvc-up-h")

    # Forwarding
    run("sysctl", "-w", "net.ipv4.ip_forward=1")
    ns("lvc-router", "sysctl", "-w", "net.ipv4.ip_forward=1")

    # NAT on the Kali host
    run("nft", "add", "table", "ip", "lvc_nat")
    run(
        "nft", "add", "chain", "ip", "lvc_nat", "postrouting",
        "{ type nat hook postrouting priority srcnat; policy accept; }"
    )
    run(
        "nft", "add", "rule", "ip", "lvc_nat", "postrouting",
        "ip", "saddr", "10.10.0.0/16",
        "oifname", ext_if,
        "masquerade"
    )

    print("\nLinux virtual network created successfully.")
    print(f"NAT interface: {ext_if}")

if __name__ == "__main__":
    main()
