#!/usr/bin/env python3
"""Reject unexpected layouts before modifying a disk image."""
import json
import sys


def inspect(table):
    table = table["partitiontable"]
    if table.get("label") != "dos" or table.get("sectorsize") != 512:
        raise ValueError("Expected a DOS partition table with 512-byte sectors")
    partitions = table["partitions"]
    if len(partitions) != 2:
        raise ValueError("Expected exactly boot and root partitions")
    boot, root = partitions
    if boot["type"].lower().lstrip("0") not in {"b", "c", "e"} or root["type"] != "83":
        raise ValueError("Expected FAT boot and Linux root partition types")
    if not (boot["start"] > 0 and boot["size"] > 0 and root["size"] > 0
            and boot["start"] + boot["size"] <= root["start"]):
        raise ValueError("Invalid or overlapping partitions")
    return root["start"]


if __name__ == "__main__":
    print(inspect(json.load(sys.stdin)))
