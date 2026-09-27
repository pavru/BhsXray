import 'package:onexray/core/model/xray_json.dart';

XrayOutbound createFreedomOutbound({
  required String tag,
  String? interfaceName,
}) => XrayOutbound(
  tag: tag,
  protocol: 'freedom',
  streamSettings: interfaceName == null
      ? null
      : XrayStreamSettings(sockopt: XraySockopt(interface: interfaceName)),
);

XrayOutbound createBlackholeOutbound({required String tag}) =>
    XrayOutbound(tag: tag, protocol: 'blackhole');

XrayOutbound createDnsOutbound({
  required String tag,
  required String dialerProxy,
  bool answerServiceBinding = false,
}) => XrayOutbound(
  tag: tag,
  protocol: 'dns',
  settings: {
    'rules': [
      const XrayOutboundDnsRule(action: 'hijack', qType: '1,28'),
      // Browsers query HTTPS (65) and SVCB (64) records for every site; when
      // other types leave outside the tunnel, answer these locally with an
      // empty response instead of exposing the visited domains.
      if (answerServiceBinding)
        const XrayOutboundDnsRule(action: 'return', qType: '64,65'),
      const XrayOutboundDnsRule(action: 'direct'),
    ].map((rule) => rule.toJson()).toList(),
  },
  streamSettings: XrayStreamSettings(
    sockopt: XraySockopt(dialerProxy: dialerProxy),
  ),
);
