"""Past-only A sell-realized/B completed-new-cohort feedback; no policy run."""
from collections import defaultdict
from decimal import Decimal as D, getcontext
from pathlib import Path
import importlib.util,json,gzip,hashlib,csv

getcontext().prec=60
O=Path(__file__).parent
E=O.parents[1]
T=E/'failure_no_progress/timeline'
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sp=importlib.util.spec_from_file_location('audited_saved_timeline_money',T/'analyze_timeline.py')
R=importlib.util.module_from_spec(sp);sp.loader.exec_module(R)
SRC={};Z=D(0);TOL=D('1e-17');ACTIONS=['first_actual_participation','add_to_existing_stock','fresh_reentry_after_actual_flat']


def n(v):return D(str(v))


def read(p,gz=False,lines=False):
 SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)


def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')


def close(a,b,k):assert abs(n(a)-n(b))<TOL,(k,a,b)


def state(v,count):return 'no_events' if not count else 'negative' if v<0 else 'positive' if v>0 else 'zero'


def values(ll,marks):
 real=sum((l['real'] for l in ll),Z);cash=sum((l['cash'] for l in ll),Z)
 basis=sum((l['basis'] for l in ll),Z);grossbasis=sum((l['gross_basis'] for l in ll),Z);feebasis=sum((l['buyfee_basis'] for l in ll),Z)
 mark=sum((D(l['q'])*marks[l['sid']][0] for l in ll if l['q']),Z);ar=sum((l['div'] for l in ll),Z)
 unreal=mark-basis;net=real+unreal+ar;close(net,cash+mark+ar,'cash/real/unreal/AR')
 return dict(layers=len(ll),stocks=len({l['sid'] for l in ll}),original_buycash=sum((l['cost'] for l in ll),Z),
  original_buygross=sum((l['gross'] for l in ll),Z),original_buyfee=sum((l['buyfee'] for l in ll),Z),
  net_trade_cash=cash,strict_realized=real,unrealized=unreal,recognized_dividend_AR=ar,recognized_wealth=net,
  current_market_value=mark,remaining_basis=basis,remaining_gross_basis=grossbasis,remaining_buyfee_basis=feebasis,
  consumed_buyfee=sum((l['buyfee']-l['buyfee_basis'] for l in ll),Z),actual_sellfee=sum((l['sellfee'] for l in ll),Z),
  active_layers=sum(l['q']>0 for l in ll),positive_unrealized=sum((max(Z,D(l['q'])*marks[l['sid']][0]-l['basis']) for l in ll if l['q']),Z),
  negative_unrealized=sum((min(Z,D(l['q'])*marks[l['sid']][0]-l['basis']) for l in ll if l['q']),Z))


def sell_feedback(pp):
 realized=sum((p['strict_realized'] for p in pp),Z)
 grosspnl=sum((p['gross_price_pnl'] for p in pp),Z);bf=sum((p['consumed_buyfee'] for p in pp),Z);sf=sum((p['actual_sellfee'] for p in pp),Z)
 close(realized,grosspnl-bf-sf,'A realized gross/buyfee/sellfee')
 return dict(actual_sell_parts=len(pp),actual_sell_trades=len({p['trade_receipt'] for p in pp}),
  distinct_layers=len({p['layer'] for p in pp}),stocks=len({p['sid'] for p in pp}),
  strict_realized=realized,positive_realized=sum((max(Z,p['strict_realized']) for p in pp),Z),
  negative_realized=sum((min(Z,p['strict_realized']) for p in pp),Z),gross_price_pnl=grosspnl,
  consumed_buygross=sum((p['consumed_buygross'] for p in pp),Z),consumed_buyfee=bf,actual_sellfee=sf,
  gross_sale_proceeds=sum((p['gross_sale'] for p in pp),Z),net_sale_proceeds=sum((p['net_sale'] for p in pp),Z),
  state=state(realized,len(pp)))


