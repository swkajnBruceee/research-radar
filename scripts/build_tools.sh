#!/bin/zsh
set -eu
RADAR_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DEVELOPER_DIR="${DEVELOPER_DIR:-/Applications/Xcode.app/Contents/Developer}"
xcrun swiftc "$RADAR_ROOT/tools/pdf_extract.swift" -O -o "$RADAR_ROOT/tools/pdf_extract"
