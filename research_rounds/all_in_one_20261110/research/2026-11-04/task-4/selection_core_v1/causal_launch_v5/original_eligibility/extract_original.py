"""Read frozen source tables only. No native imports, signals, accounts or models."""
from pathlib import Path
import hashlib,json,time
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent
ROOT=O.parents[1]
R=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
U=R/'universe-cp1-inputs-20261031'
META=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
RT=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
MARKET=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
SHA={};SCHEMAS={}
def bind(p,expected=None):
 p=Path(p).resolve();h=hashlib.sha256(p.read_bytes()).hexdigest()
 if expected is not None:assert h==expected,(str(p),'source SHA mismatch')
 SHA[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())
def pq(p,expected=None):
 p=bind(p,expected);f=pd.read_parquet(p);SCHEMAS[str(p)]=list(f.columns)
 if 'day' in f and not isinstance(f.index,pd.DatetimeIndex):f=f.set_index(pd.to_datetime(f.day))
 f.index=pd.DatetimeIndex(f.index).as_unit('ns');assert f.index.is_unique and f.index.is_monotonic_increasing
 return f
def clean(x):
 if x is None or x is pd.NA or x is pd.NaT:return None
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v)for v in x]
 if isinstance(x,pd.Timestamp):return str(x.date())
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float)and not np.isfinite(x):return None
 return x
