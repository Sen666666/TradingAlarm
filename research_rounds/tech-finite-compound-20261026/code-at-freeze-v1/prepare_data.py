"""Append verified daily deltas, keeping every old row and frozen signal prefix."""
from common import *
from concurrent.futures import ProcessPoolExecutor
from decimal import Decimal as D
import copy,csv,time

def merge_one(sid,record,history,rights,folder):
 old=read_raw(record['raw']['path'],record);d=read(history);assert d['history_status']=='complete'
 new=pd.DataFrame(d['bars']).rename(columns={'date':'trade_date'});new['trade_date']=pd.to_datetime(new.trade_date)
 rawold=old.reset_index().rename(columns={'date':'trade_date'})
 # Older index files omit observation masks; preserve the bridge's defaults
 # before concat introduces a nullable column for the entire old prefix.
 for key,default in [('observed_bar',True),('is_observed_bar',True),('source_invalid',False),('synthetic_event_bar',False)]:
  if key not in rawold:rawold[key]=default
 a=old;b=new.set_index('trade_date');ix=a.index.intersection(b.index);conf=[]
 for c in ['open','high','low','close','volume','amount']:
  av=a.loc[ix,c].to_numpy(float);bv=b.loc[ix,c].to_numpy(float);valid=np.isfinite(av)&np.isfinite(bv)
  tol=dict(rtol=0,atol=1e-6) if c in ['open','high','low','close'] else dict(rtol=1e-6,atol=1.)
  bad=valid&~np.isclose(av,bv,**tol)
  for dt,u,v in zip(ix[bad],av[bad],bv[bad]):conf.append(dict(symbol=sid,date=str(dt.date()),field=c,old=float(u),new=float(v)))
 if conf:raise ValueError('delta overlap conflict: '+str(conf[:3]))
 tail=new.loc[new.trade_date>pd.Timestamp('2026-10-22')].copy();assert not len(tail) or len(ix)
 for c in ['open','high','low','close','volume','amount']:tail[c]=pd.to_numeric(tail[c],errors='coerce')
 o=tail[['open','high','low','close']];valid=np.isfinite(o).all(axis=1)&o.gt(0).all(axis=1)&tail.high.ge(tail[['open','close']].max(axis=1))&tail.low.le(tail[['open','close']].min(axis=1))
 tail['symbol']=sid;tail['source_path']=str(history);tail['source_kind']='THS_verified_increment';tail['price_eligible']=valid;tail['volume_eligible']=np.isfinite(tail.volume)&tail.volume.gt(0);tail['source_invalid']=~valid
 for c in ['observed_bar','is_observed_bar']:tail[c]=True
 tail['synthetic_event_bar']=False;tail['volume_unit']=record['volume_unit'];tail['amount_unit']='CNY' if record['kind']=='stock' else 'source_index_amount_units';tail['price_adjustment']='raw';tail['observed_at']=now();tail['quality_status']='verified_delta'
 merged=pd.concat([rawold,tail],ignore_index=True).sort_values('trade_date');assert merged.trade_date.is_unique
 p=folder/'bars'/f'{sid}.parquet';p.parent.mkdir(parents=True,exist_ok=True);merged.to_parquet(p,index=False)
 rec=copy.deepcopy(record);rec['raw']=dict(path=str(p.resolve()),sha256=sha(p))
 if rec.get('segments'):rec['segments'][-1]['end']=str(pd.to_datetime(merged.trade_date).max().date())
 if rec.get('unavailable_from') and len(tail):raise ValueError('cannot silently remove source unavailability '+sid)
 appended=[]
 if rights:
  assert rights.exists();rawrights=read(rights)
  latest=[r for r in rawrights if '20261022'<str(r.get('1',''))<='20261026']
  normal=import_path('tech_action_terms',ROOT/'research_rounds/a-share-selection-e0-20261024/code/normalize_actions.py')
  ev,ignored,unresolved=normal.normalize(latest,str(rights),'2026-10-22','2026-10-26');assert not unresolved,(sid,unresolved)
  obj=read(record['adjustment']['actions']['path']);obj=copy.deepcopy(obj);obj['events']+=ev;appended=ev
  obj['coverage_evidence']=dict(old=obj['coverage_evidence'],delta_rights=dict(path=str(rights),sha256=sha(rights)))
  ap=folder/'actions'/f'{sid}.json';write(ap,obj);rec['adjustment']['actions']=dict(path=str(ap.resolve()),sha256=sha(ap))
 return rec,dict(symbol=sid,overlap_rows=len(ix),new_rows=len(tail),new_actions=len(appended),last=str(pd.to_datetime(merged.trade_date).max().date()),history_sha256=sha(history),rights_sha256=sha(rights) if rights else None)

