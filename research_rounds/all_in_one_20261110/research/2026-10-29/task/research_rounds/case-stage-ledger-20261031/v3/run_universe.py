"""One authorized full-universe normal A/B pair; measured segment is continued."""
from pathlib import Path
import copy,json,pickle,shutil,time
import launch_v3 as L
J=L.J
OUT=J.O/'run-universe'

class UniversePair(L.PreparedRunner):
 def checkpoint(self,out,last_event):
  super().checkpoint(out,last_event)
  out=Path(out);day=str(last_event.date())
  if day in ('2025-09-30','2025-12-31','2026-03-31'):
   for suffix in ('pkl','json'):shutil.copy2(out/('checkpoint.'+suffix),out/('checkpoint-'+day+'.'+suffix))
   p=pickle.loads((out/'checkpoint.pkl').read_bytes())
   for name,state in p['accounts'].items():
    target=out/('checkpoint-'+day+'-'+name+'.pkl');target.write_bytes(pickle.dumps(state,protocol=5))

def main():
 assert L.read(J.O/'PREFIX_GATE.json')['passed']
 assert L.read(J.O/'run-case/DONE.json')['completed']
 assert not (OUT/'DONE.json').exists(),'completed pair is not rerun'
 start=time.monotonic();seed,status=L.preflight('universe')
 r=UniversePair((seed.bundle,seed.market,seed.facts),seed.receipts,stock_cp=seed.cp,
  industry_states={s:list(rows.values()) for s,rows in seed.industry_rows.items()},industry_receipts=seed.industry_cp)
 r.source_freeze=dict(status['freeze'],**{str(Path(__file__)):L.sha(Path(__file__))})
 L.save(OUT/'FREEZE.json',dict(status,freeze=r.source_freeze,authorized_pair=['A_probe_only','B_v3_live_expansion'],
  total_replay_audit_budget_seconds=420,snapshot_not_PIT=True,no_case_priority=True))
 prepared=time.monotonic();print('UNIVERSE_INPUT_READY',round(prepared-start,3),flush=True)
 first=time.monotonic();done=r.run_prepared(OUT,10)
 segment=time.monotonic()-first;closes=len(r.daily)//2;total=sum(J.START<=str(x.date())<=J.END for x in r.market.cutoffs)
 estimate=segment*total/max(1,closes)
 measurement=dict(segment_wall_seconds=segment,completed_closes=closes,total_closes=total,
  conservative_linear_wall_estimate_seconds=estimate,first_segment_is_part_of_same_pair=True,not_replayed_from_cash=True)
 L.save(OUT/'THROUGHPUT.json',measurement);print('UNIVERSE_THROUGHPUT',json.dumps(measurement),flush=True)
 if done:pass
 elif estimate>420:
  L.save(OUT/'BUDGET_REVIEW.json',dict(reason='measured segment including necessary save/audit overhead projects above420s',
   **measurement,checkpoint=str(OUT/'checkpoint.pkl'),no_new_policy_or_scope=True))
  print('SAVED_FOR_BUDGET_REVIEW',flush=True);return
 else:
  after=J.M.N.iso(L.read(OUT/'checkpoint.json')['at']);remaining=max(1,420-segment)
  done=r.run_prepared(OUT,remaining,resume_after=after)
  if not done:
   print('SAVED_AT_TOTAL_COMPUTE_BUDGET',flush=True);return
 L.save(OUT/'TIMING.json',dict(preparation_seconds=prepared-start,
  replay_plus_audit_save_wall_seconds=time.monotonic()-prepared,total_seconds=time.monotonic()-start,
  total_full_account_paths=2,first_segment_was_continued=True))
 print('UNIVERSE_PAIR_DONE',json.dumps({k:str(a.current_nav) for k,a in r.accounts.items()}),flush=True)

if __name__=='__main__':main()
