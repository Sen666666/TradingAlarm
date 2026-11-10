"""Thin primary actual execution order-request timing join; no peak changes."""
from pathlib import Path
from collections import defaultdict,Counter
from datetime import datetime
from bisect import bisect_left,bisect_right
import json,gzip,hashlib

O=Path(__file__).parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');SRC={}


def read(p,gz=False,lines=False):
 SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)


def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')


def dt(x):return datetime.fromisoformat(x)


def dist(vals):
 a=sorted(v for v in vals if v is not None)
 def quant(q):
  if not a:return None
  k=q*(len(a)-1);i=int(k);return a[i]+(a[min(i+1,len(a)-1)]-a[i])*(k-i)
 return dict(known=len(a),unknown=len(vals)-len(a),p10=quant(.1),median=quant(.5),p90=quant(.9))


def summary(rr):
 return dict(layers=len(rr),closed_actual_request_known=sum(x['primary_actual_order_request_at'] is not None for x in rr),
  open_no_executed_request=sum(x['terminal_equity_state']=='open' for x in rr),
  primary_request_before_layer_entry=sum(x['request_clock_status']=='ORDER_CREATED_BEFORE_LAYER_ENTRY' for x in rr),
  entry_to_primary_request_held_closes=dist([x['entry_to_primary_request_held_CLOSE_observations'] for x in rr]),
  request_to_fill_native_session_steps=dist([x['request_to_fill_native_session_steps'] for x in rr]),
  next_native_session_OPEN=sum(x['actual_exit_is_next_native_session_OPEN'] is True for x in rr),
  later_than_next_native_session=sum(x['request_to_fill_native_session_steps'] is not None and x['request_to_fill_native_session_steps']>1 for x in rr),
  request_to_fill_session_count_frequencies=dict(Counter(x['request_to_fill_native_session_steps'] for x in rr if x['request_to_fill_native_session_steps'] is not None)),
  request_to_fill_calendar_days=dist([x['request_to_fill_calendar_days'] for x in rr]))


result={};validation={}
for ref,pair in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),('strong',B/'pvr_pool_feasibility/runs/2025_26/pair')]:
 rows=read(O/(ref+'_LAYERS.json'));ds=read(pair/'daily.jsonl.gz',gz=True,lines=True);book=read(pair/'B.json.gz',gz=True)
 times=[dt(x['at']) for x in ds];ix={x['at'][:10]:i for i,x in enumerate(ds)}
 nativeheld={x['at']:{y['id'] for y in x['layers']} for x in ds}
 fills={a['receipt']['receipt_id']:a for a in book['audit'] if a['kind']=='fill' and a['receipt']['side']=='sell'}
 requests={a['event_id']:a for a in book['audit'] if a['kind']=='exit_request'}
 exact={}
 for t in book['trades']:
  if t['side']!='sell':continue
  f=fills[t['receipt_id']];req=requests[f['order_id']]
  for p in t['parts']:assert p['layer'] not in exact;exact[p['layer']]=(f['order_id'],req['at'],t['at'])
 out=[]
 for x in rows:
  y=dict(layer=x['layer'],sid=x['sid'],action=x['action'],actual_exit_class=x['actual_exit_class'],terminal_equity_state=x['terminal_equity_state'],
    opened_at=x['opened'],primary_actual_order_id=None,primary_actual_order_request_at=None,actual_exit_at=None,
    entry_to_primary_request_held_CLOSE_observations=None,entry_to_primary_request_market_date_steps=None,
    request_to_fill_native_session_steps=None,request_to_fill_intervening_CLOSE_observations=None,
    request_to_fill_calendar_days=None,request_to_fill_elapsed_hours=None,actual_exit_is_next_native_session_OPEN=None,
    request_clock_status='OPEN_NO_EXECUTED_REQUEST')
  if x['terminal_equity_state']=='closed':
   oid,request,fill=exact[x['layer']];assert (oid,request,fill)==(x['actual_sale_parts'][0]['order_id'],x['actual_sale_parts'][0]['order_created_at'],x['actual_sale_parts'][0]['at'])
   start,r,f=dt(x['opened']),dt(request),dt(fill);assert r<f
   y.update(primary_actual_order_id=oid,primary_actual_order_request_at=request,actual_exit_at=fill,
       request_to_fill_native_session_steps=ix[fill[:10]]-ix[request[:10]],
       request_to_fill_intervening_CLOSE_observations=bisect_left(times,f)-bisect_right(times,r),
       request_to_fill_calendar_days=(f.date()-r.date()).days,request_to_fill_elapsed_hours=(f-r).total_seconds()/3600)
   y['actual_exit_is_next_native_session_OPEN']=y['request_to_fill_native_session_steps']==1 and (f.hour,f.minute)==(9,30)
   if r<start:y['request_clock_status']='ORDER_CREATED_BEFORE_LAYER_ENTRY'
   else:
    selected=ds[bisect_left(times,start):bisect_right(times,r)]
    assert all(x['layer'] in nativeheld[d['at']] for d in selected)
    y.update(entry_to_primary_request_held_CLOSE_observations=len(selected),
       entry_to_primary_request_market_date_steps=ix[request[:10]]-ix[x['opened'][:10]],request_clock_status='EXACT_ACTUAL_ORDER_PRIMARY')
   assert y['request_to_fill_native_session_steps']>=1 and y['request_to_fill_intervening_CLOSE_observations']==y['request_to_fill_native_session_steps']-1
  out.append(y)
 save(ref+'_REQUEST_CLOCK_JOIN.json',out)
 scopes={'all':out}
 if ref=='2022_2024':
  scopes.update(two_year=[x for x in out if x['opened_at'][:10]<'2024-01-01'],post303=[x for x in out if '2024-10-09'<=x['opened_at'][:10]<='2024-12-31'])
 for scope,rr in scopes.items():
  byaction={a:summary([x for x in rr if x['action']==a]) for a in sorted({x['action'] for x in rr})}
  byexit={a:summary([x for x in rr if x['actual_exit_class']==a]) for a in sorted({x['actual_exit_class'] for x in rr})}
  result[ref+'_'+scope]=dict(all=summary(rr),by_action=byaction,by_actual_exit=byexit)
 validation[ref]=dict(actual_order_request_identity_rechecked=True,original_LAYER_bytes_unchanged_SHA=SRC[str(O/(ref+'_LAYERS.json'))],
   no_earlier_pilot_selection=True,all_primary_entry_to_request_CLOSEs_actually_owned=True)
save('REQUEST_CLOCK_SUMMARY.json',result)
save('REQUEST_CLOCK_VALIDATION.json',dict(passed=True,refs=validation,sources=SRC,
  definitions={'entry_to_request':'Count original native CLOSE observations opened_at<=CLOSE<=actual execution order_created request; includes requestCLOSE if still held.',
   'request_to_fill_steps':'Index(fill market date)-index(order request market date); normal next native session09:30 OPEN has1 step and0 interveningCLOSEs.',
   'primary':'Actual fill.audit.order_id -> original exit_request.event_id. Earlier allpilot same-reason requests are never chosen as primary.',
   'open':'No actual executed exit means primary execution-request timing unknown; pending or earlier pilots not substituted.'},
  no_close_peak_changes=True,no_models_or_accounts=True,
  limitations=['Native market-session delay describes elapsed observed execution, not a legal-fillability guarantee or identified cause of any wait.',
    'Calendar-day/elapsed-hour gaps reported separately; holidays/weekends are not counted as extra trading observations.',
    'Original raw close peak remains unclamped and may be negative; nonnegativeMFE remains only a secondary field.']))
print(json.dumps(result,ensure_ascii=False,indent=2))
