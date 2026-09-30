#!/bin/sh
set -eu

VERSION="${1:?version required}"
PACKAGE="build/deb/multiagentos_${VERSION}_amd64"
rm -rf build/deb
mkdir -p "$PACKAGE/DEBIAN" "$PACKAGE/usr/local/bin"
cp dist/multiagentos "$PACKAGE/usr/local/bin/multiagentos"
chmod 755 "$PACKAGE/usr/local/bin/multiagentos"
cat > "$PACKAGE/DEBIAN/control" <<EOF
Package: multiagentos
Version: ${VERSION}
Section: devel
Priority: optional
Architecture: amd64
Maintainer: eaglesjo
Description: MultiAgentOS Agent Execution Runtime
EOF
dpkg-deb --build "$PACKAGE" "dist/MultiAgentOS-${VERSION}-ubuntu-amd64.deb"
