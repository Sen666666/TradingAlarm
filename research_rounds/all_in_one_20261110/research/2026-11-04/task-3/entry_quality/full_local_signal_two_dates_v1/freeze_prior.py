"""Freeze each fixed day's complete known-i_buy cohort before future labels."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
RANKS={'ALL':'rank_ALL_LOCAL_I_BUY','OLD':'rank_OLD1709_STATIC_REFERENCE_I_BUY','OUTSIDE':'rank_OUTSIDE_OLD1709_I_BUY'}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(day):
    b=ROOT/day;output=b/'FROZEN_IBUY_PRIOR_RANKS.parquet'
    assert not output.exists(), 'Frozen prior cohort is immutable; do not replace'
    source=b/'FULL5517_CANDIDATES.parquet';x=pd.read_parquet(source)
    assert len(x)==5517 and x.day.eq(day).all()
    x=x.loc[x.i_buy_research.eq(True)].copy()
    fields=['sid','day','score','pvr_status','research_PVR_pool','current_close_qfq','raw_close',
        'in_old1709_exact','current_name']+list(RANKS.values())
    x=x[fields].copy();x['PVR_rank_unknown']=x.rank_ALL_LOCAL_I_BUY.isna()
    scopes={}
    for label,col in RANKS.items():
        mask=pd.Series(True,index=x.index)if label=='ALL'else x.in_old1709_exact.eq(label=='OLD')
        known=mask&x[col].notna();N=int(known.sum());signalN=int(mask.sum())
        assert sorted(x.loc[known,col].astype(int))==list(range(1,N+1))
        ordered=x.loc[known].sort_values(['score','sid'],ascending=[False,True])
        assert ordered[col].is_monotonic_increasing
        name='decile_'+label;x[name]=pd.Series(pd.NA,index=x.index,dtype='Int64')
        if N:x.loc[known,name]=(x.loc[known,col].astype(int)-1)*10//N+1
        scopes[label]=dict(rank_column=col,signal_N=signalN,rankable_N=N,PVR_unknown_N=signalN-N,
            top20_N=min(20,N),rest20_rankable_N=max(0,N-20),top100_N=min(100,N),rest100_rankable_N=max(0,N-100),
            decile_counts={int(k):int(v)for k,v in x.loc[known,name].value_counts().sort_index().items()})
    assert x.research_PVR_pool.eq(~x.PVR_rank_unknown).all()
    x=x.sort_values(['rank_ALL_LOCAL_I_BUY','sid'],na_position='last').reset_index(drop=True)
    x.to_parquet(output,index=False,compression='zstd');x.to_csv(b/'FROZEN_IBUY_PRIOR_RANKS.csv',index=False)
    r=dict(status='FROZEN_COMPLETE_IBUY_BEFORE_FUTURE_LABELS',day=day,N=len(x),scopes=scopes,
        unknown_PVR_serialized_last_only_for_storage_not_fabricated_rank=True,
        missing_rank_rule='ALL includes allknownTruei_buy; decile/TOP/REST only known ranks; RANKABLE and PVR_UNKNOWN buckets preserve denominator.',
        source_candidate_sha256=sha(source),prior_rank_sha256=sha(output),freeze_sha256=sha(b/'FREEZE.json'),
        code_sha256=sha(__file__),future_labels_read=False)
    (b/'PRIOR_RANKS_RECEIPT.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(r,ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--day',choices=['2022-01-24','2026-01-15'],required=True);main(p.parse_args().day)
