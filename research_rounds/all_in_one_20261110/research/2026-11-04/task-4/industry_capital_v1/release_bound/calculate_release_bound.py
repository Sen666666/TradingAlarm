"""Original same-industry capital-relief bound, not a rotation policy/account.
Only existing S0 layers are marked, with strict same-OPEN identity checks.
"""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from datetime import datetime
import gzip,hashlib,json,sys,time
import numpy as np

O=Path(__file__).resolve().parent;ROOT=O.parent;W=ROOT.parent
sys.path.insert(0,str(W/'new_price_trend_v1'))
import native_mark_reader as MARK
SOURCES={};CACHE={};EPS=D('.000001');ZERO=D(0)
def bind(p):p=Path(p);SOURCES[str(p.resolve())]=hashlib.sha256(p.read_bytes()).hexdigest();return p
def read(p):return json.loads(bind(p).read_text())
def stream(p):
 with gzip.open(bind(p),'rt')as f:
  for x in f:yield json.loads(x)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def writer(n,rows):
 with gzip.open(O/n,'wt')as f:
  for x in rows:f.write(json.dumps(x,ensure_ascii=False,default=str)+'\n')
def mark_open(sid,day):
 key=sid,day
 if key in CACHE:return CACHE[key]
 at=datetime.fromisoformat(day+'T09:30:00+08:00')
 try:
  # This only initializes a read-only raw/action carrier. Its CLOSE value is
  # discarded; every price below is from unchanged native latest_mark(atOPEN).
  if sid not in MARK.views:MARK.price(sid,day)
  view=MARK.views[sid];m=MARK.F.latest_mark(view,sid,at);raw=view.raw[sid]
  import pandas as pd
  ix=pd.Timestamp(day);v=raw.loc[ix,'open']if ix in raw.index else None
  rawopen=D(str(v))if v is not None and np.isfinite(v)and v>0 else None
  live=m.known_at==at and rawopen is not None and m.cny_price(at)==rawopen
  out=dict(sid=sid,OPEN=day,status='SAME_OPEN_RAW'if live else'STALE_OR_NONOPEN_REFERENCE',
      mark=str(m.cny_price(at)),raw_OPEN=str(rawopen)if rawopen is not None else None,
      known_at=str(m.known_at),source_id=m.source_id,strict_OPEN_identity=live,
      executable_sale_not_proven=True)
 except Exception as e:out=dict(sid=sid,OPEN=day,status='SOURCE_UNKNOWN',error=repr(e),strict_OPEN_identity=False)
 CACHE[key]=out;return out

