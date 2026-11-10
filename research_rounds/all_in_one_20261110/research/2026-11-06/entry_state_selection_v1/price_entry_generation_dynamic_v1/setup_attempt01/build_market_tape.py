"""Market-only single full-history replay, original frozen inputs unchanged."""
import ast,sys,time
import numpy as np,pandas as pd
from runtime import O,R,SOURCE,sha,read,save
from generation import compute
from market_adapter import MarketAdapter,_LOCK

def replay(m,sid,cut=None):
    m._setup()
    with _LOCK:
        old=sys.modules.get('fast_core');sys.modules['fast_core']=m._core
        try:q,x=m._engine.replay(sid,cut=cut)
        finally:
            if old is None:sys.modules.pop('fast_core',None)
            else:sys.modules['fast_core']=old
    m._merge_sources(m._engine.S)
    return q,x

def main():
    out=O/'market_tape';out.mkdir(exist_ok=False)
    save(out/'STARTED.json',dict(economic_runs=0,source=sha(__file__),generation=sha(O/'generation.py'),started=time.time()))
    a=read(SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json');m=MarketAdapter(expected_sources=a['input_sha256'])
    p=R/'price_entry_generation_gate_preflight_v1/RECEIPT_GATE_FACTS.parquet'
    old=pd.read_parquet(p);assert len(old)==37456 and not old.duplicated(['sid','day']).any()
    priority=pd.read_csv(R/'old_result_association_v1/COMMON_167_DENY_BUYS.csv',usecols=['sid']).sid.unique().tolist()
    sids=sorted(old.sid.unique(),key=lambda s:(s not in priority,s));parts=[];checks=[];files={};start=time.monotonic()
    # Exact original diagnostic pure helper, extracted by AST; never its run body.
    ds=R/'price_entry_generation_gate_preflight_v1/diagnose.py';tree=ast.parse(ds.read_text());node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_root');env={'np':np}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(ds)+':pure_run_root_only','exec'),env)
    for n,sid in enumerate(sids,1):
        q,x=replay(m,sid);g=compute(q,x);refs=old[old.sid.eq(sid)].set_index('day')
        z=x.join(g);z['sid']=sid
        for c in ['open','high','low','close','raw_open','raw_close','adjustment_factor','identity','source_kind','source_path','segment_id']:z[c]=q[c]
        # Preserve all parent state including fail/unknown, receipt and protection.
        z.loc['2022-01-01':'2026-06-30'].reset_index().to_parquet(out/(sid+'.parquet'),index=False)
        files[sid+'.parquet']=sha(out/(sid+'.parquet'))
        subset=g.loc[refs.index].copy();subset['sid']=sid;subset['root_day']=x.loc[refs.index,'root_day'];subset['window']=refs.window
        fields=['generation','entry_U','entry_active','gate_status','event','ever_returned_to_root_U','current20_high_break','contemporary_prior20_high']
        for c in fields:
            av=subset[c].to_numpy();bv=refs[c].to_numpy()
            assert np.array_equal(av,bv,equal_nan=True) if av.dtype.kind in 'fi' else np.array_equal(av,bv),(sid,c,'FROZEN_RECEIPT_GATE_MISMATCH')
        for c in ['generation_birth','first_return_to_root_U','last_generation_retired']:
            assert pd.to_datetime(subset[c]).equals(pd.to_datetime(refs[c])),(sid,c,'DATE_MISMATCH')
        assert x.loc[refs.index,'receipt'].all() and x.loc[refs.index,'root_day'].equals(pd.to_datetime(refs.root_day))
        # Physically cut raw/fact/CP input through original loader, not just results.
        cut=refs.index[len(refs)//2];pq,px=replay(m,sid,cut=cut);pg=compute(pq,px)
        pd.testing.assert_frame_equal(g.loc[pg.index],pg,check_exact=True)
        checks.append(dict(sid=sid,receipts=len(refs),physical_prefix_cut=str(cut.date()),exact=True))
        parts.append(subset.reset_index())
        if n==len(priority):save(out/'PRIORITY_156_COMPLETE.json',dict(sids=priority,files={s+'.parquet':files[s+'.parquet'] for s in priority},range=['2022-01-01','2026-06-30'],economic_runs=0));print('PRIORITY_156_COMPLETE',flush=True)
        if n%100==0:print('MARKET_STOCKS',n,'seconds',round(time.monotonic()-start,1),flush=True)
    allf=pd.concat(parts,ignore_index=True).sort_values(['sid','day']).reset_index(drop=True)
    assert len(allf)==len(old)==37456 and not allf.duplicated(['sid','day']).any()
    assert set(zip(allf.sid,allf.day))==set(zip(old.sid,old.day))
    allf.to_parquet(out/'RECEIPT_GATE_FACTS.parquet',index=False);files['RECEIPT_GATE_FACTS.parquet']=sha(out/'RECEIPT_GATE_FACTS.parquet')
    sources=m.verify_sources();sources[str(p)]=sha(p);sources[str(ds)]=sha(ds)
    save(out/'SOURCE_HASHES.json',sources);save(out/'PREFIX_EXACT_QA.json',checks)
    save(out/'QA.json',dict(result='PASS_FULL_PARENT_LIFECYCLE_AND_FROZEN_RECEIPT_EXACT',stocks=len(sids),receipts=len(allf),physical_prefix_checks=len(checks),window_counts=allf.groupby('window').size().to_dict(),source_files=len(sources),economic_runs=0,holdings_or_outcome_inputs=False,elapsed_seconds=time.monotonic()-start))
    for name in ['SOURCE_HASHES.json','PREFIX_EXACT_QA.json','QA.json','PRIORITY_156_COMPLETE.json']:files[name]=sha(out/name)
    save(out/'SEAL.json',files);print('MARKET_TAPE_COMPLETE',len(sids),len(allf),flush=True)
if __name__=='__main__':main()
