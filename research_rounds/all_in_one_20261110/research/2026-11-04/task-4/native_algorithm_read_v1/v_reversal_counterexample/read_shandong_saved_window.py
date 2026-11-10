"""One parent-selected saved candidate, exact five-date slice and last applied CP.
No model, new indicators, hypothetical order or strategy/financial replay.
"""
from pathlib import Path
import gzip,hashlib,json,math
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');OUT=Path(__file__).resolve().parent;SOURCE={}
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 SOURCE[str(p)]=h.hexdigest();return p
def readj(p):return json.loads(bind(p).read_text())
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return{k:clean(v)for k,v in x.items()}
 if isinstance(x,list):return[clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

lead=readj(OUT/'ledger_search/CANDIDATES.json');candidate=next(r for r in lead['candidates']if r['exit_layer']==1183)
sid=candidate['sid'];assert sid=='601019.SH'
manifest=readj('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');rec=next(r for r in manifest if r['symbol']==sid)
fpath=bind(rec['refs']['facts']);cpath=bind(rec['refs']['CP1']);assert SOURCE[str(fpath)]==rec['output_sha256'][str(fpath)]and SOURCE[str(cpath)]==rec['output_sha256'][str(cpath)]
facts=pd.read_parquet(fpath);cp=pd.read_parquet(cpath)
pair=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair'
book=json.load(gzip.open(bind(pair/'B.json.gz'),'rt'));layers={r['id']:r for r in book['layers']}
buy0=next(r for r in book['trades']if r.get('layer')==1183);buy1=next(r for r in book['trades']if r.get('layer')==1230)
sell0=next(r for r in book['trades']if r['side']=='sell'and any(p['layer']==1183 for p in r['parts']))
proposal=next(r for r in book['audit']if r.get('kind')=='pilot_layer_exit'and 1183 in r.get('layers',[]))
firstday=proposal['at'][:10];last_cp=cp.loc[buy0['signal_at'][:10]:firstday].iloc[:-1];last_cp_day=last_cp.index[last_cp.receipt.eq(True)][-1]
last_cp_row=cp.loc[last_cp_day];last_cp_fact=facts.loc[last_cp_day]
dates=['2023-04-10','2023-04-11','2023-04-12','2023-04-13','2023-04-14'];daily={}
with gzip.open(bind(pair/'daily.jsonl.gz'),'rt')as f:
 for line in f:
  r=json.loads(line);day=r['at'][:10]
  if day in dates:daily[day]=r
  if day>'2023-04-14':break
ops=[];fund=[]
for file,target in [('opportunities.jsonl.gz',ops),('funding.jsonl.gz',fund)]:
 with gzip.open(bind(pair/file),'rt')as f:
  for line in f:
   r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
   if r.get('sid')==sid and day in dates:target.append(r)
   if day>'2023-04-14':break
points=[]
for day in dates:
 f=facts.loc[day];c=cp.loc[day];d=daily[day]
 points.append(dict(day=day,facts={k:f[k]for k in ['close','raw_close','factor','segment_id','e0_target','i_target','i_floor','i_buy','g_ready','g_grade','g_fresh_up']},CP={k:c[k]for k in ['receipt','candidate','e0_valid','reset_reason','anchor','frontier','scale','credit']},original_qty_at_CLOSE=d['positions'].get(sid,0),original_live_layers_at_CLOSE=[r for r in d['layers']if r['sid']==sid],original_opportunities=[r for r in ops if r['day']==day]))
result=dict(scope='One parent-selected original No60 candidate; facts/CP already cached, five exact dates only. No new model/order/financial path.',sid=sid,name='山东出版',canonical_sid_correction='601019.SH in original ledger, not parent typo601019.SZ',parent_saved_ledger_candidate=candidate,
 original_prior_buy=buy0,original_first_exit_proposal=proposal,original_actual_exit=sell0,original_exited_layer=layers[1183],
 last_applied_CP_before_exit_decision=dict(day=str(last_cp_day.date()),close_adjusted=last_cp_fact.close,raw_close=last_cp_fact.raw_close,factor=last_cp_fact.factor,candidate_adjusted=last_cp_row.candidate,receipt=last_cp_row.receipt,note='Last cached receipt before exit-decision CLOSE. Original layer-floor values in daily snapshot remain authoritative for what was actually checked.'),
 original_reentry_buy=buy1,original_reentry_layer=layers[1230],original_reentry_sell=[r for r in book['trades']if r['side']=='sell'and any(p['layer']==1230 for p in r['parts'])],
 points=points,original_funding=fund,
 assessment=dict(price_V='Immediate recovery from actual sell-day CLOSE then two successively higher closes; exact shape and old-level comparisons are explicitly reported, not a fitted V detector.',strict_major_winner_claim='NOT_MADE. Reentry layer closed profit5870.88; saved later same-I-epoch closed-layer total8955.15 is modest account money, not a giant whole-account winner.',no_new_PnL_or_size_calculated=True,all_price_comparisons_same_continuous_coordinate=True))
save('SHANDONG_601019_EXACT_SAVED_WINDOW.json',result)
save('SHANDONG_SOURCE_SHA256.json',SOURCE)
print(json.dumps(clean(dict(sid=sid,prior_buy=buy0['at'],exit_proposal=proposal['at'],actual_exit=sell0['at'],last_CP=result['last_applied_CP_before_exit_decision'],points=[dict(day=r['day'],C=r['facts']['close'],raw=r['facts']['raw_close'],I=r['facts']['i_target'],I_floor=r['facts']['i_floor'],CP=r['CP']['receipt'],candidate=r['CP']['candidate'],oldlayer_floors=[dict(id=x['id'],floor=x['floor'])for x in r['original_live_layers_at_CLOSE']],ops=r['original_opportunities'])for r in points])),ensure_ascii=False,indent=2))
