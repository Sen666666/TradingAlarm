"""Causal original-formula A/B market invitations. No account or outcome inputs.
root is entry_state_selection_v1 (or this module's campaign directory).
Only output events are filtered by date; state shifts use the complete calendar.
Missing states remain UNKNOWN (-1/NaN), never forward-filled.
"""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

FACT_COLUMNS=['e0_ready','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready','close','raw_close','factor','segment_id']
TYPES=['A_SECTOR_BIRTH','B_STOCK_BIRTH_DURING_SECTOR']
MANIFEST=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def build_invites(root,symbols):
    root=Path(root).resolve()
    if not (root/'momentum_persistence_breadth_v1').exists():root=root.parent
    d=root/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2'
    symbols=set(symbols)
    paths=[d/(n+'.parquet') for n in ['COMMON_K_COMPARISON','RIGHT3','KNOWN3','WARM_PREFIX_M_R','WARM_PREFIX_M_K']]+[root/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',root/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv',MANIFEST,root/'m3_stock_birth_during_sector_v1/freeze_events.py',Path(__file__)]
    hashes={str(p):sha(p) for p in paths}
    panel=pd.read_parquet(paths[0]).sort_values(['sector','day'])
    rr=pd.concat([pd.read_parquet(d/'WARM_PREFIX_M_R.parquet'),pd.read_parquet(d/'RIGHT3.parquet')]).sort_index()
    kk=pd.concat([pd.read_parquet(d/'WARM_PREFIX_M_K.parquet'),pd.read_parquet(d/'KNOWN3.parquet')]).sort_index()
    assert rr.index.equals(kk.index) and not rr.index.duplicated().any()
    assert not panel.duplicated(['sector','day']).any()
    absent=symbols-set(rr.columns)
    if absent:raise ValueError(f'Symbols absent from original M3 matrix: {sorted(absent)}')
    cols=sorted(symbols)
    M=rr[cols].eq(True).astype('int8').where(kk[cols].eq(True)&rr[cols].notna(),-1)
    prevM=M.shift() # full calendar, BEFORE event/date filtering
    calendar=rr.index
    previous_day=pd.Series(calendar,index=calendar).shift()
    pv=pd.read_parquet(root/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet').set_index(['day','sid'])
    assert not pv.index.duplicated().any()
    roster=pd.read_csv(root/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv')
    members=roster.groupby('sector_id').sid.apply(list).to_dict();names=roster.set_index('sid').name.to_dict()
    sm={m['symbol']:m for m in json.loads(MANIFEST.read_text())}
    rows=[];coverage=[]
    for sec,g in panel.groupby('sector'):
        ids=[s for s in members[sec] if s in symbols]
        if not ids:continue
        lo,hi=g.day.min(),g.day.max()
        cal=calendar[(calendar>=lo)&(calendar<=hi)]
        g=g.set_index('day').reindex(cal).rename_axis('day').reset_index()
        coverage.append(dict(sector=sec,start=str(lo.date()),end=str(hi.date()),missing_calendar_rows=int(g.M3_candidate.isna().sum())))
        g['prevS']=g.M3_candidate.shift()
        start=g.M3_candidate.eq(1)&~g.prevS.eq(1)
        # Forward-fill only original run identity, NEVER market states.
        g['sector_run_start']=g.day.where(start).ffill()
        g['sector_run_age']=g.groupby(start.cumsum()).cumcount()
        for z in g[g.day.between('2022-01-01','2026-06-30')&g.M3_candidate.eq(1)].itertuples():
            mt=M.loc[z.day,ids];pm=prevM.loc[z.day,ids]
            for sid in mt.index[mt.eq(1)]:
                ps=pm.at[sid]
                if z.prevS==0:typ=TYPES[0]
                elif z.prevS==1 and ps==0:typ=TYPES[1]
                else:continue
                q=pv.reindex(pd.MultiIndex.from_tuples([(z.day,sid)],names=['day','sid'])).iloc[0]
                known=bool(np.isfinite(q.score) and q.state>=0 and q.valid_observation==True)
                rows.append(dict(window='ALL_2022_2026H1',day=z.day,sid=sid,name=names.get(sid,''),sector=sec,industry=z.sector_name,event_type=typ,previous_common_day=previous_day.at[z.day],previous_sector_state=z.prevS,previous_stock_state=ps,sector_run_start=z.sector_run_start,sector_run_age=z.sector_run_age,PVR_score=q.score,PVR_state=q.state,PVR_known=known,sector_M3_n=z.M3_n,sector_N=z.N,sector_K=z.K,sector_delta3=z.M3_delta3,original_sector_authorization=z.sector_authorization_usable))
    e=pd.DataFrame(rows)
    if e.empty:
        e.attrs.update(source_hashes=hashes,sector_coverage=coverage)
        return e
    e['market_event_id']=[f'{t}|{pd.Timestamp(dt).date()}|{sec}|{sid}' for t,dt,sec,sid in zip(e.event_type,e.day,e.sector,e.sid)]
    e['event_id']=e.window+'|'+e.market_event_id
    for sid,g in e.groupby('sid'):
        fp=Path(sm[sid]['refs']['facts']);hashes[str(fp)]=sha(fp)
        f=pd.read_parquet(fp).reindex(pd.DatetimeIndex(g.day))
        for c in FACT_COLUMNS:e.loc[g.index,c]=f[c].to_numpy()
    e['I_qualified']=e.e0_ready.eq(1)&e.g_ready.eq(True)&e.i_target.eq(1)&np.isfinite(e.i_floor)&e.i_floor.gt(0)
    e['I_and_PVR_known']=e.I_qualified&e.PVR_known
    a=e[e.event_type.eq(TYPES[0])];ak=set(map(tuple,a[['sector','sector_run_start','sid']].to_numpy()))
    e['already_invited_at_sector_birth']=[(sec,st,sid) in ak if t==TYPES[1] else False for sec,st,sid,t in zip(e.sector,e.sector_run_start,e.sid,e.event_type)]
    assert not e.duplicated(['day','sid']).any()
    e=e.sort_values(['day','sector','sid']).reset_index(drop=True)
    e.attrs.update(source_hashes=hashes,sector_coverage=coverage,stock_calendar_start=str(calendar.min().date()),stock_calendar_end=str(calendar.max().date()),full_calendar_shift_before_filter=True,no_state_forward_fill=True,no_economic_inputs=True)
    return e

def audit_original_windows(root,output):
    root=Path(root);output=Path(output)
    sealed=root/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv'
    old=pd.read_csv(sealed,dtype={'window':str})
    old=old[old.event_type.isin(TYPES)].copy()
    for c in ['day','previous_common_day','sector_run_start']:old[c]=pd.to_datetime(old[c])
    symbols=pd.read_csv(root/'pvr_persistence_breadth_v1/FIXED_MEMBERSHIP.csv').sid.unique()
    e=build_invites(root,symbols)
    parts=[]
    for wn,lo,hi,sec in [('2022','2022-01-01','2022-12-31',None),('2024_924','2024-09-01','2024-12-31',None),('2026H1_SEMI','2026-01-01','2026-06-30','URFI881121')]:
        x=e[e.day.between(lo,hi)&(e.sector.eq(sec) if sec else True)].copy();x['window']=wn;x['event_id']=wn+'|'+x.market_event_id
        a=x[x.event_type.eq(TYPES[0])];ak=set(map(tuple,a[['sector_run_start','sid']].to_numpy()))
        x['already_invited_at_sector_birth']=[(st,sid) in ak if t==TYPES[1] else False for st,sid,t in zip(x.sector_run_start,x.sid,x.event_type)]
        parts.append(x)
    new=pd.concat(parts,ignore_index=True)
    old=old.set_index('event_id').sort_index();new=new.set_index('event_id').sort_index()
    old_only=old.index.difference(new.index);new_only=new.index.difference(old.index);common=old.index.intersection(new.index)
    checks=[]
    for c in old.columns:
        a,b=old.loc[common,c],new.loc[common,c]
        if pd.api.types.is_numeric_dtype(a) and not pd.api.types.is_bool_dtype(a):ok=np.isclose(a.astype(float),b.astype(float),rtol=1e-12,atol=1e-12,equal_nan=True)
        else:ok=(a.eq(b)|(a.isna()&b.isna())).to_numpy()
        checks.append(dict(field=c,compared=len(common),mismatch=int((~ok).sum())))
    attrs=e.attrs
    hashes=dict(attrs['source_hashes']);hashes[str(sealed)]=sha(sealed)
    report=dict(original_AB_rows=len(old),reconstructed_window_AB_rows=len(new),old_only=len(old_only),new_only=len(new_only),all_fields_match=not len(old_only) and not len(new_only) and all(c['mismatch']==0 for c in checks),field_checks=checks,full_market_AB_rows=len(e),full_market_stocks=e.sid.nunique(),full_market_start=str(e.day.min().date()),full_market_end=str(e.day.max().date()),counts=e.groupby('event_type').size().to_dict(),stock_calendar_start=attrs['stock_calendar_start'],stock_calendar_end=attrs['stock_calendar_end'],sector_coverage=attrs['sector_coverage'],comparison_numeric_tolerance=1e-12,no_economic_inputs=True,no_new_economics=True,full_calendar_shift_before_filter=True,no_state_forward_fill=True)
    (output/'CAUSAL_INVITES_TECHNICAL_QA.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (output/'CAUSAL_INVITES_SOURCE_HASHES.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
    pd.DataFrame(checks).to_csv(output/'CAUSAL_INVITES_FIELD_RECONCILIATION.csv',index=False)
    e.to_parquet(output/'ALL_MARKET_AB_INVITES.parquet',index=False)
    print(json.dumps({k:v for k,v in report.items() if k not in ['field_checks','sector_coverage']},ensure_ascii=False,indent=2))
    assert report['all_fields_match'], 'Original AB reconciliation failed'
    return report

if __name__=='__main__':
    out=Path(__file__).resolve().parent
    audit_original_windows(out.parent,out)
