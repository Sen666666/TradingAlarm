from pathlib import Path
import json,sys,hashlib,datetime
import numpy as np,pandas as pd
from fit_models import model,evaluate
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'research_rounds/pv-participation-response-20261020/code'))
sys.path.insert(0,str(ROOT/'research_rounds/temperature-prototype-20261023'))
from numeric import event_frame_numeric
from participation import participation_frame
from temperature import temperature_frame
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v) for v in x]
    if isinstance(x,np.integer):return int(x)
    if isinstance(x,np.bool_):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x) if np.isfinite(x) else None
    if isinstance(x,(datetime.date,pd.Timestamp)):return str(x)
    return x
def dump(p,x):p.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def project(target,floor=None):
    out=pd.DataFrame({'target':target.astype(int)})
    out['entered']=(target.astype(bool)&~target.shift(fill_value=0).astype(bool)).astype(int)
    out['exited']=(~target.astype(bool)&target.shift(fill_value=0).astype(bool)).astype(int)
    out['floor']=floor if floor is not None else np.nan
    return out
def controls(d):
    e=event_frame_numeric(d.close,d.volume);b,_=participation_frame(d,e,mode='volume')
    ep=event_frame_numeric(d.close,d.volume,joint=False);bp,_=participation_frame(d,ep,mode='none')
    t,_=temperature_frame(d)
    return {'original':b,'price_ablation':bp,'temperature_structure':project(t.structure,t.floor),
      'temperature_entry4':t[['target','entered','exited','floor']], 'temperature_daily4':project(t.level.ge(4)),},t,e
def episodes(s,name,bars):
    rows=[];active=None
    for dt,r in s.iterrows():
        if r.entered:
            assert active is None
            active=dict(model=name,start=str(dt.date()),start_close=float(bars.loc[dt,'close']),initial_floor=float(r.floor) if pd.notna(r.floor) else None)
        if r.exited:
            assert active is not None
            rows.append(dict(active,end=str(dt.date()),end_close=float(bars.loc[dt,'close']),closed=True));active=None
    if active:rows.append(dict(active,end=None,end_close=None,closed=False))
    return rows
