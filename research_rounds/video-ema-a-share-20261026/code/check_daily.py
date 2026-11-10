"""Independent EMA recurrence and physical prefix checks; no account calls."""
from pathlib import Path
import json,hashlib,math
import pandas as pd
import numpy as np

HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]

def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
    return h.hexdigest()

def main():
    out=HERE/'technical';out.mkdir(exist_ok=False);prefix=out/'physical-prefix';prefix.mkdir()
    freeze=json.loads((HERE/'daily-freeze.json').read_text())
    for name,h in freeze['source_hashes'].items():
        p=Path(name);p=p if p.is_absolute() else ROOT/p
        assert sha(p)==h,(name,'source changed')
    cases=pd.read_csv(HERE/'raw/cases.csv');checks=0;prefixes=[]
    for _,case in cases.iterrows():
        source=ROOT/'research_rounds/ix-a-share-entry-20261025/signals'/(case.symbol+'.parquet')
        raw=pd.read_parquet(source,columns=['segment_id','open','high','low','close','volume'])
        full=pd.read_parquet(HERE/'daily-facts'/(case.symbol+'.parquet'))
        cutoff=pd.Timestamp(case.anchor);part=raw.loc[:cutoff]
        p=prefix/(case['case']+'.parquet');part.to_parquet(p)
        truncated=pd.read_parquet(p)
        for n in [9,21,50,150]:
            expected=truncated.groupby('segment_id',sort=False).close.transform(lambda x:x.ewm(span=n,adjust=False,min_periods=n).mean())
            pd.testing.assert_series_equal(expected,full.loc[:cutoff,'ema'+str(n)],check_names=False,check_exact=True)
            # Separate scalar recurrence verifies all nonmissing source segments.
            a=2/(n+1)
            for _,g in truncated.groupby('segment_id',sort=False):
                if not np.isfinite(g.close).all():continue
                v=None
                for k,(day,px) in enumerate(g.close.items(),1):
                    v=float(px) if v is None else a*float(px)+(1-a)*v
                    actual=full.loc[day,'ema'+str(n)]
                    if k<n:assert pd.isna(actual)
                    else:assert math.isclose(v,float(actual),rel_tol=2e-12,abs_tol=2e-12)
                    checks+=1
        prefixes.append(dict(case=case['case'],symbol=case.symbol,cutoff=str(cutoff.date()),rows=len(truncated),passed=True))
    prior=ROOT/'research_rounds/a-share-local-entry-reentry-20261026/complete.json';old=json.loads(prior.read_text())
    for name,h in old['artifacts'].items():assert sha(ROOT/name)==h,('old LER changed',name)
    reg=json.loads((ROOT/'research_rounds/algorithm-baselines-20261024/registry.json').read_text())
    for name,h in reg['sha256'].items():assert sha(ROOT/name)==h,('E0/R/R1 changed',name)
    report=dict(passed=True,kind='Daily preparation only; not financial admission',independent_EMA_row_checks=checks,physical_daily_prefixes=prefixes,
        source_hash_checks=len(freeze['source_hashes']),old_LER_artifact_checks=len(old['artifacts']),E0_R_R1_hash_checks=len(reg['sha256']),economic_accounts=0,
        rules_draft_sha256=sha(HERE/'RULES_FOR_REVIEW.md'),code_sha256=sha(__file__))
    with (out/'daily-checks.json').open('x') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k!='physical_daily_prefixes'},ensure_ascii=False))

if __name__=='__main__':main()
