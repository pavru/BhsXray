import 'package:flutter/foundation.dart';

enum WindowsMode { exe, msix }

/// EXE builds start the Core through the Core service the installer
/// registers. Debug builds run from the build folder without that service and
/// elevate the Core with a UAC prompt instead.
const windowsCoreServiceEnabled = bool.fromEnvironment(
  'BHSXRAY_WINDOWS_CORE_SERVICE',
  defaultValue: kReleaseMode,
);

const _configuredMode = String.fromEnvironment(
  'ONEXRAY_WINDOWS_MODE',
  defaultValue: 'exe',
);

WindowsMode get windowsBuildMode => switch (_configuredMode) {
  'exe' => WindowsMode.exe,
  'msix' => WindowsMode.msix,
  _ => throw UnsupportedError(
    'ONEXRAY_WINDOWS_MODE must be exe or msix: $_configuredMode',
  ),
};
