"""H2 original-path holding authorization domain; no candidate account policy."""
from pathlib import Path
from collections import Counter,defaultdict
from decimal import Decimal as D,getcontext
import json,gzip,hashlib,time,sys
import numpy as np,pandas as pd

getcontext().prec=60
O=Path(__file__).resolve().parent;P=O.parent;EQ=P.parents[1];R=EQ/'trend_exit_controls_v1';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
sys.path.insert(0,str(R));from indicator_provider import IndicatorProvider
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def gz(p,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f] if lines else json.load(f)
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def frame(p,h=None,cols=None):
 p=Path(p);s=sha(p)
 if h is not None:assert s==h
 SRC[str(p)]=s;return pd.read_parquet(p,columns=cols) if p.suffix=='.parquet' else pd.read_csv(p,index_col=0,parse_dates=True)
def dayint(day):return int(np.datetime64(day,'D').astype(np.int64))
def val(x):return None if pd.isna(x) else x.item() if hasattr(x,'item') else x
provider=IndicatorProvider();SRC[str(R/'indicator_provider.py')]=sha(R/'indicator_provider.py');SRC[str(R/'indicators/MANIFEST.json')]=provider.manifest_sha256
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
ix=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018');cp=read(ix/'checkpoints/USZI399300.json');market=frame(ix/'canonical/USZI399300.csv',cp['canonical_sha256']);MC={}
for n in range(20,len(market)):
 t,a=market.index[n],market.index[n-20];MC[str(t.date())]=(str(a.date()),dayint(str(a.date())),float(market.close.iloc[n]/market.close.iloc[n-20]-1))
SD={};ID={};QC={};RAW={}
def prices(sid,sector):
 if sid not in SD:
  m=sm[sid];p=m['refs']['facts'];f=frame(p,m['output_sha256'][p],['close','segment_id','i_target','e0_target','raw_close','factor']);SD[sid]=dict(days=f.index.to_numpy('datetime64[D]').astype(np.int64),index=f.index,values=f.to_numpy(float),cols={c:i for i,c in enumerate(f.columns)})
 if sector not in ID:
  m=im[sector];p=next(p for p in m['source_sha256'] if '/industry-facts/' in p);f=frame(p,m['source_sha256'][p]);ema=pd.Series(np.nan,index=f.index)
  for _,g in f.groupby(f.segment_id.ne(f.segment_id.shift()).cumsum(),sort=False):
   c=g.close.astype(float);c=c[np.isfinite(c)&c.gt(0)];ema.loc[c.index]=c.ewm(span=20,adjust=False,min_periods=20).mean()
  ID[sector]=dict(days=f.index.to_numpy('datetime64[D]').astype(np.int64),close=f.close.to_numpy(float),segment=f.segment_id.to_numpy(float),e0=f.e0_target.to_numpy(float),EMA20=ema.to_numpy(float))
 return SD[sid],ID[sector]
