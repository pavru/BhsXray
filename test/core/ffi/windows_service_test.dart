import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:onexray/core/ffi/windows/core_service.dart';
import 'package:onexray/core/ffi/windows/service_ffi_api.dart';
import 'package:onexray/core/model/tun_json.dart';
import 'package:onexray/core/pigeon/messages.g.dart';
import 'package:onexray/core/pigeon/model.dart';

void main() {
  late _Service service;
  late List<VpnStatus> events;
  late List<Object> errors;

  WindowsServiceFfiApi create({String xrayJson = '{"inbounds":[]}'}) =>
      WindowsServiceFfiApi(
        service: service,
        filesDirectory: 'unused',
        readRequest: () async => StartVpnRequest(
          TunJson.fromJson({
            'tunDnsIPv4': '8.8.8.8',
            'autoOutboundsInterface': 'Ethernet 2',
          }),
          '18187',
          '18186',
          jsonEncode(
            LibXrayInvokeRequest(
              method: LibXrayMethod.runXray,
              payload: RunXrayRequest(xrayJson).toJson(),
            ).toJson(),
          ),
        ),
        notify: (status) async => events.add(status),
        notifyError: errors.add,
        assetsDirectory: () => r'C:\App\dat',
      );

  setUp(() {
    service = _Service();
    events = [];
    errors = [];
  });

  test('frames requests as a little-endian length and UTF-8 JSON', () {
    final frame = encodeCoreServiceMessage({'command': 'status', 'x': 'ё'});
    final body = utf8.encode('{"command":"status","x":"ё"}');
    expect(
      ByteData.sublistView(frame).getUint32(0, Endian.little),
      body.length,
    );
    expect(frame.sublist(4), body);
  });

  test('reads service responses strictly', () {
    final response = CoreServiceResponse.fromJson({
      'ok': true,
      'state': 'running',
    });
    expect(response.ok, isTrue);
    expect(response.running, isTrue);
    expect(response.error, isEmpty);
    expect(
      CoreServiceResponse.fromJson({'ok': false, 'error': 'denied'}).error,
      'denied',
    );
    expect(() => CoreServiceResponse.fromJson({}), throwsFormatException);
    expect(() => CoreServiceResponse.fromJson([]), throwsFormatException);
  });

  test('service logs live in SYSTEM\'s profile', () {
    expect(
      windowsCoreServiceLogDirectory().toLowerCase(),
      endsWith(r'\config\systemprofile\appdata\local\bhsxraycore\logs'),
    );
  });

  test('start sends the configuration, DNS, interface and assets', () async {
    final api = create(
      xrayJson: '{"env":{"xray.location.asset":"D:\\\\geo"},"inbounds":[]}',
    );
    final result = await api.startVpn();
    expect(result.state, NativeVpnCommandState.success);
    expect(result.status, VpnStatus.connected);
    expect(events, [VpnStatus.connecting, VpnStatus.connected]);
    expect(service.started, [
      (
        config: '{"env":{"xray.location.asset":"D:\\\\geo"},"inbounds":[]}',
        dns: '8.8.8.8:53',
        interfaceName: 'Ethernet 2',
        assets: r'D:\geo',
      ),
    ]);

    await create().startVpn();
    expect(service.started.last.assets, r'C:\App\dat');
  });

  test('a refused start reports the service error and disconnects', () async {
    service.startResponse = const CoreServiceResponse(
      ok: false,
      running: false,
      error: 'configuration field "keyFile" names a file',
    );
    final result = await create().startVpn();
    expect(result.state, NativeVpnCommandState.failed);
    expect(result.message, contains('keyFile'));
    expect(events, [VpnStatus.connecting, VpnStatus.disconnected]);
  });

  test('an unavailable service fails without inventing a state', () async {
    service.failure = StateError('The BhsXRay Core service is not running');
    final api = create();
    expect((await api.startVpn()).state, NativeVpnCommandState.failed);
    expect(events, [VpnStatus.connecting]);
    expect((await api.readVpnStatus()).state, NativeVpnCommandState.failed);
    expect(await api.cleanupStaleCore(), isFalse);
    await expectLater(api.observeVpnStatus(), throwsStateError);
  });

  test('stop and status follow the service', () async {
    final api = create();
    service.running = true;
    expect((await api.readVpnStatus()).status, VpnStatus.connected);
    final result = await api.stopVpn();
    expect(result.status, VpnStatus.disconnected);
    expect(events, [VpnStatus.disconnecting, VpnStatus.disconnected]);
    expect((await api.readVpnStatus()).status, VpnStatus.disconnected);
  });

  test('watching reports a Core that stops on its own', () async {
    service.running = true;
    final api = create();
    await api.observeVpnStatus();
    service.change(running: false);
    await pumpEventQueue();
    expect(events, [VpnStatus.disconnected]);

    api.disposeVpnStatus();
    service.change(running: true);
    await pumpEventQueue();
    expect(events, [VpnStatus.disconnected]);
    expect(errors, isEmpty);
  });
}

typedef _Start = ({
  String config,
  String dns,
  String interfaceName,
  String assets,
});

final class _Service implements WindowsCoreService {
  bool running = false;
  Object? failure;
  CoreServiceResponse? startResponse;
  final started = <_Start>[];
  var _changed = Completer<void>();

  void change({required bool running}) {
    this.running = running;
    final changed = _changed;
    _changed = Completer<void>();
    changed.complete();
  }

  CoreServiceResponse get _status =>
      CoreServiceResponse(ok: true, running: running);

  Future<CoreServiceResponse> _answer(CoreServiceResponse Function() work) {
    final failure = this.failure;
    if (failure != null) return Future.error(failure);
    return Future.value(work());
  }

  @override
  Future<CoreServiceResponse> start({
    required String config,
    required String dns,
    required String interfaceName,
    required String assets,
  }) => _answer(() {
    started.add((
      config: config,
      dns: dns,
      interfaceName: interfaceName,
      assets: assets,
    ));
    final response = startResponse;
    if (response != null) return response;
    running = true;
    return _status;
  });

  @override
  Future<CoreServiceResponse> stop() => _answer(() {
    running = false;
    return _status;
  });

  @override
  Future<CoreServiceResponse> status() => _answer(() => _status);

  @override
  Future<CoreServiceResponse> watch({required bool running}) async {
    while (this.running == running) {
      await _changed.future;
    }
    return _status;
  }
}
