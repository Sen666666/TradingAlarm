from pathlib import Path
import json,hashlib,datetime,os
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parents[1]
OLD=ROOT/'research_rounds/strategy-switching-20261024';SOURCE=ROOT/'research_rounds/market-regimes-exit-20261024'
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def ref(p):return dict(path=str(Path(p).resolve()),sha256=sha(p))
ENTRIES=['E34','E45','C4','C5'];EXITS=['S','X6','X7']
TEMP_POLICIES=[a+'_'+b for a in ENTRIES for b in EXITS]
NEW_POLICIES=TEMP_POLICIES+['T_ORIG','L3'];OLD_POLICIES=['E0','R','F','HOLD']
LABELS=['未知','冷','回暖','突破待验','量价立态','有效推进','多尺度强趋势','放量扩张']
SCENARIOS={'base':dict(cost=1,delay=1),'cost2':dict(cost=2,delay=1),'delay1':dict(cost=1,delay=2)}
def name(p):
 if p=='T_ORIG':return '原温度·触5结构持有'
 if p=='L3':return '原三层·独立起点/危险响应'
 if p in OLD_POLICIES:return dict(E0='E0',R='R',F='拟合F20',HOLD='被动持有')[p]
 a,b=p.split('_');return dict(E34='严格3→4',E45='严格4→5',C4='跨入≥4',C5='跨入≥5')[a]+' / '+dict(S='结构退出',X6='到6后降温退出',X7='到7后降温退出')[b]
