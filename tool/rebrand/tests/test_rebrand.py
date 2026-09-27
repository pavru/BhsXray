import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rebrand  # noqa: E402

KOTLIN_OLD = "android/app/src/main/kotlin/net/yuandev/onexray"
KOTLIN_NEW = "android/app/src/main/kotlin/net/pototskiy/bhsxray"


class RebrandTest(unittest.TestCase):
    def setUp(self):
        fixtures = (Path(__file__).resolve().parents[4] / "references" /
                    "bhsxray-rebrand" / "tests")
        fixtures.mkdir(parents=True, exist_ok=True)
        self.temp_dir = tempfile.TemporaryDirectory(dir=fixtures, prefix="rebrand-")
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)

    def write(self, path: str, content: str) -> None:
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content.encode("utf-8"))

    def read(self, path: str) -> str:
        return (self.root / path).read_bytes().decode("utf-8")

    def run_rebrand(self, write: bool = True) -> rebrand.Report:
        return rebrand.run(self.root, rebrand.DEFAULT_CONFIG, write=write)

    def write_sample(self) -> None:
        self.write(f"{KOTLIN_OLD}/vpn/Service.kt",
                   "package net.yuandev.onexray.vpn\r\n"
                   "import net.yuandev.onexray.R\r\n"
                   'const val ACTION = "net.yuandev.onexray.VPN_STATUS" // OneXray\r\n')
        self.write(f"{KOTLIN_OLD}/pigeon/Messages.g.kt", "package net.yuandev.onexray.pigeon\n")
        self.write("android/app/src/main/AndroidManifest.xml",
                   'android:label="OneXray"\n'
                   'android:host="onexray.com"\n'
                   'android:scheme="onexray" />\n')
        self.write("lib/sample.dart", "\n".join((
            "import 'package:onexray/core/x.dart';",
            "const scheme = 'onexray';",
            "const host = 'onexray.com';",
            "const docs = 'https://onexray.com/docs/';",
            "const repo = 'https://github.com/OneXray/OneXray/issues/new';",
            "const backup = 'OneXray-backup.json';",
            "const format = 'onexray-backup';",
            "const core = 'OneXrayCore.exe';",
            "const exe = 'onexray.exe';",
            "const icloud = 'iCloud.net.yuandev.onexray';",
            "const links = 'onexray://a\\nonexray://b';",
            "final class OneXrayAppLink {}",
            "",
        )))
        self.write("lib/service/shared/doc/helper.dart",
                   '  static const _domain = "onexray.com";\n')
        self.write("lib/l10n/app_en.arb", "\n".join((
            "{",
            '  "donationDescription": "Support OneXray development.",',
            '  "welcome": "Welcome to OneXray",',
            '  "prototypeAboutOneXray": "About OneXray",',
            '  "cjk": "使用OneXray"',
            "}",
            "",
        )))
        self.write("windows/packaging/exe/inno_setup.iss", "\n".join((
            "AppUpdatesURL=https://onexray.com",
            'Root: HKCU; Subkey: "Software\\Classes\\onexray"; ValueData: "URL:OneXray Protocol"',
            "",
        )))
        self.write("windows/runner/Runner.rc", 'VALUE "CompanyName", "YuanDevLLC" "\\0"\n')
        self.write("pigeon/message.dart",
                   f"kotlinOut: '{KOTLIN_OLD}/pigeon/Messages.g.kt',\n"
                   "KotlinOptions(package: \"net.yuandev.onexray.pigeon\"),\n"
                   "dartPackageName: 'onexray',\n")

    def test_apply_rewrites_fork_identity_and_keeps_compatibility_names(self):
        self.write_sample()

        report = self.run_rebrand()

        self.assertFalse((self.root / KOTLIN_OLD).exists())
        self.assertFalse((self.root / "android/app/src/main/kotlin/net/yuandev").exists())
        self.assertEqual(
            self.read(f"{KOTLIN_NEW}/vpn/Service.kt"),
            "package net.pototskiy.bhsxray.vpn\r\n"
            "import net.pototskiy.bhsxray.R\r\n"
            'const val ACTION = "net.pototskiy.bhsxray.VPN_STATUS" // BhsXRay\r\n')
        self.assertEqual(
            self.read("android/app/src/main/AndroidManifest.xml"),
            'android:label="BhsXRay"\n'
            'android:host="bhsxray.pototskiy.net"\n'
            'android:scheme="bhsxray" />\n')
        self.assertEqual(self.read("lib/sample.dart"), "\n".join((
            "import 'package:onexray/core/x.dart';",
            "const scheme = 'bhsxray';",
            "const host = 'bhsxray.pototskiy.net';",
            "const docs = 'https://onexray.com/docs/';",
            "const repo = 'https://github.com/pavru/OneXray/issues/new';",
            "const backup = 'BhsXRay-backup.json';",
            "const format = 'onexray-backup';",
            "const core = 'OneXrayCore.exe';",
            "const exe = 'bhsxray.exe';",
            "const icloud = 'iCloud.net.yuandev.onexray';",
            "const links = 'bhsxray://a\\nbhsxray://b';",
            "final class OneXrayAppLink {}",
            "",
        )))
        self.assertEqual(self.read("lib/service/shared/doc/helper.dart"),
                         '  static const _domain = "onexray.com";\n')
        self.assertEqual(self.read("lib/l10n/app_en.arb"), "\n".join((
            "{",
            '  "donationDescription": "Support OneXray development.",',
            '  "welcome": "Welcome to BhsXRay",',
            '  "prototypeAboutOneXray": "About BhsXRay",',
            '  "cjk": "使用BhsXRay"',
            "}",
            "",
        )))
        self.assertEqual(self.read("windows/packaging/exe/inno_setup.iss"), "\n".join((
            "AppUpdatesURL=https://github.com/pavru/OneXray",
            'Root: HKCU; Subkey: "Software\\Classes\\bhsxray"; ValueData: "URL:BhsXRay Protocol"',
            "",
        )))
        self.assertEqual(self.read("windows/runner/Runner.rc"),
                         'VALUE "CompanyName", "Alex Pototskiy" "\\0"\n')
        self.assertEqual(self.read("pigeon/message.dart"),
                         f"kotlinOut: '{KOTLIN_NEW}/pigeon/Messages.g.kt',\n"
                         "KotlinOptions(package: \"net.pototskiy.bhsxray.pigeon\"),\n"
                         "dartPackageName: 'onexray',\n")
        # Generated code moves with its package but is left for regeneration.
        self.assertEqual(self.read(f"{KOTLIN_NEW}/pigeon/Messages.g.kt"),
                         "package net.yuandev.onexray.pigeon\n")
        self.assertEqual([(path, line) for path, line, _ in report.residuals],
                         [(f"{KOTLIN_NEW}/pigeon/Messages.g.kt", 1)])

    def test_second_run_changes_nothing(self):
        self.write_sample()
        self.run_rebrand()
        before = {path: (self.root / path).read_bytes()
                  for path in rebrand.list_files(self.root)}

        report = self.run_rebrand()

        self.assertFalse(report.pending)
        self.assertEqual(before, {path: (self.root / path).read_bytes()
                                  for path in rebrand.list_files(self.root)})

    def test_check_reports_without_writing(self):
        self.write_sample()
        manifest = self.read("android/app/src/main/AndroidManifest.xml")

        report = self.run_rebrand(write=False)

        self.assertTrue(report.pending)
        self.assertIn((f"{KOTLIN_OLD}/vpn/Service.kt", f"{KOTLIN_NEW}/vpn/Service.kt"),
                      report.moves)
        self.assertIn(f"{KOTLIN_NEW}/vpn/Service.kt", report.changes)
        self.assertTrue((self.root / KOTLIN_OLD).is_dir())
        self.assertEqual(self.read("android/app/src/main/AndroidManifest.xml"), manifest)
        self.assertEqual(rebrand.main(["--check", "--root", str(self.root)]), 1)

    def test_unhandled_occurrence_is_reported(self):
        self.write("lib/unknown.dart", "const vendor = 'yuandev';\n")

        report = self.run_rebrand()

        self.assertEqual(report.residuals,
                         [("lib/unknown.dart", 1, "const vendor = 'yuandev';")])

    def test_restored_upstream_duplicate_is_removed(self):
        self.write(f"{KOTLIN_OLD}/A.kt", "package net.yuandev.onexray\n")
        self.write(f"{KOTLIN_NEW}/A.kt", "package net.pototskiy.bhsxray\n")

        self.run_rebrand()

        self.assertFalse((self.root / KOTLIN_OLD).exists())
        self.assertEqual(self.read(f"{KOTLIN_NEW}/A.kt"), "package net.pototskiy.bhsxray\n")

    def test_diverged_move_requires_manual_merge(self):
        self.write(f"{KOTLIN_OLD}/A.kt", "package net.yuandev.onexray\nfun upstream() {}\n")
        self.write(f"{KOTLIN_NEW}/A.kt", "package net.pototskiy.bhsxray\n")

        with self.assertRaises(rebrand.RebrandError):
            self.run_rebrand()
        self.assertEqual(self.read(f"{KOTLIN_NEW}/A.kt"), "package net.pototskiy.bhsxray\n")


if __name__ == "__main__":
    unittest.main()
