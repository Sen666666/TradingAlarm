"""Independent whole-order nominal entry-reference arithmetic; no strategy engine."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import pandas as pd
import json
import audit_pvr_saved as I
getcontext().prec=60
O=I.TASK/'loss_correction/entry_risk_commitment_review';Z=D(0);FR={};SLIP=D('.0005')
def n(v):return D(str(v))
def eq(a,b):assert abs(n(a)-n(b))<D('.00000001'),(a,b)
def main():
 binding=I.read(O/'SOURCE_BINDING.json')
 for p,h in binding['sources'].items():assert I.sha(p)==h,p
 assert I.sha(I.TASK/'loss_correction/analyze_entry_risk_commitment.py')==binding['script_sha256']
 for name in ['PROTOCOL_FREEZE.json','INPUT_FREEZE.json']:
  for p,h in I.read(O/name)['sources'].items():assert I.sha(p)==h,p
 base=I.TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024';results=I.read(O/'RESULTS.json');answer={}
 for ref,root in [('2022_2024',base/'no60/run-2024/pair'),('strong',I.TASK/'pvr_pool_feasibility/runs/2025_26/pair')]:
  ee=I.read(O/(ref+'_ENTRIES.json'));oo=I.read(O/(ref+'_ORDERS.json'));bb=I.read(root/'B.json.gz');buys={t['layer']:t for t in bb['trades']if t['side']=='buy'};jr={x['layer']:x for x in bb['journal']if x['kind']=='real_buy_fill'};raw={x['id']:x for x in bb['layers']}
  decisions={(d['at'],i['sid'],i['role']):(d,i)for d in bb['decisions']for i in d['intents']};old={x['layer']:x for x in I.read(I.TASK/'risk_constraints/ma63_information_diagnostic_v1'/(ref+'_ENTRIES.json'))};assert len(ee)==len(buys)==len(jr)==len(old)
  groups=defaultdict(list);orders=defaultdict(list);whycount=Counter();corechanges=0
  for x in ee:
   lid=x['layer'];t=buys[lid];j=jr[lid];sid=x['sid'];assert x['budget_order']==j['budget_order'];stamp=j['budget_order'].split('|')[1];assert pd.Timestamp(stamp)==pd.Timestamp(x['decision_at'])<pd.Timestamp(t['at'])
   d,i=decisions[x['decision_at'],sid,x['role']];assert x['frozen_intent']==i and i.get('CP1_id')==x['receipt'];assert x['signal_at']==j['signal_at']
   if sid not in FR:
    p=I.SM[sid]['refs']['facts'];assert I.sha(p)==I.SM[sid]['output_sha256'][p];FR[sid]=pd.read_parquet(p,columns=['raw_close','close','factor','segment_id'])
   f=FR[sid];rd=f.loc[pd.Timestamp(x['decision_at'][:10])];rf=f.loc[pd.Timestamp(t['at'][:10])];fd=n(rd.factor);ff=n(rf.factor);assert fd>0 and ff>0
   eq(n(rd.raw_close)*fd,rd.close);eq(t['floor'],i['floor']);floor=n(t['floor'])/ff;p=n(t['price']);q=D(t['shares']);refp=n(rd.raw_close)*fd/ff*(1+SLIP);assert p==n(t['raw_open'])*(1+SLIP)
   actual=q*max(Z,p-floor);fixedq=q*max(Z,refp-floor);plan=D(i['cap'])*max(Z,refp-floor)
   for k,v in [('initial_raw_floor',floor),('known_reference_price_in_fill_raw_unit',refp),('actual_initial_nominal_risk',actual),('fixed_actual_quantity_reference_risk',fixedq),('fixed_quantity_gap_risk_increment',actual-fixedq),('frozen_order_full_plan_reference_risk',plan)]:eq(x[k],v)
   why=[]
   if fd!=ff:why.append('company_action_factor_changed_between_decision_and_fill')
   if rd.segment_id!=rf.segment_id:why.append('price_source_segment_changed')
   if plan<=0:why.append('nonpositive_frozen_plan_reference_nominal_risk')
   assert x['reference_unknown_reasons']==why;whycount.update(why)
   if x['role']=='core'and why:corechanges+=1
   for k in ['cost','net','qty','value','role','pool_at_fill','action','watch_epoch']:assert x[k]==old[lid][k],(ref,lid,k)
   orders[x['budget_order']].append(x)
  om={o['budget_order']:o for o in oo};assert set(om)==set(orders)
  for oid,ll in orders.items():
   a=ll[0];o=om[oid];q=sum(x['actual_fill_quantity']for x in ll);actual=sum((n(x['actual_initial_nominal_risk'])for x in ll),Z);plan=n(a['frozen_order_full_plan_reference_risk']);why=sorted({s for x in ll for s in x['reference_unknown_reasons']})
   assert sorted(o['layer_ids'])==sorted(x['layer']for x in ll)and o['actual_total_filled_shares']==q and o['frozen_cap']==a['frozen_intent']['cap'];eq(o['planned_reference_nominal_risk'],plan);eq(o['actual_initial_nominal_risk'],actual)
   label='CORE_existing_separate_risk_contract'if a['role']=='core'else'MOBILE_reference_unknown'if why else'MOBILE_actual_nominal_above_frozen_full_plan'if actual>plan else'MOBILE_actual_nominal_within_frozen_full_plan'
   assert o['class_label']==label
   if not why:assert q<=o['frozen_cap']
   excess=max(Z,actual-plan)if a['role']=='mobile'and not why else Z;eq(excess,o['nominal_excess'])
   for x in ll:assert x['risk_reference_class']==label;eq(x['order_excess_allocated'],excess*D(x['actual_fill_quantity'])/D(q));groups[label].append(x)
  for label,g in results[ref]['groups'].items():
   ll=groups[label];assert g['fills']==len(ll);eq(g['actual_buy_cash'],sum((n(x['cost'])for x in ll),Z));eq(g['net_lifetime'],sum((n(x['net'])for x in ll),Z));eq(g['risk_excess_over_frozen_full_plan_allocated_to_fills'],sum((n(x['order_excess_allocated'])for x in ll),Z))
  eq(sum((n(x['net'])for x in ee),Z),n(bb['ending_NAV'])-1000000)
  post=[x for x in ee if ref=='2022_2024'and x['opened'][:10]>'2024-10-08'];postgroups={k:{'fills':len([x for x in post if x['risk_reference_class']==k]),'net':sum((n(x['net'])for x in post if x['risk_reference_class']==k),Z)}for k in groups}
  tails=I.read(O/(ref+'_ORIGINAL_FIXED_TAIL_CONTROLS.json'));frozen=I.read(I.TASK/'risk_constraints/ma63_information_diagnostic_v1/ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json')['members'][ref];assert {x['original']['layer']for x in tails}=={x['layer']for x in frozen}
  bykey=defaultdict(list)
  for x in ee:bykey[x['sid'],x['budget_order'],x['role'],x['receipt']].append(x)
  hit=Counter()
  for t in tails:
   a=t['original'];ll=bykey[a['sid'],a['budget_order'],a['role'],a['receipt']]
   if a['role']=='core':ll=[x for x in ll if x['watch_epoch']==a['watch_epoch']]
   assert {x['layer']for x in t['matched_No60']}=={x['layer']for x in ll};hit.update(x['risk_reference_class']for x in ll)
  phase=I.read(O/(ref+'_PHASE_WEALTH.json'));ds=I.rows(root/'daily.jsonl.gz');dayindex={x['at'][:10]:i for i,x in enumerate(ds)}
  for key in sorted({x['phase']for x in phase}):
   pp=[x for x in phase if x['phase']==key];lo=pp[0]['lo'];hi=pp[0]['hi'];dd=[x for x in ds if lo<=x['at'][:10]<=hi]
   if dd:
    j=dayindex[dd[0]['at'][:10]];begin=n(ds[j-1]['nav'])if j else D(1000000);eq(sum((n(x['actual_phase_wealth'])for x in pp),Z),n(dd[-1]['nav'])-begin)
  above=results[ref]['groups']['MOBILE_actual_nominal_above_frozen_full_plan'];answer[ref]={'passed':True,'all_actual_fills':len(ee),'all_budget_orders':len(oo),'partial_fill_multi_layer_orders':sum(len(v)>1 for v in orders.values()),'mobile_above_full_cap_plan':above,'all_unknown_reasons_including_core':dict(whycount),'core_rows_with_changes_retained_as_control':corechanges,'postOct8_303':postgroups,'full_original_tail_members':len(tails),'matched_tail_class_counts':dict(hit)}
 out={'status':'PASS_DEFINITION_COUNTS_MONEY_WITH_SCOPE; CONDITIONAL_SUPPORT_FOR_ONE_BOUNDED_TECHNICAL_PROTOTYPE_ONLY','results':answer,'source_SHA_checks':len(binding['sources']),'reviewer_source_SHA256':I.sha(__file__),'reviewer_account_events':0,'scope':'All3436actual rows, originaldecision/journal/initialtradefloor/factor/5bp, wholecap and groupedorder quantity denominators independently checked. No core.25pct contract transfer to mobile. Same frozen money/first-add-reentry/role/fixedtail keys preserved; primary net groups and allphase totalNAV bridges independently checked. Group-specific phase money reader source-reviewed/reused, not another independent pergroup daily replay. Company-action detection currently factor/source-change based; broader action-interval completeness still requires explicit saved-action crosscheck or narrowed wording. Nominal risk distances are not allin protection loss bounds or simultaneous account risk. Strong187above-reference layers make366484.03, a material counterexample. No assumed deletion/quantity-scaled PnL or new account benefit.'}
 (I.HERE/'ENTRY_RISK_COMMITMENT_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in out.items()if k!='results'},indent=2));print(json.dumps({r:{k:v for k,v in a.items()if k!='mobile_above_full_cap_plan'}for r,a in answer.items()},indent=2,default=str))
if __name__=='__main__':main()
