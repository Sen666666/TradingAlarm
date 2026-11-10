# Read-only posthoc path labels on 692 saved closed PVR rounds; execute in existing inspection process.
import numpy as np
EP=P/'analysis/entry_diagnostics_2022';horizons=[1,3,5,10,20]
cal2023=sorted(d for d in fm.rules['calendars']['A'] if str(d).startswith('2023'))
cutoff=pd.Timestamp(pd.Timestamp(cal2023[19]).date());print('LABEL_CUTOFF',cutoff,flush=True)
sm={r['symbol']:r for r in json.loads((C.U/'STOCK_MANIFEST.json').read_text())}
factor_frames={sid:pd.read_parquet(sm[sid]['refs']['facts'],columns=['factor']) for sid in {r['sid'] for r in closed}}
buys={t['layer']:t for t in A['trades'] if t['side']=='buy'}
labels=[];samples=[]
for r in closed:
 sid=r['sid'];first=min((buys[i] for i in r['layer_ids']),key=lambda t:(t['at'],t['layer']));opday=pd.Timestamp(first['at'].date());exitday=pd.Timestamp(r['closed'][:10]);fac=factor_frames[sid]
 assert str(first['at'])==r['opened'];ffirst=fac.loc[opday,'factor'] if opday in fac.index else None
 denominator=D(str(float(ffirst)))*first['price'] if ffirst is not None and np.isfinite(ffirst) and ffirst>0 else None
 df=raw[sid];valid=df.price_eligible & df.observed_bar & ~df.synthetic_event_bar
 obs=df.loc[valid & (df.index>=opday) & (df.index<=cutoff)].iloc[:20]
 seq=[]
 for day,row in obs.iterrows():
  f=fac.loc[day,'factor'] if day in fac.index else None
  ret=(D(str(row.close))*D(str(float(f)))/denominator-D(1)) if denominator and f is not None and np.isfinite(f) else None
  seq.append(dict(day=str(day.date()),ret=ret,held=day<exitday,raw_close=D(str(row.close)),factor=None if f is None else D(str(float(f)))))
 common=dict(account='PVR',sid=sid,round_id=r['id'],opened=r['opened'],signal_at=str(first['signal_at']),first_layer=first['layer'],first_fill_price=first['price'],entry_factor=None if ffirst is None else D(str(float(ffirst))),closed=r['closed'],final_round_pnl=r['pnl'],outcome='WIN' if r['pnl']>0 else 'LOSS',entry_quarter=r['opened'][:4]+'Q'+str((int(r['opened'][5:7])-1)//3+1))
 assert len(seq)==len({z['day'] for z in seq})
 for mode in ['fixed_future_label','actual_holding_only']:
  row=dict(common,mode=mode,available_valid_closes=len(seq) if mode=='fixed_future_label' else sum(z['held'] for z in seq),first_valid_close=seq[0]['day'] if seq else None,day1_is_entry_day=bool(seq and seq[0]['day']==str(opday.date())))
  for n in horizons:
   target=seq[n-1] if len(seq)>=n else None;prefix=seq[:n]
   eligible=bool(target and (mode=='fixed_future_label' or target['held']) and all(z['ret'] is not None for z in prefix))
   row[f'day{n}_date']=target['day'] if target else None;row[f'day{n}_eligible']=eligible
   row[f'day{n}_return']=target['ret'] if eligible else None
   row[f'day{n}_MAE']=min([D(0)]+[z['ret'] for z in prefix]) if eligible else None
   row[f'day{n}_MFE']=max([D(0)]+[z['ret'] for z in prefix]) if eligible else None
  labels.append(row)
 samples.extend(dict(common,observation=i+1,**z) for i,z in enumerate(seq))
summary=[]
for mode in ['fixed_future_label','actual_holding_only']:
 for quarter in ['ALL']+sorted({r['entry_quarter'] for r in labels}):
  for outcome in ['WIN','LOSS']:
   group=[r for r in labels if r['mode']==mode and r['outcome']==outcome and (quarter=='ALL' or r['entry_quarter']==quarter)]
   for n in horizons:
    good=[r for r in group if r[f'day{n}_eligible']];rr=np.array([float(r[f'day{n}_return']) for r in good]);mae=np.array([float(r[f'day{n}_MAE']) for r in good]);mfe=np.array([float(r[f'day{n}_MFE']) for r in good])
    summary.append(dict(mode=mode,entry_quarter=quarter,outcome=outcome,horizon=n,total_rounds=len(group),n=len(good),missing_or_exited=len(group)-len(good),mean_return=float(rr.mean()) if len(rr) else None,median_return=float(np.median(rr)) if len(rr) else None,positive_fraction=float((rr>0).mean()) if len(rr) else None,mean_MAE=float(mae.mean()) if len(mae) else None,median_MAE=float(np.median(mae)) if len(mae) else None,mean_MFE=float(mfe.mean()) if len(mfe) else None,median_MFE=float(np.median(mfe)) if len(mfe) else None))
print('ALL_ENTRY_PATHS',[r for r in summary if r['entry_quarter']=='ALL'],flush=True)
assert len(labels)==2*692 and len({(r['account'],r['sid'],r['round_id'],r['mode']) for r in labels})==len(labels)
pd.DataFrame(labels).to_csv(EP/'ENTRY_PATH_LABELS.csv',index=False);pd.DataFrame(summary).to_csv(EP/'PATH_SUMMARY.csv',index=False);pd.DataFrame(samples).to_csv(EP/'PATH_OBSERVATIONS.csv',index=False)
(EP/'PATH_METADATA.json').write_text(json.dumps(dict(checkpoint_sha256=h,rounds=692,cutoff=str(cutoff.date()),day1_not_entry_day=sum(not r['day1_is_entry_day'] for r in labels if r['mode']=='fixed_future_label'),return_definition='raw close times original same-day factor / (actual first fill price times entry-day factor) minus 1; fee-exclusive first-entry price label; subsequent trades ignored',MAE_MFE='min/max valid close price returns from entry through target observation, including zero baseline; not intraday high/low',holding_rule='target close strictly before final exit date 09:30; no post-exit close in actual_holding_only',fixed_future='may observe after actual exit; posthoc entry label, never portfolio return',quarter='first actual buy quarter',no_account_run=True),indent=2))
