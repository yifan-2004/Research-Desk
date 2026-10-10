#!/bin/sh
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  exec python3 app.py --open
fi
printf '%s\n' '需要 Python 3.10 或更高版本。请从 https://www.python.org/downloads/ 安装后重试。'
read -r ignored
