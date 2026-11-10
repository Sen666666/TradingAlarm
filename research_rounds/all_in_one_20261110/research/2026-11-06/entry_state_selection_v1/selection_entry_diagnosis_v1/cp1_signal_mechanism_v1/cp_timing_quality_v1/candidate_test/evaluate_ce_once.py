"""One complete evaluation of the already frozen CE membership. No fitting or accounts."""
from pathlib import Path
import json,hashlib,math,time,traceback
import pandas as pd,numpy as np
from prepare_ce import order
O=Path(__file__).resolve().parent;B=O.parents[2]/'mobile_candidate_response_v1'
MARKET=B.parent/'MARKET_FIXED1709_WARM.csv'
CAL=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
STRATEGIES=['ORIGINAL_PVR','CP_TIMING_CE'];KEY=['account','day','sid']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,x):(O/n).write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str))
def hm(g,H):
    z=g[g[f'complete{H}']];r=z[f'ret{H}'];win=r[r>0];loss=r[r<0];d=z.groupby('day')
    return dict(selected=len(g),complete=len(z),unknown=len(g)-len(z),right_censored=int((~g[f'complete{H}']&g[f'right_censored{H}']).sum()),missing_entry_open=int((~g[f'complete{H}']&~g[f'right_censored{H}']&~g.open_known).sum()),incomplete_interior_path=int((~g[f'complete{H}']&~g[f'right_censored{H}']&g.open_known).sum()),signal_days=g.day.nunique(),complete_days=z.day.nunique(),stocks=g.sid.nunique(),path_wins=len(win),path_losses=len(loss),path_zeros=int(r.eq(0).sum()),path_win_rate=r.gt(0).mean(),avg_win=win.mean(),avg_loss=loss.mean(),win_loss_ratio=win.mean()/abs(loss.mean()) if len(loss) and len(win) else np.nan,profit_factor=win.sum()/abs(loss.sum()) if len(loss) else np.nan,event_mean_return=r.mean(),day_equal_return=d[f'ret{H}'].mean().mean(),event_sum_return=r.sum(min_count=1),mean_close_MAE=z[f'mae{H}'].mean(),day_equal_close_MAE=d[f'mae{H}'].mean().mean())
def aggregate(df,groups,name):
    out=pd.DataFrame([dict(**dict(zip(groups,key if isinstance(key,tuple) else (key,))),horizon=H,**hm(g,H)) for key,g in df.groupby(groups,sort=True) for H in [5,20]])
    out.to_csv(O/name,index=False);return out

