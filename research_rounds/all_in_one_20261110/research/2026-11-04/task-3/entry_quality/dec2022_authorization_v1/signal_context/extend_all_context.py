"""Extend the same frozen diagnostic, not a new permission/filter pipeline."""
from pathlib import Path
from collections import Counter,defaultdict
import copy,csv,gzip,json,hashlib,time
import numpy as np,pandas as pd

O=Path(__file__).resolve().parent
# Reuse the completed118 reader/input identities, not its output-writing block.
original=O/'inspect_context.py';prefix=original.read_text().split('\nmother=read(')[0]
env={'__file__':str(original)};exec(compile(prefix,str(original),'exec'),env)
read,frame,save,stock,industry,market,provider,SRC=[env[k] for k in ('read','frame','save','stock','industry','market','provider','SRC')]
EQ,R,W,im,meta=[env[k] for k in ('EQ','R','W','im','meta')]
SRC[str(original)]=hashlib.sha256(original.read_bytes()).hexdigest()
IND_EMA={};IND_STATE={}
def industry_extra(sector):
 if sector not in IND_EMA:
  f=industry(sector);out=pd.Series(np.nan,index=f.index,dtype=float)
  # Original industry-facts clock already contains eligible observed prices;
  # skip invalid values, preserve source reset, use the same EMA convention.
  runs=f.segment_id.ne(f.segment_id.shift()).cumsum()
  for _,g in f.groupby(runs,sort=False):
   c=g.close.astype(float);c=c.loc[np.isfinite(c)&c.gt(0)]
   out.loc[c.index]=c.ewm(span=20,adjust=False,min_periods=20).mean()
  IND_EMA[sector]=out
  m=im[sector];p=m['refs']['state'];g=frame(p,m['output_sha256'][p]);g['day']=pd.to_datetime(g.day);IND_STATE[sector]=g.set_index('day')
 return IND_EMA[sector],IND_STATE[sector]
def context(sid,sector,day):
 t=pd.Timestamp(day);z=dict(day=day,anchor_day=None,market_calendar='fixed USZI399300 observed market calendar',market_lag=20,window_close_count=21,stock_unknown=[],industry_unknown=[],market_unknown=[],stock_return20=None,industry_return20=None,HS300_price_index_return20=None,RS20=None,RS20_positive=None,C_ge_EMA20=None,industry_C_ge_EMA20=None,industry20_minus_HS30020=None)
 f=stock(sid);g=industry(sector);ie,st=industry_extra(sector)
 if t not in market.index or market.index.get_loc(t)<20:z['market_unknown'].append('Missing current market or20 prior market intervals');return z
 n=market.index.get_loc(t);a=market.index[n-20];cal=market.index[n-20:n+1];z['anchor_day']=str(a.date());z['market_Ct']=float(market.loc[t,'close']);z['market_Ct20']=float(market.loc[a,'close']);z['HS300_price_index_return20']=z['market_Ct']/z['market_Ct20']-1
 for label,v in [('stock',f),('industry',g)]:
  q0=v.loc[a] if a in v.index else None;q1=v.loc[t] if t in v.index else None
  z[label+'_common_calendar_close_observations']=len(cal.intersection(v.index));z[label+'_missing_common_market_days']=[str(x.date()) for x in cal.difference(v.index)]
  for which,q,d in [('anchor',q0,a),('current',q1,t)]:
   if q is None:z[label+'_unknown'].append('Missing exact '+which+' endpoint '+str(d.date()));continue
   z[label+'_'+which+'_source_segment']=float(q.segment_id);z[label+'_'+which+'_causal_close']=float(q.close)
  if q1 is not None:
   for field in ['e0_target','e0_floor']+(['i_target','i_floor','factor','raw_close'] if label=='stock' else []):z[label+'_original_'+field]=env['val'](q1[field])
  if q0 is not None and q1 is not None:
   if q0.segment_id!=q1.segment_id:z[label+'_unknown'].append('Endpoint source segment differs')
   if not(np.isfinite(float(q0.close)) and np.isfinite(float(q1.close)) and min(float(q0.close),float(q1.close))>0):z[label+'_unknown'].append('Invalid endpoint price')
   if not z[label+'_unknown']:z[label+'_return20']=float(q1.close/q0.close-1)
 if not(z['stock_unknown'] or z['industry_unknown'] or z['market_unknown']):z['RS20']=z['stock_return20']-max(z['industry_return20'],z['HS300_price_index_return20']);z['RS20_positive']=z['RS20']>0
 if z['industry_return20'] is not None:z['industry20_minus_HS30020']=z['industry_return20']-z['HS300_price_index_return20']
 q=provider.at(sid,day,'EMA20');z['EMA20_provider_status']=q['status'];z['EMA20_unknown_reason']=q['unknown_reason'];z['EMA20_span']=20;z['EMA20_clock']='original valid-observation source clock; adjustFalse/min_periods20'
 if q['status']=='READY':
  assert t in f.index and np.isclose(q['causal_close'],f.loc[t,'close'],rtol=1e-12,atol=1e-12)
  z['stock_EMA20']=q['line'];z['C_ge_EMA20']=q['causal_close']>=q['line']
 z['industry_EMA20']=float(ie.loc[t]) if t in ie.index and np.isfinite(ie.loc[t]) else None;z['industry_EMA20_span']=20;z['industry_EMA20_clock']='original industry-facts eligible observed-price source clock; adjustFalse/min_periods20'
 if z['industry_EMA20'] is not None and t in g.index:z['industry_C_ge_EMA20']=float(g.loc[t,'close'])>=z['industry_EMA20']
 z['industry_I_state']='NOT_DEFINED_IN_ORIGINAL_INDUSTRY_FACTS'
 if t in st.index:
  r=st.loc[t];z['industry_original_market_state']={k:env['val'](r[k]) for k in ['E0_valid','E0_floor','E0_episode','stage_name','attempt_id','action','receipt','receipt_id','authorization_usable'] if k in r.index};z['industry_market_state_scope']='Original market stage/evidence, not actual account admission or available funding guarantee'
 else:z['industry_original_market_state']=None
 z['four_cell']='UNKNOWN' if z['RS20_positive'] is None or z['C_ge_EMA20'] is None else ('RSpos' if z['RS20_positive'] else 'RSnonpos')+'__'+('CgeEMA20' if z['C_ge_EMA20'] else 'CltEMA20')
 z['price_domain']='original causal adjusted stock/industry source price and true HS300 price index; not executable raw return or account PnL'
 return z