def context(sid,sector,day):
 key=(sid,sector,day)
 if key in QC:return QC[key]
 q=provider.at(sid,day,'EMA20');z=dict(day=day,status='UNKNOWN',unknown=[],RS20=None,jointweak=None,stock_I_target=None,stock_E0_target=None,industry_C_ge_EMA20=None,stock_EMA20=q['line'],stock_EMA20_status=q['status'],source_segment=q['source_segment'],causal_close=q['causal_close'],source_max_day=q['source_max_day'])
 s,i=prices(sid,sector);di=dayint(day);j=int(np.searchsorted(s['days'],di));k=int(np.searchsorted(i['days'],di))
 current=j<len(s['days']) and s['days'][j]==di
 if current:
  v=s['values'][j];co=s['cols'];z['stock_I_target']=bool(v[co['i_target']]);z['stock_E0_target']=bool(v[co['e0_target']]);z['stock_raw_close']=float(v[co['raw_close']]);z['stock_factor']=float(v[co['factor']])
  if j>0 and s['values'][j-1,co['segment_id']]==v[co['segment_id']]:z['return_since_previous_stock_source_close']=float(v[co['close']]/s['values'][j-1,co['close']]-1);z['previous_stock_source_observation_day']=str(s['index'][j-1].date())
 if q['status']!='READY':z['unknown'].append(q['unknown_reason'])
 if day not in MC:z['unknown'].append('Missing market t/t20');QC[key]=z;return z
 anchor,ai,rm=MC[day];z.update(anchor_day=anchor,HS300_price_index_return20=rm)
 ja=int(np.searchsorted(s['days'],ai));ka=int(np.searchsorted(i['days'],ai))
 if not current or ja==len(s['days']) or s['days'][ja]!=ai:z['unknown'].append('Missing exact stock endpoint')
 elif s['values'][j,s['cols']['segment_id']]!=s['values'][ja,s['cols']['segment_id']]:z['unknown'].append('Stock endpoints cross source')
 if k==len(i['days']) or i['days'][k]!=di or ka==len(i['days']) or i['days'][ka]!=ai:z['unknown'].append('Missing exact industry endpoint')
 elif i['segment'][k]!=i['segment'][ka]:z['unknown'].append('Industry endpoints cross source')
 if k<len(i['days']) and i['days'][k]==di:
  z['industry_E0_target']=bool(i['e0'][k]);z['industry_causal_close']=float(i['close'][k]);z['industry_EMA20']=float(i['EMA20'][k]) if np.isfinite(i['EMA20'][k]) else None
  if z['industry_EMA20'] is not None:z['industry_C_ge_EMA20']=bool(i['close'][k]>=i['EMA20'][k])
 if not z['unknown']:
  co=s['cols'];rs=float(s['values'][j,co['close']]/s['values'][ja,co['close']]-1);ri=float(i['close'][k]/i['close'][ka]-1);assert np.isclose(q['causal_close'],s['values'][j,co['close']],rtol=1e-12,atol=1e-12)
  z.update(status='KNOWN',stock_return20=rs,industry_return20=ri,RS20=rs-max(ri,rm),industry20_minus_HS30020=ri-rm,jointweak=bool(rs<=max(ri,rm) and q['causal_close']<q['line']))
 QC[key]=z;return z
def next_open(sid,nextday):
 if nextday is None:return dict(status='BEYOND_ORIGINAL_NATIVE_HORIZON',raw_quote=None,execution_certified=False)
 if sid not in RAW:
  m=sm[sid];p=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));RAW[sid]=frame(p,m['source_sha256'][p],['raw_open','raw_high','raw_low','raw_close','raw_volume','volume','volume_unit','segment_id'])
 f=RAW[sid];t=pd.Timestamp(nextday)
 if t not in f.index:return dict(status='NO_EXACT_NEXT_SESSION_SOURCE_QUOTE',day=nextday,raw_quote=None,execution_certified=False)
 q=f.loc[t];return dict(status='NEXT_NATIVE_SESSION_QUOTE_ONLY',day=nextday,earliest_session_OPEN=nextday+' 09:30:00+08:00',raw_quote={k:val(q[k]) for k in f.columns},execution_certified=False,reason='Future quote read only after first event selection. Native liquidity/quantity/T+1/limit/corporate-action window not replayed; this is not an eligible-fill claim.')
def money(rr,field):
 v=[D(x[field]) for x in rr];return dict(layers=len(rr),net=str(sum(v,D(0))),positive=str(sum((x for x in v if x>0),D(0))),negative=str(sum((x for x in v if x<0),D(0))))

