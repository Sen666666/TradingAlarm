"""Once per released window. No posterior report or economic retry in this file."""
import argparse,time,traceback
from collections import Counter
from runtime import O,sha,read,save,make_consumer,run_isolated,dump_consumer
from release import require_release,claim_once

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2024'],required=True);w=p.parse_args().window
    a=require_release(w);claim_once(w,a) # Lock BEFORE engine initialization.
    dest=O/('gate_'+w);dest.mkdir(exist_ok=False);c=None;start=time.monotonic()
    save(dest/'STARTED.json',dict(window=w,authorization_sha256=a['authorization_sha256'],protocol_sha256=a['protocol_sha256']))
    try:
        c=make_consumer(w);run_isolated(c)
        assert require_release(w)==a,'RELEASE_CHANGED_DURING_LOOP'
        dump_consumer(c,dest)
        save(dest/'LOOP_QA.json',dict(status_counts=dict(Counter(r['status'] for r in c.s.rounds)),feature_count=c.feature_count,gate_reads=len(c.entry_gate_audit),elapsed_seconds=time.monotonic()-start))
        assert require_release(w)==a,'RELEASE_CHANGED_BEFORE_SEAL'
        seal={str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()};save(dest/'OUTPUT_SEAL.json',seal)
        for name,h in seal.items():assert sha(dest/name)==h
        save(dest/'COMPLETE_SAVED_SNAPSHOT.json',dict(window=w,authorization_sha256=a['authorization_sha256'],implementation_audit_sha256=a['implementation_audit_sha256'],protocol_sha256=a['protocol_sha256'],output_seal_sha256=sha(dest/'OUTPUT_SEAL.json'),raw_ledger_saved=True,elapsed_seconds=time.monotonic()-start))
        print('GATE_LOOP_SAVED',w,len(c.s.rounds),len(c.s.actions),flush=True)
    except BaseException as exc:
        # Preserve in-memory partial ledgers without finalizing, advancing, or retrying.
        if c is not None:
            from run_economic import save as oldsave
            oldsave(dest/'PARTIAL_RAW_STATE.json',dict(rounds=c.s.rounds,actions=c.s.actions,decisions=c.s.decisions,ranking_audit=c.s.ranking_audit,states=c.states,archives=c.s.archives,claims=c.s.claims,price_audit=c.price_audit,offer_audit=c.offer_audit,entry_gate_audit=c.entry_gate_audit,books={rid:dict(responsibility=b.responsibility(),parents=b.parents,orders=b.orders,lots=b.lots,events=b.events) for rid,b in c.books.items()}))
        save(dest/'FAILED_NO_RETRY.json',dict(error=repr(exc),traceback=traceback.format_exc(),loop_saved=(dest/'ECONOMIC_LOOP_COMPLETE.json').exists(),no_retry=True,elapsed_seconds=time.monotonic()-start))
        save(dest/'FAILED_OUTPUT_SEAL.json',{str(p.relative_to(dest)):sha(p) for p in dest.rglob('*') if p.is_file()})
        raise
if __name__=='__main__':main()
