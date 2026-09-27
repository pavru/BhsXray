# Ребрендинг форка

`rebrand.py` переводит исходники upstream OneXray на идентичность форка из
[`brand.json`](brand.json). Скрипт идемпотентный: его запускают после каждого
merge из upstream. Затрагиваются Android, Windows и общий Dart-код;
iOS, macOS и пакеты Linux не меняются.

```shell
python tool/rebrand/rebrand.py --check   # только отчёт; exit 1, если есть изменения или необработанные вхождения
python tool/rebrand/rebrand.py           # применить
dart run pigeon --input pigeon/message.dart
flutter gen-l10n
python -m unittest discover -s tool/rebrand/tests -p 'test_*.py'
```

Нужен Python 3.12+ без зависимостей.

## Что меняется

- Android: `applicationId`/`namespace`, Kotlin-пакет (каталоги переносятся),
  intent actions, каналы уведомлений, `fastlane/Appfile`, подписи ресурсов.
- Схема и хост App Link: `AndroidManifest.xml`, `OneXrayAppLinkParser`,
  регистрация протокола в установщике Windows, тесты.
- Видимое имя: Dart-строки, ARB, заголовок окна, `Runner.rc`, имя `.exe`, ярлык,
  установщик Inno Setup, User-Agent, имена файлов экспорта и бэкапа.
- Ссылки на репозиторий (issues, исходники, проверка обновлений), издатель
  Windows и GUID установщика (он же GUID уведомлений Windows).

Сгенерированный код (`*.g.dart`, `*.g.kt`, `*.g.swift`) скрипт не правит.
`Messages.g.kt` переносится вместе с пакетом, а затем его перегенерирует pigeon.
До перегенерации `--check` показывает его как необработанный.

## Что намеренно остаётся от upstream

- Dart-пакет `onexray` (`package:onexray/…`, каналы pigeon): иначе почти каждый
  merge давал бы конфликты.
- Имена классов и идентификаторов с `OneXray` внутри (`OneXrayAppLink`,
  `DownloadUserAgentMode.oneXray`, маршрут `about-onexray`).
- Формат бэкапа `onexray-backup`, внутренние префиксы `.onexray-*` и
  `onexray-local-socks`: совместимость данных.
- Ядро `OneXrayCore(.exe)`, интерфейс `OneXrayTun`, переменные `ONEXRAY_*`:
  их имена задают libXray и build-скрипты; переименование выполняется вместе с шагом CI.
- Документация `https://onexray.com/…`: собственной документации у форка нет.
- Текст о пожертвованиях (`donationDescription`): пожертвования идут upstream.
- Apple (iCloud-контейнер), Linux (`.desktop`), `msix_config` в `pubspec.yaml`:
  эти платформы и публикация MSIX в форке не собираются.
- Copyright Yuan Dev LLC в `Runner.rc`: GPL требует сохранять уведомления об авторстве.

Если после merge `--check` сообщает о новом вхождении, добавьте правило в
`build_rules` или шаблон в `KEPT_PATTERNS` и тест.

## Вне скрипта

- `build_scripts/app/config.py` → `app.executable.windows` повторяет `BINARY_NAME`;
  тест `test_windows_packaging.py` проверяет, что значения совпадают.
- Имена артефактов (`OneXray-windows-*.exe`, `OneXray-android-universal.apk`),
  CI и публикация остаются как в upstream, пока не будет сделан шаг CI из `FORK_PLAN.md`.
- При переносе Kotlin-файлов скрипт удаляет копию, восстановленную merge'ем,
  только если после ребрендинга она совпадает с файлом форка. Иначе он
  останавливается, и файлы нужно слить вручную.
