"""Saved same-pool three-queue audit only; no feature/model recomputation."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

BASE=Path(__file__).resolve().parents[1];D=BASE/'dual_same_pool';OUT=Path(__file__).resolve().parent
KEY=['sid','day'];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def half_rank(s):
    v=sorted(s.tolist());m={};i=0
    while i<len(v):
        j=i+1
        while j<len(v)and v[j]==v[i]:j+=1
        m[v[i]]=i+j-1;i=j
    return s.map(m).astype('int64')
def equal(a,b):np.testing.assert_allclose(np.asarray(a,float),np.asarray(b,float),rtol=0,atol=0,equal_nan=True)
def main():
    receipt=json.loads((D/'COMPLETION.json').read_text());bound={str((D/'COMPLETION.json').resolve()):sha(D/'COMPLETION.json')}
    for name,h in receipt['outputs'].items():
        p=D/name;assert sha(p)==h,(name,'output hash');bound[str(p.resolve())]=h
    for name,h in receipt['source_sha256'].items():
        if Path(name).suffix=='.py':assert sha(name)==h;bound[name]=h
    x=pd.read_parquet(D/'ALL_1681_COORDINATE_FEATURES.parquet')
    a=pd.read_parquet(D/'ALL_COMMON_QUEUE_RANKS.parquet')
    t=pd.read_csv(D/'TARGET_231_SAME_POOL_RANKS.csv',float_precision='round_trip')
    summary=pd.read_csv(D/'DAY_QUEUE_SUMMARY.csv',float_precision='round_trip')
    top=pd.read_csv(D/'TOP20_BOTH_SIDES.csv',float_precision='round_trip')
    assert len(x)==11767 and not x.duplicated(KEY).any()and x.groupby('day').size().eq(1681).all()
    assert len(a)==33046 and not a.duplicated(KEY+['queue']).any()
    assert len(t)==231 and not t.duplicated(KEY+['queue']).any() and len(summary)==21 and len(top)==840
    summary_rows=[];expected_tops=[]
    for (day,queue),q in a.groupby(['day','queue']):
        mother=x[x.day.eq(day)].set_index('sid')
        cols={'PVR':['score'],'FAST':['E_fast'],'CONT':['E_fast','E_slow']}[queue]
        mask=mother.source_row_present & mother.target_row_present
        for c in cols:
            for side in ['old','new']:mask&=np.isfinite(mother[c+'_'+side])
        assert set(q.sid)==set(mother.index[mask])
        q=q.set_index('sid').sort_index();g=mother.loc[q.index]
        n=len(q);assert q.common_pool_N.eq(n).all()
        order={}
        for side in ['old','new']:
            if queue=='CONT':
                af=half_rank(g['E_fast_'+side]);bs=half_rank(g['E_slow_'+side]);num=3*af+7*bs
                equal(q['p_fast_'+side],af/(2*(n-1)));equal(q['p_slow_'+side],bs/(2*(n-1)))
                equal(q['CONT_num_'+side],num);equal(q['queue_value_'+side],num)
                equal(q['CONT_'+side],num/(20*(n-1)))
                assert q['CONT_'+side].between(0,1).all()
                value=num
            else:
                value=g[cols[0]+'_'+side];equal(q['queue_value_'+side],value)
            ordered=sorted(q.index,key=lambda sid:(-value.loc[sid],sid));order[side]=ordered
            assert q.loc[ordered,'rank_'+side].tolist()==list(range(1,n+1))
            expected_tops.extend((day,queue,side,sid)for sid in ordered[:20])
        equal(q.rank_new_minus_old,q.rank_new-q.rank_old)
        oldtop=set(order['old'][:20]);newtop=set(order['new'][:20])
        z=summary[(summary.day.eq(day))&(summary.queue.eq(queue))].iloc[0]
        values={'mother':1681,'common_pool_N':n,'top20_intersection':len(oldtop&newtop),'top20_new_only':len(newtop-oldtop),'top20_old_only':len(oldtop-newtop),'rank_changed':int(q.rank_old.ne(q.rank_new).sum()),'max_abs_rank_change':int(q.rank_new_minus_old.abs().max()),'old_queue_tie_excess':int(q.queue_value_old.duplicated().sum()),'new_queue_tie_excess':int(q.queue_value_new.duplicated().sum())}
        assert all(z[k]==v for k,v in values.items()),(day,queue,'summary')
        summary_rows.append({'day':day,'queue':queue,**values})
        tt=t[t.day.eq(day)&t.queue.eq(queue)]
        assert len(tt)==11
        for r in tt.itertuples(index=False):
            assert r.common_pool_N==n
            if r.sid in q.index:
                saved=q.loc[r.sid];assert r.status=='COMMON_COMPLETE'
                for c in ['rank_old','rank_new','rank_new_minus_old','queue_value_old','queue_value_new']:assert getattr(r,c)==saved[c]
                assert r.old_top20==(saved.rank_old<=20)and r.new_top20==(saved.rank_new<=20)
            else:
                m=mother.loc[r.sid]
                known={side:bool(m['source_row_present'if side=='old'else'target_row_present'])and all(np.isfinite(m[c+'_'+side])for c in cols)for side in ['old','new']}
                status='BOTH_UNKNOWN'if not known['old']and not known['new']else'OLD_UNKNOWN'if not known['old']else'NEW_UNKNOWN'
                assert r.status==status and pd.isna(r.rank_old)and pd.isna(r.rank_new)and pd.isna(r.queue_value_old)and pd.isna(r.queue_value_new)
    assert set(top[['day','queue','side','sid']].itertuples(index=False,name=None))==set(expected_tops)
    for r in top.itertuples(index=False):
        q=a[a.day.eq(r.day)&a.queue.eq(r.queue)].set_index('sid').loc[r.sid]
        for c in ['rank_old','rank_new','queue_value_old','queue_value_new']:assert getattr(r,c)==q[c]
        assert r.top20_status=='BOTH'
    previous=pd.read_csv(BASE/'adjustment_review/ALL_COMMON_FINITE_PVR_RANKS.csv',float_precision='round_trip').set_index(KEY).sort_index()
    pvr=a[a.queue.eq('PVR')].set_index(KEY).sort_index()
    assert previous.index.equals(pvr.index)
    for col in ['rank_old','rank_new','rank_new_minus_old']:equal(previous[col],pvr[col])
    for side in ['old','new']:equal(previous['score_'+side],pvr['queue_value_'+side])
    changed=t[t.status.eq('COMMON_COMPLETE')&t.rank_new_minus_old.ne(0)]
    target_counts={}
    for queue,g in t.groupby('queue'):
        known=g.status.eq('COMMON_COMPLETE');c=g[known&g.rank_new_minus_old.ne(0)]
        target_counts[queue]={'target_rows':len(g),'known':int(known.sum()),'unknown':int((~known).sum()),'rank_changed':len(c),'max_abs_target_rank_change':int(c.rank_new_minus_old.abs().max()),'crossed_top20':int((g.loc[known,'old_top20']!=g.loc[known,'new_top20']).sum())}
    assert {k:v['rank_changed']for k,v in target_counts.items()}=={'CONT':16,'FAST':2,'PVR':3}
    assert all(r['known']==66 and r['unknown']==11 and r['crossed_top20']==0 for r in target_counts.values())
    assert all(r['top20_intersection']==20 for r in summary_rows)
    bound[str(Path(__file__).resolve())]=sha(Path(__file__))
    prior=BASE/'adjustment_review/SAME_POOL_PVR_AUDIT.json';bound[str(prior.resolve())]=sha(prior)
    out={'status':'PASS_BOUNDED_ALL_SAVED_DUAL_QUEUE_RANKS_WITH_SOURCE_LIMITS','remaining_blocks':[],'counts':{'saved_coordinate_rows':11767,'saved_common_rank_rows':33046,'day_queue_groups':21,'top20_both_sides_rows':840,'target_rows':231},'target_counts':target_counts,'summaries':summary_rows,'changed_targets':changed.replace({np.nan:None}).to_dict('records'),'findings':['Every queue independently uses exactly the same both-source-complete stock pool for its two rankings. PVR/FAST/CONT pools differ and are disclosed.','CONT uses independently reconstructed integer half-ranks:3a+7b. queue_value is this integer numerator, not normalized score; CONT_old/new=num/(20*(N-1)). Equal numerators use ascending exact symbol.','All21 top20 sets have intersection20; changed within-pool ranks remain, not all ranks or source values identical.','PVR all11031 same-pool ranks and score fields exactly bridge the prior immutable PVR audit.','All231 target status/rank/value/top20 fields checked against saved coordinate rows and independently derived rankings.'], 'scope_limits':['No indicator/model/E0/G1/account/forward execution; only saved arrays ranked.','Producer reports full old8-column grid bitexact and2prefix checks. This audit binds its receipt/output bytes but does not independently rerun that feature calculation or original1681 source histories.','This1681 exact intersection contrast does not construct old-source full5517 features or establish a pureCA intervention for every row. Prior3maximum-difference local factor evidence is not generalized to the entire table.','Canonical qfq/source snapshots and current metadata are not historical published/PIT/tradable certification. No E0/I/CP/order eligibility claim.'],'bindings':bound}
    f=OUT/'DUAL_QUEUE_OUTPUT_AUDIT.json';f.write_text(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':out['status'],'sha256':sha(f),'target_counts':target_counts,'groups':21,'all_top20_intersection':20},ensure_ascii=False))
if __name__=='__main__':main()
