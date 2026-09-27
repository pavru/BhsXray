import 'dart:io';

import 'package:path/path.dart' as p;

/// Files the elevated Core runs or loads from its own directory.
const elevatedCoreFiles = ['OneXrayCore.exe', 'wintun.dll'];

/// Fails when the user running the App could replace the elevated Core or
/// plant a DLL beside it.
///
/// The Core starts through a UAC prompt the user expects after pressing
/// Connect. From a user-writable directory (a per-user install or an extracted
/// archive), any program running as that user could swap the files first and
/// receive administrator rights from that prompt. Installs under Program Files
/// are writable only by administrators.
Future<void> verifyProtectedInstall(String directory) async {
  final probe = File(
    p.join(
      directory,
      '.write-probe-$pid-${DateTime.now().microsecondsSinceEpoch}',
    ),
  );
  var writable = await _canCreate(probe);
  for (final name in elevatedCoreFiles) {
    if (writable) break;
    writable = await _canWrite(File(p.join(directory, name)));
  }
  if (writable) {
    throw StateError(
      'The VPN Core is in a folder that standard users can modify ($directory), '
      'so starting it as administrator is unsafe. Install the App with its '
      'installer, which places it under Program Files.',
    );
  }
}

Future<bool> _canCreate(File probe) async {
  try {
    await probe.create(exclusive: true);
  } on FileSystemException {
    return false;
  }
  try {
    await probe.delete();
  } on FileSystemException {
    // The probe proved the directory is writable either way.
  }
  return true;
}

Future<bool> _canWrite(File file) async {
  // Appending never creates a missing file and never changes an existing one.
  if (!await file.exists()) return false;
  try {
    final handle = await file.open(mode: FileMode.append);
    await handle.close();
    return true;
  } on FileSystemException {
    return false;
  }
}
