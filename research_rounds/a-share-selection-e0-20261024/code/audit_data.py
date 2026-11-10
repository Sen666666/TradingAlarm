"""Independent observation/selection/action coverage audit. No account engine."""
from pathlib import Path
import json,csv,collections,math
import pandas as pd,numpy as np
from build_inputs import HERE,OLD,read,write,ref,now
from current_pool_bridge import sha256

def audit():
 data=HERE/'data-adjudicated-v2';summary=read(data/'summary.json')
 if len(read(HERE/'source-view-v1/sources.json'))!=108:raise ValueError('Source batch count differs')
 cov=list(csv.DictReader((data/'coverage.csv').open()));unresolved=list(csv.DictReader((data/'unresolved.csv').open()))
 out=HERE/'audit/data-independent-v1';out.mkdir(exist_ok=False)
 caproot=HERE/'downloads/current-cap-all';cap=read(caproot/'snapshot.json');seen_attempts={};cap_checked=0
 for row in cap['rows']:
  for kind in ['200','202']:
   obs=row['observations'][kind];ap=caproot/obs['response_attempt']
   if str(ap) not in seen_attempts:
    request=read(ap/'request.json');receipt=read(ap/'receipt.json');decoded=read(ap/'decoded.json')
    assert sha256(ap/'response.bin')==receipt['sha256']==obs['response_sha256']
    assert (ap/'response.bin').stat().st_size==receipt['bytes']
    assert str(request['query']['id'])==kind and request['node']=='9602'
    assert len({x['5'] for x in decoded})==len(decoded)
    seen_attempts[str(ap)]={x['5']:x for x in decoded}
   original=seen_attempts[str(ap)].get(row['symbol'])
   for field in (['10','55'] if kind=='200' else ['2942','1771976','3475914','3541450']):
    if original is None:
     assert obs['returned_symbol_matched'] is False and row['raw_fields'][field] is None
    else:assert row['raw_fields'][field]==original.get(field)
  cap_checked+=1
 write(out/'current-cap-integrity.json',dict(snapshot=ref(caproot/'snapshot.json'),rows_checked=cap_checked,
  response_attempts_hash_checked=len(seen_attempts),field_semantics_source=ref(OLD/'audit-snapshot/REVIEW.md'),
  currency_interpretation='A quote CNY company total-value field3541450; separately observed24, roster22; no historical cap chain claim'))
 prices=[];errors=[]
 for i,c in enumerate(cov):
  p=Path(c['bars_path'])
  if not p.is_file():errors.append({'symbol':c['symbol'],'reason':'no_raw_file'});continue
  f=pd.read_parquet(p);dates=pd.to_datetime(f.trade_date)
  geometry=np.isfinite(f[['open','high','low','close']]).all(axis=1)&f[['open','high','low','close']].gt(0).all(axis=1)&f.high.ge(f[['open','close','low']].max(axis=1))&f.low.le(f[['open','close','high']].min(axis=1))
  checks=dict(raw_hash=sha256(p)==c['bars_sha256'],rights_hash=sha256(c['rights_path'])==c['rights_sha256'],rows=len(f)==int(c['rows']),unique=dates.is_unique,ordered=dates.is_monotonic_increasing,
   first=str(dates.iloc[0].date())==c['first'],last=str(dates.iloc[-1].date())==c['last'],
   mask_equal=bool((geometry.to_numpy()==f.price_eligible.to_numpy()).all()),
   source_end=bool((dates<=pd.Timestamp('2026-10-22')).all()),
   volume_unit=set(f.volume_unit.dropna())=={'shares'},raw_price=set(f.price_adjustment.dropna())=={'raw'})
  if not all(checks.values()):errors.append(dict(symbol=c['symbol'],checks=checks))
  prices.append(dict(symbol=c['symbol'],rows=len(f),valid_price=int(geometry.sum()),positive_volume=int((f.volume>0).sum()),
   missing_volume=int(f.volume.isna().sum()),negative_volume=int((f.volume<0).sum()),first=c['first'],last=c['last']))
  if (i+1)%1000==0:print({'raw_audited':i+1},flush=True)
 write(out/'price-observation-audit.json',prices);write(out/'errors.json',errors)
 selected=read(HERE/'inputs-v1/selection.json')['lines'];selected_ids={x['security_id'] for x in selected if x['company_cap_cny'] is not None}
 selected_unresolved=[c for c in unresolved if c['symbol'] in selected_ids]
 # Empty earlier response is evidence about source boundary, never an OHLC bar.
 empty_cp=HERE/'downloads/supplement-queue-01/batches/03-head-rest-002/checkpoints/USZA002731.json'
 cp=read(empty_cp);attempt=empty_cp.parent.parent/cp['pages'][0]['attempt'];decoded=read(attempt/'decoded.json')
 empty_verified=decoded==[] and cp['pages'][0]['query']['end']=='20141104' and cp['stop_reason']=='empty_raw_page'
 report=dict(recorded_at=now(),raw_roster=len(cov),raw_summary=summary,independent_errors=len(errors),
  qualified=len(selected_ids),qualified_unresolved=selected_unresolved,all_roster_unresolved=unresolved,
  unknown_cap_retained=[x['security_id'] for x in selected if x['company_cap_cny'] is None],
  empty_head_response_adjudication=dict(symbol='002731.SZ',verified=empty_verified,evidence=[ref(empty_cp),ref(attempt/'decoded.json')],
   classification='empty request through cached2014-11-04 origin; source boundary not proven; original quarantine and origin uncertainty retained; current cap unknown prevents strategy admission'),
  no_silent_deletion=True,accounts_run=0,decision='await independent review; this script is not a closeout certificate')
 write(out/'report.json',report)
 print({k:report[k] for k in ['raw_roster','independent_errors','qualified','unknown_cap_retained']},flush=True)
 print('unresolved',len(unresolved),'qualified',len(selected_unresolved),flush=True)

if __name__=='__main__':audit()
