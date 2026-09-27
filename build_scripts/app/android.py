import os
import shutil
from pathlib import Path

from app.builder import Builder
from app.command_line import check_and_create_dir, run_command

# Named like the Play-downloaded APK so provenance records it the same way.
UNIVERSAL_APK_NAME = "OneXray-android-universal.apk"


def android_package(project_config: dict) -> str:
    """Returns "apk" to sign locally or "appbundle" to publish through Google Play."""
    return project_config.get("android.package", "appbundle")


class AndroidBuilder(Builder):
    def before_build(self):
        super().before_build()
        self.build_core()
        if android_package(self.project_config) == "appbundle":
            self.fix_fastlane_version_code()

    def fix_fastlane_version_code(self):
        file_path = os.path.join(self.project_dir, "fastlane", "Fastfile")
        with open(file_path, mode="r") as f:
            text = f.read()
            text = text.replace("##version_code##", f"{self.build_number}")

        with open(file_path, mode="w") as f:
            f.write(text)

    def build_app(self):
        if android_package(self.project_config) == "apk":
            apk = Path(self.root_dir) / "build/app/outputs/flutter-apk/app-release.apk"
            if not apk.is_file():
                raise FileNotFoundError(f"Release APK missing: {apk}")
            check_and_create_dir(self.output_dir)
            shutil.copy2(apk, Path(self.output_dir) / UNIVERSAL_APK_NAME)
            return
        run_command(["fastlane", self.fastlane, "--verbose"], cwd=self.project_dir)
