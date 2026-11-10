"""Summarize the frozen states; no signal fitting, accounts or future-return labels."""
from pathlib import Path
import collections,json,math
import numpy as np
import pandas as pd
from study import HERE,START,END,SAMPLES,clean,dump,sha,bridge

def csv(name,rows):
    f=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    f.to_csv(HERE/name,index=False,encoding='utf-8-sig')
def first(f,col):
    q=f.index[f[col]];return str(q[0].date()) if len(q) else None
def order(ids,scores):
    fallback=any(scores.get(i) is None or not math.isfinite(scores[i]) for i in ids)
    return (sorted(ids) if fallback else sorted(ids,key=lambda i:(-round(scores[i],12),i))),fallback

def main():
    if (HERE/'analysis-complete.json').exists():raise FileExistsError('analysis already completed')
    complete=json.loads((HERE/'run-complete.json').read_text());coverage=pd.read_csv(HERE/'coverage.csv',dtype={'symbol':str}).fillna('')
    assert not coverage.error_type.eq('AssertionError').any(),'Technical assertion failure cannot be classified as a data exclusion'
    inv=pd.read_csv(HERE/'universe.csv',dtype={'symbol':str}).fillna('');metadata=inv.set_index('symbol').to_dict('index')
    for sid,v in metadata.items():
        if not str(v['name']).strip():v['name']='名称未核 '+sid
    sectors={p.stem:pd.read_parquet(p) for p in sorted((HERE/'sector-daily').glob('*.parquet'))}
    cal=pd.DatetimeIndex(sorted(set(d for f in sectors.values() for d in f.index)));assert len(cal)==242
    sector_info={sid:dict(name=str(f.sector_name.iloc[0])) for sid,f in sectors.items()}
    sector_rows=[]
    for sid,f in sectors.items():
        f['own_up']=f.own_ready.eq(1)&f.own_target.eq(1)
        f['own_watch']=f.own_ready.eq(1)&(f.own_target.eq(1)|f.own_pending.eq(1))
        f['chan_up']=f.chan_up.eq(1);f['chan_watch']=f.chan_watch.eq(1)
        for dt,r in f.iterrows():sector_rows.append(dict(date=dt,sector_id=sid,sector_name=sector_info[sid]['name'],rs=r.own_rs,own_up=bool(r.own_up),chan_up=bool(r.chan_up),own_watch=bool(r.own_watch),chan_watch=bool(r.chan_watch)))
    sector_table=pd.DataFrame(sector_rows);csv('sector-daily.csv',sector_table)
    books={m:collections.defaultdict(lambda:collections.defaultdict(list)) for m in ('own','chan')}
    counts={m:collections.Counter() for m in ('own','chan')};wcounts={m:collections.Counter() for m in ('own','chan')}
    monthly_sets={m:collections.defaultdict(set) for m in ('own','chan')}
    paired=[];events=[];watch_events=[];stock_summary=[];both_count=collections.Counter();union_count=collections.Counter()
    for p in sorted((HERE/'daily').glob('*.parquet')):
        f=pd.read_parquet(p);sid=p.stem;meta=metadata[sid];sec=sectors[meta['sector_id']].reindex(f.index)
        f['own_up']=f.own_ready.eq(1)&f.own_target.eq(1)
        f['own_watch']=f.own_ready.eq(1)&(f.own_target.eq(1)|f.own_pending.eq(1))
        f['chan_up']=f.chan_up.eq(1);f['chan_watch']=f.chan_watch.eq(1)
        tradable=f.volume.gt(0)&np.isfinite(f.volume)
        for m in ['own','chan']:
            f[m+'_q']=f[m+'_up']&sec[m+'_up'].fillna(False)&tradable
            f[m+'_wq']=f[m+'_watch']&sec[m+'_watch'].fillna(False)&tradable
        sr=dict(symbol=sid,name=meta['name'],sector_id=meta['sector_id'],sector_name=meta['sector_name'],observations=len(f),cap_status='未知，未用于筛选')
        for m in ['own','chan']:
            q=f[m+'_q'];wq=f[m+'_wq'];sr[m+'_first_watch']=first(f,m+'_wq');sr[m+'_first']=first(f,m+'_q')
            sr[m+'_days']=int(q.sum());sr[m+'_watch_days']=int(wq.sum())
            starts=q&~q.shift(fill_value=False);sr[m+'_episodes']=int(starts.sum());sr[m+'_carry_in']=bool(q.iloc[0] and f.index[0]==cal[0])
            for dt,r in f.loc[q].iterrows():
                rs=clean(r.own_rs);sf=sectors[meta['sector_id']].loc[dt]
                floor=clean(r.own_floor if m=='own' else r.chan_floor)
                floor_raw=floor/r.adjustment_factor if floor is not None else None
                rec=dict(symbol=sid,name=meta['name'],rs=rs,close=clean(r.raw_close),floor=floor_raw,sector_id=meta['sector_id'],sector_name=meta['sector_name'])
                books[m][str(dt.date())][meta['sector_id']].append(rec);counts[m][dt]+=1;monthly_sets[m][str(dt.to_period('M'))].add(sid)
            for dt in f.index[wq]:wcounts[m][dt]+=1
            for dt in f.index[starts]:
                r=f.loc[dt];sf=sectors[meta['sector_id']].loc[dt];i=f.index.get_loc(dt)
                sp=(i>0 and bool(f[m+'_up'].iloc[i-1]));sidx=sectors[meta['sector_id']].index.get_loc(dt)
                gp=(sidx>0 and bool(sectors[meta['sector_id']][m+'_up'].iloc[sidx-1]))
                origin=('年初既有状态承接' if i==0 and dt==cal[0] else '板块确认后承接个股已有结构' if sp and not gp else '个股确认，板块已通过' if gp and not sp else '板块与个股同时确认' if not sp and not gp else '可见行情或成交量恢复')
                floor=clean(r.own_floor if m=='own' else r.chan_floor)
                events.append(dict(date=str(dt.date()),method=m,symbol=sid,name=meta['name'],sector_id=meta['sector_id'],sector_name=meta['sector_name'],
                    stock_rs=clean(r.own_rs),sector_rs=clean(sf.own_rs),close_raw=clean(r.raw_close),floor_raw=floor/r.adjustment_factor if floor is not None else None,
                    origin=origin,signal_kind=(str(r.own_entry_kind) if r.own_entered else '已有上行结构') if m=='own' else (str(r.chan_cause) or '已有结构'),
                    stock_confirmation_date=(str(dt.date()) if r.own_entered else None) if m=='own' else (str(r.chan_recognized) or None),
                    endpoint_date=None if m=='own' or pd.isna(r.chan_endpoint) else str(r.chan_endpoint),cap_status='unknown_not_applied'))
            for dt in f.index[wq&~wq.shift(fill_value=False)]:watch_events.append(dict(date=str(dt.date()),method=m,symbol=sid,name=meta['name'],sector_name=meta['sector_name'],participation=bool(f.at[dt,m+'_q'])))
        sr['both_days']=int((f.own_q&f.chan_q).sum());sr['own_only_days']=int((f.own_q&~f.chan_q).sum());sr['chan_only_days']=int((f.chan_q&~f.own_q).sum())
        sr['category']='两者全年都曾选择' if sr['own_days'] and sr['chan_days'] else '仅趋势法曾选择' if sr['own_days'] else '仅缠论法曾选择' if sr['chan_days'] else '两者均未选择'
        sr['first_lag_sessions']=int(cal.get_loc(pd.Timestamp(sr['chan_first']))-cal.get_loc(pd.Timestamp(sr['own_first']))) if sr['own_first'] and sr['chan_first'] else None
        stock_summary.append(sr)
        for dt in f.index[f.own_q&f.chan_q]:both_count[dt]+=1
        for dt in f.index[f.own_q|f.chan_q]:union_count[dt]+=1
        z=f[['own_q','chan_q','own_wq','chan_wq']].copy();z['symbol']=sid;paired.append(z.reset_index())
    summary=pd.DataFrame(stock_summary);csv('stock-year-comparison.csv',summary)
    pd.concat(paired,ignore_index=True).to_parquet(HERE/'paired-daily-selection.parquet',index=False)
    rankmap={};days=[];rank_fallbacks=[];daily_records=[]
    for dt in cal:
        ds=str(dt.date());day=dict(date=ds,own_count=counts['own'][dt],chan_count=counts['chan'][dt],both=both_count[dt],union=union_count[dt],own_watch=wcounts['own'][dt],chan_watch=wcounts['chan'][dt],methods={})
        for m in ['own','chan']:
            groups=books[m][ds];scores={g:clean(sectors[g].at[dt,'own_rs']) for g in groups}
            gids,gfallback=order(groups,scores);out=[]
            if gfallback:rank_fallbacks.append(dict(date=ds,method=m,group='industries'))
            for gi,g in enumerate(gids,1):
                recs={r['symbol']:r for r in groups[g]};sids,sfallback=order(recs,{s:r['rs'] for s,r in recs.items()})
                if sfallback:rank_fallbacks.append(dict(date=ds,method=m,group=g))
                vals=[]
                for si,s in enumerate(sids,1):
                    rr=dict(recs[s],sector_rank=gi,stock_rank=si,date=ds,method=m,ranking='代码顺序' if sfallback else 'RS降序')
                    rankmap[(m,ds,s)]=(gi,si,rr['ranking']);daily_records.append(rr)
                    if si<=3:vals.append(rr)
                out.append(dict(sector_id=g,name=sector_info[g]['name'],rank=gi,rs=scores[g],count=len(sids),stocks=vals,ranking='代码顺序' if sfallback else 'RS降序'))
            day['methods'][m]=out
            day[m+'_sector_count']=int(sum(bool(f.at[dt,m+'_up']) for f in sectors.values() if dt in f.index))
        days.append(day)
    for e in events:
        e['sector_rank'],e['stock_rank'],e['ranking']=rankmap[(e['method'],e['date'],e['symbol'])]
    event_df=pd.DataFrame(events).sort_values(['date','method','sector_rank','stock_rank','symbol']);csv('opening-events.csv',event_df)
    csv('attention-events.csv',pd.DataFrame(watch_events).sort_values(['date','method','symbol']))
    # Complete daily selection, with no presentation cutoffs or slot caps.
    csv('daily-candidates.csv',pd.DataFrame(daily_records).sort_values(['date','method','sector_rank','stock_rank']))
    csv('ranking-fallbacks.csv',rank_fallbacks)
    daily_summary=pd.DataFrame([{k:v for k,v in d.items() if k!='methods'} for d in days]);csv('daily-summary.csv',daily_summary)
    monthly=[];month_end=[];month_sector=[]
    for month,g in daily_summary.groupby(daily_summary.date.str[:7]):
        last=next(d for d in days if d['date']==g.date.iloc[-1]);a=monthly_sets['own'][month];b=monthly_sets['chan'][month]
        e=event_df.loc[event_df.date.str.startswith(month)]
        r=dict(month=month,last_session=last['date'],own_unique=len(a),chan_unique=len(b),both_unique=len(a&b),own_only=len(a-b),chan_only=len(b-a),
            own_new=int((e.method.eq('own')&e.origin.ne('年初既有状态承接')).sum()),chan_new=int((e.method.eq('chan')&e.origin.ne('年初既有状态承接')).sum()),
            own_end=last['own_count'],chan_end=last['chan_count'],own_sectors_end=last['own_sector_count'],chan_sectors_end=last['chan_sector_count'])
        for m in ['own','chan']:
            r[m+'_examples']='；'.join(x['name']+'：'+ '、'.join(y['name']+' '+y['symbol'].split('.')[0] for y in x['stocks'][:2]) for x in last['methods'][m][:3])
        monthly.append(r)
        for rr in daily_records:
            if rr['date']==last['date']:month_end.append(rr)
        for sid,f in sectors.items():
            z=f.loc[f.index.strftime('%Y-%m')==month]
            if z.empty:continue
            month_sector.append(dict(month=month,sector_id=sid,sector_name=sector_info[sid]['name'],own_up_days=int(z.own_up.sum()),chan_up_days=int(z.chan_up.sum()),own_watch_days=int(z.own_watch.sum()),chan_watch_days=int(z.chan_watch.sum()),rs_end=clean(z.own_rs.iloc[-1])))
    csv('monthly-comparison.csv',monthly);csv('month-end-candidates.csv',month_end);csv('sector-monthly.csv',month_sector)
    excluded=coverage.loc[coverage.status.ne('included'),['symbol','name','sector_name','reason']].to_dict('records')
    excluded.extend({k:r[k] for k in ['symbol','name','sector_name','reason']} for r in inv.loc[~inv.eligible_raw.astype(bool)].to_dict('records'))
    csv('excluded.csv',excluded)
    core=dict(sample_included=len(summary),raw_2024_candidates=int(coverage.shape[0]),inventory=len(inv),excluded_2024=int(len(coverage)-len(summary)),
        retired_without_matching_industry=int(inv.scope.eq('available_retired').sum()),sessions=len(cal),industries=len(sectors),
        own_unique=int(summary.own_days.gt(0).sum()),chan_unique=int(summary.chan_days.gt(0).sum()),both_unique=int((summary.own_days.gt(0)&summary.chan_days.gt(0)).sum()),
        own_only_unique=int((summary.own_days.gt(0)&summary.chan_days.eq(0)).sum()),chan_only_unique=int((summary.own_days.eq(0)&summary.chan_days.gt(0)).sum()),
        own_stock_days=int(summary.own_days.sum()),chan_stock_days=int(summary.chan_days.sum()),both_stock_days=int(summary.both_days.sum()),
        own_episodes=int(summary.own_episodes.sum()),chan_episodes=int(summary.chan_episodes.sum()),ranking_fallbacks=len(rank_fallbacks),
        algorithm_changes=0,account_runs=0,market_downloads=0)
    # Diagnostic examples selected without any forward-return criterion.
    cases=[s for s in SAMPLES if (HERE/'daily'/(s+'.parquet')).exists()]
    diag=summary.assign(disagreement=(summary.own_days-summary.chan_days).abs()).loc[summary.observations.ge(60)].sort_values(['disagreement','symbol'],ascending=[False,True]).head(2)
    cases=list(dict.fromkeys(cases+diag.symbol.tolist()))
    chart_data=[]
    for sid in cases:
        f=pd.read_parquet(HERE/'daily'/(sid+'.parquet'));meta=metadata[sid];sec=sectors[meta['sector_id']].reindex(f.index)
        base=float(f.close.iloc[0]);sbase=float(sec.close.iloc[0]);p=pd.read_parquet(HERE/'paired-daily-selection.parquet',filters=[('symbol','=',sid)]).set_index('date')
        chart_data.append(dict(symbol=sid,name=meta['name'],sector_name=meta['sector_name'],summary=summary.loc[summary.symbol.eq(sid)].iloc[0].to_dict(),
            rows=[dict(date=str(dt.date()),price=100*r.close/base,own_floor=clean(100*r.own_floor/base),chan_floor=clean(100*r.chan_floor/base),
                       sector_price=100*sec.at[dt,'close']/sbase,own_q=bool(p.at[dt,'own_q']),chan_q=bool(p.at[dt,'chan_q']),
                       own_sector=bool(sec.at[dt,'own_up']),chan_sector=bool(sec.at[dt,'chan_up']),volume=float(r.volume)) for dt,r in f.iterrows()]))
    dump(HERE/'report-data.json',dict(summary=core,monthly=monthly,days=days,cases=chart_data,stock_summary=stock_summary,sector_monthly=month_sector,excluded=excluded))
    dump(HERE/'workbook-data.json',dict(summary=core,monthly=monthly,stocks=stock_summary,sector_monthly=month_sector,excluded=excluded))
    # Independent reconciliation against all saved paired booleans.
    pairs=pd.read_parquet(HERE/'paired-daily-selection.parquet')
    assert int(pairs.own_q.sum())==core['own_stock_days'];assert int(pairs.chan_q.sum())==core['chan_stock_days']
    assert int((pairs.own_q & pairs.chan_q).sum())==core['both_stock_days']
    assert len(daily_records)==core['own_stock_days']+core['chan_stock_days']
    assert len(summary.symbol.unique())==len(summary)
    dump(HERE/'analysis-complete.json',dict(summary=core,paired_rows=len(pairs),rank_and_count_reconciliation=True,outputs={p.name:sha(p) for p in HERE.glob('*.csv')},prefix_checks=complete['prefix_checks']))
    print(json.dumps(core,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
