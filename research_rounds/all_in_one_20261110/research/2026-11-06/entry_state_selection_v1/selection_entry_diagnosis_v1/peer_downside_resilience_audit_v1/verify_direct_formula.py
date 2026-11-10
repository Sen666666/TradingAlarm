
import pandas as pd, numpy as np, json, hashlib
from pathlib import Path
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/peer_downside_resilience_audit_v1')
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
x=pd.read_csv(O/'ALL_FIRST_ENTRY_FEATURES.csv')
meta=json.loads(M.read_text());h=np.load(P/'h1.npz'); dates=pd.DatetimeIndex(h['dates']); syms=list(h['symbols']); ids=[s for s in syms if not s.startswith('URFI')]
C=pd.DataFrame(h['close'],index=dates,columns=syms).loc['2021-01-01':'2026-05-15',ids];G=pd.DataFrame(h['segment'],index=dates,columns=syms).reindex(C.index)[ids]
C=C.where(np.isfinite(C)&C.gt(0));R=np.log(C).diff().where(G.eq(G.shift()))
sectors={}
for s in ids:sectors.setdefault(meta[s]['sector_id'],[]).append(s)
errs=[];breaks=[]
for row in x.itertuples():
    at=C.index.get_loc(pd.Timestamp(row.signal_day)); sid=row.sid; peers=[s for s in sectors[meta[sid]['sector_id']] if s!=sid]
    a=R[sid].iloc[at-20:at];b=R[peers].iloc[at-20:at].mean(axis=1) if peers else pd.Series(np.nan,index=a.index)
    v=(a-b).where(b<0,0).where(a.notna()&b.notna())
    direct=v.sum() if len(v)==20 and v.notna().all() else np.nan
    errs.append(abs(direct-row.A) if np.isfinite(direct) and np.isfinite(row.A) else 0 if np.isnan(direct) and np.isnan(row.A) else np.inf)
    if G[sid].iloc[at]!=G[sid].iloc[at-21]:
        breaks.append(dict(row_id=row.row_id,sid=sid,date=row.signal_day,known=bool(row.known)))
assert max(errs)<1e-12
assert not any(r['known'] for r in breaks)
out=dict(rows=len(x),direct_A_max_error=float(max(errs)),mismatch_count=int(sum(e>1e-12 for e in errs)),source_break_rows=breaks,source_break_known=0,pvr_risk=x.loc[x.account=='PVR','risk'].describe(percentiles=[.01,.05,.5,.95,.99]).to_dict())
(O/'DIRECT_FORMULA_AUDIT.json').write_text(json.dumps(out,indent=2))
(O/'OUTPUT_SHA256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(O.iterdir()) if p.is_file() and p.name!='OUTPUT_SHA256.json'},indent=2))
print(json.dumps(out))
