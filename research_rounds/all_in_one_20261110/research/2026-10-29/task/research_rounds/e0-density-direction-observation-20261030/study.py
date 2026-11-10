"""Cached E0 openings and market-session windows. No indicator/trading engine imports."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import sys,json,csv,time,hashlib,math
import numpy as np,pandas as pd
T=time.monotonic();O=Path(__file__).resolve().parent;R=Path('/Users/bytedance/Documents/ChatGPT/money');RR=R/'research_rounds';PH=RR/'ph1-cross-sector-20261028';END='2026-10-27';START='2023-12-29';stage=sys.argv[1];assert stage in ['sample','full'];dest=O/stage;dest.mkdir(exist_ok=False)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def export(p,x):pd.DataFrame(x).to_csv(p,index=False)
pool=list(csv.DictReader((RR/'tech-compound-design-20261026/proposed-pool.csv').open()));assert len(pool)==407;meta={x['symbol']:x for x in pool};sample_ids=['300308.SZ','300502.SZ'];assert [meta[s]['name'] for s in sample_ids]==['中际旭创','新易盛']
calendar_file=Path('/Users/bytedance/Library/Python/3.13/lib/python/site-packages/akshare/file_fold/calendar.json');dates=[datetime.strptime(x,'%Y%m%d').date().isoformat() for x in read(calendar_file)];official=read(R/'TradingAlarm/desk/calendar.json');assert {d for d in dates if d[:4]=='2026'}==set(official['sessions'])
oldrules=read(RR/'pvr-act-comparison-20261027/execution-rules-v2.json');oldcal={d[:10] for d in oldrules['calendars']['A']}|{d[:10] for d in oldrules['decision_cutoffs']};assert oldcal=={d for d in dates if '2015-01-05'<=d<=END};dates=[d for d in dates if d<=END];calendar=pd.DatetimeIndex(dates);N=len(dates);snap=Path(read(RR/'pvr-act-comparison-20261027/input.json')['snapshot']['path']);proof=read(PH/'event-validation.json');assert proof['passed'];records={x['symbol']:x for x in proof['records'] if x['sector']=='TECH'}
Qpath=RR/'s-entry-mechanism-audit-20261029/market-cache.parquet';qf=pd.read_parquet(Qpath,columns=['date','symbol','Q','i_buy']);qm={(x.symbol,str(x.date.date())):(bool(x.Q),bool(x.i_buy)) for x in qf.itertuples(index=False)}
inputs=[O/'PROTOCOL.txt',Path(__file__),calendar_file,R/'TradingAlarm/desk/calendar.json',RR/'pvr-act-comparison-20261027/execution-rules-v2.json',RR/'tech-compound-design-20261026/proposed-pool.csv',RR/'pvr-act-comparison-20261027/input.json',PH/'event-validation.json',Qpath];identity={str(p):sha(p) for p in inputs};profiles={};features=[];class_counts=Counter();coverage=[];sources_off_calendar=0
if stage=='full':
 sample=read(O/'sample/VERIFICATION.json');assert sample['passed'] and sample['future_labels_computed']==0 and sample['code_hash']==sha(Path(__file__)) and sample['protocol_hash']==sha(O/'PROTOCOL.txt')
selected=sample_ids if stage=='sample' else [x['symbol'] for x in pool]
for j,s in enumerate(selected):
 fp=snap/'facts'/f'{s}.parquet';ep=PH/'events/TECH'/f'{s}.parquet';sp=snap/'signals'/f'{s}.parquet';rec=records[s]
 for p,h in [(fp,rec['inputs'][str(fp)]),(ep,rec['output_sha256']),(sp,rec['inputs'][str(sp)])]:assert sha(p)==h,(s,p);identity[str(p)]=h
 f=pd.read_parquet(fp).loc[:END];ev=pd.read_parquet(ep).loc[:END];raw=pd.read_parquet(sp,columns=['volume','observed_bar','source_invalid','synthetic_event_bar']).loc[:END];assert f.index.equals(ev.index);np.testing.assert_array_equal(f.close.to_numpy(float),ev.close.to_numpy(float));np.testing.assert_array_equal(f.segment_id,ev.segment_id)
 target=f.e0_target.fillna(0).to_numpy(bool);seg=f.segment_id.to_numpy();event=ev.event.to_numpy(int);same=np.r_[False,seg[1:]==seg[:-1]];previous=np.r_[False,target[:-1]];opens=target&~previous&same;unknown_initial=target&~same;cont=(event==1)&target&previous&same;ignored=(event==1)&~target&previous&same;unclassified=(event==1)&~(opens|cont|ignored)
 assert not unclassified.any(),(s,'unclassified positive event');assert ((event[opens])==1).all();class_counts.update(dict(open=int(opens.sum()),continue_positive=int(cont.sum()),ignored_exit_positive=int(ignored.sum()),initial_active_unknown=int(unknown_initial.sum())))
 gi=calendar.get_indexer(f.index);ok=gi>=0;sources_off_calendar+=int((~ok).sum());price=np.full(N,np.nan);state=np.full(N,np.nan);sg=np.full(N,np.nan);op=np.full(N,np.nan);co=np.full(N,np.nan);ig=np.full(N,np.nan);observed=np.zeros(N,bool)
 for a,v in [(price,f.close.to_numpy(float)),(state,target.astype(float)),(sg,seg.astype(float)),(op,opens.astype(float)),(co,cont.astype(float)),(ig,ignored.astype(float))]:a[gi[ok]]=v[ok]
 observed[gi[ok]]=True;rawknown=np.zeros(N,bool);nontrade=np.zeros(N,bool);rg=calendar.get_indexer(raw.index);rok=rg>=0;rv=raw.volume.to_numpy(float);bad=(np.isfinite(rv)&(rv<=0))|~raw.observed_bar.to_numpy(bool)|raw.source_invalid.to_numpy(bool)|raw.synthetic_event_bar.to_numpy(bool);rawknown[rg[rok]]=True;nontrade[rg[rok]]=bad[rok]
 profiles[s]=dict(price=price,source=sg,observed=observed,rawknown=rawknown,nontrade=nontrade,open=op,continue_positive=co,ignored_positive=ig,state=state)
 coverage.append(dict(symbol=s,name=meta[s]['name'],first=str(f.index[0].date()),last=str(f.index[-1].date()),valid_price_observations=len(f),openings=int(opens.sum()),off_market_dates=int((~ok).sum())))
 for fi in np.flatnonzero(opens):
  day=str(f.index[fi].date());ci=int(gi[fi]);q=qm.get((s,day));I=bool(f.iloc[fi].i_buy);assert q is None or q[1]==I
  row=dict(epoch_id=f'{s}|{seg[fi]}|{day}',symbol=s,name=meta[s]['name'],source_segment=str(seg[fi]),open_date=day,open_year=day[:4],calendar_index=ci,I_event=I,Q_known=q is not None,Q=q[0] if q else None,IQ_status='legal_IQ' if I and q and q[0] else 'unknown_Q_for_I' if I and q is None else 'not_I_or_Q',in_research_window=START<=day<=END,D_open=None,D_continue=None,active_days=None,ignored_exit_positive_prior21=None,T21=None,past_return21=None,past_vol21=None,past_missing_price_days=None,past_missing_state_days=None,past_source_mixed=None,past_nontradable_proxy_days=None,window_start=None,window_last_before_open=None,feature_status='unknown')
  reasons=[]
  if ci<0:reasons.append('opening_not_market_session')
  elif ci<21:reasons.append('market_calendar_left_history_insufficient')
  else:
   sl=slice(ci-21,ci);px=price[ci-21:ci+1];st=state[sl];sr=sg[ci-21:ci+1];mp=int(np.isnan(px).sum());ms=int(np.isnan(st).sum());mixed=bool(np.isfinite(sr).any() and np.any(sr[np.isfinite(sr)]!=float(seg[fi])));row.update(window_start=dates[ci-21],window_last_before_open=dates[ci-1],past_missing_price_days=mp,past_missing_state_days=ms,past_source_mixed=mixed,past_nontradable_proxy_days=int(nontrade[ci-21:ci+1].sum()))
   if dates[ci-21]<str(f.index[0].date()):reasons.append('source_or_IPO_left_history_insufficient')
   if mp:reasons.append('past_market_price_missing')
   if ms:reasons.append('past_market_state_missing')
   if mixed:reasons.append('source_boundary_in_window')
   if ms==0 and not mixed:row.update(D_open=int(np.sum(op[sl])),D_continue=int(np.sum(co[sl])),active_days=int(np.sum(st)),ignored_exit_positive_prior21=int(np.sum(ig[sl])))
   if mp==0 and not mixed:
    dif=np.diff(px);den=float(np.abs(dif).sum());row.update(past_return21=float(px[-1]/px[0]-1),past_vol21=float(np.std(np.diff(np.log(px)),ddof=0)))
    if den==0:reasons.append('T21_zero_price_path_denominator')
    else:row['T21']=float((px[-1]-px[0])/den);assert -1-1e-12<=row['T21']<=1+1e-12
  row['feature_status']='complete' if not reasons else '|'.join(reasons);row['natural_group']=('D0' if row['D_open']==0 else 'Dplus')+('_Tpositive' if row['T21']>0 else '_Tnonpositive') if row['feature_status']=='complete' else 'unknown_features';features.append(row)
 if stage=='full' and (j+1)%80==0:print(json.dumps(dict(stage='features',stocks=j+1,openings=len(features),seconds=time.monotonic()-T)),flush=True)
 if time.monotonic()-T>285:raise TimeoutError('300-second study budget')
export(dest/'features-before-labels.csv',features);export(dest/'source-coverage.csv',coverage);save(dest/'INPUT_IDENTITY.json',dict(at=datetime.now(timezone.utc).isoformat(),before_future_labels=True,calendar_source='existing packaged Sina market calendar, cross-checked official2026 and old2869 dates',sha256=identity))
if stage=='sample':
 known=[x for x in features if x['feature_status']=='complete'];choose=[]
 for s in sample_ids:
  z=[x for x in known if x['symbol']==s and x['in_research_window']];assert z;choose.append(min(z,key=lambda x:x['open_date']))
 for test in [lambda x:x['feature_status']=='complete' and x['D_open']>0,lambda x:x['feature_status']=='complete' and x['D_continue']>0,lambda x:x['feature_status']=='complete' and x['T21']<=0,lambda x:x['feature_status']!='complete',lambda x:(x['ignored_exit_positive_prior21'] or 0)>0]:
  z=[x for x in features if test(x)]
  if z:choose.append(min(z,key=lambda x:(x['open_date'],x['symbol'])))
 choose=list({x['epoch_id']:x for x in choose}.values());detail=[]
 for x in choose:
  if x['calendar_index']<21:continue
  p=profiles[x['symbol']];ci=x['calendar_index']
  for k in range(ci-21,ci+1):detail.append(dict(epoch_id=x['epoch_id'],day=dates[k],included_in_density=k<ci,close=p['price'][k],E0_active=p['state'][k],E0_open=p['open'][k],continue_positive=p['continue_positive'][k],ignored_positive=p['ignored_positive'][k],missing_price=not p['observed'][k]))
  if x['feature_status']=='complete':assert np.sum(p['open'][ci-21:ci])==x['D_open'] and p['open'][ci]==1 and len(dates[ci-21:ci])==21
 export(dest/'selected-samples.csv',choose);export(dest/'window-detail.csv',detail);save(dest/'VERIFICATION.json',dict(passed=True,symbols=2,selected_samples=len(choose),known_openings=len(features),positive_events_classified=dict(class_counts),future_labels_computed=0,code_hash=sha(Path(__file__)),protocol_hash=sha(O/'PROTOCOL.txt'),seconds=time.monotonic()-T));print(json.dumps(dict(stage='sample_passed',samples=choose,seconds=time.monotonic()-T)),flush=True)
else:
 freeze={str(dest/n):sha(dest/n) for n in ['features-before-labels.csv','source-coverage.csv','INPUT_IDENTITY.json']};freeze[str(O/'PROTOCOL.txt')]=sha(O/'PROTOCOL.txt');save(O/'FEATURE_FREEZE.json',dict(at=datetime.now(timezone.utc).isoformat(),before_future_labels=True,sha256=freeze));print(json.dumps(dict(stage='features_frozen',mother=len(features),seconds=time.monotonic()-T)),flush=True)
 labels=[]
 for x in features:
  p=profiles[x['symbol']];ci=x['calendar_index'];out=dict(epoch_id=x['epoch_id'])
  for h in [63,21]:
   prefix=f'H{h}_';d=dict(status='unknown',target_date=None,price_change=None,MFE=None,MAE=None,complete_path=False,missing_price_days=None,nontradable_proxy_days=None,endpoint_nontradable_proxy=None,endpoint_raw_source_known=None,source_boundary=False)
   if ci<0:d['status']='opening_not_market_session'
   elif ci+h>=N:d['status']='data_end_right_censored'
   else:
    end=ci+h;d['target_date']=dates[end];seq=p['price'][ci+1:end+1];missing=~np.isfinite(seq);ss=p['source'][ci:end+1];mixed=bool(np.any(ss[np.isfinite(ss)]!=float(x['source_segment'])));d.update(missing_price_days=int(missing.sum()),nontradable_proxy_days=int(p['nontrade'][ci+1:end+1].sum()),endpoint_nontradable_proxy=bool(p['nontrade'][end]),endpoint_raw_source_known=bool(p['rawknown'][end]),source_boundary=mixed)
    if mixed:d['status']='source_boundary_price_unknown'
    elif not np.isfinite(p['price'][end]):d['status']='endpoint_price_missing_nonobserved_proxy' if p['rawknown'][end] and p['nontrade'][end] else 'endpoint_price_missing_unknown_reason'
    else:
     C=p['price'][ci];d.update(status='endpoint_price_observed_path_incomplete' if missing.any() else 'complete_prices_nontradable_proxy_present' if d['nontradable_proxy_days'] else 'complete_prices',price_change=float(p['price'][end]/C-1),complete_path=not missing.any())
     if not missing.any():d.update(MFE=max(0.,float(np.max(seq)/C-1)),MAE=min(0.,float(np.min(seq)/C-1)))
   out.update({prefix+k:v for k,v in d.items()})
  labels.append(out)
 joined=[a|b for a,b in zip(features,labels)];export(dest/'forward-labels.csv',labels);export(O/'observation-ledger.csv',joined);assert len({x['epoch_id'] for x in features})==len(features);assert all(sha(p)==h for p,h in identity.items());assert all(sha(p)==h for p,h in freeze.items())
 summary=dict(passed=True,stocks=407,mother_openings=len(features),features_complete=sum(x['feature_status']=='complete' for x in features),feature_status=dict(Counter(x['feature_status'] for x in features)),positive_event_classes=dict(class_counts),IQ_status=dict(Counter(x['IQ_status'] for x in features)),natural_groups=dict(Counter(x['natural_group'] for x in features)),opening_research_window=sum(x['in_research_window'] for x in features),source_dates_off_calendar=sources_off_calendar,labels_63=dict(Counter(x['H63_status'] for x in labels)),labels_21=dict(Counter(x['H21_status'] for x in labels)),future_path_missing_not_zero=True,current_open_excluded_from_D=True,future_horizon_fixed_market_sessions=True,source_hashes_unchanged=True,feature_hashes_unchanged=True,indicators_recomputed=0,trade_paths=0,seconds=time.monotonic()-T);save(dest/'VERIFICATION.json',summary);print(json.dumps(dict(stage='full_done',summary=summary),ensure_ascii=False),flush=True)
