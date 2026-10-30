#!/usr/bin/env bash
set -euo pipefail

SHARE="${EYE_CARE_SHARE_DIR:-/mnt/hgfs/Hi3861}"
SDK="${EYE_CARE_SDK_DIR:-$HOME/Hi3861/code-v1.1.5-LTS/OpenHarmony}"
SOURCE="$SHARE/eye-care-desk-system/firmware/demo/50_eye_care"
PYTHON="$HOME/miniconda3/envs/ohos38/bin/python3"
RELEASE="$SHARE/eye-care-desk-system/release"

if [[ ! -d "$SOURCE" ]]; then
    echo "Eye Care firmware source not found: $SOURCE" >&2
    exit 1
fi
if [[ ! -d "$SDK" ]]; then
    echo "Hi3861 SDK not found: $SDK" >&2
    exit 1
fi
echo "SDK: $SDK"
if [[ ! -x "$PYTHON" ]]; then
    echo "Python 3.8 build environment not found: $PYTHON" >&2
    exit 1
fi

DEMO_ROOT="$(find "$SDK/src" -type d -path '*/pzkj/pz_hi3861/demo' 2>/dev/null | head -n 1 || true)"
if [[ -z "$DEMO_ROOT" ]]; then
    DEMO_ROOT="$(find "$SDK/applications" -type d -name demo 2>/dev/null | head -n 1 || true)"
fi
if [[ -z "$DEMO_ROOT" && -d "$SDK/applications/sample/wifi-iot/app" ]]; then
    DEMO_ROOT="$SDK/applications/sample/wifi-iot/app"
fi
if [[ -z "$DEMO_ROOT" ]]; then
    echo "Cannot locate the Hi3861 demo component directory under $SDK" >&2
    echo "Available top-level directories:" >&2
    find "$SDK" -maxdepth 2 -type d | sort | head -n 80 >&2
    echo "Existing 50_eye_care directories:" >&2
    find "$SDK" -type d -name '50_eye_care' 2>/dev/null | head -n 20 >&2 || true
    exit 1
fi
echo "Demo component root: $DEMO_ROOT"
DEMO_GN="$DEMO_ROOT/BUILD.gn"
DEST="$DEMO_ROOT/50_eye_care"

CONFIG_FILE="$(
    find "$SDK/device" -path '*/hispark_pegasus/sdk_liteos/build/config/usr_config.mk' 2>/dev/null |
        head -n 1 || true
)"
if [[ -z "$CONFIG_FILE" ]]; then
    echo "Cannot locate Hi3861 usr_config.mk under $SDK/device" >&2
    exit 1
fi
"$PYTHON" - "$CONFIG_FILE" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = re.sub(
    r"^#\\s*CONFIG_I2C_SUPPORT is not set\\s*$",
    "CONFIG_I2C_SUPPORT=y",
    text,
    flags=re.MULTILINE,
)
text = re.sub(
    r"^CONFIG_I2C_SUPPORT\\s*=.*$",
    "CONFIG_I2C_SUPPORT=y",
    text,
    flags=re.MULTILINE,
)
if "CONFIG_I2C_SUPPORT=y" not in text:
    text = text.rstrip() + "\nCONFIG_I2C_SUPPORT=y\n"
path.write_text(text, encoding="utf-8")
print(f"enabled I2C driver: {path}")
PY

install -d "$DEST"
cp -f "$SOURCE"/*.c "$SOURCE"/*.h "$SOURCE"/BUILD.gn "$DEST"/

"$PYTHON" - "$DEMO_GN" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(f"BUILD.gn not found: {path}")
text = path.read_text(encoding="utf-8")
match = re.search(r"(features\s*=\s*\[)(.*?)(\])", text, re.S)
if not match:
    raise SystemExit(f"features list not found in {path}")
body = '\n        "50_eye_care:template",\n    '
updated = text[:match.start(2)] + body + text[match.end(2):]
path.write_text(updated, encoding="utf-8")
print(f"selected only 50_eye_care in: {path}")
PY

export PATH="$HOME/miniconda3/envs/ohos38/bin:/opt/gcc_riscv32/bin:/usr/local/bin:$PATH"
cd "$SDK"
"$PYTHON" build.py -p wifiiot_hispark_pegasus@hisilicon -c gcc -f

IMAGE="$(find "$SDK/out" -name 'Hi3861_wifiiot_app_allinone.bin' | head -n 1)"
if [[ -z "$IMAGE" ]]; then
    echo "Hi3861 build finished but no all-in-one image was produced." >&2
    exit 1
fi

install -d "$RELEASE"
cp -f "$IMAGE" "$RELEASE/hi3861-local-sensors.bin"
sha256sum "$RELEASE/hi3861-local-sensors.bin"
echo "Firmware copied to: $RELEASE/hi3861-local-sensors.bin"