t0=time.monotonic();ALL={};MOTHERS={};BY_BUDGET={}
for ref in ['2022_2024','strong']:
 mother=read(EQ/'entry_exit_scale/holding_exit'/(ref+'_LAYERS.json'));MOTHERS[ref]=mother;rows=[]
 for h in mother:
  assert meta[h['sid']]['sector_id']==h['sector']
  z=context(h['sid'],h['sector'],h['decision_at'][:10]);z.update(window=ref,layer=h['layer'],sid=h['sid'],name=h['name'],industry_name=h['industry'],sector=h['sector'],role=h['role'],action=h['action'],decision_at=h['decision_at'],actual_fill_at=h['opened'],budget_order=h['budget_order'],original_cost=h['cost'],original_lifecycle_net=h['net'],industry_assignment_basis='original frozen current snapshot, not PIT',financial_field_scope='original whole-life layer money, never monthly wealth or avoidable loss')
  rows.append(z);BY_BUDGET[ref,h['budget_order']]=z
 ALL[ref]=rows;save(ref+'_ALL_DECISION_CONTEXT_EXTENDED.json',rows)

month=read(O.parent/'month_attribution/ALL_AFFECTED_LAYERS.json');old=[x for x in month if x['cohort']=='old_inventory_at_Nov30'];new=[x for x in month if x['cohort']!='old_inventory_at_Nov30'];assert len(old)==87 and len(new)==122
def match(h):
 z=BY_BUDGET['2022_2024',h['budget_order']]
 assert z['sid']==h['sid'] and z['role']==h['role'] and z['decision_at'].replace(' ','T')==h['decision_at'] and z['actual_fill_at'].replace(' ','T')==h['opened']
 return z
dec122=[]
for h in new:
 z=dict(match(h),month_cohort=h['cohort'],month_components=h['month_components'],month_book_layer_identity=h['layer_in_this_book']);dec122.append(z)
