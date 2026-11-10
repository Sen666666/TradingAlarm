"""Read-only per-arm projections for the existing independent finance reader."""
from pathlib import Path
import gzip, hashlib, json, os


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def export(root):
    root=Path(root); pair=root/'pair'
    done=json.loads((root/'DONE.json').read_text()); arms=list(done['ending_NAV'])
    index={}
    for arm in arms:
        out=root/'arms'/arm; dest=out/'pair'; dest.mkdir(parents=True,exist_ok=True)
        target=dest/'B.json.gz'; source=pair/(arm+'.json.gz')
        if target.exists():assert sha(target)==sha(source)
        else:os.link(source,target)
        index[arm]=dict(source_book=str(source),source_book_sha256=sha(source),
                        view_book=str(target),only_stream_account_label_normalized_to_B=True)
        (out/'DONE.json').write_text(json.dumps(dict(completed=True,ending_NAV={'B':done['ending_NAV'][arm]},
                  source_run=str(root),source_account=arm,projection_only_no_account_events=True),indent=2)+'\n')
    for name in ('daily','balances','opportunities','funding','industry','rank-policy'):
        source=pair/(name+'.jsonl.gz')
        if not source.exists():continue
        writers={a:gzip.open(root/'arms'/a/'pair'/(name+'.jsonl.gz'),'wt')for a in arms}
        try:
            with gzip.open(source,'rt')as f:
                for line in f:
                    row=json.loads(line);arm=row['account'];row['account']='B'
                    writers[arm].write(json.dumps(row,ensure_ascii=False)+'\n')
        finally:
            for f in writers.values():f.close()
    (root/'ARM_VIEW_INDEX.json').write_text(json.dumps(index,indent=2)+'\n')
    return index