def merge(which):
 origin=HERE/('tail-v3' if which=='core' else 'reference-tail');assert (origin/'retrieval.json').exists()
 receipt=read(origin/'retrieval.json');assert not receipt['stopped_nodes']
 old=read(OLD/'inputs-v2/input-manifest.json');records={r['series_id']:r for r in old['series']};master=pd.read_csv(ROOT/'research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv',dtype=str);natives=dict(zip(master.symbol,master.ths_symbol));native_to_id={v:k for k,v in natives.items()}
 histories={p.stem:p for p in origin.glob('batch-*/history/*.json')};folder=CORE if which=='core' else HERE/'data'/which;folder.mkdir(parents=True,exist_ok=False);out=[];coverage=[]
 for n,(native,hp) in enumerate(sorted(histories.items())):
  sid=native if native.startswith('URFI') else native_to_id[native];record=records[sid]
  rights=None
  if record['kind']=='stock':
   cp=read(hp.parents[1]/'checkpoints'/f'{native}.json');assert cp['rights_status']=='received';rights=Path(cp['rights']['evidence_dir'])/'decoded.json' if 'evidence_dir' in cp['rights'] else hp.parents[1]/'rights'/native/'attempt-001/decoded.json'
  rec,c=merge_one(sid,record,hp,rights,folder);out.append(rec);coverage.append(c)
  if (n+1)%100==0:print(dict(stage='merge_'+which,done=n+1),flush=True)
 expected=418 if which=='core' else 1381;assert len(out)==expected,(which,len(out),expected)
 write(folder/'manifest.json',dict(series=out,coverage=coverage,old_rows_retained=True,network_downloads_here=0))
 print(dict(merged=which,series=len(out),new_rows=sum(x['new_rows'] for x in coverage),actions=sum(x['new_actions'] for x in coverage),tails=dict(pd.Series([x['last'] for x in coverage]).value_counts().map(int))),flush=True)

def signal_worker(rec):
 sid=rec['series_id'];p=Path(rec['raw']['path']);assert sha(p)==rec['raw']['sha256'];raw=read_raw(p,rec);ev,_=read_actions(rec,p.parent)
 signals=[]
 for j,part in enumerate(source_segments(raw,rec)):
  s=prepare_signal(raw.loc[part['start']:part['end']],rec,ev);s['segment_id']=j;signals.append(s)
 signal=pd.concat(signals);out=PREP/'signals';out.mkdir(parents=True,exist_ok=True);signal.to_parquet(out/f'{sid}.parquet')
 sys.path[:0]=[str(B5/'code'),str(G1/'code'),str(ROOT/'research_rounds/pv-participation-response-20261020/code')]
 import api
 from grade import classify
 from policies_g1 import project
 from data_utils import eligible_prices
 f=eligible_prices(signal)[['open','high','low','close','volume','segment_id']].copy();f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
 z=api.run_b5(f,enhancements=False);e=z['evidence'];b=z['state'];g,_=classify(e);ix=project(e,b,g,'G1_IX');ip=project(e,b,g,'G1_I')
 keep=f[['close','segment_id']].copy()
 for prefix,frame in [('e0',b),('i',ip),('ix',ix)]:
  for c in ['ready','target','floor']:
   if c in frame:keep[prefix+'_'+c]=frame[c]
 keep['i_buy']=ip.buy_event;keep['ix_buy']=ix.buy_event
 for c in ['grade','fresh_up','acute_down','ready']:keep['g_'+c]=g[c]
 keep['factor']=signal.adjustment_factor.reindex(keep.index);keep['raw_close']=signal.raw_close.reindex(keep.index)
 # Rebuilding all original observations must preserve the cached old policy.
 if rec['kind']=='stock':
  old=pd.read_parquet(IX/'signals'/f'{sid}.parquet');common=keep.loc[:'2026-10-22'].index;assert common.equals(old.index),(sid,'old complete index changed')
  for c in ['e0_target','e0_floor','ix_target','ix_floor']:
   np.testing.assert_array_equal(keep.loc[common,c].to_numpy(float),old.loc[common,c].to_numpy(float),err_msg=sid+c)
  np.testing.assert_array_equal(keep.loc[common,'i_buy'].to_numpy(bool),old.loc[common,'IX'].to_numpy(bool),err_msg=sid+' I/IX entry identity')
 else:
  pm={r['series_id']:r for r in read(OLD/'prepared-v2/manifest.json')['series']};rr=pm[sid]['files']['states'];old=pd.read_parquet(OLD/'prepared-v2'/rr['path']);common=keep.loc[:'2026-10-22'].index;assert common.equals(old.index),(sid,'old complete index changed')
  for c in ['target','floor']:np.testing.assert_array_equal(keep.loc[common,'e0_'+c].to_numpy(float),old.loc[common,c].to_numpy(float),err_msg=sid+c)
 kp=PREP/'facts'/f'{sid}.parquet';kp.parent.mkdir(parents=True,exist_ok=True);keep.to_parquet(kp)
 return dict(symbol=sid,rows=len(keep),old_prefix_rows=len(common),source_sha256=rec['raw']['sha256'],signal_sha256=sha(out/f'{sid}.parquet'),facts_sha256=sha(kp))

