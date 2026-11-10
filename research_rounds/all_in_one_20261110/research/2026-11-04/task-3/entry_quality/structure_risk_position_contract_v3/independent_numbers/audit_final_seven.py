"""Independent fixed-seven source and Decimal checks. Does not create financial objects."""
from pathlib import Path
from decimal import Decimal as D
import gzip, hashlib, json, runpy
import pandas as pd

OUT=Path(__file__).resolve().parent;V3=OUT.parent;ENTRY=V3.parent;Z=D(0)
SOURCES={};CHECKS=[];CARD_RECONCILIATION=[]
def read(p):
 p=Path(p);data=p.read_bytes();SOURCES[str(p)]=hashlib.sha256(data).hexdigest()
 return json.loads(gzip.decompress(data) if p.suffix=='.gz' else data)
def check(n,x):
 CHECKS.append({'name':n,'pass':bool(x)});assert x,n
def money(n,a,b):check(n,abs(D(str(a))-D(str(b)))<=D('1e-20'))
def sha(p):p=Path(p);SOURCES[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return SOURCES[str(p)]

local=read(V3/'cases/SEVEN_FIXED_PREFIX_LOCAL_ARITHMETIC.json')
manifest=read(V3/'cases/LOCAL_SOURCE_MANIFEST.json')
for p,h in manifest['sources'].items():
 current=sha(p)
 if p.endswith('/designer/MINIMUM_MATH_CONTRACT.md') and current!=h:
  card=Path(p).read_text()
  check('current card explicitly keeps per-layer P and one prospective same-sid fee group', 'X_l^P=min(M_i,h_l)' in card and 'prospective liquidation group' in card and 'D_k=max(0,L_k−G_k)' in card)
  CARD_RECONCILIATION.append({'path':p,'author_case_card_sha256':h,'current_card_sha256':current,'consumed_math':'P/kappa, one sell-fee group and fixed same-k B/D independently recalculated under current card. Cases do not implement G1/G2/full Omega. Current common-sid pressure/postfill amendments are not claimed numerically tested here.'})
 else:check('case source bytes stable: '+p,current==h)
check('case script source stable',sha(V3/'cases/local_fixed_prefixes.py')==manifest['script_sha256'])
# The independent five arithmetic is re-bound to the final card. This is scalar
# arithmetic only, and does not import the author's calculation or finance code.
independent=runpy.run_path(str(OUT/'check_fixed_local_arithmetic.py'))
five=read(OUT/'INDEPENDENT_FIVE_LOCAL_ARITHMETIC.json')['rows']
fee=independent['fee'];rules=independent['rules']
case_by_sid={sid:read(ENTRY/'structure_risk_position_review_v2/cases'/(sid.replace('.','_')+'_DAILY_PAPER_INPUTS.json')) for sid in ['688146.SH','000620.SZ']}
book_by_sid={sid:read(ENTRY/'trend_exit_controls_v1/runs/BASELINE'/('strong' if sid=='688146.SH' else '2022_2024')/'pair/B.json.gz')for sid in case_by_sid}
stock_manifest=read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
sm={r['symbol']:r for r in stock_manifest}
semantics=[]
for sid,root in [('688146.SH','2026-04-03'),('000620.SZ','2022-01-06')]:
 m=sm[sid];sp=next(p for p in m['source_sha256']if p.endswith('/states.parquet'));sha(sp)
 states=pd.read_parquet(sp);rootidx=states.index.get_loc(pd.Timestamp(root));rr=states.iloc[rootidx]
 check(sid+': true E0 off-on root, not price-event naming',not bool(states.iloc[rootidx-1].target) and bool(rr.target) and bool(rr.entered))
 if sid=='000620.SZ':
  jan20=states.loc[pd.Timestamp('2022-01-20')];day20=next(x for x in case_by_sid[sid]['days']if x['day']=='2022-01-20')
  check('Jan20 states/G1 not entered; persistent original E0',bool(jan20.target) and not bool(jan20.entered) and not bool(day20['original_G1']['e0_entered']) and all(bool(states.loc[pd.Timestamp(d)].target) for d in ['2022-01-06','2022-01-10','2022-01-20','2022-01-21','2022-01-24']))
  semant={'sid':sid,'root':root,'Jan20_states_entered':int(jan20.entered),'Jan20_G1_E0_entered':day20['original_G1']['e0_entered'],'same_canonical_episode_across_fixed_CP_requests':len({r['original_CP_canonical_receipt']['original_E0_episode_id']for r in case_by_sid[sid]['days']if r['day']in ['2022-01-10','2022-01-21','2022-01-24']})==1}
  check('Jan10/21/24 canonical source episode same',semant['same_canonical_episode_across_fixed_CP_requests']);semantics.append(semant)
 b=book_by_sid[sid];orig=min((a for a in b['audit']if a.get('kind')=='reserve'and a.get('sid')==sid and a['decision_at'][:10]>=root),key=lambda a:a['at'])
 for r in local:
  if r['sid']!=sid:continue
  check(sid+'/'+r['decision']+': exact first successful reserve origin',r['origin_first_original_successful_reserve']==orig and r['origin_signal_day']==orig['decision_at'][:10])
  origin_decision=next(x for x in b['decisions']if x['at']==orig['decision_at'])
  money(sid+'/'+r['decision']+': B frozen once at original signal NAV',r['B'],D(origin_decision['nav'])*D('.0025'))

for r,ind in zip(local[:5],five):
 check(r['sid']+'/'+r['decision']+': fixed pair order and source-bound q',r['sid']==ind['sid'] and r['decision']==ind['decision_day'] and r['q_local_after_source_and_frozen_caps']==ind['local_q_after_original_source_cap_and_gross'])
 for a,b in [('B','B_once'),('D_before','D_before')]:money(r['decision']+': '+a,r[a],ind[b])
 for outkey,inkey in [('total','local_total_D_plus_buyfee_plus_kappa'),('kappa_sum','kappa_sum_positive_per_layer'),('unpaid_candidate_buyfee','buyfee_unpaid_or_newly_paid_once'),('sell_group_fee','prospective_same_sid_sellfee_once')]:
  money(r['decision']+': selected '+outkey,r['local_cost_at_q'][outkey],ind['witnesses']['chosen'][inkey])
 for outkey,inkey in [('total','local_total_D_plus_buyfee_plus_kappa'),('kappa_sum','kappa_sum_positive_per_layer')]:money(r['decision']+': next legal '+outkey,r['next_legal_cost'][outkey],ind['witnesses']['next_legal_quantity'][inkey])
 check(r['decision']+': original frozen cap and gross constraint preserved',r['original_frozen_source_cap']==ind['source_cap'] and r['q_local_after_source_and_frozen_caps']<=ind['source_cap'])

Ichecks=[]
for r in local[5:]:
 sid,day,od=r['sid'],r['decision'],r['nextOPEN'];case=case_by_sid[sid];d=next(x for x in case['days']if x['day']==day);n=next(x for x in case['days']if x['day']==od);book=book_by_sid[sid]
 check(sid+'/'+day+': typed branch eligibility is original known absent CP, held, true i_buy/coreQ, confirmed, nonpending',not d['original_CP_cache']['receipt'] and bool(d['original_stock_facts']['i_buy']) and bool(d['original_opportunities'][0]['core_Q']) and bool(d['original_live_layers']) and all(l['saved_native_layer']['pool']=='confirmed' for l in d['original_live_layers']) and not any(l['original_layer_exit_latched_at_CLOSE'] for l in d['original_live_layers']))
 m=D(str(n['original_bar']['raw_open']));p=m*D('1.0005');factor=D(str(n['original_stock_facts']['factor']));h=D(str(d['original_stock_facts']['i_floor']))/factor
 money(sid+'/'+day+': raw actual next OPEN quote',r['next_rawOPEN'],m);money(sid+'/'+day+': buy quote plus frozen 5bp',r['next_buy_price'],p);money(sid+'/'+day+': line is signal I, not next CLOSE I',r['holding_floor_raw_OPEN'],h)
 venue='SSE_STAR' if sid=='688146.SH' else 'SZSE_MAIN';schedule=next(v['schedule']for v in rules['fee_versions'][venue]if v['from']<=od<v['to']);minq=200 if sid=='688146.SH' else 100
 units=next(v['rule']for v in rules['quantity_versions'][sid]if v['from']<=od and (v['to']is None or od<v['to']))
 check(sid+'/'+day+': dated unit and fee schedules exact',r['dated_units']==units and r['dated_fee_schedule']==schedule and minq==units['buy_minimum'])
 buys={t['layer']:t for t in book['trades']if t['side']=='buy'and t['security_id']==sid};existing=[]
 for l in d['original_live_layers']:
  bt=buys[l['layer']];existing.append({'layer':l['layer'],'q':D(l['qty']),'K':D(bt['gross_cny']),'line':D(l['guard_after_original_CLOSE_adjusted'])/factor})
 paid=sum((D(t['fees_cny'])for t in buys.values()if t['at'][:10]<=day and t['signal_at'][:10]>=r['opportunity_key'][2]),Z)
 # Both added I examples precede any realized sale in their original k.
 check(sid+'/'+day+': no realized sale or rights in this prefix',not r['D_components']['sell_parts'] and D(r['D_components']['paid_rights'])==0)
 money(sid+'/'+day+': existing paid fees in D once',r['D_before'],paid)
 parts=existing+[{'layer':'candidate','q':D(minq),'K':D(minq)*p,'line':h}]
 proceeds=[l['q']*min(m,l['line'])*D('.9995')for l in parts];qt=sum(l['q']for l in parts);sf=fee('sell',sum(proceeds,Z),qt,schedule);bf=fee('buy',D(minq)*p,D(minq),schedule)
 kappas=[max(Z,l['K']-n+sf*l['q']/qt)for l,n in zip(parts,proceeds)];total=paid+bf+sum(kappas,Z)
 money(sid+'/'+day+': one minimum-fee prospective group',r['local_minimum_unit_cost']['sell_group_fee'],sf)
 money(sid+'/'+day+': minimum buy fee once',r['local_minimum_unit_cost']['unpaid_candidate_buyfee'],bf)
 money(sid+'/'+day+': minimum per-layer-positive kappa',r['local_minimum_unit_cost']['kappa_sum'],sum(kappas,Z))
 money(sid+'/'+day+': minimum total',r['local_minimum_unit_cost']['total'],total)
 check(sid+'/'+day+': no legal minimum under same B',total>D(r['B']) and r['q_local_after_source_and_frozen_caps']==0 and r['final_disposition']=='DENY_ZERO_LOCAL_MINIMUM_UNIT')
 Ichecks.append({'sid':sid,'day':day,'minimum':minq,'actual_raw_next_OPEN':str(m),'minimum_local_total':str(total),'B_once':r['B'],'outcome':'ZERO_LOCAL_NECESSARY_CONDITION_NOT_A_POSITIVE_GRANT'})

for r in local:
 sid,day=r['sid'],r['decision'];d=next(x for x in case_by_sid[sid]['days']if x['day']==day);book=book_by_sid[sid]
 risk=next(x for x in book['audit']if x['kind']=='risk_checkpoint'and x['at'][:10]==day)
 A=max(Z,D(d['original_account']['NAV'])-D('.8')*D(risk['peak']));lower=D('.36')*D(d['original_account']['inventory'])
 money(sid+'/'+day+': original ACT peak A',r['CLOSE_reference_account']['A'],A);money(sid+'/'+day+': source CLOSE stock-only 36% lower bound',r['CLOSE_reference_account']['G2_no_fee_market_value_lower_bound'],lower)
 check(sid+'/'+day+': no CLOSE to OPEN global-denial leap',r['CLOSE_reference_account']['scope']=='SIGNAL_CLOSE_ONLY_NOT_OPEN_DENIAL' and r['OPEN_full_portfolio_pressure']=='UNVERIFIED_NO_NEW_LOADER' and r['independent_single_prefix'] and r['no_sequence_or_return_claim'])
 check(sid+'/'+day+': positive q conditional only',r['q_local_after_source_and_frozen_caps']==0 or r['final_disposition']=='CONDITIONAL_LOCAL_CAP_NOT_FINAL_GRANT')

res={'status':'PASS_FIXED_SEVEN_LOCAL_ONLY_WITH_SOURCE_AND_FEE_CORRECTIONS','checks':CHECKS,'fixed_local_q':[r['q_local_after_source_and_frozen_caps']for r in local],'added_I_minimum_checks':Ichecks,'k_semantics':semantics,'card_version_reconciliation':CARD_RECONCILIATION,'corrections_from_first_three':['Apr21 risk-only495 must respect original frozen cap476.','Nonpending same sid different plan lines use one prospective sell order, one minimum commission; Jan21 next100 cost7197.023508 corrected to7192.023508.'],'scope':['Five original-prefix arithmetic cases plus the two explicitly added I-minimum checks; no joined replacement sequence.','No full portfolio Omega/Lambda/A/T, historical capacity, all original capital/cash/sector-risk gates or typed grant implementation verified by local positive q.','All positive q conditional. Local B/minimum failures do not manufacture actual orders.','Common-sid boundary stress uses final card only; local calculation checks P/kappa, not a prior G2 implementation.'],'new_accounts':0,'new_models':0,'new_parameter_sweeps':0,'source_sha256':SOURCES,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(OUT/'FINAL_SEVEN_LOCAL_AUDIT.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':res['status'],'checks':len(CHECKS),'q':res['fixed_local_q'],'I_minimum':Ichecks},ensure_ascii=False))