save('DEC122_ACTUAL_FILL_DECISION_CONTEXT.json',dec122)
dec118=[x for x in ALL['2022_2024'] if x['decision_at'][:7]=='2022-12'];a={x['budget_order']:x for x in dec118};b={x['budget_order']:x for x in dec122}
save('DEC118_VS_DEC122_CLOCK_DIFFERENCE.json',dict(decision_Dec118=len(a),actualfill_Dec122=len(b),intersection=len(set(a)&set(b)),Decfill_from_other_month_decision=[b[k] for k in sorted(set(b)-set(a))],Decdecision_filled_other_month=[a[k] for k in sorted(set(a)-set(b))],identity='Exact budget_order plus sid/role/decision/fill clocks, not cross-book layer-ID guess'))
pair=env['B']/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair/daily.jsonl.gz';SRC[str(pair)]=sha=hashlib.sha256(pair.read_bytes()).hexdigest()
with gzip.open(pair,'rt') as f:ds=[json.loads(x) for x in f]
hist=defaultdict(list)
for d in ds:
 if '2022-11-30'<=d['at'][:10]<='2022-12-30':
  for x in d['layers']:hist[x['id']].append((d['at'],x,d['on']))
orig={h['layer']:h for h in MOTHERS['2022_2024']};oldout=[]
for h in old:
 z=match(h);lid=z['layer'];rh=orig[lid];hh=hist[lid];assert hh[0][0][:10]=='2022-11-30'
 firstreq=min((x['at'] for x in rh['original_exit_request_events']),default=None)
 events=[('Nov30_CLOSE_month_opening_reference',hh[0])]
 if h['closed'] is not None and h['closed'][:7]=='2022-12':
  fill=h['closed'].replace('T',' ');prior=max(x for x in hh if x[0]<fill);events.append(('last_actual_held_CLOSE_before_Dec_sale_OPEN',prior))
 else:events.append(('last_Dec_held_CLOSE_or_month_end',hh[-1]))
 for r in rh['original_exit_request_events']:
  if '2022-11-30'<=r['at'][:10]<='2022-12-30':
   s=next((x for x in hh if x[0]==r['at']),None)
   if s is not None:events.append(('original_specific_exit_request_CLOSE',s));break
 contexts=[]
 for kind,(at,snap,on) in events:
  q=context(h['sid'],h['sector'],at[:10]);q.update(event_kind=kind,at=at,original_ACT_on=on,at_or_after_earliest_original_request=firstreq is not None and at>=firstreq,original_snapshot_layer={k:snap.get(k) for k in ['id','kind','qty','floor','last_core_line','pool','episode','attempt','pending_I_exit_reference']});contexts.append(q)
 oldout.append(dict(sid=h['sid'],name=h['name'],sector=h['sector'],role=h['role'],original_No60_layer=lid,month_book_layer_identity=h['layer_in_this_book'],budget_order=h['budget_order'],month_components=h['month_components'],month_component_scope='One per original old layer. Do not sum the repeated context events as money.',original_first_specific_request_at=firstreq,contexts=contexts))
save('OLD87_MONTHSTART_AND_EXIT_HELD_CONTEXT.json',oldout)
def counts(rr):return dict(rows=len(rr),stock20_unknown=sum(bool(x['stock_unknown']) for x in rr),industry20_unknown=sum(bool(x['industry_unknown']) for x in rr),market20_unknown=sum(bool(x['market_unknown']) for x in rr),stock_EMA20_unknown=sum(x['C_ge_EMA20'] is None for x in rr),industry_EMA20_unknown=sum(x['industry_C_ge_EMA20'] is None for x in rr),four_cells=dict(Counter(x['four_cell'] for x in rr)))
summary=dict(all_original_actual_entries=sum(len(x) for x in ALL.values()),per_window={k:counts(v) for k,v in ALL.items()},Dec122=counts(dec122),Dec118=counts(dec118),old87_layers=len(oldout),old87_contexts=sum(len(x['contexts']) for x in oldout),old87_context_readiness=counts([q for x in oldout for q in x['contexts']]),seconds=time.monotonic()-t0,new_accounts=0,new_filters=0,new_candidate_policy_code=0,scope='Root diagnostic extension only. New-buy-only stock gate stopped; industry fields not a frozen industry policy or selection by strong-window money.')
save('EXTENSION_VALIDATION.json',summary)
SRC[str(__file__)]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();save('EXTENSION_SOURCE_SHA256.json',SRC)
print(json.dumps(summary,ensure_ascii=False,indent=2))
