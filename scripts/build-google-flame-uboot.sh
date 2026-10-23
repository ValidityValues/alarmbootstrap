#!/usr/bin/env bash
set -Eeuo pipefail

REPO_URL="https://gitlab.com/andrewgigena/u-boot.git"
BRANCH="andrew/google-flame"
DEVICE="sm8150-google-flame"
PARTITION="userdata"
FLASH=0
SOURCE=""
WORKDIR=""

usage() {
    cat <<'USAGE'
Usage: build-google-flame-uboot.sh [--flash] [--source DIR] [--workdir DIR]

Build the U-Boot branch used by Google Pixel 4 (flame) Nura setups.
By default this only builds .output/u-boot.img. It never flashes implicitly.
  --flash       Flash the built image to the boot partition after checks and prompt
  --source DIR  Use a clean checkout of the requested branch
  --workdir DIR Working directory for clone and build artifacts
USAGE
}

while (($#)); do
    case "$1" in
        --flash)
            FLASH=1
            shift
            ;;
        --source)
            [[ $# -ge 2 ]] || { echo "Missing directory after --source" >&2; exit 2; }
            SOURCE="$2"
            shift 2
            ;;
        --workdir)
            [[ $# -ge 2 ]] || { echo "Missing directory after --workdir" >&2; exit 2; }
            WORKDIR="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

SCRIPT_DIR="$(cd -- "$(dirname -- "$BASH_SOURCE")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
if [[ -z "$WORKDIR" ]]; then
    WORKDIR="$REPO_ROOT/.cache/uboot-google-flame"
fi
mkdir -p "$WORKDIR"

for tool in git make aarch64-linux-gnu-gcc aarch64-linux-gnu-ld aarch64-linux-gnu-objcopy bison flex swig dtc openssl gzip cat mkbootimg sha256sum python3 nproc awk grep; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "Missing required tool: $tool" >&2
        exit 2
    }
done

if [[ -z "$SOURCE" ]]; then
    SOURCE="$WORKDIR/u-boot"
    if [[ ! -d "$SOURCE/.git" ]]; then
        git clone --depth=1 --branch "$BRANCH" --single-branch "$REPO_URL" "$SOURCE"
    else
        actual_origin="$(git -C "$SOURCE" remote get-url origin)"
        [[ "$actual_origin" == "$REPO_URL" ]] || {
            echo "Refusing checkout with unexpected origin: $actual_origin" >&2
            exit 2
        }
        [[ -z "$(git -C "$SOURCE" status --porcelain)" ]] || {
            echo "Existing U-Boot checkout has local changes; inspect it or remove it and retry." >&2
            exit 2
        }
        git -C "$SOURCE" fetch --depth=1 origin "$BRANCH"
        git -C "$SOURCE" checkout -B "$BRANCH" FETCH_HEAD
    fi
else
    SOURCE="$(cd -- "$SOURCE" && pwd)"
    [[ -d "$SOURCE/.git" ]] || { echo "Not a git checkout: $SOURCE" >&2; exit 2; }
    [[ "$(git -C "$SOURCE" branch --show-current)" == "$BRANCH" ]] || {
        echo "Source checkout must be on branch $BRANCH" >&2
        exit 2
    }
    [[ -z "$(git -C "$SOURCE" status --porcelain)" ]] || {
        echo "Source checkout has local changes; refusing to overwrite them." >&2
        exit 2
    }
fi

ENV_FILE="$SOURCE/board/qualcomm/qcom-phone.env"
[[ -f "$ENV_FILE" ]] || { echo "Expected environment file not found: $ENV_FILE" >&2; exit 2; }

restore_environment() {
    git -C "$SOURCE" checkout -- board/qualcomm/qcom-phone.env >/dev/null 2>&1 || true
}
trap restore_environment EXIT

python3 - "$ENV_FILE" "$PARTITION" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
partition = sys.argv[2]
dollar = "$"
replacement = (
    f"preboot=scsi scan; part start scsi 0 {partition} {partition}_start; "
    f"part size scsi 0 {partition} {partition}_size; blkmap create root; "
    "blkmap map root 0 0x" + dollar + "{" + partition + "_size} linear scsi 0 0x"
    + dollar + "{" + partition + "_start}"
)
original = path.read_text()
updated, count = re.subn(r"(?m)^preboot=.*$", lambda _match: replacement, original)
if count != 1:
    raise SystemExit(f"Expected exactly one preboot= assignment in {path}, found {count}")
path.write_text(updated)
print("Configured userdata blkmap preboot")
PY

cd "$SOURCE"
make mrproper
make CROSS_COMPILE=aarch64-linux-gnu- O=.output qcom_defconfig qcom-phone.config "$DEVICE.config"
make CROSS_COMPILE=aarch64-linux-gnu- O=.output "-j$(nproc)"

DTB="$SOURCE/.output/dts/upstream/src/arm64/qcom/$DEVICE.dtb"
[[ -s "$SOURCE/.output/u-boot-nodtb.bin" ]] || {
    echo "U-Boot binary was not produced" >&2
    exit 1
}
[[ -s "$DTB" ]] || {
    echo "Expected DTB was not produced: $DTB" >&2
    exit 1
}

gzip -c .output/u-boot-nodtb.bin > .output/u-boot-nodtb.bin.gz
cat .output/u-boot-nodtb.bin.gz "$DTB" > .output/uboot-dtb
mkbootimg --base 0 --kernel_offset 0x8000 --pagesize 4096 \
    --kernel .output/uboot-dtb -o .output/u-boot.img
sha256sum .output/u-boot.img
echo "Built image: $SOURCE/.output/u-boot.img"

if ((FLASH)); then
    command -v fastboot >/dev/null 2>&1 || { echo "fastboot not found" >&2; exit 2; }
    devices="$(fastboot devices)"
    count="$(printf '%s\n' "$devices" | awk 'NF >= 2 { n++ } END { print n+0 }')"
    [[ "$count" == "1" ]] || {
        echo "Expected exactly one fastboot device; found $count." >&2
        printf '%s\n' "$devices" >&2
        exit 2
    }
    product="$(fastboot getvar product 2>&1 || true)"
    if ! grep -Eiq 'product:[[:space:]]*flame([[:space:]]|$)' <<< "$product"; then
        echo "Refusing to flash: fastboot did not identify the device as product flame." >&2
        printf '%s\n' "$product" >&2
        exit 2
    fi
    [[ -t 0 ]] || { echo "--flash requires an interactive terminal for confirmation" >&2; exit 2; }
    echo "WARNING: this overwrites the phone's boot partition."
    echo "Ensure a known-good recovery path and boot image backup are available."
    read -r -p 'Type FLASH boot to continue: ' answer
    [[ "$answer" == "FLASH boot" ]] || {
        echo "Cancelled; no flash performed."
        exit 1
    }
    fastboot flash boot .output/u-boot.img
    echo "U-Boot image flashed to boot. No automatic reboot was performed."
fi
