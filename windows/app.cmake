set(APP_DIR "${CMAKE_CURRENT_SOURCE_DIR}/app")

install(CODE "file(REMOVE_RECURSE \"${CMAKE_INSTALL_PREFIX}/bin\")"
        COMPONENT Runtime)

# VCore runs only in MSIX mode. EXE builds that omit it set
# ONEXRAY_WINDOWS_WITHOUT_VCORE=1 (build_scripts: windows.exe.vcore).
set(VCORE_LIBRARIES "${APP_DIR}/vcore.dll")
set(VCORE_PROGRAMS
    "${APP_DIR}/vcore-windows-vpn-host.exe"
    "${APP_DIR}/vcore-windows-session-host.exe")
if("$ENV{ONEXRAY_WINDOWS_WITHOUT_VCORE}" STREQUAL "1")
  set(VCORE_LIBRARIES "")
  set(VCORE_PROGRAMS "")
endif()

# Both distribution modes use the same flat runtime layout. Missing native
# dependencies must fail the build instead of producing an incomplete package.
install(FILES
        "${APP_DIR}/libXray.dll"
        "${APP_DIR}/wintun.dll"
        ${VCORE_LIBRARIES}
        DESTINATION "${CMAKE_INSTALL_PREFIX}"
        COMPONENT Runtime)

install(PROGRAMS
        "${APP_DIR}/OneXrayCore.exe"
        ${VCORE_PROGRAMS}
        DESTINATION "${CMAKE_INSTALL_PREFIX}"
        COMPONENT Runtime)
