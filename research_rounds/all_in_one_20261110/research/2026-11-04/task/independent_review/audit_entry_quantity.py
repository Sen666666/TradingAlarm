"""Independent closed-form legal quantity audit of a fixed-price screen only."""
from pathlib import Path
from decimal import Decimal as D,localcontext
from fractions import Fraction
from collections import defaultdict,Counter
import json,hashlib,statistics
HERE=Path(__file__).resolve().parent;T=HERE.parent;O=T/'ar6_native_feasibility/MOBILE_OPEN_RISK_QUANTITY_V1';Q=T/'loss_correction/entry_risk_commitment_review';M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eq(a,b):assert abs(D(str(a))-D(str(b)))<D('1e-8'),(a,b)
def main():
 freeze=read(O/'FREEZE.json')
 for p,h in freeze['sources'].items():assert sha(p)==h,p
 done=read(O/'DONE.json');assert done['orders']==3436 and done['sources_post_exact']and done['new_account_objects']==done['new_order_or_fill_events']==done['new_PnL_NAV']==0
 rules=read(M/'pvr-act-comparison-20261027/execution-rules-v2.json');summary=read(O/'SUMMARY.json');answer={};all_count=0
 for ref in ['2022_2024','strong']:
  rows=read(O/(ref+'_ROWS.json'));ee={x['layer']:x for x in read(Q/(ref+'_ENTRIES.json'))};assert len(rows)==len(ee);stats=Counter();gross=defaultdict(lambda:D(0));risk=defaultdict(lambda:D(0));changed=defaultdict(list)
  for r in rows:
   e=ee[r['layer']];assert r['budget_order']==e['budget_order']and r['q0_actual']==e['actual_fill_quantity']and r['original_plan_cap_S']==e['frozen_intent']['cap'];day=r['opened'][:10]
   vv=[v for v in rules['quantity_versions'][r['sid']]if v['from']<=day and(not v.get('to')or day<v['to'])];assert len(vv)==1;v=vv[0]['rule'];assert (r['rule_id'],r['buy_minimum'],r['buy_step'],r['fill_step'])==(v['rule_id'],v['buy_minimum'],v['buy_step'],v['fill_step'])
   assert r['dated_rule_source']==vv[0]['source_id']
   with localcontext()as c:
    c.prec=28
    p=D(e['actual_execution_price']);floor=D(e['frozen_initial_adjusted_floor'])/D(e['fill_factor']);refp=D(e['signal_close_raw'])*D('1.0005');fd=D(e['signal_factor']);R=D(e['frozen_intent']['cap'])*max(D(0),refp-D(e['frozen_initial_adjusted_floor'])/fd);width=p-floor
    assert str(R)==r['original_plan_reference_nominal_R_CNY'];assert p==D(r['execution_price'])and floor==D(r['floor_raw'])
    q0=r['q0_actual'];minimum=v['buy_minimum'];step=v['buy_step'];base=0 if q0<minimum else minimum+((q0-minimum)//step)*step
    if e['role']=='core':expected=q0;assert r['status']=='CORE_UNCHANGED'
    elif e['reference_unknown_reasons']:expected=0;assert r['status']=='UNKNOWN_NO_NEW_MOBILE'
    else:
     assert R>0 and width>0 and r['status']=='KNOWN_PRIMARY_FIXED_PRICE'
     cap=min(q0,int(Fraction(R)//Fraction(width)));expected=0 if cap<minimum else minimum+((cap-minimum)//step)*step
     # The frozen producer predicate multiplies under Decimal28. Exact rational
     # division can sit one lattice step below a rounded-equal monetary boundary.
     # Check that immediate neighbor under the original arithmetic, not a new EPS.
     initial=expected;candidate=minimum if not expected else expected+step
     while candidate<=q0 and D(candidate)*width<=R:
      expected=candidate;candidate+=step
     if expected!=initial:
      stats['Decimal28_boundary_neighbor_corrections']+=1
      assert expected-initial<=max(minimum,step)
     assert r['qbase_legal_new_order']==base
     if expected:assert D(expected)*width<=R
     if expected+step<=q0 and expected>=minimum:assert D(expected+step)*width>R
    assert r['qnew']==expected,(ref,r['layer'],r['qnew'],expected)
    eq(r['fixed_price_gross_delta'],D(q0-expected)*p);eq(r['new_fixed_price_gross'],D(expected)*p);eq(r['new_fixed_price_nominal_risk'],D(expected)*max(D(0),width));assert 0<=expected<=q0
   assert r['original_lifetime_net_ASSOCIATION_ONLY']==e['net']and r['original_buy_fee_UNSCALED']==e['buy_fee']
   if e['role']=='core':assert expected==q0
   stats['orders']+=1;stats['changed']+=expected<q0;stats['unknown']+=r['status']=='UNKNOWN_NO_NEW_MOBILE';stats['known_shrunk']+=r['known_risk_reduced'];stats['known_minunit_disappeared']+=r['known_minunit_disappears'];stats['original_legal_projection_mismatch']+=base!=q0
  # Independent aggregate gross/risk/association sums for every published group.
  def subset(g):
   if g=='ALL':return rows
   if g=='CORE':return [r for r in rows if r['role']=='core']
   if g=='MOBILE_KNOWN':return [r for r in rows if r['status']=='KNOWN_PRIMARY_FIXED_PRICE']
   if g=='MOBILE_UNKNOWN':return [r for r in rows if r['status']=='UNKNOWN_NO_NEW_MOBILE']
   if g=='FIXED_ORIGINAL_PVR_TAIL_EXACT_MATCH':return [r for r in rows if r['fixed_original_tail_match']]
   if g=='2024postOct8_303':return [r for r in rows if r['opened'][:10]>'2024-10-08']
   return None
  for g,s in summary[ref].items():
   rr=subset(g)
   if rr is None:continue
   assert s['orders']==len(rr)and s['quantity_reduced']==sum(x['qnew']<x['q0_actual']for x in rr)
   assert s['known_risk_reduced']==sum(x['known_risk_reduced']for x in rr)and s['known_minunit_disappears']==sum(x['known_minunit_disappears']for x in rr)
   for field in ['fixed_price_gross_delta','fixed_price_nominal_risk_delta','known_risk_only_gross_delta']:eq(s[field],sum((D(x[field])for x in rr if x[field]is not None),D(0)))
   eq(s['original_net_of_changed_orders_ASSOCIATION_ONLY'],sum((D(x['original_lifetime_net_ASSOCIATION_ONLY'])for x in rr if x['qnew']<x['q0_actual']),D(0)))
  tails=read(Q/(ref+'_ORIGINAL_FIXED_TAIL_CONTROLS.json'));ids={m['layer']for x in tails for m in x['matched_No60']};assert ids=={r['layer']for r in rows if r['fixed_original_tail_match']}
  answer[ref]={'passed':True,'counts':dict(stats),'known':summary[ref]['MOBILE_KNOWN'],'unknown':summary[ref]['MOBILE_UNKNOWN'],'fixed_original_tail':summary[ref]['FIXED_ORIGINAL_PVR_TAIL_EXACT_MATCH'],'postOct8':summary[ref].get('2024postOct8_303')};all_count+=len(rows)
 assert all_count==3436;out={'status':'PASS_PURE_QUANTITY_SCREEN_ONLY','results':answer,'source_SHA_checks':len(freeze['sources']),'independent_maximum_method':'Closed-form rational R/width bound and dated minimum/step lattice, then immediate-neighbor check under frozen Decimal28 rounded multiplication; original LR binary search not invoked. No new epsilon added.','reviewer_readonly_attempt':'First independent rational-only maximality assertion exposed rounded-equal Decimal28 boundary; reviewer corrected neighbor evaluation to match frozen arithmetic. Producer source/result unchanged.','reviewer_account_events':0,'reviewer_source_SHA256':sha(__file__),'scope':'All3436actual orders/initialR wholecap vsqactual searchcap, datedrules, floor/5bp units and exact maximalq independently checked. Core unchanged;13unknown separately zero; no legal-projection artifacts in observed mother. Core/fixedtail/303/known/unknown aggregate gross/risk/associatednet checked. Original fee/net unscaled associations only. No account/route/reallocation/newNAV/PnL/partialfill runtime/corporateaction conversion. Per latest root directive no native expansion is supported now; fixed-path amount sensitivity and R0 dedup must determine priority first.'}
 (HERE/'ENTRY_RISK_PURE_QUANTITY_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in out.items()if k!='results'},indent=2));print(json.dumps({r:a['counts']for r,a in answer.items()},indent=2))
if __name__=='__main__':main()
