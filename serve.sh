#!/usr/bin/env sh
# Sirve el sitio en http://localhost:8787 (fetch de .md no funciona desde file://)
cd "$(dirname "$0")" && exec python3 -m http.server "${PORT:-8787}" --bind 127.0.0.1
