"""Independent bounded label/aggregation/evaluation audit, no account or signal engine."""
from pathlib import Path
from collections import defaultdict,Counter
from fractions import Fraction as F
import ast, hashlib, json, math
import numpy as np
import pandas as pd
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent
checks=defaultdict(int)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def eq(a,b,key):
 if a is None or b is None:assert a is None and b is None,(key,a,b)
 else:assert abs(float(a)-float(b))<=2e-12*max(1,abs(float(a)),abs(float(b))),(key,a,b)
 checks[key]+=1
manifest=read(P/'SOURCE_MANIFEST.json');script=P/'analyze.py';assert manifest['script_sha256']==sha(script)
for path,h in manifest['sources'].items():assert sha(path)==h,path;checks['source_sha256']+=1
protocol=read(P/'PROTOCOL.json');summary=read(P/'SUMMARY.json')
marketpath=next(path for path in manifest['sources'] if path.endswith('.csv') and 'market' in Path(path).name.lower()) if any(path.endswith('.csv') and 'market' in Path(path).name.lower() for path in manifest['sources']) else None
native_state=read(P.parent/'first_entry_regime/native_state/SOURCE_MANIFEST.json');marketpath=native_state['original_ACT_source_path'];market=pd.read_csv(marketpath,index_col=0,parse_dates=True);calendar=[str(x.date()) for x in market.index];ix={d:i for i,d in enumerate(calendar)};calindex=pd.to_datetime(calendar)
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
with (P/'input_readiness/SIGNALS.jsonl').open() as f:signals=[json.loads(x) for x in f]
sig={e['signal_id']:e for e in signals};assert len(sig)==len(signals)==25407
cache={};qsource={}
def quote(sid):
 if sid not in cache:
  man=sm[sid];paths=[p for p in man['source_sha256'] if p.endswith('/signal.parquet')];assert len(paths)==1;p=paths[0];assert manifest['sources'][p]==man['source_sha256'][p]
  f=pd.read_parquet(p,columns=['close','amount','volume','observed_bar','synthetic_event_bar','source_invalid','price_eligible','volume_eligible','segment_id']);assert f.index.is_unique and f.index.is_monotonic_increasing
  present=calindex.isin(f.index);g=f.reindex(calindex);v={k:g[k].to_numpy(float) for k in ['close','amount','volume','segment_id']};flags={k:g[k].eq(True).to_numpy(bool) for k in ['observed_bar','synthetic_event_bar','source_invalid','price_eligible','volume_eligible']}
  code=np.full(len(calendar),2,dtype=np.int8)
  for j in np.flatnonzero(present):
   if not flags['observed_bar'][j] or flags['synthetic_event_bar'][j]:code[j]=3;continue
   if flags['source_invalid'][j] or not math.isfinite(v['close'][j]) or v['close'][j]<=0:code[j]=4;continue
   a,b=v['amount'][j],v['volume'][j]
   if math.isfinite(a) and math.isfinite(b) and min(a,b)>=0 and (a==0 or b==0):code[j]=1;continue
   if not flags['price_eligible'][j]:code[j]=4;continue
   code[j]=0 if flags['volume_eligible'][j] and math.isfinite(a) and math.isfinite(b) and a>0 and b>0 else 5
  v['code']=code;cache[sid]=v;qsource[sid]=p
 return cache[sid]
def expected_label(e,end):
 q=quote(e['sid']);s=ix[e['day']];segment=float(e['source_segment']);valid=[];halt=[];bad=None;reason=None;m=None;r=None
 if q['code'][s]!=0 or not math.isfinite(q['segment_id'][s]) or q['segment_id'][s]!=segment:bad=s;reason='SIGNAL_QUOTE_NOT_VALID_'+str(int(q['code'][s]))
 else:
  for j in range(s+1,end+1):
   code=int(q['code'][j])
   if not math.isfinite(q['segment_id'][j]) or q['segment_id'][j]!=segment:bad=j;reason='MISSING_QUOTE' if code==2 else 'PRICE_DOMAIN_UNKNOWN_OR_CHANGED';break
   if code==1:halt.append(calendar[j]);continue
   if code:bad=j;reason={2:'MISSING_QUOTE',3:'NOT_OBSERVED_OR_SYNTHETIC',4:'INVALID_SOURCE_PRICE',5:'UNKNOWN_TRADE_QUOTE'}[code];break
   valid.append(calendar[j])
   if len(valid)==5:m=j;r=q['close'][j]/q['close'][s]-1;break
 return dict(valid_close_days=valid,no_trade_days=halt,first_bad_day=None if bad is None else calendar[bad],first_bad_reason=reason,maturity_day=None if m is None else calendar[m],return5=r,signal_to_maturity_market_sessions=None if m is None else m-s,source_max_used_day=calendar[m if m is not None else bad if bad is not None else end],final_status='MATURED' if m is not None else 'SIGNAL_QUOTE_UNKNOWN' if bad==s else 'HORIZON_AMBIGUOUS' if bad is not None else 'RIGHT_CENSORED_NOT_FIVE',label_observation_end=calendar[end])
