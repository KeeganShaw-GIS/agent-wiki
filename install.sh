#!/usr/bin/env bash
set -e

REPO="KeeganShaw-GIS/agent-wiki"
INSTALL_DIR="/usr/local/bin"

OS=$(uname -s)
ARCH=$(uname -m)

if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
    BINARY="agent-wiki-macos-arm64"
elif [ "$OS" = "Linux" ] && [ "$ARCH" = "x86_64" ]; then
    BINARY="agent-wiki-linux-x86_64"
else
    echo "Unsupported platform: $OS $ARCH"
    exit 1
fi

URL="https://github.com/$REPO/releases/latest/download/$BINARY"

echo "Downloading $BINARY..."
curl -fsSL "$URL" -o /tmp/agent-wiki
chmod +x /tmp/agent-wiki
sudo mv /tmp/agent-wiki "$INSTALL_DIR/agent-wiki"

echo "Installed to $INSTALL_DIR/agent-wiki"
agent-wiki --help
