"""Read-only I/E0 exit/gap census, no supplementary strategy or account."""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,hashlib,json,pickle,time
import pandas as pd
O=Path(__file__).resolve().parent;T=O.parent.parent/'task';SRC={}
def bind(p):p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def gz(p):
 with gzip.open(bind(p),'rt')as h:return json.load(h)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')

def main():
 start=time.monotonic();bind(__file__)
 with bind(O/'PRICE_FEATURES.pkl').open('rb')as h:features=pickle.load(h)
 sm={r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 roots={'long':T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair/B.json.gz',
        'strong':T/'pvr_pool_feasibility/runs/2025_26/pair/B.json.gz'}
 exits=defaultdict(list);mother={}
 for w,path in roots.items():
  b=gz(path);first={}
  for r in b['audit']:
   if r['kind']=='pilot_layer_exit':
    for lid in r['layers']:first.setdefault(lid,r)
  native={r['id']:r for r in b['layers']}
  mother[w]=dict(layers=len(native),first_exit_reasons=dict(Counter(r['reason']for r in first.values())))
  for lid,r in first.items():
   if r['reason']=='I_structure_exit':exits[r['sid']].append(dict(window=w,layer=lid,sid=r['sid'],day=r['at'][:10],role=native[lid]['kind']))
  del b
 summary=defaultdict(Counter);exitrows=[];events=[]
 for sid,r in sm.items():
  assert time.monotonic()-start<60,'read-only I census compute cap exceeded'
  p=Path(r['refs']['facts']);assert hashlib.sha256(p.read_bytes()).hexdigest()==r['output_sha256'][str(p)]
  f=pd.read_parquet(bind(p),columns=['close','segment_id','e0_target','e0_floor','i_target','i_floor','g_grade','g_fresh_up'])
  for e in exits.get(sid,[]):
   dt=pd.Timestamp(e['day']);known=dt in f.index and all(pd.notna(f.loc[dt,k])for k in ['close','e0_target','i_target'])
   row=dict(e,exact_price_state_known=bool(known))
   if known:
    z=f.loc[dt];row.update(close=float(z.close),e0_target=bool(z.e0_target),i_target=bool(z.i_target),
     e0_floor=float(z.e0_floor)if pd.notna(z.e0_floor)else None,i_floor=float(z.i_floor)if pd.notna(z.i_floor)else None)
   exitrows.append(row)
  pf=features[sid];g=f.reindex(pf.index);known=g.e0_target.notna()&g.i_target.notna()
  rawgap=known&g.e0_target.eq(1)&g.i_target.eq(0)
  above=pf.ema20.gt(pf.ema60);prevabove=above.groupby(pf.source_segment,sort=False).shift()
  prevema=pf.ema60.groupby(pf.source_segment,sort=False).shift()
  ec_known=pf.ema_trend_known&prevema.notna();ec=ec_known&above&prevabove.eq(False)
  cp=pd.read_parquet(bind(r['refs']['CP1']),columns=['receipt']).receipt.reindex(pf.index)
  for w,lo,hi in [('long','2022-01-01','2024-12-31'),('strong','2025-07-01','2026-06-30')]:
   within=(pf.index>=pd.Timestamp(lo))&(pf.index<=pd.Timestamp(hi));mask=rawgap&within
   z=summary[w];z['known_E0_I_stock_CLOSEs']+=int((known&within).sum());z['raw_E0_on_I_off_stock_CLOSEs']+=int(mask.sum())
   z['raw_gap_BB_cross_events']+=int((mask&pf.bb20_cross).sum());z['raw_gap_EMA_cross_events']+=int((mask&ec).sum())
   z['raw_gap_original_CP_receipts']+=int((mask&cp.eq(True)).sum())
   for d in pf.index[mask&(pf.bb20_cross|ec)]:
    events.append(dict(window=w,sid=sid,day=str(d.date()),source_segment=str(pf.loc[d,'source_segment']),
     original_e0_target=True,original_i_target=False,original_e0_floor=float(g.loc[d,'e0_floor'])if pd.notna(g.loc[d,'e0_floor'])else None,
     BB_cross=bool(pf.loc[d,'bb20_cross']),EMA20_60_cross=bool(ec.loc[d]),original_CP_receipt=bool(cp.loc[d])if pd.notna(cp.loc[d])else None,
     raw_price_evidence_only=True))
 for w in roots:
  a=[r for r in exitrows if r['window']==w];known=[r for r in a if r['exact_price_state_known']]
  mother[w]['first_I_exit_diagnostic']=dict(layers=len(a),unique_stock_CLOSEs=len({(r['sid'],r['day'])for r in a}),
   known=len(known),unknown=len(a)-len(known),E0_still_on=sum(r['e0_target']for r in known),
   E0_off=sum(not r['e0_target']for r in known),I_still_on=sum(r['i_target']for r in known))
 save('ALL_FIRST_I_EXIT_E0_STATES.json',exitrows);save('RAW_I_AUTH_GAP_PRICE_EVENTS.json',events)
 save('I_AUTHORIZATION_CENSUS_SUMMARY.json',dict(mother=mother,raw_gap_summary={w:dict(z)for w,z in summary.items()},
  scope='Source semantics and original stock-CLOSE states only; raw E0-on/I-off price crosses do not imply S0/Q/industry/ACT/units/funding permission or future returns. No I overlay or account implemented.',
  EMA_cross='EMA20 crosses aboveEMA60, previous same-source known line ordering, using already computed arrays. First saved2022 observation lacks previous saved line and is UNKNOWN, not forcedFalse evidence.',
  next_hypothesis='A new supplemental starting proof during E0-valid/I-not-activated gaps would be a separate entry authorization policy, not prevention of cold-G1 holding exits.',
  seconds=time.monotonic()-start,new_accounts=0,new_price_indicators=0))
 save('I_AUTH_CENSUS_SOURCE_SHA256.json',SRC);print(json.dumps(dict(mother=mother,raw_gap_summary={w:dict(z)for w,z in summary.items()},seconds=time.monotonic()-start),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
