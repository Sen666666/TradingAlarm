"""One bounded pure-feature export. No labels, PnL, model/cache or Account calls."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,gzip,hashlib,importlib.util,json,math,signal,time
import numpy as np,pandas as pd
import pyarrow as pa,pyarrow.parquet as pq
O=Path(__file__).resolve().parent;P=O.parent;E=P.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');F=P/'feature_design/features.py'
FEATURE_SHA='cbb46aaa6c93a0760e570cb482151112da430f3047c3cc8ec2b7ad0bd1ca69a6'
spec=importlib.util.spec_from_file_location('pvr_information_pure_features_export',F);API=importlib.util.module_from_spec(spec);spec.loader.exec_module(API)
class BudgetExceeded(Exception):pass
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,z):
 with Path(p).open('x')as f:json.dump(z,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def load(p,sources):p=Path(p);sources[str(p.resolve())]=sha(p);return json.loads(p.read_text())
def feature_schema():
 fields=[pa.field(k,pa.string())for k in ['sid','day','window','sector']]
 for k in API.PVR_COLUMNS:fields.append(pa.field(k,pa.float64()))
 fields += [pa.field('source_segment',pa.float64()),pa.field('pvr_valid_observation',pa.bool_()),pa.field('pvr_clock_block',pa.int64()),pa.field('pvr_block_observation',pa.int64()),pa.field('pvr_status',pa.string()),pa.field('return5_anchor_day',pa.timestamp('ns')),pa.field('return20_anchor_day',pa.timestamp('ns'))]
 for k in API.FEATURE_COLUMNS:fields += [pa.field(k,pa.bool_()if k=='breakout_prior_high20'else pa.float64()),pa.field(k+'_status',pa.string())]
 fields += [pa.field('stock_source_row_present',pa.bool_()),pa.field('sector_source_row_present',pa.bool_()),pa.field('sector_source_segment',pa.float64()),pa.field('sector_pvr_valid_observation',pa.bool_()),pa.field('sector_pvr_clock_block',pa.int64())]
 for k in ['sector_return20','sector_sign_persistence21_w09','aligned_sector_return_on_stock20_interval','relative_return20']:fields += [pa.field(k,pa.float64()),pa.field(k+'_status',pa.string())]
 fields.append(pa.field('aligned_sector_anchor_day',pa.timestamp('ns')))
 return pa.schema(fields)
QUOTE_SCHEMA=pa.schema([pa.field(k,pa.string())for k in ['sid','day','window']]+[pa.field('open',pa.float64()),pa.field('close',pa.float64()),pa.field('valid',pa.bool_()),pa.field('block',pa.int64()),pa.field('observed',pa.bool_())])
def calendars(sources):
 dates=[];windows=[];out={}
 for win,n in [('2022_2024',726),('strong',242)]:
  path=E/'trend_exit_controls_v1/runs/BASELINE'/win/'pair/daily.jsonl.gz';sources[str(path.resolve())]=sha(path)
  with gzip.open(path,'rt')as f:ds=[json.loads(x)['at'][:10]for x in f]
  assert len(ds)==len(set(ds))==n and ds==sorted(ds);out[win]=ds;dates+=ds;windows += [win]*n
 return pd.DatetimeIndex(dates),windows,out
def signal_path(record):
 paths=[p for p in record['source_sha256']if p.endswith('/signal.parquet')];assert len(paths)==1
 return Path(paths[0]),record['source_sha256'][paths[0]]
def read_signal(record,sources):
 path,h=signal_path(record);assert sha(path)==h,('changed original signal',str(path));sources[str(path)]=h
 return pd.read_parquet(path)
def standardized(full,dates):
 q=full.reindex(dates).copy();present=dates.isin(full.index)
 q['source_segment']=q.source_segment.astype('float64')
 q['pvr_valid_observation']=q.pvr_valid_observation.fillna(False).astype(bool)
 for k in ['pvr_clock_block','pvr_block_observation']:q[k]=q[k].astype('Int64')
 for k in ['return5_anchor_day','return20_anchor_day']:q[k]=pd.to_datetime(q[k])
 q['pvr_status']=q.pvr_status.astype('string').fillna('NO_EXACT_SOURCE_OBSERVATION')
 for k in API.FEATURE_COLUMNS:
  q[k]=q[k].astype('boolean'if k=='breakout_prior_high20'else'float64');q[k+'_status']=q[k+'_status'].astype('string').fillna('NO_EXACT_SOURCE_OBSERVATION')
 return q,present
def aligned_sector(stock,sector_signal,sector_features,dates):
 anchor=pd.DatetimeIndex(stock.return20_anchor_day);g0=sector_features.reindex(anchor);g1=sector_features.reindex(dates);raw0=sector_signal.reindex(anchor);raw1=sector_signal.reindex(dates)
 v0=g0.pvr_valid_observation.fillna(False).to_numpy(bool);v1=g1.pvr_valid_observation.fillna(False).to_numpy(bool);b0=g0.pvr_clock_block.to_numpy(float,na_value=np.nan);b1=g1.pvr_clock_block.to_numpy(float,na_value=np.nan)
 p0=raw0.close.to_numpy(float);p1=raw1.close.to_numpy(float);known=stock.return20_status.eq('KNOWN').to_numpy(bool)&~anchor.isna()
 status=np.full(len(dates),'UNKNOWN_NO_STOCK20_WINDOW',dtype=object);status[known]='UNKNOWN_SECTOR_NO_EXACT_ENDPOINT'
 exact=known&anchor.isin(sector_signal.index)&dates.isin(sector_signal.index);status[exact]='UNKNOWN_SECTOR_INVALID_PVR_ENDPOINT'
 valid=exact&v0&v1&np.isfinite(p0)&np.isfinite(p1)&(p0>0)&(p1>0);status[valid]='UNKNOWN_SECTOR_BLOCK_TRANSITION';same=valid&(b0==b1);status[same]='UNKNOWN_NUMERICAL_RESULT'
 ret=np.full(len(dates),np.nan);ret[same]=p1[same]/p0[same]-1;ready=same&np.isfinite(ret);status[ready]='KNOWN'
 relative=np.full(len(dates),np.nan);relative[ready]=stock.return20.to_numpy(float)[ready]-ret[ready]
 return ret,relative,pd.Series(status,index=dates,dtype='string')
def build_stock(sid,sector,sig,full,dates,windows,sector_signal,sector_full):
 f,present=standardized(full,dates);g,gpresent=standardized(sector_full,dates)
 f.insert(0,'sector',sector);f.insert(0,'window',windows);f.insert(0,'day',dates.strftime('%Y-%m-%d'));f.insert(0,'sid',sid)
 f['stock_source_row_present']=present;f['sector_source_row_present']=gpresent;f['sector_source_segment']=g.source_segment;f['sector_pvr_valid_observation']=g.pvr_valid_observation;f['sector_pvr_clock_block']=g.pvr_clock_block
 for dst,src in [('sector_return20','return20'),('sector_sign_persistence21_w09','sign_persistence21_w09')]:f[dst]=g[src];f[dst+'_status']=g[src+'_status']
 aligned,relative,status=aligned_sector(f,sector_signal,sector_full,dates)
 f['aligned_sector_return_on_stock20_interval']=aligned;f['aligned_sector_return_on_stock20_interval_status']=status;f['relative_return20']=relative;f['relative_return20_status']=status;f['aligned_sector_anchor_day']=f.return20_anchor_day
 obs=pd.Series(True,index=sig.index,dtype=bool)
 for name in ['observed_bar','is_observed_bar']:
  if name in sig:obs &= sig[name].fillna(False).astype(bool)
 if 'synthetic_event_bar'in sig:obs &= ~sig.synthetic_event_bar.fillna(True).astype(bool)
 raw=sig.reindex(dates);quotes=pd.DataFrame(dict(sid=sid,day=dates.strftime('%Y-%m-%d'),window=windows,open=raw.open.astype(float),close=raw.close.astype(float),valid=f.pvr_valid_observation,block=f.pvr_clock_block,observed=obs.reindex(dates).fillna(False).astype(bool)),index=dates)
 return f,quotes
def ranklog_queries(sources):
 by=defaultdict(list);counts=Counter()
 for win in ['2022_2024','strong']:
  path=E/'trend_exit_controls_v1/runs/BASELINE'/win/'pair/rank-policy.jsonl.gz';sources[str(path.resolve())]=sha(path)
  with gzip.open(path,'rt')as f:
   for line in f:
    r=json.loads(line);assert r['account']=='B';by[r['sid']].append((win,r['day'],bool(r['PVR_ready']),r['PVR']));counts[win]+=1
 return by,dict(counts)
def check_scores(sid,features,queries,counter):
 for win,day,ready,value in queries.get(sid,[]):
  q=features.loc[pd.Timestamp(day)];assert q.window==win
  got=float(q.score);known=math.isfinite(got);assert known==ready,(sid,day,'readiness mismatch',got,value)
  if ready:assert np.float64(got).view(np.uint64)==np.float64(value).view(np.uint64),(sid,day,'score not bitexact',got,value)
  else:assert value is None or not math.isfinite(float(value))
  counter['ranklog_queries_checked']+=1;counter['ranklog_ready_bitexact'if ready else'ranklog_UNKNOWN_exact']+=1
def schema_description():
 return dict(feature_fields=[dict(name=f.name,type=str(f.type))for f in feature_schema()],reference_quote_fields=[dict(name=f.name,type=str(f.type))for f in QUOTE_SCHEMA],day='ISO YYYY-MM-DD string; calendar index is position in manifest calendars[window], never continuous across windows',quote_coordinates='Original causal signal open/close, not raw executable OPEN. valid=original PVR close+amount+original masks; block=original PVR invalid/source restart block; observed=true original observed and not synthetic. No filled/carry quote.',relative_clock='Stock return20 actual anchor; industry endpoints exact and both PVR-valid same industry block. Industry own20-observation return remains separate.',no_future_labels=True,no_PnL=True,new_accounts=0,new_market_models=0)
def execute(seconds):
 started=time.monotonic();sources={};assert sha(F)==FEATURE_SHA
 assert not any((O/n).exists()for n in ['RUN_STARTED.json','FEATURE_MANIFEST_PRE_LABEL.json','features.parquet','reference_quotes.parquet'])
 for p in [Path(__file__),F,P/'ANALYSIS_FREEZE.json',P/'PRE_LABEL_MASS_CONCENTRATION_SUPPLEMENT.json',P/'PRE_EXPORT_INTERVAL_AND_PRICE_DOMAIN.json',P/'PRE_LABEL_CLOCK_AND_WEIGHT_CLARIFICATION.json']:
  assert p.is_file(),str(p);sources[str(p.resolve())]=sha(p)
 save(O/'RUN_STARTED.json',dict(started_epoch=time.time(),budget_seconds=seconds,source_sha256=sources,single_execution=True,automatic_retry=False,no_future_labels=True,new_accounts=0))
 def alarm(*_):raise BudgetExceeded('Single pure-feature export wall-time budget exceeded')
 signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,seconds)
 fw=qw=None;count=Counter();progress=dict(stage='load_inputs',completed_stocks=0,completed_industries=0);status_counts=defaultdict(Counter)
 try:
  sm=load(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json',sources);im=load(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json',sources);meta=load('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json',sources)
  assert len(sm)==1709 and len(im)==90;dates,windows,cals=calendars(sources);assert len(dates)==968 and dates.is_unique
  queries,qcounts=ranklog_queries(sources);sector_data={};progress['stage']='industry_features'
  for rec in im:
   sig=read_signal(rec,sources);sector_data[rec['series']]=(sig,API.compute_features(sig));progress['completed_industries']+=1
  fs=feature_schema();fw=pq.ParquetWriter(O/'features.parquet',fs,compression='zstd',use_dictionary=True);qw=pq.ParquetWriter(O/'reference_quotes.parquet',QUOTE_SCHEMA,compression='zstd',use_dictionary=True);progress['stage']='stock_features'
  for rec in sm:
   sid=rec['symbol'];progress['current_sid']=sid;sector=meta[sid]['sector_id'];assert sector in sector_data
   sig=read_signal(rec,sources);full=API.compute_features(sig);f,q=build_stock(sid,sector,sig,full,dates,windows,*sector_data[sector]);check_scores(sid,f,queries,count)
   fw.write_table(pa.Table.from_pandas(f,schema=fs,preserve_index=False,safe=True));qw.write_table(pa.Table.from_pandas(q,schema=QUOTE_SCHEMA,preserve_index=False,safe=True))
   count['stock_days']+=len(f);count['stock_source_rows_present']+=int(f.stock_source_row_present.sum());count['reference_observed']+=int(q.observed.sum());count['reference_valid_PVR_domain']+=int(q.valid.sum());count['empty_signal_symbols']+=int(sig.empty);count['PVR_known_stockdays']+=int(np.isfinite(f.score).sum())
   for k in [x for x in f if x.endswith('_status')]:status_counts[k].update({str(a):int(b)for a,b in f[k].value_counts(dropna=False).items()})
   progress['completed_stocks']+=1
   if progress['completed_stocks']%100==0:
    temp=O/'PROGRESS.json';temp.write_text(json.dumps(dict(progress,elapsed_seconds=time.monotonic()-started,counts=dict(count)),ensure_ascii=False,indent=2)+'\n');print('FEATURE_EXPORT_PROGRESS',progress['completed_stocks'],round(time.monotonic()-started,2),flush=True)
  fw.close();qw.close();fw=qw=None;progress['stage']='seal_pre_label_manifest'
  assert count['stock_days']==1709*968 and count['ranklog_queries_checked']==sum(qcounts.values())and count['empty_signal_symbols']==22
  assert sha(F)==FEATURE_SHA
  for p,h in list(sources.items()):
   if p.endswith('.py')or p.endswith('.json'):assert sha(p)==h,('source changed during export',p)
  outputs={n:dict(path=str((O/n).resolve()),sha256=sha(O/n),rows=pq.read_metadata(O/n).num_rows,row_groups=pq.read_metadata(O/n).num_row_groups)for n in ['features.parquet','reference_quotes.parquet']}
  manifest=dict(status='COMPLETE_PURE_FEATURE_EXPORT_BEFORE_ANY_LABEL_OR_PNL',feature_source_sha256=FEATURE_SHA,exporter_sha256=sha(__file__),source_sha256=sources,calendars=cals,windows=dict((w,dict(days=len(ds),stock_day_rows=len(ds)*1709))for w,ds in cals.items()),counts=dict(count),ranklog_queries_by_window=qcounts,status_counts={k:dict(v)for k,v in status_counts.items()},schema=schema_description(),outputs=outputs,elapsed_seconds=time.monotonic()-started,budget_seconds=seconds,stock_symbols=1709,industry_symbols=90,automatic_retry=False,no_future_labels=True,no_original_PnL_imported=True,new_accounts=0,new_market_models=0)
  save(O/'FEATURE_MANIFEST_PRE_LABEL.json',manifest);print('FEATURE_EXPORT_COMPLETE',count['stock_days'],round(time.monotonic()-started,2),flush=True)
 except BaseException as err:
  signal.setitimer(signal.ITIMER_REAL,0)
  if fw is not None:fw.close()
  if qw is not None:qw.close()
  save(O/'EXPORT_STOPPED.json',dict(status='STOPPED_PRESERVE_PARTIAL_NO_AUTOMATIC_RETRY',error=repr(err),progress=progress,counts=dict(count),elapsed_seconds=time.monotonic()-started,no_future_labels=True,new_accounts=0))
  raise
 finally:signal.setitimer(signal.ITIMER_REAL,0)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--budget-seconds',type=float,default=120);a=p.parse_args()
 if a.execute:execute(a.budget_seconds)
 else:print(json.dumps(schema_description(),ensure_ascii=False,indent=2))
