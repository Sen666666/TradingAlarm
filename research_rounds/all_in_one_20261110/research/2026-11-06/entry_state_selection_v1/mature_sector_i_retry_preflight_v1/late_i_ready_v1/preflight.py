from pathlib import Path
from decimal import Decimal as D
import pandas as pd,numpy as np,json,gzip,hashlib,sys,collections,ast
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent;PRE=O.parent;T=R/'technology_winrate_scope_audit_v1';C=R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2';M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared');U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');hs={}
# Only prior pure helpers, never prior runner body or any account consumer.
source=(PRE/'analyze.py').read_text();names={'h','js','pq','csv','out','load','point','state_at','fee','closecheck'}
for node in ast.parse(source).body:
 if isinstance(node,ast.FunctionDef) and node.name in names:exec(compile(ast.Module(body=[node],type_ignores=[]),str(PRE/'analyze.py')+':pure_helper','exec'),globals())
h(PRE/'analyze.py');protocol=js(O/'PROTOCOL.json');out('FREEZE.json',dict(protocol=hs[str(O/'PROTOCOL.json')],code=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),history_seen=True,account_runs=0))
roster=csv(R/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').set_index('sid');manifest={x['symbol']:x for x in js(U/'STOCK_MANIFEST.json')};panel=pq(C/'COMMON_K_COMPARISON.parquet').sort_values(['sector','day']);panel['previous_S']=panel.groupby('sector').M3_candidate.shift();panel=panel.set_index(['sector','day']);rr=pd.concat([pq(C/'WARM_PREFIX_M_R.parquet'),pq(C/'RIGHT3.parquet')]).sort_index();kk=pd.concat([pq(C/'WARM_PREFIX_M_K.parquet'),pq(C/'KNOWN3.parquet')]).sort_index();ms=rr.astype('int8').where(kk,-1);pm=ms.shift();cal=rr.index;pv=pq(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet').set_index(['sid','day']);facts={};ix={};cps={};raws={};caps={};accounts={}
for win,sub in [('2024_924','indexed_execution_v1/cohort_2024_924'),('2022','known_halt_contract_v1/cohort_2022_recovery_v2')]:
 b=R/'m3_ab_shared_probe_v1'/sub;accounts[win]={n:js(b/(n+'.json')) for n in ['EXACT_TRADE_JOURNAL','ARCHIVES','AUDIT','DAY_LEDGER','DECISIONS','SOURCE_ROUNDS','LAYER_REPORT']}
B=M/'rs-h1-execution-20261025';sys.path.insert(0,str(B/'code'));from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
rules=js(B/'inputs-v2/market-rules.json');proxy=js(B/'inputs-v2/economic-protocol.json')['approved_proxy_ids'];slip=D('.0005')
fast=pd.concat([pq(R/'fast_entry_equity_2022_v1/ALL_MARKET_INPUTS_2022.parquet'),pq(R/'fast_entry_equity_2022_v1/STARTUP_MARKET_INPUTS.parquet')]);fast.day=pd.to_datetime(fast.day);fast=fast.drop_duplicates(['sid','day']).set_index(['sid','day'])
def istate(sid,d):
 load(sid);f=facts[sid]
 if d not in f.index:return -1,'MISSING_FACTS'
 x=f.loc[d]
 if x.get('e0_ready')!=1 or x.get('g_ready')!=True:return -1,'NOT_READY_IS_UNKNOWN'
 if x.get('i_target') not in [0,1] or not np.isfinite(x.get('close',np.nan)) or x.get('close',0)<=0 or not np.isfinite(x.get('factor',np.nan)) or x.get('factor',0)<=0:return -1,'TARGET_OR_COORDINATE_UNKNOWN'
 if x.i_target==0:return 0,'KNOWN_NOT_ACTIVE'
 if not np.isfinite(x.get('i_floor',np.nan)) or x.i_floor<=0:return -1,'ACTIVE_FLOOR_UNKNOWN'
 return 1,'KNOWN_ACTIVE'