t0=time.monotonic();month=read(P.parent/'month_attribution/ALL_AFFECTED_LAYERS.json');monthby={x['budget_order']:x for x in month};ALL={};SUM={};VAL={};ROOTS={'2022_2024':B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair','strong':B/'pvr_pool_feasibility/runs/2025_26/pair'}
for ref,pair in ROOTS.items():
 mother=read(EQ/'entry_exit_scale/holding_exit'/(ref+'_LAYERS.json'));mm={x['layer']:x for x in mother};ds=gz(pair/'daily.jsonl.gz',True);cal=[d['at'][:10] for d in ds];rows={};counts=Counter();obs=Counter()
 for h in mother:
  m=monthby.get(h['budget_order']) if ref=='2022_2024' else None
  rows[h['layer']]=dict(window=ref,layer=h['layer'],sid=h['sid'],name=h['name'],role=h['role'],action=h['action'],budget_order=h['budget_order'],original_lifecycle_net=h['net'],original_cost=h['cost'],month_cohort=None if m is None else m['cohort'],original_Dec_month_wealth=None if m is None else m['month_components']['wealth'],first_original_specific_request=min((x['at'] for x in h['original_exit_request_events']),default=None),global_first_eligible_H2=None,Dec_first_eligible_H2=None,pre_request_unknown_held_CLOSEs=0)
 with (O/(ref+'_ALL_HELD_RS_EMA_CONTEXT.jsonl')).open('x') as out:
  for n,d in enumerate(ds):
   day=d['at'][:10];at=d['at'];nd=cal[n+1] if n+1<len(cal) else None
   for x in d['layers']:
    h=mm[x['id']];r=rows[x['id']];q=context(h['sid'],h['sector'],day);obs[h['layer']]+=1;counts['all_held_CLOSEs']+=1
    if r['first_original_specific_request'] is not None and at>=r['first_original_specific_request']:priority='ORIGINAL_LAYER_REQUEST_ALREADY_OR_SAME_CLOSE'
    elif not d['on']:priority='ORIGINAL_ACT_OFF'
    elif q['stock_I_target'] is False:priority='ORIGINAL_I_OFF'
    elif q['stock_I_target'] is None or q['status']!='KNOWN':priority='UNKNOWN_CURRENT_INPUT'
    else:priority='ORIGINAL_ACT_I_ON_LAYER_NOT_PENDING'
    role=h['role']=='mobile';eligible=bool(role and priority=='ORIGINAL_ACT_I_ON_LAYER_NOT_PENDING' and q['jointweak'] is True)
    if q['status']!='KNOWN':counts['unknown_held_rows']+=1
    if priority=='UNKNOWN_CURRENT_INPUT':r['pre_request_unknown_held_CLOSEs']+=1
    counts['H2_eligible_held_CLOSEs']+=eligible
    record=dict(window=ref,layer=h['layer'],sid=h['sid'],role=h['role'],at=at,original_priority_status=priority,H2_role_eligible_mobile=role,H2_condition_eligible_on_original_path=eligible,context=q)
    out.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n')
    if eligible and (r['global_first_eligible_H2'] is None or (day[:7]=='2022-12' and r['Dec_first_eligible_H2'] is None)):
     prior_global=r['global_first_eligible_H2'];wealth=None
     if q.get('stock_raw_close') is not None:wealth=str(D(x['cash'])+D(x['dividend'])+D(x['qty'])*D(str(q['stock_raw_close'])))
     event=dict(at=at,context=dict(q),held_quantity_at_CLOSE=x['qty'],original_snapshot_floor_after_native_management=x['floor'],original_snapshot_last_core_line=x.get('last_core_line'),original_ACT_on=d['on'],first_original_specific_request=r['first_original_specific_request'],current_CLOSE_layer_wealth_already_accrued=wealth,current_CLOSE_wealth_scope='Original layer cash+dividend+current raw mark; already accrued, not avoidable. No subtraction from future whole-life money.',next_native_session_OPEN_quote=next_open(h['sid'],nd),earlier_global_H2_event_at=None if prior_global is None else prior_global['at'],counterfactual_scope='Event on original path only; no claim same layer still exists after an earlier hypothetical exit.')
     if r['global_first_eligible_H2'] is None:r['global_first_eligible_H2']=event
     if day[:7]=='2022-12' and r['Dec_first_eligible_H2'] is None:r['Dec_first_eligible_H2']=event
 for lid,h in mm.items():assert obs[lid]==h['held_close_observations']
 rr=list(rows.values());ALL[ref]=rr;save(ref+'_LAYER_FIRST_ELIGIBLE_H2.json',rr)
 SUM[ref]=dict(all_original_entries=len(rr),all_mobile=sum(r['role']=='mobile' for r in rr),global_eligible_layers=sum(r['global_first_eligible_H2'] is not None for r in rr),global_original_money_touched=money([r for r in rr if r['global_first_eligible_H2'] is not None],'original_lifecycle_net'),original_path_scope='Coverage only, never avoided PnL or account delta')
 if ref=='2022_2024':
  dec=[r for r in rr if r['month_cohort'] is not None];assert len(dec)==209
  SUM[ref]['Dec209_by_cohort']={co:dict(all_layers=len([r for r in dec if r['month_cohort']==co]),eligible_Dec_layers=len([r for r in dec if r['month_cohort']==co and r['Dec_first_eligible_H2'] is not None]),original_month_wealth_covered=money([r for r in dec if r['month_cohort']==co and r['Dec_first_eligible_H2'] is not None],'original_Dec_month_wealth'),original_lifecycle_covered=money([r for r in dec if r['month_cohort']==co and r['Dec_first_eligible_H2'] is not None],'original_lifecycle_net')) for co in sorted({r['month_cohort'] for r in dec})}
 VAL[ref]=dict(counts=counts,all_layer_held_counts_match=True,all_first_events_before_original_requests=all(r['first_original_specific_request'] is None or r['global_first_eligible_H2'] is None or r['global_first_eligible_H2']['at']<r['first_original_specific_request'] for r in rr),core_tool_events=sum(r['role']=='core' and r['global_first_eligible_H2'] is not None for r in rr))
 tails=read(EQ/'local_high'/(ref+'_FIXED_TAILS.json'));tt=[]
 for t in tails:
  actual=[]
  for h in t['matched_actual_No60_rows']:
   r=rows[h['layer']];assert r['budget_order']==h['budget_order'] and r['sid']==h['sid']
   actual.append(r)
  tt.append(dict(original_fixed_tail=t['original'],No60_matched_actual_layers=actual,status='UNMATCHED_UNKNOWN' if not actual else 'TOUCHED_BEFORE_ORIGINAL_REQUEST' if any(r['global_first_eligible_H2'] is not None for r in actual) else 'NO_ELIGIBLE_MOBILE_H2_ON_ORIGINAL_PATH'))
 save(ref+'_FULL_FIXED_TAIL_H2_CONTROLS.json',tt)
 touched=[r for t in tt for r in t['No60_matched_actual_layers'] if r['global_first_eligible_H2'] is not None]
 SUM[ref]['fixed_tails']=dict(all_original_members=len(tt),No60_matched_original_members=sum(bool(t['No60_matched_actual_layers']) for t in tt),No60_touched_original_members=sum(t['status']=='TOUCHED_BEFORE_ORIGINAL_REQUEST' for t in tt),No60_original_money_of_touched=money(touched,'original_lifecycle_net'),original_PVR_contribution_of_touched=str(sum((D(t['original_fixed_tail']['net']) for t in tt if t['status']=='TOUCHED_BEFORE_ORIGINAL_REQUEST'),D(0))))
save('SUMMARY.json',SUM);save('VALIDATION.json',dict(passed=True,refs=VAL,seconds=time.monotonic()-t0,new_accounts=0,new_native_OPEN=0,new_native_CLOSE=0,unique_cached_sid_sector_days=len(QC),frozen_policy_created=False))
SRC[str(__file__)]=sha(__file__);save('SOURCE_SHA256.json',SRC)
print(json.dumps(SUM,ensure_ascii=False,indent=2));print('SECONDS',time.monotonic()-t0)
