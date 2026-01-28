"""Simple OPC UA address-space lister.

Usage:
    python -m px_device_interfaces.tools.opcua_list_nodes <endpoint> [--depth N]

Example:
    python px_device_interfaces/tools/opcua_list_nodes.py opc.tcp://169.254.152.1:4840 --depth 3
"""
from __future__ import annotations

import argparse
from opcua import Client


def walk(node, depth: int, prefix: str = ""):
    try:
        bn = node.get_browse_name()
    except Exception:
        bn = None
    try:
        nid = node.nodeid
    except Exception:
        nid = None
    print(f"{prefix}{nid} - {bn}")
    if depth <= 0:
        return
    try:
        for child in node.get_children():
            walk(child, depth - 1, prefix + "  ")
    except Exception:
        return


def main():
    p = argparse.ArgumentParser()
    p.add_argument("endpoint")
    p.add_argument("--depth", type=int, default=3)
    args = p.parse_args()

    client = Client(args.endpoint)
    try:
        client.connect()
    except Exception as e:
        print("Failed to connect:", e)
        return
    try:
        root = client.get_root_node()
        print("Root:")
        walk(root, args.depth)
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
