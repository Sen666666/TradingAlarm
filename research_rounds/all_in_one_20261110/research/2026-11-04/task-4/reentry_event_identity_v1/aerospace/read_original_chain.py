"""Bounded source-row joins for one original No60 stock; no model/feature/account run.

Prices and pivots are original saved fields. Reference comparisons and observation
counts are scalar bookkeeping, not regenerated E0/G1/CP or a new trading policy.
"""
from pathlib import Path
from decimal import Decimal as D
import gzip,hashlib,json,math,csv
import pandas as pd
ROOT=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-4');OUT=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={};SID='000547.SZ'
def bind(p):
 p=Path(p);h=hashlib.sha256()
 with p.open('rb')as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 SRC[str(p)]=h.hexdigest();return p
def rj(p):return json.loads(bind(p).read_text())
def clean(x):
 if x is pd.NA or x is pd.NaT:return None
 if isinstance(x,pd.Timestamp):return x.isoformat()
 if isinstance(x,D):return str(x)
 if isinstance(x,dict):return {k:clean(v)for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v)for v in x]
 if hasattr(x,'item'):return clean(x.item())
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def save(n,x):(OUT/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
sm=rj(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');rec=next(r for r in sm if r['symbol']==SID)
case=rj(W/'case-stock-cp1-warmup-20261031/MANIFEST.json');case=next(r for r in case if r['sid']==SID)
def frame(path,expected):
 p=bind(path);assert SRC[str(p)]==expected;return pd.read_parquet(p)
facts=frame(rec['refs']['facts'],rec['output_sha256'][rec['refs']['facts']]);cp=frame(rec['refs']['CP1'],rec['output_sha256'][rec['refs']['CP1']])
events_path=next(p for p in rec['source_sha256']if p.endswith('/events.parquet'));events=frame(events_path,rec['source_sha256'][events_path])
ixpath=next(p for p in rec['source_sha256']if p.endswith('/000547.SZ.parquet'));ix=frame(ixpath,rec['source_sha256'][ixpath])
receipts=rj(rec['refs']['receipts']);assert SRC[rec['refs']['receipts']]==rec['output_sha256'][rec['refs']['receipts']]
by_receipt={r['confirmed_day']:r for r in receipts}
dates=[str(d.date())for d in facts.loc['2025-11-20':'2025-12-05'].index]+['2026-01-15','2026-01-16'];wanted=set(dates)
pair=ROOT/'new_price_trend_v1/funding/runs/strong_OFF/pair';book=json.load(gzip.open(bind(pair/'B.json.gz'),'rt'));daily={}
with gzip.open(bind(pair/'daily.jsonl.gz'),'rt')as f:
 for line in f:
  r=json.loads(line);day=r['at'][:10]
  if day in wanted:daily[day]=r
  if day>'2026-01-16':break
ops=[];fund=[]
for file,target in [('opportunities.jsonl.gz',ops),('funding.jsonl.gz',fund)]:
 with gzip.open(bind(pair/file),'rt')as f:
  for line in f:
   r=json.loads(line);day=r.get('day',r.get('at',''))[:10]
   if r.get('sid')==SID and day in wanted:target.append(r)
   if day>'2026-01-16':break
decisions={r['at'][:10]:r for r in book['decisions']if r['at'][:10]in wanted};layers={r['id']:r for r in book['layers']}
layer_saved={r['layer']:r for r in rj(ROOT/'new_price_trend_v1/analysis/strong_OFF_LAYERS.json')}

references=[
 dict(id='old_CP_confirm_2025_11_20',kind='actual prior CP confirmation CLOSE, not daily intraday high',known_day='2025-11-20',price=facts.loc['2025-11-20'].close,raw_close=facts.loc['2025-11-20'].raw_close),
 dict(id='old_I_floor_known_2025_11_24',kind='Nov21 low confirmed at Nov24 event+1, original I line before Nov27 failure',known_day='2025-11-24',price=facts.loc['2025-11-24'].i_floor,raw_close_at_pivot=facts.loc['2025-11-21'].raw_close,pivot_day='2025-11-21'),
 dict(id='CP_confirm_2025_11_24',kind='new CP confirmation CLOSE within old E0 episode, below prior Nov20 high',known_day='2025-11-24',price=facts.loc['2025-11-24'].close,raw_close=facts.loc['2025-11-24'].raw_close),
 dict(id='confirmed_peak_from_2025_11_25',kind='Close-based developing peak Nov25, confirmed only at Nov26 event-1',known_day='2025-11-26',price=events.loc['2025-11-26'].confirmed_pivot_price,raw_close_at_pivot=facts.loc['2025-11-25'].raw_close,pivot_day='2025-11-25'),
]
rows=[]
for day in dates:
 at=pd.Timestamp(day);f=facts.loc[at];c=cp.loc[at];e=events.loc[at];g=ix.loc[at];d=daily[day]
 # Only compare existing cached G1 fields; never use legacy ix_target as actual I.
 equal={a:bool(f[a]==g[b])for a,b in [('g_grade','grade'),('g_fresh_up','fresh_up'),('g_acute_down','acute_down'),('g_ready','strength_ready')]};assert all(equal.values())
 hist=events.loc[:at];peaks=hist[(hist.event.eq(-1))&hist.confirmed_pivot_price.notna()];lows=hist[(hist.event.eq(1))&hist.confirmed_pivot_price.notna()]
 def last_known(p):
  if p.empty:return None
  z=p.iloc[-1];return dict(confirmation_day=str(p.index[-1].date()),pivot_day=z.confirmed_pivot_date,pivot_price=z.confirmed_pivot_price,event=z.event)
 previous_receipts=[r for r in receipts if r['confirmed_day']<=day]
 rows.append(dict(day=day,decision_clock=day+'T15:10:00+08:00',facts=f.to_dict(),original_price_event=e.to_dict(),
   known_confirmed_high=last_known(peaks),known_confirmed_low=last_known(lows),
   cached_G1=dict(grade=g.grade,fresh_up=g.fresh_up,acute_down=g.acute_down,strength_ready=g.strength_ready,phase=g.phase,up_reasons=g.up_reasons,legacy_ix_target_not_actual_I=g.ix_target),actual_G1_fields_equal_saved_IX=equal,
   CP=c.to_dict(),canonical_receipt_today=by_receipt.get(day),last_historical_canonical_receipt=previous_receipts[-1]if previous_receipts else None,
   historical_receipt_warning='Last receipt is historical evidence, not an active current permission. New E0 active Nov28 has no receipt until Dec1; do not backfill future receipt as a Nov28 trade credential.',
   reference_comparisons=[dict(reference_id=r['id'],known_today=r['known_day']<=day,reference_price=r['price']if r['known_day']<=day else None,close_strictly_above=bool(f.close>r['price'])if r['known_day']<=day else None)for r in references],
   original_stock_qty_at_CLOSE=d['positions'].get(SID,0),original_live_layers_at_CLOSE=[r for r in d['layers']if r['sid']==SID],
   original_opportunity=[r for r in ops if r['day']==day],original_frozen_intents=[r for r in decisions[day]['intents']if r['sid']==SID],
   original_ACT_checkpoints=[r for r in book['audit']if r.get('kind')=='risk_checkpoint'and r['at'][:10]==day]))
save('DAILY_ORIGINAL_E0_G1_I_CP_AND_LEDGER.json',rows)

def observation_gap(start,end):return int(facts.index.get_loc(pd.Timestamp(end))-facts.index.get_loc(pd.Timestamp(start)))
reclaims=[]
for ref in references:
 after=[r for r in rows if'2025-11-28'<=r['day']<='2025-12-05'and ref['known_day']<=r['day']and float(r['facts']['close'])>float(ref['price'])]
 first=after[0]if after else None
 reclaims.append(dict(reference=ref,first_post_Nov27_failure_saved_CLOSE_above=first['day']if first else None,observations_after_Nov27_failure_CLOSE=observation_gap('2025-11-27',first['day'])if first else None,observations_after_Nov28_actual_sell_day=observation_gap('2025-11-28',first['day'])if first else None,scope='Scalar comparison across all original stock observations Nov28-Dec5, using only previously known stored references; no new event/signal detector.'))
save('KNOWN_REFERENCES_AND_RECLAIM_CLOCKS.json',dict(references=references,reclaims=reclaims,semantics='Reference prices are adjusted continuous CLOSE/pivot/I line; raw_CLOSE at the originating observation is separately labeled, not intraday high.'))

ids=[415,483,485,493,506,548,555,565];old=[415,483,485,493];new=[548,555,565]
trades=[r for r in book['trades']if r['security_id']==SID and ((r['side']=='buy'and r.get('layer')in ids)or(r['side']=='sell'and any(x['layer']in ids for x in r['parts'])))]
proposals=[r for r in book['audit']if r.get('kind')=='pilot_layer_exit'and r.get('sid')==SID and set(r.get('layers',[])).intersection(ids)]
save('ORIGINAL_PROXY_TRADES_AND_THREE_GROUPS.json',dict(execution_boundary='All trades/FillReceipt are records of the original daily-bar-proxy backtest, not broker receipts or quote-level execution proof; no intraday crossing timestamp asserted.',trades=trades,original_exit_proposals=proposals,original_selected_funding=fund,
 original_layer_snapshots=[layers[k]for k in ids],original_terminal_metadata_not_historical_backfill={str(k):book['metadata'][str(k)]if str(k)in book['metadata']else book['metadata'].get(k)for k in ids},
 groups=[dict(group='Nov24 old MOBILE group',layers=[layer_saved[k]for k in old],closed_net=sum((D(layer_saved[k]['net'])for k in old),D(0))),dict(group='Nov25 failed CORE506',layers=[layer_saved[506]],closed_net=layer_saved[506]['net']),dict(group='Dec2/3/5 new-wave MOBILE',layers=[layer_saved[k]for k in new],closed_net=sum((D(layer_saved[k]['net'])for k in new),D(0)),actual_buy_cost=sum((D(layer_saved[k]['cost'])for k in new),D(0)))],
 note='Groups are original realized closed-layer contributions with modeled fees and recognized dividends, not whole-account returns or hypothetical retained profits.'))

old_id=by_receipt['2025-11-24']['original_E0_episode_id'];new_id=by_receipt['2025-12-01']['original_E0_episode_id'];assert old_id!=new_id
cols=['close','segment_id','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready','e0_ready','factor','raw_close']
save('IDENTITY_AND_SOURCE_FIELD_BOUNDARIES.json',dict(
 actual_E0_proof=dict(old_canonical_E0_id=old_id,new_canonical_E0_id=new_id,saved_in_receipts=['2025-11-24','2025-12-01','2025-12-02','2025-12-04'],Nov27_actual_E0_target=int(facts.loc['2025-11-27'].e0_target),Nov28_actual_E0_target=int(facts.loc['2025-11-28'].e0_target),Nov28_original_price_event=events.loc['2025-11-28'].to_dict(),identity_note='Local canonical trace hash stored in CP receipts, not a provider-issued E0 ID; current actual target0->1 plus saved pivot/event corroborates new episode. No inference from I counter alone; no receipt existed Nov28 itself.'),
 actual_I_epoch=dict(old_CORE506=layers[506]['epoch'],new_MOBILE548=layers[548]['epoch'],source_segment_unchanged=True,meaning='Native joint planning216-219 increments counter when (I_target,segment) changes. [0,3]->off-> [0,5] is this I/source state counter, not the canonical E0 SHA or account ACT episode.'),
 account_ACT_episode_by_saved_day={r['day']:[z.get('episode')for z in r['original_ACT_checkpoints']]for r in rows},
 industry_budget_episode_note='Terminal layer metadata episode/attempt is industry financial authorization identity; it is not stock E0 canonical ID. Exported separately and not backfilled into historical daily rows.',
 original_manifest_checks=rec['checks'],original_case_I_E0_audit_fields_exact=case['I_E0_audit_fields_exact'],original_native_cache_equivalence_field_list=cols,
 legacy_state_scope='prepared-v2 states.parquet companion pending_id/ended_id/consumed_by_base/independent_entry and legacy IX.ix_target are not imported as actual No60 decision states. Original native equivalence covers the14 listed facts fields, not companion pending/N1 fields. This readout uses actual facts E0/I and raw original confirmed-pivot fields, not a rerun of legacy policy.',
 direct_this_slice_G1_equality='Only g_grade/g_fresh_up/g_acute_down/g_ready were compared to saved IX grade/fresh_up/acute_down/strength_ready; legacy ix_target was never substituted for actual i_target.'))
for p in [W/'case-stage-ledger-20261031/v3/joint_v3.py',W/'cp1-evidence-trace-20261031/trace.py',W/'native-I-cache-interface-20261031/cache.py',W/'case-stock-cp1-warmup-20261031/generate.py']:bind(p)
save('SOURCE_SHA256.json',SRC)
save('SCOPE.json',dict(status='ORIGINAL_IDENTITY_CHAIN_READ_COMPLETE',stock=SID,saved_daily_rows=len(rows),price_window='2025-11-20..2025-12-05 original daily observations;2026 onlyJan15/16. Prior confirmed-pivot/receipt metadata as-of each selected date comes from existing event records, not regenerated pivots.',new_models_features_or_strategies=0,new_accounts_or_backtests=0,new_financial_replay=0,new_intraday_quotes=0,legacy_pending_state_not_promoted=True,execution_basis='Original daily-bar-proxy ledger only, not broker/trade-minute proof.'))
print(json.dumps(clean(dict(days=len(rows),old_E0=old_id,new_E0=new_id,ACT_episodes={r['day']:[z.get('episode')for z in r['original_ACT_checkpoints']]for r in rows},reclaims=reclaims,Jan15=next(r for r in rows if r['day']=='2026-01-15'))),ensure_ascii=False)[:5000])
