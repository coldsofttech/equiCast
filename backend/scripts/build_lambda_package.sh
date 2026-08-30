#!/usr/bin/env bash
# Builds the zip deployment package this Django app would ship to Lambda,
# and reports its size against Lambda's 250MB (unzipped) limit.
#
# Cross-compiles for Lambda's Amazon Linux 2023 (glibc 2.28+) x86_64
# runtime regardless of the host OS/architecture this script runs on —
# matters concretely for `pyarrow`, the one compiled/platform-specific
# wheel in this dependency set. `--only-binary pyarrow` (not `:all:`)
# forces a real Linux wheel for just that package rather than whatever's
# locally installed, while still letting `equicast-backend`/
# `equicast-core` themselves build from their local source trees (they
# have no published wheel to fetch at all — `:all:` would block them too).
#
# `--no-editable` is required: `uv export` otherwise emits `-e ./backend`/
# `-e ./packages/core` for these workspace-local packages, which `uv pip
# install --target` would turn into a path reference back to this build
# machine — meaningless once the zip is deployed elsewhere. Non-editable
# mode makes it build a real wheel from each local path and copy its actual
# files into the target directory instead.
#
# Must run from the repo root, not `backend/`: `uv export`'s local-path
# entries (`./backend`, `./packages/core`) are written relative to the
# workspace root regardless of which directory the command is invoked
# from, so the later install step needs the same working directory to
# resolve them correctly.

set -euo pipefail
cd "$(dirname "$0")/../.."   # repo root

BUILD_DIR="backend/build"
ZIP_PATH="backend/lambda_package.zip"
REQUIREMENTS_FILE="backend/build_requirements.txt"
LAMBDA_ZIP_LIMIT_BYTES=$((250 * 1000 * 1000))

rm -rf "$BUILD_DIR" "$ZIP_PATH" "$REQUIREMENTS_FILE"
mkdir -p "$BUILD_DIR"

uv export --package equicast-backend --no-dev --no-editable --no-hashes \
    --format requirements.txt -o "$REQUIREMENTS_FILE"

uv pip install \
    --target "$BUILD_DIR" \
    --python-platform x86_64-manylinux_2_28 \
    --python-version 3.13 \
    --only-binary pyarrow \
    -r "$REQUIREMENTS_FILE"

UNZIPPED_BYTES=$(du -sb "$BUILD_DIR" | cut -f1)
UNZIPPED_MB=$(awk "BEGIN { printf \"%.1f\", $UNZIPPED_BYTES / 1000000 }")

python -c "
import pathlib, zipfile
build_dir = pathlib.Path('$BUILD_DIR')
with zipfile.ZipFile('$ZIP_PATH', 'w', zipfile.ZIP_DEFLATED) as zf:
    for path in build_dir.rglob('*'):
        if path.is_file():
            zf.write(path, path.relative_to(build_dir))
"
ZIP_BYTES=$(du -sb "$ZIP_PATH" | cut -f1)
ZIP_MB=$(awk "BEGIN { printf \"%.1f\", $ZIP_BYTES / 1000000 }")

echo "Unzipped size: ${UNZIPPED_MB}MB (Lambda limit: 250MB)"
echo "Zip size:      ${ZIP_MB}MB"

if [ "$UNZIPPED_BYTES" -gt "$LAMBDA_ZIP_LIMIT_BYTES" ]; then
    echo "OVER Lambda's unzipped deployment package limit." >&2
    exit 1
fi
echo "Within Lambda's unzipped deployment package limit."
