#!/bin/sh
# Reconstruit l'AppImage de l'installeur d'archives à partir d'un AppImage « de base » qui contient déjà
# Python 3.12 + PySide6 (par exemple ton installeur de thème rsh_plasma_installer_*.AppImage).
# Besoins : unsquashfs, mksquashfs (paquet squashfs-tools), python3.
# Usage : ./build.sh base.AppImage [sortie.AppImage]
set -eu
BASE="${1:?usage: $0 base.AppImage [sortie.AppImage]}"
OUT="${2:-rh_archive_installer_1_0_x86_64.AppImage}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"; trap 'rm -rf "$WORK"' EXIT

OFFSET="$(python3 -I - "$BASE" <<'PY'
import struct, sys
h = open(sys.argv[1], "rb").read(64)
shoff = struct.unpack("<Q", h[0x28:0x30])[0]; entsize, num = struct.unpack("<HH", h[0x3A:0x3E])
print(shoff + entsize * num)
PY
)"
unsquashfs -no-progress -offset "$OFFSET" -d "$WORK/tree" "$BASE" >/dev/null
rm -rf "$WORK/tree/opt/rsh" "$WORK"/tree/rsh-installer.* "$WORK/tree/.DirIcon" "$WORK/tree/opt/rh"
mkdir -p "$WORK/tree/opt/rh"
cp -r "$HERE/rh_archive_installer" "$WORK/tree/opt/rh/"
find "$WORK/tree/opt/rh" -name __pycache__ -prune -exec rm -rf {} +
cp "$HERE/packaging/launcher.py" "$WORK/tree/opt/rh/launcher.py"
cp "$HERE/packaging/AppRun" "$WORK/tree/AppRun" && chmod 755 "$WORK/tree/AppRun"
cp "$HERE/packaging/rh-archive-installer.desktop" "$WORK/tree/"
cp "$HERE/rh_archive_installer/assets/rh-archive-installer.png" "$WORK/tree/"
ln -s rh-archive-installer.png "$WORK/tree/.DirIcon"
"$WORK/tree/opt/python3.12/bin/python3.12" -E -s -m compileall -q "$WORK/tree/opt/rh"

mksquashfs "$WORK/tree" "$WORK/app.squashfs" -root-owned -noappend -comp zstd -Xcompression-level 19 -b 262144 -no-progress >/dev/null
head -c "$OFFSET" "$BASE" > "$WORK/runtime"
cat "$WORK/runtime" "$WORK/app.squashfs" > "$OUT"
chmod 755 "$OUT"
echo "Créé : $OUT"
