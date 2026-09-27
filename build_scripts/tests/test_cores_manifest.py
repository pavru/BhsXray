import json
import struct
import tempfile
import unittest
from pathlib import Path

from cores_manifest import PE_MACHINES, core_entry, main, merge_entries

_METADATA = {"requestedRef": "5ca6f4b7d4dc20a881d4330e498892697627ec0c", "local": False,
             "version": "v1.260327.1-0.20260728075948-5ca6f4b7d4dc", "revision": "5ca6f4b7d4dc"}


def _pe(machine: int) -> bytes:
    header = bytearray(0x80)
    header[:2] = b"MZ"
    struct.pack_into("<I", header, 0x3C, 0x40)
    header[0x40:0x44] = b"PE\0\0"
    struct.pack_into("<H", header, 0x44, machine)
    return bytes(header)


def _entry(version: str, arch: str) -> dict:
    return {"version": version, "arch": arch, "file": f"{version}-{arch}.exe"}


class CoresManifestTest(unittest.TestCase):
    def setUp(self):
        fixtures = (Path(__file__).resolve().parents[3] / "references" /
                    "bhsxray-ci" / "cores-manifest")
        fixtures.mkdir(parents=True, exist_ok=True)
        self.temp_dir = tempfile.TemporaryDirectory(dir=fixtures)
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def test_entry_records_the_verified_core(self):
        binary = self.root / "xray.exe"
        binary.write_bytes(_pe(PE_MACHINES["arm64"]))

        entry = core_entry(binary, _METADATA, version="v26.7.28", query=_METADATA["requestedRef"],
                           arch="arm64", asset="BhsXRay-core-v26.7.28-windows-arm64.exe")

        self.assertEqual(entry["moduleVersion"], _METADATA["version"])
        self.assertEqual(entry["revision"], "5ca6f4b7d4dc")
        self.assertEqual(entry["size"], binary.stat().st_size)
        self.assertEqual(len(entry["sha256"]), 64)

    def test_entry_rejects_wrong_ref_architecture_or_file(self):
        binary = self.root / "xray.exe"
        binary.write_bytes(_pe(PE_MACHINES["x64"]))
        for metadata, arch in (
            ({**_METADATA, "requestedRef": "other"}, "x64"),
            ({**_METADATA, "local": True}, "x64"),
            (_METADATA, "arm64"),
        ):
            with self.subTest(metadata=metadata, arch=arch), self.assertRaises(ValueError):
                core_entry(binary, metadata, version="v26.7.28", query=_METADATA["requestedRef"],
                           arch=arch, asset="core.exe")
        binary.write_bytes(b"not a PE file")
        with self.assertRaises(ValueError):
            core_entry(binary, _METADATA, version="v26.7.28", query=_METADATA["requestedRef"],
                       arch="x64", asset="core.exe")

    def test_merge_requires_every_version_and_architecture_once(self):
        config = {"default": "v26.9.9", "versions": ["v26.9.9", "v26.7.28"]}
        entries = [_entry(version, arch) for version in reversed(config["versions"])
                   for arch in PE_MACHINES]

        manifest = merge_entries(config, entries)

        self.assertEqual(manifest["default"], "v26.9.9")
        self.assertEqual([(core["version"], core["arch"]) for core in manifest["cores"]],
                         [("v26.9.9", "x64"), ("v26.9.9", "arm64"),
                          ("v26.7.28", "x64"), ("v26.7.28", "arm64")])
        for broken in (entries[1:], entries + [entries[0]]):
            with self.assertRaises(ValueError):
                merge_entries(config, broken)
        for invalid in ({"default": "v1", "versions": ["v26.9.9"]},
                        {"default": "v26.9.9", "versions": ["v26.9.9", "v26.9.9"]}):
            with self.assertRaises(ValueError):
                merge_entries(invalid, entries)

    def test_cli_writes_entry_and_manifest(self):
        binary = self.root / "xray.exe"
        binary.write_bytes(_pe(PE_MACHINES["x64"]))
        metadata = self.root / "xray-core.json"
        metadata.write_text(json.dumps(_METADATA))
        versions = self.root / "versions.json"
        versions.write_text(json.dumps({"default": "v26.7.28", "versions": ["v26.7.28"]}))
        paths = []
        for arch in PE_MACHINES:
            binary.write_bytes(_pe(PE_MACHINES[arch]))
            paths.append(self.root / f"{arch}.json")
            self.assertEqual(main([
                "entry", "--binary", str(binary), "--metadata", str(metadata),
                "--version", "v26.7.28", "--query", _METADATA["requestedRef"],
                "--arch", arch, "--asset", f"core-{arch}.exe", "--output", str(paths[-1]),
            ]), 0)
        output = self.root / "cores.json"

        self.assertEqual(main(["merge", "--versions", str(versions), "--output", str(output),
                               *map(str, paths)]), 0)

        manifest = json.loads(output.read_text())
        self.assertEqual([core["file"] for core in manifest["cores"]],
                         ["core-x64.exe", "core-arm64.exe"])


if __name__ == "__main__":
    unittest.main()
