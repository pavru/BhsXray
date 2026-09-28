import 'package:onexray/core/ffi/windows/core_service.dart';
import 'package:onexray/core/ffi/windows/mode.dart';
import 'package:onexray/core/pigeon/host_api.dart';
import 'package:onexray/core/tools/platform.dart';
import 'package:path/path.dart' as p;

class VpnConstants {
  static const tunMtu = 1500;

  /// The only App-side Geodata directory. Installed files are always flat.
  static String get datDir => p.join(AppHostApi().tunFilesDir, "dat");
  static const systemGeoTimestamp = "timestamp.txt";

  static String get runDir => p.join(AppHostApi().tunFilesDir, "run");

  static String get startPath => p.join(runDir, "start.json");

  /// Where Xray writes its logs. The Windows Core service writes them only to
  /// its own folder, which the App user may read.
  static String get logDir =>
      AppPlatform.isWindows &&
          windowsBuildMode == WindowsMode.exe &&
          windowsCoreServiceEnabled
      ? windowsCoreServiceLogDirectory()
      : runDir;
}
