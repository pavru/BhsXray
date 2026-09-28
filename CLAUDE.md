# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

The authoritative engineering rules live in `AGENTS.md` (imported below) and the
contracts indexed in `docs/README.md`. This file adds commands and a map of the
architecture; when they disagree, `AGENTS.md` and `docs/` win.

@AGENTS.md

## Commands

All `flutter`/`dart` commands must run **serially** (shared `.dart_tool` and native-asset state) — never in parallel tool calls or agents.

```shell
flutter pub get
flutter gen-l10n                                   # after editing lib/l10n/*.arb
dart run build_runner build                        # json_serializable, Drift, flutter_gen (*.g.dart, lib/gen/)
dart run pigeon --input pigeon/message.dart        # regenerates Dart + Kotlin + Swift bridge
dart run ffigen                                    # lib/core/ffi/generated_bindings.dart from c/include/*.h (needs LLVM)
dart run tool/check_layer_dependencies.dart        # enforces core ↛ service/pages, service ↛ pages
dart run tool/check_native_model_contract.dart
dart format --output=none --set-exit-if-changed <changed Dart files>
flutter analyze
flutter test
flutter test test/service/connect/<file>_test.dart           # single file
flutter test test/path/to_test.dart --plain-name "<test name>" # single test
git diff --check
```

Pick only the checks the change needs (see `docs/refactor-validation.md`). Docs-only changes: link/path checks and `git diff --check` only.

Android native tests (from `android/`): `./gradlew :app:testDebugUnitTest` (Robolectric widget tests); add `./gradlew :app:lintVitalRelease` when touching Manifest/XML resources.

Build-script tests (Python 3.12+, no deps): `cd build_scripts && python -m unittest discover -s tests -p 'test_*.py'`.

Packaging: `uv run --project build_scripts python build_scripts/main.py OneXray <system>` with `BUILD_NUMBER` set. Requires sibling checkouts `../libXray` (and `../VCore` for Windows); output goes to `../output`. The ios/macos/android lanes run Fastlane and **may upload to stores** — never use them as local validation. Read `build_scripts/README.md` and `docs/windows-build.md` first.

## Architecture

**Layers** — `lib/pages` (UI) → `lib/service` (business logic) → `lib/core` (models, DB, native bridges, tools). Reverse imports are rejected by `tool/check_layer_dependencies.dart`. Imports must be `package:onexray/...` (`always_use_package_imports`). `test/` mirrors `lib/`.

**Startup** — `lib/main.dart` wires the Pigeon Flutter API, initializes the tun files dir via `AppHostApi`, runs `AppStartupService` (`lib/service/launch/`), then `GoRouteApp` (`lib/pages/main/router.dart`). `ServiceManager` (`lib/service/manager.dart`) owns storage, Geodata and permission checks.

**Connection lifecycle** — every start/stop (UI, shortcuts, tray, quick actions) goes through `ConnectionCoordinator` (`lib/service/connect/coordinator.dart`). Configuration is resolved and compiled in `lib/service/connect/` (`resolver`, `compiler`, `raw/`, `routing/`) into Xray JSON written under the tun files dir (`run/start.json`), then handed to the native side. Native VPN status is the source of truth.

**Native bridge, per platform** — `AppHostApi` (`lib/core/pigeon/host_api.dart`) dispatches:
- **iOS / macOS / Android**: Pigeon (`pigeon/message.dart` → `lib/core/pigeon/messages.g.dart`, `android/.../pigeon/Messages.g.kt`, `swift/App/pigeon/Messages.g.swift`). Android runs Xray in `OneVpnService.kt` via the libXray gomobile AAR; the VPN service also owns notification/widget/tile traffic sampling. Apple code is in `swift/` (App, Tunnel, VCore, libXray) with Xcode projects in `ios/`, `macos/`, `macos_se/`.
- **Windows**: `lib/core/ffi/windows/` — two modes: EXE/ZIP (spawns elevated `OneXrayCore.exe` + `wintun.dll`, see `exe_ffi_api.dart`/`core_process.dart`) and MSIX (system VPN provider via VCore, `msix_ffi_api.dart`).
- **Linux**: `lib/core/ffi/linux_ffi_api.dart` (FFI to libXray, `OneXrayCore` needs `cap_net_admin`).
- FFI bindings come from `c/include/libXray.h` and `c/include/vcore.h`. Xray-core itself is compiled into libXray; its version is pinned by `../libXray/go.mod`.

