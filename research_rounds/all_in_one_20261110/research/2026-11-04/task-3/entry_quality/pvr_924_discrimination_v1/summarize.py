"""Fixed prior-rank groups, then price-only future labels. No models/accounts."""
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
SCOPES={'ALL':('rank_ALL_LOCAL_I_BUY',2313),'OLD':('rank_OLD1709_STATIC_REFERENCE_I_BUY',997),'OUTSIDE':('rank_OUTSIDE_OLD1709_I_BUY',1316)}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bands(g,rankcol,decile):
    yield 'ALL',g
    for d in range(1,11):yield f'D{d}',g.loc[g[decile].eq(d)]
    for k in [20,100]:
        yield f'TOP{k}',g.loc[g[rankcol].le(k)]
        yield f'REST{k}',g.loc[g[rankcol].gt(k)]


def stats(g,h,tail,denoms,view,scope,band):
    c=g.loc[g[f'h{h}_complete'].eq(True)].copy();N=len(g);n=len(c)
    r=dict(view=view,scope=scope,band=band,horizon=h,prior_N=N,complete_N=n,unknown_N=N-n,
           horizon_censored_N=int(g[f'h{h}_right_censored'].eq(True).sum()),
           source_gap_proxy_N=int(g[f'h{h}_source_union_missing_row_proxy'].gt(0).sum()))
    for field,label in [('return','terminal'),('max_up','MFE'),('max_adverse','MAE_signed')]:
        v=c[f'h{h}_{field}']
        r.update({label+'_mean':v.mean(),label+'_median':v.median(),label+'_p10':v.quantile(.1),label+'_p90':v.quantile(.9),label+'_min':v.min(),label+'_max':v.max()})
        if field=='return':r.update(terminal_p25=v.quantile(.25),terminal_p75=v.quantile(.75))
    r['terminal_positive_N']=int(c[f'h{h}_return'].gt(0).sum());r['terminal_positive_rate_complete']=r['terminal_positive_N']/n if n else np.nan
    r['terminal_positive_fraction_prior']=r['terminal_positive_N']/N if N else np.nan
    for field,label in [('return','terminal'),('max_up','MFE')]:
        for cut in [.2,.5,1.0]:
            count=int(c[f'h{h}_{field}'].ge(cut).sum());r[f'{label}_ge{int(cut*100)}pct_N']=count;r[f'{label}_ge{int(cut*100)}pct_rate']=count/n if n else np.nan
    for cut in [.1,.2]:r[f'terminal_le_minus{int(cut*100)}pct_rate']=float(c[f'h{h}_return'].le(-cut).mean())
    r['positive_terminal_change_mass_share']=c[f'h{h}_return'].clip(lower=0).sum()/denoms['positive_terminal'] if denoms['positive_terminal'] else np.nan
    r['MFE_change_mass_share']=c[f'h{h}_max_up'].sum()/denoms['MFE'] if denoms['MFE'] else np.nan
    # Apply the already-frozen largest1/5/20 concentration definition inside
    # each fixed prior group as well; labels never become a new ranking rule.
    ordered=c.sort_values([f'h{h}_return','sid'],ascending=[False,True])
    mass=ordered[f'h{h}_return'].clip(lower=0);total=float(mass.sum())
    for k in [1,5,20]:r[f'within_group_largest{k}_positive_terminal_mass_share']=float(mass.head(k).sum())/total if total else np.nan
    r['terminal_mean_excluding_expost_largest1_diagnostic']=ordered.iloc[1:][f'h{h}_return'].mean()
    for label,ids in tail.items():
        hit=int(c.sid.isin(ids).sum());r[label+'_global_N']=len(ids);r[label+'_hits']=hit
        r[label+'_capture_global_complete']=hit/len(ids)if ids else np.nan;r[label+'_precision_group_complete']=hit/n if n else np.nan
    r['actual_nth_date_min']=c[f'h{h}_nth_date'].min() if n else None;r['actual_nth_date_max']=c[f'h{h}_nth_date'].max()if n else None
    r['calendar_span_min']=c[f'h{h}_calendar_span_days'].min();r['calendar_span_max']=c[f'h{h}_calendar_span_days'].max()
    # Availability-only consistency diagnostic, not a new selection rule:
    # common earliest hth observed date, never chosen from return performance.
    expected={5:'2024-10-08',20:'2024-10-29'}[h]
    aligned=c.loc[c[f'h{h}_nth_date'].eq(expected)]
    r['common_endpoint_date']=expected;r['common_endpoint_N']=len(aligned)
    for field,label in [('return','terminal'),('max_up','MFE'),('max_adverse','MAE_signed')]:r['common_endpoint_'+label+'_mean']=aligned[f'h{h}_{field}'].mean()
    return r


