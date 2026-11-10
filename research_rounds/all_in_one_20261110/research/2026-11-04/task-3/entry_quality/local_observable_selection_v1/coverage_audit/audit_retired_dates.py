"""239 original retired JSONs once; fixed-date coverage and exact old-ID join.

No PVR, new score, future return, ranking, refresh or network client imported.
"""
from pathlib import Path
from collections import Counter,defaultdict
from bisect import bisect_left,bisect_right
from datetime import date
import csv,hashlib,json,math,re,time

O=Path(__file__).resolve().parent;E=O.parents[1]
INDEX=E/'local_universe_data_audit_v1/security_master/ALL239_DOWNLOADED_PAYLOAD_EXISTENCE.json'
BAR=E/'local_universe_data_audit_v1/bars/BAR_SYMBOL_COVERAGE.csv'
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
DATES=['2022-01-10','2022-01-24','2024-09-24','2024-10-08','2026-01-15','2026-01-20','2026-05-15']
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def number(v):
 if v is None or isinstance(v,bool):return None
 try:
  f=float(v)
  return f if math.isfinite(f)else None
 except(TypeError,ValueError):return None
def positive(v):f=number(v);return f is not None and f>0
def status(r):
 q={k:number(r.get(k))for k in ['open','high','low','close','volume','amount']}
 decodable=all(v is not None for v in q.values())
 close=positive(r.get('close'));ohlc=all(positive(r.get(k))for k in ['open','high','low','close'])
 if ohlc:ohlc=q['high']>=max(q['open'],q['close'],q['low'])and q['low']<=min(q['open'],q['close'],q['high'])
 volume=positive(r.get('volume'));amount=positive(r.get('amount'))
 return dict(all_six_numeric_finite=decodable,positive_close=close,positive_valid_OHLC=ohlc,positive_volume=volume,positive_amount=amount,
  close_amount_usable=close and amount,OHLCVA_numeric_usable=ohlc and volume and amount,
  invalid_or_undecodable_fields=[k for k,v in q.items()if v is None])

save('FIXED_DATE_SCOPE_BEFORE_PAYLOAD_CENSUS.json',dict(dates=DATES,retired_source='Prior sealed 239 downloaded identity index',separate_from_canonical_ranking=True,
 future_returns=False,PVR_or_ranking=False,no_missing_row_listing_inference=True,
 prior_observation_units='Unique original source dates, not market trading sessions or verified continuous time; exclude duplicates and invalid numeric dates from usable counts'))