**State** — page controllers extend `PageCubit` (`lib/pages/shared/page_cubit.dart`) with `flutter_bloc`. Persistence is Drift (`lib/core/db/`), config JSON stored as Base64. Traffic/speed come only from the Xray metrics HTTP endpoint and are never persisted.

**UI** — shadcn_ui + material_ui, theme in `lib/pages/theme/`, icons from `lucide_icons_flutter`. Localization: ARB in `lib/l10n/` (en, fa, ru, zh, zh_Hant).

## Generated code (never hand-edit)

`*.g.dart`, `lib/gen/`, `lib/core/pigeon/messages.g.dart`, `Messages.g.kt`, `Messages.g.swift`, `lib/core/ffi/generated_bindings.dart`, generated l10n. Edit the source (models, `pigeon/message.dart`, headers, ARB) and regenerate.

## Fork (BhsXRay)

This checkout is the `pavru/OneXray` fork, rebranded to BhsXRay (`net.pototskiy.bhsxray`) for Android and Windows; the plan is in `FORK_PLAN.md`. Identity rewrites are produced by `tool/rebrand/rebrand.py` from `tool/rebrand/brand.json` — re-run it after every upstream merge and extend its rules or kept patterns rather than hand-editing brand strings. `python tool/rebrand/rebrand.py --check` must report nothing pending. The same tool sets the fork's own version (`"version"` in `brand.json` → `pubspec.yaml`; release tags are `vX.Y.Z` and must match) and copies the fork icon files from `tool/rebrand/files/`, which `tool/rebrand/icon/generate.py` builds (needs Inkscape and Pillow) — never edit those icons in place. See `tool/rebrand/README.md` for what is intentionally left upstream-named.

Fork CI is `.github/workflows/bhsxray.yml` (Android and Windows only; upstream `build.yml`/publish workflows are disabled in the fork). The fork builds one Xray-core version, set in `.github/xray-core-version.json` and passed to builds as `XRAY_CORE_REF` / `--xray-core-ref`, recorded as `xrayCore` in provenance. Android builds a locally signed arm64-v8a-only APK (`android.package: apk` in `build_scripts/app/config.py`) instead of the upstream Google Play fastlane lane — never run that lane. Windows EXE builds omit VCore (`windows.exe.vcore: false`; `windows/app.cmake` honours `ONEXRAY_WINDOWS_WITHOUT_VCORE=1`) because only MSIX mode, disabled in the fork, uses it. Windows ships only the per-machine installer (`privileges_required: admin`, Program Files); the installer registers the `BhsXRayCore` Windows service (`OneXrayCore.exe service install`, SYSTEM, pipe `\\.\pipe\BhsXRay.Core`), and release builds start and stop the Core only through it (`lib/core/ffi/windows/service_ffi_api.dart`, `core_service.dart`), so connecting needs no UAC prompt and there is no ZIP release. The service confines logs to its own folder (`VpnConstants.logDir`) and refuses configuration fields that name files; its protocol and rules are in `../libXray/README.md#windows-core-service`. Debug builds (or `--dart-define=BHSXRAY_WINDOWS_CORE_SERVICE=false`) keep the UAC path (`exe_ffi_api.dart`), which passes `-config-sha256` and, in release mode, refuses to elevate a Core standard users can modify (`install_protection.dart`). All fork CI inputs are pinned in `bhsxray.yml`: `LIBXRAY_REF` is a `pavru/libXray` commit SHA (bump it after every libXray change), actions are pinned by commit SHA, and Flutter, Go, Python, uv, Fastforge and LLVM-MinGW by exact version (Flutter also by commit, LLVM-MinGW by SHA-256). The fork's libXray (`pavru/libXray`) must be a revision with `LIBXRAY_XRAY_CORE_REF` support and the warm latency probe in `pingBatch` (the fork's reason to exist: upstream counts connection setup and reports about 5× the real ping).

## Docs language

Business docs in `docs/` are written in Chinese; `docs/agents/` in English (see `docs/AGENTS.md`). Keep one contract per topic and link rather than duplicate.
