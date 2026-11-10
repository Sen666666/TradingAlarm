"""Unique released DMI arm. Save all raw ledgers before posterior reporting."""
import argparse,time
from collections import Counter
from runtime import O,sha,read,make_consumer,run_isolated,dump_consumer
from dmi_gates import require_release

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True)
    w=p.parse_args().window
    a=require_release(w) # Before original engine import and any economic work.
    from run_economic import save
    dest=O/('dmi_'+w);dest.mkdir(exist_ok=False)
    start=time.monotonic()
    save(dest/'STARTED.json',dict(window=w,authorization_sha256=a['authorization_sha256'],protocol_sha256=a['protocol_sha256']))
    try:
        c=run_isolated(make_consumer(w,'dmi'))
        post=require_release(w)
        assert post==a, 'RELEASE_CHANGED_DURING_ECONOMIC_LOOP'
        save(dest/'DMI_RANK_AUDIT.json',c.dmi_rank_audit)
        dump_consumer(c,dest)
        save(dest/'LOOP_QA.json',dict(status_counts=dict(Counter(r['status'] for r in c.s.rounds)),feature_count=c.feature_count,dmi_rank_rows=len(c.dmi_rank_audit),elapsed_seconds=time.monotonic()-start,raw_ledger_saved=True))
        post=require_release(w)
        assert post==a, 'RELEASE_CHANGED_BEFORE_FINAL_SEAL'
        seal={str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()}
        save(dest/'OUTPUT_SEAL.json',seal)
        for name,h in seal.items():assert sha(dest/name)==h
        save(dest/'COMPLETE_SAVED_SNAPSHOT.json',dict(window=w,authorization_sha256=a['authorization_sha256'],implementation_audit_sha256=a['implementation_audit_sha256'],protocol_sha256=a['protocol_sha256'],output_seal_sha256=sha(dest/'OUTPUT_SEAL.json'),raw_ledger_and_rank_audit_saved=True,legacy_ECONOMIC_LOOP_COMPLETE_scope='Original ledger marker only; consumers must require this complete snapshot and OUTPUT_SEAL',elapsed_seconds=time.monotonic()-start))
        print('DMI_LOOP_SAVED',w,len(c.s.rounds),len(c.s.actions),flush=True)
        # Any posterior failure is recovered from saved ledgers, never a re-run.
    except BaseException as exc:
        save(dest/'FAILED_NO_RETRY.json',dict(error=repr(exc),loop_saved=(dest/'ECONOMIC_LOOP_COMPLETE.json').exists(),complete_snapshot=(dest/'COMPLETE_SAVED_SNAPSHOT.json').exists(),persisted_files=sorted(str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file()),no_retry=True,elapsed_seconds=time.monotonic()-start))
        raise
if __name__=='__main__':main()
