"""Input/initial-state preparation; NO native account event/step/window call."""
from pathlib import Path
from dataclasses import asdict
import copy,sys,json,os,time
import month_r0 as X
E=X.E;R=X.HERE

def main():
 t=time.perf_counter();old=X.M.guard();rec=old['inputs']['2025_26'];inputs=X.M.MonthInputs(rec['path'])
 for k in inputs.m['files']:inputs.ref(k)
 for k in inputs.m['extensions']:inputs.extra(k)
 for k in inputs.m['month_extension']:inputs.month_ref(k)
 assert len(inputs.days)==23 and inputs.days[0]=='2025-07-01' and inputs.days[-1]=='2025-07-31'
 actions=[a for d in inputs.days for a in inputs.actions(d)];problems=[];splitrows=[]
 for day in inputs.days:
  for a in inputs.actions(day):
   try:inputs.check_action_support(a,[])
   except Exception as ex:problems.append(dict(day=day,source=a,error=repr(ex)))
   if E.D(a['split_ratio'])!=1:
    n=inputs.days.index(day);prev=inputs.days[n-1] if n else inputs.m['warm_through'];s=inputs.stock(a['sid'],prev,'CLOSE')
    splitrows.append(dict(source=a,previous_close=prev,stock_Q=s['retained_stock_Q'],core_Q=s['retained_core_event_Q'],canonical_receipt=s['canonical_receipt'],possible_unsubmitted_C=bool(s['canonical_receipt'] and s['retained_stock_Q']['value'] is True),status='conditional: only actual positive C Q before action would block; no account path guessed'))
 physical=X.read(R/'PHYSICAL_INPUT.json')
 identity=dict(physical_manifest=physical['path'],physical_manifest_sha256=physical['sha256'],scope='INPUT_AND_ZERO_FINANCE_PREPARATION_ONLY',financial_events_authorized=False,window='2025_26',start=inputs.days[0],end=inputs.days[-1],days=inputs.days,ids=len(inputs.ids),industries=len(inputs.m['sectors']),warm_through=inputs.m['warm_through'],month_manifest=rec['path'],month_manifest_sha256=X.sha(rec['path']),
  original_full_input_files=inputs.m['files'],extensions=inputs.m['extensions'],month_extension=inputs.m['month_extension'],original_inputs_unchanged=True,no_new_indicator_compute=True,risk_core_sha256=X.RISK_SHA,
  canonical_generation_rule='Preserve original Jul1/2 source generation; Jul3+ same original as-of generation. No future signal used.',source_only_action_problems=problems)
 X.save(R/'INPUT_IDENTITY.json',identity);X.save(R/'CORPORATE_ACTION_PREFLIGHT.json',dict(all_source_events=len(actions),source_only_unsupported=problems,all_source_events_retained=True,split_events=splitrows,financial_events=0,not_a_forecast_of_future_positions=True))
 assert not problems,'original source event unsupported; no financial start permitted'
 accounts={};gate_initials={}
 for mode in ['C10','C_BATCH20']:
  for branch,enabled in [('full',True),('full',False),('physical',True)]:
   r=X.Runner(mode,branch=branch,risk_enabled=enabled);warm=E.iso(inputs.m['warm_through']+'T15:10:00+08:00');a=r.account
   assert a.available==E.D(1000000) and a.nav(warm)==E.D(1000000)
   assert not any([a.positions,a.pending,a.buys,a.exits,a.policy.losses,a.policy.consumed,a.core_epoch,r.authority.orders,r.risk.approvals])
   assert r.last_completed_event is None and r.budget is None
   key=mode+'|'+branch+'|'+('on' if enabled else 'off');p=R/'initial'/(key.replace('|','-')+'.pkl');r.checkpoint(p);scopes=a.policy.scopes
   record=dict(path=str(p),sha256=X.sha(p),provenance_sha256=X.sha(p.with_suffix('.provenance.json')),mode=mode,branch=branch,risk_enabled=enabled,available=a.available,NAV=a.nav(warm),warm_cursor=r.cursor,F1_nodes=len(r.f1),
    global_scope=asdict(scopes['G']),industry_support=sum(s.support for k,s in scopes.items() if k!='G'),industry_permit=sum(s.permit for k,s in scopes.items() if k!='G'),industry_mature=sum(s.mature for k,s in scopes.items() if k!='G'),
    positions=0,orders=0,pending_intents=0,trial_facts=0,consumed_receipts=0,old_loss=0,core_locks=0,last_completed=None,initial_state_hash=r.initial_state_hash,full_input_binding_kept_initial_zero_view=True,financial_events=0)
   gate_initials[key]=record
   if branch=='full' and enabled:accounts[mode]=record
   X.save(R/'initial'/(key.replace('|','-')+'.json'),dict(record=record,observable=r.observable(warm)))
   print('INITIAL_NATIVE_ACCOUNT_READY',key,'1m','F1nodes',len(r.f1),'pending0','events0',flush=True)
 X.save(R/'INITIAL_CHECKPOINTS.json',dict(accounts=accounts,gate_initials=gate_initials,original_no_event_initial_state_exact=True,financial_events=0))
 grant=dict(scope='TWO_NEW1M_R0_JULY_PATHS_ONLY',parent_approved=False,independent_audit_PASS=False,financial_events_authorized=False,modes=['C10','C_BATCH20'],start=inputs.days[0],end=inputs.days[-1],runtime_sha256=X.sha(R/'month_r0.py'),entry_sha256=X.sha(R/'run_july.py'),risk_core_sha256=X.RISK_SHA,input_identity_sha256=X.sha(R/'INPUT_IDENTITY.json'),initial_checkpoints=accounts,no_old_baseline_rerun=True,no_2022=True,no_parameter_change=True)
 X.save(R/'AUTHORIZATION_PROPOSAL.json',grant)
 X.save(R/'PREPARATION.json',dict(passed=True,financial_events=0,model_recomputations=0,seconds=time.perf_counter()-t,formal_initial_accounts=2,technical_initial_accounts=4,all_source_actions_retained=len(actions),split_event_count=len(splitrows),potential_unsubmitted_C=[(r['source']['sid'],r['source']['effective_date']) for r in splitrows if r['possible_unsubmitted_C']],free_disk_bytes=os.statvfs(R).f_bavail*os.statvfs(R).f_frsize,guard='financial grant remains false; await parent audit release'))
 print('PREPARATION_COMPLETE','seconds',round(time.perf_counter()-t,3),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  import traceback
  X.save(R/'PREPARE_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),financial_events=0));raise
