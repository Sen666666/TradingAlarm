"""Conditional PVR-decile observations. No model, ranking score or account."""
from pathlib import Path
import argparse,hashlib,json,time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'pvr_residual_ranking_v1/run_v1_exact_ties/ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet'
KEY=['window','day','sid']
FEATURES={'RS20':'relative_return20','frontier':'close_gap_prior_high20','low_improvement':'low_improvement'}
SECTOR=['window','day','sector']
SCOPES={'sector':SECTOR,'market':['window','day'],'market_sector_potential':['window','day','market_decile','sector']}
METRICS=['ret20_open','mfe20_open','mae20_open','ret20_close','mfe20_close','mae20_close']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with p.open('x')as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def periods(day):return np.select([day.lt('2024-01-01'),day.lt('2025-01-01')],['2022_23','2024'],default='2025H2_2026H1')

def cell_columns(scope):
    return SECTOR+['sector_decile'] if scope=='sector'else ['window','day','market_decile']+(['sector']if scope=='market_sector_potential'else[])

def member_coverage(a,scope):
    cells=cell_columns(scope);outs=[]
    for tag,col in FEATURES.items():
        median=a.groupby(cells)[col].transform('median')
        arm=np.sign(a[col]-median)
        a[tag+'_arm']=arm
        t=a.assign(_high=arm.eq(1),_low=arm.eq(-1),_neutral=arm.eq(0),_known=np.isfinite(a[col]))
        s=t.groupby(cells,sort=False).agg(n_all=('sid','size'),n_high=('_high','sum'),n_low=('_low','sum'),n_neutral=('_neutral','sum'),n_known=('_known','sum')).reset_index()
        s['paired_source']=s.n_high.gt(0)&s.n_low.gt(0);s['feature']=tag;s['period']=periods(s.day)
        outs.append(s)
    return a,pd.concat(outs,ignore_index=True)

