#!/usr/bin/env sh
# Sirve el sitio en http://localhost:8787 con el endpoint de edición (ver server.py)
cd "$(dirname "$0")" && exec python3 server.py
