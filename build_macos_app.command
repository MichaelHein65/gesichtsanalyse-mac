#!/bin/zsh
set -e

cd "${0:A:h}"

APP_NAME="Gesichtsanalyse.app"
CONTENTS="$APP_NAME/Contents"
ICONSET="assets/AppIcon.iconset"

mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources" "$ICONSET"
cp macos_launcher/Info.plist "$CONTENTS/Info.plist"

PYTHON_CFLAGS=("${(@f)$(python3-config --embed --cflags)}")
PYTHON_LDFLAGS=("${(@f)$(python3-config --embed --ldflags)}")
clang macos_launcher/main.c \
  -o "$CONTENTS/MacOS/Gesichtsanalyse" \
  -Wno-deprecated-declarations \
  ${=PYTHON_CFLAGS} \
  ${=PYTHON_LDFLAGS}

sips -z 16 16 assets/app-icon.png --out "$ICONSET/icon_16x16.png" >/dev/null
sips -z 32 32 assets/app-icon.png --out "$ICONSET/icon_16x16@2x.png" >/dev/null
sips -z 32 32 assets/app-icon.png --out "$ICONSET/icon_32x32.png" >/dev/null
sips -z 64 64 assets/app-icon.png --out "$ICONSET/icon_32x32@2x.png" >/dev/null
sips -z 128 128 assets/app-icon.png --out "$ICONSET/icon_128x128.png" >/dev/null
sips -z 256 256 assets/app-icon.png --out "$ICONSET/icon_128x128@2x.png" >/dev/null
sips -z 256 256 assets/app-icon.png --out "$ICONSET/icon_256x256.png" >/dev/null
sips -z 512 512 assets/app-icon.png --out "$ICONSET/icon_256x256@2x.png" >/dev/null
sips -z 512 512 assets/app-icon.png --out "$ICONSET/icon_512x512.png" >/dev/null
sips -z 1024 1024 assets/app-icon.png --out "$ICONSET/icon_512x512@2x.png" >/dev/null
iconutil -c icns "$ICONSET" -o assets/AppIcon.icns
cp assets/AppIcon.icns "$CONTENTS/Resources/AppIcon.icns"

codesign --force --deep --sign - "$APP_NAME" >/dev/null
touch "$APP_NAME"
echo "$APP_NAME wurde erstellt."
