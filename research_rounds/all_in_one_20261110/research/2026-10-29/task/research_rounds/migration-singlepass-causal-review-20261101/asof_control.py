"""Read existing cached facts and saved ledgers only. No model/account calls."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,collections
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;W=O.parent
R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def pq(p):SRC[str(p)]=sha(p);return pd.read_parquet(p)
def gz(p,lines=False):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):
 p=O/n;t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n');t.replace(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if x is None or (not isinstance(x,(str,bool)) and pd.isna(x)):return None
 if isinstance(x,np.generic):return x.item()
 return x
SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
IM={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
META=read(R/'a-share-selection-e0-20261024/inputs-v2/metadata.json')
OLD=R/'a-share-selection-e0-20261024/prepared-v2'
OR={x['series_id']:x for x in read(OLD/'manifest.json')['series']}
hp=R/'rs-h1-execution-20261025/h1/matrix.npz';SRC[str(hp)]=sha(hp)
H=np.load(hp);HD=pd.DatetimeIndex(H['dates']);HC={str(s):j for j,s in enumerate(H['symbols'])}
F={};CP={};IX={};IS={};IC={};SIG={}
def original(sid):
 if sid not in SIG:
  p=OLD/OR[sid]['files']['signal']['path'];assert sha(p)==OR[sid]['files']['signal']['sha256'];SIG[sid]=pq(p)
 return SIG[sid]
def row(f,d):
 t=pd.Timestamp(d);assert t in f.index,('no exact as-of row',d);return f.loc[t]
def h1(sid,d):
 j=HD.get_loc(pd.Timestamp(d));return clean(H['score'][j,HC[sid]])
def state(sid,d):
 if sid not in F:
  for k,store in [('facts',F),('CP1',CP)]:
   p=Path(SM[sid]['refs'][k]);assert sha(p)==SM[sid]['output_sha256'][str(p)];store[sid]=pq(p)
  IX[sid]=pq(R/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet')
 sector=META[sid]['sector_id']
 if sector not in IS:
  for k,store in [('state',IS),('CP1_input',IC)]:
   p=Path(IM[sector]['refs'][k]);assert sha(p)==IM[sector]['output_sha256'][str(p)];store[sector]=pq(p)
  IS[sector]=IS[sector].set_index('day')
 r=row(F[sid],d);c=row(CP[sid],d);z=row(IX[sid],d);s=IS[sector].loc[d];orig=row(original(sid),d)
 out=dict(day=d,sid=sid,name=META[sid]['name'],raw_close=r.raw_close,adjusted_close=r['close'],factor=r.factor,
  I={k:r[k] for k in ['i_target','i_floor','i_buy']},E0={k:r[k] for k in ['e0_target','e0_floor','e0_ready']},
  G1={k:r[k] for k in ['g_grade','g_ready','g_fresh_up','g_acute_down']},
  G1_detail={k:z[k] for k in ['proposal','promotion_blocked','z5','z21']},
  H1_score=h1(sid,d),CP1={k:c[k] for k in ['receipt','candidate','phase','anchor','frontier','scale','credit','displacement','delta_frontier','reset_reason']},
  industry=dict(id=sector,name=META[sid]['industry'],H1_score=h1(sector,d),**{k:s[k] for k in ['close','E0_valid','E0_floor','E0_episode','stage_name','attempt_id','action','receipt','mobile_before','mobile_after']}),
  raw_OHLC={k:orig[k] for k in ['raw_open','raw_high','raw_low','raw_close','raw_volume']})
 return clean(out)

def main():
 points=[]
 for opening,sid in [('2025-09-01','601869.SH'),('2025-12-19','601869.SH'),('2026-04-22','301511.SZ')]:
  for ref in ['SC','SD']:
   p=read(O/'points'/f'{opening}_{sid}_{ref}.json');x=state(sid,p['previous'])
   x.update(opening=opening,reference=ref,ACT_on=p['ACT_on'],rank=p['signal']['rank'],target_maximum=p['original_maxq'],minimum=p['minimum'],actual_reserved=p['actual_reserved'])
   points.append(x)
 save('ASOF_FIRST_DIVERGENCES.json',points)
 root=W/'migration-admission-singlepass-economics-20261101/runs/2022/pair'
 b=gz(root/'B.json.gz');ds=gz(root/'daily.jsonl.gz',True)
 neg=collections.defaultdict(lambda:D(0))
 for x in b['layers']:
  net=D(x['cash'])+D(x['dividend'])
  if x['qty']==0 and net<0:neg[x['sid']]+=net
 sid=min(neg,key=lambda s:(neg[s],s));assert sid=='000620.SZ'
 ls=[x for x in b['layers'] if x['sid']==sid]
 tx=[x for x in b['trades'] if x['security_id']==sid]
 timeline=[]
 for i,daily in enumerate(ds):
  day=daily['at'][:10]
  if not ('2022-01-11'<=day<='2022-02-08'):continue
  x=state(sid,day);previous=ds[i-1] if i else None
  old=[z for z in (previous['layers'] if previous else []) if z['sid']==sid]
  x.update(ACT_on=daily['on'],NAV=daily['nav'],old_known_protection=[{k:z.get(k) for k in ['id','qty','role','pool','floor','last_core_line']} for z in old],
   end_layers=[{k:z.get(k) for k in ['id','qty','role','pool','floor','last_core_line','attempt']} for z in daily['layers'] if z['sid']==sid],
   native_exit_requests=[z for z in b['audit'] if z.get('sid')==sid and z['at'][:10]==day and z['kind'] in ['exit_request','pilot_layer_exit']],actual_trades=[z for z in tx if z['at'][:10]==day],pending_sell=sid in daily['pending_sells'])
  timeline.append(x)
 save('DETERMINISTIC_2022_CONTROL.json',dict(selection='minimum stock sum of negative fully-closed layer contributions in complete saved SD2022 ledger, ties stock code; no future opportunity selection',sid=sid,name=META[sid]['name'],closed_negative=neg[sid],net=sum((D(x['cash'])+D(x['dividend']) for x in ls),D(0)),layers=ls,actual_trades=tx,all_exit_requests=[x for x in b['audit'] if x.get('sid')==sid and x['kind'] in ['exit_request','pilot_layer_exit']],first_failure_and_reentry_timeline=timeline))
 save('ASOF_CONTROL_SOURCE_SHA256.json',SRC)
 print('POINTS',[(x['opening'],x['reference'],x['sid'],x['G1']['g_grade'],x['H1_score'],x['industry']['H1_score'],x['industry']['stage_name']) for x in points])
 print('CONTROL',sid,str(neg[sid]),str(sum((D(x['cash'])+D(x['dividend']) for x in ls),D(0))),len(ls))
 for x in timeline:
  if x['actual_trades'] or x['native_exit_requests'] or x['CP1']['receipt']:print('CONTROL_DAY',x['day'],x['raw_close'],x['I'],x['G1']['g_grade'],x['H1_score'],x['industry']['stage_name'],[(t['side'],t['shares']) for t in x['actual_trades']],bool(x['native_exit_requests']))
if __name__=='__main__':main()
