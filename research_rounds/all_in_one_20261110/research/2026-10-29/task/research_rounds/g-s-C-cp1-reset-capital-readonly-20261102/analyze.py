"""Existing causal CP1 traces and native ledgers only; no market/account events."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
from dataclasses import is_dataclass,asdict
import sys,json,pickle,hashlib,math,time
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-month-continuation-20261102'))
import month_runtime as M
import c_selector as C
B=C.B;J=C.J;Z=D(0);ENG=W/'g-s-C-engineering-causal-readonly-20261102';MONTH=W/'g-s-C-month-continuation-20261102'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def clean(x):
 if is_dataclass(x):return clean(asdict(x))
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list,set)):return [clean(v) for v in x]
 if isinstance(x,float) and not math.isfinite(x):return None
 if hasattr(x,'item'):return clean(x.item())
 if x is None:return None
 try:
  import pandas as pd
  if pd.isna(x):return None
 except (ValueError,TypeError):pass
 if isinstance(x,D):return str(x)
 return x
def save(n,x):M.E.IO.write_json(HERE/n,clean(x),encoder=M.E.encode)
def scan(cp,facts):
 out={};contexts=[]
 for sid,g in cp.groupby('sid',sort=True):
  root=None;anchor=None;neg=False;low=False;last_receipt=None;segment=None;prior=None
  for z in g.sort_values('day').to_dict('records'):
   day=z['day'];f=facts.get((sid,day));seg=f['segment_id'] if f else None;reason=z['reset_reason']
   if seg is None:raise ValueError('missing source identity '+sid+' '+day)
   changed=segment is not None and seg!=segment
   if changed:root=anchor=None;neg=low=False
   segment=seg
   if reason in ('unprepared','E0_invalid'):
    root=anchor=None;neg=low=False
   elif reason in ('start','E0_down_reset'):
    root=dict(sid=sid,segment=seg,day=day,reason=reason);anchor=root.copy();neg=reason=='E0_down_reset';low=False
   elif reason=='lower_anchor':anchor=dict(sid=sid,segment=seg,day=day,reason=reason);low=True
   if z['receipt']:
    assert reason=='receipt_consumed' and z['e0_valid']
    if z['phase']=='UP':kind='UP_CONTINUATION'
    elif z['phase']=='SEEK' and (neg or low):kind='RESET_SEEK_REPAIR'
    elif z['phase']=='SEEK' and root is not None and root['reason']=='start':kind='START_SEEK_FIRST'
    elif z['phase']=='SEEK':kind='SEEK_ORIGIN_UNKNOWN'
    else:kind='UNKNOWN'
    row=dict(kind=kind,negative_reset_observed=neg,lower_anchor_observed=low,root_reset=root,latest_anchor_reset=anchor,
      diagnostic_root_id=J.digest(root) if root else None,diagnostic_anchor_id=J.digest(anchor) if anchor else None,
      inherited_origin_unknown=root is None,previous_receipt_observed=last_receipt,trace=z,
      I_target=f['i_target'],E0_target=f['e0_target'],signal_close=f['close'],segment_id=seg,
      receipt_context_is_not_native_id=True)
    out[(sid,day)]=row;last_receipt=dict(sid=sid,day=day,phase=z['phase']);neg=low=False
   prior=day
 return out
def brief_validation(v,sid):
 return dict(ok=v['validation']['ok'],violations=v['validation']['violations'],terminal=v['validation']['terminal'],
  own_reserve_checks=[z for z in v['validation']['checks'] if z['stage']=='reserve:'+sid],D=v['D'],actual_cash_released=0,actual_risk_released=0)
def aggregate(events):
 groups=defaultdict(lambda:dict(events=0,stocks=set(),Q_pass=0,Q_unknown=0,Q_false=0,C_requested=0,C_positive=0,C_actual_reserved=0,C_actual_filled=0,
  original_max_gross=Z,planned_gross=Z,actual_buy_gross=Z,layers=0,entry_classes=Counter(),role_pool=Counter(),
  actual_realized=Z,unrealized=Z,booked_dividend=Z,closed_positive=Z,closed_negative=Z,open_layer_contribution=Z))
 for e in events:
  a=groups[e['classification']['kind']];a['events']+=1;a['stocks'].add(e['sid']);a['Q_pass']+=e['Q'] is True;a['Q_unknown']+=e['Q'] is None;a['Q_false']+=e['Q'] is False
  a['C_requested']+=e['C_demand'] is not None;a['C_positive']+=bool(e['C_plan_q']);a['C_actual_reserved']+=bool(e['C_orders']);a['C_actual_filled']+=any(z['filled_qty'] for z in e['C_orders'])
  a['original_max_gross']+=e['original_max_gross'];a['planned_gross']+=e['planned_gross']
  for z in e['actual_layers']:
   a['layers']+=1;a['entry_classes'][z['entry_class']]+=1;a['role_pool'][z['role']+'|'+z['pool']+'|'+z['purpose']]+=1
   a['actual_buy_gross']+=D(z['buy_gross']);a['actual_realized']+=D(z['realized_trade_PNL']);a['unrealized']+=D(z['unrealized_net_buy_cost']);a['booked_dividend']+=D(z['booked_dividend_income'])
   cc=D(z['total_contribution'])
   if z['remaining_qty']:a['open_layer_contribution']+=cc
   elif cc>0:a['closed_positive']+=cc
   elif cc<0:a['closed_negative']+=cc
 for a in groups.values():a['stocks']=len(a['stocks'])
 return dict(groups)
def main():
 start=time.perf_counter();M.guard();co=read(ENG/'ALL_FRESH_CP1_COHORT.json');layers=read(MONTH/'july_end_analysis/ALL_LAYERS.json');stocks=read(MONTH/'july_end_analysis/ALL_STOCKS.json');meta=read(MONTH/'inputs/2025_26/metadata.json')
 ids={arm:{(e['sid'],e['day'],e['canonical']['receipt_id']) for e in es} for arm,es in co.items()};assert len(next(iter(ids.values())))==3336 and len({J.digest(sorted(v))for v in ids.values()})==1
 summaries={};checks={};all_events={};previews={};control_candidates={};ledger_paths={}
 for arm,cohort in co.items():
  path=MONTH/'runs'/arm/'2025-07-31-CLOSE.pkl';expected=read(path.with_suffix('.provenance.json'));assert sha(path)==expected['checkpoint_sha256'];r=pickle.loads(path.read_bytes());assert r.binding()==expected['binding'];before=J.digest(M.C.prefix_view(r));ledger_paths[str(path)]=sha(path)
  cp=clean(r.inputs.table('cp').to_dict('records'));facts=clean(r.inputs.table('facts').to_dict('records'));fm={(z['sid'],z['day']):z for z in facts};cm=scan(__import__('pandas').DataFrame(cp),fm)
  assert {(sid,day)for sid,day in cm if day>='2025-07-01'}=={(e['sid'],e['day'])for e in cohort}
  lm=defaultdict(list)
  for z in layers[arm]:lm[(z['sid'],z['signal_at'][:10])].append(z)
  projections={};pv=[]
  for v in r.results:
   day=v['at'][:10];tr=r.trusted[v['certificate']['trusted_id']];s,ds,audit=C.transform(tr['snapshot'],tr['demands'],tr['evidence']);ds=sorted(ds,key=lambda d:(d['priority'],d['sid']));Q={d['sid']:0 for d in ds};Dpre={}
   assert len(ds)==len(v['projection']['trace'])
   for d,t in zip(ds,v['projection']['trace']):
    assert d['sid']==t['sid'];Q[d['sid']]=t['q']
    if t['q'] and cm[(d['sid'],day)]['kind']=='RESET_SEEK_REPAIR':
     standalone={sid:0 for sid in Q};standalone[d['sid']]=t['q'];x=B.evaluate(s,ds,standalone,{})
     y=B.evaluate(s,ds,Q,{})
     pv.append(dict(day=day,sid=d['sid'],q=t['q'],original_max=d['max_q'],original_D_before=Dpre.copy(),original_D_after=t.get('D',Dpre).copy(),
        standalone_no_sale=brief_validation(x,d['sid']),fixed_original_Q_prefix_no_sale=brief_validation(y,d['sid']),
        source_snapshot_sha256=J.digest(s),prior_Q={sid:q for sid,q in Q.items() if sid!=d['sid'] and q},historical_cash_not_claimed_exogenous=True))
    if 'D'in t:Dpre=dict(t['D'])
   assert Q==v['projection']['Q'] and Dpre==v['projection']['D']
  output=[]
  prices=defaultdict(list)
  for z in facts:
   if z['day']>='2025-07-01':prices[z['sid']].append(dict(day=z['day'],adjusted_close=z['close']))
  for e in cohort:
   sid=e['sid'];day=e['day'];d=e['C_demand'];cls=cm[(sid,day)];associated=lm.get((sid,day),[]);further=[z for z in prices[sid] if z['day']>day]
   output.append(dict(sid=sid,name=meta[sid]['name'],day=day,canonical_id=e['canonical']['receipt_id'],canonical=e['canonical'],classification=cls,
    Q=e['stock_Q'],I_structure=e.get('source_structure'),original_core_qualified=e['original_core_qualified'],G_scope=e['G_scope'],S_scope=e['S_scope'],
    original_E0_episode_id=e['canonical']['original_E0_episode_id'],stage_class=e['stage_class'],C_demand=d,C_plan_q=e['C_Q'],
    original_max_gross=D(d['max_q'])*D(d['mark'])*(1+J.SLIP) if d else Z,planned_gross=D(e['C_Q'] or 0)*D(d['mark'])*(1+J.SLIP) if d else Z,
    C_orders=e['C_actual_reserved_orders'],T_orders=e['T_actual_reserved_orders'],actual_layers=associated,
    same_window_later_price_path=further,followup_observations=len(further),terminal_window_censored=True,
    terminal_same_source_return=(D(str(further[-1]['adjusted_close']))/D(str(cls['signal_close']))-1) if further else None,
    variable_followup_not_equal_horizon_label=True))
  summaries[arm]=aggregate(output);all_events[arm]=output;previews[arm]=pv
  # Positive controls are posthoc logic counterexamples, selected by fixed contribution ordering,
  # with a repair, observed earlier UP receipt and later UP receipt, all within July.
  candidates=[]
  stockby={z['sid']:z for z in stocks[arm]}
  for e in output:
   sid=e['sid'];day=e['day'];same=[z for z in output if z['sid']==sid];st=stockby.get(sid)
   prior_up=[z['day']for z in same if z['day']<day and z['classification']['kind']=='UP_CONTINUATION'];later_up=[z['day']for z in same if z['day']>day and z['classification']['kind']=='UP_CONTINUATION']
   if e['classification']['kind']=='RESET_SEEK_REPAIR' and st and D(st['contribution'])>0 and prior_up and later_up:
    candidates.append(dict(sid=sid,name=e['name'],repair_day=day,actual_month_stock=st,prior_UP_days=prior_up,later_UP_days=later_up,
      repair_event=e,all_stock_receipt_events=same,selection='posthoc positive logic control, not independent validation'))
  candidates.sort(key=lambda z:(-D(z['actual_month_stock']['contribution']),z['sid'],z['repair_day']));control_candidates[arm]=candidates
  assert before==J.digest(M.C.prefix_view(r)) and sha(path)==ledger_paths[str(path)]
  assigned={z['layer']for e in output for z in e['actual_layers']};assert len(assigned)==sum(len(e['actual_layers'])for e in output)
  checks[arm]=dict(canonical_receipts=len(output),source_CP_receipts_in_month=sum(z['receipt']and z['day']>='2025-07-01' for z in cp),
    actual_layer_total=len(layers[arm]),layers_with_same_signal_fresh_receipt=len(assigned),core_only_or_nonfresh_layers=[z for z in layers[arm]if z['layer']not in assigned],
    native_CP_negative_reset_count=sum(z['reset_reason']=='E0_down_reset'and z['day']>='2025-07-01' for z in cp),
    negative_reset_with_I_still_valid=sum(z['reset_reason']=='E0_down_reset'and z['day']>='2025-07-01'and z['e0_valid']for z in cp),
    original_complete_state_hash_unchanged=before,financial_events=0)
  print('ARM_DONE',arm,{k:v['events']for k,v in summaries[arm].items()},'positive-controls',len(candidates),flush=True)
 save('EVENTS.json',all_events);save('SUMMARY.json',summaries);save('NO_OPPORTUNITY_SALE_PREVIEWS.json',previews);save('POSITIVE_CONTROL_CANDIDATES.json',control_candidates);save('CHECKS.json',checks)
 save('SOURCE_FREEZE.json',dict(contract_sha256=sha(HERE/'CONTRACT.txt'),analysis_sha256=sha(__file__),CP_source_sha256=sha('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py'),
  checkpoint_SHA256=ledger_paths,original_policy_guard=True,financial_events=0,seconds=time.perf_counter()-start))
 print('READONLY_DONE',round(time.perf_counter()-start,3),flush=True)

if __name__=='__main__':
 try:main()
 except BaseException as e:
  import traceback
  save('ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),financial_events=0));raise
