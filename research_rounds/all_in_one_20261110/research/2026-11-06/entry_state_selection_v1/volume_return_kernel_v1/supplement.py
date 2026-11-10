from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).resolve().parent;B=O.parent/'selection_entry_diagnosis_v1'
sc=pd.read_parquet(O/'full_SCORES.parquet');sel=pd.read_parquet(O/'SELECTIONS_WITH_PRICE_LABELS.parquet')
q=pd.read_parquet(B/'mobile_candidate_response_v1/LEGAL_EMPTY_MOBILE_CANDIDATES.parquet');q=q[q.account.eq('PVR')].copy()
lab=pd.read_parquet(B/'mobile_candidate_response_v1/FIXED_NATIVE_PRICE_LABELS.parquet')
allq=q.merge(sc,on=['sid','day'],how='left',validate='one_to_one').merge(lab,on=['sid','day'],how='left',validate='many_to_one')
allq.to_parquet(O/'ALL_CANDIDATES_WITH_LABELS.parquet',index=False)
known=allq.original_PVR.notna()&allq.native_pvr.notna()
print('PVR_SOURCE_MAX_ERROR',float((allq.loc[known,'original_PVR']-allq.loc[known,'native_pvr']).abs().max()))
fits=pd.read_csv(O/'full_FITS.csv');assert (fits.train_last<fits.root).all()
audit={'full_prefix_checks':6,'source_pvr_max_error':float((allq.loc[known,'original_PVR']-allq.loc[known,'native_pvr']).abs().max()),'training_rows_min':int(fits.n.min()),'training_rows_max':int(fits.n.max()),'known_main':int(allq.OO.notna().sum()),'queue_rows':len(allq),'missing_main':int(allq.OO.isna().sum()),'comparison': 'No ranking uses future labels. Full physical source prefix score checks 3 stocks x2 cutoffs at atol1e-12.'}
(O/'ADDITIONAL_AUDIT.json').write_text(json.dumps(audit,indent=2))
# Selected-set differences at same fixed counts, retain unknown outcomes explicitly.
diffs=[];moves=[]
for day,g in allq.groupby('day'):
    base=g.sort_values(['original_priority_rank','sid']);positions={s:i+1 for i,s in enumerate(base.sid)}
    for model in ['OO','AR']:
        ready=base[model].notna()&base.original_PVR.notna();ranked=base[ready].sort_values([model,'original_priority_rank','sid'],ascending=[False,True,True])
        it=iter(ranked.index);ix=[next(it) if ready.loc[i] else i for i in base.index];alt=base.loc[ix]
        for pos,r in enumerate(alt.itertuples()):
            moves.append(dict(day=day,sid=r.sid,model=model,old_rank=positions[r.sid],new_rank=pos+1,score=getattr(r,model),h=getattr(r,model+'_h'),sector=r.sector))
        bs=set(base.head(20).sid);vs=set(alt.head(20).sid)
        for side,ids in [('removed',bs-vs),('added',vs-bs)]:
            a=g[g.sid.isin(ids)].copy();a['side']=side;a['model']=model;diffs.append(a)
pd.DataFrame(moves).to_csv(O/'RANK_MOVES.csv',index=False)
d=pd.concat(diffs,ignore_index=True)
res=[]
for (yr,model,side),g in d.groupby(['year','model','side']):
    rr=dict(year=yr,model=model,side=side,n=len(g),big60=int(g.big60_posthoc.sum()))
    for h in [5,20,60]:
        z=g[g['complete'+str(h)]]
        rr['n'+str(h)]=len(z);rr['ret'+str(h)]=z['ret'+str(h)].mean();rr['mae'+str(h)]=z['mae'+str(h)].mean()
    res.append(rr)
pd.DataFrame(res).to_csv(O/'ADDED_REMOVED.csv',index=False)
# Original account round association: only existing actual first mobile rounds with original legal candidate row.
first=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv');first=first[first.account.eq('PVR')&first.first_kind.eq('add')]
af=first.merge(allq[['sid','day','OO','AR']],left_on=['sid','signal_day'],right_on=['sid','day'],validate='one_to_one')
members={m:set(zip(g.day,g.sid)) for m,g in sel.groupby('strategy')}
ar=[]
for m in ['PVR','OO','AR']:
    af[m+'_chosen']=[(r.signal_day,r.sid) in members[m] for r in af.itertuples()]
