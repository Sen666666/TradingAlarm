"""Restored one selected original I-exit V lead; only four cached dates, no model."""
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
 if isinstance(x,dict):return {k:clean(v)for k,v in x.items()}
 if isinstance(x,list):return [clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

leads=readj(OUT/'ledger_search/I_EXIT_CANDIDATES.json');lead=next(r for r in leads['candidates']if r['I_exit_layer']==506);sid=lead['sid'];assert sid=='000547.SZ'
manifest=readj('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json');rec=next(r for r in manifest if r['symbol']==sid)
fp=bind(rec['refs']['facts']);cp=bind(rec['refs']['CP1']);assert SOURCE[str(fp)]==rec['output_sha256'][str(fp)]and SOURCE[str(cp)]==rec['output_sha256'][str(cp)]
facts=pd.read_parquet(fp);cpf=pd.read_parquet(cp)
pair=ROOT/'new_price_trend_v1/funding/runs/strong_OFF/pair';book=json.load(gzip.open(bind(pair/'B.json.gz'),'rt'));layers={r['id']:r for r in book['layers']}
dates=['2025-11-27','2025-11-28','2025-12-01','2025-12-02'];daily={}
with gzip.open(bind(pair/'daily.jsonl.gz'),'rt')as f:
 for line in f:
  r=json.loads(line);day=r['at'][:10]
  if day in dates:daily[day]=r
  if day>'2025-12-02':break
ops=[];fund=[]
for file,target in [('opportunities.jsonl.gz',ops),('funding.jsonl.gz',fund)]:
 with gzip.open(bind(pair/file),'rt')as f:
  for line in f:
   r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
   if r.get('sid')==sid and day in dates:target.append(r)
   if day>'2025-12-02':break
points=[]
for day in dates:
 f=facts.loc[day];c=cpf.loc[day];d=daily[day]
 points.append(dict(day=day,same_coordinate='continuous CLOSE/I/CP/last_core_line; raw_close separately labeled',facts={k:f[k]for k in ['close','raw_close','factor','segment_id','e0_target','i_target','i_floor','i_buy','g_ready','g_grade','g_fresh_up']},CP={k:c[k]for k in ['ready','receipt','candidate','e0_valid','e0_floor','reset_reason']},original_qty_at_CLOSE=d['positions'].get(sid,0),original_live_layers_at_CLOSE=[r for r in d['layers']if r['sid']==sid],original_opportunity=[r for r in ops if r['day']==day]))
buys=[r for r in book['trades']if r.get('layer')in[506,548,555,565]]
sells=[r for r in book['trades']if r['security_id']==sid and r['side']=='sell'and(r['at'][:10]in['2025-11-24','2025-11-28','2026-01-16'])]
proposals=[r for r in book['audit']if r.get('kind')=='pilot_layer_exit'and r.get('sid')==sid and set(r.get('layers',[])).intersection({415,483,485,493,506,548,555,565})]
save('RESTORED_000547_EXACT_SAVED_WINDOW.json',dict(status='FOUR_CACHED_DATES_READ_AFTER_ENVIRONMENT_RESTORED',sid=sid,name='航天发展',source_scope='Parent-selected completed original No60 ledger, precise four existing facts/CP dates; no broad price scan.',execution_evidence_boundary='All actual/trade/FillReceipt wording refers to executed entries in the original daily-bar-proxy No60 backtest ledger, not broker receipts or quote-level execution evidence. Prices are recorded daily OPEN plus protocol slippage. Closed-layer net is a proxy-ledger result including modeled fees and recognized dividends. Daily CLOSE recovery does not establish the intraday crossing time or post-open availability.',parent_saved_ledger_lead=lead,points=points,original_actual_buys=buys,original_actual_sells=sells,original_exit_proposals=proposals,original_funding=fund,
 original_prior_failed_core_layer=layers[506],original_winning_wave_layers=[layers[k]for k in [548,555,565]],
 interpretation_limits=['I_structure_exit is distinct from CP1_add_protection.','Nov24 CP exit then Nov25 CORE reentry failed before the later winning wave; not a one-way perfect V.','Later profit51001.61 is the saved three actual closed layers after Dec2 in the new I epoch, not foregone holding PnL or whole-account return.','Exact four-date price recovery can be described; no new V detector, model, indicators, account or financial path was run.'],new_models=0,new_indicators=0,new_accounts_or_backtests=0))
save('RESTORED_000547_SOURCE_SHA256.json',SOURCE)
print(json.dumps(clean(dict(sid=sid,points=[dict(day=r['day'],C=r['facts']['close'],rawC=r['facts']['raw_close'],I=r['facts']['i_target'],I_floor=r['facts']['i_floor'],CP=r['CP']['receipt'],candidate=r['CP']['candidate'],core_live=[{k:x.get(k)for k in ['id','floor','last_core_line','pending_I_exit_reference']}for x in r['original_live_layers_at_CLOSE']if x['kind']=='core'],op=r['original_opportunity'])for r in points],funding=fund)),ensure_ascii=False,indent=2))
