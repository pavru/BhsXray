import 'dart:convert';
import 'dart:ffi';
import 'dart:io';
import 'dart:isolate';

import 'package:ffi/ffi.dart';
import 'package:flutter/foundation.dart';
import 'package:path/path.dart' as p;
import 'package:win32/win32.dart';

/// Names the installer registers the Core service with
/// (`windows/packaging/exe/inno_setup.iss`).
const windowsCoreServiceName = 'BhsXRayCore';
const windowsCoreServicePipe = r'\\.\pipe\BhsXRay.Core';

/// Where the Core service writes Xray logs; the App user may read them. The
/// service computes the same folder inside SYSTEM's profile.
String windowsCoreServiceLogDirectory() => p.windows.join(
  _systemDirectory(),
  'config',
  'systemprofile',
  'AppData',
  'Local',
  windowsCoreServiceName,
  'logs',
);

final class CoreServiceResponse {
  final bool ok;
  final bool running;

  /// With [ok] false, why the request failed; otherwise the last Core failure.
  final String error;

  const CoreServiceResponse({
    required this.ok,
    required this.running,
    this.error = '',
  });

  factory CoreServiceResponse.fromJson(Object? json) {
    if (json is! Map<String, dynamic> || json['ok'] is! bool) {
      throw const FormatException('Invalid Core service response');
    }
    final state = json['state'];
    final error = json['error'];
    return CoreServiceResponse(
      ok: json['ok'] as bool,
      running: state == 'running',
      error: error is String ? error : '',
    );
  }
}

/// Requests to the Core service; see libXray's README, "Windows Core service".
class WindowsCoreService {
  final String _pipe;

  const WindowsCoreService() : _pipe = windowsCoreServicePipe;

  @visibleForTesting
  const WindowsCoreService.forTesting({required this._pipe});

  Future<CoreServiceResponse> start({
    required String config,
    required String dns,
    required String interfaceName,
    required String assets,
  }) => _send({
    'command': 'start',
    'config': config,
    'dns': dns,
    'interface': interfaceName,
    'assets': assets,
  });

  Future<CoreServiceResponse> stop() => _send({'command': 'stop'});

  Future<CoreServiceResponse> status() => _send({'command': 'status'});

  /// Answers when the Core state differs from [running], or after a while
  /// with the unchanged state.
  Future<CoreServiceResponse> watch({required bool running}) =>
      _send({'command': 'watch', 'known': running ? 'running' : 'stopped'});

  Future<CoreServiceResponse> _send(Map<String, Object?> request) {
    final pipe = _pipe;
    final body = encodeCoreServiceMessage(request);
    return Isolate.run(
      () => CoreServiceResponse.fromJson(
        jsonDecode(utf8.decode(_exchange(pipe, body))),
      ),
    );
  }
}

const _maxMessageBytes = 32 * 1024 * 1024;

/// A 4-byte little-endian length followed by UTF-8 JSON.
@visibleForTesting
Uint8List encodeCoreServiceMessage(Map<String, Object?> message) {
  final body = utf8.encode(jsonEncode(message));
  if (body.length > _maxMessageBytes) {
    throw const FormatException('Core service request is too large');
  }
  final frame = Uint8List(4 + body.length);
  ByteData.sublistView(frame).setUint32(0, body.length, Endian.little);
  frame.setRange(4, frame.length, body);
  return frame;
}

Uint8List _exchange(String path, Uint8List request) {
  final handle = _open(path);
  try {
    _checkOwner(handle);
    _write(handle, request);
    final size = ByteData.sublistView(_read(handle, 4))
        .getUint32(0, Endian.little);
    if (size == 0 || size > _maxMessageBytes) {
      throw const FormatException('Invalid Core service response size');
    }
    return _read(handle, size);
  } finally {
    CloseHandle(handle);
  }
}

