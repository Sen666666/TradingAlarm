"""Causal DMI for every market PRICE receipt, independent of any holding path."""
import ast, hashlib, json, warnings
from pathlib import Path
import numpy as np, pandas as pd
from runtime import O,R,SOURCE,sha,read
warnings.filterwarnings('ignore',category=FutureWarning)
M=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
DMI=R/'dmi_boundary_migration_v1/experiment.py'
RECEIPTS=R/'independent_channel_full1709_preflight_v1/overlap/RECEIPT_CONDITIONAL_OVERLAP.parquet'
N=14

def load_math():
    nodes=[n for n in ast.parse(DMI.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ('calc','rma')]
    assert [n.name for n in nodes]==['rma','calc']
    env=dict(np=np,pd=pd,N=14)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(DMI)+':pure_definitions','exec'),env)
    return env['calc'],env['rma']

def build():
    from run_economic import save
    out=O/'features';out.mkdir(exist_ok=False)
    save(out/'STARTED.json',dict(no_economics=True,script_sha256=sha(__file__)))
    inputs={str(p):sha(p) for p in [M,H,DMI,RECEIPTS]}
    manifest={x['symbol']:x for x in read(M)}
    cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)['dates'])
    cal=cal[(cal>='2013-01-01')&(cal<='2026-05-15')]
    requests=pd.read_parquet(RECEIPTS,columns=['sid','day','window'])
    requests=requests[requests.window.isin(['2022','2024_924'])].copy()
    assert not requests.duplicated(['sid','day']).any()
    assert requests.day.between('2022-01-01','2024-12-31').all()
    calc,_=load_math();parts=[];aud=[];prefix_checks=0
    for i,(sid,g) in enumerate(requests.groupby('sid',sort=True)):
        m=manifest[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
        assert sha(p)==m['source_sha256'][p];inputs[p]=m['source_sha256'][p]
        raw=pd.read_parquet(p).reindex(cal)
        # Same segment must never hide a source identity change; this makes the
        # frozen calc's segment reset exactly the complete-source reset contract.
        cols=['open','high','low','close']
        valid=np.isfinite(raw[cols]).all(axis=1)&raw[cols].gt(0).all(axis=1)&raw.high.ge(raw[cols].max(axis=1))&raw.low.le(raw[cols].min(axis=1))&raw.segment_id.notna()
        for c in ['price_eligible','observed_bar','is_observed_bar']:valid &= raw[c].fillna(False).astype(bool)
        for c in ['source_invalid','synthetic_event_bar']:valid &= ~raw[c].fillna(True).astype(bool)
        for seg,sg in raw[valid].groupby('segment_id'):
            assert sg.source_kind.notna().all() and sg.source_path.notna().all(),('MISSING_SOURCE_IDENTITY',sid,seg)
            assert sg.source_kind.nunique()==sg.source_path.nunique()==1,('SOURCE_CHANGED_WITHIN_SEGMENT',sid,seg)
        z=calc(raw,cal)
        f=z.reindex(g.day).reset_index(drop=True)
        f['sid']=sid;f['day']=g.day.to_numpy();f['window']=g.window.to_numpy();parts.append(f)
        # A deterministic actual receipt prefix per stock proves future rows do
        # not change available values; no dynamic economic path is touched.
        cut=g.day.sort_values().iloc[len(g)//2]
        prefix=calc(raw.loc[:cut],cal[cal<=cut])
        pd.testing.assert_frame_equal(prefix,z.loc[prefix.index],check_exact=True)
        prefix_checks+=1
        aud.append(dict(sid=sid,receipts=len(g),known=int(np.isfinite(f.d).sum()),source=p,sha256=inputs[p],valid_segments=int(raw.loc[valid,'segment_id'].nunique()),source_identity_unique=True))
        if (i+1)%200==0:print('ALL_RECEIPT_FEATURES',i+1,flush=True)
    allf=pd.concat(parts,ignore_index=True).sort_values(['sid','day']).reset_index(drop=True)
    assert len(allf)==len(requests)
    # Compare old 6528 only as regression evidence. Never consume old selected
    # identities/positions/labels for selection or newly simulated economics.
    static=R/'price_dmi_priority_preflight_v1/FEATURES.parquet'
    sf=pd.read_parquet(static);inputs[str(static)]=sha(static)
    joined=sf.merge(allf,on=['sid','day'],suffixes=('_old','_all'),validate='one_to_one')
    assert len(joined)==6528
    for col in ['d','dclose','plus_di','minus_di','dx','adx','up_rma','dn_rma','gain_rma','loss_rma','age','raw_plus_dm','raw_minus_dm']:
        assert np.array_equal(joined[col+'_old'].to_numpy(),joined[col+'_all'].to_numpy(),equal_nan=True),('OLD_FEATURE_MISMATCH',col)
    allf.to_parquet(out/'ALL_PRICE_RECEIPT_FEATURES.parquet',index=False)
    pd.DataFrame(aud).to_csv(out/'SOURCE_AUDIT.csv',index=False)
    save(out/'INPUT_SHA256.json',inputs)
    summary=allf.groupby('window').agg(receipts=('sid','size'),stocks=('sid','nunique'),d_known=('d','count')).to_dict('index')
    save(out/'QA.json',dict(result='PASS_ALL_RECEIPT_CAUSAL_FEATURES',windows=summary,prefix_checks=prefix_checks,static_rows_exact=6528,all_static_dmi_columns_exact=True,source_identity_invariant_stocks=len(aud),old_queue_not_runtime_input=True,history_start='2013-01-01',history_end='2026-05-15',no_2026_births=True,economic_runs=0,source_count=len(inputs)))
    save(out/'SEAL.json',{p.name:sha(p) for p in out.iterdir() if p.is_file()})
    print('FEATURES_PASS',summary,flush=True)

if __name__=='__main__':build()
