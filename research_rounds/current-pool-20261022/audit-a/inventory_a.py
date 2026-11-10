"""Read existing A-share caches only. No imports from online collectors."""
from pathlib import Path
import collections,csv,datetime,hashlib,json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

FORMAL=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
EXTERNAL=Path('/Users/bytedance/repos/my-quant/data/processed')
OUT=Path(__file__).resolve().parent
RAW=EXTERNAL/'daily_bars_history/daily_bars.parquet'
RESEARCH=FORMAL/'TradingAlarm/research'
CACHE=RESEARCH/'data/ths-refresh-20261018'

def write_json(name,obj):
 with (OUT/name).open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def write_csv(name,rows):
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (OUT/name).open('x',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
def identity(p):
 st=p.stat();r={'path':str(p),'bytes':st.st_size,'mtime_ns':st.st_mtime_ns}
 r['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
 return r

pf=pq.ParquetFile(RAW);parts=[];source_counts=collections.Counter();missing=0
for batch in pf.iter_batches(batch_size=500_000,columns=['symbol','trade_date','source']):
 d=batch.to_pandas();missing+=int(d.symbol.isna().sum()+d.trade_date.isna().sum());source_counts.update(d.source.fillna('NULL'))
 p=d.groupby('symbol').trade_date.agg(['min','max','count']).reset_index();parts.append(p)
ranges=pd.concat(parts).groupby('symbol').agg(first=('min','min'),last=('max','max'),rows=('count','sum'))
sec=pd.read_parquet(EXTERNAL/'securities/securities.parquet').set_index('symbol')
checkpoint=json.loads((CACHE/'batch-checkpoint.json').read_text())['records']
files=[];by_symbol={};invalid=[];ths_frames={}
for path in sorted((CACHE/'ths-raw').glob('*.json')):
 try:
  x=json.loads(path.read_text());ths=x['symbol'];market,code=ths[:4],ths[4:]
  if market not in ('USHA','USZA'):continue
  symbol=code+('.SH' if market=='USHA' else '.SZ');bars=x['bars'];dates=[b['date'] for b in bars]
  q=checkpoint.get(symbol,{})
  rec={'symbol':symbol,'ths_symbol':ths,'path':str(path),'first':min(dates) if dates else '',
       'last':max(dates) if dates else '', 'rows':len(bars),'unique_dates':len(set(dates)),
       'status':q.get('status','unlisted'),'fetched_at':x.get('fetched_at'),'overlap_conflicts':len(x.get('overlap_conflicts',[])),
       'rights_path':str(CACHE/'rights'/(ths+'.json')),'rights_exists':(CACHE/'rights'/(ths+'.json')).exists(),
       'raw_semantics':x.get('adjustment'),'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
  files.append(rec);by_symbol[symbol]=rec
  f=pd.DataFrame(bars);f['trade_date']=pd.to_datetime(f.date);ths_frames[symbol]=f.set_index('trade_date')
 except Exception as e:invalid.append({'path':str(path),'error_type':type(e).__name__})
# Read 2026 overlap only. This does not recompute features or query providers.
local=pq.read_table(RAW,columns=['symbol','trade_date','open','high','low','close','volume','amount','source'],
                    filters=[('trade_date','>=',pd.Timestamp('2026-01-01'))]).to_pandas()
local_groups={s:g.set_index('trade_date') for s,g in local.groupby('symbol')}
overlap=[]
for symbol,ths in ths_frames.items():
 old=local_groups.get(symbol)
 if old is None:continue
 common=old.index.intersection(ths.index)
 if not len(common):continue
 a,b=old.loc[common],ths.loc[common]
 price=float((a[['open','high','low','close']]-b[['open','high','low','close']]).abs().max().max())
 valid=(a.volume>0)&(b.volume>0)&(a.amount>0)&(b.amount>0)
 vr=(b.volume[valid]/a.volume[valid]);ar=(b.amount[valid]/a.amount[valid])
 overlap.append({'symbol':symbol,'dates':len(common),'OHLC_max_abs_diff':price,
                 'ths_over_local_volume_median':float(vr.median()) if len(vr) else None,
                 'ths_over_local_volume_min':float(vr.min()) if len(vr) else None,
                 'ths_over_local_volume_max':float(vr.max()) if len(vr) else None,
                 'ths_over_local_amount_median':float(ar.median()) if len(ar) else None,
                 'local_sources':','.join(sorted(a.source.unique())),'old_checkpoint':checkpoint.get(symbol,{}).get('status')})
rows=[]
for symbol in sorted(set(ranges.index)|set(sec.index)|set(checkpoint)):
 r=ranges.loc[symbol] if symbol in ranges.index else None;c=by_symbol.get(symbol);cp=checkpoint.get(symbol,{})
 local_last=str(r['last'].date()) if r is not None else ''
 verified_last=c['last'] if c and cp.get('status')=='signal_window_checked' else ''
 latest=max(local_last,verified_last)
 rows.append({'symbol':symbol,'name':str(sec.loc[symbol,'name']) if symbol in sec.index else '',
              'market':symbol.rsplit('.',1)[-1],'external_rows':int(r.rows) if r is not None else 0,
              'external_first':str(r['first'].date()) if r is not None else '', 'external_last':local_last,
              'external_raw_path':str(RAW) if r is not None else '',
              'ths_status':cp.get('status','not_attempted'), 'ths_symbol':cp.get('ths_symbol') or (c['ths_symbol'] if c else ''),
              'ths_raw_path':c['path'] if c else '', 'ths_first':c['first'] if c else '',
              'ths_last':c['last'] if c else '', 'ths_rows':c['rows'] if c else 0,
              'rights_path':c['rights_path'] if c else '',
              'latest_previously_checked':latest,
              'days_to_20261022':(datetime.date(2026,10,22)-datetime.date.fromisoformat(latest)).days if latest else None,
              'next_task':'resolve_BJ_native_symbol_then_one_recent_page' if symbol.endswith('.BJ') else
                 'one_recent_raw_page_with_overlap' if r is not None else 'resolve_current_symbol_then_bounded_history',
              'current_pool_membership':'not_asserted_join_frozen_20261022_manifest'})
write_csv('security-coverage.csv',rows);write_csv('ths-cache-files.csv',files);write_csv('overlap-unit-check.csv',overlap)
counts=collections.Counter(r['latest_previously_checked'] for r in rows);market_counts=collections.Counter(s.rsplit('.',1)[-1] for s in ranges.index)
summary={'created_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'current-pool cache inventory only; not historical qualification audit','network_requests':0,
         'raw_rows':pf.metadata.num_rows,'raw_symbols':len(ranges),'market_symbols':dict(market_counts),
         'raw_earliest':str(ranges['first'].min().date()),'raw_latest':str(ranges['last'].max().date()),'source_row_counts':dict(source_counts),
         'missing_symbol_or_date_cells':missing,'old_security_snapshot_rows':len(sec),'coverage_union_symbols':len(rows),
         'ths_checkpoint_records':len(checkpoint),'ths_checkpoint_status':dict(collections.Counter(x['status'] for x in checkpoint.values())),
         'ths_raw_files_read':len(files),'ths_rights_files_existing':sum(r['rights_exists'] for r in files),'invalid_cache_files':invalid,
         'previously_checked_latest_distribution':dict(counts),'overlap_symbols':len(overlap),
         'overlap_OHLC_equal_1e6':sum(r['OHLC_max_abs_diff']<=1e-6 for r in overlap),
         'volume_ratio_median_across_symbols':float(np.median([r['ths_over_local_volume_median'] for r in overlap if r['ths_over_local_volume_median'] is not None])),
         'amount_ratio_median_across_symbols':float(np.median([r['ths_over_local_amount_median'] for r in overlap if r['ths_over_local_amount_median'] is not None])),
         'current_20261022_survivor_or_cap_filter_certified':False,'note':'Join today frozen stock/cap/industry snapshot. Old security snapshot alone is not today universe. Calendar days are descriptive, not missing trade days.'}
write_json('summary.json',summary)
sources=[RAW,EXTERNAL/'securities/securities.parquet',EXTERNAL/'adjusted_daily_bars/adjusted_daily_bars.parquet',CACHE/'batch-checkpoint.json',
         RESEARCH/'fetch_history.py',RESEARCH/'fetch_ths_rights.py',RESEARCH/'ths_refresh_batch.py',FORMAL/'TradingAlarm/market.py',FORMAL/'TradingAlarm/search.py',
         Path('/Users/bytedance/repos/my-quant/src/my_quant/data/sources/__init__.py'),Path('/Users/bytedance/repos/my-quant/src/my_quant/data/cleaning.py')]
write_json('source-manifest.json',[identity(p) for p in sources]);print(json.dumps(summary,ensure_ascii=False,indent=2))
