"""Independent thin native-held-close and actual exit-request audit; no price features."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from datetime import datetime
from collections import defaultdict,Counter
import gzip,json,hashlib,math
import pandas as pd
import numpy as np
getcontext().prec=70
P=Path(__file__).resolve().parents[1]/'holding_exit';O=Path(__file__).resolve().parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');Z=D(0);checks=defaultdict(int)
def read(p,lines=False):
 p=Path(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(s) for s in f] if lines else json.load(f)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def n(x):return D(str(x))
def dt(x):return datetime.fromisoformat(x)
def eq(a,b,key):
 assert abs(n(a)-n(b))<D('1e-17'),(key,a,b)
 checks[key]+=1
def quant(v,p):
 s=sorted(v);i=p*(len(s)-1);a=math.floor(i);b=math.ceil(i);return s[a]+(s[b]-s[a])*(i-a)
def fq(a,b,k):
 if a is None or b is None:assert a is None and b is None,(k,a,b)
 else:assert abs(float(a)-float(b))<1e-10*max(1,abs(float(a)),abs(float(b))),(k,a,b)
 checks[k]+=1
sources={**read(P/'SOURCE_SHA256.json'),**read(P/'REQUEST_CLOCK_VALIDATION.json')['sources']}
for path,h in sources.items():assert sha(path)==h,path;checks['source_SHA']+=1
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};frames={};stale=0;refs={};samples=[];ALL={}
def quote(sid,day,exact=False):
 if sid not in frames:
  path=sm[sid]['refs']['facts'];assert sources[path]==sm[sid]['output_sha256'][path];frames[sid]=pd.read_parquet(path,columns=['close','raw_close','factor','segment_id'])
 f=frames[sid];day=pd.Timestamp(day)
 if exact and day not in f.index:return None
 j=f.index.searchsorted(day,side='right')-1;assert j>=0;r=f.iloc[j];assert f.index[j]<=day
 assert math.isclose(float(r.raw_close)*float(r.factor),float(r.close),rel_tol=1e-10,abs_tol=1e-10)
 return dict(raw=n(r.raw_close),signal=n(r.close),factor=n(r.factor),segment=None if pd.isna(r.segment_id) else str(float(r.segment_id)),day=str(f.index[j].date()))
for ref,root in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),('strong',B/'pvr_pool_feasibility/runs/2025_26/pair')]:
 rows=read(P/(ref+'_LAYERS.json'));rm={x['layer']:x for x in rows};rclock={x['layer']:x for x in read(P/(ref+'_REQUEST_CLOCK_JOIN.json'))};book=read(root/'B.json.gz');daily=read(root/'daily.jsonl.gz',True);times=[dt(d['at']) for d in daily];dateidx={d['at'][:10]:j for j,d in enumerate(daily)};native={x['id']:x for x in book['layers']};buys={t['layer']:t for t in book['trades'] if t['side']=='buy'};original={x['layer']:x for x in read(B/f'risk_constraints/ma63_information_diagnostic_v1/{ref}_ENTRIES.json')}
 fills={a['receipt']['receipt_id']:a for a in book['audit'] if a['kind']=='fill' and a['receipt']['side']=='sell'};requests={a['event_id']:a for a in book['audit'] if a['kind']=='exit_request'};pilots=defaultdict(list);sales=defaultdict(list)
 for a in book['audit']:
  if a['kind']=='pilot_layer_exit':
   for lid in a['layers']:pilots[lid].append(a)
 for t in book['trades']:
  if t['side']=='sell':
   for part in t['parts']:sales[part['layer']].append((t,part))
 assert all(len(v)==1 for v in sales.values())
 expected={lid:dict(count=0,U=None,W=None,segments={}) for lid in rm};observations=defaultdict(list);stale_ref=0
 for d in daily:
  total=Z
  for l in d['layers']:
   lid=l['id'];x=rm[lid];assert l['qty']>0 and dt(x['opened'])<=dt(d['at']) and (not x['closed'] or dt(d['at'])<dt(x['closed']));eq(-n(l['cash']),x['cost'],'held_no_partial_basis')
   q=quote(x['sid'],d['at'][:10]);value=D(l['qty'])*q['raw'];total+=value;u=value-n(x['cost']);w=n(l['cash'])+value+n(l['dividend']);stale_ref+=q['day']!=d['at'][:10];point=dict(at=d['at'],quote_day=q['day'],quantity=l['qty'],raw_close=q['raw'],signal_close=q['signal'],remaining_basis=n(x['cost']),unrealized=u,cumulative_cash=n(l['cash']),recognized_dividend_AR=n(l['dividend']),economic_wealth=w)
   z=expected[lid];z['count']+=1;observations[lid].append((d['at'],l))
   if z['U'] is None or u>z['U']['unrealized']:z['U']=point
   if z['W'] is None or w>z['W']['economic_wealth']:z['W']=point
   seg=q['segment'] or 'UNKNOWN'
   if seg not in z['segments'] or q['signal']>z['segments'][seg]['signal_close']:z['segments'][seg]=point
   checks['all_native_held_point']+=1
  eq(total,d['inventory'],'native_inventory')
 for lid,x in rm.items():
  e=original[lid];z=expected[lid];assert all(x[k]==v for k,v in e.items());assert z['count']==x['held_close_observations'];checks['all_holding_count']+=1
  for target,value in [('held_close_peak_unrealized',z['U']),('held_close_peak_wealth',z['W'])]:
   actual=x[target];assert (actual is None)==(value is None)
   if value:
    for k,v in value.items():
     if k in ['at','quote_day','quantity']:assert actual[k]==v
     else:eq(actual[k],v,'all_peak_point_value')
    checks['all_peak_point_clock_identity']+=1
  assert set(x['signal_close_peak_by_segment'])==set(z['segments'])
  for seg,p in z['segments'].items():assert x['signal_close_peak_by_segment'][seg]['at']==p['at'];eq(x['signal_close_peak_by_segment'][seg]['signal_close'],p['signal_close'],'all_signal_segment_peak')
  closed=bool(sales[lid]);assert closed==(x['terminal_equity_state']=='closed')==(x['qty']==0);cost=n(x['cost']);end=x['closed'] if closed else daily[-1]['at'];assert x['holding_end_at']==end and x['holding_end_kind']==('actual_sale_OPEN' if closed else 'right_censored_original_cutoff_CLOSE');assert x['calendar_days_to_actual_exit_or_cutoff']==(dt(end).date()-dt(x['opened']).date()).days;fq(x['actual_elapsed_calendar_days'],(dt(end)-dt(x['opened'])).total_seconds()/86400,'all_elapsed_days')
  eq(x['peak_held_close_unrealized_per_own_buycash'],z['U']['unrealized']/cost,'all_unclamped_peak_ratio');eq(x['peak_held_close_wealth_per_own_buycash'],z['W']['economic_wealth']/cost,'all_wealth_peak_ratio');eq(x['held_close_MFE_unrealized_nonnegative_yuan'],max(Z,z['U']['unrealized']),'secondary_nonnegative_only');assert x['held_close_peak_unrealized_state']==('positive' if z['U']['unrealized']>0 else 'nonpositive');assert x['holding_scale_vs_five']==('no_held_close' if not z['count'] else 'at_most_five_actual_held_closes' if z['count']<=5 else 'more_than_five_actual_held_closes')
  fillq=quote(x['sid'],x['opened'][:10],True);comparable=fillq is not None and fillq['segment'] is not None and set(z['segments'])=={fillq['segment']};assert x['signal_price_domain_comparable']==comparable
  if comparable:
   eq(x['fill_price_coordinate']['execution_signal_price'],n(buys[lid]['price'])*fillq['factor'],'fill_signal_coordinate');p=z['segments'][fillq['segment']];eq(x['comparable_price_MFE_ratio'],p['signal_close']/(n(buys[lid]['price'])*fillq['factor'])-1,'all_price_MFE_ratio');assert x['comparable_signal_price_peak']['at']==p['at']
  else:assert x['comparable_price_MFE_ratio'] is None
  actualreasons=sorted({part['reason'] for t,part in sales[lid]});assert x['actual_exit_reason_set']==actualreasons;assert x['actual_exit_class']==('OPEN_NO_ACTUAL_EXIT' if not actualreasons else actualreasons[0] if len(actualreasons)==1 else 'MIXED:'+'|'.join(actualreasons));checks['all_actual_exit_reason_set']+=1
  c=rclock[lid];assert (c['sid'],c['action'],c['opened_at'],c['actual_exit_class'],c['terminal_equity_state'])==(x['sid'],x['action'],x['opened'],x['actual_exit_class'],x['terminal_equity_state'])
  lifecycle=[dict(at=z['W']['at'],wealth=z['W']['economic_wealth'],point_kind='actual_held_CLOSE')]
  if closed:
   t,p=sales[lid][0];order=fills[t['receipt_id']]['order_id'];req=requests[order];assert req['sid']==x['sid'] and dt(req['at'])<dt(t['at']);assert c['primary_actual_order_id']==order and c['primary_actual_order_request_at']==req['at'] and c['actual_exit_at']==t['at'];sp=x['actual_sale_parts'][0];assert (sp['at'],sp['reason'],sp['shares'],sp['net_cash'],sp['order_id'],sp['order_created_at'])==(t['at'],p['reason'],p['shares'],p['net_cash'],order,req['at']);eq(n(p['net_cash'])-cost,native[lid]['cash'],'closed_cash_bridge');eq(n(native[lid]['cash'])+n(native[lid]['dividend']),x['net'],'closed_cash_AR_net')
   holdbefore=[s for s,l in observations[lid] if dt(s)<=dt(req['at'])];between=[s for s,l in observations[lid] if dt(req['at'])<dt(s)<dt(t['at'])];steps=dateidx[t['at'][:10]]-dateidx[req['at'][:10]];assert c['request_clock_status']=='EXACT_ACTUAL_ORDER_PRIMARY' and c['entry_to_primary_request_held_CLOSE_observations']==len(holdbefore) and c['request_to_fill_intervening_CLOSE_observations']==len(between)==steps-1 and c['request_to_fill_native_session_steps']==steps;assert z['count']==len(holdbefore)+len(between);checks['all_closed_request_holding_identity']+=1
   assert c['entry_to_primary_request_market_date_steps']==dateidx[req['at'][:10]]-dateidx[x['opened'][:10]];assert c['actual_exit_is_next_native_session_OPEN']==(steps==1 and (dt(t['at']).hour,dt(t['at']).minute)==(9,30));assert c['request_to_fill_calendar_days']==(dt(t['at']).date()-dt(req['at']).date()).days;fq(c['request_to_fill_elapsed_hours'],(dt(t['at'])-dt(req['at'])).total_seconds()/3600,'all_request_elapsed_hours')
   candidates=sorted({a['at'] for a in pilots[lid] if a['reason']==p['reason'] and dt(a['at'])<dt(t['at'])});assert sp['matching_specific_layer_reason_request_times']==candidates
   lifecycle.append(dict(at=end,wealth=n(x['net']),point_kind='actual_final_sale_OPEN_including_known_AR'))
  else:
   assert all(c[k] is None for k in ['primary_actual_order_id','primary_actual_order_request_at','actual_exit_at','entry_to_primary_request_held_CLOSE_observations','request_to_fill_native_session_steps','request_to_fill_intervening_CLOSE_observations']);assert c['request_clock_status']=='OPEN_NO_EXECUTED_REQUEST'
  best=max(lifecycle,key=lambda p:p['wealth']);assert x['lifecycle_peak_known_wealth']['at']==best['at'] and x['lifecycle_peak_known_wealth']['point_kind']==best['point_kind'];eq(x['lifecycle_peak_known_wealth']['wealth'],best['wealth'],'lifecycle_peak_value');eq(x['lifecycle_peak_known_wealth_per_buycash'],best['wealth']/cost,'lifecycle_peak_ratio')
 for reason,predicate in [('negative_unclamped_peak',lambda x:n(x['held_close_peak_unrealized']['unrealized'])<0),('delayed_actual_exit',lambda x:rclock[x['layer']]['request_to_fill_native_session_steps'] is not None and rclock[x['layer']]['request_to_fill_native_session_steps']>1),('open_right_censor',lambda x:x['qty']>0),('dividend_peak_differs',lambda x:x['held_close_peak_wealth']['at']!=x['held_close_peak_unrealized']['at']),('multiple_specific_requests',lambda x:bool(x['actual_sale_parts']) and len(x['actual_sale_parts'][0]['matching_specific_layer_reason_request_times'])>1)]:
  cases=sorted((x for x in rows if predicate(x)),key=lambda x:x['layer'])
  if cases:
   x=cases[0];samples.append(dict(ref=ref,reason=reason,layer=x['layer'],sid=x['sid'],opened=x['opened'],closed=x['closed'],native_peak=x['held_close_peak_unrealized'],actual_order_clock=rclock[x['layer']]))
 # Deliberate same-date CP/I pilot collision, if present; never invent a sample.
 collision=[]
 for lid,pp in pilots.items():
  bytime=defaultdict(set)
  for p in pp:bytime[p['at']].add(p['reason'])
  if any(len(v)>1 for v in bytime.values()):collision.append(lid)
 if collision:
  lid=min(collision);samples.append(dict(ref=ref,reason='same_close_I_CP_pilot_collision',layer=lid,sid=rm[lid]['sid'],all_pilots=[dict(at=p['at'],reason=p['reason']) for p in pilots[lid]],actual_order_clock=rclock[lid]))
 splits=[a for a in book['audit'] if a['kind']=='split']
 for a in splits:
  candidates=[x for x in rows if x['sid']==a['sid'] and dt(x['opened'])<dt(a['at']) and (x['closed'] is None or dt(a['at'])<dt(x['closed']))]
  if candidates:
   x=min(candidates,key=lambda x:x['layer']);samples.append(dict(ref=ref,reason='held_across_actual_split',layer=x['layer'],sid=x['sid'],split=a,first_native=observations[x['layer']][0],last_native=observations[x['layer']][-1]));break
 refs[ref]=dict(layers=len(rows),closed_layers=sum(x['qty']==0 for x in rows),open_layers=sum(x['qty']>0 for x in rows),native_close_rows=len(daily),held_layer_observations=sum(z['count'] for z in expected.values()),stale_native_mark_points=stale_ref,delayed_layers=sum((c['request_to_fill_native_session_steps'] or 0)>1 for c in rclock.values()),same_close_CP_I_collision_layers=len(collision));ALL[ref]=rows
# Full monetary summaries and all group membership; no new holding-price feature work.
summ=read(P/'SUMMARY.json')
for ref,rows in ALL.items():
 scopes={'all':rows}
 if ref=='2022_2024':scopes.update(two_year=[x for x in rows if x['opened'][:10]<'2024-01-01'],post303=[x for x in rows if '2024-10-09'<=x['opened'][:10]<='2024-12-31'])
 def monetary(sr,g):
  closed=[x for x in sr if not x['qty']];opened=[x for x in sr if x['qty']]
  assert (g['layers'],g['stocks'],g['closed_layers'],g['open_layers'])==(len(sr),len({x['sid'] for x in sr}),len(closed),len(opened))
  sets={'net':sr,'closed_net':closed,'open_lifecycle_net':opened}
  for k,z in sets.items():eq(sum((n(x['net']) for x in z),Z),g[k],'summary_money')
  for pos,neg,z in [('positive_net','negative_net',sr),('closed_positive','closed_negative',closed),('open_positive','open_negative',opened)]:eq(sum((max(Z,n(x['net'])) for x in z),Z),g[pos],'summary_positive');eq(sum((min(Z,n(x['net'])) for x in z),Z),g[neg],'summary_negative')
  for a,b in [('cost','actual_buycash'),('strict_realized','strict_realized'),('open_unrealized','open_unrealized'),('recognized_dividend_AR','recognized_dividend_AR'),('buy_fee','buyfees'),('sell_fee','sellfees')]:eq(sum((n(x[a]) for x in sr),Z),g[b],'summary_financial_field')
  for key,field in [('held_close_observations','held_close_observations'),('calendar_days','calendar_days_to_actual_exit_or_cutoff'),('peak_held_close_unrealized_per_own_buycash','peak_held_close_unrealized_per_own_buycash'),('peak_held_close_wealth_per_own_buycash','peak_held_close_wealth_per_own_buycash')]:
   v=[float(x[field]) for x in sr if x[field] is not None];d=g[key];assert d['known']==len(v) and d['unknown']==len(sr)-len(v)
   if v:
    for q in [.1,.5,.9]:fq(d['quantiles'][str(q)],quant(v,q),'summary_holding_distribution')
   else:assert d['quantiles'] is None
  checks['complete_summary_group']+=1
 for name,sr in scopes.items():
  g=summ[ref+'_'+name];monetary(sr,g['all'])
  for key,groups in g.items():
   if key=='all':continue
   member=[]
   for group in groups:
    chosen=[x for x in sr if all(x[k]==v for k,v in group['labels'].items())];member.extend(x['layer'] for x in chosen);monetary(chosen,group)
   assert sorted(member)==sorted(x['layer'] for x in sr)
out=dict(status='PASS_WITH_SCOPE_LIMITS',checks=dict(checks),refs=refs,sample_cases=samples,source_sha256=sources,reviewed_output_sha256={f:sha(P/f) for f in ['2022_2024_LAYERS.json','strong_LAYERS.json','2022_2024_REQUEST_CLOCK_JOIN.json','strong_REQUEST_CLOCK_JOIN.json','SUMMARY.json','REQUEST_CLOCK_SUMMARY.json']},scope='All57213 original native held-layer mark points, all3436 counts/peaks/economic and comparable-price ratios, all3362 actually executed order-request clocks, all primary monetary groups. Purposive boundary cases from original book/daily retained; no rolling entry-price features recomputed.',limitations=['Primary is native held-CLOSE rawmark less remaining fee-inclusive basis, including explicitly dated stale marks; not intraday peak or achievable exit profit.','No nontrivial per-layer partial sale in this mother. Native held cash=-owncost checked at every point; this thin basis method is not generalized to partial books.','74 open layers right-censored and actual-request time stays unknown; pending/pilot requests are not actual executed exits.','Request delay is observed sessions, not its cause or a fillability guarantee. Exit reason is actual responsibility, not causal proof of loss.'],new_account=0,new_policy=0)
(O/'HOLDING_EXIT_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=str)+'\n');print(json.dumps(dict(status=out['status'],checks=checks,refs=refs,sample_cases=len(samples)),indent=2))