def qtile(points,q):
 if not points:return None
 weights=defaultdict(F)
 for r,w in points:weights[r]+=w
 cumulative=F();threshold=q*sum(weights.values(),F())
 for r,w in sorted(weights.items()):
  cumulative+=w
  if cumulative>=threshold:return float(r)
 raise AssertionError('cdf')
def stats(batches):
 groups=[v for v in batches.values() if v];B=len(groups);N=sum(map(len,groups))
 if not B:return dict(batch_count=0,events=0,median=None,positive_fraction=None,p10=None,negative_mean=None,mean=None,effective_weighted_events=None,max_event_weight=None,min_batch_size=None,max_batch_size=None,delayed_events=0,max_signal_to_maturity_sessions=None)
 points=[(e['return5'],F(1,B*len(g))) for g in groups for e in g];neg=[(r,w) for r,w in points if r<0];nw=sum((w for r,w in neg),F());weights=[w for r,w in points]
 return dict(batch_count=B,events=N,median=qtile(points,F(1,2)),positive_fraction=float(sum((w for r,w in points if r>0),F())),p10=qtile(points,F(1,10)),negative_mean=sum(float(w)*r for r,w in neg)/float(nw) if nw else None,mean=sum(float(w)*r for r,w in points),effective_weighted_events=1/float(sum((w*w for w in weights),F())),max_event_weight=float(max(weights)),min_batch_size=min(map(len,groups)),max_batch_size=max(map(len,groups)),delayed_events=sum(bool(e['no_trade_days']) for g in groups for e in g),max_signal_to_maturity_sessions=max(e['signal_to_maturity_market_sessions'] for g in groups for e in g))
def cmpstats(actual,expected):
 for k,v in expected.items():eq(actual[k],v,'daily_stat_'+k)
# Exercise actual producer nested label function against ten independent prefix cases.
root=ast.parse(script.read_text());main=next(n for n in root.body if isinstance(n,ast.FunctionDef) and n.name=='main');node=next(n for n in main.body if isinstance(n,ast.FunctionDef) and n.name=='label')
fixturecal=[str(d.date()) for d in pd.bdate_range('2020-01-02',periods=12)];base=dict(signal_id='fixture',window='w',day=fixturecal[0],sid='s',sector='i',union_signal_kind='core',original_I_root='r',original_I_root_start=fixturecal[0],source_segment=0,evaluation_window=True)
def fixture():return dict(close=np.arange(100.,112.),amount=np.ones(12),volume=np.ones(12),segment_id=np.zeros(12),code=np.zeros(12,dtype=int),source='fixture',source_sha256='fixture')
def call(q,e,cut):
 ns=dict(np=np,math=math,calendar=fixturecal,ix={d:i for i,d in enumerate(fixturecal)},quotes=lambda sid:q)
 exec(compile(ast.Module(body=[node],type_ignores=[]),'producer_label_fixture','exec'),ns)
 return ns['label'](e,cut)