def save(name,x):(O/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def emit(name,rows):
 f=pd.DataFrame(rows);f.to_parquet(O/(name+'.parquet'),index=False);f.to_csv(O/(name+'.csv'),index=False);return f
def asof(f,t):
 i=f.index.searchsorted(t,side='right')-1
 return (None,None)if i<0 else(f.index[i],f.iloc[i])
def prefixed(row,prefix,dst):
 if row is not None:
  for k,v in row.items():dst[prefix+k]=clean(v)
def bool_value(row,k):
 return None if row is None or k not in row or pd.isna(row[k])else bool(row[k])

def main():
 begun=time.monotonic();bind(__file__);bind(O.parent/'EXTRACTION_CONTRACT.txt')
 im={r['series']:r for r in read(U/'INDUSTRY_MANIFEST.json')};sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')};meta=read(META)
 f=pq(O.parent/'feature_paths/EXISTING_FEATURE_PATHS.parquet')
 keycols=['case_id','case_role','date','relative_session','sector_id_static']
 keys=f[keycols].copy();assert len(keys)==105
 cal=pd.DatetimeIndex(pd.read_csv(bind(MARKET),usecols=['date']).date)
 assert cal.is_unique and cal.is_monotonic_increasing
 counter=pq(O.parent/'feature_paths/COUNTEREXAMPLE_EXISTING_FEATURE_PATHS.parquet')[keycols]
 assert len(counter)==63
 keys=pd.concat([keys,counter],ignore_index=True)
 for case,g in keys.groupby('case_id'):
  anchor=pd.Timestamp(g.loc[g.relative_session.eq(0),'date'].iloc[0]);p=cal.get_loc(anchor)
  assert g.sort_values('relative_session').date.tolist()==[str(d.date())for d in cal[p-5:p+16]],case
 keys['anchor_date']=keys.groupby('case_id').date.transform(lambda s:keys.loc[s.index].loc[keys.loc[s.index].relative_session.eq(0),'date'].iloc[0])
 keys['industry_static']=keys.sector_id_static.map({v['sector_id']:v['industry']for v in meta.values()})
 keys.to_csv(O/'FIXED_KEYS.csv',index=False)
 ind=[];alternate=[];source_rows=[];missing=[]
 for sec,g in keys.groupby('sector_id_static',sort=True):
  r=im[sec];source={};tables={}
  for kind,token in [('native_E0','/industry-facts/'),('upstream_events','/events.parquet'),('upstream_states','/states.parquet'),('upstream_signal','/signal.parquet')]:
   ps=[p for p in r['source_sha256']if token in p];assert len(ps)==1
   source[kind]=ps[0];tables[kind]=pq(ps[0],r['source_sha256'][ps[0]])
  for kind,ref in [('CP_input','CP1_input'),('CP','CP1'),('market_state','state')]:
   p=r['refs'][ref];source[kind]=p;tables[kind]=pq(p,r['output_sha256'][p])
  source['ALT_RUNTIME_I_NOT_CONSUMED']=str(RT/'facts'/f'{sec}.parquet')
  alt=pq(source['ALT_RUNTIME_I_NOT_CONSUMED'])if Path(source['ALT_RUNTIME_I_NOT_CONSUMED']).exists()else pd.DataFrame(index=pd.DatetimeIndex([]))
  for k,p in source.items():source_rows.append(dict(sector_id_static=sec,source_role=k,path=p,exists=Path(p).exists(),sha256=SHA.get(p),schema=SCHEMAS.get(p),consumed_for_native_industry_I=False))
  for key in g.to_dict('records'):
   t=pd.Timestamp(key['date']);row=dict(key,industry_I_permission='N/A_NOT_USED_BY_NO60',market_authorization_is_financial_permission=False,membership_PIT_verified=False)
   for kind in tables:
    table=tables[kind];exact=t in table.index
    # Persistent native target is read as-of, like Facts.row. Fresh CP/state never forward-fill.
    d,x=asof(table,t)if kind=='native_E0'else(t,table.loc[t])if exact else(None,None)
    row[kind+'_source_date']=clean(d);row[kind+'_exact_date']=exact;row[kind+'_source_ref']=source[kind]
    prefixed(x,kind+'__',row)
    if x is None:missing.append(dict(case_id=key['case_id'],date=key['date'],sector_id_static=sec,table=kind,status='NO_EXACT_OBSERVATION'if kind!='native_E0'else'NO_PRIOR_OBSERVATION'))
   factor=row.get('native_E0__factor');seg=row.get('upstream_events__segment_id')
   ev=tables['upstream_events'];known=ev.loc[ev.index<=t]
   if seg is not None:known=known.loc[known.segment_id.eq(seg)]
   for label,sign in [('low',1),('high',-1)]:
    events=known.loc[known.event.eq(sign)&known.confirmed_pivot_price.notna()]
    if len(events):
     d=events.index[-1];x=events.iloc[-1]
     row['last_confirmed_'+label+'_confirmation_date']=clean(d)
     row['last_confirmed_'+label+'_pivot_date']=clean(x.confirmed_pivot_date)
     row['last_confirmed_'+label+'_price_a']=clean(x.confirmed_pivot_price)
     row['last_confirmed_'+label+'_raw_at_current_factor']=float(x.confirmed_pivot_price)/factor if factor and np.isfinite(factor)else None
     row['last_confirmed_'+label+'_source_segment']=clean(x.segment_id)
     row['last_confirmed_'+label+'_provider_event_id']='NOT_SAVED'
   row['native_industry_structural_high']='NOT_SAVED_IN_NATIVE_FACTS'
   row['CP_frontier_coordinate']='natural_log_price_NOT_E0_confirmed_high'
   row['CP_input_i_floor_semantics']='ALIAS_NATIVE_E0_FLOOR_NOT_INDUSTRY_I'
   ind.append(row)
   d,x=asof(alt,t);a=dict(key,status='ALT_RUNTIME_I_NOT_CONSUMED',used_as_No60_industry_permission=False,source_exists=Path(source['ALT_RUNTIME_I_NOT_CONSUMED']).exists(),source_ref=source['ALT_RUNTIME_I_NOT_CONSUMED'],source_date=clean(d),exact_date=t in alt.index)
   for k in ['i_target','i_floor','g_grade','g_ready','e0_ready','e0_target','e0_floor','close','segment_id','factor','raw_close']:a[k]=clean(x[k])if x is not None and k in x else None
   for k in ['g_fresh_up','g_acute_down']:
    a[k+'_asof_raw']=bool_value(x,k);a[k]=bool_value(alt.loc[t],k)if t in alt.index else None
   a['i_buy_exact_field']=clean(alt.at[t,'i_buy'])if t in alt.index and 'i_buy'in alt else None
   a['i_entered']='NOT_SAVED';alternate.append(a)
 indf=emit('ORIGINAL_INDUSTRY_E0_CP_EVENT_PATHS',ind);emit('ALT_RUNTIME_I_G1_NOT_CONSUMED',alternate)
 # Facts-only stock aggregates. These are not complete S0 Q or financial permission.
 stocks=[]
 for sec,g in keys.groupby('sector_id_static',sort=True):
  members=[sid for sid in sm if meta[sid]['sector_id']==sec]
  for sid in members:
   r=sm[sid];p=r['refs']['facts'];f=pq(p,r['output_sha256'][p]);
   for key in g.to_dict('records'):
    t=pd.Timestamp(key['date']);d,x=asof(f,t);exact=t in f.index
    row=dict(key,sid=sid,name=meta[sid]['name'],source_ref=p,source_date=clean(d),exact_date=exact,asof_stale_sessions=int(((cal>d)&(cal<=t)).sum())if d is not None else None,membership_PIT_verified=False)
    for k in ['e0_ready','e0_target','i_target','g_ready']:row[k]=bool_value(x,k)
    for k in ['close','segment_id','e0_floor','i_floor','factor','g_grade']:row[k]=clean(x[k])if x is not None and k in x else None
    today=f.loc[t]if exact else None
    for k in ['g_fresh_up','g_acute_down']:
     row[k+'_asof_raw']=bool_value(x,k);row[k]=bool_value(today,k)
    row['i_buy_exact_field']=bool_value(today,'i_buy')
    row['i_buy_original_daily_event']=bool_value(today,'i_buy')if exact else False
    stocks.append(row)
 stockf=emit('STATIC_MEMBERS_ORIGINAL_STOCK_FACTS',stocks)
 # Copy U denominator already computed by frozen feature line; do not recalculate U.
 opp=pq(ROOT/'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet').set_index(['date','sector_id_static'])
 agg=[]
 measures=['e0_ready','e0_target','i_target','i_buy_exact_field','i_buy_original_daily_event','g_ready','g_fresh_up','g_acute_down']
 for (case,day),g in stockf.groupby(['case_id','date'],sort=False):
  k=g.iloc[0];row={c:clean(k[c])for c in keycols+['anchor_date','industry_static']};row.update(whole_static_sector_N=len(g),facts_asof_known_N=int(g.source_date.notna().sum()),facts_exact_date_N=int(g.exact_date.sum()),facts_stale_date_N=int((g.source_date.notna()&~g.exact_date).sum()),facts_asof_source_date_counts=json.dumps(g.source_date.fillna('NO_PRIOR').value_counts().to_dict(),sort_keys=True),facts_only_not_full_S0_Q=True)
  for m in measures:
   row[m+'_known_N']=int(g[m].notna().sum());row[m+'_true_N']=int(g[m].eq(True).sum());row[m+'_false_N']=int(g[m].eq(False).sum());row[m+'_unknown_N']=int(g[m].isna().sum())
  pair=(day,k.sector_id_static);x=opp.loc[pair]if pair in opp.index else None
  row['U_N_from_saved_industry_aggregate']=int(x.N_U_t)if x is not None else None
  row['U_inside_original_E0_I_counts_status']='UNKNOWN_NO_FULL_WINDOW_STOCK_U_MASK_SAVED'
  for m in measures:
   for n in ['known_N','true_N','false_N','unknown_N']:row['U_'+m+'_'+n]=None
  agg.append(row)
 aggf=emit('ORIGINAL_STOCK_FACTS_SECTOR_AGGREGATES',agg)
 emit('ANCHOR_ORIGINAL_INDUSTRY_ROWS',indf.loc[indf.relative_session.eq(0)].to_dict('records'))
 emit('ANCHOR_ORIGINAL_STOCK_AGGREGATES',aggf.loc[aggf.relative_session.eq(0)].to_dict('records'))
 save('SOURCE_SCHEMAS_AND_ROLES.json',source_rows);save('MISSING_OBSERVATIONS.json',missing)
 save('SUMMARY.json',dict(status='COMPLETE_SOURCE_EXTRACTION',industry_rows=len(indf),main_rows=int(indf.case_role.eq('MAIN').sum()),aux_rows=int(indf.case_role.eq('AUX').sum()),counterexample_rows=int(indf.case_role.eq('COUNTEREXAMPLE').sum()),case_roles=indf.case_role.value_counts().to_dict(),stock_fact_rows=len(stockf),unique_stocks=stockf.sid.nunique(),sectors=stockf.groupby('sector_id_static').sid.nunique().to_dict(),missing_industry_observations=len(missing),all_industry_native_exact=bool(indf.native_E0_exact_date.all()),industry_I_permission='N/A_NOT_USED_BY_NO60',runtime_I='ALT_RUNTIME_I_NOT_CONSUMED',U_inside_qualification_counts='UNKNOWN_PENDING_EXISTING_OR_SAME_PASS_U_MASK',new_models=0,new_accounts=0,source_only=True,seconds=time.monotonic()-begun))
 save('SOURCE_SCHEMAS.json',SCHEMAS);save('SOURCE_SHA256.json',SHA)
 save('OUTPUT_SHA256.json',{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest()for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_SHA256.json'})
 print(json.dumps(clean(read(O/'SUMMARY.json')),ensure_ascii=False),flush=True)
 show=['case_id','date','native_E0__e0_target','native_E0__e0_floor','CP__receipt','market_state__E0_episode','market_state__stage_name','market_state__authorization_usable']
 print(indf.loc[indf.relative_session.eq(0),show].to_string(index=False),flush=True)
 print(aggf.loc[aggf.relative_session.eq(0),['case_id','whole_static_sector_N','e0_target_true_N','i_target_true_N','i_buy_exact_field_true_N','U_N_from_saved_industry_aggregate']].to_string(index=False),flush=True)

if __name__=='__main__':main()