def main():
    protocol=json.loads((HERE/'fit-protocol.json').read_text())
    for p,h in protocol['inputs_and_imitation_code'].items():assert sha(HERE/p)==h
    for p,h in protocol['original_code'].items():assert sha(ROOT/p)==h
    out=HERE/'results/v0';out.mkdir(parents=True,exist_ok=False);(out/'daily').mkdir()
    dump(out/'run-freeze.json',dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=sha(HERE/'fit-protocol.json'),run_code_sha256=sha(__file__),accounts=0,original_changes=0))
    d=pd.read_csv(HERE/'data/sina-AU0.csv',index_col='date',parse_dates=True)
    sge=pd.read_csv(HERE/'data/sge-Au9999.csv',index_col='date',parse_dates=True)
    assert not d.isna().any().any() and (d[['open','high','low','close','volume']]>0).all().all()
    target=json.loads((HERE/'targets.json').read_text());end=target['alignment']['inferred_last_date']
    idx=d.loc['2025-01-01':end].index
    states,t,event=controls(d);candidates=[]
    for cfg in protocol['configurations']:
        states[cfg['id']]=model(d,cfg);candidates.append(cfg['id'])
    scores=[];matches=[];all_ep=[]
    for name,state in states.items():
        z=state.reindex(idx);summary,mt=evaluate(z,target['points'],idx)
        scores.append(dict(model=name,type='fit' if name in candidates else 'control',**summary))
        for row in mt:
            row=dict(model=name,**row)
            if 'predicted_index' in row:row['predicted_date']=str(idx[row['predicted_index']].date())
            if 'target_index' in row:row['target_date']=str(idx[row['target_index']].date())
            matches.append(row)
        all_ep+=episodes(state,name,d)
        state.join(d,rsuffix='_bar').to_parquet(out/'daily'/(name+'.parquet'))
    ranking=pd.DataFrame(scores).sort_values(['score','model']);ranking.to_csv(out/'ranking.csv',index=False)
    pd.DataFrame(matches).to_csv(out/'event-matches.csv',index=False)
    pd.DataFrame(all_ep).to_csv(out/'episodes.csv',index=False)
    best=ranking.loc[ranking.type.eq('fit'),'model'].iloc[0]
    family=[]
    for name in ['EMA','Channel','ATR','VolumeATR']:
        names=[c['id'] for c in protocol['configurations'] if c['family']==name]
        row=ranking.loc[ranking.model.isin(names)].iloc[0].to_dict();row['family']=name;family.append(row)
    # Complete state/evidence tables permit inspection of every bar, not just winners.
    daily=d.join(t.add_prefix('temperature_')).join(states['original'].add_prefix('original_')).join(event.add_prefix('event_'))
    daily.to_csv(out/'evidence.csv',float_format='%.17g');daily.to_parquet(out/'evidence.parquet')
    display=d.loc[idx];spot=sge.reindex(idx)
    pair=pd.DataFrame({'AU0':display.close,'SGE':spot.close});returns=np.log(pair).diff().dropna()
    diff=pair.AU0/pair.SGE-1
    quality=dict(primary_rows=len(d),primary_first=str(d.index[0].date()),primary_last=str(d.index[-1].date()),display_download_rows=len(d.loc['2025':]),
       evaluation_rows=len(idx),evaluation_first=str(idx[0].date()),evaluation_last=str(idx[-1].date()),price_crosscheck_return_correlation=returns.corr().iloc[0,1],
       price_basis_percentiles=diff.quantile([0,.05,.5,.95,1]).to_dict(),sge_only_dates=[str(x.date()) for x in sge.index.difference(d.index)],
       primary_only_dates=[str(x.date()) for x in d.index.difference(sge.index)],negative_or_zero_volume=int(d.volume.le(0).sum()),missing_ohlcv=int(d[['open','high','low','close','volume']].isna().sum().sum()),
       duplicate_dates=int(d.index.duplicated().sum()),calendar_limit='Observed provider dates, not independently certified exchange-complete calendar. 2025 onward two sources share same436 dates.',
       screenshot_exact_date_price_check={dt:dict(AU0=float(d.loc[dt,'close']),SGE=float(sge.loc[dt,'close'])) for dt in ['2025-09-01','2025-10-22']})
    dump(out/'quality.json',quality)
    sensitivity=[]
    for uncertainty in [1,3,5]:
      for cut_shift in [-3,0,3]:
        stop=d.index.get_loc(end)+cut_shift;ix=d.loc['2025-01-01':d.index[stop]].index
        for name in ['original','temperature_entry4','temperature_daily4',best]+[r['model'] for r in family]:
            row,_=evaluate(states[name].reindex(ix),target['points'],ix,uncertainty=uncertainty)
            sensitivity.append(dict(model=name,unprinted_uncertainty=uncertainty,cutoff=str(ix[-1].date()),**row))
    pd.DataFrame(sensitivity).to_csv(out/'sensitivity.csv',index=False)
    # Runtime prefix check of frozen original + temperature and the best of each
    # finite imitation family, with no parameter re-estimation on prefixes.
    checks=[]
    configs={c['id']:c for c in protocol['configurations']}
    cuts=sorted(set([d.index.get_loc(pd.Timestamp(dt)) for dt in ['2025-03-13','2025-04-22','2025-09-01','2025-10-22','2025-12-23','2026-02-02','2026-08-28','2026-10-23']]))
    for cut in cuts:
        z=d.iloc[:cut+1];cc,tt,ee=controls(z)
        for name,ss in cc.items():
            for col in ['target','entered','exited','floor']:np.testing.assert_array_equal(ss[col].to_numpy(),states[name][col].iloc[:cut+1].to_numpy())
            checks.append(dict(model=name,cutoff=str(z.index[-1].date()),rows=len(z),passed=True))
        pd.testing.assert_frame_equal(tt,t.iloc[:cut+1],check_freq=False)
        for row in family:
            name=row['model'];ss=model(z,configs[name]);pd.testing.assert_frame_equal(ss,states[name].iloc[:cut+1],check_freq=False)
            checks.append(dict(model=name,cutoff=str(z.index[-1].date()),rows=len(z),passed=True))
    dump(out/'verification.json',dict(prefix_checks=checks,count=len(checks),temperature_all_fields_prefixes=len(cuts),old_code_hashes_unchanged=all(sha(ROOT/p)==h for p,h in protocol['original_code'].items()),
      caveat='Prefix checks certify fixed-parameter runtime consistency. All fit parameters chosen retrospectively from screenshot; no out-of-sample result.'))
    # Existing ETF proxy is retained without downloading or rewriting it.
    proxy=pd.read_parquet(ROOT/'research_rounds/temperature-prototype-20261023/results/v0/daily/USHJ518880.parquet')
    zz=proxy.loc[idx[0]:idx[-1]]
    proxy_summary=dict(source='Existing frozen 518880 ETF proxy, different instrument and preparation/warmup; not scored as AU0 algorithm evidence',rows=len(zz),last=str(zz.index[-1].date()),original_starts=int(zz.baseline_entered.sum()),original_ends=int(zz.baseline_exited.sum()),temperature_starts=int(zz.entered.sum()),temperature_ends=int(zz.exited.sum()))
    dump(out/'proxy-reference.json',proxy_summary)
    complete=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),fit_configurations=36,evaluation_last=end,ranking=ranking.to_dict('records'),best=best,family_best=family,quality=quality,proxy_reference=proxy_summary,
       prefix_checks=len(checks),accounts=0,old_code_changes=0,post_fit_rule_revisions=0,unknowns=['Proprietary formula, exact input contract splice/index pricing, signal timestamp versus fill timestamp, and percentage annotation semantics remain unknown.','Chart contains no individual color transition labels; this study cannot validate its four temperature classes.'],
       failure_preserved='First image ridge tracer followed gold text and failed price-axis sign sanity check; corrected before model freeze. attempt-01-ridge-trace-failure retained. No signal model was fit on that failed measurement.')
    dump(out/'complete.json',complete)
    print(ranking.head(14).to_string(index=False));print('family',family);print('verified',len(checks))
if __name__=='__main__':main()
