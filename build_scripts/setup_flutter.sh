#!/usr/bin/env bash

set -euo pipefail

# ONEXRAY_FLUTTER_VERSION pins a release tag instead of the moving stable
# branch; ONEXRAY_FLUTTER_COMMIT, when set, must match the checked-out commit.
flutter_channel="${ONEXRAY_FLUTTER_VERSION:-stable}"
flutter_root="${ONEXRAY_FLUTTER_ROOT:-$HOME/flutter/$flutter_channel}"
flutter_bin_dir="$flutter_root/bin"

uname_s="$(uname -s)"
case "$uname_s" in
  Linux|Darwin)
    platform="unix"
    ;;
  MINGW*|MSYS*|CYGWIN*)
    platform="windows"
    ;;
  *)
    echo "unsupported operating system: $uname_s" >&2
    exit 1
    ;;
esac

add_to_github_path() {
  local path_value="$1"
  if [[ -z "${GITHUB_PATH:-}" ]]; then
    return
  fi

  if [[ "$platform" == "windows" ]]; then
    cygpath -w "$path_value" >> "$GITHUB_PATH"
  else
    echo "$path_value" >> "$GITHUB_PATH"
  fi
}

add_to_github_env() {
  local name="$1"
  local value="$2"
  if [[ -z "${GITHUB_ENV:-}" ]]; then
    return
  fi

  if [[ "$platform" == "windows" ]]; then
    value="$(cygpath -w "$value")"
  fi
  echo "${name}=${value}" >> "$GITHUB_ENV"
}

rm -rf "$flutter_root"
mkdir -p "$(dirname "$flutter_root")"
git clone --depth 1 --branch "$flutter_channel" https://github.com/flutter/flutter.git "$flutter_root"
if [[ -n "${ONEXRAY_FLUTTER_COMMIT:-}" ]]; then
  actual_commit="$(git -C "$flutter_root" rev-parse HEAD)"
  if [[ "$actual_commit" != "$ONEXRAY_FLUTTER_COMMIT" ]]; then
    echo "Flutter $flutter_channel is $actual_commit, expected $ONEXRAY_FLUTTER_COMMIT" >&2
    exit 1
  fi
fi

export PATH="$flutter_bin_dir:$PATH"
add_to_github_path "$flutter_bin_dir"
add_to_github_env "FLUTTER_ROOT" "$flutter_root"

flutter --version