def cycle_values(cc,ll,marks):
 v=values(ll,marks);v['stock_campaigns']=len(cc);v['state']=state(v['net_trade_cash'],len(cc));return v


def outcome(rr):
 return dict(fills=len(rr),stocks=len({x['sid'] for x in rr}),actual_buycash=sum((n(x['cost']) for x in rr),Z),
  net=sum((n(x['net']) for x in rr),Z),positive_net=sum((max(Z,n(x['net'])) for x in rr),Z),negative_net=sum((min(Z,n(x['net'])) for x in rr),Z),
  negative_fills=sum(n(x['net'])<0 for x in rr),strict_realized=sum((n(x['strict_realized']) for x in rr),Z),
  open_unrealized=sum((n(x['open_unrealized']) for x in rr),Z),recognized_dividend_AR=sum((n(x['recognized_dividend_AR']) for x in rr),Z),open_layers=sum(bool(x['qty']) for x in rr))


def groups(rr,fields):
 bb=defaultdict(list)
 for x in rr:bb[tuple(x[f] for f in fields)].append(x)
 return [dict(labels=dict(zip(fields,k)),**outcome(v)) for k,v in sorted(bb.items())]


def run(ref,pair,expected):
 book=read(pair/'B.json.gz',gz=True);ds=read(pair/'daily.jsonl.gz',gz=True,lines=True)
 timeline=read(T/(ref+'_DECISION_TIMELINE.json'));source_daily=read(T/(ref+'_DAILY.json'))
 assert len(ds)==len(source_daily)==expected
 emap={x['layer']:x for x in timeline};byat=defaultdict(list)
 for x in timeline:byat[x['decision_at']].append(x)
 events=[(t['at'],1,i,'trade',t) for i,t in enumerate(book['trades'])]
 for i,t in enumerate(book['audit']):
  if t['kind']=='split':events.append((t['at'],0,i,'split',t))
  elif t['kind']=='dividend_accrual':
   assert t['receivable']['paid_at'] is None;events.append((t['receivable']['ex_at'],2,i,'div',t['receivable']))
 assert not any(t['kind']=='dividend_paid' for t in book['audit'])
 events.sort(key=lambda x:x[:3]);ei=0;layers={};parts=[];divs=[];campaigns=[];current={};qstock=defaultdict(int)
 allrows=[];daily=[];checks=dict(native_closes=0,held_layer_checks=0,sell_parts=0,closed_stock_campaigns=0,stale_stockday_marks=0)
 for di,(snap,sd) in enumerate(zip(ds,source_daily)):
  at=snap['at'];day=at[:10];assert sd['at']==at
  while ei<len(events) and events[ei][0]<at:
   et,_,_,kind,t=events[ei];ei+=1
   if kind=='split':
    for l in layers.values():
     if l['sid']==t['sid'] and l['q']:
      exact=D(l['q'])*n(t['ratio']);assert exact==int(exact);qstock[l['sid']]+=int(exact)-l['q'];l['q']=int(exact)
   elif kind=='div':
    held=[l for l in layers.values() if l['sid']==t['security_id'] and l['q']];q=sum(l['q'] for l in held);assert q>0
    for l in held:l['div']+=n(t['net_local'])*D(l['q'])/D(q)
    divs.append(dict(at=et,sid=t['security_id'],recognized_AR=n(t['net_local'])))
   elif t['side']=='buy':
    lid=t['layer'];sid=t['security_id'];e=emap[lid];assert lid not in layers
    if qstock[sid]==0:
     c=dict(sid=sid,opened_at=et,closed_at=None,layer_ids=[]);campaigns.append(c);current[sid]=c
    current[sid]['layer_ids'].append(lid)
    gross=n(t['gross_cny']);fee=n(t['fees_cny'])
    layers[lid]=dict(id=lid,sid=sid,q=t['shares'],basis=gross+fee,gross_basis=gross,buyfee_basis=fee,
      real=Z,cash=-gross-fee,div=Z,cost=gross+fee,gross=gross,buyfee=fee,sellfee=Z,opened_at=et,action=e['action'])
    qstock[sid]+=t['shares']
   else:
    sid=t['security_id'];proceeds=Z
    for p in t['parts']:
     l=layers[p['layer']];q=p['shares'];assert l['sid']==sid and 0<q<=l['q']
     consumed_g=l['gross_basis']*D(q)/D(l['q']);consumed_f=l['buyfee_basis']*D(q)/D(l['q']);basis=consumed_g+consumed_f
     net=n(p['net_cash']);gross=n(t['price'])*D(q);sellfee=gross-net
     realized=net-basis;l['q']-=q;l['basis']-=basis;l['gross_basis']-=consumed_g;l['buyfee_basis']-=consumed_f
     l['cash']+=net;l['real']+=realized;l['sellfee']+=sellfee;qstock[sid]-=q;proceeds+=net
     parts.append(dict(at=et,layer=l['id'],sid=sid,shares=q,trade_receipt=t['receipt_id'],consumed_buygross=consumed_g,
       consumed_buyfee=consumed_f,actual_sellfee=sellfee,gross_sale=gross,net_sale=net,gross_price_pnl=gross-consumed_g,
       strict_realized=realized,role=emap[l['id']]['role'],action=l['action']))
    close(proceeds,n(t['gross_cny'])-n(t['fees_cny']),'native sell parts')
    if qstock[sid]==0:current[sid]['closed_at']=et;checks['closed_stock_campaigns']+=1
  native={l['id']:l for l in snap['layers']};assert set(native)=={lid for lid,l in layers.items() if l['q']}
  assert {s:q for s,q in qstock.items() if q}=={s:int(q) for s,q in snap['positions'].items() if q}
  marks={sid:R.mark(sid,day) for sid,q in qstock.items() if q};checks['stale_stockday_marks']+=sum(d!=day for _,d in marks.values())
  for lid,nl in native.items():
   l=layers[lid];assert nl['qty']==l['q'];close(nl['cash'],l['cash'],'native cash');close(nl['dividend'],l['div'],'native AR')
   close(l['basis'],l['gross_basis']+l['buyfee_basis'],'gross/fee basis');checks['held_layer_checks']+=1
  total=values(list(layers.values()),marks)
  close(total['current_market_value'],snap['inventory'],'native inventory');close(total['recognized_dividend_AR'],snap['dividend_receivable'],'native AR total')
  close(D(1000000)+total['recognized_wealth'],snap['nav'],'native NAV')
  lo=ds[max(0,di-20)]['at'][:10]
  recent=[l for l in layers.values() if lo<=l['opened_at'][:10]<=day]
  recent_value=values(recent,marks)
  for a,b in [('actual_buycash','original_buycash'),('strict_realized','strict_realized'),('unrealized','unrealized'),('recognized_dividend_AR','recognized_dividend_AR')]:close(sd['recent21_all'][a],recent_value[b],'old recent cohort '+a)
  aa=sell_feedback([p for p in parts if lo<=p['at'][:10]<=day and p['at']<at])
  closed=[l for l in recent if l['q']==0];openlayers=[l for l in recent if l['q']>0]
  bl=values(closed,marks);bl['state']=state(bl['net_trade_cash'],len(closed))
  bo=values(openlayers,marks)
  # Both complete and unfinished campaigns must START within the same21 dates.
  recentc=[c for c in campaigns if lo<=c['opened_at'][:10]<=day]
  closedc=[c for c in recentc if c['closed_at'] is not None and c['closed_at']<at]
  openc=[c for c in recentc if c['closed_at'] is None]
  bc=cycle_values(closedc,[layers[lid] for c in closedc for lid in c['layer_ids']],marks)
  bcopen=cycle_values(openc,[layers[lid] for c in openc for lid in c['layer_ids']],marks)
  assert all(l['opened_at']<at for l in recent)
  features=dict(decision_at=at,window_first=lo,window_last=day,native_observations=min(di+1,21),
    A_recent_actual_sell_realized=aa,window_dividend_AR_accrual_separate=sum((v['recognized_AR'] for v in divs if lo<=v['at'][:10]<=day and v['at']<at),Z),
    B1_recent_new_complete_layers=bl,B1_recent_new_still_held_excluded=bo,
    B2_recent_new_complete_stockcampaigns=bc,B2_recent_new_unfinished_stockcampaigns_excluded=bcopen,
    recent_new_all=recent_value,A_state=aa['state'],B1_state=bl['state'],B2_state=bc['state'],
    unfinished_new_layer_wealth_state=state(bo['recognized_wealth'],bo['layers']),
    unfinished_new_layer_unrealized_state=state(bo['unrealized'],bo['layers']))
  daily.append(features)
  for x in byat.get(at,[]):
   # Original terminal outcomes are merely copied for final attribution; they do
   # not enter any A/B feature, stock mark, completion or cohort membership.
   allrows.append(dict(x,realized_feedback=features,A_state=aa['state'],B1_state=bl['state'],B2_state=bc['state'],
                      unfinished_new_layer_wealth_state=features['unfinished_new_layer_wealth_state'],
                      unfinished_new_layer_unrealized_state=features['unfinished_new_layer_unrealized_state']))
  checks['native_closes']+=1
 assert ei==len(events) and len(allrows)==len(timeline)
 for l in layers.values():
  final=next(x for x in book['layers'] if x['id']==l['id']);assert l['q']==final['qty'];close(l['cash'],final['cash'],'native final cash');close(l['div'],final['dividend'],'native final AR')
  e=emap[l['id']];v=D(l['q'])*R.mark(l['sid'],ds[-1]['at'][:10])[0] if l['q'] else Z;close(l['cash']+l['div']+v,e['net'],'native terminal layer')
 checks['sell_parts']=len(parts)
 save(ref+'_DECISIONS.json',allrows);save(ref+'_DAILY.json',daily);save(ref+'_SELL_PARTS_REALIZED.json',parts)
 save(ref+'_STOCK_CAMPAIGNS.json',campaigns)
 print('SAVED',ref,len(allrows),'parts',len(parts),flush=True)
 return allrows,daily,checks


