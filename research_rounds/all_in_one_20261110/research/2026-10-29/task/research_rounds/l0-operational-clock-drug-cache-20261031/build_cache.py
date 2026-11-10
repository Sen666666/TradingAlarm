from pathlib import Path
import sys,json,hashlib,time,importlib.util,datetime,traceback
from concurrent.futures import ProcessPoolExecutor
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');RR=ROOT/'research_rounds';NEW=ROOT/'TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared';OLD=RR/'innovative-drug-sfw3-20261028/prepared';LOCAL=RR/'innovative-drug-local-recovery-20261028';CUT='2026-10-27'
sys.path.insert(0,str(RR/'innovative-drug-sfw3-20261028/code'));import drug_common as DC
sys.path.insert(0,str(ROOT));from TradingAlarm.desk.refresh import prepare_facts
C=DC.C
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def signal(rec,cut=None):
 assert sha(rec['raw']['path'])==rec['raw']['sha256'];raw=C.read_raw(rec['raw']['path'],rec);events,_=C.read_actions(rec,Path(rec['raw']['path']).parent)
 if cut:raw=raw.loc[:cut];events=[e for e in events if e['effective_date']<=cut]
 parts=[]
 for j,part in enumerate(C.source_segments(raw,rec)):
  g=raw.loc[part['start']:part['end']]
  if len(g):f=C.prepare_signal(g,rec,events,cutoff=cut);f['segment_id']=j;parts.append(f)
 return pd.concat(parts)
def job(rec):
 t=time.monotonic();sid=rec['series_id'];f=signal(rec);facts=prepare_facts(f)
 for name,new in [('signals',f),('facts',facts)]:
  old=pd.read_parquet(OLD/name/f'{sid}.parquet');pd.testing.assert_frame_equal(new.loc[:CUT],old.loc[:CUT],check_exact=True,check_freq=False)
  new.to_parquet(O/'prepared'/name/f'{sid}.parquet')
 physical=[]
 if sid in ['000513.SZ','300601.SZ']:
  small=signal(rec,'2026-10-28');pd.testing.assert_frame_equal(small,f.loc[:'2026-10-28'],check_exact=True,check_freq=False);sf=prepare_facts(small);pd.testing.assert_frame_equal(sf,facts.loc[:'2026-10-28'],check_exact=True,check_freq=False);physical.append('2026-10-28')
 result=dict(sid=sid,rows=len(facts),old_prefix_rows=len(facts.loc[:CUT]),last=str(facts.index[-1].date()),prefix_exact=True,physical_prefixes=physical,facts_sha=sha(O/'prepared/facts'/f'{sid}.parquet'),signals_sha=sha(O/'prepared/signals'/f'{sid}.parquet'),created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),seconds=time.monotonic()-t)
 save(O/'receipts'/f'{sid}.json',result);return result
