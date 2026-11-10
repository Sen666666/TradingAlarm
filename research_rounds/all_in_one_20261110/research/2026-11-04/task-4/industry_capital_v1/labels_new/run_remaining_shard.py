"""Resource-only disjoint continuation; original native path helper is unchanged."""
from pathlib import Path
from collections import Counter
import argparse,gzip,hashlib,json,time,traceback
from native_single_asset import Provider,O,WORK,read,SOURCES,COUNTS,encoded,LabelDeadline,N,dependency_hashes

PLAN=O/'remaining_shards/REMAINING_SHARD_PLAN.json'
CARD=O/'RESOURCE_CONTINUATION_CARD.txt'
FREEZE=O/'CONTINUATION_SOURCE_FREEZE.json'
GATE=O.parent/'review/REMAINING_SINGLE_ASSET_CONTINUATION_ADMISSION.json'
OLD=O/'FIRST_REJECT_SHADOW_LABELS.partial.jsonl.gz'
MOTHER=O.parent/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz'
FINAL=O/'FIRST_REJECT_SHADOW_LABELS.jsonl.gz'
LIMIT=90.0
MARGIN=0.5

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(encoded(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def rawlines(p):
    with gzip.open(p,'rb')as h:
        yield from h

def sources():
    plan=json.loads(PLAN.read_text())
    files=[Path(__file__),CARD,PLAN,OLD,MOTHER,O/'native_single_asset.py',O/'FULL_LABEL_TIMING.json',
           O/'TECHNICAL_CALIBRATION_RESULT.json',O.parent/'MATCHED_PROTOCOL.txt']
    files += [Path(s['event_file'])for s in plan['shards']]
    result={str(p.resolve()):sha(p)for p in files};result.update(dependency_hashes());return result

def prepare():
    start=time.monotonic();plan=json.loads(PLAN.read_text())
    assert plan['already_complete']==3879 and plan['remaining']==4456 and len(plan['shards'])==4
    freeze=dict(scope='remaining4456_same_native_minimum_unit_labels_disjoint_SID_continuation',
         shard_ids=[0,1,2,3],events_per_shard=1114,per_worker_limit_seconds=LIMIT,
         per_path_deadline_margin_seconds=MARGIN,total_additional_limit_seconds=360,
         original_label_compute_seconds=120.10009508393705,
         source_sha256=sources(),no_new_portfolio_policy_accounts=True)
    save(FREEZE,freeze)
    save(O/'CONTINUATION_PREPARATION.json',dict(seconds=time.monotonic()-start,
         new_single_asset_shadow_paths=0,execution_started=False,source_freeze_sha256=sha(FREEZE)))
    print('PREPARED_ONLY',sha(FREEZE))

def admitted():
    gate=json.loads(GATE.read_text());f=json.loads(FREEZE.read_text())
    assert gate['passed']is True and gate['scope']=='remaining_single_asset_labels_resource_continuation'
    assert gate['source_freeze_sha256']==sha(FREEZE)
    assert f['source_sha256']==sources(),'Continuation source changed'
    return f

def execute(shard):
    admitted();plan=json.loads(PLAN.read_text());spec=next(s for s in plan['shards']if s['shard']==shard)
    outdir=O/'remaining_shards'/f'worker{shard}';outdir.mkdir(exist_ok=False)
    prepared=time.monotonic();provider=Provider()
    with gzip.open(spec['event_file'],'rt')as h:events=list(map(json.loads,h))
    assert len(events)==1114 and [r['key']for r in events]==spec['keys']
    save(outdir/'INPUT_PREPARATION.json',dict(seconds=time.monotonic()-prepared,events=1114))
    start=time.monotonic();provider.deadline=start+LIMIT-MARGIN
    statuses=Counter();completed=0;timed=False;incomplete=None;failure=None
    partial=outdir/'LABELS.partial.jsonl.gz'
    try:
        with gzip.open(partial,'wt')as out:
            for r in events:
                COUNTS['label_attempts']+=1
                try:value=provider.path(r)
                except LabelDeadline:timed=True;incomplete=r['key'];break
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
                    out.flush();save(outdir/'PROGRESS.json',dict(completed=completed,total=1114,
                         seconds=time.monotonic()-start,statuses=dict(statuses),counts=dict(COUNTS)))
    except Exception as exc:
        failure=dict(type=type(exc).__name__,error=str(exc),traceback=traceback.format_exc())
        save(outdir/'FAILURE.json',failure);raise
    finally:
        save(outdir/'TIMING.json',dict(completed=completed,total=1114,seconds=time.monotonic()-start,
            limit_seconds=LIMIT,path_deadline_seconds=LIMIT-MARGIN,timed_out=timed,incomplete_key=incomplete,
            statuses=dict(statuses),counts=dict(COUNTS),failure=failure,new_portfolio_policy_accounts=0))
        save(outdir/'SOURCE_SHA256.json',SOURCES)
    if completed==1114 and not timed:
        target=outdir/'LABELS.jsonl.gz';partial.rename(target)
        save(outdir/'COMPLETE.json',dict(passed=True,events=1114,output_sha256=sha(target),
            helper_sha256=sha(O/'native_single_asset.py'),counts=dict(COUNTS)))
    else:save(outdir/'PARTIAL.json',dict(complete=False,completed=completed,automatic_retry=False))
    print(json.dumps(dict(shard=shard,completed=completed,seconds=time.monotonic()-start,timed_out=timed)),flush=True)

def merge():
    admitted();start=time.monotonic();assert not FINAL.exists()
    original=list(rawlines(OLD));assert len(original)==3879
    rows={json.loads(line)['key']:line for line in original};assert len(rows)==3879
    linehash={json.loads(line)['key']:hashlib.sha256(line).hexdigest()for line in original}
    original_prefix_hash=hashlib.sha256(b''.join(original)).hexdigest()
    worker_times=[];initializations=0;attempts=0
    for shard in range(4):
        folder=O/'remaining_shards'/f'worker{shard}'
        done=json.loads((folder/'COMPLETE.json').read_text());assert done['passed']and done['events']==1114
        file=folder/'LABELS.jsonl.gz';assert sha(file)==done['output_sha256']
        for line in rawlines(file):
            key=json.loads(line)['key'];assert key not in rows;rows[key]=line
        timing=json.loads((folder/'TIMING.json').read_text());worker_times.append(timing['seconds'])
        initializations+=timing['counts'].get('single_asset_shadow_paths',0)
        attempts+=timing['counts'].get('label_attempts',0)
    assert len(rows)==8335
    order=[];windows=Counter()
    for line in rawlines(MOTHER):
        r=json.loads(line)
        if r['is_first_sector_reject_in_original_source_I_epoch']:
            order.append(r['key']);windows[r['window']]+=1
    assert len(order)==len(set(order))==8335 and set(order)==set(rows)
    assert windows==Counter(long=5264,strong=3071)
    with gzip.open(FINAL,'wb')as out:
        for key in order:out.write(rows[key])
    merged=list(rawlines(FINAL))
    assert merged[:3879]==original
    assert hashlib.sha256(b''.join(merged[:3879])).hexdigest()==original_prefix_hash
    assert all(hashlib.sha256(rows[key]).hexdigest()==digest for key,digest in linehash.items())
    save(O/'ORIGINAL_COMPLETED_LINE_SHA256.json',dict(original_partial_sha256=sha(OLD),
         decompressed_original_prefix_sha256=original_prefix_hash,line_sha256=linehash))
    first=json.loads((O/'FULL_LABEL_TIMING.json').read_text())
    result=dict(passed=True,events=8335,windows=dict(windows),old_completed3879_exact_bytes_preserved=True,
         new_continuation_events=4456,worker_compute_seconds=worker_times,
         additional_compute_seconds=sum(worker_times),additional_compute_limit_seconds=360,
         original_compute_seconds=first['seconds'],total_label_compute_seconds=first['seconds']+sum(worker_times),
         single_asset_shadow_paths=first['counts']['single_asset_shadow_paths']+initializations,
         label_attempts=first['counts']['label_attempts']+attempts,new_portfolio_policy_accounts=0,
         merge_seconds=time.monotonic()-start,output_sha256=sha(FINAL),source_freeze_sha256=sha(FREEZE),
         scope='Complete unchanged first-reject isolated native labels, not common-capital rotation returns')
    assert result['additional_compute_seconds']<=360
    save(O/'FULL_LABEL_COMPLETE.json',result);save(O/'CONTINUATION_MERGE.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--execute',action='store_true');p.add_argument('--merge',action='store_true');p.add_argument('--shard',type=int,choices=range(4))
    a=p.parse_args();assert sum((a.prepare,a.execute,a.merge))==1
    if a.prepare:prepare()
    elif a.execute:assert a.shard is not None;execute(a.shard)
    else:merge()
