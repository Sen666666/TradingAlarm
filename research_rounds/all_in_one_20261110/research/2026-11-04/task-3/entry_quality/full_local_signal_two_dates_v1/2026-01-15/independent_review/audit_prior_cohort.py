"""Read only full signal mother and prelabel ranks; never reads future paths."""
from pathlib import Path
import json,hashlib
import numpy as np,pandas as pd

R=Path(__file__).resolve().parents[1];O=R/'independent_review';DAY=R.name
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    receipt=json.loads((R/'PRIOR_RANKS_RECEIPT.json').read_text());priorpath=R/'FROZEN_IBUY_PRIOR_RANKS.parquet';source=R/'FULL5517_CANDIDATES.parquet'
    assert sha(priorpath)==receipt['prior_rank_sha256']and sha(source)==receipt['source_candidate_sha256']and sha(R/'FREEZE.json')==receipt['freeze_sha256']
    assert sha(R.parent/'freeze_prior.py')==receipt['code_sha256']
    p=pd.read_parquet(priorpath).set_index('sid').sort_index();x=pd.read_parquet(source).set_index('sid');expected=x[x.i_buy_research.eq(True)]
    assert len(p)==receipt['N']and set(p.index)==set(expected.index)
    for c in ['day','score','pvr_status','research_PVR_pool','current_close_qfq','raw_close','in_old1709_exact','current_name','rank_ALL_LOCAL_I_BUY','rank_OLD1709_STATIC_REFERENCE_I_BUY','rank_OUTSIDE_OLD1709_I_BUY']:
        pd.testing.assert_series_equal(p[c].sort_index(),expected[c].sort_index(),check_names=False,check_dtype=False)
    assert p.day.eq(DAY).all()and p.PVR_rank_unknown.eq(p.rank_ALL_LOCAL_I_BUY.isna()).all()
    assert p.research_PVR_pool.eq(~p.PVR_rank_unknown).all()
    scopes={}
    for scope,column in [('ALL','rank_ALL_LOCAL_I_BUY'),('OLD','rank_OLD1709_STATIC_REFERENCE_I_BUY'),('OUTSIDE','rank_OUTSIDE_OLD1709_I_BUY')]:
        mask=pd.Series(True,index=p.index)if scope=='ALL'else p.in_old1709_exact.eq(scope=='OLD')
        g=p[mask];known=g[column].notna();n=int(known.sum());unknown=int((~known).sum())
        q=g[known].reset_index().sort_values(['score','sid'],ascending=[False,True]);assert q[column].tolist()==list(range(1,n+1))
        d=1+(np.arange(n,dtype=np.int64)*10//n)if n else np.array([],int)
        assert np.array_equal(q['decile_'+scope].to_numpy(int),d)and g.loc[~known,'decile_'+scope].isna().all()
        result={'rank_column':column,'signal_N':len(g),'rankable_N':n,'PVR_unknown_N':unknown,'top20_N':int(g[column].le(20).sum()),'rest20_rankable_N':int(g[column].gt(20).sum()),'top100_N':int(g[column].le(100).sum()),'rest100_rankable_N':int(g[column].gt(100).sum()),'decile_counts':{str(int(k)):int(v)for k,v in pd.Series(d).value_counts().sort_index().items()}}
        for k in [20,100]:assert result[f'top{k}_N']==min(k,n)and result[f'rest{k}_rankable_N']==max(0,n-k)and result[f'top{k}_N']+result[f'rest{k}_rankable_N']+unknown==len(g)
        existing=receipt['scopes'][scope];assert result=={**existing,'decile_counts':{str(k):v for k,v in existing['decile_counts'].items()}}
        scopes[scope]=result
    unknown=[]
    for sid,row in p[p.PVR_rank_unknown].iterrows():
        s=x.loc[sid];unknown.append({'sid':sid,'pvr_status':row.pvr_status,'score':None,'rank':None,'price_observations':int(s.current_block_observations_through_t),'e0_ready':int(s.e0_ready),'g_ready':bool(s.g_ready),'i_target':int(s.i_target),'raw_i_buy':bool(s.i_buy),'interpreted_i_buy':bool(s.i_buy_research)})
    result={'status':'PASS_BOUNDED_FULL_IBUY_PRIOR_AND_UNKNOWN_PVR_DENOMINATORS','day':DAY,'remaining_blocks':[],'N':len(p),'scopes':scopes,'unknownPVR_members_preserved':unknown,'future_labels_read_in_review':False,'new_models':0,'new_accounts':0,'notes':['ALL includes knownTrue i_buy with missingPVR. Rank groups do not absorb them; unknown is explicit, not score0 or fake last rank.','TOP100 may equal whole known-rank subgroup with REST100N0; not forced100.','Prior files and source candidates/code hashes agree. The documented workflow freezes this cohort before paths; this audit itself never opens future labels.','This is original stock signal membership, not fullS0/order/PIT certification.'],'source_sha256':{str(p.resolve()):sha(p)for p in[priorpath,R/'PRIOR_RANKS_RECEIPT.json',source,R/'FREEZE.json',R.parent/'freeze_prior.py',Path(__file__)]}}
    path=O/'PRIOR_COHORT_AUDIT.json';path.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n');print(json.dumps({'status':result['status'],'day':DAY,'sha256':sha(path),'N':len(p),'scopes':scopes,'unknownPVR':unknown},ensure_ascii=False))
if __name__=='__main__':main()
