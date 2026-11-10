"""Recover static output after the representation-only comparator failure."""
from c_batch20 import *
import time,traceback

def main():
    f=read(O/'AUTHORIZATION_AND_FREEZE.json');guard()
    assert all(sha(O/n)==h for n,h in f['code'].items()),'frozen model/original runner changed'
    assert read(O/'SYNTHETIC_RESULTS.json')['passed']
    save(O/'EXPORT_RECOVERY_BINDING.json',dict(reason='Decimal versus JSON string comparator',model_source_unchanged=True,
        recovery_source_sha256=sha(__file__),original_freeze_sha256=sha(O/'AUTHORIZATION_AND_FREEZE.json'),
        preserved_failure='failure-export-representation-v1',scope='failed Jul3 pure target export + not-yet-run Jan6 target',financial_events=0))
    for k in ('2025_26','2022'):
        out=O/'results'/k
        if (out/'C20.json').exists():raise RuntimeError('completed result exists; no silent recompute')
        x=read(O/'inputs'/(k+'.json'));start=time.monotonic();history=[]
        try:
            def progress(row):
                history.append(row);save(out/'RECOVERY_PROGRESS.json',dict(completed=history,seconds=time.monotonic()-start,financial_events=0))
                if time.monotonic()-start>180:raise RuntimeError('static time bound')
            r=solve_C20(x['snapshot'],x['B_demands'],x['industry_evidence'],progress=progress)
            save(out/'COMPUTED_BEFORE_IDENTITY_CHECK.json',r)
            prior=read(O.parent/'g-s-C-batch20-projection-v1-20261102/results'/k/'C20.json')
            checked=['Q','D','mobile_targets','donors','validation','batch20','trace','native_checks']
            equal={key:J.digest(r[key])==J.digest(prior[key]) for key in checked};assert all(equal.values()),equal
            save(out/'R1_ECONOMIC_IDENTITY.json',dict(exact=True,fields=equal,comparison='canonical JSON digest',financial_events=0))
            save(out/'C20.json',r);save(out/'RUN.json',dict(seconds=time.monotonic()-start,completed=True,
                original_module_globals_unchanged=True,export_recovery=True,financial_events=0))
            print('R2_READY',k,sum(bool(q) for q in r['Q'].values()),round(time.monotonic()-start,2),flush=True)
        except BaseException as exc:
            save(out/'RECOVERY_ERROR.json',dict(error=repr(exc),traceback=traceback.format_exc(),completed=history,financial_events=0));raise

if __name__=='__main__':main()