def signals():
 recs=read(CORE/'manifest.json')['series'];results=[]
 with ProcessPoolExecutor(max_workers=6) as pool:
  for x in pool.map(signal_worker,recs,chunksize=1):
   results.append(x)
   if len(results)%30==0:print(dict(stage='signals',done=len(results),total=len(recs)),flush=True)
 write(PREP/'manifest.json',dict(series=results,old_policy_prefix_identity=True,complete_old_indexes_equal=True))

def h1():
 from rs_h1_model import raw_momentum,MIN_REFERENCE
 old=dict(np.load(OLD/'h1/matrix.npz'));dates=pd.DatetimeIndex(old['dates']);added=pd.DatetimeIndex(['2026-10-23','2026-10-26']);cal=dates.append(added);n=len(old['symbols']);byid={str(s):j for j,s in enumerate(old['symbols'])};records={r['series_id']:r for p in [CORE/'manifest.json',HERE/'data/references/manifest.json'] for r in read(p)['series']};pm={r['series_id']:r for r in read(OLD/'prepared-v2/manifest.json')['series']}
 close=np.vstack([old['close'],np.full((2,n),np.nan)]);segment=np.vstack([old['segment'],np.full((2,n),np.nan)]);count=np.vstack([old['obs_count'],np.tile(old['obs_count'][-1],(2,1))]);hh=np.vstack([old['h'],np.minimum(old['h'][-1]+np.arange(1,3)[:,None],252)])
 for j,s in enumerate(old['symbols']):
  sid=str(s);rec=records[sid];raw=read_raw(rec['raw']['path'],rec);r=pm[sid]['files']['signal'];f=pd.read_parquet(OLD/'prepared-v2'/r['path'],columns=['adjustment_factor','segment_id']);last=f.iloc[-1];factor=D(str(last.adjustment_factor));seg=int(last.segment_id);ev,_=read_actions(rec,Path(rec['raw']['path']).parent);new_events={pd.Timestamp(e['effective_date']):e for e in ev if e['effective_date']>'2026-10-22'};previous=D(str(raw.loc[:'2026-10-22'].close.iloc[-1]));counter=int(old['obs_count'][-1,j])
  for i,day in enumerate(added,start=len(dates)):
   e=new_events.get(day)
   if e:
    cash=D(e.get('signal_cash_per_old_share',e['cash_per_old_share']));split=D(e.get('signal_split_ratio',e['split_ratio']));factor*=previous/((previous-cash)/split)
   if day in raw.index:
    row=raw.loc[day];o=[float(row[c]) for c in ['open','high','low','close']];valid=all(np.isfinite(o)) and min(o)>0 and row.high>=max(row.open,row.close) and row.low<=min(row.open,row.close) and np.isfinite(row.volume) and row.volume>0
    if valid:close[i,j]=float(D(str(row.close))*factor);segment[i,j]=seg;counter+=1
    if np.isfinite(row.close) and row.close>0:previous=D(str(row.close))
   count[i,j]=counter
  if (j+1)%300==0:print(dict(stage='h1_delta_inputs',done=j+1,total=n),flush=True)
 score=np.vstack([old['score'],np.full((2,n),np.nan)]);rawmom=np.vstack([old['raw'],np.full((2,n),np.nan)]);nref=np.vstack([old['nref'],np.zeros((2,n),int)])
 for t in range(len(dates),len(cal)):
  for left,right in [(0,1709),(1709,n)]:
   age=hh[t,left:right];ready=np.isfinite(close[t,left:right])&(count[t,left:right]>=6)&(age>=5)
   for h in np.unique(age[ready]):
    v=raw_momentum(close[:,left:right],segment[:,left:right],count[:,left:right],t,int(h));ref=np.sort(v[np.isfinite(v)]);target=np.flatnonzero((age==h)&ready);jj=target+left;rawmom[t,jj]=v[target];nref[t,jj]=len(ref)
    if len(ref)>=MIN_REFERENCE:
     vv=v[target];pct=100*(np.searchsorted(ref,vv,'left')+.5*(np.searchsorted(ref,vv,'right')-np.searchsorted(ref,vv,'left')))/len(ref);score[t,jj]=np.where(np.isfinite(vv),pct,np.nan)
 np.testing.assert_array_equal(score[:len(dates)],old['score']);PREP.mkdir(exist_ok=True);np.savez_compressed(PREP/'h1.npz',dates=cal.values,symbols=old['symbols'],score=score,close=close,segment=segment,obs_count=count,h=hh,raw=rawmom,nref=nref)
 write(PREP/'h1-receipt.json',dict(old_prefix_exact=True,stocks=1709,industries=90,new_dates=[str(x.date()) for x in added],matrix_sha256=sha(PREP/'h1.npz'),original_formula_sha256=sha(OLD/'code/rs_h1_model.py')))
 print('H1 delta complete',flush=True)

if __name__=='__main__':
 mode=sys.argv[1]
 if mode.startswith('merge-'):merge(mode.split('-',1)[1])
 elif mode=='signals':signals()
 elif mode=='h1':h1()
