"""Saved CP numeric cache extraction only. No CP/indicator/account computation."""
from pathlib import Path
import csv,gzip,hashlib,json,math
import pandas as pd
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[1];H={};NS='NOT_SAVED'
def bind(p):
 p=Path(p).resolve();H[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def clean(x):
 if x is pd.NA or x is pd.NaT:return 'SOURCE_NULL'
 if isinstance(x,pd.Timestamp):return x.isoformat()
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return 'SOURCE_NULL'
 return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2)+'\n')
def csvsave(n,rows):
 with(OUT/n).open('w',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(clean(rows))

def main():
 bind(__file__)
 old=read(ROOT/'native_algorithm_read_v1/daily_hytera/ALL_DAYS_ORIGINAL_STOCK_OUTPUTS.json')
 snapshots=read(ROOT/'upside_state_v1/examples_924/FINITE_KEYPOINT_SNAPSHOTS.json')
 chains=read(ROOT/'upside_state_v1/examples_924/ACTUAL_NINE_LAYER_CHAINS.json')
 manifest=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
 rec=next(r for r in manifest if r['symbol']=='300085.SZ')
 frames={}
 for label in ['facts','CP1','CP1_input']:
  p=bind(rec['refs'][label]);assert H[str(p)]==rec['output_sha256'][str(p)];frames[label]=pd.read_parquet(p)
 signalpath=next(p for p in rec['source_sha256']if p.endswith('/signal.parquet'))
 p=bind(signalpath);assert H[str(p)]==rec['source_sha256'][str(p)];frames['signal']=pd.read_parquet(p)
 hytera=[dict(day=r['day'],facts=r['facts'],source_signal=r['source_signal'],CP1=r['CP1'],
  current_CLOSE_stock_layers=r['current_CLOSE_stock_layers'],previous_CLOSE_stock_layers=r['previous_CLOSE_stock_layers'],
  original_protection_exit_proposals=[a for a in r['audit']if a.get('kind')=='pilot_layer_exit'],
  original_trades=r['trades'])for r in old]
 base=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair'
 with gzip.open(bind(base/'B.json.gz'),'rt')as f:b=json.load(f)
 with gzip.open(bind(base/'daily.jsonl.gz'),'rt')as f:ds={r['at'][:10]:r for r in map(json.loads,f)}
 all_days=list(ds);silver=[]
 for day in frames['facts'].loc['2024-09-23':'2024-11-27'].index:
  s=frames['signal'].loc[day]
  if not bool(s.is_observed_bar):continue
  d=str(day.date());prev=all_days[all_days.index(d)-1];f=frames['facts'].loc[day];c=frames['CP1'].loc[day];inp=frames['CP1_input'].loc[day]
  assert float(inp.amount)==float(s.amount)
  assert bool(c.e0_valid)==bool(f.i_target)
  silver.append(dict(day=d,facts=f.to_dict(),source_signal=s.to_dict(),CP1=c.to_dict(),
   current_CLOSE_stock_layers=[l for l in ds[d]['layers']if l['sid']=='300085.SZ'],
   previous_CLOSE_stock_layers=[l for l in ds[prev]['layers']if l['sid']=='300085.SZ'],
   original_protection_exit_proposals=[a for a in b['audit']if a.get('sid')=='300085.SZ'and a.get('kind')=='pilot_layer_exit'and a.get('at','')[:10]==d],
   original_trades=[t for t in b['trades']if t['security_id']=='300085.SZ'and t['at'][:10]==d]))
 for sid,data in [('002583.SZ',hytera),('300085.SZ',silver)]:
  rows=[];protection=[]
  for r in data:
   f,s,c=r['facts'],r['source_signal'],r['CP1']
   row=dict(sid=sid,date=r['day'],continuous_CLOSE=f['close'],raw_OPEN=s['raw_open'],raw_HIGH=s['raw_high'],raw_LOW=s['raw_low'],raw_CLOSE=s['raw_close'],factor=f['factor'],amount=s['amount'],source_segment=f['segment_id'],
    original_E0_target=f['e0_target'],original_I_target=f['i_target'],original_I_floor_a=f['i_floor'],
    **{k:c[k]for k in ['ready','phase','reset_reason','r','s','z','B','u','v','m','anchor','frontier','scale','credit','delta_frontier','displacement','receipt','candidate','next_anchor','next_scale','next_credit','next_phase','e0_valid','e0_floor']})
   rows.append(row)
   # Retain only old factual protection/exit clock, no funding, fees, NAV or PnL advice.
   protection.append(dict(sid=sid,date=r['day'],continuous_CLOSE=f['close'],raw_CLOSE=s['raw_close'],factor=f['factor'],
    previous_CLOSE_original_layers=[{k:l[k]for k in ['id','kind','qty','floor','last_core_line']if k in l}for l in r['previous_CLOSE_stock_layers']],
    current_CLOSE_original_layers=[{k:l[k]for k in ['id','kind','qty','floor','last_core_line']if k in l}for l in r['current_CLOSE_stock_layers']],
    original_protection_exit_proposals=r['original_protection_exit_proposals'],
    original_filled_protection_events=[{k:t[k]for k in ['side','at','kind','layer','shares','signal_at','raw_open','price','floor','reason']if k in t}for t in r['original_trades']],
    last_floor_not_backfilled=True,intra_CLOSE_before_update_certificate=NS))
  csvsave(sid+'_ORIGINAL_CP_DAILY.csv',rows);save(sid+'_ORIGINAL_CP_DAILY.json',rows)
  save(sid+'_ORIGINAL_PROTECTION_CLOCKS.json',protection)
  save(sid+'_ORIGINAL_SELECTED_ROWS.json',[r for r in rows if r['date']in['2024-09-23','2024-09-24','2024-09-25','2024-09-30','2024-10-08','2024-10-09','2024-10-10','2024-10-11','2024-10-15','2024-10-18','2024-10-21','2024-10-22','2024-10-31','2024-11-04']])
  assert len(rows)==43
 # Reuse the exact seven previous silver snapshots as identity checks, never select new stocks.
 old_s=[r for r in snapshots if r['sid']=='300085.SZ']
 for r in old_s:
  if r['day']<'2024-09-23'or r['day']>'2024-11-27':continue
  d=next(x for x in silver if x['day']==r['day'])
  # Previous JSON encoded source numeric NaN as null; this extractor labels it.
  scalar=lambda v:'SOURCE_NULL'if clean(v)is None else clean(v)
  assert all(scalar(r['original_CP1_fields'][k])==scalar(d['CP1'][k])for k in r['original_CP1_fields'])
 save('EXISTING_SILVER_CASE_BINDING.json',dict(sid='300085.SZ',existing_case_source=str(ROOT/'upside_state_v1/examples_924'),old_saved_keypoints=len(old_s),old_saved_layers=[r['layer']for r in chains if r['sid']=='300085.SZ'],numeric_cache_matches_old_keypoints=True,
  selection='Fixed already-existing named September/October failed CP-protection example; no new stock or winner search. No profitability analysis here.',
  source_paths={k:str(v)for k,v in rec['refs'].items()},all_original_CP_numeric_history_start=str(frames['CP1'].index.min()),numeric_history_rows=len(frames['CP1'])))
 source=bind('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py');ls=source.read_text().splitlines()
 (OUT/'ORIGINAL_CP_FORMULA_SOURCE.txt').write_text(f'PATH {source}\nSHA256 {H[str(source)]}\nLINES1-61\n'+'\n'.join(f'{i:4d} {ls[i-1]}'for i in range(1,62))+'\n')
 for name in ['CP_stock_input_native_frame.py.txt','CP_stock_input_older_common_frame.py.txt']:
  p=bind(ROOT/'native_algorithm_read_v1/cp_pvr/snippets'/name);(OUT/name).write_text(p.read_text())
 save('AVAILABILITY_AND_SCOPE.json',dict(stocks={'002583.SZ':{'window':['2024-09-23','2024-11-27'],'observations':43,'ready':sum(bool(r['CP1']['ready'])for r in hytera),'receipts':sum(bool(r['CP1']['receipt'])for r in hytera)},'300085.SZ':{'window':['2024-09-23','2024-11-27'],'observations':43,'ready':sum(bool(r['CP1']['ready'])for r in silver),'receipts':sum(bool(r['CP1']['receipt'])for r in silver)}},
  original_windows={'s':'prior63 abs log returns,shifted,median*1.4826; floor1e-8','B':'prior21 amount observations,shifted median','z':'max(s,log1p0.001)','scale':'frozen at start/lower-anchor/receipt; today z becomes next_scale after receipt'},
  price_and_clock='Original numeric continuous price+raw OHLC/factor. CP is CLOSE-only, not intraday quote proof. Original execution references daily-bar proxy only.',
  CP_input_gate='Stock field named e0_valid is mapped from actual i_target; e0_down from original price event=-1. Preserve this source identity, do not silently replace with E0_target.',
  prehistory='Prior63/21 ingredients extend before9/23; full original cached input/history paths are available. Current extraction copies saved s/B/u/v/m instead of recomputing them.',
  shadow_formula_frozen_or_run=False,new_accounts=0,new_indicators=0,new_CP_calculations=0,new_funding_or_order_designs=0,new_return_comparisons=0))
 save('SOURCE_SHA256.json',H)
if __name__=='__main__':main()
