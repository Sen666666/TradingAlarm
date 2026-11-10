"""Existing audited layer joins only. No export, model, new account or new factor."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,hashlib,csv,time,math
import numpy as np
O=Path(__file__).resolve().parent;Q=O.parents[1];S=Q/'structural_failure_v1';SRC={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def agg(rr):
 n=lambda r:D(r['net']);cost=sum((D(r['cost']) for r in rr),Z);pos=sum((max(Z,n(r)) for r in rr),Z);neg=sum((min(Z,n(r)) for r in rr),Z)
 return dict(layers=len(rr),stocks=len({r['sid'] for r in rr}),industries=len({r['sector'] for r in rr}),cost=cost,positive=pos,negative=neg,net=pos+neg,positive_layers=sum(n(r)>0 for r in rr),negative_layers=sum(n(r)<0 for r in rr),fees=sum((D(r['buy_fee'])+D(r['sell_fee']) for r in rr),Z),tail_layers=sum(n(r)/D(r['cost'])>=D('.3') for r in rr))
def group(rr,fn):
 g=defaultdict(list)
 for r in rr:g[str(fn(r))].append(r)
 return {k:agg(v) for k,v in sorted(g.items())}
def qtiles(rr,fn):
 vals=[float(fn(r)) for r in rr if fn(r) is not None and math.isfinite(float(fn(r)))]
 return dict(known=len(vals),unknown=len(rr)-len(vals),p10=None if not vals else float(np.quantile(vals,.1)),median=None if not vals else float(np.median(vals)),p90=None if not vals else float(np.quantile(vals,.9)))
def action(r):return {'first_actual_participation':'first','add_while_held':'add','add_to_existing_stock':'add','fresh_reentry_after_actual_flat':'reentry'}.get(r['action'],r['action'])
def compact(r):
 keys=['layer','sid','name','sector','industry','role','simple_action','decision_at','signal_at','opened','closed','cost','net','strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee','original_stock_state','G1_source_class','G1_up_reasons','industry_stage','industry_attempt','industry_auth_id','industry_new_receipt_now','industry_last_receipt_day','industry_last_receipt_age_observations','industry_authorization_same_as_prior_actual_buy_decision','new_industry_receipt_since_prior_actual_buy','CP_formation_start_exclusive','CP_candidate','CP_delta_frontier','CP_displacement','CP_credit','CP_used_scale','CP_anchor_on_or_after_prior_actual_buy_fill','I_buy_now','CP_new_unconsumed_frontier','I_CP_same_confirmation_CLOSE','signal_differs_from_actual_decision','actual_initial_risk_pct_decisionNAV','actual_buycash_pct_decisionNAV','actual_initial_nominal_risk','frozen_order_full_plan_reference_risk','entry_gap_pct','direction_snapshot','divergence','request_clock','ratchet']
 z={k:r[k] for k in keys};z['PVR_score']=r['frozen_intent']['PVR_score'];z['held_close_observations']=r['holding']['held_close_observations'];z['actual_exit_class']=r['holding']['actual_exit_class'];z['actual_sale_parts']=r['holding']['actual_sale_parts'];z['source_layer_join_key']=r['layer'];return z
start=time.monotonic();rows={};features={}
for w in ['2022_2024','strong']:
 state=read(S/'state_semantics'/(w+'_ROWS.json'));holding={r['layer']:r for r in read(Q/'entry_exit_scale/holding_exit'/(w+'_LAYERS.json'))};request={r['layer']:r for r in read(Q/'entry_exit_scale/holding_exit'/(w+'_REQUEST_CLOCK_JOIN.json'))};ratchet={r['layer']:r for r in read(Q/'entry_exit_scale/mechanism_review'/(w+'_ACTUAL_CP_REQUEST_RATCHET_JOIN.json'))};scale={r['layer']:r for r in read(Q/'entry_exit_scale/mechanism_review'/(w+'_ACTUAL_ENTRY_SCALE_JOIN.json'))};direction={r['layer']:r for r in read(Q/'direction_divergence'/(w+'_ROWS.json'))}
 rr=[]
 for r in state:
  lid=r['layer'];h=holding[lid];d=direction[lid];assert r['sid']==h['sid']==d['sid'];assert D(r['net'])==D(h['net'])==D(d['net']);x=dict(r);x['holding']=h;x['request_clock']=request[lid];x['ratchet']=ratchet[lid];x['scale']=scale[lid];x['direction_snapshot']=d['direction_snapshot'];x['divergence']=d['divergence'];x['direction_unknown']=d['unknown'];x['simple_action']=action(r)
  reasons=[z for z in r['G1_up_reasons'] if z]
  x['G1_source_class']='frontier_only' if reasons==['new_price_frontier_in_confirmed_up_structure'] else 'other_new_source' if reasons else 'no_current_G1_new_source'
  x['signal_to_fill_calendar_days']=(__import__('datetime').date.fromisoformat(r['opened'][:10])-__import__('datetime').date.fromisoformat(r['signal_at'][:10])).days
  x['receipt_confirmation_to_actual_decision_calendar_days']=(__import__('datetime').date.fromisoformat(r['decision_at'][:10])-__import__('datetime').date.fromisoformat(r['signal_at'][:10])).days
  rr.append(x)
 rows[w]=rr
cohorts=dict(post303=[r for r in rows['2022_2024'] if r['opened'][:10]>'2024-10-08'],preOct8_1962=[r for r in rows['2022_2024'] if r['opened'][:10]<='2024-10-08'],strong_all=rows['strong'],strong_tail123=[r for r in rows['strong'] if D(r['net'])/D(r['cost'])>=D('.3')],strong_ordinary1048=[r for r in rows['strong'] if D(r['net'])/D(r['cost'])<D('.3')])
cohorts['post_negative219']=[r for r in cohorts['post303'] if D(r['net'])<0]
cohorts['post_positive84']=[r for r in cohorts['post303'] if D(r['net'])>0]
assert len(cohorts['post303'])==303 and len(cohorts['strong_tail123'])==123
predicates={
 'original_I_target_on':lambda r:bool(r['original_stock_state']['i_target']),
 'original_E0_target_on':lambda r:bool(r['original_stock_state']['e0_target']),
 'I_buy_now':lambda r:bool(r['I_buy_now']),
 'mobile_fresh_CP_new_unconsumed_frontier':lambda r:r['role']=='mobile' and bool(r['CP_new_unconsumed_frontier']),
 'mobile_same_CLOSE_I_buy_and_CP':lambda r:r['role']=='mobile' and bool(r['I_CP_same_confirmation_CLOSE']),
 'no_new_industry_receipt_at_decision':lambda r:not r['industry_new_receipt_now'],
 'same_industry_auth_as_prior_actual_buy':lambda r:r['industry_authorization_same_as_prior_actual_buy_decision'] is True,
 'no_new_industry_receipt_since_prior_actual_buy':lambda r:r['new_industry_receipt_since_prior_actual_buy'] is False,
 'mobile_CP_formation_before_prior_actual_fill':lambda r:r['role']=='mobile' and r['CP_anchor_on_or_after_prior_actual_buy_fill'] is False,
 'actual_fill_nominal_risk_exceeds_frozen_full_plan':lambda r:r['role']=='mobile' and D(r['actual_initial_nominal_risk'])>D(r['frozen_order_full_plan_reference_risk'])+D('.000001'),
 'fill_open_above_decision_close':lambda r:D(r['entry_gap_pct'])>0,
 'daily_r_negative_E_positive':lambda r:r['direction_snapshot']['pvr_r']<0 and r['direction_snapshot']['pvr_E']>0,
 'mobile_prior_daily_r_negative_E_positive_then_freshCP':lambda r:r['role']=='mobile' and r['divergence']['pvr_daily_down_smooth_positive']['fresh_CP1_after_prior_divergence'],
 'amount_smoothed_positive_price_smoothed_nonpositive':lambda r:r['divergence']['pvr_amount_smooth_positive_price_smooth_nonpositive']['current'],
 # Posterior evaluation labels below are explicitly never eligible entry gates.
 'POSTHOC_held_CLOSE_at_most5':lambda r:r['holding']['held_close_observations']<=5,
 'POSTHOC_primary_CP_request':lambda r:r['holding']['actual_exit_class']=='CP1_add_protection',
 'POSTHOC_primary_CP_at_most1_held_CLOSE':lambda r:r['holding']['actual_exit_class']=='CP1_add_protection' and r['ratchet']['entry_to_primary_request_held_CLOSE_observations']<=1,
 'POSTHOC_primary_CP_at_most5_held_CLOSE':lambda r:r['holding']['actual_exit_class']=='CP1_add_protection' and r['ratchet']['entry_to_primary_request_held_CLOSE_observations']<=5,
 'POSTHOC_primary_CP_unchanged_entry_line':lambda r:r['ratchet']['entry_to_primary_CP_ratchet']=='UNCHANGED_ENTRY_LINE',
 'POSTHOC_primary_CP_short5_unchanged_entry_line':lambda r:r['holding']['actual_exit_class']=='CP1_add_protection' and r['holding']['held_close_observations']<=5 and r['ratchet']['entry_to_primary_CP_ratchet']=='UNCHANGED_ENTRY_LINE',
 'POSTHOC_not_next_native_OPEN_exit':lambda r:r['request_clock']['actual_exit_is_next_native_session_OPEN'] is False,
}
numeric={
 'held_CLOSE_observations_POSTHOC':lambda r:r['holding']['held_close_observations'],
 'industry_last_receipt_age_observations':lambda r:r['industry_last_receipt_age_observations'],
 'CP_scale_freeze_age_observations':lambda r:r['scale']['CP1_freeze_to_decision_original_valid_observations'],
 'initial_mobile_log_width_over_CP_used_scale':lambda r:r['scale']['initial_width_over_used_scale'] if r['role']=='mobile' else None,
 'fill_gap_pct':lambda r:r['entry_gap_pct'],
 'actual_initial_risk_pct_NAV':lambda r:r['actual_initial_risk_pct_decisionNAV'],
 'buycash_pct_NAV':lambda r:r['actual_buycash_pct_decisionNAV'],
 'PVR_score':lambda r:r['frozen_intent']['PVR_score'],
 'daily_log_price_r':lambda r:r['direction_snapshot']['pvr_r'],
 'smoothed_price_amount_E':lambda r:r['direction_snapshot']['pvr_E'],
 'CP_daily_amount_multiplier_m':lambda r:r['direction_snapshot']['cp1_m'],
 'CP_displacement':lambda r:r['CP_displacement'],
 'CP_frontier_delta':lambda r:r['CP_delta_frontier'],
 'CP_credit':lambda r:r['CP_credit'],
 'signal_to_fill_calendar_days':lambda r:r['signal_to_fill_calendar_days'],
}
summary={};compare=[]
for name,rr in cohorts.items():
 a=agg(rr);features[name]=rr
 g=dict(all=a,by_role_action=group(rr,lambda r:r['role']+'|'+r['simple_action']),by_exit=group(rr,lambda r:r['holding']['actual_exit_class']),by_holding=group(rr,lambda r:'held_close_le5' if r['holding']['held_close_observations']<=5 else 'held_close_gt5'),by_G1_source=group(rr,lambda r:r['G1_source_class']),by_industry_stage=group(rr,lambda r:r['industry_stage']),by_signal_to_fill_days=group(rr,lambda r:r['signal_to_fill_calendar_days']),by_request_delay=group(rr,lambda r:r['request_clock']['request_to_fill_native_session_steps']),numeric={k:qtiles(rr,fn) for k,fn in numeric.items()},predicates={})
 for p,fn in predicates.items():
  hit=[r for r in rr if fn(r)];ha=agg(hit);ha['negative_money_coverage']=None if a['negative']==0 else ha['negative']/a['negative'];ha['positive_money_coverage']=None if a['positive']==0 else ha['positive']/a['positive'];g['predicates'][p]=ha;compare.append(dict(cohort=name,predicate=p,**ha))
 # Actual-filled dispersion only; this is not eligible market or industry breadth.
 sectors=group(rr,lambda r:r['industry']);g['filled_industry_concentration']=dict(by_industry=sectors,top5_negative=sorted(sectors.items(),key=lambda z:z[1]['negative'])[:5],top5_positive=sorted(sectors.items(),key=lambda z:z[1]['positive'],reverse=True)[:5],cost_HHI=sum(((v['cost']/a['cost'])**2 for v in sectors.values()),Z),positive_HHI=None if not a['positive'] else sum(((v['positive']/a['positive'])**2 for v in sectors.values()),Z),negative_HHI=None if not a['negative'] else sum(((v['negative']/a['negative'])**2 for v in sectors.values()),Z))
 days=group(rr,lambda r:r['decision_at'][:10]);g['actual_filled_decision_day_dispersion']=dict(days=len(days),median_industries=float(np.median([v['industries'] for v in days.values()])),by_day=days)
 summary[name]=g
save('CORE_TABLES.json',summary);save('ALL_JOINED_LAYER_ROWS.json',{k:[compact(r) for r in rr] for k,rr in rows.items()})
with (O/'PREDICATE_COVERAGE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(compare[0]));w.writeheader();w.writerows(compare)
# Same original campaign, but post-new layers only: do not mix old inventory P10 loss.
campaigns=read(S/'accounting/results_v2/2022_2024_CAMPAIGNS_FULL_ACCOUNTING.json');postids={r['layer'] for r in cohorts['post303']};lookup={r['layer']:r for r in rows['2022_2024']};chains=[]
for c in campaigns:
 hit=[lookup[i] for i in c['layer_ids'] if i in postids]
 if hit:chains.append(dict(campaign=c,post303_layers=agg(hit),post_layer_rows=[compact(r) for r in hit]))
chains.sort(key=lambda c:c['post303_layers']['net']);save('POST303_ALL_CAMPAIGN_CHAINS.json',chains)
p10=read(S/'accounting/results_v2/2022_2024_P10_after2024Oct8_DETAIL.json');cg=defaultdict(list)
for r in p10['layer_rows']:cg[r['cohort']].append(r)
bridge={k:dict(layers=len(v),stocks=len({r['sid'] for r in v}),**{field:sum((D(r[field]) for r in v),Z) for field in ['wealth','real','unreal','AR','actual_new_buycash']}) for k,v in cg.items()}
save('P10_NEW_VS_OLD_COHORT_BRIDGE.json',dict(by_cohort=bridge,post303=agg(cohorts['post303']),limitation='post303 complete layer contributions are not the entire P10 account change; old inventory remains in stage bridge'))
save('VALIDATION.json',dict(status='PASS_ORIGINAL_ROW_JOIN',counts={k:len(v) for k,v in cohorts.items()},all3436_layer_net_and_sid_exact=True,post303_expected_net='-112457.6005694286215',post303_actual_net=agg(cohorts['post303'])['net'],unknown_state_rows=sum(bool(r['unknown']) for r in rows['2022_2024']+rows['strong']),unknown_direction_rows=sum(bool(r['direction_unknown']) for r in rows['2022_2024']+rows['strong']),new_exports=0,model_replays=0,new_accounts=0,elapsed_seconds=time.monotonic()-start))
save('SOURCE_MANIFEST.json',dict(source_sha256=SRC,script_sha256=sha(__file__),write_scope=str(O),previous_sealed_outputs_edited=False))
print(json.dumps({k:{z:v[z] for z in ['all','by_role_action','by_exit','by_holding']} for k,v in summary.items() if k in ['post303','strong_tail123','strong_ordinary1048']},ensure_ascii=False,default=str),flush=True)
