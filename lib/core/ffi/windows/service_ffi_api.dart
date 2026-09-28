import 'dart:async';
import 'dart:convert';

import 'package:onexray/core/ffi/windows/core_service.dart';
import 'package:onexray/core/ffi/windows/ffi_api.dart';
import 'package:onexray/core/ffi/windows/model.dart';
import 'package:onexray/core/pigeon/constants.dart';
import 'package:onexray/core/pigeon/flutter_api.dart';
import 'package:onexray/core/pigeon/messages.g.dart';
import 'package:onexray/core/pigeon/model.dart';
import 'package:onexray/core/pigeon/model_reader.dart';
import 'package:onexray/core/tools/logger.dart';

/// EXE mode of installed releases: the Core service the installer registers
/// runs the Core as SYSTEM, so connecting needs no UAC prompt. The service
/// state is authoritative; `watch` requests report changes such as a Core
/// that exits on its own.
class WindowsServiceFfiApi extends WindowsFfiApi {
  final WindowsCoreService _service;
  final String? _filesDirectory;
  final Future<StartVpnRequest> Function() _readRequest;
  final Future<void> Function(VpnStatus) _notify;
  final void Function(Object) _notifyError;
  final String Function() _assetsDirectory;
  // Each observation owns one watch loop; a new generation retires the old.
  int _watchGeneration = 0;
  bool _observing = false;
  VpnStatus? _transition;

  WindowsServiceFfiApi({
    this._service = const WindowsCoreService(),
    this._filesDirectory,
    Future<StartVpnRequest> Function()? readRequest,
    Future<void> Function(VpnStatus)? notify,
    void Function(Object)? notifyError,
    String Function()? assetsDirectory,
  }) : _readRequest = readRequest ?? StartVpnRequestReader.readFromStartFile,
       _notify = notify ?? AppFlutterApi().vpnStatusChanged,
       _notifyError =
           notifyError ?? AppFlutterApi().vpnStatusController.addError,
       _assetsDirectory = assetsDirectory ?? (() => VpnConstants.datDir),
       super.base();

  @override
  Future<String> getTunFilesDir() async =>
      _filesDirectory ?? await super.getTunFilesDir();

  @override
  Future<void> ensureRuntime() =>
      checkRuntimeFiles(const ['libXray.dll', 'OneXrayCore.exe', 'wintun.dll']);

  @override
  Future<void> observeVpnStatus() async {
    _observing = true;
    final generation = ++_watchGeneration;
    final CoreServiceResponse status;
    try {
      status = await _service.status();
    } catch (_) {
      if (generation == _watchGeneration) disposeVpnStatus();
      rethrow;
    }
    unawaited(_watch(generation, status.running));
  }

  Future<void> _watch(int generation, bool running) async {
    bool current() => _observing && generation == _watchGeneration;
    while (current()) {
      final CoreServiceResponse response;
      try {
        response = await _service.watch(running: running);
      } catch (error) {
        if (current() && _transition == null) _notifyError(error);
        return;
      }
      if (!current()) return;
      if (response.running == running) continue;
      running = response.running;
      // Start and stop report their own outcome.
      if (_transition == null) {
        await _notify(running ? VpnStatus.connected : VpnStatus.disconnected);
      }
    }
  }

  @override
  void disposeVpnStatus() {
    _observing = false;
    _watchGeneration++;
  }

  @override
  Future<NativeVpnCommandResult> readVpnStatus() async {
    try {
      final status = await _service.status();
      return commandSuccess(
        status:
            _transition ??
            (status.running ? VpnStatus.connected : VpnStatus.disconnected),
      );
    } catch (error, stackTrace) {
      return _failed('read', error, stackTrace);
    }
  }

  @override
  Future<bool?> cleanupStaleCore() async {
    final status = await readVpnStatus();
    return status.state == NativeVpnCommandState.success;
  }

  @override
  Future<NativeVpnCommandResult> startVpn({
    String? configYaml,
    WindowsVpnNetworkSettings? networkSettings,
    WindowsVpnPolicy policy = const WindowsVpnPolicy(
      alwaysOn: false,
      allowLocalNetwork: true,
      excludedCidrs: [],
    ),
  }) async {
    _transition = VpnStatus.connecting;
    try {
      await _notify(VpnStatus.connecting);
      final request = await _readRequest();
      final xrayJson = readRunXrayRequest(request).request.xrayJson;
      if (xrayJson == null || xrayJson.isEmpty) {
        throw const FormatException('xrayJson is empty');
      }
      final dns = request.tun?.tunDnsIPv4 ?? '';
      final interfaceName = request.tun?.autoOutboundsInterface ?? '';
      if (dns.isEmpty || interfaceName.isEmpty) {
        throw const FormatException('Core DNS or interface is missing');
      }
      final response = await _service.start(
        config: xrayJson,
        dns: '$dns:53',
        interfaceName: interfaceName,
        assets: _configuredAssets(xrayJson) ?? _assetsDirectory(),
      );
      if (!response.ok) throw StateError(response.error);
      await _notify(VpnStatus.connected);
      return commandSuccess(status: VpnStatus.connected);
    } catch (error, stackTrace) {
      try {
        if (!(await _service.status()).running) {
          await _notify(VpnStatus.disconnected);
        }
      } catch (statusError) {
        ygLogger('read Windows Core service after start: $statusError');
      }
      return _failed('start', error, stackTrace);
    } finally {
      _transition = null;
    }
  }

  @override
  Future<NativeVpnCommandResult> stopVpn() async {
    _transition = VpnStatus.disconnecting;
    try {
      await _notify(VpnStatus.disconnecting);
      final response = await _service.stop();
      if (!response.ok) throw StateError(response.error);
      await _notify(VpnStatus.disconnected);
      return commandSuccess(status: VpnStatus.disconnected);
    } catch (error, stackTrace) {
      return _failed('stop', error, stackTrace);
    } finally {
      _transition = null;
    }
  }

  // The service copies Geodata from where the configuration expects it.
  String? _configuredAssets(String xrayJson) {
    final root = jsonDecode(xrayJson);
    final env = root is Map ? root['env'] : null;
    final assets = env is Map ? env['xray.location.asset'] : null;
    return assets is String && assets.isNotEmpty ? assets : null;
  }

  NativeVpnCommandResult _failed(
    String operation,
    Object error,
    StackTrace stackTrace,
  ) {
    ygLogger('$operation Windows Core service failed: $error\n$stackTrace');
    return commandFailed(error.toString());
  }
}
