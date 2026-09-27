import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:onexray/core/tools/logger.dart';
import 'package:onexray/core/tools/platform.dart';

final class NotificationService {
  static final NotificationService _singleton = NotificationService._internal();

  factory NotificationService() => _singleton;

  NotificationService._internal();

  //==========================
  final _localNotification = FlutterLocalNotificationsPlugin();

  Future<void> asyncInit() async {
    const initializationSettingsAndroid = AndroidInitializationSettings(
      'ic_launcher',
    );
    const initializationSettingsDarwin = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestSoundPermission: false,
      requestBadgePermission: false,
    );
    final initializationSettingsLinux = LinuxInitializationSettings(
      defaultActionName: 'Open notification',
    );
    final WindowsInitializationSettings initializationSettingsWindows =
        WindowsInitializationSettings(
          appName: 'BhsXRay',
          appUserModelId: 'net.pototskiy.bhsxray',
          // Search online for GUID generators to make your own
          guid: '292e71ae-61e0-439a-8310-20d2febca33d',
        );
    final initializationSettings = InitializationSettings(
      android: initializationSettingsAndroid,
      iOS: initializationSettingsDarwin,
      macOS: initializationSettingsDarwin,
      linux: initializationSettingsLinux,
      windows: initializationSettingsWindows,
    );
    await _localNotification.initialize(
      settings: initializationSettings,
      onDidReceiveNotificationResponse: _onReceiveNotification,
    );

    if (AppPlatform.isAndroid) {
      await _localNotification
          .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin
          >()
          ?.requestNotificationsPermission();
    }
  }

  Future<void> _onReceiveNotification(
    NotificationResponse notificationResponse,
  ) async {
    final payload = notificationResponse.payload;
    if (payload != null) {
      ygLogger(payload);
    }
  }

  Future<void> pushNotification(String message) async {
    if (AppPlatform.isIOS) {
      await _localNotification
          .resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin
          >()
          ?.requestPermissions(alert: true);
    } else if (AppPlatform.isMacOS) {
      await _localNotification
          .resolvePlatformSpecificImplementation<
            MacOSFlutterLocalNotificationsPlugin
          >()
          ?.requestPermissions(alert: true);
    }

    if (AppPlatform.isAndroid) {
      const details = NotificationDetails(
        android: AndroidNotificationDetails(
          'net.pototskiy.bhsxray',
          'BhsXRay',
          channelDescription: 'BhsXRay',
          importance: Importance.defaultImportance,
          priority: Priority.defaultPriority,
          ticker: 'BhsXRay',
        ),
      );
      await _localNotification.show(
        id: 0,
        title: message,
        notificationDetails: details,
      );
      return;
    }
    await _localNotification.show(id: 0, title: message);
  }
}
