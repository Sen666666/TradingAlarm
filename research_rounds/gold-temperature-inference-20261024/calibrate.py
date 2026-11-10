"""Conditional interpretation of four hot subclasses; NOT an autonomous strategy.

Observed source starts are supplied to anchor-based explanations. Their results
cannot be presented as predicting those starts, avoiding August, or trading P&L.
"""
from pathlib import Path
import json,hashlib,datetime
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent;PRIOR=HERE.parent/'gold-chart-fit-20261024'
FEATURES={
 'age':'Number of observed bars since supplied screenshot start',
 'advance':'Log close/close at supplied screenshot start',
 'peak_advance':'Running maximum log close/close at supplied screenshot start',
 'normalized_advance':'Advance divided by previous63-return RMS at supplied start',
 'normalized_peak':'Peak advance divided by previous63-return RMS at supplied start',
 'z20':'20-observation log net advance / previous63-return RMS / sqrt20',
 'ema_gap':'(EMA10-EMA40) / previous14 mean true range',
 'multi_scale':'minimum of z20 and z63'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def fit_thresholds(x,y):
    """Exact ordered partition DP, inverse class count weighted absolute error.

    Equal scores share a bin. Empty classes cannot be identified from a fold;
    only labels actually present in its training set can be predicted.
    """
    classes=np.sort(np.unique(y));u=np.unique(x);n=len(u);k=len(classes)
    costs=np.zeros((k,n));weights={c:1/np.sum(y==c)/k for c in classes}
    for j,v in enumerate(u):
        yy=y[x==v]
        for a,c in enumerate(classes):costs[a,j]=sum(abs(c-z)*weights[z] for z in yy)
    cum=np.c_[np.zeros(k),np.cumsum(costs,axis=1)]
    dp=np.full((k+1,n+1),np.inf);dp[0,0]=0;back={}
    for a in range(1,k+1):
      for end in range(a,n+1):
        options=[(dp[a-1,start]+cum[a-1,end]-cum[a-1,start],start) for start in range(a-1,end)]
        dp[a,end],back[a,end]=min(options,key=lambda t:t[0])
    boundaries=[];end=n
    for a in range(k,0,-1):
        start=back[a,end]
        if a>1:boundaries.append((u[start-1]+u[start])/2)
        end=start
    return dict(classes=classes.tolist(),thresholds=boundaries[::-1],training_loss=float(dp[k,n]))
def predict(x,fit):return np.array(fit['classes'])[np.searchsorted(fit['thresholds'],x,side='right')]
def metrics(y,p):
    classes=np.unique(y);return dict(rows=len(y),accuracy=float(np.mean(y==p)),mae=float(np.mean(np.abs(y-p))),balanced_mae=float(np.mean([np.mean(np.abs(y[y==c]-p[y==c])) for c in classes])))
def make_features(d,points):
    c=d.close;r=np.log(c/c.shift());sigma=r.pow(2).shift().rolling(63).mean().pow(.5);q=d.volume/d.volume.shift().rolling(21).median()
    tr=pd.concat([d.high-d.low,(d.high-c.shift()).abs(),(d.low-c.shift()).abs()],axis=1).max(axis=1)
    f=pd.DataFrame(index=d.index)
    f['sigma']=sigma;f['q']=q
    for h in [5,20,63]:f['z'+str(h)]=np.log(c/c.shift(h))/(sigma*np.sqrt(h))
    f['ma20']=c.rolling(20).mean();f['ma63']=c.rolling(63).mean();f['ma63_slope20']=np.log(f.ma63/f.ma63.shift(20))/(sigma*np.sqrt(20))
    f['return63']=c/c.shift(63)-1;f['ema_gap']=(c.ewm(span=10,adjust=False).mean()-c.ewm(span=40,adjust=False).mean())/tr.shift().rolling(14).mean()
    f['multi_scale']=f[['z20','z63']].min(axis=1)
    for k in ['age','advance','peak_advance','normalized_advance','normalized_peak','pair']:f[k]=np.nan
    for i,(s,t) in enumerate(zip(points[::2],points[1::2]),1):
        if pd.Timestamp(s['date']) not in c.index:continue
        z=c.loc[(c.index>=pd.Timestamp(s['date']))&(c.index<pd.Timestamp(t['date']))]
        advance=np.log(z/c.loc[s['date']]);f.loc[z.index,'pair']=i;f.loc[z.index,'age']=np.arange(len(z));f.loc[z.index,'advance']=advance;f.loc[z.index,'peak_advance']=advance.cummax();f.loc[z.index,'normalized_advance']=advance/sigma.loc[s['date']];f.loc[z.index,'normalized_peak']=advance.cummax()/sigma.loc[s['date']]
    pending=None;guards=[]
    for i,(dt,bar) in enumerate(d.iterrows()):
        if pending is not None and bar.close>pending:pending=None
        adverse=i>0 and q.loc[dt]>=2 and bar.close<c.iloc[i-1] and bar.close<f.loc[dt,'ma20']
        if adverse:pending=max(pending if pending is not None else -np.inf,c.iloc[i-1])
        guards.append((int(adverse),int(pending is not None),pending))
    f[['q2_adverse','unreclaimed_adverse','reclaim_price']]=guards
    return f
def main():
    protocol=HERE/'calibration-protocol.json'
    if not protocol.exists():
        dump(protocol,dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),code_sha256=sha(Path(__file__)),input_hashes={s:sha(HERE/s) for s in ['measured-daily.csv','measurement.json','refined-targets.json']},
          purpose='Eight explanatory scalar hypotheses for colors CONDITIONED on observed rightside segments; no independent start/exit model, no strategy/account. Price controls do not replace project quantity-price mainline.',features=FEATURES,
          fit='Optimal nondecreasing four-color thresholds with inverse-class-count absolute ordinal error. Only confident active colors; off-region0 is not a measured cold state.',
          checks='Leave one whole observed rightside episode out; report absent training classes. Inspect all428 dates for visible long-horizon context and volume-shock contradictions without adding rules.',
          stopping='Exactly8 explanations, one full calibration plus5 omitted-episode calibrations each. No added models/threshold grid after results. No P&L, no original-code modification.',
          limitations='All images already viewed, folds are within-image sensitivity not genuine unseen/out-of-sample validation; source anchors and approximate proxy prices limit identification.'))
    fr=json.loads(protocol.read_text());assert sha(Path(__file__))==fr['code_sha256']
    for s,h in fr['input_hashes'].items():assert sha(HERE/s)==h
    out=HERE/'results/v0';out.mkdir(parents=True,exist_ok=False)
    d=pd.read_csv(PRIOR/'data/sina-AU0.csv',index_col='date',parse_dates=True);points=json.loads((HERE/'refined-targets.json').read_text())['points'];labels=pd.read_csv(HERE/'measured-daily.csv',index_col='date',parse_dates=True)
    f=make_features(d,points);z=labels.join(f);training=z.loc[z.known.eq(1)&z.level.gt(0)&z.pair.notna()];records=[];predictions=[];thresholds=[]
    for name in FEATURES:
        train=training.dropna(subset=[name]);x=train[name].to_numpy();y=train.level.astype(int).to_numpy();fit=fit_thresholds(x,y);p=predict(x,fit)
        thresholds.append(dict(feature=name,description=FEATURES[name],**fit));records.append(dict(feature=name,split='all_visible_colors',held_out_pair=None,**metrics(y,p)))
        for dt,yy,pp in zip(train.index,y,p):predictions.append(dict(feature=name,split='all_visible_colors',date=str(dt.date()),true=int(yy),predicted=int(pp)))
        for pair in range(1,6):
            a=train.loc[train.pair.ne(pair)];b=train.loc[train.pair.eq(pair)]
            if not len(b):continue
            fit=fit_thresholds(a[name].to_numpy(),a.level.astype(int).to_numpy());pred=predict(b[name].to_numpy(),fit)
            records.append(dict(feature=name,split='omit_one_episode',held_out_pair=pair,missing_training_classes=','.join(str(i) for i in range(1,5) if i not in fit['classes']),**metrics(b.level.astype(int).to_numpy(),pred)))
            for dt,yy,pp in zip(b.index,b.level,pred):predictions.append(dict(feature=name,split='omit_one_episode',date=str(dt.date()),true=int(yy),predicted=int(pp)))
    scores=pd.DataFrame(records);scores.to_csv(out/'conditional-scores.csv',index=False);pd.DataFrame(predictions).to_csv(out/'conditional-predictions.csv',index=False);dump(out/'thresholds.json',thresholds)
    aggregates=[]
    for name in FEATURES:
        pp=pd.DataFrame(predictions);pp=pp.loc[pp.feature.eq(name)&pp.split.eq('omit_one_episode')]
        aggregates.append(dict(feature=name,**metrics(pp.true.to_numpy(),pp.predicted.to_numpy())))
    pd.DataFrame(aggregates).sort_values('balanced_mae').to_csv(out/'omitted-episode-summary.csv',index=False)
    # Compare information available at the five source starts and at August10.
    date_rows=[]
    for dt,label in [(p['date'],'source_start_'+str((p['id']+1)//2)) for p in points if p['kind']=='start']+[('2026-08-10','countertrend_example')]:
        r=f.loc[dt];date_rows.append(dict(date=dt,case=label,close=float(d.loc[dt,'close']),volume=int(d.loc[dt,'volume']),**{c:float(r[c]) for c in ['q','sigma','z5','z20','z63','ma63','ma63_slope20','return63','ema_gap']}))
    pd.DataFrame(date_rows).to_csv(out/'start-context.csv',index=False)
    # A hard volume-danger story can be contradicted on confidently colored
    # days away from noisy entry/exit boundaries. This does not prove volume is absent.
    contradict=z.loc[z.known.eq(1)&z.level.gt(0)&z.unreclaimed_adverse.eq(1)]
    contradict.to_csv(out/'volume-veto-contradictions.csv')
    f.join(d,rsuffix='_bar').to_csv(out/'all-features.csv',float_format='%.17g');f.join(d,rsuffix='_bar').to_parquet(out/'all-features.parquet')
    # Prefix check only price/volume history, retaining the same supplied source
    # anchors; conditional tests do not certify source signal causal generation.
    checks=[]
    for date in ['2025-04-16','2025-09-01','2025-10-22','2026-01-21','2026-08-10','2026-10-23']:
        ff=make_features(d.loc[:date],points);pd.testing.assert_frame_equal(ff,f.loc[:date],check_freq=False);checks.append(dict(cutoff=date,rows=len(ff),passed=True))
    # Sensitivity of scalar ordering to one-observation entry-center shifts.
    sensitivity=[]
    for shift in [-1,1]:
        pp=[dict(p) for p in points]
        for p in pp:
            if p['kind']=='start' and p['uncertainty_observations']:
                p['date']=str(d.index[d.index.get_loc(p['date'])+shift].date())
        f2=make_features(d,pp);tt=labels.join(f2);tt=tt.loc[tt.known.eq(1)&tt.level.gt(0)&tt.pair.notna()]
        for name in FEATURES:
            t=tt.dropna(subset=[name]);fit=fit_thresholds(t[name].to_numpy(),t.level.astype(int).to_numpy());sensitivity.append(dict(entry_shift=shift,feature=name,**metrics(t.level.astype(int).to_numpy(),predict(t[name].to_numpy(),fit))))
    pd.DataFrame(sensitivity).to_csv(out/'entry-center-sensitivity.csv',index=False)
    done=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),protocol_sha256=sha(protocol),conditional_color_observations=len(training),confident_grade_counts=training.level.value_counts().sort_index().to_dict(),features=FEATURES,all_calibration=scores.loc[scores.split.eq('all_visible_colors')].to_dict('records'),omitted_episode=aggregates,start_context=date_rows,volume_veto_conflicts=len(contradict),prefix_checks=checks,accounts=0,original_code_changes=0,post_run_hypothesis_changes=0,
      caveat='Scores only explain internal colors after observed source starts have been supplied. Cannot claim predicted starts/ends, avoided August or replicated opponent algorithm. Grades/thresholds are measured/fit, not original formulas. Folds are within-image development sensitivity.')
    dump(out/'complete.json',done)
    print(scores.loc[scores.split.eq('all_visible_colors')].to_string(index=False));print('omit-episode',pd.DataFrame(aggregates).sort_values('balanced_mae').to_string(index=False));print('context',pd.DataFrame(date_rows).to_string(index=False));print('volume veto conflicts',len(contradict))
if __name__=='__main__':main()