synthetic=[]
def test(name,ok):assert ok,name;synthetic.append(dict(name=name,passed=True))
q=fixture();test('exclude_signal_and_four_pending',call(q,base,4)['maturity_day'] is None and len(call(q,base,4)['valid_close_days'])==4);test('fifth_close_first_publication',call(q,base,5)['maturity_day']==fixturecal[5])
q=fixture();q['code'][2]=1;test('known_no_trade_delays',call(q,base,5)['maturity_day'] is None and call(q,base,6)['maturity_day']==fixturecal[6] and call(q,base,6)['no_trade_days']==[fixturecal[2]])
q=fixture();q['code'][2]=2;q['segment_id'][2]=np.nan;test('missing_not_silently_skipped',call(q,base,11)['final_status']=='HORIZON_AMBIGUOUS' and call(q,base,11)['first_bad_reason']=='MISSING_QUOTE')
q=fixture();q['segment_id'][2]=1;test('source_change_ambiguous',call(q,base,11)['first_bad_reason']=='PRICE_DOMAIN_UNKNOWN_OR_CHANGED')
q=fixture();q['code'][2]=3;test('synthetic_not_observed_ambiguous',call(q,base,11)['first_bad_reason']=='NOT_OBSERVED_OR_SYNTHETIC')
q=fixture();q['code'][0]=1;test('signal_bad_quote_separate',call(q,base,11)['final_status']=='SIGNAL_QUOTE_UNKNOWN')
q=fixture();old=call(q,base,5);q['close'][6:]=-999;test('future_quote_perturbation_prefix_exact',call(q,base,5)==old)
q=fixture();e=dict(base,day=fixturecal[5]);test('same_day_maturity_new_signal_count_zero',call(q,base,5)['maturity_day']==fixturecal[5] and call(q,e,5)['valid_close_days']==[])
test('empty_batches_NULL_not_zero',stats({fixturecal[i]:[] for i in range(5)})['median'] is None and stats({})['batch_count']==0)
test('exact_half_inverse_CDF_left_value',qtile([(-1.,F(1,2)),(1.,F(1,2))],F(1,2))==-1.)
test('cross_batch_equal_weight_sparse_day',stats({'a':[dict(return5=-1.,no_trade_days=[],signal_to_maturity_market_sessions=5)],'b':[dict(return5=1.,no_trade_days=[],signal_to_maturity_market_sessions=5) for _ in range(100)]})['positive_fraction']==.5)
views={'2022_weak':('2022-01-04','2022-12-30','2022_2024'),'2024_recovery':('2024-09-02','2024-11-29','2022_2024'),'strong':('2025-07-01','2026-06-30','strong')};reports={};outputsha={};age_omissions=[]
for view,(lo,hi,sourcewindow) in views.items():
 ev=read(P/view/'EVENTS.json');daily=read(P/view/'DAILY_FEEDBACK.json');future=read(P/view/'EVALUATION_ONLY_NEXT_DAY.json');outputsha[view]={name:sha(P/view/name) for name in ['EVENTS.json','DAILY_FEEDBACK.json','EVALUATION_ONLY_NEXT_DAY.json']};end=min(ix[hi]+5,len(calendar)-1)
 expectedids={e['signal_id'] for e in signals if e['window']==sourcewindow and e['day']<=hi};assert {e['signal_id'] for e in ev}==expectedids
 issued=defaultdict(list);mature=defaultdict(list)
 for e in ev:
  original=sig[e['signal_id']]
  for k in ['signal_id','window','day','sid','sector','union_signal_kind','original_I_root','original_I_root_start','source_segment','evaluation_window']:assert e[k]==original[k]
  x=expected_label(original,end)
  for k,v in x.items():
   if k=='return5':eq(e[k],v,'all_event_return5')
   else:assert e[k]==v,(e['signal_id'],k,e[k],v)
  assert e['quote_source']==qsource[e['sid']] and e['quote_source_sha256']==manifest['sources'][qsource[e['sid']]];checks['all_event_source_dates_status']+=1
  issued[e['day']].append(e)
  if e['maturity_day']:mature[e['maturity_day']].append(e)
 for row,fo in zip(daily,future):
  j=ix[row['day']];days=calendar[max(0,j-4):j+1];expected=stats({d:mature[d] for d in days});cmpstats(row,expected)
  assert row['lookback_first']==days[0] and row['lookback_last']==row['day'];feedback='NO_MATURE_DATA' if expected['median'] is None else 'positive' if expected['median']>0 else 'negative' if expected['median']<0 else 'zero';assert row['feedback_state']==feedback;assert row['new_mature_events']==len(mature[row['day']]) and row['new_signal_events']==len(issued[row['day']]);checks['fixed_calendar_asof_feedback']+=1
  prior=[d for d,z in mature.items() if z and d<=row['day']];latest=max(prior,default=None)
  if latest is not None and all(not mature[d] for d in days):age_omissions.append(dict(view=view,day=row['day'],actual_latest_batch=latest,actual_age=j-ix[latest]))
  nd=calendar[j+1] if j+1<len(calendar) else None;target=[] if nd is None or nd>hi else issued[nd];known=[e for e in target if e['return5'] is not None];fs=stats({nd:known});status='OUTSIDE_TARGET_WINDOW' if nd is None or nd>hi else 'NO_TARGET_SIGNALS' if not target else 'NO_EVALUABLE_TARGETS' if not known else 'PARTIAL_TARGET_LABELS' if len(known)<len(target) else 'COMPLETE'
  assert fo['asof_day']==row['day'] and fo['target_signal_day']==nd and fo['status']==status and fo['feedback_state']==feedback and fo['evaluation_only'] is True;assert (fo['target_events'],fo['target_evaluable'],fo['target_missing'])==(len(target),len(known),len(target)-len(known))
  for a,b in [('future_cohort_median','median'),('future_cohort_positive_fraction','positive_fraction'),('future_cohort_p10','p10')]:eq(fo[a],fs[b],'next_day_evaluation_only_stats')
  checks['all_next_day_target_membership']+=1
 # Same declared circular block bootstrap from the independently verified future rows.
 rng=np.random.default_rng(20261104);N=len(future);diffs=[]
 for _ in range(1000):
  starts=rng.integers(0,N,size=math.ceil(N/5));sample=[future[(int(s)+k)%N] for s in starts for k in range(5)][:N];pos=[r['future_cohort_median'] for r in sample if r['feedback_state']=='positive' and r['future_cohort_median'] is not None];neg=[r['future_cohort_median'] for r in sample if r['feedback_state']=='negative' and r['future_cohort_median'] is not None]
  if pos and neg:diffs.append(float(np.mean(pos)-np.mean(neg)))
 assert len(diffs)==summary[view]['valid_bootstrap_resamples']
 if diffs:
  for a,b in zip(np.quantile(diffs,[.025,.975]),summary[view]['positive_minus_negative_bootstrap95']):eq(a,b,'fixed_bootstrap_1000_seed')
 else:assert summary[view]['positive_minus_negative_bootstrap95'] is None
 for st,g in summary[view]['next_day_groups'].items():
  sr=[r for r in future if r['feedback_state']==st];valid=[r for r in sr if r['future_cohort_median'] is not None];assert (g['asof_days'],g['evaluable_future_days'],g['target_events'],g['target_evaluable'],g['target_missing'])==(len(sr),len(valid),sum(r['target_events'] for r in sr),sum(r['target_evaluable'] for r in sr),sum(r['target_missing'] for r in sr));eq(g['mean_next_cohort_median'],None if not valid else np.mean([r['future_cohort_median'] for r in valid]),'summary_next_cohort_group');checks['future_group_membership']+=1
 reports[view]=dict(events_including_warmup=len(ev),evaluation_events=sum(lo<=e['day']<=hi for e in ev),market_days=len(daily),label_status_counts=dict(Counter(e['final_status'] for e in ev if lo<=e['day']<=hi)),bootstrap_valid_resamples=len(diffs),bootstrap95=summary[view]['positive_minus_negative_bootstrap95'])
 print('AUDIT_VIEW_DONE',view,len(ev),len(daily),flush=True)
