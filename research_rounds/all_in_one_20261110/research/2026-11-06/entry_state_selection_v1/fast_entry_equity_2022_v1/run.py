"""Single fixed new-arm conditional lifecycle. No sweep or account."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
import lifecycle as l
s=l.s;O=Path(__file__).resolve().parent
def verify_inputs():
 frame=l.load_inputs()
 a=frame[frame.AB_event_id.notna()].set_index('AB_event_id');b=s.ev.set_index('event_id')
 assert len(a)==len(b)==12917 and set(a.index)==set(b.index)
 for key,newkey in [('sid','sid'),('day','day'),('sector','sector'),('event_type','AB_event_type'),('I_qualified','AB_I_qualified'),('PVR_known','AB_PVR_known')]:
  x=a.loc[b.index,newkey];y=b[key]
  if key=='day':assert pd.to_datetime(x).equals(pd.to_datetime(y).rename(x.name))
  else:assert np.array_equal(x.to_numpy(),y.to_numpy()),key
 assert np.allclose(a.loc[b.index,'PVR_score'].to_numpy(float),b.PVR_score.to_numpy(float),equal_nan=True,atol=1e-10,rtol=1e-12)
 assert set(a.AB_event_type)=={'A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR'}
 return frame
if __name__=='__main__':
 import sys
 if sys.argv[1]=='inputs':
  f=verify_inputs();s.save(O/'CONSUMER_INPUT_QA.json',dict(passed=True,candidates=len(f),original_AB_exact=12917,canonical_CP=len(l.cpmap),new_economics=0));print('CONSUMER_INPUT_PASS',len(f),flush=True)
 elif sys.argv[1]=='economic':
  seal=s.read(O/'FREEZE.json');assert seal['independent_audit_passed']
  for path,h in seal['source_hashes'].items():assert s.sha(path)==h,('frozen source drift',path)
  for name,h in seal['artifact_hashes'].items():assert s.sha(O/name)==h,('frozen artifact drift',name)
  assert not (O/'RUN_ONCE.json').exists() and not (O/'economic').exists()
  f=verify_inputs();l.reset(True)
  s.save(O/'RUN_ONCE.json',dict(started=pd.Timestamp.now(tz='UTC').isoformat(),arm='AB_FAST_SMALL',baseline='sealed dynamic A_UNION_B cached, not rerun',freeze_sha256=s.sha(O/'FREEZE.json'),new_arm_runs_allowed=1,no_sweep=True,no_shared_account=True))
  l.run_new(f)
  z=pd.DataFrame(s.rounds);d=pd.DataFrame(s.decisions);a=pd.DataFrame(s.actions)
  assert not z.round_id.duplicated().any() and set(z.round_id)==set(d.loc[d.selected,'round_id'])
  assert d.groupby(['day','sector']).selected.sum().le(2).all()
  buy=a[a.side.eq('buy_core')];assert (buy.q*buy.price+buy.fee).le(24000+1e-7).all()
  entered=z[z.entry_status.eq('CONDITIONAL_OPEN_PROXY')];assert entered.entry_risk.le(3000+1e-7).all()
  assert a[a.side.eq('buy_add')].prior_round_net.gt(0).all() and a[a.side.eq('buy_add')].groupby('round_id').size().le(1).all()
  consumed=pd.DataFrame(l.consumptions);cp=consumed[~consumed.kind.eq('CORE_EPOCH')]
  assert not cp.duplicated(['arm','identity']).any()
  # Independent no-overlap/UNKNOWN lock test from final per-stock roots.
  for sid,g in z[z.entry_status.eq('CONDITIONAL_OPEN_PROXY')].groupby('sid'):
   end=None
   for r in g.sort_values('entry_day').itertuples():
    if end is not None:assert pd.Timestamp(r.entry_day)>end,(sid,'stock overlap or UNKNOWN reopened')
    end=pd.Timestamp(r.exit_day) if r.status=='COMPLETE_CONDITIONAL_STOCK_ROUND' else s.END
  s.dump(O/'economic');pd.DataFrame(l.role_attempts).to_csv(O/'economic/ROLE_ATTEMPTS.csv',index=False);consumed.to_csv(O/'economic/CONSUMPTIONS.csv',index=False)
  qa=dict(passed=True,rounds=len(z),actions=len(a),decisions=len(d),max_two_industry_day=True,one_result_per_pending=True,small_entry_budget=True,plan_risk=True,profitable_single_add=True,CP_unique_fill_consumption=True,independent_no_overlap_UNKNOWN_lock=True,T1_cash_fee_dividend=s.ledger_qa())
  s.save(O/'economic/QA.json',qa)
  s.save(O/'economic/OUTPUT_HASHES.json',{p.name:s.sha(p) for p in (O/'economic').iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
  print('ECONOMIC_DONE',z.status.value_counts().to_dict(),flush=True)
