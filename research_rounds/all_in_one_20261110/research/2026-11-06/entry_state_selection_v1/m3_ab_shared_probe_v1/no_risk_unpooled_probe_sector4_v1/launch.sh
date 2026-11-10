#!/bin/sh
set -eu
cd "$(dirname "$0")"
exec env PYTHONDONTWRITEBYTECODE=1 /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python -u runner.py unpooled_probe_sector4
