"""Fixed equal-ticket forward-price diagnosis, never an account simulation."""
from pathlib import Path
import hashlib,json,time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
RANK=ROOT/'ranks/ALL_FAMILY_RANKS_PRE_LABEL.parquet'
LABEL=ROOT.parent/'pvr_conditional_information_v1/path20_labels/PATH20_LABELS.parquet'
KEY=['window','day','sid']
METRICS=['ret20_open','mfe20_open','mae20_open','ret20_close','mfe20_close','mae20_close']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with p.open('x')as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')

def main():
    start=time.monotonic();out=ROOT/'results';out.mkdir(exist_ok=False)
    lockpath=ROOT/'ranks/COMPLETION_PRE_FUTURE_LABELS.json';lock=json.loads(lockpath.read_text())
    for name,h in lock['outputs'].items():assert sha(lockpath.parent/name)==h
    x=pd.read_parquet(RANK)
    y=pd.read_parquet(LABEL,columns=KEY+['path20_complete','path20_status']+METRICS)
    assert len(y)==133713 and not y.duplicated(KEY).any()
    x=x.merge(y,on=KEY,how='left',validate='many_to_one');assert x.path20_complete.notna().all()
    rows=[];days=[]
    for keys,g in x.groupby(['family','window','day'],sort=True):
        family,window,day=keys;arms=['PVR','FAST']+(['SLOW','CONT']if family=='COMMON'else[])
        n=len(g);k=int(g.K.iloc[0]);good=g.path20_complete.astype(bool)
        union=g[['pick_'+a for a in arms]].any(axis=1);matched=bool(good[union].all())
        p=g.period.iloc[0];pool_unknown=int((~good).sum())
        tails={'peak30':good&g.mfe20_open.ge(.30),'terminal30':good&g.ret20_open.ge(.30)}
        days.append(dict(family=family,period=p,window=window,day=day,N=n,K=k,selected_union=int(union.sum()),unknown_union=int((union&~good).sum()),matched_all_arms=matched,pool_unknown=pool_unknown,pool_known=n-pool_unknown))
        for arm in arms:
            pick=g['pick_'+arm].astype(bool);assert int(pick.sum())==k
            valid=pick&good;v=g.loc[valid];u=int((pick&~good).sum())
            row=dict(family=family,period=p,window=window,day=day,arm=arm,N=n,K=k,known_selected=len(v),unknown_selected=u,matched_all_arms=matched,pool_unknown=pool_unknown,pool_known=n-pool_unknown,
                mean_E_fast=float(g.loc[pick,'E_fast'].mean()),mean_E_slow=float(g.loc[pick,'E_slow'].mean()),
                fast_nonpositive_count=int((pick&g.E_fast.le(0)).sum()),slow_nonpositive_count=int((pick&g.E_slow.le(0)).sum()),
                selected_slow_unknown=int((pick&~np.isfinite(g.E_slow)).sum()),selected_PVR_unknown=int((pick&~np.isfinite(g.score)).sum()))
            for m in METRICS:row['mean_'+m]=float(v[m].mean())if len(v)else np.nan
            for q in [.1,.5,.9]:row['terminal_q'+str(int(q*100))]=float(v.ret20_open.quantile(q))if len(v)else np.nan
            row['negative_terminal_fraction']=float(v.ret20_open.lt(0).mean())if len(v)else np.nan
            for name,tail in tails.items():
                T=int(tail.sum());a=int((pick&tail).sum())
                row[name+'_pool_known_tails']=T;row[name+'_selected_known_tails']=a
                row[name+'_precision_lower']=a/k;row[name+'_precision_upper']=(a+u)/k
                row[name+'_known_capture']=a/T if T else np.nan
                # Sharp bounds when a known tail denominator exists; otherwise unknown.
                row[name+'_capture_lower']=a/(T+pool_unknown-u)if T else np.nan
                row[name+'_capture_upper']=(a+u)/(T+u)if T else np.nan
                row[name+'_lost_PVR_tails']=int((tail&g.pick_PVR&~pick).sum())
                row[name+'_gained_PVR_tails']=int((tail&pick&~g.pick_PVR).sum())
            rows.append(row)
    daily=pd.DataFrame(rows);support=pd.DataFrame(days)
    daily.to_parquet(out/'ALL_FIXED_PICK_DAY_DIAGNOSTICS.parquet',index=False)
    support.to_csv(out/'MATCHED_DAY_SUPPORT.csv',index=False)
    matched=daily[daily.matched_all_arms].copy();assert (matched.known_selected==matched.K).all()
    metrics=['mean_'+m for m in METRICS]+['terminal_q10','terminal_q50','terminal_q90','negative_terminal_fraction']
    metrics += [t+'_'+m for t in ['peak30','terminal30']for m in ['precision_lower','precision_upper','known_capture','capture_lower','capture_upper']]
    summaries=[]
    for keys,g in matched.groupby(['family','period','arm']):
        row=dict(family=keys[0],period=keys[1],arm=keys[2],matched_dates=len(g),source_picks=int(g.K.sum()),known_selected=int(g.known_selected.sum()),unknown_selected=int(g.unknown_selected.sum()))
        row.update({m:float(g[m].mean())for m in metrics})
        for t in ['peak30','terminal30']:
            row[t+'_tail_opportunity_dates']=int(g[t+'_pool_known_tails'].gt(0).sum())
            for c in ['pool_known_tails','selected_known_tails','lost_PVR_tails','gained_PVR_tails']:row[t+'_'+c]=int(g[t+'_'+c].sum())
        summaries.append(row)
    pd.DataFrame(summaries).to_csv(out/'MATCHED_DAY_EQUAL_SUMMARY.csv',index=False)
    cov=[]
    for keys,g in daily.groupby(['family','period','arm']):
        cov.append(dict(family=keys[0],period=keys[1],arm=keys[2],source_dates=len(g),source_picks=int(g.K.sum()),known_selected=int(g.known_selected.sum()),unknown_selected=int(g.unknown_selected.sum()),matched_dates=int(g.matched_all_arms.sum()),matched_picks=int(g.loc[g.matched_all_arms,'K'].sum()),selected_slow_unknown=int(g.selected_slow_unknown.sum()),selected_PVR_unknown=int(g.selected_PVR_unknown.sum()),fast_nonpositive_count=int(g.fast_nonpositive_count.sum()),slow_nonpositive_count=int(g.slow_nonpositive_count.sum())))
    pd.DataFrame(cov).to_csv(out/'ALL_SOURCE_PICK_COVERAGE.csv',index=False)
    # Keep full-source tail counts and valid partial labels explicitly apart.
    av=[]
    for keys,g in daily.groupby(['family','period','arm']):
        row=dict(family=keys[0],period=keys[1],arm=keys[2],source_dates=len(g),source_picks=int(g.K.sum()),known_selected=int(g.known_selected.sum()),unknown_selected=int(g.unknown_selected.sum()))
        for t in ['peak30','terminal30']:
            a=int(g[t+'_selected_known_tails'].sum());u=int(g.unknown_selected.sum());K=int(g.K.sum())
            row[t+'_known_tails']=a;row[t+'_precision_count_lower']=a/K;row[t+'_precision_count_upper']=(a+u)/K
        av.append(row)
    pd.DataFrame(av).to_csv(out/'ALL_SOURCE_TAIL_PRECISION_BOUNDS.csv',index=False)
    base=matched[matched.arm=='PVR'][['family','window','day']+metrics]
    comp=matched.merge(base,on=['family','window','day'],suffixes=('','_PVR'),validate='many_to_one')
    for m in metrics:comp['delta_'+m]=comp[m]-comp[m+'_PVR']
    dcols=['delta_'+m for m in metrics]
    comp[['family','period','window','day','arm','K']+dcols].to_parquet(out/'MATCHED_DAY_ARM_DELTAS_VS_PVR.parquet',index=False)
    delta=comp.groupby(['family','period','arm'])[dcols].mean().reset_index();delta.to_csv(out/'MATCHED_DAY_EQUAL_DELTAS_VS_PVR.csv',index=False)
    calpath=ROOT.parent/'pvr_information_v1/export/FEATURE_MANIFEST_PRE_LABEL.json'
    cal=json.loads(calpath.read_text())['calendars'];cr=[]
    for window,dates in cal.items():
        cr += [dict(window=window,day=day,block20=n//20)for n,day in enumerate(dates)]
    cb=comp.merge(pd.DataFrame(cr),on=['window','day'],validate='many_to_one')
    block=cb.groupby(['family','period','window','block20','arm'])[dcols].mean().reset_index()
    block.to_csv(out/'FIXED20_SESSION_BLOCK_DELTAS.csv',index=False)
    br=[]
    for keys,g in block.groupby(['family','period','arm']):
        for m in ['delta_mean_ret20_open','delta_peak30_precision_lower','delta_mean_mae20_open']:
            br.append(dict(family=keys[0],period=keys[1],arm=keys[2],metric=m,blocks=len(g),positive_blocks=int(g[m].gt(0).sum()),negative_blocks=int(g[m].lt(0).sum()),median_delta=float(g[m].median()),min_delta=float(g[m].min()),max_delta=float(g[m].max())))
    pd.DataFrame(br).to_csv(out/'FIXED20_SESSION_BLOCK_SUMMARY.csv',index=False)
    save(out/'COMPLETION.json',dict(status='COMPLETE_FIXED_EQUAL_TICKET_PRICE_DIAGNOSIS_NOT_ACCOUNT',
      sources={str(p.resolve()):sha(p)for p in[Path(__file__),ROOT/'FREEZE.json',lockpath,RANK,LABEL,calpath]},
      outputs={p.name:sha(p)for p in out.iterdir()if p.is_file()},new_accounts=0,no_IID_inference=True,no_future_replacement=True,elapsed_seconds=time.monotonic()-start))
    print(pd.DataFrame(summaries)[['family','period','arm','matched_dates','source_picks','mean_ret20_open','terminal_q10','terminal_q50','terminal_q90','mean_mfe20_open','mean_mae20_open','peak30_precision_lower','peak30_known_capture','peak30_lost_PVR_tails','peak30_gained_PVR_tails']].to_string(index=False))

if __name__=='__main__':main()
