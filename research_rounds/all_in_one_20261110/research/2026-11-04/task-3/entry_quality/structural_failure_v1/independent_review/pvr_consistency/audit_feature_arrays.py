"""Independent full eta export/rank-clock oracle; zero Account imports/events."""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,hashlib,json,math,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
F=O.parents[1]/'mechanism_design'
T=O.parents[2]/'trend_exit_controls_v1'
WT=.9**np.arange(20,-1,-1);WT=WT/WT.sum()


def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:
        for l in f:yield json.loads(l)


def independent(f):
    valid=np.isfinite(f.close)&f.close.gt(0)&np.isfinite(f.amount)&f.amount.gt(0)
    for k in ['price_eligible','observed_bar','is_observed_bar']:
        if k in f:valid &= f[k].fillna(False).astype(bool)
    for k in ['source_invalid','synthetic_event_bar']:
        if k in f:valid &= ~f[k].fillna(True).astype(bool)
    seg=f.segment_id if 'segment_id' in f else pd.Series(0,index=f.index)
    resets=(~valid)|(~valid.shift(fill_value=False))|seg.ne(seg.shift())
    blocks=resets.cumsum()
    out=pd.DataFrame(np.nan,index=f.index,columns=['original_E','absolute_energy','original_score','score'])
    for _,g in f[valid].groupby(blocks[valid],sort=False):
        r=np.log(g.close).diff()
        scale=(r.abs().shift(1).rolling(63,min_periods=63).median()*1.4826).clip(lower=1e-8)
        background=g.amount.shift(1).rolling(21,min_periods=21).median()
        u=np.tanh(r/scale);b=np.tanh(np.log(g.amount/background))
        e=u*(1+.5*u.abs()*b)
        N=e.rolling(21,min_periods=21).apply(lambda a:np.dot(WT,a),raw=True)
        A=e.abs().rolling(21,min_periods=21).apply(lambda a:np.dot(WT,a),raw=True)
        eta=(N/A).where(np.isfinite(N)&np.isfinite(A)&A.gt(0))
        out.loc[g.index]=pd.DataFrame(dict(original_E=N,absolute_energy=A,
                                         original_score=50+50*np.tanh(2*N),score=eta),index=g.index)
    return out


def order(rs,vals):
    base=sorted(rs,key=lambda r:r['original_H1_rank'])
    assert len({r['sid'] for r in base})==len(base)
    assert len({r['original_H1_rank'] for r in base})==len(base)
    known=[r for r in base if math.isfinite(vals[r['sid']])]
    known.sort(key=lambda r:(-round(vals[r['sid']],12),r['original_H1_rank']))
    it=iter(known)
    final=[r if not math.isfinite(vals[r['sid']]) else next(it) for r in base]
    return {r['sid']:(n,base[n]['original_H1_rank']) for n,r in enumerate(final)}


