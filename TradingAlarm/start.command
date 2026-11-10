#!/bin/zsh
cd -- "${0:A:h}"
if [[ -x research/.venv/bin/python ]]; then
  exec research/.venv/bin/python server.py
fi
python3 -c 'import pandas, numpy, pyarrow' 2>/dev/null || { print '请先安装 pandas、numpy、pyarrow，或使用项目 research/.venv 环境。'; exit 1; }
exec python3 server.py
