from pathlib import Path
import json,hashlib,datetime
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
NAMES={'AU0':'沪金主连','518880':'黄金ETF','512480':'半导体ETF','001309.SZ':'德明利','688981.SH':'中芯国际','600036.SH':'招商银行','600519.SH':'贵州茅台'}
def prepare():
 out=HERE/'inputs';assert not (out/'manifest.json').exists();pm={x['series_id']:x for x in read(ROOT/'research_rounds/a-share-selection-e0-20261024/prepared-v2/manifest.json')['series']};sources=[]
 for sid in NAMES:
  if sid=='AU0':
   p=ROOT/'research_rounds/gold-chart-fit-20261024/raw/sina-AU0.response';txt=p.read_text();rows=json.loads(txt[txt.index('([')+1:txt.rindex(')')]);f=pd.DataFrame(rows).rename(columns={'d':'date','o':'open','h':'high','l':'low','c':'close','v':'volume'});f.date=pd.to_datetime(f.date);f=f.set_index('date')[['open','high','low','close','volume']].apply(pd.to_numeric)
  elif sid in ('518880','512480'):
   p=ROOT/f'research_rounds/market-regimes-exit-20261024/inputs/USHJ{sid}.parquet';f=pd.read_parquet(p)
  else:
   p=ROOT/'research_rounds/a-share-selection-e0-20261024/prepared-v2'/pm[sid]['files']['signal']['path'];assert sha(p)==pm[sid]['files']['signal']['sha256'];f=pd.read_parquet(p)
  f=f.copy();f.index=pd.DatetimeIndex(f.index);f.index.name='date'
  valid=np.isfinite(f[['open','high','low','close','volume']]).all(axis=1)&f[['open','high','low','close','volume']].gt(0).all(axis=1)&f.high.ge(f[['open','close','low']].max(axis=1))&f.low.le(f[['open','close','high']].min(axis=1))
  for c in ['source_invalid','synthetic_event_bar']:
   if c in f:valid&=~f[c].astype(bool)
  if 'observed_bar'in f:valid&=f.observed_bar.astype(bool)
  f['valid_strength_observation']=valid
  if 'segment_id'not in f:f['segment_id']=0
  target=out/(sid+'.parquet');f.to_parquet(target)
  src=[dict(path=str(p),sha256=sha(p))]
  if sid in pm:
   st=ROOT/'research_rounds/a-share-selection-e0-20261024/prepared-v2'/pm[sid]['files']['states']['path'];assert sha(st)==pm[sid]['files']['states']['sha256'];src.append(dict(path=str(st),sha256=sha(st)));pd.read_parquet(st).to_parquet(out/(sid+'-e0-frozen.parquet'))
  sources.append(dict(asset=sid,name=NAMES[sid],sources=src,path=str(target),sha256=sha(target),rows=len(f),valid=int(valid.sum()),first=str(f.index[0].date()),last=str(f.index[-1].date())))
 write(out/'manifest.json',dict(recorded_at=now(),series=sources,protocol_sha256=sha(HERE/'PROTOCOL.md'),network_quotes=0))
 print({'prepared':len(sources)},flush=True)
if __name__=='__main__':prepare()