def main():
    start=time.monotonic();m=read(F/'SCORES_MANIFEST.json');p=read(F/'PROTOCOL.json')
    assert digest(F/'prepare_eta.py')==m['script_sha256']==p['code_sha256'][str(F/'prepare_eta.py')]
    assert digest(F/'PROTOCOL.json')==m['protocol_sha256']
    assert len(m['entries'])==len(set(m['fixed_stock_ids']))==m['stocks']==1709
    assert [r['symbol'] for r in m['entries']]==m['fixed_stock_ids']
    calendars={w:[r['at'][:10] for r in rows(T/'runs/BASELINE'/w/'pair/daily.jsonl.gz')] for w in ['2022_2024','strong']}
    dates=pd.DatetimeIndex(sorted(set(sum(calendars.values(),[]))),name='day')
    assert [len(calendars[w]) for w in ['2022_2024','strong']]==[726,242]
    exports={};counts=Counter();prefix=[];binding={};max_error=defaultdict(float);round_examples=[]
    sample={0,100,500,1000,1500,1708}
    for i,r in enumerate(m['entries']):
        sid=r['symbol'];src=Path(r['source']);dest=F/'scores'/(sid+'.parquet')
        assert digest(src)==r['source_sha256'];assert digest(dest)==r['output_sha256']
        binding[str(src)]=r['source_sha256'];binding[str(dest)]=r['output_sha256']
        f=pd.read_parquet(src).loc[:'2026-06-30'];q=pd.read_parquet(dest)
        pd.testing.assert_index_equal(q.index,dates)
        expected=independent(f).reindex(dates)
        for col in expected:
            got,want=q[col].to_numpy(),expected[col].to_numpy()
            assert np.array_equal(np.isnan(got),np.isnan(want)),(sid,col,'NA mask')
            err=float(np.nanmax(np.abs(got-want))) if np.isfinite(want).any() else 0.
            max_error[col]=max(max_error[col],err)
            if col in ('original_E','original_score'):
                assert np.array_equal(got,want,equal_nan=True),(sid,col)
            else:
                # Group-wise independent dot inputs can differ in BLAS memory
                # alignment from the producer's full assigned e series. Bound
                # sub-ULP noise explicitly instead of claiming bit identity.
                assert np.allclose(got,want,atol=5e-15,rtol=0,equal_nan=True),(sid,col,err)
        for day,got,want in zip(q.index,q.score,expected.score):
            if math.isfinite(got) and round(float(got),12)!=round(float(want),12):
                counts['raw_eta_round12_independent_ULP_disagreements']+=1
                if len(round_examples)<20:round_examples.append(dict(sid=sid,day=str(day.date()),got=got,independent=want))
        original_segment=f.segment_id.reindex(dates)
        assert np.array_equal(q.source_segment.to_numpy(),original_segment.to_numpy(),equal_nan=True)
        assert len(q)==r['rows'] and int(q.score.notna().sum())==r['ready']
        assert int(q.score.isna().sum())==r['NA']
        counts['stocks']+=1;counts['source_rows']+=len(f);counts['export_cells']+=len(q)
        counts['old_score_ready']+=int(q.original_score.notna().sum())
        counts['eta_ready']+=int(q.score.notna().sum())
        counts['zero_denominator_old_ready']+=int((q.original_score.notna()&q.absolute_energy.eq(0)).sum())
        counts['eta_plus_one_round12']+=int(q.score.round(12).eq(1).sum())
        counts['eta_minus_one_round12']+=int(q.score.round(12).eq(-1).sum())
        exports[sid]=q[['score','original_score']].assign(independent_eta=expected.score)
        if i in sample:
            full=independent(f)
            for cut in ['2022-01-21','2024-10-08','2026-04-21']:
                sub=f.loc[:cut];want=full.loc[:cut]
                pd.testing.assert_frame_equal(independent(sub),want,check_exact=True)
                mut=f.copy();future=mut.index>pd.Timestamp(cut)
                mut.loc[future,'close']*=11;mut.loc[future,'amount']*=.0007
                mut.loc[future,'segment_id']+=1000
                pd.testing.assert_frame_equal(independent(mut).loc[:cut],want,check_exact=True)
                prefix.append(dict(sid=sid,cut=cut,prefix_rows=len(sub),physical_exact=True,future_price_amount_source_mutation_exact=True))
        if (i+1)%400==0:print('INDEPENDENT_ETA_ARRAYS',i+1,round(time.monotonic()-start,2),flush=True)
    assert counts['stocks']==1709 and counts['export_cells']==1709*968
    query={}
    for win in ['2022_2024','strong']:
        rp=T/'runs/BASELINE'/win/'pair/rank-policy.jsonl.gz'
        mp=F/(win+'_PENDING_RANK_MOVES.jsonl.gz')
        groups=defaultdict(list)
        for r in rows(rp):groups[r['day']].append(r)
        changes={(r['day'],r['sid']):r for r in rows(mp)}
        c=Counter()
        for day,rs in groups.items():
            stamp=pd.Timestamp(day)
            oldvals={r['sid']:float(exports[r['sid']].loc[stamp,'original_score']) for r in rs}
            newvals={r['sid']:float(exports[r['sid']].loc[stamp,'score']) for r in rs}
            ivals={r['sid']:float(exports[r['sid']].loc[stamp,'independent_eta']) for r in rs}
            oldorder=order(rs,oldvals);neworder=order(rs,newvals)
            assert order(rs,ivals)==neworder,(win,day,'Independent ULP changes actual rank')
            for r in rs:
                s=r['sid'];a,b=oldorder[s],neworder[s];n=changes.pop((day,s))
                assert bool(r['PVR_ready'])==math.isfinite(oldvals[s])
                if r['PVR_ready']:assert r['PVR']==oldvals[s]
                assert (r['final_slot'],r['priority_rank'])==a
                assert (n['old_PVR_slot'],n['old_PVR_rank'])==a
                assert (n['new_eta_slot'],n['new_eta_rank'])==b
                assert n['roles']==r['roles']
                assert n['eta_minus_PVR_slot']==b[0]-a[0]
                assert n['eta']==newvals[s] if math.isfinite(newvals[s]) else n['eta'] is None
                c['query_stock_days']+=1;c['changed']+=a[0]!=b[0]
                c['eta_unknown']+=not math.isfinite(newvals[s])
                c['eta_plus_one_round12']+=math.isfinite(newvals[s]) and round(newvals[s],12)==1
                c['eta_minus_one_round12']+=math.isfinite(newvals[s]) and round(newvals[s],12)==-1
        assert not changes
        query[win]=dict(c)
        binding[str(rp)]=digest(rp);binding[str(mp)]=digest(mp)
    for pth in [F/'SCORES_MANIFEST.json',F/'PROTOCOL.json',F/'prepare_eta.py',F/'SOURCE_BINDING.json']:
        binding[str(pth)]=digest(pth)
    out=dict(status='PASS_ALL_1709_FEATURE_ARRAYS_AND_ALL_ORIGINAL_RANK_QUERIES_WITH_LIMITS',
             arrays=dict(counts),rank_queries=query,physical_prefix_checks=prefix,
             numerical_match='Bitwise original E/score and all NA/source masks; independent grouped A/raw_eta bounded at5e-15. Independent raw_eta gives identical native ranks at every original query batch.',
             max_absolute_float_error=dict(max_error),raw_eta_round12_ULP_disagreement_examples=round_examples,
             technical_note='Initial audit assertion demanded bitwise A/eta identity; observed sub-ULP full-series versus grouped dot differences, not a producer formula/source defect. Explicit numerical bound and all actual query-rank equivalence replace that overstrong assertion.',
             source_and_export_sha256=binding,script_sha256=digest(__file__),seconds=time.monotonic()-start,
             remaining=['Pure rank/resource background and actual-entry diagnostics are necessary scope, not candidate financial outcomes.','Tie/non-tie displacement annex and scarcity semantics still require separate review.','Native candidate prefix and source-only launcher gate not covered by this receipt.'],
             new_accounts=0,new_financial_events=0)
    (O/'FEATURE_ARRAY_AND_RANK_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status=out['status'],arrays=out['arrays'],rank_queries=query,seconds=out['seconds']),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