def aggregate(rows,subset):
 a=[x for x in rows if subset(x)];known=[x for x in a if x['release_amount_status']=='KNOWN_NECESSARY_BOUND']
 def desc(k,positive=False):
  vs=sorted(D(x[k])for x in known if x.get(k)is not None and(not positive or D(x[k])>0))
  if not vs:return dict(n=0)
  return dict(n=len(vs),min=str(vs[0]),median=str(vs[len(vs)//2]),p90=str(vs[min(len(vs)-1,int(len(vs)*.9))]),max=str(vs[-1]))
 return dict(events=len(a),known_bounds=len(known),unknown_reasons=dict(Counter(x['release_amount_status']for x in a if x['release_amount_status']!='KNOWN_NECESSARY_BOUND')),
   no_old_inventory=sum(x['no_old_inventory']for x in a),
   minimum_itself_above_sector_allowance=sum(bool(x.get('qmin_itself_exceeds_sector_allowance_SAFE'))for x in known),
   required_relief_exceeds_all_old_gross=sum(bool(x.get('relief_exceeds_all_old_inventory_SAFE'))for x in known),
   required_relief_exceeds_nonlocked_old_upper=sum(bool(x.get('relief_exceeds_nonlocked_old_upper_SAFE'))for x in known),
   positive_relief=sum(D(x['required_sector_relief_lower_bound_SAFE'])>0 for x in known),
   relief_amount=desc('required_sector_relief_lower_bound_SAFE'),positive_relief_amount=desc('required_sector_relief_lower_bound_SAFE',True),
   relief_to_new_minimum_gross=desc('relief_to_new_minimum_gross'),
   amounts_not_summed=True,unblocked_is_not_admission_or_trade=True)

def main():
 t=time.monotonic();bind(__file__)
 events=list(stream(ROOT/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz'))
 snapshots=read(ROOT/'events/ORIGINAL_EXISTING_LAYER_SNAPSHOTS.json')
 nav={}
 for p in stream(W/'core_supplement_v1/funding/P_ORIGINAL_RESOURCE_CONTEXT.jsonl.gz'):
  s=p.get('original_S0')
  if not s:continue
  key=p['window'],p['next_OPEN'];v=s['optimistic_NAV_upper']
  if key in nav:assert nav[key]==v
  nav[key]=v
 meta=read(MARK.E.J.M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');semis={s for s,r in meta.items()if r['industry']=='半导体'};assert len(semis)==126
 vals={};partial=False
 for n,(key,s)in enumerate(snapshots.items()):
  if time.monotonic()-t>82:partial=True;break
  pending=set(s['CLOSE_account']['pending_sells']);layers=[];gross=ZERO;locked=ZERO;reference=ZERO;bad=[]
  for z in s['surviving_existing_layers_at_S0']:
   q=D(str(z['qty_after_original_actions_and_protection_exits']));m=mark_open(z['sid'],s['OPEN']);value=q*D(m['mark'])if m.get('mark')is not None else None
   definite_lock=z['sid']in pending and z['previous_CLOSE_raw_layer'].get('reason')in ['ACT_pause','I_structure_exit','CP1_add_protection']
   layers.append(dict(layer=z['layer'],sid=z['sid'],role=z['role'],qty=str(q),mark_key=z['sid']+'|'+s['OPEN'],
       value=str(value)if value is not None else None,definitely_prior_exit_locked=definite_lock,
       source_prior_pending=z['sid']in pending,source_prior_reason=z['previous_CLOSE_raw_layer'].get('reason')))
   if value is not None:reference+=value
   if not m['strict_OPEN_identity']:bad.append(z['sid']);continue
   gross+=value
   if definite_lock:locked+=value
  known=not bad
  vals[key]=dict(window=s['window'],OPEN=s['OPEN'],sector=s['sector'],layers=layers,
      all_strict_OPEN_prices=known,non_OPEN_or_unknown_stocks=sorted(set(bad)),old_inventory_gross=str(gross)if known else None,
      all_native_references_gross=str(reference),definitely_locked_old_gross=str(locked)if known else None,
      nonlocked_old_gross_upper=str(gross-locked)if known else None,
      upper_scope='Excludes only proven surviving prior-exit layers. Other T+1/new CA-share locks, capacity/slippage/fees can further reduce what is sellable; never an executable sale guarantee.')
  if n%500==0:
   save('PROGRESS.json',dict(phase='target_old_layer_OPEN_marks',snapshots_done=len(vals),snapshots_total=len(snapshots),unique_marks=len(CACHE),seconds=time.monotonic()-t,limit_seconds=100))
  if n and n%2000==0:save('SNAPSHOT_OPEN_VALUES.partial.json',vals)
 result=[]
 for r in events:
  if r['snapshot_key']not in vals:continue
  v=vals[r['snapshot_key']];old=snapshots[r['snapshot_key']]['surviving_existing_layers_at_S0'];n=nav.get((r['window'],r['OPEN']))
  x=dict(key=r['key'],window=r['window'],sid=r['sid'],signal_day=r['signal_day'],OPEN=r['OPEN'],sector=r['industry'],classification=r['classification'],failure_tags=r['failure_tags'],
      is_first=r['is_first_sector_reject_in_original_source_I_epoch'],semiconductor126=r['sid']in semis,
      snapshot_key=r['snapshot_key'],no_old_inventory=not old,
      qmin_gross=r['original_OPEN_contract_preview']['dated_minimum_gross'],
      qmin_cash=r['original_OPEN_contract_preview']['dated_minimum_cash'],
      front_same_sector_actual_reserved_gross=r['original_sameOPEN_prior_commitments']['same_sector_recorded_reserved_gross'],
      front_same_sector_order_keys=r['original_sameOPEN_prior_commitments']['same_sector_prior_order_keys'],
      front_orders_cannot_assume_cancel=True,front_orders_or_fills_not_old_sellable_inventory=True,
      old_inventory_gross=v['old_inventory_gross'],nonlocked_old_gross_upper=v['nonlocked_old_gross_upper'],
      old_inventory_mark_status='STRICT_SAME_OPEN_RAW'if v['all_strict_OPEN_prices']else'CONTAINS_STALE_OR_UNKNOWN',
      release_amount_status='KNOWN_NECESSARY_BOUND'if v['all_strict_OPEN_prices']and n is not None else'NO_NAV_UPPER_IN_EXISTING_CONTEXT'if n is None else'STALE_OR_UNKNOWN_OLD_PRICE',
      NAV_optimistic_upper_source=str(n)if n is not None else None,
      not_a_release_order=True,complete_risk_and_cash_admission_unknown=True)
  if x['release_amount_status']=='KNOWN_NECESSARY_BOUND':
   sc=D(v['old_inventory_gross']);front=D(x['front_same_sector_actual_reserved_gross']);qn=D(x['qmin_gross']);upper=D(n)+EPS;allow=D('.02')*upper
   formula=max(ZERO,sc+front+qn-allow);safe=max(ZERO,formula-EPS);movable=D(v['nonlocked_old_gross_upper'])
   x.update(pre_candidate_industry_capital_from_old_plus_actual_front=str(sc+front),sector_allowance_optimistic_upper=str(allow),
      required_sector_relief_formula=str(formula),required_sector_relief_lower_bound_SAFE=str(safe),
      relief_to_new_minimum_gross=str(safe/qn),relief_to_all_old_inventory_gross=str(safe/sc)if sc else None,
      relief_exceeds_all_old_inventory_SAFE=safe>sc+EPS,relief_exceeds_nonlocked_old_upper_SAFE=safe>movable+EPS,
      qmin_itself_exceeds_sector_allowance_SAFE=qn>allow+EPS,front_itself_exceeds_sector_allowance_SAFE=front>allow+EPS)
  result.append(x)
 suffix='.partial'if partial else''
 writer('RELEASE_BOUND_EVENTS'+suffix+'.jsonl.gz',result);save('SNAPSHOT_OPEN_VALUES'+suffix+'.json',vals);save('OPEN_MARK_STATUS'+suffix+'.json',list(CACHE.values()))
 groups={
  'ALL_RAW':aggregate(result,lambda x:True),'ALL_FIRST':aggregate(result,lambda x:x['is_first']),
  'LONG_RAW':aggregate(result,lambda x:x['window']=='long'),'STRONG_RAW':aggregate(result,lambda x:x['window']=='strong'),
  'H1_2026_SEMICONDUCTOR_RAW':aggregate(result,lambda x:x['window']=='strong'and x['OPEN']>='2026-01-01'and x['semiconductor126']),
  'H1_2026_SEMICONDUCTOR_FIRST':aggregate(result,lambda x:x['window']=='strong'and x['OPEN']>='2026-01-01'and x['semiconductor126']and x['is_first'])}
 SOURCES.update(MARK.sources)
 save('SOURCE_SHA256'+suffix+'.json',SOURCES)
 save('RELEASE_BOUND_SUMMARY'+suffix+'.json',dict(complete=not partial,events=len(result),mother_events=len(events),snapshots=len(vals),unique_stock_OPEN_marks=len(CACHE),
    mark_status_counts=dict(Counter(m['status']for m in CACHE.values())),existing_NAVupper_OPENs=len(nav),groups=groups,
    seconds=time.monotonic()-t,limit_seconds=100,new_accounts=0,new_RiskBooks=0,new_full_market_preparations=0,
    formula='max(0, old_SC_gross+actual_prior_same_sector_reserved_gross+qmin_gross-.02*(existing_NAVupper+1e-6))',
    numerical_safety='Additional 1e-6 currency deducted from bound; comparisons add 1e-6 to inventory upper. No economic parameter change.',
    claim='Necessary original-path capital relief lower bound only. Ignores sell fees/NAV loss and does not permit cancelling committed front orders or selling T+1/locked assets. No return/shortfall totals.'))
 print('RELEASE_BOUND_COMPLETE'if not partial else'RELEASE_BOUND_PARTIAL',len(result),len(vals),len(CACHE),time.monotonic()-t,flush=True)
if __name__=='__main__':main()