for yr,g in af.groupby('year'):
    for model in ['OO','AR']:
        for group,mask in [('original_top20',g.PVR_chosen),('kept_original_top20',g.PVR_chosen&g[model+'_chosen']),('lost_original_top20',g.PVR_chosen&~g[model+'_chosen'])]:
            z=g[mask];c=z[z.closed]
            ar.append(dict(year=yr,model=model,group=group,n=len(z),closed=len(c),wins=int(c.round_pnl.gt(0).sum()),winrate=c.round_pnl.gt(0).mean(),pnl=float(c.round_pnl.sum()),positive_pnl=float(c.loc[c.round_pnl.gt(0),'round_pnl'].sum())))
pd.DataFrame(ar).to_csv(O/'EXISTING_MOBILE_ROUND_MEMBERSHIP.csv',index=False)
af.to_csv(O/'EXISTING_MOBILE_FIRST_ROUNDS.csv',index=False)
# Original opportunity root coverage; first 6 common dates from first legal opportunity, no hindsight best entry.
roots=[]
for (sid,epoch),g in allq.groupby(['sid','epoch']):
    g=g.sort_values('t');b=g.iloc[0];early=g[g.t<=b.t+5]
    rr=dict(sid=sid,epoch=epoch,first_day=b.day,year=b.year,complete60=b.complete60,big60=b.big60_posthoc)
    for m,keys in members.items():rr[m]=any((r.day,sid) in keys for r in early.itertuples())
    roots.append(rr)
roots=pd.DataFrame(roots);roots.to_csv(O/'ROOT_COVERAGE.csv',index=False)
rs=[]
for yr,g in roots.groupby('year'):
    b=g[g.big60]
    for m in ['OO','AR']:
        rs.append(dict(year=yr,model=m,roots=len(g),known60=int(g.complete60.sum()),big60=len(b),base=int(b.PVR.sum()),candidate=int(b[m].sum()),lost=int((b.PVR&~b[m]).sum()),added=int((~b.PVR&b[m]).sum())))
pd.DataFrame(rs).to_csv(O/'ROOT_COVERAGE_SUMMARY.csv',index=False)
# Paired date equal means, month bootstrap diagnostic only; all arms common union-complete dates.
rng=np.random.default_rng(20261106);rr=[]
for h in [5,20,60]:
    good=sel.groupby('day')['complete'+str(h)].all();x=sel[sel.day.isin(good[good].index)]
    means=x.groupby(['day','strategy'])['ret'+str(h)].mean().unstack('strategy')
    for period,sub in [('ALL',means)]+[(str(y),means[means.index.str.startswith(str(y))]) for y in [2022,2023,2024,2025,2026]]:
        for m in ['OO','AR']:
            delta=sub[m]-sub.PVR
            if not len(delta):continue
            z=pd.DataFrame({'d':delta,'month':delta.index.str[:7]});bs=z.groupby('month').d.agg(['sum','count'])
            draw=rng.integers(0,len(bs),(2000,len(bs)));boot=bs['sum'].to_numpy()[draw].sum(1)/bs['count'].to_numpy()[draw].sum(1)
            low,high=np.quantile(boot,[.025,.975])
            rr.append(dict(H=h,period=period,model=m,dates=len(delta),delta=float(delta.mean()),lo=low,hi=high,leave_best_delta_date=float(delta.drop(delta.idxmax()).mean()) if len(delta)>1 else np.nan))
pd.DataFrame(rr).to_csv(O/'MONTH_BLOCK_DIAGNOSTIC.csv',index=False)
# Fixed semiconductor names and important broad-market dates; report absence, not forced opportunity.
named=['300666.SZ','688603.SH','301611.SZ','002583.SZ','300085.SZ','600056.SH','002317.SZ','000620.SZ']
pd.DataFrame(moves).query('sid in @named').to_csv(O/'CASE_RANK_PATHS.csv',index=False)
print('AUDIT',audit);print('ROOTS',pd.DataFrame(rs).to_string(index=False));print('ASSOCIATION',pd.DataFrame(ar).to_string(index=False));print('BLOCKS',pd.DataFrame(rr).to_string(index=False))
