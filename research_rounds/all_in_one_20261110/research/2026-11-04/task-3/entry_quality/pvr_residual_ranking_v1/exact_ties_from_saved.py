"""Recover the frozen rational score's exact ties from saved components only."""
from pathlib import Path
import hashlib,json,time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OLD=ROOT/'run_v1'
OUT=ROOT/'run_v1_exact_ties'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
    with p.open('x') as f: json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

def main():
    start=time.monotonic(); OUT.mkdir(exist_ok=False)
    sources={str(p.resolve()):sha(p)for p in[Path(__file__),ROOT/'FREEZE.json',ROOT/'EXACT_TIE_CLARIFICATION.json',OLD/'COMPLETION.json',OLD/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet']}
    x=pd.read_parquet(OLD/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet')
    known=x.rank_status.eq('KNOWN'); n=x.loc[known,'n_common']; unit=2*(n-1)
    cols={'S':'residual_percentile','S_naive_RS':'q','S_isotonic':'isotonic_residual_percentile'}
    changed={}; grouped=[]
    for name,rc in cols.items():
        parts=[]
        for col in ['p',rc,'structure_percentile']:
            raw=x.loc[known,col]*unit; rounded=np.rint(raw)
            assert np.allclose(raw,rounded,rtol=0,atol=1e-10)
            parts.append(rounded.astype('int64'))
        numerator=5*parts[0]+3*parts[1]+2*parts[2]
        x.loc[known,name+'_exact_numerator']=numerator
        exact=numerator/(20*(n-1))
        assert np.allclose(exact,x.loc[known,name],rtol=0,atol=5e-16)
        x.loc[known,name]=exact
        oldrank=x[name+'_common_rank'].copy()
        for _,g in x.loc[known].groupby(['window','day','sector'],sort=False):
            order=g.sort_values([name+'_exact_numerator','original_H1_rank','sid'],ascending=[False,True,True]).index
            x.loc[order,name+'_common_rank']=np.arange(1,len(g)+1)
            if name!='S_naive_RS':
                dest='hybrid_S_pending_slot'if name=='S'else'hybrid_S_isotonic_pending_slot'
                x.loc[order,dest]=np.sort(g.original_PVR_slot.to_numpy(int))
        changed[name]=int((oldrank[known]!=x.loc[known,name+'_common_rank']).sum())
    for nm,dest in [('hybrid_S_pending_slot','hybrid_S_sector_rank'),('hybrid_S_isotonic_pending_slot','hybrid_S_isotonic_sector_rank')]:
        x[dest]=x.groupby(['window','day','sector'])[nm].rank(method='first').astype(int)
        assert (x.loc[~known,nm]==x.loc[~known,'original_PVR_slot']).all()
        for _,g in x.groupby(['window','day','sector'],sort=False):
            assert sorted(g[nm])==sorted(g.original_PVR_slot)
    for w,g in x.groupby('window'):
        kg=g[g.rank_status.eq('KNOWN')]
        grouped.append(dict(window=w,legal_rows=len(g),known_rows=len(kg),
          S_vs_PVR_changed_rows=int((kg.hybrid_S_pending_slot!=kg.original_PVR_slot).sum()),
          S_vs_isotonic_changed_rows=int((kg.S_common_rank!=kg.S_isotonic_common_rank).sum())))
    x.to_parquet(OUT/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet',index=False)
    for filename in ['ALL_FIXED_TARGET_DATES.csv','ALL_SAME_DAY_INDUSTRY_COMPETITORS.csv','EARLY_FIXED_CASE_TABLE.csv']:
        old=pd.read_csv(OLD/filename,usecols=['window','day','sid'])
        new=old.merge(x,on=['window','day','sid'],how='left',validate='one_to_one')
        assert len(new)==len(old)
        # Preserve each original table's practical presentation columns plus exact keys.
        columns=list(pd.read_csv(OLD/filename,nrows=0).columns)+[a+'_exact_numerator'for a in cols]
        new[columns].to_csv(OUT/filename,index=False)
    detail=x.loc[known,['window','day','sector','sid','S_common_rank','S_isotonic_common_rank']]
    old=pd.read_parquet(OLD/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet',columns=['window','day','sid','S_common_rank','S_isotonic_common_rank'])
    cmp=detail.merge(old,on=['window','day','sid'],suffixes=('_exact','_IEEE'),validate='one_to_one')
    cmp=cmp[(cmp.S_common_rank_exact!=cmp.S_common_rank_IEEE)|(cmp.S_isotonic_common_rank_exact!=cmp.S_isotonic_common_rank_IEEE)]
    cmp.to_csv(OUT/'CHANGED_TIE_ORDER_ROWS.csv',index=False)
    save(OUT/'NUMERIC_ORDER_AUDIT.json',dict(changed_rank_rows=changed,by_window=grouped,cohorts_features_fits_unchanged=True,
      exact_numerator_validated=True,industry_slot_sets_preserved=True,unknown_slots_fixed=True,
      future_labels_loaded=False,new_accounts=0,elapsed_seconds=time.monotonic()-start))
    save(OUT/'COMPLETION.json',dict(status='COMPLETE_EXACT_MATHEMATICAL_TIES_FROM_SAVED_ONLY',sources=sources,
      outputs={p.name:sha(p)for p in OUT.iterdir()if p.is_file()},new_accounts=0))
    print(json.dumps(dict(changed=changed,by_window=grouped),indent=2))

if __name__=='__main__':main()