bindings={str(INDEX):sha(INDEX.read_bytes()),str(BAR):sha(BAR.read_bytes()),str(OLD):sha(OLD.read_bytes())}
index=json.loads(INDEX.read_text());assert len(index)==239
perday=[];files=[];errors=[];started=time.monotonic()
for record in index:
 p=Path(record['payload_path']);sid=record['symbol']
 try:
  b=p.read_bytes();bindings[str(p)]=sha(b);j=json.loads(b)
  bars=j['bars'];assert isinstance(bars,list)
  bydate=defaultdict(list);invalid_rows=[];raw_order=[];numeric_bad=Counter()
  for n,r in enumerate(bars):
   if not isinstance(r,dict):invalid_rows.append(n);continue
   d=r.get('date')
   try:
    assert isinstance(d,str)and date.fromisoformat(d).isoformat()==d
   except(Exception):invalid_rows.append(n);continue
   z=status(r);bydate[d].append((r,z));raw_order.append(d)
   for k in z['invalid_or_undecodable_fields']:numeric_bad[k]+=1
  days=sorted(bydate);stats=[]
  for d in days:
   r=bydate[d];stats.append(r[0][1]if len(r)==1 else None)
  ca=[0];va=[0]
  for z in stats:
   ca.append(ca[-1]+int(z is not None and z['close_amount_usable']))
   va.append(va[-1]+int(z is not None and z['OHLCVA_numeric_usable']))
  bars_hash=sha(json.dumps(bars,sort_keys=True).encode())
  files.append(dict(symbol=sid,payload_path=str(p),payload_bytes=len(b),raw_rows=len(bars),unique_dates=len(days),
   first_observation=days[0]if days else None,last_observation=days[-1]if days else None,
   invalid_date_or_nondict_rows=len(invalid_rows),duplicate_date_n=sum(len(v)>1 for v in bydate.values()),
   raw_date_order_nondecreasing=raw_order==sorted(raw_order),invalid_numeric_field_counts=dict(numeric_bad),
   source=j.get('source'),source_symbol=j.get('symbol'),fetched_at=j.get('fetched_at'),adjustment=j.get('adjustment'),
   volume_unit=j.get('volume_unit','NOT_STATED_RAW_THS_DO_NOT_MATCH_CANONICAL_UNITS_BY_NAME'),amount_unit=j.get('amount_unit','NOT_STATED_RAW_THS_DO_NOT_MATCH_CANONICAL_UNITS_BY_NAME'),
   page_budget_exhausted=j.get('page_budget_exhausted'),overlap_conflict_count=len(j.get('overlap_conflicts',[])),
   saved_bars_hash=j.get('bars_sha256'),computed_bars_hash=bars_hash,bars_hash_matches=bars_hash==j.get('bars_sha256'),
   old_download_reported_rows=record['download_reported_rows'],old_master_out_date=record['master_out_date'],quality_scope='Numerical/format coverage only, no CA/calendar/execution certification'))
  for day in DATES:
   pos=bisect_left(days,day);through=bisect_right(days,day);matches=bydate.get(day,[])
   row=matches[0][0]if len(matches)==1 else None;z=matches[0][1]if len(matches)==1 else None
   trailing=None
   if z is not None:
    trailing=0;k=pos
    while k>=0 and stats[k]is not None and stats[k]['close_amount_usable']:trailing+=1;k-=1
   day_status='NO_EXACT_SOURCE_ROW'if not matches else'DUPLICATE_EXACT_SOURCE_DATE'if len(matches)>1 else'EXACT_NUMERIC_OHLCVA_USABLE'if z['OHLCVA_numeric_usable']else'EXACT_ROW_NUMERIC_OR_POSITIVITY_UNUSABLE'
   perday.append(dict(symbol=sid,day=day,status=day_status,exact_rows=len(matches),raw_source_values=row,field_status=z,
    past_unique_source_observations_excluding_day=pos,through_day_unique_source_observations=through,
    past_positive_close_amount_observations_excluding_day=ca[pos],through_day_positive_close_amount_observations=ca[through],
    past_numeric_usable_OHLCVA_observations_excluding_day=va[pos],through_day_numeric_usable_OHLCVA_observations=va[through],
    trailing_positive_close_amount_source_rows_ending_exact_day=trailing,
    first_last_not_listing_or_delisting_fact=True,not_in_canonical_ranking=True))
 except Exception as exc:
  errors.append(dict(symbol=sid,payload_path=str(p),error=repr(exc)))
  for day in DATES:perday.append(dict(symbol=sid,day=day,status='PAYLOAD_OR_SCHEMA_UNPARSEABLE',exact_rows=None,not_in_canonical_ranking=True))
