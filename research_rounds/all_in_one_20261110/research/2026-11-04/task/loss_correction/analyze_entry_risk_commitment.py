"""Frozen financial entry-risk diagnostic; zero account/new signal calls."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import importlib.util,json,gzip,hashlib
import pandas as pd
P=Path(__file__).resolve().parent;O=P/'entry_risk_commitment_review';ROOT=P.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');Z=D(0);SLIP=D('.0005');SRC={}
s=importlib.util.spec_from_file_location('existing_pure_phase_ledger_gap',ROOT/'risk_constraints/analyze_ma63_information.py');M=importlib.util.module_from_spec(s);s.loader.exec_module(M)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def n(x):return D(str(x))
def agg(ee):
 r=M.agg(ee);r.update(actual_initial_nominal_risk=sum((n(x['actual_initial_nominal_risk']) for x in ee),Z),fixed_actual_quantity_reference_risk=sum((n(x['fixed_actual_quantity_reference_risk']) for x in ee),Z),fixed_quantity_gap_risk_increment=sum((n(x['fixed_quantity_gap_risk_increment']) for x in ee),Z),positive_fixed_quantity_gap_risk_increment=sum((max(Z,n(x['fixed_quantity_gap_risk_increment'])) for x in ee),Z),risk_excess_over_frozen_full_plan_allocated_to_fills=sum((n(x['order_excess_allocated']) for x in ee),Z));return r
def main():
 for fn in ['PROTOCOL_FREEZE.json','INPUT_FREEZE.json']:
  for p,h in read(O/fn)['sources'].items():assert sha(p)==h,('frozen input changed',p)
 sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};M.SM=sm;M.IM={};final={};fixed=read(ROOT/'risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json');allframes={}
 for ref,root in [('2022_2024',ROOT/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024'),('strong',ROOT/'pvr_pool_feasibility/runs/2025_26')]:
  ee=read(ROOT/'risk_constraints/ma63_information_diagnostic_v1'/(ref+'_ENTRIES.json'));b=M.book(root/'pair/B.json.gz');ds=M.rows(root/'pair/daily.jsonl.gz');assert len(ee)==(2265 if ref=='2022_2024' else 1171)
  buys={t['layer']:t for t in b['trades'] if t['side']=='buy'};intent={(pd.Timestamp(d['at']).isoformat(),i['sid'],i['role']):(d,i) for d in b['decisions'] for i in d['intents']};ordergroups=defaultdict(list)
  for x in ee:
   sid=x['sid'];dt=pd.Timestamp(x['decision_at']);ft=pd.Timestamp(x['opened']);assert dt<ft;t=buys[x['layer']];d,i=intent[dt.isoformat(),sid,x['role']];assert i['CP1_id']==x['receipt'];m=sm[sid];fp=Path(m['refs']['facts'])
   if sid not in allframes:
    assert sha(fp)==m['output_sha256'][str(fp)];SRC[str(fp)]=sha(fp);allframes[sid]=pd.read_parquet(fp,columns=['raw_close','close','factor','segment_id'])
   f=allframes[sid];rd=f.loc[pd.Timestamp(dt.date())];rf=f.loc[pd.Timestamp(ft.date())];fd,ff=n(rd.factor),n(rf.factor);assert abs(n(rd.raw_close)*fd-n(rd.close))<D('.000001');p=n(t['price']);q=D(t['shares']);assert p==n(t['raw_open'])*(1+SLIP);floor=n(t['floor'])/ff;refp=n(rd.raw_close)*fd/ff*(1+SLIP);A=q*max(Z,p-floor);Q=q*max(Z,refp-floor);plan=D(i['cap'])*max(Z,refp-floor);why=[]
   if fd!=ff:why.append('company_action_factor_changed_between_decision_and_fill')
   if rd.segment_id!=rf.segment_id:why.append('price_source_segment_changed')
   if plan<=0:why.append('nonpositive_frozen_plan_reference_nominal_risk')
   x.update(original_inclusive_MA_class=x['MA63_class'],decision_NAV=d['nav'],frozen_intent=i,signal_close_raw=n(rd.raw_close),signal_factor=fd,fill_factor=ff,signal_source_segment=int(rd.segment_id),fill_source_segment=int(rf.segment_id),frozen_initial_adjusted_floor=t['floor'],initial_raw_floor=floor,actual_fill_quantity=int(q),actual_raw_open=t['raw_open'],actual_execution_price=p,known_reference_price_in_fill_raw_unit=refp,actual_initial_nominal_risk=A,fixed_actual_quantity_reference_risk=Q,fixed_quantity_gap_risk_increment=A-Q,actual_initial_risk_pct_decisionNAV=A/n(d['nav'])*100,frozen_order_full_plan_reference_risk=plan,frozen_plan_reference_risk_pct_decisionNAV=plan/n(d['nav'])*100,actual_buycash_pct_decisionNAV=n(x['cost'])/n(d['nav'])*100,entry_gap_pct=(p/refp-1)*100,reference_unknown_reasons=why,existing_core_allin_risk_budget=i.get('risk_budget'),order_excess_allocated=Z)
   ordergroups[x['budget_order']].append(x)
  orders=[]
  for oid,ll in ordergroups.items():
   a=ll[0];assert len({(x['frozen_intent']['cap'],str(x['frozen_order_full_plan_reference_risk'])) for x in ll})==1;A=sum((x['actual_initial_nominal_risk'] for x in ll),Z);plan=a['frozen_order_full_plan_reference_risk'];why=sorted({r for x in ll for r in x['reference_unknown_reasons']});q=sum(x['actual_fill_quantity'] for x in ll);assert why or q<=a['frozen_intent']['cap']
   if a['role']=='core':label='CORE_existing_separate_risk_contract'
   elif why:label='MOBILE_reference_unknown'
   elif A>plan:label='MOBILE_actual_nominal_above_frozen_full_plan'
   else:label='MOBILE_actual_nominal_within_frozen_full_plan'
   excess=max(Z,A-plan) if a['role']=='mobile' and not why else Z
   for x in ll:x['risk_reference_class']=label;x['order_excess_allocated']=excess*D(x['actual_fill_quantity'])/D(q);x['MA63_class']=label
   orders.append(dict(budget_order=oid,sid=a['sid'],role=a['role'],decision_at=a['decision_at'],layer_ids=[x['layer'] for x in ll],frozen_cap=a['frozen_intent']['cap'],actual_total_filled_shares=q,original_nominal_budget=a['frozen_intent']['budget'],original_decision_NAV=a['decision_NAV'],planned_reference_nominal_risk=plan,actual_initial_nominal_risk=A,nominal_excess=excess,class_label=label,unknown_reasons=why))
  save(ref+'_ENTRIES.json',ee);save(ref+'_ORDERS.json',orders)
  # Quick primary money/scale receipt before the reused full phase ledger.
  groups={k:agg([x for x in ee if x['risk_reference_class']==k]) for k in sorted({x['risk_reference_class'] for x in ee})};save(ref+'_QUICK_SCALE.json',dict(groups=groups,orders_byclass=dict(Counter(x['class_label'] for x in orders)),fixed_quantity_gappositive=agg([x for x in ee if x['fixed_quantity_gap_risk_increment']>0]),primary_is_full_frozen_plan_not_actual_quantity_reference=True))
  print('QUICK_SCALE',ref,json.dumps(groups,default=str,ensure_ascii=False),flush=True)
  # Already audited pure saved ledger, changing grouping labels only. No MA,
  # state machine, signal or account initialization function is invoked.
  enriched,history,deployment=M.ledger(ref,b,ds,ee);phases=[]
  for phase,lo,hi in M.phase_specs(ref,ds):
   for label in groups:
    rr=[r for r in history if lo<=r['day']<=hi and r['key'][0]==label];phases.append(dict(phase=phase,lo=lo,hi=hi,risk_reference_class=label,actual_phase_wealth=sum((r['wealth'] for r in rr),Z),real_change=sum((r['real_change'] for r in rr),Z),unreal_change=sum((r['unreal_change'] for r in rr),Z),AR_change=sum((r['div_change'] for r in rr),Z),phase_buycash=sum((r['buycash'] for r in rr),Z),phase_fees=sum((r['fees'] for r in rr),Z)))
  crosses={}
  for key in ['action','role','pool_at_fill']:
   crosses[key]=[dict(risk_reference_class=k,dimension=v,**agg([x for x in ee if x['risk_reference_class']==k and x[key]==v])) for k in groups for v in sorted({x[key] for x in ee})]
  bykey=defaultdict(list)
  for x in ee:bykey[(x['sid'],x['budget_order'],x['role'],x['receipt'])].append(x)
  tails=[]
  for old in fixed['members'][ref]:
   matched=bykey[(old['sid'],old['budget_order'],old['role'],old['receipt'])]
   if old['role']=='core':matched=[x for x in matched if x['watch_epoch']==old['watch_epoch']]
   tails.append(dict(original=old,matched_No60=[{k:x[k] for k in ['layer','risk_reference_class','entry_gap_pct','actual_initial_nominal_risk','frozen_order_full_plan_reference_risk','net','qty','reference_unknown_reasons']} for x in matched],same_stock_other_fill_layers=[x['layer'] for x in ee if x['sid']==old['sid'] and x not in matched]))
  save(ref+'_PHASE_WEALTH.json',phases);save(ref+'_CROSSES.json',crosses);save(ref+'_ORIGINAL_FIXED_TAIL_CONTROLS.json',tails)
  final[ref]=dict(groups=groups,crosses=crosses,financial_NAV_check=sum((n(x['net']) for x in ee),Z),old_fixed_tail_members=len(tails),exact_matched_fixed_tail_members=sum(bool(t['matched_No60']) for t in tails),grouping_does_not_simulate_removed_or_resized_orders=True)
 save('RESULTS.json',final);SRC.update(M.SRC)
 for sid in M.C.A.frames:
  fp=Path(M.C.A.SM[sid]['refs']['facts']);assert sha(fp)==M.C.A.SM[sid]['output_sha256'][str(fp)];SRC[str(fp)]=sha(fp)
 save('SOURCE_BINDING.json',dict(sources=SRC,script_sha256=sha(__file__),account_events=0,new_signals=0,shared_financial_reader=str(Path(M.__file__)),shared_financial_reader_sha256=sha(M.__file__),nominal_risk_not_allin_loss_bound=True))
 print('ENTRY_RISK_DIAGNOSTIC_COMPLETE',flush=True)
if __name__=='__main__':main()