assert sha(script)==manifest['script_sha256']
for view,files in outputsha.items():
 for name,h in files.items():assert sha(P/view/name)==h,'concurrent output change'
output=dict(status='PASS_WITH_SCOPE_LIMITS',checks=dict(checks),producer_code_sha256=manifest['script_sha256'],reviewer_code_sha256=sha(__file__),synthetic_prefix_cases=synthetic,real_views=reports,quote_sources=len(cache),reviewed_output_sha256=outputsha,asof_information_age_omissions=age_omissions,scope='All event identities against authorized SIGNALS input, all loaded original quote statuses/endpoints/returns, every daily weighted feedback and every next-day outcome-only target row, fixed bootstrap and summary groups. Upstream whole1709 qualification/root construction and tail mapping delegated to other reviewer; not claimed here.',limitations=['Code prefix fixtures test producer nested label; independent real labels use exact calendar-bounded raw quotes. All asof aggregation checks exclude later maturity dates even though offline outcome labels are stored separately.','Historical data availability remains declared proxy; this audit verifies causal observation indices, not real historical vendor arrival times.','Bootstrap code is circular moving blocks of5 sessions with wrap-around,1000,seed20261104; not independent trials or a deployment guarantee.','latest_batch_day/information_age are window-local; cases with older published data outside the empty5-session window are listed as a reporting omission, not a primary statistic error.','No risk gate, half-quantity policy, trading account, live action or source modification.'],account_events=0,new_policy=0)
(O/'AUDIT.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(status=output['status'],checks=checks,quote_sources=len(cache),synthetic_cases=len(synthetic),age_omissions=len(age_omissions)),indent=2))
