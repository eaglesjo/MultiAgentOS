#!/bin/sh
set -eu

VERSION="${1:?version required}"
ARCH="${2:?architecture required}"
rm -rf build/macos staging
mkdir -p staging/usr/local/bin
cp "dist/multiagentos" staging/usr/local/bin/multiagentos
chmod 755 staging/usr/local/bin/multiagentos
pkgbuild --root staging --identifier com.eaglesjo.multiagentos --version "$VERSION" --install-location / "dist/MultiAgentOS-${VERSION}-macos-${ARCH}.pkg"
