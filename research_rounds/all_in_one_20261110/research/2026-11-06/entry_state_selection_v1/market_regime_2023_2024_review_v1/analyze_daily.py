import pathlib,json,hashlib,pandas as pd,numpy as np
R=pathlib.Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=pathlib.Path(__file__).parent
U=pathlib.Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031');BASE=pathlib.Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
phases=[('2023_early_AI','2023-01-03','2023-04-28'),('2023_AI_second_leg','2023-05-04','2023-06-20'),('2023_downtrend','2023-06-21','2023-10-23'),('2023_late_rebound','2023-10-24','2023-12-29'),('2024_early_decline','2024-01-02','2024-02-05'),('2024_reversal_and_resources','2024-02-06','2024-05-20'),('2024_summer_decline','2024-05-21','2024-09-23'),('2024_924_reversal','2024-09-24','2024-10-08'),('2024_late_diffusion','2024-10-09','2024-12-31')]
extra=[('2023_H1','2023-01-03','2023-06-30'),('2023_full','2023-01-03','2023-12-29'),('2024_full','2024-01-02','2024-12-31')]
rep=['300308.SZ','300502.SZ','300394.SZ','000977.SZ','601138.SH','300418.SZ','300624.SZ','300364.SZ','002558.SZ','300735.SZ','300045.SZ','601398.SH','601939.SH','600547.SH','601899.SH','601088.SH','600900.SH','688981.SH','688256.SH','300085.SZ','300059.SZ','000158.SZ','300339.SZ','601127.SH','002085.SZ','001696.SZ','601012.SH','300750.SZ','600519.SH']
sources={};sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):sources[str(p)]=sha(p);return json.loads(p.read_text())
manifest=read(U/'INDUSTRY_MANIFEST.json');stock=read(U/'STOCK_MANIFEST.json');masterpath=BASE/'data-adjudicated-v2/master-input.csv';sources[str(masterpath)]=sha(masterpath);master=pd.read_csv(masterpath)
names=master.dropna(subset=['industry_index_symbol']).groupby('industry_index_symbol').industry_name.first().to_dict();stocknames=master.dropna(subset=['name']).set_index('symbol').name.to_dict()
def load(row):
 ps=[(p,h) for p,h in row['source_sha256'].items() if p.endswith('/signal.parquet') and '/a-share-selection-e0-' in p];assert len(ps)==1;p,h=ps[0];assert sha(p)==h;sources[p]=h;df=pd.read_parquet(p);assert df.index.is_unique;sid=row.get('series',row.get('symbol'));assert set(df.symbol.dropna())=={sid};return df
sector={m['series']:load(m) for m in manifest};calendar=sorted(set().union(*(set(d.loc['2022-12-30':'2024-12-31'].index) for d in sector.values())))
results=[]
def metrics(sid,name,kind,df,phase,start,end):
 d=df.loc[start:end]; prior=df.loc[:pd.Timestamp(start)-pd.Timedelta(days=1)];valid=d.observed_bar.astype(bool)&d.price_eligible.astype(bool)&~d.source_invalid.astype(bool)&~d.synthetic_event_bar.astype(bool)&d.close.gt(0)
 z=d[valid];expected=[x for x in calendar if pd.Timestamp(start)<=x<=pd.Timestamp(end)];unknown=set(expected)-set(z.index)
 r={'phase':phase,'start':start,'end':end,'sid':sid,'name':name,'kind':kind,'expected_sessions':len(expected),'valid_sessions':len(z),'missing_sessions':len(unknown),'missing_dates':[str(x.date()) for x in sorted(unknown)],'source_kind':','.join(sorted(set(d.source_kind.astype(str))))}
 prior=prior[prior.observed_bar.astype(bool)&prior.price_eligible.astype(bool)&~prior.source_invalid.astype(bool)&~prior.synthetic_event_bar.astype(bool)&prior.close.gt(0)]
 if prior.empty or z.empty:r['status']='UNKNOWN_NO_BASE_OR_ROWS';return r
 b=prior.iloc[-1];bd=prior.index[-1]; base=float(b.close);vals=np.r_[base,z.close.values.astype(float)];dates=[bd]+list(z.index);peak=np.maximum.accumulate(vals);dd=vals/peak-1;floor=np.minimum.accumulate(vals);ru=vals/floor-1;di=int(np.argmin(dd));ri=int(np.argmax(ru));pi=int(np.argmax(vals[:di+1]));fi=int(np.argmin(vals[:ri+1]));maxi=int(np.argmax(vals));
 r.update(status='COMPLETE' if len(unknown)==0 else 'OBSERVED_PATH_WITH_GAPS',base_day=str(bd.date()),actual_last_day=str(z.index[-1].date()),return_pct=(vals[-1]/base-1)*100,max_drawdown_pct=float(dd[di]*100),dd_peak_day=str(dates[pi].date()),dd_trough_day=str(dates[di].date()),max_runup_pct=float(ru[ri]*100),runup_low_day=str(dates[fi].date()),runup_high_day=str(dates[ri].date()),peak_from_base_pct=(vals[maxi]/base-1)*100,peak_day=str(dates[maxi].date()))
 return r
for sid,d in sector.items():
 for p,s,e in phases+extra:results.append(metrics(sid,names.get(sid,sid),'THS_industry_index',d,p,s,e))
sm={m['symbol']:m for m in stock};missing=[s for s in rep if s not in sm]
for sid in rep:
 if sid not in sm:continue
 d=load(sm[sid])
 for p,s,e in phases+extra:results.append(metrics(sid,stocknames.get(sid,sid),'fixed_representative_stock',d,p,s,e))
def norm(o):
 if isinstance(o,dict):return {k:norm(v) for k,v in o.items()}
 if isinstance(o,list):return [norm(v) for v in o]
 if isinstance(o,np.generic):return o.item()
 return o
pd.DataFrame(results).to_csv(O/'ALL_PHASE_METRICS.csv',index=False);(O/'ALL_PHASE_METRICS.json').write_text(json.dumps(norm(results),ensure_ascii=False,indent=2)+'\n');(O/'SOURCE_HASHES.json').write_text(json.dumps(sources,indent=2)+'\n');(O/'PROTOCOL.json').write_text(json.dumps(dict(purpose='Retrospective subjective market map, not entry signal or new strategy evidence',phases=phases,additional_fixed_aggregates=extra,representatives_preselected=rep,representatives_missing_from_manifest=missing,stocks_NON_PIT=True,industry_composition_PIT_unverified=True,returns='Adjusted close for stocks; raw THS industry index close. Prior session close to phase end.',MDD='Ordered close drawdown with prior close as initial point; not intraday drawdown.',runup='Ordered trough-before-peak descriptive statistic; never captureable return claim.'),ensure_ascii=False,indent=2)+'\n')
assert all(sha(p)==h for p,h in sources.items())
print('MISSING_REP',missing)
a=pd.DataFrame(results)
for p,s,e in phases+extra:
 z=a[(a.kind=='THS_industry_index')&(a.phase==p)].sort_values('return_pct',ascending=False)
 print('\nPHASE',p,'valid',len(z),'gapseries',sum(z.missing_sessions>0));print(z[['sid','name','return_pct','max_drawdown_pct','peak_from_base_pct']].head(8).round(2).to_string(index=False));print('BOTTOM',z[['name','return_pct']].tail(4).round(2).to_dict('records'))
