"""Import/binding/canonical gates only; no financial event."""
from pathlib import Path
from dataclasses import replace
import subprocess,sys,copy,json,pickle
import c_horizon as C
HERE=C.HERE;E=C.E
def main():
 C.guard();assert C.read(HERE/'INPUT_GATE.json')['passed'];rows=[]
 for window in C.DATES:
  for mode in ('C10','C_BATCH20'):
   for branch in ('full','physical'):
    out=HERE/'runs'/(window+'-'+mode)/branch;progress=out/'PROGRESS.json'
    if progress.exists():assert C.read(progress)['phase']=='IMPORT','preflight cannot rerun after finance'
    else:
     log=HERE/('IMPORT-'+window+'-'+mode+'-'+branch)
     with log.with_suffix('.out').open('w') as so,log.with_suffix('.err').open('w') as se:
      z=subprocess.run([sys.executable,'-B',str(HERE/'day_driver.py'),'--window',window,'--mode',mode,'--branch',branch,'--phase','IMPORT'],stdout=so,stderr=se)
     if z.returncode:raise RuntimeError('import failed '+str(log))
    cp=Path(C.read(progress)['checkpoint']);r=C.HorizonRunner.restore(cp);before=C.E.digest(C.prefix_view(r));a=r.account
    pending=[i['receipt'] for i in a.pending if i['receipt'] is not None]
    assert all(a.receipt_verified(c) for c in pending)
    # Strict horizon rejection must occur before ANY financial mutation.
    for bad in [C.P.EXPECTED[window][-1],('2022-01-07' if window=='2022' else '2025-07-04')]:
     try:r.step(bad,'OPEN')
     except ValueError:pass
     else:raise AssertionError('unapproved day accepted')
     assert C.E.digest(C.prefix_view(r))==before
    # Source tamper rejection, on a memory-only copy of authorization.
    real=C.read
    fake=copy.deepcopy(real(HERE/'AUTHORIZATION.json'));fake['sources'][str(HERE/'c_horizon.py')]='0'*64
    try:
     C.read=lambda p:fake if Path(p)==HERE/'AUTHORIZATION.json' else real(p)
     try:C.guard()
     except ValueError:pass
     else:raise AssertionError('wrong binding accepted')
    finally:C.read=real
    assert C.E.digest(C.prefix_view(r))==before
    clone=pickle.loads(pickle.dumps(r));at=E.iso(C.DATES[window]+'T15:10:00+08:00');clone.account.market.refresh(at);packet=clone.stock_packet(at)
    fresh=[v['receipt'] for v in packet.values() if v.get('receipt')]
    assert fresh and all(clone.account.receipt_verified(c) for c in fresh)
    assert all(not clone.account.receipt_verified(replace(c,source_binding=clone.account.old_canonical_binding)) for c in fresh)
    rows.append(dict(window=window,mode=mode,branch=branch,complete_prefix_exact=True,old_valid_receipts=len(pending),next_day_canonical=len(fresh),wrong_generation_rejected=True,wrong_source_rejected=True,old_and_future_finance_dates_rejected=True,financial_events=0))
    print('PREFLIGHT',window,mode,branch,flush=True)
 E.IO.write_json(HERE/'PREFLIGHT_GATE.json',dict(passed=True,rows=rows,accounts_constructed=0,financial_events=0),encoder=E.encode)
if __name__=='__main__':main()
