"""Only four saved semiconductor source tables; no stock reads or feature/model execution."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
PREFIX='SUPPLEMENT_2025NOV28_SEMI_E0_ANCHOR_21'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
CAL=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
SOURCES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p,expected=None):
 p=Path(p).resolve();h=sha(p)
 if expected is not None:assert h==expected,(str(p),'SHA mismatch')
 SOURCES[str(p)]=h;return p
def clean(x):
 if x is None or x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v)for v in x]
 if isinstance(x,pd.Timestamp):return str(x.date())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float)and not np.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

before={str(p.resolve()):sha(p)for p in [O/'ORIGINAL_INDUSTRY_E0_CP_EVENT_PATHS.parquet',O/'ORIGINAL_INDUSTRY_E0_CP_EVENT_PATHS.csv',O/'STATIC_MEMBERS_ORIGINAL_STOCK_FACTS.parquet',O/'ORIGINAL_STOCK_FACTS_SECTOR_AGGREGATES.parquet']}
bind(__file__)
im=json.loads(bind(U/'INDUSTRY_MANIFEST.json').read_text());r=next(x for x in im if x['series']=='URFI881121')
paths={'native_E0':next(p for p in r['source_sha256']if '/industry-facts/'in p),'upstream_events':next(p for p in r['source_sha256']if p.endswith('/events.parquet')),'CP':r['refs']['CP1'],'market_state':r['refs']['state']}
tables={};schemas={}
cpcols=['ready','phase','reset_reason','anchor','frontier','scale','credit','delta_frontier','displacement','receipt','candidate','next_anchor','next_scale','next_credit','next_phase','r','s','z','e0_valid','e0_floor']
for role,p in paths.items():
 expected=r['source_sha256'].get(p,r['output_sha256'].get(p));bind(p,expected)
 f=pd.read_parquet(p,columns=cpcols if role=='CP'else None);schemas[role]=list(f.columns)
 if role=='market_state':f=f.set_index(pd.to_datetime(f.day))
 f.index=pd.DatetimeIndex(f.index).as_unit('ns');assert f.index.is_unique and f.index.is_monotonic_increasing
 tables[role]=f
cal=pd.DatetimeIndex(pd.read_csv(bind(CAL),usecols=['date']).date);p=cal.get_loc(pd.Timestamp('2025-11-28'));dates=cal[p-5:p+16];assert len(dates)==21
rows=[]
for i,t in enumerate(dates):
 row=dict(case_id='2025NOV28_SEMI_E0_ANCHOR',case_role='SOURCE_DRIVEN_SUPPLEMENT',anchor_date='2025-11-28',date=str(t.date()),relative_session=i-5,sector_id_static='URFI881121',industry_static='半导体',registered_after_original_E0_anchor_observed=True,original_168_rows_replaced=False,industry_I_permission='N/A_NOT_USED_BY_NO60',market_authorization_is_financial_permission=False,membership_PIT_verified=False)
 for role,f in tables.items():
  assert t in f.index,(role,str(t.date()),'missing exact observation')
  x=f.loc[t];row[role+'_source_date']=str(t.date());row[role+'_exact_date']=True;row[role+'_source_ref']=paths[role]
  for k,v in x.items():row[role+'__'+k]=clean(v)
 ev=tables['upstream_events'];known=ev.loc[(ev.index<=t)&ev.segment_id.eq(row['upstream_events__segment_id'])]
 for label,sign in [('low',1),('high',-1)]:
  g=known.loc[known.event.eq(sign)&known.confirmed_pivot_price.notna()]
  if len(g):
   x=g.iloc[-1];row['last_confirmed_'+label+'_confirmation_date']=str(g.index[-1].date());row['last_confirmed_'+label+'_pivot_date']=clean(x.confirmed_pivot_date);row['last_confirmed_'+label+'_price_a']=clean(x.confirmed_pivot_price);row['last_confirmed_'+label+'_raw_at_current_factor']=float(x.confirmed_pivot_price)/row['native_E0__factor'];row['last_confirmed_'+label+'_provider_event_id']='NOT_SAVED'
 row['CP_frontier_coordinate']='natural_log_price_NOT_E0_confirmed_high';rows.append(row)
f=pd.DataFrame(rows);f.to_parquet(O/(PREFIX+'.parquet'),index=False);f.to_csv(O/(PREFIX+'.csv'),index=False)
anchor=f.loc[f.relative_session.eq(0)].iloc[0]
checks={'rows_21':len(f)==21,'unique_dates_21':f.date.nunique()==21,'native_target_equals_market_state':f.native_E0__e0_target.astype(bool).eq(f.market_state__E0_valid.astype(bool)).all().item(),'CP_receipt_equals_market_state':f.CP__receipt.astype(bool).eq(f.market_state__receipt.astype(bool)).all().item(),'anchor_confirms_low':anchor.upstream_events__event==1,'anchor_pivot_2025_11_21':anchor.upstream_events__confirmed_pivot_date=='2025-11-21','native_asof_exact_all':f.native_E0_exact_date.all().item(),'financial_state_owned_false_all':f.market_state__financial_state_owned.eq(False).all().item(),'main168_and_stock_artifacts_unchanged':all(sha(p)==h for p,h in before.items())}
for label in ['low','high']:checks[label+'_confirmation_not_future']=f['last_confirmed_'+label+'_confirmation_date'].le(f.date).all().item()
assert all(checks.values()),checks
save(PREFIX+'_SUMMARY.json',dict(status='COMPLETE_SOURCE_ONLY_SUPPLEMENT',rows=21,first=f.date.min(),last=f.date.max(),anchor_original_fields=anchor.to_dict(),checks=checks,industry_source_tables=4,stock_source_reads=0,stock_aggregates=0,amount_calculations=0,new_models=0,new_accounts=0,main_artifacts_before_and_after_SHA=before,scope='Registered after reading original E0 date; not blind, not replacing Jan5/924, not an asserted optimal trend beginning.',coordinate_notes='Original source index is confirmation-known date; confirmed_pivot_date is historical pivot location. Existing CP anchor/frontier are log-price coordinates.',schemas=schemas))
save(PREFIX+'_SOURCE_SHA256.json',SOURCES)
save(PREFIX+'_OUTPUT_SHA256.json',{str(p.resolve()):sha(p)for p in O.glob(PREFIX+'*')if p.is_file()and not p.name.endswith('_OUTPUT_SHA256.json')})
print(f[['date','relative_session','native_E0__e0_target','native_E0__e0_floor','upstream_events__event','upstream_events__confirmed_pivot_date','CP__receipt','market_state__stage_name','market_state__authorization_usable']].to_string(index=False))
print('PASS',json.dumps(clean(checks)),flush=True)
