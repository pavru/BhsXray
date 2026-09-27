#!/usr/bin/env python3
"""Describes standalone Windows Cores and merges them into cores.json.

`entry` checks one Core built by libXray's `core windows` command against the
requested Xray-core ref and target architecture, then writes its manifest
entry. `merge` combines the entries of every version and architecture listed
in .github/xray-core-versions.json into the release's cores.json.
"""

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

FORMAT_VERSION = 1
# Machine field of the PE header for each Windows architecture.
PE_MACHINES = {"x64": 0x8664, "arm64": 0xAA64}


def pe_machine(data: bytes) -> int:
    if data[:2] != b"MZ":
        raise ValueError("Core is not a PE executable")
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[offset:offset + 4] != b"PE\0\0":
        raise ValueError("Core has no PE header")
    return struct.unpack_from("<H", data, offset + 4)[0]


def core_entry(binary: Path, metadata: dict, *, version: str, query: str,
               arch: str, asset: str) -> dict:
    if metadata.get("requestedRef") != query or metadata.get("local"):
        raise ValueError(f"Core was not built from the requested Xray-core ref {query}")
    data = binary.read_bytes()
    if pe_machine(data) != PE_MACHINES[arch]:
        raise ValueError(f"Core architecture does not match {arch}")
    return {
        "version": version,
        "moduleVersion": metadata["version"],
        "revision": metadata.get("revision"),
        "os": "windows",
        "arch": arch,
        "file": asset,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def merge_entries(config: dict, entries: list[dict]) -> dict:
    versions = config["versions"]
    if config["default"] not in versions or len(set(versions)) != len(versions):
        raise ValueError("Invalid Xray-core version list")
    found = {(entry["version"], entry["arch"]): entry for entry in entries}
    expected = {(version, arch) for version in versions for arch in PE_MACHINES}
    if len(found) != len(entries) or set(found) != expected:
        raise ValueError("Cores must cover every listed version and architecture once")
    return {
        "formatVersion": FORMAT_VERSION,
        "default": config["default"],
        "cores": [found[(version, arch)] for version in versions for arch in PE_MACHINES],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    entry = commands.add_parser("entry")
    entry.add_argument("--binary", type=Path, required=True)
    entry.add_argument("--metadata", type=Path, required=True, help="libXray xray-core.json")
    entry.add_argument("--version", required=True)
    entry.add_argument("--query", required=True)
    entry.add_argument("--arch", choices=PE_MACHINES, required=True)
    entry.add_argument("--asset", required=True, help="published file name")
    entry.add_argument("--output", type=Path, required=True)
    merge = commands.add_parser("merge")
    merge.add_argument("--versions", type=Path, required=True)
    merge.add_argument("--output", type=Path, required=True)
    merge.add_argument("entries", type=Path, nargs="+")
    args = parser.parse_args(argv)

    if args.command == "entry":
        result = core_entry(
            args.binary, json.loads(args.metadata.read_text(encoding="utf-8")),
            version=args.version, query=args.query, arch=args.arch, asset=args.asset,
        )
    else:
        result = merge_entries(
            json.loads(args.versions.read_text(encoding="utf-8")),
            [json.loads(path.read_text(encoding="utf-8")) for path in args.entries],
        )
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
