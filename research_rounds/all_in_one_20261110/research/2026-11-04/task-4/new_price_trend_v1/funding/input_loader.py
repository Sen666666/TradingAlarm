"""Read only frozen full facts/CP1 and the three canonical receipt years.

The original context provides prices, actions, H1, execution and market facts.
This extends immutable lookups, never imports a prior financial account.
"""
from pathlib import Path
import json, time
import pandas as pd
import entry_adapter as E
J,L,N,S = E.J,E.L,E.N,E.S
W = E.A.W
GEN24 = Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full')
WINDOWS = {'long': ('2022-01-01','2024-12-31'), 'strong': ('2025-07-01','2026-06-30')}
RECEIPT_MANIFESTS = [W/'2022-normal-reference-20261031/inputs/MANIFEST.json',
                    W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json', GEN24/'inputs/MANIFEST.json']
SCORES = {'long':GEN24/'SCORES_MANIFEST.json', 'strong':N.O/'SCORES_MANIFEST.json'}
BASELINES = {'long':GEN24/'cycle2024/no60/run-2024/pair', 'strong':E.POOL/'runs/2025_26/pair'}

def read(path): return json.loads(Path(path).read_text())

def inputs(window, through=None):
    begun=time.monotonic(); start,end=WINDOWS[window]; end=through or end
    J.START,J.END=start,end
    sm,im=read(L.U/'STOCK_MANIFEST.json'),read(L.U/'INDUSTRY_MANIFEST.json')
    fixed=read(L.U/'FREEZE.json')['stocks']; assert len(sm)==len(fixed)==1709 and len(im)==90
    canonical=[{r['sid']:r for r in read(path)} for path in RECEIPT_MANIFESTS] if window=='long' else None
    checked={}; counts={}; full={}; cp={}; receipts={}
    def check(path, digest):
        if path not in checked:
            assert E.sha(path)==digest,('source changed',path)
            checked[str(path)]=digest
    def receipt_rows(r,sid):
        if canonical is None:
            return [x for x in read(r['refs']['receipts']) if start<=x['confirmed_day']<=end]
        rows=[]
        for mapping in canonical:
            z=mapping[sid]; assert z['original_output_sha256']==r['output_sha256']
            check(z['output_path'],z['output_sha256'])
            rows.extend(x for x in read(z['output_path']) if start<=x['confirmed_day']<=end)
        days=[x['confirmed_day'] for x in rows]; assert len(days)==len(set(days)),('duplicate receipt day',sid)
        return rows
    for r in sm:
        sid=r['symbol']
        for p,h in r['output_sha256'].items(): check(p,h)
        f=pd.read_parquet(r['refs']['facts']).loc[:end]
        q=pd.read_parquet(r['refs']['CP1_input']).loc[:end]
        z=pd.read_parquet(r['refs']['CP1']).loc[:end]
        assert f.index.equals(q.index) and q.index.equals(z.index)
        for k in ('close','segment_id','i_target','i_floor'):
            pd.testing.assert_series_equal(f[k],q[k],check_exact=True,check_dtype=False,check_freq=False)
        rr=receipt_rows(r,sid); assert len(rr)==int(z.loc[start:end].receipt.eq(True).sum()),('receipt count',sid)
        full[sid],cp[sid],receipts[sid]=f,z,{x['confirmed_day']:x for x in rr}
        counts[sid]={'rows':len(f.loc[start:end]),'receipts':len(rr)}
    shared=J.M.context(end,ids=fixed); bundle,market,facts=shared
    assert set(market.lines)==set(fixed)=={x.security_id for x in bundle.lines}
    for sid,f in full.items():
        facts.f[sid]=f
        bundle.series[sid].states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
    states={}; ir={}
    for r in im:
        sid=r['series']
        for p,h in r['output_sha256'].items(): check(p,h)
        s=pd.read_parquet(r['refs']['state']); states[sid]=J.T.norm(s[s.day<=end].to_dict('records'))
        for x in receipt_rows(r,sid): ir[sid+'|'+x['confirmed_day']]=x
        assert facts.f[sid].index.max()<=pd.Timestamp(end)
    recovery=J.M.O/'recovery.csv'; check(str(recovery),read(J.BASE/'PAIR_FREEZE.json')['sha256'][str(recovery)])
    identity=dict(window=[start,end],fixed_ids=fixed,sectors=[r['series']for r in im],cash_each=1000000,
        stock_manifest_sha256=E.sha(L.U/'STOCK_MANIFEST.json'),industry_manifest_sha256=E.sha(L.U/'INDUSTRY_MANIFEST.json'),
        canonical_manifest_sha256={str(p):E.sha(p)for p in RECEIPT_MANIFESTS}if canonical else None,
        ACT_external_sha256=E.sha(recovery),H1_sha256=E.sha(J.M.P/'h1.npz'),scores_manifest_sha256=E.sha(SCORES[window]),
        checked_source_sha256=checked,stock_counts=counts,numeric_models_recomputed=0,prior_account_imports=0,
        seconds=time.monotonic()-begun)
    return shared,receipts,cp,states,ir,identity

def physical(value, cut):
    shared,receipts,cp,states,ir,identity=value
    shared,receipts,kw=S.physical_inputs(shared,receipts,cp,states,ir,cut)
    return shared,receipts,kw['stock_cp'],kw['industry_states'],kw['industry_receipts'],identity

if __name__ == '__main__': raise SystemExit('Loader only; no account execution.')
