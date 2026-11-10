"""Original zero-finance factory and frozen January inputs; no events."""
from pathlib import Path
from dataclasses import asdict
import json,sys,time
import jan_r0 as X
E=X.E;P=X.HERE

def main():
 t=time.perf_counter();full=X.M.guard()['inputs']['2022'];physical=X.read(P/'PHYSICAL_INPUT.json');ident=dict(full=full,physical=dict(path=physical['path'],sha256=physical['sha256']),start='2022-01-04',end='2022-01-28',original_frozen_inputs_unchanged=True,no_new_indicators=True,rights_runtime=str(X.CONT_PATH/'resume_runtime_v2.py'),rights_runtime_sha256=X.sha(X.CONT_PATH/'resume_runtime_v2.py'),rights_source_sha256=X.sha(Path(X.RIGHTS.__file__)),risk_core_sha256=X.RISK_SHA)
 X.save(P/'INPUT_IDENTITY.json',ident);i=X.Inputs(full['path']);actions=[]
 for d in i.days:
  for a in i.actions(d):i.check_action_support(a,[]);actions.append(a)
 E.require(len(i.ids)==1709 and len(i.m['sectors'])==90 and i.days[0]=='2022-01-04' and i.days[-1]=='2022-01-28','January scope')
 X.save(P/'ACTION_PREFLIGHT.json',dict(source_events=actions,unsupported_source_only=[],rights=[a for a in actions if a.get('classification')==X.RIGHTS.KIND],held_or_pending_fractional_conditions_remain_atomic_runtime_guards=True,financial_events=0))
 accounts={};cells={}
 for mode in ['C10','C_BATCH20']:
  for branch,on in [('full',True),('full',False),('physical',True)]:
   r=X.Runner(mode,risk_enabled=on,branch=branch);a=r.account;warm=E.iso(i.m['warm_through']+'T15:10:00+08:00');E.require(a.available==E.D(1000000) and a.nav(warm)==E.D(1000000) and not any([a.positions,a.pending,a.buys,a.exits,a.policy.losses,a.policy.consumed,a.core_epoch,r.risk.approvals,r.authority.orders]),'fresh financial state')
   key=mode+'|'+branch+'|'+('on' if on else 'off');cp=P/'initial'/(key.replace('|','-')+'.pkl');r.checkpoint(cp);rec=dict(path=str(cp),sha256=X.sha(cp),mode=mode,branch=branch,risk_enabled=on,initial_state_hash=r.initial_state_hash,available=a.available,NAV=a.nav(warm),warm_cursor=r.cursor,F1_nodes=len(r.f1),pending=0,losses=0,consumed=0,old_financial_account_imported=False)
   cells[key]=rec
   if branch=='full' and on:accounts[mode]=rec
   print('INITIAL_READY',key,flush=True)
 X.save(P/'INITIAL_CHECKPOINTS.json',dict(accounts=accounts,gate_initials=cells,financial_events=0));X.save(P/'PREPARATION.json',dict(passed=True,seconds=time.perf_counter()-t,financial_events=0,ids=1709,industries=90,days=i.days,original_warmup_and_zero_account=True))
if __name__=='__main__':main()