def main():
 R.SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 save('PROTOCOL.json',dict(A='Actual sell.parts realized within current plus previous20 native CLOSE dates, with consumed gross buy basis, consumed original buy fee and actual sell fee; all events strictly<decisionCLOSE. AR separate.',
   B1='Layers actually opened within same21 dates and q==0 by decision; tradecash excludes AR. Still-held layers explicitly excluded and shown.',
   B2='Full stock campaigns actually STARTED within same21 dates and stock flat strictly before decision; partial or unfinished campaigns excluded and shown.',
   fixed_windows='Original L02 Apr27-Jul4 2022 recovery and L04 Nov1-Jan30 market-up failure, plus Sep24-Oct8 2024. Retrospective labels only.',
   original_fixed_tails='Full authoritative83/94 retained, matched actual45/67; unmatched retain current No60 calendar feedback as descriptive cross-arm correspondence, no synthetic fill.',
   no_window_search=True,no_gates=True,no_accounts=True,new_signals=0))
 data={};validation={}
 for ref,pair,days in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',726),('strong',B/'pvr_pool_feasibility/runs/2025_26/pair',242)]:
  rr,dd,ck=run(ref,pair,days);data[ref]=(rr,dd);validation[ref]=ck
 legs=read(B/'pvr_pool_feasibility/market_phase_2022_2023/HS300_ALL_LEGS.json')
 periods=[(l['id'],l['first_analysis_day'],l['last_analysis_day']) for l in legs if l['id'] in ['L02','L04']]+[('2024_Sep24_Oct8','2024-09-24','2024-10-08')]
 summary={}
 for ref,(rr,dd) in data.items():
  scopes={'all':rr,'first_entries':[x for x in rr if x['action']==ACTIONS[0]]}
  if ref=='2022_2024':
   scopes.update(two_year=[x for x in rr if x['actual_fill_at'][:10]<'2024-01-01'],two_year_first=[x for x in rr if x['actual_fill_at'][:10]<'2024-01-01' and x['action']==ACTIONS[0]],post303=[x for x in rr if '2024-10-09'<=x['actual_fill_at'][:10]<='2024-12-31'])
   for name,lo,hi in periods:
    scopes[name]=[x for x in rr if lo<=x['actual_fill_at'][:10]<=hi]
    scopes[name+'_first']=[x for x in scopes[name] if x['action']==ACTIONS[0]]
  for name,sr in scopes.items():
   summary[ref+'_'+name]=dict(all=outcome(sr),A=groups(sr,['A_state']),B1=groups(sr,['B1_state']),B2=groups(sr,['B2_state']),
     action_A=groups(sr,['action','A_state']),action_B1=groups(sr,['action','B1_state']),action_B2=groups(sr,['action','B2_state']),
     A_vs_B1=groups(sr,['A_state','B1_state']),B1_vs_unfinished_wealth=groups(sr,['B1_state','unfinished_new_layer_wealth_state']))
  controls=read(B/'risk_constraints/ma63_information_diagnostic_v1'/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'))
  byday={d['decision_at'][:10]:d for d in dd};byid={x['layer']:x for x in rr};tails=[];actual=[]
  for c in controls:
   old=c['original'];f=byday[old['decision_at'][:10]]
   tails.append(dict(original=old,matched_No60_layers=c['matched_No60_layers'],current_No60_feedback_at_original_decision=f,
       scope='Calendar-aligned current No60 account feedback at an original PVR tail decision; unmatched is not a current-arm fill or lost profit.'))
   actual.extend(byid[lid] for lid in c['matched_No60_layers'])
  assert len(actual)==len({x['layer'] for x in actual})
  save(ref+'_FIXED_ORIGINAL_TAILS.json',tails)
  summary[ref+'_fixed_tail_actual_matches']=dict(original_members=len(tails),matched_members=len(actual),all=outcome(actual),
      A=groups(actual,['A_state']),B1=groups(actual,['B1_state']),B2=groups(actual,['B2_state']),
      B1_vs_unfinished_wealth=groups(actual,['B1_state','unfinished_new_layer_wealth_state']))
 # Fixed paths retained from earlier work, not selected by this feedback result.
 cases=['000620.SZ','601595.SH','301319.SZ','002969.SZ','688146.SH','300489.SZ']
 save('FIXED_CASES.json',{sid:[dict(reference=ref,**x) for ref,(rr,dd) in data.items() for x in rr if x['sid']==sid] for sid in cases})
 save('FIXED_PERIOD_DAILY.json',{name:[d for d in data['2022_2024'][1] if lo<=d['decision_at'][:10]<=hi] for name,lo,hi in periods})
 save('SUMMARY.json',summary)
 save('VALIDATION.json',dict(passed=True,refs=validation,all_decisions=3436,strict_before_decision=True,
   native_q_cash_AR_inventory_NAV=True,old_timeline_recent_cohort_exact=True,new_account_events=0,new_signals=0,
   limitations=['Completed samples overrepresent short-lived failures and exclude incomplete winners. Descriptive only, no causal gate effect.',
    'A window is sell time; B windows are opening time plus completed-by-now, not interchangeable.',
    'AR is recognized but unpaid and never part of net trading cash. Sell proceeds are not spendable-cash accounting.',
    'Repeated overlapping21 windows and repeated decisions are not independent trials.',
    'Original current-survivor/current-sector historical development and daily execution proxies retained.']))
 SRC.update(R.SRC);SRC[str(T/'analyze_timeline.py')]=hashlib.sha256((T/'analyze_timeline.py').read_bytes()).hexdigest();SRC[str(Path(__file__))]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 save('SOURCE_SHA256.json',SRC)


if __name__=='__main__':main()
