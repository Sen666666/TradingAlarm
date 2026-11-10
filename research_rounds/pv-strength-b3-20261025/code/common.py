from pathlib import Path
import hashlib,json
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
OLD=REPO/'research_rounds/pv-strength-20261025'
B2=REPO/'research_rounds/pv-strength-three-axis-20261025'
NAMES={'AU0':'沪金主连','518880':'黄金ETF','512480':'半导体ETF','001309.SZ':'德明利',
       '688981.SH':'中芯国际','600036.SH':'招商银行','600519.SH':'贵州茅台'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,d):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    with Path(p).open('x') as f:json.dump(d,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def now():return datetime.now(timezone.utc).isoformat()
def identity():
    frozen=read(ROOT/'freeze.json')
    for k,v in frozen['sha256'].items():assert sha(REPO/k)==v,k
    for k,v in frozen['old_files'].items():assert sha(REPO/k)==v,k
    for k,v in read(REPO/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'].items():assert sha(REPO/k)==v,k
    return True
