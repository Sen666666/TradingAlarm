"""Independent bounded saved-source audit; no account/price/signal imports."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import gzip,json,hashlib,time
getcontext().prec=90
O=Path(__file__).resolve().parent;T=O.parent;P=T/'carry_exit_responsibility_v1';Z=D(0);start=time.monotonic();SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(p)]=sha(p);return json.loads(Path(p).read_text())
def gz(p):
 SRC[str(p)]=sha(p)
 with gzip.open(p,'rt') as f:return json.load(f)
def near(a,b,tag):assert abs(D(a)-D(b))<D('.000001'),(tag,a,b)
freeze=read(P/'INPUT_FREEZE.json')
for p,h in freeze['sources'].items():assert sha(p)==h,(p,'source changed')
auditpath=T/'ma63_down_replenishment_review_v1/SAVED_PERIOD_WEALTH_AUDIT.json';assert sha(auditpath)=='915dc0b929b5201951354939b0ad1216cebd5a82d5407b5f09e22be8cc609a2b';prior=read(auditpath)
assert prior['status'].startswith('PASS_WITH_SCOPE')
master=read(T/'ma63_down_replenishment_v1/ALL_LAYER_PERIOD_WEALTH.json');spells={r['spell_id']:r for r in read(T/'ma63_down_replenishment_v1/ALL_SPELL_RESULTS.json')};selected={'DOWN_04','DOWN_05','DOWN_06'}
mother={(r['spell_id'],r['layer']):r for r in master if r['spell_id'] in selected and r['group']=='carry_at_previous_CLOSE'};traces=read(P/'ALL_CARRY_TRACE_ROWS.json');trace={(r['spell_id'],r['layer']):r for r in traces};assert len(mother)==len(trace)==len(traces)==241 and mother.keys()==trace.keys()
for k,m in mother.items():
 for field,v in m.items():assert trace[k][field]==v,(k,field,'mother differs')
sourcebook=T/'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/B.json.gz';b=gz(sourcebook);dp=sourcebook.parent/'daily.jsonl.gz';SRC[str(dp)]=sha(dp)
with gzip.open(dp,'rt') as f:ds=[json.loads(x) for x in f]
calendar=[r['at'][:10] for r in ds];assert len(calendar)==len(set(calendar))==726;di={d:i for i,d in enumerate(calendar)};dmap={r['at'][:10]:r for r in ds};terminal={r['id']:r for r in b['layers']};reqs=defaultdict(list);sells=defaultdict(list)
for r in b['audit']:
 if r['kind']=='pilot_layer_exit':
  for lid in r['layers']:reqs[lid].append(r)
for tr in b['trades']:
 if tr['side']=='sell':
  for part in tr['parts']:sells[part['layer']].append((tr,part))
requested=[];categories=Counter();summary=[];ca_crossings=[]
for k,r in trace.items():
 lid=r['layer'];sid=r['sid'];p=spells[r['spell_id']];before=p['previous_close']+' 15:10:00+08:00';end=p['end']+' 15:10:00+08:00';qq=next(x for x in dmap[p['previous_close']]['layers'] if x['id']==lid);assert qq['qty']==r['qty_at_boundary']>0
 known=[x for x in reqs[lid] if x['at']<=end];first=known[0] if known else None;assert r['first_layer_request']==first and r['request_reason_change_observations']==known
 cat='NO_LAYER_EXIT_REQUEST_BY_END' if first is None else 'ALREADY_REQUESTED_BEFORE_START' if first['at']<=before else 'FIRST_REQUEST_DURING_SPELL_MIXED_MONEY_UNKNOWN';assert r['timing_category']==cat;categories[cat]+=1
 assert r['broker_ack_timestamp']=='UNKNOWN_NOT_RECORDED_IN_SAVED_TRACE'
 if cat.startswith('FIRST_REQUEST_DURING'):
  assert r['pre_request_wealth'] is None and r['post_request_wealth'] is None and r['mixed_request_pre_post_money']=='UNKNOWN_NO_NEW_INTRASPELL_FINANCIAL_BOUNDARY'
 elif first is None:assert r['pre_request_wealth']==r['period_wealth'] and r['post_request_wealth'] is None
 else:assert r['post_request_wealth']==r['period_wealth'] and r['pre_request_wealth'] is None
 if first is None:continue
 nxt=calendar[di[first['at'][:10]]+1]+' 09:30:00+08:00';assert nxt==r['request_NEXT_OPEN'];later=[(tr,part) for tr,part in sells[lid] if tr['at']>first['at']];assert later and later[0][0]['at']==nxt
 live=next(x for x in dmap[first['at'][:10]]['layers'] if x['id']==lid);assert live['qty']>0
 cas=[x for x in b['audit'] if x['kind'] in ('split','split_fraction_floor_proxy') and x['sid']==sid and first['at']<x['at']<=nxt]
 if cas:ca_crossings.append(dict(key=k,events=cas));raise AssertionError(('CA crossing needs separate native units bridge',k))
 assert sum(part['shares'] for tr,part in later if tr['at']==nxt)==live['qty'],(k,'partial remains')
 assert all(tr['at']==nxt for tr,part in later) and terminal[lid]['closed']==nxt and terminal[lid]['qty']==0
 assert r['request_to_first_sell_sessions']==1 and r['first_actual_sell_at_request_NEXT_OPEN'] is True
 requested.append(dict(spell_id=k[0],layer=lid,sid=sid,request_at=first['at'],next_OPEN=nxt,remaining_qty_at_request_CLOSE=live['qty'],actual_sell_part_qty_next_OPEN=sum(part['shares'] for tr,part in later)))
completion=read(P/'FULL_EXIT_COMPLETION_SUPPLEMENT.json');assert completion['source_book_sha256']==sha(sourcebook) and completion['requested_rows']==completion['closed_all_next_OPEN']==len(requested)==200 and not completion['not_closed_all_next_OPEN'] and completion['ACK_timestamp']=='UNKNOWN_NOT_SAVED'
assert {(r['spell_id'],r['layer']) for r in completion['rows']}=={(r['spell_id'],r['layer']) for r in requested}
for name in sorted(selected):
 rr=[r for r in traces if r['spell_id']==name];wealth=sum((D(r['period_wealth']) for r in rr),Z);pos=sum((D(r['period_wealth']) for r in rr if D(r['period_wealth'])>0),Z);neg=sum((D(r['period_wealth']) for r in rr if D(r['period_wealth'])<0),Z)
 for key,v in [('wealth',wealth),('positive_wealth',pos),('negative_wealth',neg)]:near(v,spells[name]['old'][key],(name,key))
 summary.append(dict(spell_id=name,carry_rows=len(rr),carry_wealth=wealth,positive_wealth=pos,negative_wealth=neg,requested_observations=sum(r['first_layer_request'] is not None for r in rr)))
ctx=read(P/'CUTOFF2023_WINNER_CONTEXT_SUPPLEMENT.json');cp=Path(ctx['source']);assert sha(cp)==ctx['source_sha256'];life=read(cp);assert len(life)==1557 and all(r['original_money_cutoff']=='2023-12-29' for r in life);lm={r['layer']:r for r in life};stockchecks=[]
for stock in ctx['stocks']:
 sid=stock['sid'];group={'DOWN_05','DOWN_06'} if stock['group']=='negative_focus' else {'DOWN_04'};rr=[r for r in traces if r['sid']==sid and r['spell_id'] in group];ids=sorted({r['layer'] for r in rr});assert ids==stock['selected_carry_unique_layer_ids'];allstock=[r for r in life if r['sid']==sid]
 for field,v in [('period_carry_wealth',sum((D(r['period_wealth']) for r in rr),Z)),('selected_carry_lifetime_to2023_net',sum((D(lm[i]['net']) for i in ids),Z)),('full_stock_original2023cutoff_net',sum((D(r['net']) for r in allstock),Z))]:near(stock[field],v,(sid,field))
 assert stock['stock_all_layer_ids']==[r['layer'] for r in allstock] and stock['full_stock_all2022_2023_layers']==len(allstock)
 for item in stock['selected_layers']:
  original=lm[item['layer']];assert original['sid']==sid
  for field,v in item.items():assert original[field]==v,(sid,item['layer'],field)
 stockchecks.append(dict(sid=sid,period_observations=len(rr),deduplicated_selected_layers=ids,period_carry_wealth=stock['period_carry_wealth'],selected2023cutoff_net=stock['selected_carry_lifetime_to2023_net'],whole_stock2023cutoff_net=stock['full_stock_original2023cutoff_net']))
assert set(x['sid'] for x in stockchecks)=={'603083.SH','301128.SZ','688003.SH','920808.BJ','002315.SZ'}
result=dict(status='PASS_WITH_SCOPE_ALL_CARRY_SOURCE_REQUEST_NEXTOPEN_FULL_CLOSE_AND_2023_CONTEXT',source_period_audit_reused=str(auditpath),source_period_audit_sha256=sha(auditpath),carry_observations=241,spell_summaries=summary,requested_observations_full_remaining_closed_next_OPEN=200,observed_multi_session_waits=0,actual_CA_crossings_request_to_fill=ca_crossings,timing_categories=dict(categories),ACK='UNKNOWN_NO_INDEPENDENT_BROKER_ACK_TIMESTAMP',mixed_pre_post_request_money='UNKNOWN_FOR_ALL_FIRST_REQUEST_DURING_SPELL_ROWS; no allocation or whole-PnL-to-before assertion',stock2023cutoff_checks=stockchecks,new_accounts=0,new_price_reads=0,new_signals_or_models=0,scope='Source amounts bound to prior 915dc0b9 audit, not a second valuation engine. Repeated layer across spells is separate period observation; lifetime context deduplicates IDs. Native daily execution proxy only, no real-exchange certification, no gap-PnL isolation, no stop guarantee, no new exit rule or avoidable-loss conclusion.',source_sha256=SRC,checker_sha256=sha(__file__),seconds=time.monotonic()-start)
(O/'AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n');(O/'CHECKED_REQUESTED_ROWS.json').write_text(json.dumps(requested,ensure_ascii=False,indent=2)+'\n');print(result['status'],sha(O/'AUDIT.json'),flush=True)
