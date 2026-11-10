from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;E=O.parents[1];B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');S={}
def read(p):p=Path(p);S[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def agg(z):return dict(layers=len(z),stocks=len({e['sid'] for e in z}),cost=sum((D(e['cost']) for e in z),D(0)),net=sum((D(e['net']) for e in z),D(0)),positive_net=sum((D(e['net']) for e in z if D(e['net'])>0),D(0)),negative_net=sum((D(e['net']) for e in z if D(e['net'])<0),D(0)))
rows={r:read(O/(r+'_NATIVE_EVENT_ROWS.json')) for r in ['2022_2024','strong']};act=read(B/'ar6_native_feasibility/ACT_RECOVERY_SEMANTICS/ACT_CLOCK_AND_CLAUSES.json');events=next(x['actual_events'] for x in act['records'] if x['policy']=='no60');resumes=[x['at'] for x in events if x['event']=='resume'];out=[]
for at in resumes:
 later=[x for x in rows['2022_2024'] if x['decision_at']>=at and (not any(y>at and y<=x['decision_at'] for y in resumes))];inherit=[x for x in later if x['native_E0_event_context']['current_I_true_start']<at[:10]];same=[x for x in later if x['decision_at']==at]
 out.append(dict(actual_resume_at=at,all_until_next_resume=agg(later),entries_in_Iroot_started_strict_before_resume=agg(inherit),same_resume_CLOSE_entries=agg(same),same_resume_CLOSE_inheritedI=agg([x for x in same if x['native_E0_event_context']['current_I_true_start']<at[:10]]),inherited_rows=[{k:x[k] for k in ['layer','sid','name','decision_at','opened','role','action','cost','net','native_E0_event_context']} for x in inherit]))
save('ACT_EXISTING_I_RECOVERY.json',dict(original_no60_events=events,actual_resume_inherited_I=out,source_logic='ACT20_BREAK requires flat and current composite breakout, no stock E0/I new epoch; actual later entries shown not counterfactual missed opportunities'))
# Exact fixed original winner lists, full membership retained.
tails={}
for ref in rows:
 rr={x['layer']:x for x in rows[ref]};cc=[]
 for c in read(E/'local_high'/(ref+'_FIXED_TAILS.json')):
  mm=[rr[x['layer']] for x in c['matched_actual_No60_rows']];hit=[x for x in mm if x['role']=='mobile' and x['native_negative_event_unreconfirmed']]
  cc.append(dict(original=c['original'],all_matching_No60_layers=[x['layer'] for x in mm],hit_matching_No60_layers=[x['layer'] for x in hit],hit_original_path=agg(hit),matched_no60_rows=[{k:x[k] for k in ['layer','sid','role','action','decision_at','net','native_negative_event_unreconfirmed','native_E0_event_context']} for x in mm]))
 tails[ref]=dict(original_members=len(cc),matched_members=sum(bool(c['all_matching_No60_layers']) for c in cc),hit_original_members=sum(bool(c['hit_matching_No60_layers']) for c in cc),hit_No60=agg([rr[l] for c in cc for l in c['hit_matching_No60_layers']]),all_members=cc)
save('NATIVE_NEGATIVE_EVENT_FIXED_WINNERS.json',tails)
# Deterministic representative chains: top3 adverse per-stock original net per pre-existing weak/post cohort,
# then3 requested strong controls + top full-window strong winner other than requested names. No predicate selects samples.
weak=[x for x in rows['2022_2024'] if x['opened'][:4]<'2024'];post=[x for x in rows['2022_2024'] if x['opened'][:10]>'2024-10-08'];strong=rows['strong'];selected=[]
for label,z in [('2022_2023',weak),('post_Oct8_303',post)]:
 g=defaultdict(list)
 for x in z:g[x['sid']].append(x)
 for sid,zz in sorted(g.items(),key=lambda kv:(sum(D(x['net']) for x in kv[1]),kv[0]))[:3]:selected.append((label,sid,zz,'top3 original loss contribution per-stock in complete pre-existing cohort; explanatory only'))
for sid in ['002969.SZ','688146.SH','301319.SZ']:selected.append(('strong',sid,[x for x in strong if x['sid']==sid],'previously requested fixed winner control, all original actual layers'))
g=defaultdict(list)
for x in strong:
 if x['sid'] not in ['002969.SZ','688146.SH','301319.SZ']:g[x['sid']].append(x)
sid,zz=max(g.items(),key=lambda kv:sum(D(x['net']) for x in kv[1]));selected.append(('strong',sid,zz,'largest full-window original per-stock net, excluding fixed3; retrospective control only'))
chains=[]
for label,sid,zz,why in selected:
 chains.append(dict(cohort=label,sid=sid,name=zz[0]['name'] if zz else None,selection=why,original_path=agg(zz),entry_nodes=[{k:x[k] for k in ['layer','decision_at','opened','closed','role','action','pool_at_fill','cost','net','I_buy_now','I_CP_same_confirmation_CLOSE','I_G1_frontier_and_CP_new_frontier_same_CLOSE','G1_up_reasons','G1_phase','original_stock_state','CP_formation_start_exclusive','CP_delta_frontier','CP_displacement','CP_credit','CP_used_scale','CP_candidate','stock_floor_binding','industry_state','industry_last_receipt_day','industry_last_receipt_age_observations','new_industry_receipt_since_prior_actual_buy','new_stock_close_above_known_postbuy_high','native_E0_event_context']} for x in sorted(zz,key=lambda x:(x['decision_at'],x['layer']))]))
assert len(chains)==10;save('TEN_REPRESENTATIVE_CHAINS.json',dict(selection_protocol='3 worst stock net in 2022-23,3 worst in strict postOct8,3 named strong controls,largest remaining strong per-stock net; all complete cohort entries included, outcome used only to choose explanation/control, never signal.',chains=chains))
# Original source lines and hashes, plus failed-neighbor reports.
source_specs=[(W/'case-stage-ledger-20261031/v3/joint_v3.py','native management/new-role/routing/open clock'),(W/'case-stage-ledger-20261031/budget_v3/model.py','industry financial permission'),(W/'industry-mobile-stage-20261031/stage.py','industry market stage'),(W/'native-I-cache-interface-20261031/cache.py','native-I input facts and explicitly disabled participation decline memory'),(W/'pvr-current-v3-information-capital-20261101/original_score_function.py','PVR original score'),(W/'cp1-evidence-trace-20261031/trace.py','canonical CP fresh advance identity'),(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py'),'native E0 event'),(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py'),'E0 participation'),(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py'),'G1 ordinal and fresh frontier'),(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py'),'I participation'),(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py'),'G1 upstream S21/S63'),(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py'),'CP1 original market evidence'),(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/risk_policy.py'),'original ACT state'),(W/'mainline-absolute-Q4-20261031/recovery.csv','original actual composite input'),(E/'direction_divergence/READOUT.txt','previous signed volume-direction refutation'),(E/'first_entry_regime/native_state/NATIVE_PERMISSION_SEMANTICS.txt','actual first-mobile independent funding'),(E/'dec2022_authorization_v1/followup_robustness_v1/entry_mechanism/DISPOSITION.txt','formation gate STOP'),(E/'dec2022_authorization_v1/followup_robustness_v1/entry_mechanism/I_BUY_SOURCE_COVERAGE/READOUT.md','existing-frontier filter failed winner control'),(B/'loss_correction/entry_risk_commitment_review/FINAL_DISPOSITION_STOP.txt','q risk/R0 neighbor stop'),(W/'g-s-C-R0-continuous-january-v1-20261102/REPORT.txt','R0 is approved nominal risk preservation, not negative-event leg')]
ss=[]
for p,meaning in source_specs:ss.append(dict(path=str(p),purpose=meaning,exists=p.exists(),sha256=None if not p.exists() else hashlib.sha256(p.read_bytes()).hexdigest()))
save('SOURCE_SEMANTICS_HASHES.json',dict(sources=ss,additional_input_sources=S,new_models=0,new_accounts=0,new_price_downloads=0));print('ACT',[(x['actual_resume_at'],x['entries_in_Iroot_started_strict_before_resume'],x['same_resume_CLOSE_inheritedI']) for x in out]);print('TAILS',[(k,{a:v[a] for a in ['original_members','matched_members','hit_original_members','hit_No60']}) for k,v in tails.items()]);print('CHAINS',[(c['cohort'],c['sid'],c['name'],c['original_path']) for c in chains])