def narrow(sid,d):
 d=pd.Timestamp(d);r=point(sid,d);j=cal.get_loc(d);prev=cal[j-1];a,ar=istate(sid,prev);b,br=istate(sid,d)
 same=d in facts[sid].index and prev in facts[sid].index and facts[sid].at[d,'segment_id']==facts[sid].at[prev,'segment_id']
 r.update(previous_I_state=a,current_I_state=b,previous_I_reason=ar,current_I_reason=br,same_segment=bool(same),D_raw=bool(r['S']==r['previous_S']==r['M']==r['previous_M']==1 and a==0 and b==1 and same and r['PVR_known']),I_edge_known=bool(a>=0 and b>=0),I_edge_unknown=bool(a<0 or b<0),earliest_common_OPEN=str(cal[j+1].date()) if j+1<len(cal) else None)
 r['D_receipt_id']=f'{sid}|I_READY|{facts[sid].at[d,"segment_id"]}|{r["day"]}' if r['D_raw'] else None
 if (sid,d) in fast.index:
  f=fast.loc[(sid,d)];r.update(FAST_source_available=True,original_event_Q=f.event_Q,original_epoch_lineage_known=f.epoch_lineage_known,original_i_epoch=f.i_epoch,original_event_Q_reasons=f.event_Q_reasons)
 else:r.update(FAST_source_available=False,original_event_Q=None,original_epoch_lineage_known=None,original_i_epoch=None,original_event_Q_reasons='NOT_IN_SAVED_FAST_WINDOW')
 if r['D_raw']:assert r['i_buy'] and not r['AB_type']
 return r
fixed=csv(PRE/'FIXED7_REQUEST_SUMMARY.csv').day.tolist();old=csv(PRE/'OLD8_EXACT_DECISION_STATE.csv');queue=[];diag=[];summ=[]
for ds in fixed:
 d=pd.Timestamp(ds);win='2022' if ds<'2023' else '2024_924';a=accounts[win];snap=next(x for x in a['AUDIT'] if x['type']=='CLOSE_SNAPSHOT' and x['day'].startswith(ds));nd=D(snap['Nd'])
 ab=[dict(z,channel='AB',D_shadow_selected=bool(z.get('selected')),shadow_warning='Original AB selection preserved locally, not future path') for z in a['DECISIONS'] if z['day'].startswith(ds)];dr=[];unknown=0
 for sid in ms.columns:
  sec=roster.loc[sid,'sector_id'];p=panel.loc[(sec,d)]
  if p.M3_candidate!=1 or p.previous_S!=1 or ms.at[d,sid]!=1 or pm.at[d,sid]!=1:continue
  z=narrow(sid,d);diag.append(dict(z));unknown+=z['I_edge_unknown']
  if not z['D_raw']:continue
  z.update(channel='D',stock_state_before=state_at(sid,d));z.update(closecheck(z,nd));z['shadow_feasible']=z['stock_state_before']=='FLAT' and z['close_check']=='PASS';z['PVR_score']=z['PVR'];z['D_shadow_selected']=False;dr.append(z)
 original_counts=collections.Counter(z['sector'] for z in ab if z.get('selected'))
 for sec in {x['sector'] for x in dr}:
  seq=sorted([z for z in dr if z['sector']==sec and z['shadow_feasible']],key=lambda z:(-z['PVR_score'],z['sid']))
  for rank,z in enumerate(seq,1):z['D_feasible_rank']=rank;z['AB_slots_used']=original_counts[sec];z['D_shadow_selected']=rank<=max(0,2-original_counts[sec])
 for z in ab+dr:z['signal_day']=ds
 queue+=ab+dr;summ.append(dict(day=ds,AB_events=len(ab),AB_original_pending=sum(z.get('selected',False) for z in ab),AB_shadow_preserved=sum(z['D_shadow_selected'] for z in ab),mature_M3_checked=sum(z['day']==ds for z in diag),I_edge_unknown=unknown,D_raw=len(dr),D_flat=sum(z['stock_state_before']=='FLAT' for z in dr),D_close_feasible=sum(z['shadow_feasible'] for z in dr),D_remaining_slot_selected=sum(z['D_shadow_selected'] for z in dr),old8_D_selected=[z['sid'] for z in dr if z['D_shadow_selected'] and z['sid'] in set(old.sid)]))