def market(roster):
 z=np.load(NEW/'h1.npz');dates=pd.DatetimeIndex(z['dates']);col={str(s):j for j,s in enumerate(z['symbols'])};closes=z['close'];segments=z['segment'];returns={};mom={}
 for sid in roster.symbol:
  rec=next(r for r in read(NEW/'manifest.json')['series'] if r['series_id']==sid);raw=C.read_raw(rec['raw']['path'],rec);j=col[sid];index=dates[np.isfinite(closes[:,j])];f=raw.reindex(index);f=f[f.observed_bar.fillna(False)&f.price_eligible.fillna(False)&~f.synthetic_event_bar.fillna(True)];f=f.assign(close=pd.Series(closes[:,j],index=dates).reindex(f.index),segment_id=pd.Series(segments[:,j],index=dates).reindex(f.index));rs=[];ms=[]
  for _,g in f.groupby('segment_id',sort=False):
   r=np.log(g.close).diff();q=g.amount/g.amount.shift().rolling(21,min_periods=21).median();u=r*np.minimum(1,np.sqrt(q));m=u.ewm(span=21,adjust=False).mean();ready=np.arange(len(g))>=64;rs.append(r.where(ready));m.iloc[:64]=np.nan;ms.append(m)
  returns[sid]=pd.concat(rs).sort_index();mom[sid]=pd.concat(ms).sort_index()
 # Original broad component files carry the full common date index. Restrict
 # to that same historical clock, append exactly three already observed days.
 oldr=pd.read_parquet(RR/'innovative-drug-sfw3-20261028/market-returns.parquet',columns=roster.symbol.tolist());oldm=pd.read_parquet(RR/'innovative-drug-sfw3-20261028/market-momentum.parquet',columns=roster.symbol.tolist());ix=oldr.index.append(pd.DatetimeIndex(['2026-10-28','2026-10-29','2026-10-30']));r=pd.DataFrame(returns).reindex(ix);m=pd.DataFrame(mom).reindex(ix)
 pd.testing.assert_frame_equal(r.loc[:CUT],oldr,check_exact=True,check_freq=False);pd.testing.assert_frame_equal(m.loc[:CUT],oldm,check_exact=True,check_freq=False)
 # Import the existing local formula only; do not call its old-file main().
 src=(LOCAL/'code/recovery.py').read_text();body=src[src.index('MIN_SECTORS='):src.index('\ndef main():')];env=dict(pd=pd,np=np);exec(body,env);out,cov=env['calculate'](r,m,roster);old=pd.read_csv(LOCAL/'recovery.csv',index_col=0,parse_dates=True)
 # CSV parsing can differ by last binary digits. Keep every frozen historical
 # row byte-for-byte in the versioned CSV after verifying the actual formula.
 pd.testing.assert_frame_equal(out.loc[:CUT],old,check_exact=False,rtol=1e-14,atol=1e-14,check_freq=False);assert np.array_equal(out.loc[:CUT,'breakout'],old.breakout)
 out=pd.concat([old,out.loc[out.index>pd.Timestamp(CUT)]]);r.to_parquet(O/'prepared/market-returns.parquet');m.to_parquet(O/'prepared/market-momentum.parquet');out.to_csv(O/'prepared/recovery.csv');cov.to_csv(O/'prepared/market-coverage.csv')
 reread=pd.read_csv(O/'prepared/recovery.csv',index_col=0,parse_dates=True);pd.testing.assert_frame_equal(reread.loc[:CUT],old,check_exact=True,check_freq=False)
 return dict(passed=True,old_component_prefix_exact=True,old_recovery_values_exact_after_preserving_frozen_rows=True,recalculated_recovery_matches_within_original_1e14_tolerance=True,breakout_prefix_exact=True,minimum_stocks_per_sector=5,minimum_sectors=3,new_rows=out.loc[out.index>pd.Timestamp(CUT)].reset_index().to_dict('records'),valid_sectors_new={str(k):int(v) for k,v in cov.loc[cov.index>pd.Timestamp(CUT),'valid_sectors'].items()},created_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
def main():
 start=time.monotonic();root=O/'prepared';root.mkdir(exist_ok=False)
 for name in ['signals','facts']:(root/name).mkdir()
 (O/'receipts').mkdir();roster=pd.read_csv(LOCAL/'pool.csv');ids=set(roster.symbol)|set(roster.sector_id);records={r['series_id']:r for r in read(NEW/'manifest.json')['series']};selected=[records[s] for s in sorted(ids)];assert len(selected)==52
 sources=[Path(__file__),ROOT/'TradingAlarm/desk/refresh.py',RR/'innovative-drug-sfw3-20261028/code/drug_common.py',RR/'innovative-drug-sfw3-20261028/code/recovery.py',LOCAL/'code/recovery.py',LOCAL/'pool.csv',NEW/'manifest.json',NEW/'h1.npz']
 save(O/'FREEZE.json',dict(before_new_economic_paths=True,new_economic_paths=0,source_sha={str(p):sha(p) for p in sources},records=selected,created_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
 receipts=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  for r in pool.map(job,selected):receipts.append(r);print('CACHE',len(receipts),r['sid'],round(r['seconds'],2),flush=True)
 save(O/'CACHE_GATE.json',dict(passed=True,series=52,stocks=48,sectors=4,signal_and_fact_prefixes=104,physical_prefixes=sum(len(r['physical_prefixes']) for r in receipts),receipts=receipts,seconds=time.monotonic()-start))
 clock=market(roster);save(O/'MARKET_GATE.json',clock);save(root/'manifest.json',dict(series=selected,facts=receipts,as_of='2026-10-30',created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),TECH_clock_not_used=True));save(O/'BUILD_TIMING.json',dict(seconds=time.monotonic()-start));print('COMPLETE52',round(time.monotonic()-start,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save(O/'BUILD_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
