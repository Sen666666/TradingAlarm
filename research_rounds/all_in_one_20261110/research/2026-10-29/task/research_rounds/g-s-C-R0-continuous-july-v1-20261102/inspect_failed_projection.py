"""Exact saved C20 failed optional-stage diagnostics; NO financial events.
Higher technical loop ceiling is only a pure planning feasibility diagnostic,
not accepted authority, new policy or permission to resume the account.
"""
from pathlib import Path
import time,copy,json,traceback,hashlib
import month_r0 as X
E=X.E;P=X.HERE;ROOT=P/'runs/C_BATCH20'
def main():
 t=time.perf_counter();f=ROOT/'FAILED_WORKING_STATE.pkl';r=X.Runner.restore(f);at=r.last_completed_event;stage=r.close_stages[at.isoformat()]
 E.require(str(at).startswith('2025-07-22 15:10') and stage['optional_status']=='failed_exception','specific saved optional failure only')
 old_fills=E.digest([X.asdict(v) for v in r.account.fills]);old_balance=E.digest(r.account.bridge(at));old_bytes=X.sha(f)
 intents=copy.deepcopy(stage['prepared_intents']);e=copy.deepcopy(stage['evidence']);s,ds,wait=r.provider(at,intents,e);r._init_or_bind(s,intents,e);before=r.budget.dumps()
 X.save(P/'C20_FAILED_PROJECTION_INPUT.json',dict(failed_checkpoint=str(f),failed_checkpoint_sha256=old_bytes,snapshot=s,demands=ds,evidence=e,budget_before=before,actual_financial_events=0))
 cls=X.R.M.BatchBook;book=cls.loads(before,trusted_sha256=hashlib.sha256(before.encode()).hexdigest(),account_id=s['account_id'],source_binding=E.digest(s),actual_commitments=json.loads(before)['body']['lines'])
 trace=[]
 def progress(v):
  trace.append(v);X.save(P/'C20_PURE_SEARCH_PROGRESS.json',dict(seconds=time.perf_counter()-t,completed_candidates=len(trace),last=v,financial_events=0))
 try:
  result=X.R.M.BC.solve_C20(s,ds,e,book=book,max_native_checks=1000000,progress=progress)
  E.require(old_fills==E.digest([X.asdict(v) for v in r.account.fills]) and old_balance==E.digest(r.account.bridge(at)) and X.sha(f)==old_bytes,'pure planning changed finance or original failed bytes')
  X.save(P/'C20_PURE_SEARCH_RESULT.json',dict(pure_result=result,native_checks=result['native_checks'],original_technical_ceiling=100000,diagnostic_technical_ceiling=1000000,seconds=time.perf_counter()-t,financial_events=0,authority_accepted=False,account_continued=False,original_failed_checkpoint_unchanged=True))
  print('PURE_SEARCH_COMPLETED',result['native_checks'],time.perf_counter()-t,flush=True)
 except Exception as ex:
  X.save(P/'C20_PURE_SEARCH_FAILURE.json',dict(error=repr(ex),traceback=traceback.format_exc(),seconds=time.perf_counter()-t,financial_events=0));raise
if __name__=='__main__':main()
