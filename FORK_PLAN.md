# План форка OneXray (передача из чата в Claude Code)

## Цель
Форк https://github.com/OneXray/OneXray (GPL-3.0) под своим названием для **Windows и Android**
с возможностью выбора версии Xray-core.

## Нужно уточнить у пользователя перед ребрендингом
- Новое название приложения: `<NAME>`
- Идентификатор пакета: `<PACKAGE_ID>` (вместо `net.yuandev.onexray`)
- GitHub-аккаунт/организация для форков: `<GH_ORG>`

## Что выяснено об устройстве проекта
- Flutter-приложение; прочитать `AGENTS.md` и `build_scripts/README.md` перед работой.
- Xray-core **не отдельный бинарник**: он компилируется внутрь `XTLS/libXray` (Go),
  версия зафиксирована в `libXray/go.mod` (`github.com/xtls/xray-core`).
- Структура workspace: `OneXray/`, `libXray/`, `VCore/` (только Windows), `output/` — соседние каталоги.
- CI: `.github/workflows/build.yml`, env `LIBXRAY_REF`, `VCORE_REPOSITORY`, `VCORE_REF`;
  сборка ядра — `build_scripts/app/builder.py` → `build_core()` запускает `libXray/build/main.py`.
- **Android**: libXray подключается как gomobile AAR (`android/app/libs`),
  `OneVpnService.kt` вызывает `libXray.LibXray.invoke(...)`. Одна версия ядра на APK.
- **Windows EXE/ZIP**: трафик идёт через отдельный процесс `OneXrayCore.exe`
  (исходник — `libXray/desktop_bin`, CLI: `run -dns -interface -config [-error-file]`),
  запускается с правами администратора (UAC). Путь задан в
  `lib/core/ffi/windows/exe_ffi_api.dart`; `ensureRuntime()` проверяет
  `libXray.dll`, `OneXrayCore.exe`, `wintun.dll`.
- **Windows MSIX** (Microsoft Store) — ядро через системный VPN-провайдер; выбор ядра не поддерживать.
- Идентификатор `net.yuandev.onexray*` (+ `.tun`, `.se`, `.vpn`, `group.net.yuandev.onexray*`)
  встречается в ~68 файлах, слово «OneXray» — в ~147. Также: схема ссылок `onexray://`,
  winget ID `YuanDevLLC.OneXray`, ссылки на onexray.com и Telegram, логотип/иконки.

## Порядок работы
1. **Форки** OneXray, libXray, VCore в `<GH_ORG>`; в `build.yml` указать свои репозитории.
2. **Скрипт ребрендинга** (идемпотентный, запускаемый повторно после merge из upstream),
   а не ручные правки. Учесть: Android `applicationId` и пакеты Kotlin, pigeon
   (`pigeon/message.dart` → перегенерация, сгенерированный код руками не править),
   Windows-идентичность, схема ссылок, иконки. iOS/macOS/Linux можно не трогать.
3. **Параметр `XRAY_CORE_REF`** в `build_scripts` и `build.yml`: перед сборкой libXray
   `go get github.com/xtls/xray-core@<ref> && go mod tidy`; фактическую версию писать в
   provenance-файл. Покрыть тестами в `build_scripts/tests`.
4. **Матрица CI** по нескольким версиям Xray:
   - Android: отдельный APK на версию (`…-xray-<ver>.apk`).
   - Windows: `OneXrayCore.exe` (x64, arm64) на каждую версию + манифест
     (версия, архитектура, SHA-256), публикация в Releases форка.
5. **Выбор ядра в настройках (Windows EXE/ZIP)**: список из манифеста, загрузка,
   проверка SHA-256, переключение пути к ядру, предупреждение о минимальной
   поддерживаемой версии. Слои: pages → service → core (см. `AGENTS.md`).

## Безопасность (обязательно)
`OneXrayCore.exe` запускается с правами администратора. Скачанные ядра нельзя
запускать из каталога, доступного на запись обычному пользователю, без проверки:
проверять SHA-256 по манифесту **перед каждым запуском** и/или хранить ядра в
защищённом каталоге. Иначе — локальное повышение привилегий.

## Лицензия
Форк остаётся под GPL-3.0; при распространении — публиковать исходники, сохранить
уведомления об авторстве, отметить изменения. Xray-core — MPL-2.0.