HANDLE _open(String path) => using((arena) {
  final name = arena.pcwstr(path);
  final waiting = Stopwatch()..start();
  while (true) {
    // Without FILE_APPEND_DATA, which doubles as the right to create pipe
    // instances and which the service withholds from users.
    final opened = CreateFile(
      name,
      GENERIC_READ | FILE_WRITE_DATA,
      FILE_SHARE_NONE,
      null,
      OPEN_EXISTING,
      const FILE_FLAGS_AND_ATTRIBUTES(0),
      null,
    );
    if (opened.value.isValid) return opened.value;
    if (opened.error == ERROR_FILE_NOT_FOUND) {
      throw StateError(
        'The BhsXRay Core service is not running. Install BhsXRay again to '
        'restore it.',
      );
    }
    // Between connections the service may not have its next instance yet.
    if (opened.error != ERROR_PIPE_BUSY ||
        waiting.elapsed > const Duration(seconds: 5)) {
      throw StateError('Core service connection failed: ${opened.error}');
    }
    sleep(const Duration(milliseconds: 20));
  }
});

// Anyone may create a pipe with a free name, so a program running as this user
// could pose as the service before it starts and receive the configuration.
// The service's pipe belongs to SYSTEM (or Administrators); a user's does not.
void _checkOwner(HANDLE handle) => using((arena) {
  final owner = arena<Pointer>();
  final descriptor = arena<Pointer>();
  final result = _getSecurityInfo(
    handle,
    _seKernelObject,
    OWNER_SECURITY_INFORMATION,
    owner,
    nullptr,
    nullptr,
    nullptr,
    descriptor,
  );
  if (result != 0) throw StateError('Core service owner check failed: $result');
  try {
    if (_isWellKnownSid(owner.value, _winLocalSystemSid) == 0 &&
        _isWellKnownSid(owner.value, _winBuiltinAdministratorsSid) == 0) {
      throw StateError('The Core service pipe is not owned by the system');
    }
  } finally {
    LocalFree(HLOCAL(descriptor.value));
  }
});

void _write(HANDLE handle, Uint8List data) => using((arena) {
  final buffer = arena<Uint8>(data.length);
  buffer.asTypedList(data.length).setAll(0, data);
  final written = arena<Uint32>();
  var offset = 0;
  while (offset < data.length) {
    final result = WriteFile(
      handle,
      buffer + offset,
      data.length - offset,
      written,
      null,
    );
    if (!result.value) {
      throw StateError('Core service write failed: ${result.error}');
    }
    offset += written.value;
  }
});

Uint8List _read(HANDLE handle, int length) => using((arena) {
  final buffer = arena<Uint8>(length);
  final read = arena<Uint32>();
  var offset = 0;
  while (offset < length) {
    final result = ReadFile(
      handle,
      buffer + offset,
      length - offset,
      read,
      null,
    );
    if (!result.value || read.value == 0) {
      throw StateError('Core service read failed: ${result.error}');
    }
    offset += read.value;
  }
  return Uint8List.fromList(buffer.asTypedList(length));
});

String _systemDirectory() => using((arena) {
  final buffer = arena.pwstrBuffer(32768);
  final result = GetSystemDirectory(buffer, 32768);
  if (result.value == 0 || result.value >= 32768) {
    throw StateError('GetSystemDirectory failed: ${result.error}');
  }
  return buffer.toDartString();
});

// Not exposed by package:win32.
const _seKernelObject = 6;
const _winLocalSystemSid = 22;
const _winBuiltinAdministratorsSid = 26;

final _advapi32 = DynamicLibrary.open('advapi32.dll');

final _getSecurityInfo = _advapi32
    .lookupFunction<
      Uint32 Function(
        Pointer,
        Int32,
        Uint32,
        Pointer<Pointer>,
        Pointer<Pointer>,
        Pointer<Pointer>,
        Pointer<Pointer>,
        Pointer<Pointer>,
      ),
      int Function(
        Pointer,
        int,
        int,
        Pointer<Pointer>,
        Pointer<Pointer>,
        Pointer<Pointer>,
        Pointer<Pointer>,
        Pointer<Pointer>,
      )
    >('GetSecurityInfo');

final _isWellKnownSid = _advapi32
    .lookupFunction<Int32 Function(Pointer, Int32), int Function(Pointer, int)>(
      'IsWellKnownSid',
    );