pd.DataFrame(queue).to_csv(O/'FIXED7_AB_D_SHADOW_QUEUES.csv',index=False);pd.DataFrame(diag).to_csv(O/'FIXED7_ALL_MATURE_STATE_CHECKS.csv',index=False);pd.DataFrame(summ).to_csv(O/'FIXED7_SUMMARY.csv',index=False)
# All previously fixed controls, no fresh outcome-selected cases.
ident=[]
for x in old.itertuples():ident.append(dict(sid=x.sid,day=x.day,case_scope='OLD8',original_actual_net=x.old_actual_net))
for x in csv(PRE/'FIXED42_UNCHANGED_CONTROLS.csv').to_dict('records'):ident.append(dict(sid=x['sid'],day=x['day'],case_scope='FIXED42',original_core_NET80=x['original_core_NET80'],original_actual_shared_fill=x['original_actual_shared_fill']))
for x in csv(R/'klinger_vf_entry_preflight_v1/FIXED6_EARLY_IDENTITIES.csv').to_dict('records'):ident.append(dict(sid=x['sid'],day=x['signal_day'],case_scope='EARLY6_NOT_AB'))
case=[]
for x in ident:
 z=narrow(x['sid'],x['day']);z.update(x);case.append(z)
pd.DataFrame(case).to_csv(O/'FIXED56_CASES.csv',index=False)
# Previously fixed weak-exit trace; no following returns evaluated.
w=[]
for x in csv(PRE/'WEAK_ORIGINAL_EXIT_RETRY_TRACE.csv').to_dict('records'):
 z=narrow(x['sid'],x['day']);z.update(old_exit_day=x['old_exit_day'],original_baseline_state=x['current_state'],prior_actual_core_NET80=x['prior_actual_core_NET80']);w.append(z)
pd.DataFrame(w).to_csv(O/'WEAK_ORIGINAL_EXIT_D_TRACE.csv',index=False)
# Genuine independent source clock overlap checks for all existing date labels.
E=csv(R/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv',low_memory=False);keys={(z.sid,str(z.day)[:10]) for z in E.itertuples() if z.event_type in ['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR']};assert not any((z['sid'],z['day']) in keys for z in diag if z['D_raw'])
# Physical prefix-like access test: narrow only t,t-1; verify actual f.loc[:t] states exactly for D rows.
prefix=[]
for z in diag:
 if not z['D_raw']:continue
 sid=z['sid'];d=pd.Timestamp(z['day']);orig=facts[sid];facts[sid]=orig.loc[:d].copy();zz=narrow(sid,d);facts[sid]=orig;assert zz==z;prefix.append(dict(sid=sid,day=z['day'],truncated_facts_exact=True))
pd.DataFrame(prefix).to_csv(O/'FACT_PREFIX_CHECKS.csv',index=False)
for p in [R/'epoch_v3/rolling_prebreak_v31/check_epoch_semantics.py',R/'fast_entry_equity_2022_v1/PROTOCOL_DRAFT.md',R/'m3_stock_birth_during_sector_v1/relative_priority_v1/PROTOCOL.json',R/'m3_stock_birth_during_sector_v1/relative_c_entry_v1/PROTOCOL.json']:h(p)
out('SOURCE_HASHES.json',hs);assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==hh for p,hh in hs.items());out('QA.json',dict(fixed_days=len(fixed),fixed_cases=len(case),D_raw_total=sum(x['D_raw'] for x in diag),AB_overlap=0,AB_same_day_selected_all_preserved=all(x['AB_original_pending']==x['AB_shadow_preserved'] for x in summ),D_always_original_i_buy=True,new_I_edges_unknown_not_false=True,physical_fact_prefix_checks=len(prefix),account_runs=0,new_fills=0,source_unchanged=True))
print(pd.DataFrame(summ).to_string(index=False));print('OLD8',pd.DataFrame(case).query('case_scope=="OLD8"')[['sid','day','previous_I_state','current_I_state','D_raw']].to_string(index=False));print('weak new D',pd.DataFrame(w).query('D_raw==True')[['sid','day','old_exit_day','original_baseline_state']].to_string(index=False))
