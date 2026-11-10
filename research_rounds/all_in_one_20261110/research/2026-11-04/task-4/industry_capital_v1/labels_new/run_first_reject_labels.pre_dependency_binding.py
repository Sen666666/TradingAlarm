"""One finite native single-asset label pass, only after independent admission."""
from pathlib import Path
from collections import Counter
import argparse,gzip,hashlib,json,time,traceback
from native_single_asset import Provider,O,WORK,read,bind,SOURCES,COUNTS,encoded,LabelDeadline,N

LIMIT=120.0
INPUT=O.parent/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz'
OUTPUT=O/'FIRST_REJECT_SHADOW_LABELS.jsonl.gz'
PARTIAL=O/'FIRST_REJECT_SHADOW_LABELS.partial.jsonl.gz'
GATE=O.parent/'review/FULL_SINGLE_ASSET_LABEL_ADMISSION.json'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,value):(O/name).write_text(json.dumps(encoded(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--execute',action='store_true')
    args=parser.parse_args();assert args.prepare!=args.execute
    sources={str(p.resolve()):sha(p)for p in [Path(__file__),O/'native_single_asset.py',O/'TECHNICAL_CALIBRATION_RESULT.json',O.parent/'MATCHED_PROTOCOL.txt',INPUT]}
    contract=dict(scope='8335 first window/sid/source-I-epoch original sector-rejected CORE; q_min isolated native labels only',
                  single_pass_limit_seconds=LIMIT,new_portfolio_policy_accounts=0,source_sha256=sources)
    if args.prepare:
        save('PROPOSED_FULL_LABEL_CONTRACT.json',contract)
        print('PREPARED_ONLY');return
    assert not OUTPUT.exists()and not PARTIAL.exists(),'Existing full/partial output cannot be silently replayed'
    gate=read(GATE);assert gate['passed']is True and gate['scope']=='first_reject_single_asset_labels'
    for path,digest in sources.items():assert gate['source_sha256'][path]==digest,('source differs from admission',path)
    prepared=time.monotonic();provider=Provider();events=[]
    with gzip.open(bind(INPUT),'rt')as h:
        for line in h:
            r=json.loads(line)
            if r['is_first_sector_reject_in_original_source_I_epoch']:events.append(r)
    assert len(events)==8335
    assert len({(r['window'],r['sid'],tuple(r['original_intent']['epoch']))for r in events})==8335
    save('FULL_LABEL_INPUT_PREPARATION.json',dict(seconds=time.monotonic()-prepared,events=len(events),source_sha256=sources))
    statuses=Counter();completed=0;fail=None;start=time.monotonic();timed_out=False;incomplete_key=None
    provider.deadline=start+LIMIT
    try:
        with gzip.open(PARTIAL,'wt')as out:
            for r in events:
                if time.monotonic()-start>=LIMIT:timed_out=True;break
                COUNTS['label_attempts']+=1
                try:value=provider.path(r)
                except LabelDeadline:
                    timed_out=True;incomplete_key=r['key'];break
                except N.RuleUnavailable as exc:
                    value=dict(key=r['key'],status='unknown_source_exception',known_net=False,
                               unknown_reason=str(exc),new_portfolio_policy_account=False)
                value.update(window=r['window'],sid=r['sid'],signal_day=r['signal_day'],OPEN=r['OPEN'],
                             source_I_epoch=r['original_intent']['epoch'])
                for name in ('entry_cash_actual','initial_seed_cash','net_pnl_original_ledger','terminal_NAV',
                             'horizon_CLOSE_day','terminal_qty','terminal_net_liquidation_estimate',
                             'wealth_from_invested_Cn_excluding_unspent_seed','wealth_from_invested_Cn_net_liquidation'):
                    value.setdefault(name,None)
                value.update(classification=r['classification'],failure_tags=r['failure_tags'],industry=r['industry'],
                             signal_original_PVR=r['original_intent'].get('PVR_score'),
                             original_source_I_epoch=r['original_intent']['epoch'])
                out.write(json.dumps(encoded(value),ensure_ascii=False,allow_nan=False)+'\n')
                completed+=1;statuses[value['status']]+=1
                if completed%100==0:
                    out.flush()
                    save('FULL_LABEL_PROGRESS.json',dict(completed=completed,total=len(events),seconds=time.monotonic()-start,
                        statuses=dict(statuses),counts=dict(COUNTS)))
                    if completed%1000==0:print(json.dumps(dict(completed=completed,seconds=time.monotonic()-start)),flush=True)
    except Exception as exc:
        fail=dict(type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc(),automatic_replay=False)
        save('FULL_LABEL_FAILURE.json',fail)
        raise
    finally:
        save('FULL_LABEL_TIMING.json',dict(completed=completed,total=len(events),seconds=time.monotonic()-start,
              limit_seconds=LIMIT,timed_out=timed_out,statuses=dict(statuses),counts=dict(COUNTS),
              incomplete_path_key=incomplete_key,failure=fail,source_sha256=sources,new_portfolio_policy_accounts=0))
        SOURCES.update(sources);save('FULL_LABEL_SOURCE_SHA256.json',SOURCES)
    if completed==len(events)and not timed_out:
        PARTIAL.rename(OUTPUT)
        save('FULL_LABEL_COMPLETE.json',dict(passed=True,events=completed,output_sha256=sha(OUTPUT),counts=dict(COUNTS),
             seconds=time.monotonic()-start,single_asset_shadow_paths=COUNTS['single_asset_shadow_paths'],new_portfolio_policy_accounts=0,
             interpretation='Conditional isolated native net labels, not a feasible common-capital rotation portfolio'))
    else:
        save('FULL_LABEL_PARTIAL.json',dict(complete=False,events_completed=completed,total=len(events),
             output=str(PARTIAL),timed_out=timed_out,automatic_retry=False))
    print(json.dumps(dict(completed=completed,total=len(events),timed_out=timed_out,statuses=dict(statuses),seconds=time.monotonic()-start)),flush=True)

if __name__=='__main__':main()
