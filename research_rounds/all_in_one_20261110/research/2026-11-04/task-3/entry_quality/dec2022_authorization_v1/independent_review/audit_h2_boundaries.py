"""Thin phase/readiness/role and pointwise permission annex for audited DONE paths."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D
import json,gzip,hashlib
O=Path(__file__).resolve().parent;P=O.parent;R=P.parent/'trend_exit_controls_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
results={}
for arm in ['R_ONLY','P_ONLY','JOINT']:
 for window in ['2022_2024','strong']:
  receipt=O/(arm+'_'+window+'_ACCOUNT_AUDIT.json')
  if not receipt.exists():continue
  audit=read(receipt)
  for p,h in audit['source_sha256'].items():assert sha(p)==h
  out=P/'runs'/arm/window;book=read(out/'pair/B.json.gz');logs=read(out/'pair/mobile-authorization-policy.jsonl.gz');C=Counter();phase=defaultdict(Counter);examples={};denied={};returns=[]
  for z in logs:
   q=z['context'];p=z['phase'];de=z['decision'];phase[p]['rows']+=1;phase[p]['both_ready' if q['ready_R'] and q['ready_P'] else 'R_unknown_P_ready' if q['ready_P'] else 'R_ready_P_unknown' if q['ready_R'] else 'both_unknown']+=1;phase[p]['state_'+de['predicate_state']]+=1
   if de['predicate_state']=='UNKNOWN':
    assert not de['denies_mobile']
    if p=='held_mobile_after_native_hard_exits':assert z['added_mobile_exit_layer_ids']==[]
    else:assert z['allowed']
    examples.setdefault(p+'_unknown',z)
   if p=='held_mobile_after_native_hard_exits':
    assert not z['core_exit_ids_added'];C['no_CORE_overlay_exit_records']+=1
    assert not set(z['added_mobile_exit_layer_ids'])&set(z['prior_pending_layer_ids']);C['no_pending_ID_readded']+=1
    if z['prior_pending_layer_ids'] and not de['denies_mobile']:C['false_or_unknown_with_pending_kept']+=1;examples.setdefault('pending_retained_on_false_or_unknown',z)
    for lid in z['added_mobile_exit_layer_ids']:assert book['metadata'][str(lid)]['role']=='mobile'
   else:
    assert z['role']=='mobile'
    k=z['sid']
    if not z['allowed']:denied[k]=z
    elif k in denied:
     prior=denied.pop(k);assert prior['at']<z['at'] and prior['CP1_id']!=z['CP1_id'];returns.append(dict(sid=k,denied_at=prior['at'],denied_CP=prior['CP1_id'],later_allowed_at=z['at'],later_fresh_CP=z['CP1_id'],later_predicate=de['predicate_state']));C['pointwise_recovery_new_CP']+=1
  reasons=Counter(p['reason'] for t in book['trades'] if t['side']=='sell' for p in t['parts'] if book['metadata'][str(p['layer'])]['role']=='core');assert not any(x.startswith('mobile_authorization_') for x in reasons)
  baseline_receipt=R/'independent_review'/('BASELINE_'+window+'_ACCOUNT_AUDIT.json');baseline=read(baseline_receipt)
  results[arm+'|'+window]=dict(status='PASS_AUDITED_ACCOUNT_BOUNDARY_ANNEX',ending_NAV=audit['ending_NAV'],baseline_ending_NAV=baseline['ending_NAV'],exact_NAV_delta=str(D(audit['ending_NAV'])-D(baseline['ending_NAV'])),all_audit_checks=audit['checks'],checks=dict(C),phase_readiness={p:dict(c) for p,c in phase.items()},CORE_actual_sale_part_reasons=dict(reasons),CORE_count=sum(v['role']=='core' for v in book['metadata'].values()),first_recovery_examples=returns[:5],boundary_examples=examples,source_sha256={str(receipt):sha(receipt),str(baseline_receipt):sha(baseline_receipt),str(out/'pair/mobile-authorization-policy.jsonl.gz'):sha(out/'pair/mobile-authorization-policy.jsonl.gz')},limits=['Whole account delta is endogenous; no original-layer avoided-loss attribution.','CORE eligibility/exit implementation is unchanged; actual capital and ACT feedback can alter CORE quantities/timing.','Selected-factor UNKNOWN means absence of added restriction, not improvement. P_ONLY may legitimately act when R is unknown and P known.','A later allowed role is only permission at a genuinely fresh same-day original CP; it does not guarantee budget or actual funding.'])
(O/'H2_COMPLETED_BOUNDARY_ANNEX.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:{'NAV':v['ending_NAV'],'delta':v['exact_NAV_delta'],'phases':v['phase_readiness'],'checks':v['checks']} for k,v in results.items()},ensure_ascii=False,indent=2))