def prepare():
    out=ROOT/'prepared';out.mkdir(exist_ok=False);start=time.monotonic()
    columns=KEY+['sector','score','relative_return20','close_gap_prior_high20','low_improvement','return20_anchor_day','original_PVR_slot']
    x=pd.read_parquet(OLD,columns=columns);assert len(x)==133713 and not x.duplicated(KEY).any()
    x['period']=periods(x.day);known=np.isfinite(x.score)
    cohorts={};cover=[]
    for scope,grp in [('sector',SECTOR),('market',['window','day'])]:
        a=x.loc[known].copy();a['N']=a.groupby(grp).sid.transform('size');a=a[a.N.ge(10)].copy()
        rank=a.groupby(grp).original_PVR_slot.rank(method='first').astype(int)
        a[scope+'_decile']=1+(10*(rank-1)//a.N).astype(int)
        a['PVR_percentile']=1-(rank-1)/(a.N-1)
        a,c=member_coverage(a,scope);cohorts[scope]=a;cover.append(c.assign(scope=scope))
        a.to_parquet(out/(scope+'_MEMBERSHIP_PRE_LABEL.parquet'),index=False)
    a=cohorts['market'].copy();a,c=member_coverage(a,'market_sector_potential');cover.append(c.assign(scope='market_sector_potential'))
    a.to_parquet(out/'market_sector_potential_MEMBERSHIP_PRE_LABEL.parquet',index=False)
    coverage=pd.concat(cover,ignore_index=True)
    coverage.to_parquet(out/'SOURCE_CELL_COVERAGE.parquet',index=False)
    summary=[]
    for keys,g in coverage.groupby(['scope','period','feature'],sort=True):
        ok=g[g.paired_source]
        summary.append(dict(zip(['scope','period','feature'],keys))|dict(cells=len(g),source_paired_cells=len(ok),source_arm_rows=int((ok.n_high+ok.n_low).sum()),source_paired_cell_members=int(ok.n_all.sum()),source_paired_dates=ok.day.nunique(),source_paired_sector_dates=ok[SECTOR].drop_duplicates().shape[0]if keys[0]!='market' else None))
    pd.DataFrame(summary).to_csv(out/'SOURCE_PAIR_COVERAGE.csv',index=False)
    y=x.groupby('period').agg(mother=('sid','size'),dates=('day','nunique'),stocks=('sid','nunique')).reset_index()
    y.to_csv(out/'MOTHER_COVERAGE.csv',index=False)
    save(out/'COMPLETION_PRE_FUTURE_LABELS.json',dict(status='MEMBERSHIP_FROZEN_BEFORE_LOADING_FUTURE_LABELS',
        sources={str(p.resolve()):sha(p)for p in[OLD,ROOT/'FREEZE.json',Path(__file__)]},
        outputs={p.name:sha(p)for p in out.iterdir()if p.is_file()},rows=len(x),new_accounts=0,elapsed_seconds=time.monotonic()-start))
    print(pd.DataFrame(summary).to_string(index=False))

def calendar_blocks():
    p=ROOT.parent/'pvr_information_v1/export/FEATURE_MANIFEST_PRE_LABEL.json'
    cal=json.loads(p.read_text())['calendars'];rows=[]
    for window,days in cal.items():
        for n,day in enumerate(days):rows.append(dict(window=window,day=day,block20=n//20))
    return pd.DataFrame(rows)

def analyze(labels):
    out=ROOT/'results';out.mkdir(exist_ok=False);start=time.monotonic();prep=ROOT/'prepared'
    lock=json.loads((prep/'COMPLETION_PRE_FUTURE_LABELS.json').read_text())
    for name,h in lock['outputs'].items():assert sha(prep/name)==h
    y=pd.read_parquet(labels);assert len(y)==133713 and not y.duplicated(KEY).any()
    assert set(KEY+['path20_complete','path20_status']+METRICS)<=set(y.columns)
    assert y.path20_complete.notna().all()
    y=y[KEY+['path20_complete','path20_status']+METRICS]
    assert np.isfinite(y.loc[y.path20_complete,METRICS]).all().all()
    source_coverage=pd.read_parquet(prep/'SOURCE_CELL_COVERAGE.parquet')
    funnel=[];sector_deltas=[];global_mixture=[]
    for scope in SCOPES:
        a=pd.read_parquet(prep/(scope+'_MEMBERSHIP_PRE_LABEL.parquet')).merge(y,on=KEY,how='left',validate='one_to_one')
        assert a.path20_complete.notna().all();cells=cell_columns(scope)
        cell_complete=a.groupby(cells).path20_complete.all().rename('entire_cell_future_complete').reset_index()
        for tag,col in FEATURES.items():
            c=source_coverage[(source_coverage.scope==scope)&(source_coverage.feature==tag)].copy()
            c=c.merge(cell_complete,on=cells,validate='one_to_one');c['evaluable']=c.paired_source&c.entire_cell_future_complete
            c['scope']=scope;funnel.append(c)
            if scope!='sector':continue
            # All members remain; arms were frozen before loading labels.
            validkeys=c.loc[c.evaluable,cells]
            z=a.merge(validkeys,on=cells,how='inner',validate='many_to_one')
            arm=tag+'_arm';cols=METRICS+['score','PVR_percentile',col]
            high=z[z[arm].eq(1)].groupby(cells)[cols].mean()
            low=z[z[arm].eq(-1)].groupby(cells)[cols].mean()
            d=high-low;assert d.notna().all().all()
            d=d.add_prefix('delta_').reset_index();d['feature']=tag;d['period']=periods(d.day)
            d=d.merge(c[cells+['n_all','n_high','n_low']],on=cells,validate='one_to_one')
            sector_deltas.append(d)
        if scope=='market':
            g=a.groupby(cells).agg(n=('sid','size'),sectors=('sector','nunique')).reset_index()
            g['period']=periods(g.day);global_mixture.append(g)
    all_funnel=pd.concat(funnel,ignore_index=True);all_funnel.to_parquet(out/'COMPLETE_CELL_COVERAGE.parquet',index=False)
    rows=[]
    for keys,g in all_funnel.groupby(['scope','period','feature']):
        s=g[g.paired_source];v=g[g.evaluable]
        rows.append(dict(zip(['scope','period','feature'],keys))|dict(source_cells=len(g),source_paired_cells=len(s),eval_cells=len(v),source_arm_rows=int((s.n_high+s.n_low).sum()),eval_arm_rows=int((v.n_high+v.n_low).sum()),eval_cell_members=int(v.n_all.sum()),eval_dates=v.day.nunique(),eval_sector_dates=v[SECTOR].drop_duplicates().shape[0]if keys[0]!='market' else None,unpaired_source_cells=int((~g.paired_source).sum()),incomplete_future_paired_cells=int((g.paired_source&~g.entire_cell_future_complete).sum())))
    pd.DataFrame(rows).to_csv(out/'COVERAGE_FUNNEL.csv',index=False)
    d=pd.concat(sector_deltas,ignore_index=True);d.to_parquet(out/'EVALUABLE_CELL_DELTAS.parquet',index=False)
    metrics=['delta_'+m for m in METRICS]+['delta_score','delta_PVR_percentile']
    sd=d.groupby(['period','window','day','sector','feature'])[metrics].mean().reset_index()
    sd.to_parquet(out/'SECTOR_DATE_EQUAL_CELL_DELTAS.parquet',index=False)
    daily=sd.groupby(['period','window','day','feature'])[metrics].mean().reset_index()
    daily.to_csv(out/'DAY_EQUAL_SECTOR_DELTAS.csv',index=False)
    summary=[]
    for keys,g in daily.groupby(['period','feature']):
        sub=sd[(sd.period==keys[0])&(sd.feature==keys[1])]
        for m in metrics:
            summary.append(dict(period=keys[0],feature=keys[1],metric=m,dates=len(g),sector_dates=len(sub),industries=sub.sector.nunique(),day_equal_mean_delta=float(g[m].mean()),day_equal_median_delta=float(g[m].median()),positive_date_fraction=float(g[m].gt(0).mean()),sector_date_mean_delta=float(sub[m].mean()),sector_date_median_delta=float(sub[m].median())))
    pd.DataFrame(summary).to_csv(out/'PERIOD_CONDITIONAL_SUMMARY.csv',index=False)
    b=daily.merge(calendar_blocks(),on=['window','day'],validate='many_to_one')
    block=b.groupby(['period','window','block20','feature'])[metrics].mean().reset_index()
    block.to_csv(out/'FIXED20_SESSION_BLOCK_DELTAS.csv',index=False)
    bs=[]
    for keys,g in block.groupby(['period','feature']):
        for m in metrics:
            bs.append(dict(period=keys[0],feature=keys[1],metric=m,blocks=len(g),positive_blocks=int(g[m].gt(0).sum()),negative_blocks=int(g[m].lt(0).sum()),min_block_delta=float(g[m].min()),median_block_delta=float(g[m].median()),max_block_delta=float(g[m].max())))
    pd.DataFrame(bs).to_csv(out/'FIXED20_SESSION_BLOCK_SUMMARY.csv',index=False)
    # Preserve per-decile behavior, with the same sector-then-day equality.
    dec_daily=d.groupby(['period','window','day','sector_decile','feature'])[metrics].mean().reset_index()
    dec=dec_daily.groupby(['period','sector_decile','feature'])[metrics].mean().reset_index()
    dec.to_csv(out/'PER_DECILE_DAY_EQUAL_SUMMARY.csv',index=False)
    mix=pd.concat(global_mixture);mix.to_csv(out/'MARKET_DECILE_SECTOR_MIX.csv',index=False)
    save(out/'COMPLETION.json',dict(status='COMPLETE_FIXED_CONDITIONAL_DESCRIPTIVE_OBSERVATION',
      sources={str(p.resolve()):sha(p)for p in[ROOT/'FREEZE.json',Path(__file__),prep/'COMPLETION_PRE_FUTURE_LABELS.json',Path(labels)]},
      outputs={p.name:sha(p)for p in out.iterdir()if p.is_file()},
      no_IID_inference=True,future_missing_never_changes_membership=True,new_residual_models=0,new_scores=0,new_accounts=0,elapsed_seconds=time.monotonic()-start))
    print(pd.DataFrame(rows).query('scope=="sector"').to_string(index=False))
    print(pd.DataFrame(summary).query('metric in ["delta_ret20_open","delta_mfe20_open","delta_mae20_open","delta_score"]')[['period','feature','metric','dates','sector_dates','day_equal_mean_delta']].to_string(index=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--labels',type=Path);a=p.parse_args()
    if a.prepare:prepare()
    elif a.labels:analyze(a.labels)
    else:raise SystemExit('Choose --prepare before --labels; neither runs accounts.')
