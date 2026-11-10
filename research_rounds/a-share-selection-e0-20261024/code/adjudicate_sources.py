"""Before accounts: resolve demonstrated BSE source-volume convention conflicts.

Prices must agree over the entire old/new overlap. No blending V or choosing by
returns. Old files, rejected batches and original unresolved report stay intact.
"""
from pathlib import Path
import sys,csv,collections,os
import pandas as pd,numpy as np
from build_inputs import HERE,OLD,read,write,ref,now
sys.path.insert(0,str(OLD/'audit-a'))
import finalize_a as f

def main():
 q=HERE/'downloads/bse-unified-01'
 if read(q/'queue-state.json')['status']!='finished':raise ValueError('Wait for stopped source writers')
 src=HERE/'data-finalized-v1';out=HERE/'data-adjudicated-v2';out.mkdir(exist_ok=False)
 for folder in ['bars','signal-bars','rights']:(out/folder).mkdir()
 cov=list(csv.DictReader((src/'coverage.csv').open()));oldse=list(csv.DictReader((src/'source-evidence.csv').open()))
 paths={p.stem:p for b in f.discover_history_batches(q) for p in (b/'history').glob('*.json')}
 requested=set(read(HERE/'plans/bse-unified-index.json')['symbols']);details=[]
 if len(requested)!=200 or len(paths)!=200:raise ValueError('Expected200 unique conflicting BSE stocks')
 for c in cov:
  sid=c['symbol'];native=c['ths_symbol'];old=pd.read_parquet(c['bars_path']);new=old
  changed=sid in requested
  if changed:
   frame,x,cp,item,seen=f.verified_raw_frame(paths[native])
   if cp['history_status']!='complete':raise ValueError('BSE full source incomplete: '+sid)
   frame=frame.loc[frame.trade_date.between('2013-01-01','2026-10-22')]
   new=f.annotate_observations(frame,sid,paths[native].resolve(),seen)
   a=old.set_index('trade_date');b=new.set_index('trade_date');common=a.index.intersection(b.index)
   price_equal=all(np.isclose(a.loc[common,k],b.loc[common,k],rtol=0,atol=1e-6).all() for k in ['open','high','low','close'])
   if not price_equal or not len(common):raise ValueError('Full BSE price overlap failed: '+sid)
   d=dict(symbol=sid,policy='single complete THS OHLCV source; no old/new volume splice',old_raw=ref(c['bars_path']),
    primary_source=ref(paths[native]),overlap_rows=len(common),overlap_OHLC_equal=price_equal,
    old_rows=len(old),new_rows=len(new),old_first=c['first'],old_last=c['last'],
    source_first=str(new.trade_date.iloc[0].date()),source_last=str(new.trade_date.iloc[-1].date()),
    old_V_amount_conflicts_retained_in=str(src/'conflicts.csv'),volume_convention_reason='Observed THS V/amount exceeds old source on some days with equal OHLC; exact trade-type inclusion not certified. Uniform source chosen before outcomes.',
    no_profit_or_algorithm_selection=True)
   details.append(d)
   c.update(first=d['source_first'],last=d['source_last'],rows=len(new),start_status='available_source_start_verified' if d['source_first']>'2013-01-04' else 'reaches_start',
    tail_status='end_reached' if d['source_last']=='2026-10-22' else 'latest_source_bar_before_end_suspension_or_source_limit',
    source_conflict_cells=0,unresolved_source_failures=0,prior_conflict_resolution='uniform_full_THS_OHLCV_price_overlap_verified',price_eligible_rows=int(new.price_eligible.sum()))
  else:
   se=[x for x in oldse if x['symbol']==sid]
   if c['start_status']=='later_first_bar_unconfirmed' and any(x['accepted']=='True' and x['history_status']=='complete' and x['requested_earliest']<='20130101' for x in se):
    c['start_status']='requested_start_covered_first_observation_later_not_listing_claim'
   if sid=='002731.SZ':
    cp=read(HERE/'downloads/supplement-queue-01/batches/03-head-rest-002/checkpoints/USZA002731.json')
    batch=HERE/'downloads/supplement-queue-01/batches/03-head-rest-002'
    rows,seen,attempt=f.verify_attempt(batch,cp['pages'][0],210,native,'9602')
    if rows!=[] or cp['pages'][0]['query']['end']!='20141104' or c['first']!='2014-11-04':raise ValueError('Empty source boundary mismatch')
    c.update(start_status='source_origin_unconfirmed_empty_response_disagrees_with_cached_date',prior_conflict_resolution='empty response at cached origin verified; source identity/boundary unresolved, no OHLC invented; unknown cap retained')
  for folder in ['bars','signal-bars','rights']:
   oldpath=Path(c[{'bars':'bars_path','signal-bars':'signal_bars_path','rights':'rights_path'}[folder]])
   path=out/folder/oldpath.name
   if changed and folder in ('bars','signal-bars'):
    if folder=='bars':new.to_parquet(path,index=False)
    else:new.loc[new.price_eligible].to_parquet(path,index=False)
   else:os.link(oldpath,path)
   key={'bars':'bars','signal-bars':'signal_bars','rights':'rights'}[folder]
   c[key+'_path']=str(path.resolve());c[key+'_sha256']=f.digest(path)
  c.update(complete_actions_certified=False,account_ready=False)
 unresolved=[c for c in cov if c['start_status'] in ('no_bars','later_first_bar_unconfirmed') or c['tail_status'] in ('no_bars','tail_unresolved') or int(c['unresolved_source_failures']) or c['rights_status']!='received_current']
 (out/'master-input.csv').write_bytes((src/'master-input.csv').read_bytes())
 f.write_csv(out/'coverage.csv',cov);f.write_csv(out/'unresolved.csv',unresolved);write(out/'adjudications.json',details)
 summary=dict(recorded_at=now(),raw_roster=len(cov),with_bars=sum(int(c['rows'])>0 for c in cov),rows=sum(int(c['rows']) for c in cov),
  raw_original_summary=ref(src/'summary.json'),original_conflict_cells_retained=2600,source_records_with_conflict=203,unique_conflict_securities=200,
  source_conflicts_resolved_by_uniform_source=len(details),unresolved_securities=len(unresolved),
  start_status_counts=dict(collections.Counter(c['start_status'] for c in cov)),tail_status_counts=dict(collections.Counter(c['tail_status'] for c in cov)),
  rights_status_counts=dict(collections.Counter(c['rights_status'] for c in cov)),data_collection_complete=not unresolved,
  exact_pay_date_ledger_complete=False,account_ready=False,algorithm_changes=0,account_runs=0,
  caveat='Current survivors; current classification. Source boundaries not listing/suspension certificates; BSE actual listing dates handled separately. Source-volume convention chosen, not externally certified equivalent.')
 write(out/'summary.json',summary);write(out/'code-source-manifest.json',{'adjudicator':ref(__file__),'initial_finalizer':ref(OLD/'audit-a/finalize_a.py'),'plans':ref(HERE/'plans/bse-unified-index.json')})
 print(summary,flush=True)

if __name__=='__main__':main()