assert len(perday)==239*len(DATES)
save('ALL239_PAYLOAD_FORMAT_AND_RANGE.json',files);save('ALL239_SEVEN_DATE_OBSERVATIONS.json',perday);save('ERRORS.json',errors)
summary=[]
for day in DATES:
 rs=[r for r in perday if r['day']==day];present=[r for r in rs if isinstance(r['exact_rows'],int)and r['exact_rows']>0]
 summary.append(dict(day=day,mother=239,status_counts=dict(Counter(r['status']for r in rs)),exact_row_symbols=len(present),
  valid_close_and_amount_n=sum(bool((r.get('field_status')or{}).get('close_amount_usable'))for r in present),
  numerical_OHLCVA_usable_n=sum(bool((r.get('field_status')or{}).get('OHLCVA_numeric_usable'))for r in present),
  absent_is_not_listing_or_delisting_inference=True,
  through_day_positive_close_amount_observations_min=min((r['through_day_positive_close_amount_observations']for r in present if 'through_day_positive_close_amount_observations'in r),default=None),
  through_day_positive_close_amount_observations_median=None if not present else sorted(r['through_day_positive_close_amount_observations']for r in present)[len(present)//2]))

with BAR.open()as f:canonical={r['symbol']:r for r in csv.DictReader(f)}
old=json.loads(OLD.read_text());oldby={r['symbol']:r for r in old};assert len(oldby)==1709 and len(canonical)==5517
canonical_ids=set(canonical);oldids=set(oldby)
membership=[dict(symbol=sid,in_old1709=sid in oldby,old_manifest_status=oldby[sid]['status']if sid in oldby else None,exact_id_only=True)for sid in sorted(canonical_ids)]
save('CANONICAL5517_EXACT_OLD1709_MEMBERSHIP.json',membership)
with (O/'CANONICAL5517_EXACT_OLD1709_MEMBERSHIP.csv').open('w')as f:
 w=csv.DictWriter(f,fieldnames=list(membership[0]));w.writeheader();w.writerows(membership)
missing=[dict(symbol=sid,old_status=oldby[sid]['status'],old_mode=oldby[sid]['mode'],warm_from=oldby[sid]['warm_from'],cache_through=oldby[sid]['cache_through'],alias_status='NO_VERIFIED_ALIAS_USED_ID_ABSENCE_ONLY')for sid in sorted(oldids-canonical_ids)]
save('MISSING_OLD1709_IDS.json',missing)
identity=dict(old1709_count=len(oldids),canonical_count=len(canonical_ids),exact_intersection=len(oldids&canonical_ids),old_not_canonical=len(oldids-canonical_ids),canonical_not_old=len(canonical_ids-oldids),
 old_exchange_counts=dict(Counter(sid[-2:]for sid in oldids)),canonical_exchange_counts=dict(Counter(sid[-2:]for sid in canonical_ids)),
 old_BJ_ids=sorted(sid for sid in oldids if sid.endswith('.BJ')),old_BJ_not_canonical=sorted(sid for sid in oldids-canonical_ids if sid.endswith('.BJ')),
 malformed_old_ids=[sid for sid in oldids if not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)',sid)],
 malformed_canonical_ids=[sid for sid in canonical_ids if not re.fullmatch(r'\d{6}\.(SH|SZ|BJ)',sid)],
 alias_mapping_applied=False,alias_note='Exact .SH/.SZ/.BJ identifiers only. No independently verified date-aware old-code/920xxx issuer alias input; do not force map missing IDs.',
 current100B_scope_evidence=[dict(path='/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/PROTOCOL.md',lines='5,21',fact='Current company market cap > CNY10bn, current2026-10-22 universe/industry; BJ listing/prelisting handling separate'),dict(path='/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/README.md',lines='9,38',fact='Market cap observed2026-10-24;5576raw current universe,1709current cap-qualified,not historical PIT')])
save('OLD1709_EXACT_ID_AUDIT.json',identity)
receipt=dict(status='ONE_READ_239_FIXED_SEVEN_DATE_COVERAGE_COMPLETE',dates=DATES,parsed_payloads=len(files),errors=len(errors),raw_rows_read=sum(r['raw_rows']for r in files),
 bars_hash_matches=sum(r['bars_hash_matches']for r in files),fixed_date_rows=len(perday),daily_summary=summary,old1709_membership=identity,
 elapsed_seconds=time.monotonic()-started,new_network=0,new_refresh=0,new_PVR_or_scores=0,new_rankings=0,new_future_returns=0,new_accounts=0,
 units_or_adjustment_merged_with_canonical=False,source_sha256=bindings)
save('AUDIT_RECEIPT.json',receipt)
print(json.dumps({k:v for k,v in receipt.items()if k not in ['source_sha256','old1709_membership']},ensure_ascii=False))
