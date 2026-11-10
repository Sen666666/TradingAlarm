"""Freeze all-roster dispositions and explicit common A-only economic inputs.

No account engine import or profit selection. Actual raw closeout is a separate
reviewed step; this script refuses to manufacture it.
"""
from pathlib import Path
import json,csv,collections,datetime,sys
import pandas as pd
from current_pool_bridge import sha256,UPSTREAM
from normalize_actions import normalize

HERE=Path(__file__).resolve().parents[1];OLD=HERE.parent/'current-pool-20261022'
def read(p):return json.loads(Path(p).read_text())
def write(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def ref(p):return {'path':str(Path(p).resolve()),'sha256':sha256(p)}
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()

def build():
 out=HERE/'inputs-v1';out.mkdir(exist_ok=False);(out/'actions').mkdir();(out/'bse-raw').mkdir()
 data=HERE/'data-adjudicated-v2'
 cov={x['symbol']:x for x in csv.DictReader((data/'coverage.csv').open())}
 master=list(csv.DictReader((data/'master-input.csv').open()))
 snap=read(HERE/'downloads/current-cap-all/snapshot.json');caps={x['symbol']:x for x in snap['rows']}
 bse={x['code']:x for x in read(HERE/'audit/bse-listing-facts.json')['rows']}
 lines=[];series=[];dispositions=[];normalization=[];metadata={}
 for r in master:
  sid=r['current_symbol'];q=caps[r['ths_symbol']];rawcap=q['raw_fields'].get('3541450')
  cap=rawcap if isinstance(rawcap,(int,float)) and rawcap>0 else None
  selected=cap is not None and cap>10_000_000_000
  keep=selected or cap is None
  name=q['raw_fields'].get('55') or r['name']
  dispositions.append(dict(symbol=sid,native=r['ths_symbol'],name=name,cap_cny=cap,cap_observed_at=q['observations']['202']['observed_at'],
    industry=r['industry_name'],sector_id=r['industry_index_symbol'],disposition='selected' if selected else 'unknown_cap_retained' if cap is None else 'known_current_cap_not_above_100yi',
    raw_rows=cov[sid]['rows'],raw_sha256=cov[sid]['bars_sha256']))
  if not keep:continue
  c=cov[sid];path=Path(c['bars_path']);raw=pd.read_parquet(path)
  origin=c['first'];end=c['last'];original=ref(path)
  if r['code'] in bse:
   cut=bse[r['code']]['bse_start'];raw=raw.loc[pd.to_datetime(raw.trade_date)>=pd.Timestamp(cut)].copy()
   if raw.empty:raise ValueError('BSE official start has no source observations: '+sid)
   path=out/'bse-raw'/(sid+'.parquet');raw.to_parquet(path,index=False);origin=str(pd.Timestamp(raw.trade_date.iloc[0]).date())
  rights=read(c['rights_path']);events,ignored,unresolved=normalize(rights['records'],rights['source_sha256'],origin,'2026-10-22')
  if unresolved:raise ValueError('Action terms still unresolved: '+sid+' '+str(unresolved))
  action=dict(series_id=sid,currency='CNY',status='declared_research_proxy',coverage_evidence=[ref(c['rights_path'])],events=events,
    ignored_before_origin_or_after_scope=ignored,unresolved=unresolved,raw_response_empty=not rights['records'],
    exact_pay_dates_certified=False,policy='PROTOCOL.md: no subscription; net80% dividends receivable; bonus next session; fraction floor; empty source no-supported-events proxy')
  ap=out/'actions'/(sid+'.json');write(ap,action)
  series.append(dict(series_id=sid,kind='stock',status='ready',currency='CNY',source_start=origin,
    volume_unit='shares',price_adjustment='raw',close_available_time='15:05:00',raw=ref(path),original_full_raw=original,
    source_filter='BSE-only official listing onward; pre-BSE preserved in original_full_raw, not used as signal warmup' if r['code'] in bse else 'all source observations retained',
    adjustment=dict(method='theoretical_ex_price',actions=ref(ap))))
  lines.append(dict(security_id=sid,market='A',issuer_id='issuer:'+r['code'],sector_id=r['industry_index_symbol'] or None,
    company_cap_cny=cap,current_stock=True,southbound_selected=None))
  metadata[sid]=dict(name=name,industry=r['industry_name'],sector_id=r['industry_index_symbol'],code=r['code'],
    par_value='1',par_value_basis='unverified_uniform_research_proxy_pre20150801_only',native=r['ths_symbol'])
  normalization.append(dict(symbol=sid,records=len(rights['records']),events=len(events),ignored=len(ignored),
    empty=not rights['records'],classifications=dict(collections.Counter(e['classification'] for e in events))))
 sec=read(OLD/'sector-trajectories-v1/input-manifest.json')
 sectors=[x for x in sec['series'] if x['series_id'].startswith('URFI')]
 if len(sectors)!=90 or any(x['status']!='ready' for x in sectors):raise ValueError('Expected90 ready A sectors')
 for s in sectors:
  if sha256(s['raw']['path'])!=s['raw']['sha256']:raise ValueError('Changed sector source')
 series.extend(sectors)
 write(out/'roster-dispositions.json',dispositions);write(out/'action-normalization.json',normalization);write(out/'metadata.json',metadata)
 selection=dict(snapshot_id='A-roster-industry22-cap-observed24',observed_at=snap['updated_at'],source_id='THS-current-3541450-company-total-CNY; separate roster22',
  roster_asof='2026-10-22',cap_observed_date='2026-10-24',market_timestamp_unknown=True,lines=lines,
  universe_limit='Current survivors/current cap/current industry historical development, not PIT or out-of-sample',
  all_roster_dispositions=ref(out/'roster-dispositions.json'))
 write(out/'selection.json',selection)
 manifest=dict(schema_version=1,scope_date='2026-10-22',research_basis='current_pool_historical_development',
   upstream_sha256={n:sha256(p) for n,p in UPSTREAM.items()},selection=ref(out/'selection.json'),series=series,
   sector_series={x['series_id']:x['series_id'] for x in sectors})
 # The receipt must be produced after independent all-roster gap review.
 write(out/'manifest-before-closeout.json',manifest)
 write(out/'construction-summary.json',dict(created_at=now(),raw_roster=len(master),selected=sum(x['company_cap_cny'] is not None for x in lines),
  unknown_cap=sum(x['company_cap_cny'] is None for x in lines),stocks_retained=len(lines),sectors=len(sectors),
  normalization_classifications=dict(sum((collections.Counter(x['classifications']) for x in normalization),collections.Counter())),accounts_run=0))
 print(read(out/'construction-summary.json'),flush=True)

if __name__=='__main__':build()
