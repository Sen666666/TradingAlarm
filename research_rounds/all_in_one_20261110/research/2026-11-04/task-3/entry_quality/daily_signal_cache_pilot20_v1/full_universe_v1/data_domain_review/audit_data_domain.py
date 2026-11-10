"""One bounded streamed data-domain audit; no signal/model/account imports."""
from pathlib import Path
from collections import Counter
import hashlib,json,time,sys,resource
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[2]
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
ROSTER=ENTRY/'full_local_signal_20240924_v1/signals/UNIVERSE5517.csv'
ORIGINAL=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/data_utils.py')
CHECKS=['2022-01-24','2024-09-24','2026-01-15'];STAMPS={d:pd.Timestamp(d).value for d in CHECKS}
START=pd.Timestamp('2022-01-01').value;NAT=np.iinfo(np.int64).min
BATCH=131072

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(n,v):(HERE/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def day(v):return None if v is None else str(pd.Timestamp(v,unit='ns').date())

def main():
 assert not(HERE/'SEAL.json').exists()
 started=time.monotonic();source_sha=sha(SOURCE)
 assert source_sha=='11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b'
 source_stat=SOURCE.stat();pf=pq.ParquetFile(SOURCE);schema=set(pf.schema_arrow.names)
 flags=[x for x in ['observed_bar','synthetic_event_bar','source_invalid','source_anomaly','price_eligible','is_observed_bar']if x in schema]
 cols=['symbol','trade_date','open','high','low','close','volume','amount','source']+flags
 roster=set(pd.read_csv(ROSTER).sid);assert len(roster)==5517
 stats={};global_counts=Counter();date_union=set();batches=0
 for batch in pf.iter_batches(batch_size=BATCH,columns=cols):
  batches+=1;f=batch.to_pandas();n=len(f);dates=pd.to_datetime(f.trade_date).to_numpy(dtype='datetime64[ns]').view('i8')
  numeric={k:pd.to_numeric(f[k],errors='coerce').to_numpy(float)for k in ['open','high','low','close','volume','amount']}
  o,h,l,c=[numeric[k]for k in ['open','high','low','close']];v=numeric['volume'];a=numeric['amount']
  positive=np.isfinite(o)&np.isfinite(h)&np.isfinite(l)&np.isfinite(c)&(o>0)&(h>0)&(l>0)&(c>0)
  geometry=(h>=l)&(h>=o)&(h>=c)&(l<=o)&(l<=c)
  price=positive&geometry
  def flag(name,default):
   return f[name].astype(str).str.lower().isin(['true','1','1.0']).to_numpy()if name in f else np.full(n,default,dtype=bool)
  price&=flag('observed_bar',True)&~flag('synthetic_event_bar',False)&~flag('source_invalid',False)
  if'source_anomaly'in f:price&=~f.source_anomaly.fillna('').astype(str).str.strip().ne('').to_numpy()
  vgood=np.isfinite(v)&(v>0);agood=np.isfinite(a)&(a>0)
  pvr=np.isfinite(c)&(c>0)&agood
  for key in ['price_eligible','observed_bar','is_observed_bar']:
   if key in f:pvr&=f[key].fillna(False).astype(bool).to_numpy()
  for key in ['source_invalid','synthetic_event_bar']:
   if key in f:pvr&=~f[key].fillna(True).astype(bool).to_numpy()
  after=(dates>=START)&(dates!=NAT);date_union.update(np.unique(dates[after]).tolist())
  masks=dict(raw_rows=np.ones(n,dtype=bool),raw_rows_2022_onward=after,
    OHLC_nonfinite_or_nonpositive=~positive,OHLC_geometry_invalid=~geometry,
    original_price_mask_rejected=~price,original_price_valid=price,original_price_valid_2022_onward=price&after,
    volume_nonpositive_or_nonfinite=~vgood,price_valid_but_volume_invalid=price&~vgood,
    amount_nonpositive_or_nonfinite=~agood,price_valid_but_amount_invalid=price&~agood,
    PVR_own_valid=pvr,PVR_own_valid_2022_onward=pvr&after,
    PVR_valid_but_original_price_invalid=pvr&~price,price_valid_but_PVR_invalid=price&~pvr,
    invalid_date=dates==NAT)
  for k,m in masks.items():global_counts[k]+=int(m.sum())
  for sid,idx in f.groupby('symbol',sort=False,dropna=False).indices.items():
   sid=str(sid);d=dates[idx];pv=price[idx]
   if sid not in stats:
    stats[sid]=dict(sid=sid,_dates=[],_price=[],sources=set(),source_null_rows=0,source_unknown_rows=0,
      first_bad_CP_amount_ns=None,nonincreasing_physical_rows=0,last_physical_ns=None,
      checks={x:dict(raw=False,price=False,pvr=False)for x in CHECKS},counts=Counter())
   s=stats[sid];s['_dates'].append(d.copy());s['_price'].append(pv.copy())
   good_dates=d[d!=NAT]
   if len(good_dates):
    s['nonincreasing_physical_rows']+=int((np.diff(good_dates)<=0).sum())
    if s['last_physical_ns']is not None:s['nonincreasing_physical_rows']+=int(good_dates[0]<=s['last_physical_ns'])
    s['last_physical_ns']=int(good_dates[-1])
   bad=d[pv&~agood[idx]&(d!=NAT)]
   if len(bad):s['first_bad_CP_amount_ns']=int(bad.min())if s['first_bad_CP_amount_ns']is None else min(s['first_bad_CP_amount_ns'],int(bad.min()))
   source_values=f.source.iloc[idx]
   s['source_null_rows']+=int(source_values.isna().sum())
   for value in source_values.unique():
    if pd.isna(value):s['sources'].add('__NULL__');continue
    text=str(value);s['sources'].add(text)
   unknown=source_values.isna()|source_values.fillna('').astype(str).str.strip().str.lower().isin(['','unknown','none','null','nan','na','<na>'])
   s['source_unknown_rows']+=int(unknown.sum())
   for k,m in masks.items():s['counts'][k]+=int(m[idx].sum())
   for check,stamp in STAMPS.items():
    at=d==stamp;s['checks'][check]['raw']|=bool(at.any());s['checks'][check]['price']|=bool((at&pv).any());s['checks'][check]['pvr']|=bool((at&pvr[idx]).any())
 save('STREAM_PASS_COMPLETE.json',dict(rows=int(global_counts['raw_rows']),batches=batches,symbols=len(stats),source_sha256=source_sha))
 output=[];dups=[];missing={d:[]for d in CHECKS};coverage=[]
 for sid,s in sorted(stats.items()):
  d=np.concatenate(s.pop('_dates'));pv=np.concatenate(s.pop('_price'));valid_dates=d[d!=NAT]
  unique,cnt=np.unique(valid_dates,return_counts=True);dup=int((cnt-1).sum())
  if dup:dups.append(dict(sid=sid,duplicate_extra_rows=dup,dates=[day(int(x))for x in unique[cnt>1]]))
  bad=s['first_bad_CP_amount_ns'];blocked=np.zeros(len(d),dtype=bool)if bad is None else pv&(d>=bad)
  providers=sorted(s['sources']);c=dict(s['counts'])
  r=dict(sid=sid,**c,source_first_observation_day=day(int(unique.min()))if len(unique)else None,
    source_last_observation_day=day(int(unique.max()))if len(unique)else None,
    unique_source_dates=len(unique),duplicate_symbol_date_extra_rows=dup,
    nonincreasing_physical_rows=s['nonincreasing_physical_rows'],source_values='|'.join(providers),source_value_count=len(providers),
    source_null_rows=s['source_null_rows'],source_unknown_rows=s['source_unknown_rows'],
    first_bad_CP_amount_on_original_price_clock=day(bad),
    CP_price_rows_strictly_before_first_bad=int((pv&~blocked).sum()),CP_price_rows_at_or_after_first_bad=int(blocked.sum()),
    CP_price_rows_2022_at_or_after_first_bad=int((blocked&(d>=START)).sum()),
    historical_listing_identity='UNKNOWN',source_first_not_certified_listing_date=True,
    source_last_not_certified_delisting_date=True,full_listing_history_certified=False)
  for check in CHECKS:
   for typ in ['raw','price','pvr']:r[f'{check}_{typ}_present']=s['checks'][check][typ]
   if not s['checks'][check]['raw']:missing[check].append(sid)
  output.append(r)
 table=pd.DataFrame(output);table.to_csv(HERE/'SYMBOL_DATA_DOMAINS.csv',index=False)
 table.to_parquet(HERE/'SYMBOL_DATA_DOMAINS.parquet',index=False)
 for check in CHECKS:
  stamp=STAMPS[check]
  coverage.append(dict(day=check,source_symbols_present=int(table[f'{check}_raw_present'].sum()),
      missing_symbols=len(missing[check]),price_mask_valid_symbols=int(table[f'{check}_price_present'].sum()),
      PVR_own_valid_symbols=int(table[f'{check}_pvr_present'].sum()),
      CP_amount_domain_blocked_price_symbols=sum(bool(s['checks'][check]['price'])and s['first_bad_CP_amount_ns']is not None and s['first_bad_CP_amount_ns']<=stamp for s in stats.values())))
 pd.DataFrame(coverage).to_csv(HERE/'THREE_DATE_COVERAGE.csv',index=False);save('THREE_DATE_MISSING_IDS.json',missing);save('DUPLICATE_KEYS.json',dups)
 rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss;rss_bytes=int(rss if sys.platform=='darwin'else rss*1024)
 current=SOURCE.stat();assert current.st_size==source_stat.st_size and current.st_mtime_ns==source_stat.st_mtime_ns
 summary=dict(status='COMPLETE_READ_ONLY_STREAMED_DATA_DOMAIN_AUDIT',source_path=str(SOURCE),source_sha256=source_sha,
    source_rows=pf.metadata.num_rows,scanned_rows=int(global_counts['raw_rows']),symbols=len(stats),
    source_IDs_exactly_match_fixed5517=set(stats)==roster,unexpected_IDs=sorted(set(stats)-roster),missing_roster_IDs=sorted(roster-set(stats)),
    duplicate_symbol_date_extra_rows=int(table.duplicate_symbol_date_extra_rows.sum()),
    symbols_with_nonincreasing_physical_order=int(table.nonincreasing_physical_rows.gt(0).sum()),
    single_nonnull_known_source_symbols=int((table.source_value_count.eq(1)&table.source_unknown_rows.eq(0)).sum()),
    multi_source_symbols=table.loc[table.source_value_count.gt(1),'sid'].tolist(),unknown_source_symbols=table.loc[table.source_unknown_rows.gt(0),'sid'].tolist(),
    original_mask_source_path=str(ORIGINAL),original_mask_source_sha256=sha(ORIGINAL),optional_mask_fields_present=flags,
    original_optional_mask_defaults='observed_bar=True; synthetic_event_bar/source_invalid=False; source_anomaly absent; exclude_dates=()',
    row_counts=dict(global_counts),source_date_union_2022_rows=len(date_union),source_date_union_first=day(min(date_union)),source_date_union_last=day(max(date_union)),
    source_union_not_official_calendar=True,
    CP_first_bad_amount_symbols=int(table.first_bad_CP_amount_on_original_price_clock.notna().sum()),
    CP_domain_blocked_price_rows=int(table.CP_price_rows_at_or_after_first_bad.sum()),CP_domain_blocked_price_rows_2022=int(table.CP_price_rows_2022_at_or_after_first_bad.sum()),
    CP_domain_rule='first bad amount on original eligible-price clock blocks that row and subsequent CP within this source history; prior valid prefix retained; no fill/drop/restart or E0/PVR clock change',
    source_first_last_are_observations_not_listing_delisting=True,full_listing_history_certified=False,historical_listing_identity_all_unknown=True,
    three_date_coverage=coverage,batch_size=BATCH,batches=batches,
    auxiliary_date_plus_price_mask_raw_bytes=pf.metadata.num_rows*9,peak_self_RSS_bytes=rss_bytes,
    elapsed_seconds=time.monotonic()-started,one_source_rows_pass=True,source_bytes_hash_pass_separate=True,
    source_size_mtime_unchanged=True,new_models=0,new_accounts=0,source_rewrites=0)
 save('DATA_DOMAIN_SUMMARY.json',summary)
 print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
