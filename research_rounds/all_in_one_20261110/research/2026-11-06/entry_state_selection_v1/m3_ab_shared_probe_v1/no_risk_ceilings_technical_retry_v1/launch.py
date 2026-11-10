"""One explicitly authorized environment-only retry. No strategy mutation."""
from pathlib import Path
import hashlib,json,os,sys
HERE=Path(__file__).resolve().parent
PY='/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
m=json.loads((HERE/'TECHNICAL_MANIFEST.json').read_text())
for p,h in m['hashes'].items():assert sha(p)==h,('TECHNICAL_DRIFT',p)
assert Path(sys.executable).absolute()==Path(PY).absolute(),('WRONG_PYTHON',sys.executable)
import pandas,pyarrow
assert pandas.__version__==m['environment']['pandas']
assert pyarrow.__version__==m['environment']['pyarrow']
assert sys.version==m['environment']['python_version']
release=json.loads((HERE/'TECHNICAL_REVIEW_RELEASE.json').read_text())
assert release['result']=='PASS_TECHNICAL_RETRY_ONLY'
assert release['technical_manifest_sha256']==sha(HERE/'TECHNICAL_MANIFEST.json')
assert not (HERE/'no_risk_ceilings.ONCE.lock').exists()
os.execv(PY,[PY,'-u',str(HERE/'runner.py'),'no_risk_ceilings'])
