"""Export onsets from frozen E0-NR1 states; no indicator or account is rerun."""
from pathlib import Path
import gzip, json, hashlib, sys
import pandas as pd

ATLAS=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ATLAS/'code'))
from common_atlas import PREPS

def digest(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    with gzip.open(ATLAS/'web/data/index.json.gz','rt') as f:index=json.load(f)
    hashes=json.loads((ATLAS/'packaging-verification.json').read_text())['source_sha256']
    out=ATLAS/'web/data/e0-entry-v1'
    out.mkdir(exist_ok=False)
    total=without_i=rows=prefixes=0
    records=[]
    for sid,meta in index['stocks'].items():
        path=PREPS[meta['sector']]/'facts'/f'{sid}.parquet'
        assert digest(path)==hashes[str(path)],sid
        facts=pd.read_parquet(path)
        assert facts.index.is_unique and facts.index.is_monotonic_increasing
        active=facts.e0_target.eq(1)
        # Full source history and within-segment predecessor: never invent a
        # fresh signal just because the plotted date range begins mid-trend.
        prior=active.groupby(facts.segment_id,sort=False).shift(fill_value=False)
        onset=active&~prior
        with gzip.open(ATLAS/'web/data/prices'/f'{sid}.json.gz','rt') as f:price=json.load(f)
        days={b[0] for b in price['bars']}
        visible=facts.loc[onset]
        visible=visible.loc[[str(t.date()) in days for t in visible.index]]
        assert visible.e0_ready.eq(1).all()
        entries=[str(t.date()) for t in visible.index]
        # Independent sequential scan of stored states, including segment reset.
        expected=[];last_segment=None;was_active=False
        for t,row in facts.iterrows():
            if row.segment_id!=last_segment:was_active=False
            now=bool(row.e0_target)
            if now and not was_active and str(t.date()) in days:expected.append(str(t.date()))
            was_active=now;last_segment=row.segment_id
        assert entries==expected,sid
        for cutoff in ['2024-12-31','2026-06-30']:
            short=facts.loc[:cutoff]
            a=short.e0_target.eq(1)
            starts=a&~a.groupby(short.segment_id,sort=False).shift(fill_value=False)
            assert [str(t.date()) for t in short.index[starts] if str(t.date()) in days]==[d for d in entries if d<=cutoff]
            prefixes+=1
        payload=dict(symbol=sid,algorithm='E0-NR1',definition='e0_target: 0→1 within source segment; close-confirmed, independent of I/S/RS/account',entries=entries,source_sha256=digest(path))
        with (out/f'{sid}.json.gz').open('xb') as f:
            with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as z:z.write(json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode())
        n=int((~visible.i_buy.astype(bool)).sum())
        records.append(dict(symbol=sid,sector=meta['sector'],entries=len(entries),onsets_without_i_buy=n,source=str(path),sha256=digest(path)))
        total+=len(entries);without_i+=n;rows+=len(price['bars'])
    proof=dict(passed=True,stocks=len(records),real_candles=rows,e0_onsets=total,onsets_without_i_buy=without_i,stored_state_prefix_checks=prefixes,independent_sequential_state_scan_exact=True,source_hashes_unchanged=True,existing_price_and_account_files_rewritten=0,new_indicator_runs=0,new_backtests=0,records=records)
    (ATLAS/'e0-markers-20261029/data-verification.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in proof.items() if k!='records'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