def main():
    start=time.monotonic();assert not (O/'EVALUATION_STARTED.json').exists(),'No repeated complete evaluation.'
    sourcefiles=[O/'CANDIDATE_CE.parquet',O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet',O/'FULL_QUEUE_ORDERS.parquet',O/'QUEUE_COUNTS.csv',O/'prepare_ce.py',O/'RANK_SEAL.json',B/'LEGAL_EMPTY_MOBILE_CANDIDATES.parquet',B/'FIXED_NATIVE_PRICE_LABELS.parquet',B/'SEALED_SAME_K_SELECTIONS.parquet',B/'ROOT_EPISODE_COVERAGE.csv',MARKET,CAL,Path(__file__)]
    sources={str(p):sha(p) for p in sourcefiles};dump('EVALUATION_SOURCE_BEFORE.json',sources)
    seal=json.loads((O/'RANK_SEAL.json').read_text());assert sha(O/'CANDIDATE_CE.parquet')==seal['score_sha256'];assert sha(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet')==seal['selections_sha256'];assert sha(O/'prepare_ce.py')==seal['script_sha256']
    sc=pd.read_parquet(O/'CANDIDATE_CE.parquet');selected=pd.read_parquet(O/'SEALED_SELECTIONS_BEFORE_LABELS.parquet');mov=pd.read_parquet(O/'FULL_QUEUE_ORDERS.parquet');queue=pd.read_csv(O/'QUEUE_COUNTS.csv')
    assert len(sc)==103766 and len(selected)==55980
    cols=['account','day','selected_rank','sid','CP1_id'];old=pd.read_parquet(B/'SEALED_SAME_K_SELECTIONS.parquet',columns=cols+['strategy'])
    pd.testing.assert_frame_equal(selected[selected.strategy=='ORIGINAL_PVR'][cols].sort_values(cols[:3]).reset_index(drop=True),old[old.strategy=='ORIGINAL_PVR'][cols].sort_values(cols[:3]).reset_index(drop=True),check_dtype=False)
    dump('EVALUATION_STARTED.json',dict(started_utc=pd.Timestamp.now(tz='UTC').isoformat(),single_complete_pass=True,formula_changes=0,parameter_scans=0,previous_18_example_diagnostic_already_seen=True,all_history_consumed_development_not_blind_not_OOS=True))
    labels=pd.read_parquet(B/'FIXED_NATIVE_PRICE_LABELS.parquet');assert len(labels)==54852 and not labels.duplicated(['sid','day']).any()
    market=pd.read_csv(MARKET,index_col=0,keep_default_na=False);h=np.load(CAL,allow_pickle=False);calendar=pd.DatetimeIndex(h['dates']);calendar=calendar[(calendar>='2022-01-01')&(calendar<='2026-05-15')];ncal=len(calendar)
    sc=sc.merge(labels,on=['sid','day'],validate='many_to_one');selected=selected.merge(labels,on=['sid','day'],validate='many_to_one')
    for df in [sc,selected]:
        df['quarter']=pd.to_datetime(df.day).dt.to_period('Q').astype(str);df['market_state']=df.day.map(market.regime);assert df.market_state.notna().all() and df.t.notna().all()
        df['signal_price_return']=np.expm1(df.source_r);df['original_CP_excess']=np.minimum(df.source_displacement,df.source_credit)/(math.sqrt(5)*df.sigma_frozen)
        for H in [5,20]:
            df[f'right_censored{H}']=df.t+H>=ncal;assert df.loc[df[f'complete{H}'],[f'ret{H}',f'mae{H}']].notna().all().all()
    selected.to_parquet(O/'SELECTED_WITH_FIXED_LABELS.parquet',index=False)
    annual=aggregate(selected,['account','year','strategy'],'ANNUAL_OUTCOMES.csv');overall=aggregate(selected,['account','strategy'],'OVERALL_OUTCOMES.csv');aggregate(selected,['account','quarter','strategy'],'QUARTER_OUTCOMES.csv');aggregate(selected,['account','year','market_state','strategy'],'MARKET_STATE_BY_YEAR_OUTCOMES.csv');aggregate(selected,['account','market_state','strategy'],'MARKET_STATE_OUTCOMES.csv')
    replacement=mov[mov.original_selected!=mov.CE_selected].copy();replacement['side']=np.where(replacement.CE_selected,'added','removed');replacement=replacement[['account','day','sid','original_rank','CE_rank','side']].merge(sc,on=KEY,validate='one_to_one');replacement.to_parquet(O/'REPLACEMENTS_WITH_FIXED_LABELS.parquet',index=False)
    aggregate(replacement,['account','year','side'],'ANNUAL_ADDED_REMOVED_OUTCOMES.csv');aggregate(replacement,['account','quarter','side'],'QUARTER_ADDED_REMOVED_OUTCOMES.csv');aggregate(replacement,['account','market_state','side'],'MARKET_ADDED_REMOVED_OUTCOMES.csv')
    # Root birth and boundary exactly retain the original root semantics.
    lookup={s:set(zip(g.account,g.day,g.sid,g.epoch)) for s,g in selected.groupby('strategy')};episodes=[]
    for (account,sid,epoch),g in sc.groupby(['account','sid','epoch'],sort=True):
        g=g.sort_values('t');b=g.iloc[0];early=g[g.t<=int(b.t)+5]
        row=dict(account=account,sid=sid,epoch=epoch,birth_day=b.day,year=int(b.year),complete60=bool(b.complete60),big60=bool(b.big60_posthoc),candidate_events=len(g),early_candidate_events=len(early))
        for s,ss in lookup.items():row[s+'_early_capture']=any((account,r.day,sid,epoch) in ss for r in early.itertuples())
        row['lost']=row['ORIGINAL_PVR_early_capture'] and not row['CP_TIMING_CE_early_capture'];row['added']=not row['ORIGINAL_PVR_early_capture'] and row['CP_TIMING_CE_early_capture'];episodes.append(row)
    ep=pd.DataFrame(episodes);olde=pd.read_csv(B/'ROOT_EPISODE_COVERAGE.csv',keep_default_na=False);ek=['account','sid','epoch'];rc=ek+['birth_day','year','complete60','big60','candidate_events','early_candidate_events','ORIGINAL_PVR_early_capture']
    pd.testing.assert_frame_equal(ep[rc].sort_values(ek).reset_index(drop=True),olde[rc].sort_values(ek).reset_index(drop=True),check_dtype=False)
    ep.to_csv(O/'ROOT_EPISODES.csv',index=False);ep[ep.big60&(ep.lost|ep.added)].to_csv(O/'BIG_ROOT_LOST_ADDED.csv',index=False)
    def rootmet(g):
        b=g[g.big60];return dict(roots=len(g),complete60_roots=int(g.complete60.sum()),unknown60_roots=int((~g.complete60).sum()),big_roots=len(b),base_captured=int(b.ORIGINAL_PVR_early_capture.sum()),CE_captured=int(b.CP_TIMING_CE_early_capture.sum()),lost=int(b.lost.sum()),added=int(b.added.sum()),net_added=int(b.added.sum()-b.lost.sum()),retained_baseline_fraction=int((b.ORIGINAL_PVR_early_capture&b.CP_TIMING_CE_early_capture).sum())/int(b.ORIGINAL_PVR_early_capture.sum()) if b.ORIGINAL_PVR_early_capture.sum() else np.nan)
    cov=pd.DataFrame([dict(account=a,year=int(y),**rootmet(g)) for (a,y),g in ep.groupby(['account','year'])]);cov.to_csv(O/'ANNUAL_BIG_ROOT_COVERAGE.csv',index=False)
    print('ANNUAL_PRIMARY_READY',flush=True);print(annual[['account','year','strategy','horizon','complete','path_win_rate','avg_win','avg_loss','win_loss_ratio','event_mean_return','mean_close_MAE']].to_string(index=False),flush=True);print('BIG_ROOT_COVERAGE',flush=True);print(cov.to_string(index=False),flush=True)
    # Full common-date pairing: both strategies must have every same-K selection complete.
    rows=[]
    for (account,day),g in selected.groupby(['account','day'],sort=True):
        for H in [5,20]:
            vals={s:hm(g[g.strategy==s],H) for s in STRATEGIES};b=vals['ORIGINAL_PVR'];a=vals['CP_TIMING_CE'];K=b['selected'];assert K==a['selected']
            row=dict(account=account,day=day,year=int(g.year.iloc[0]),quarter=g.quarter.iloc[0],market_state=g.market_state.iloc[0],horizon=H,K=K,both_all_complete=b['complete']==K and a['complete']==K)
            for label,v in [('base',b),('CE',a)]:
                for metric in ['complete','path_win_rate','event_mean_return','event_sum_return','mean_close_MAE']:row[label+'_'+metric]=v[metric]
            for metric in ['path_win_rate','event_mean_return','event_sum_return','mean_close_MAE']:row['diff_'+metric]=a[metric]-b[metric]
            rows.append(row)
    pair=pd.DataFrame(rows).merge(queue[['account','day','added']],on=['account','day'],validate='many_to_one');pair['changed']=pair.added.gt(0);pair.to_csv(O/'PAIRED_DATE_DETAILS.csv',index=False)
    def pairmet(g):
        z=g[g.both_all_complete];ch=z[z.changed];N=z.K.sum()
        return dict(all_dates=len(g),common_complete_dates=len(z),complete_events_per_strategy=int(N),changed_complete_dates=len(ch),base_day_equal_return=z.base_event_mean_return.mean(),CE_day_equal_return=z.CE_event_mean_return.mean(),day_paired_return_diff=z.diff_event_mean_return.mean(),event_paired_return_diff=z.diff_event_sum_return.sum()/N if N else np.nan,day_paired_win_rate_diff=z.diff_path_win_rate.mean(),event_paired_win_rate_diff=(z.diff_path_win_rate*z.K).sum()/N if N else np.nan,day_paired_MAE_diff=z.diff_mean_close_MAE.mean(),event_paired_MAE_diff=(z.diff_mean_close_MAE*z.K).sum()/N if N else np.nan,positive_return_diff_dates=int(z.diff_event_mean_return.gt(0).sum()),negative_return_diff_dates=int(z.diff_event_mean_return.lt(0).sum()),equal_return_diff_dates=int(z.diff_event_mean_return.eq(0).sum()),changed_day_paired_return_diff=ch.diff_event_mean_return.mean())
    for group,name in [(['account','year','horizon'],'MATCHED_COMPLETE_DATE_RESULTS.csv'),(['account','quarter','horizon'],'QUARTER_PAIRED_RESULTS.csv'),(['account','market_state','horizon'],'MARKET_PAIRED_RESULTS.csv'),(['account','horizon'],'OVERALL_PAIRED_RESULTS.csv')]:
        result=pd.DataFrame([dict(**dict(zip(group,key)),**pairmet(g)) for key,g in pair.groupby(group,sort=True)]);result.to_csv(O/name,index=False)
    common=[]
    for (account,year,H),g in pair.groupby(['account','year','horizon']):
        good=set(g[g.both_all_complete].day);zz=selected[(selected.account==account)&selected.year.eq(year)&selected.day.isin(good)]
        for s,ss in zz.groupby('strategy'):common.append(dict(account=account,year=int(year),horizon=H,strategy=s,**hm(ss,H)))
    pd.DataFrame(common).to_csv(O/'COMMON_COMPLETE_DATE_EVENT_METRICS.csv',index=False)
    # Explicit-root sensitivity excludes unknown root identity; no replacement grouping is invented.
    sensitivity=[]
    for (account,year),g in ep.groupby(['account','year']):
        for scope,z in [('original_all_roots',g),('explicit_epoch_only',g[~g.epoch.eq('None')]),('literal_None_epoch_only',g[g.epoch.eq('None')])]:sensitivity.append(dict(account=account,year=int(year),scope=scope,**rootmet(z)))
    pd.DataFrame(sensitivity).to_csv(O/'EPOCH_COVERAGE_SENSITIVITY.csv',index=False)
    changes=queue.groupby(['account','year']).agg(days=('day','size'),changed_days=('added',lambda s:int(s.gt(0).sum())),selected_per_strategy=('K','sum'),added=('added','sum'),unknown_score=('CE_unknown','sum'),unknown_PVR=('PVR_unknown','sum')).reset_index();changes['replacement_fraction']=changes.added/changes.selected_per_strategy;changes.to_csv(O/'ANNUAL_REPLACEMENTS.csv',index=False)
    def exposure(g):
        return dict(events=len(g),n1_count=int(g.formation_n.eq(1).sum()),n1_fraction=g.formation_n.eq(1).mean(),mean_n=g.formation_n.mean(),median_n=g.formation_n.median(),mean_signal_log_r=g.source_r.mean(),median_signal_log_r=g.source_r.median(),mean_signal_price_return=g.signal_price_return.mean(),median_signal_price_return=g.signal_price_return.median(),mean_prior21_RMS=g.sigma_recent.mean(),median_prior21_RMS=g.sigma_recent.median(),mean_PVR=g.original_PVR.mean(),median_PVR=g.original_PVR.median(),mean_H1=g.original_H1.mean(),median_H1=g.original_H1.median(),mean_H1_rank=g.original_H1_rank.mean(),mean_original_CP_excess=g.original_CP_excess.mean(),mean_CE=g.CE.mean(),i_buy_false_fraction=(~g.source_i_buy).mean(),unknown_PVR=int((~np.isfinite(g.original_PVR)).sum()))
    for group,name in [(['account','year','strategy'],'SELECTED_EXPOSURES_BY_YEAR.csv'),(['account','strategy'],'SELECTED_EXPOSURES_OVERALL.csv'),(['account','market_state','strategy'],'SELECTED_EXPOSURES_BY_MARKET.csv')]:pd.DataFrame([dict(**dict(zip(group,key)),**exposure(g)) for key,g in selected.groupby(group)]).to_csv(O/name,index=False)
    pd.DataFrame([dict(account=a,year=int(y),side=s,**exposure(g)) for (a,y,s),g in replacement.groupby(['account','year','side'])]).to_csv(O/'ADDED_REMOVED_EXPOSURES_BY_YEAR.csv',index=False)
    # Test all queues after destroying every label value: ranking input is restricted to original sealed columns.
    poison=sc.copy()
    for col in labels.columns:
        if col not in ['sid','day']:poison[col]=-999999 if pd.api.types.is_numeric_dtype(poison[col]) else 'POISON'
    expected={(a,d):g.sort_values('CE_rank').sid.tolist() for (a,d),g in mov.groupby(['account','day'])}
    for (a,d),g in poison.groupby(['account','day']):
        base,alt=order(g);assert g.loc[alt,'sid'].tolist()==expected[(a,d)]
        positions={i:j for j,i in enumerate(alt)};assert all(positions[i]==j for j,i in enumerate(base) if not g.at[i,'slot_replaceable'])
    for p,hsh in sources.items():assert sha(p)==hsh,(p,'source changed')
    dump('SUMMARY.json',dict(status='COMPLETE_ONE_FROZEN_CE_CANDIDATE_EVALUATION_NOT_ACCOUNT_NOT_OOS',candidate_rows=len(sc),unique_stock_days=len(labels),selected_per_strategy=len(selected)//2,baseline_exact=True,original_root_identity_exact=True,common_calendar_observations=ncal,unknown_epoch_candidates=int(sc.epoch.eq('None').sum()),unknown_epoch_roots=int(ep.epoch.eq('None').sum()),all_equal_K=True,all_queues_label_poison_unchanged=len(expected),unknown_slots_preserved=True,source_hashes_unchanged=True,original_indicator_runs=0,account_runs=0,parameter_scans=0,full_label_evaluation_passes=1,seconds=time.monotonic()-start))
    print('COMPLETE',json.dumps(json.loads((O/'SUMMARY.json').read_text())),flush=True)
if __name__=='__main__':
    try:main()
    except Exception:
        (O/('EVALUATION_TECHNICAL_FAILURE_'+str(time.time_ns())+'.txt')).write_text(traceback.format_exc());raise