def main():
    prior=HERE/'FROZEN2313_PRIOR_RANKS.parquet';p=pd.read_parquet(prior)
    receipt=json.loads((HERE/'PRIOR_RANKS_RECEIPT.json').read_text());assert sha(prior)==receipt['prior_rank_sha256']
    paths=HERE/'paths/HORIZON_PATHS.parquet';f=pd.read_parquet(paths)
    assert len(p)==len(f)==2313 and set(p.sid)==set(f.sid)
    assert p.set_index('sid').current_close_qfq.equals(f.set_index('sid').loc[p.sid].anchor_close.rename('current_close_qfq'))
    f=f.drop(columns=['day','rank_ALL_LOCAL_I_BUY']);x=p.merge(f,on='sid',validate='one_to_one')
    assert x.rank_ALL_LOCAL_I_BUY.tolist()==list(range(1,2314))
    rows=[];concentrations=[];labels=[]
    for h in [5,20]:
        c=x.loc[x[f'h{h}_complete'].eq(True)].copy();ordered=c.sort_values([f'h{h}_return','sid'],ascending=[False,True])
        tail={f'EXPOST_TOP{pc}PCT':set(ordered.head(math.ceil(len(c)*pc/100)).sid)for pc in [1,5]}
        denoms={'positive_terminal':float(c[f'h{h}_return'].clip(lower=0).sum()),'MFE':float(c[f'h{h}_max_up'].sum())}
        for label,ids in tail.items():
            for sid in ids:labels.append(dict(sid=sid,horizon=h,label=label,label_universe_complete_N=len(c),not_prior_rank=True))
        for scope,(rankcol,N)in SCOPES.items():
            g=x.loc[x[rankcol].notna()];assert len(g)==N
            for band,z in bands(g,rankcol,'decile_'+scope):rows.append(stats(z,h,tail,denoms,'WITHIN_SCOPE_RANKS',scope,band))
            cc=g.loc[g[f'h{h}_complete'].eq(True)]
            for field,label in [('return','positive_terminal'),('max_up','MFE')]:
                mass=cc[f'h{h}_{field}'].clip(lower=0);total=float(mass.sum())
                zz=cc.assign(_mass=mass).sort_values(['_mass','sid'],ascending=[False,True])
                for k in [1,5,20]:concentrations.append(dict(scope=scope,horizon=h,price_mass_type=label,complete_N=len(cc),expost_largest_k=k,
                    total_positive_price_change_mass=total,largest_k_mass=float(zz.head(k)._mass.sum()),largest_k_share=float(zz.head(k)._mass.sum())/total if total else np.nan,
                    price_path_only_not_portfolio_profit=True))
        for band,g in bands(x,'rank_ALL_LOCAL_I_BUY','decile_ALL'):
            for scope,m in [('OLD',True),('OUTSIDE',False)]:
                rows.append(stats(g.loc[g.in_old1709_exact.eq(m)],h,tail,denoms,'GLOBAL_BANDS_BY_MEMBERSHIP',scope,band))
    results=pd.DataFrame(rows);results.to_csv(HERE/'GROUP_SUMMARIES.csv',index=False)
    pd.DataFrame(concentrations).to_csv(HERE/'TAIL_PRICE_CONCENTRATION.csv',index=False)
    pd.DataFrame(labels).to_csv(HERE/'EXPOST_DIAGNOSTIC_LABELS_ONLY.csv',index=False)
    x.to_parquet(HERE/'FROZEN_RANKS_WITH_PRICE_LABELS.parquet',index=False,compression='zstd')
    x.to_csv(HERE/'FROZEN_RANKS_WITH_PRICE_LABELS.csv',index=False)
    selected=results.loc[results.view.eq('WITHIN_SCOPE_RANKS')&results.band.isin(['ALL','TOP20','REST20','TOP100','REST100'])]
    selected.to_csv(HERE/'TOP_VS_REST_MAIN.csv',index=False)
    inputs={str(q):sha(q)for q in [prior,paths,HERE/'FREEZE.json',Path(__file__).resolve()]}
    (HERE/'SUMMARY_RECEIPT.json').write_text(json.dumps(dict(status='COMPLETE_FIXED_PRIOR_PVR_PRICE_PATH_DESCRIPTION_NO_ACCOUNT',N=2313,group_rows=len(results),input_sha256=inputs,
        common_endpoint_sensitivity='Added after availability metadata and before aggregate outcome analysis, fixed earliest common hth date10/8 and10/29; does not change primary fixed-rank groups or replace missing. No threshold/performance fitting.',
        global_expost_labels_only=True,no_new_signals_or_accounts=True),indent=2)+'\n')
    print(selected.loc[selected.scope.eq('ALL'),['horizon','band','prior_N','complete_N','terminal_mean','terminal_median','MFE_mean','MAE_signed_mean','terminal_positive_rate_complete','EXPOST_TOP1PCT_hits']].to_string(index=False),flush=True)


if __name__=='__main__':main()
