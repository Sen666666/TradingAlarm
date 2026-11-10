#!/bin/zsh
atlas_dir="${0:A:h}"
exec /Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python "$atlas_dir/serve.py" --port 8810
