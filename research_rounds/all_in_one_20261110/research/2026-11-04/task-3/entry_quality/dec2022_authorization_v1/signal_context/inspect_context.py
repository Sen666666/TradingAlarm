"""Frozen Dec118 signal context only; no eligibility or account implementation."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D,getcontext
import json,gzip,hashlib,sys
import numpy as np,pandas as pd

getcontext().prec=60
O=Path(__file__).resolve().parent;EQ=O.parents[1];R=EQ/'trend_exit_controls_v1';W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');ROOT=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data')
sys.path.insert(0,str(R));from indicator_provider import IndicatorProvider
SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,allow_nan=False)
def frame(p,expect=None,columns=None):
 p=Path(p);h=sha(p)
 if expect is not None:assert h==expect
 SRC[str(p)]=h
 return pd.read_parquet(p,columns=columns) if p.suffix=='.parquet' else pd.read_csv(p,index_col=0,parse_dates=True)
def val(x):return None if pd.isna(x) else x.item() if hasattr(x,'item') else x
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
meta_path=RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json';meta=read(meta_path)
idxpath=ROOT/'ths-index-history-20261018/canonical/USZI399300.csv';checkpoint=read(ROOT/'ths-index-history-20261018/checkpoints/USZI399300.json');market=frame(idxpath,checkpoint['canonical_sha256'])
assert market.index.is_unique and market.index.is_monotonic_increasing
provider=IndicatorProvider();SRC[str(R/'indicator_provider.py')]=sha(R/'indicator_provider.py');SRC[str(R/'indicators/MANIFEST.json')]=sha(R/'indicators/MANIFEST.json');assert SRC[str(R/'indicators/MANIFEST.json')]==provider.manifest_sha256
FF={};II={}
def stock(sid):
 if sid not in FF:
  m=sm[sid];p=m['refs']['facts'];FF[sid]=frame(p,m['output_sha256'][p],['close','segment_id','i_target','i_floor','e0_target','e0_floor','factor','raw_close'])
 return FF[sid]
def industry(sector):
 if sector not in II:
  m=im[sector];p=next(p for p in m['source_sha256'] if '/industry-facts/' in p);II[sector]=frame(p,m['source_sha256'][p])
 return II[sector]
def context(sid,sector,day,compute_values):
 t=pd.Timestamp(day);z=dict(day=day,market_calendar='USZI399300 true HS300 index observed trading dates, fixed before diagnostic',market_anchor_lag=20,window_close_count=21,anchor_day=None,stock_unknown=[],industry_unknown=[],market_unknown=[],RS20=None,RS20_positive=None,EMA20=None,C_ge_EMA20=None)
 if t not in market.index:z['market_unknown'].append('No current HS300 observation');return z
 n=market.index.get_loc(t)
 if n<20:z['market_unknown'].append('Insufficient20 market intervals');return z
 a=market.index[n-20];cal=market.index[n-20:n+1];z['anchor_day']=str(a.date());z['market_Ct']=float(market.loc[t,'close']);z['market_Ct20']=float(market.loc[a,'close'])
 f=stock(sid);g=industry(sector)
 def endpoints(v,label):
  for d in [a,t]:
   if d not in v.index:z[label+'_unknown'].append('Missing exact endpoint '+str(d.date()))
  if z[label+'_unknown']:return None,None
  q0,q1=v.loc[a],v.loc[t]
  if not np.isfinite(float(q0.close)) or not np.isfinite(float(q1.close)) or min(float(q0.close),float(q1.close))<=0:z[label+'_unknown'].append('Invalid endpoint price')
  if q0.segment_id!=q1.segment_id:z[label+'_unknown'].append('Endpoint source segment differs')
  z[label+'_anchor_source_segment']=val(q0.segment_id);z[label+'_current_source_segment']=val(q1.segment_id)
  z[label+'_common_calendar_close_observations']=len(cal.intersection(v.index))
  z[label+'_missing_interior_common_market_days']=[str(x.date()) for x in cal.difference(v.index)]
  z[label+'_Ct']=float(q1.close);z[label+'_Ct20']=float(q0.close)
  return q0,q1
 s0,s1=endpoints(f,'stock');i0,i1=endpoints(g,'industry')
 if s1 is not None:
  z['stock_original_I_target']=val(s1.i_target);z['stock_original_I_floor']=val(s1.i_floor);z['stock_original_E0_target']=val(s1.e0_target);z['stock_original_E0_floor']=val(s1.e0_floor);z['stock_current_factor']=val(s1.factor);z['stock_raw_close']=val(s1.raw_close)
 if i1 is not None:
  z['industry_original_E0_target']=val(i1.e0_target);z['industry_original_E0_floor']=val(i1.e0_floor);z['industry_I_state']='NOT_DEFINED_IN_ORIGINAL_INDUSTRY_FACTS';z['industry_factor']=val(i1.factor)
 q=provider.at(sid,day,'EMA20');z['EMA20_provider_status']=q['status'];z['EMA20_unknown_reason']=q['unknown_reason'];z['EMA20_span']=20;z['EMA20_clock']='Original valid observed source-price observations, adjust=False/min_periods20; not20 market-calendar rows';z['EMA20_source_max_day']=q['source_max_day']
 if q['status']=='READY':
  assert s1 is not None and np.isclose(q['causal_close'],s1.close,rtol=1e-12,atol=1e-12)
  z['EMA20']=q['line'];z['C_ge_EMA20']=q['causal_close']>=q['line']
 if compute_values and not(z['stock_unknown'] or z['industry_unknown'] or z['market_unknown']):
  rs=float(s1.close/s0.close-1);ri=float(i1.close/i0.close-1);rm=float(market.loc[t,'close']/market.loc[a,'close']-1)
  z.update(stock_return20=rs,industry_return20=ri,HS300_price_index_return20=rm,RS20=rs-max(ri,rm),RS20_positive=rs>max(ri,rm))
 return z

mother=read(EQ/'entry_exit_scale/holding_exit/2022_2024_LAYERS.json');dec=[x for x in mother if x['decision_at'][:7]=='2022-12'];assert len(dec)==118
pair=B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair/daily.jsonl.gz';SRC[str(pair)]=sha(pair)
with gzip.open(pair,'rt') as f:dm={x['at'][:10]:x for x in map(json.loads,f)}
rows=[]
for h in dec:
 assert meta[h['sid']]['sector_id']==h['sector']
 z=context(h['sid'],h['sector'],h['decision_at'][:10],True)
 z.update(layer=h['layer'],sid=h['sid'],name=h['name'],industry_name=h['industry'],sector=h['sector'],role=h['role'],action=h['action'],decision_at=h['decision_at'],actual_fill_at=h['opened'],decision_ACT_on=dm[h['decision_at'][:10]]['on'],industry_assignment_basis='original frozen current snapshot, not historical PIT membership',original_lifecycle_cost=h['cost'],original_lifecycle_net=h['net'],money_label='Original saved full lifecycle contribution, not conditional policy PnL')
 z['four_cell']='UNKNOWN' if z['RS20_positive'] is None or z['C_ge_EMA20'] is None else ('RSpos' if z['RS20_positive'] else 'RSnonpos')+'__'+('CgeEMA20' if z['C_ge_EMA20'] else 'CltEMA20')
 rows.append(z)
save('DEC2022_ALL118_DECISION_CONTEXT.json',rows)
cells=[]
for cell in ['RSpos__CgeEMA20','RSpos__CltEMA20','RSnonpos__CgeEMA20','RSnonpos__CltEMA20','UNKNOWN']:
 for role in ['core','mobile','ALL']:
  rr=[x for x in rows if x['four_cell']==cell and (role=='ALL' or x['role']==role)];vv=[D(x['original_lifecycle_net']) for x in rr]
  cells.append(dict(cell=cell,role=role,layers=len(rr),stocks=len({x['sid'] for x in rr}),original_cost=str(sum((D(x['original_lifecycle_cost']) for x in rr),D(0))),original_positive=str(sum((v for v in vv if v>0),D(0))),original_negative=str(sum((v for v in vv if v<0),D(0))),original_net=str(sum(vv,D(0))),policy_scope='Four descriptive cells, not an AND entry gate and not avoidable loss'))
save('DEC2022_COMPLETE_FOUR_CELLS.json',cells)
tail=read(EQ/'local_high/strong_FIXED_TAILS.json');tr=[]
for old in tail:
 h=old['original'];z=context(h['sid'],h['sector'],h['decision_at'][:10],False)
 tr.append(dict(sid=h['sid'],decision_at=h['decision_at'],sector=h['sector'],original_tail_layer_identity=h['layer'],original_tail_control_basis='Full original94 fixed members, no financial classification or gate applied here',source_readiness=z))
save('STRONG_ORIGINAL94_INPUT_READINESS_ONLY.json',tr)
sources=[('HS300_true_price_index',idxpath,market),('HS300_ETF_causal_signal',B/'capacity_cost_guard_analysis_v1/benchmark_B_2025_26/inputs/510300_history.csv',None),('SSE50_price_index_not_ETF',ROOT/'ths-refresh-20261018/USZA000016-signal.parquet',None)]
availability=[]
for kind,p,f in sources:
 if f is None:f=frame(p)
 availability.append(dict(kind=kind,path=str(p),rows=len(f),first=str(f.index.min().date()),last=str(f.index.max().date()),columns=list(f.columns),used_for_fixed_diagnostic=kind=='HS300_true_price_index'))
save('SOURCE_AVAILABILITY.json',dict(benchmarks=availability,ETF510050_found_in_two_primary_data_roots=False,ETF510050_search_roots=['/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/data',str(ROOT)],industry_state='90 original index facts have E0, not I; do not synthesize I',industry_assignment_source=str(meta_path),assignment_not_PIT=True))
save('VALIDATION.json',dict(passed=True,Dec_layers=len(rows),Dec_stocks=len({x['sid'] for x in rows}),Dec_industries=len({x['sector'] for x in rows}),roles=dict(Counter(x['role'] for x in rows)),four_cells=dict(Counter(x['four_cell'] for x in rows)),stock_unknown_layers=sum(bool(x['stock_unknown']) for x in rows),industry_unknown_layers=sum(bool(x['industry_unknown']) for x in rows),market_unknown_layers=sum(bool(x['market_unknown']) for x in rows),EMA20_unknown_layers=sum(x['C_ge_EMA20'] is None for x in rows),all_exact_current_stock_I_on=all(x.get('stock_original_I_target')==1 for x in rows),all_original_decision_ACT_on=all(x['decision_ACT_on'] for x in rows),strong94_exact_endpoints_unknown=sum(bool(x['source_readiness']['stock_unknown'] or x['source_readiness']['industry_unknown'] or x['source_readiness']['market_unknown']) for x in tr),strong94_EMA20_unknown=sum(x['source_readiness']['C_ge_EMA20'] is None for x in tr),new_accounts=0,new_filters=0,root_candidate_code_written=False))
SRC[str(__file__)]=sha(__file__);save('SOURCE_SHA256.json',SRC)
print(json.dumps(read(O/'VALIDATION.json'),ensure_ascii=False,indent=2))
