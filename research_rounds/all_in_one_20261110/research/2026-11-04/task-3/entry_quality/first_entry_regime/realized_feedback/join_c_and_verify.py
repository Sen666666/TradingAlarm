"""C accurate new-layer realized feedback, pure joins plus bounded verification."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal as D,getcontext
import gzip,json,hashlib

getcontext().prec=60
O=Path(__file__).parent;E=O.parents[1];B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');T=E/'failure_no_progress/timeline'
Z=D(0);SRC={};CHECK={}


def read(p,gz=False,lines=False):
 SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)


def save(name,x):
 with (O/name).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')


def close(a,b,k):assert abs(D(str(a))-D(str(b)))<D('1e-17'),(k,a,b)


def state(v,c):return 'no_realization' if not c else 'negative' if v<0 else 'positive' if v>0 else 'zero'


def outcome(rr):
 return dict(fills=len(rr),stocks=len({x['sid'] for x in rr}),actual_buycash=sum((D(x['cost']) for x in rr),Z),
  net=sum((D(x['net']) for x in rr),Z),positive_net=sum((max(Z,D(x['net'])) for x in rr),Z),negative_net=sum((min(Z,D(x['net'])) for x in rr),Z),
  strict_realized=sum((D(x['strict_realized']) for x in rr),Z),open_unrealized=sum((D(x['open_unrealized']) for x in rr),Z),
  recognized_dividend_AR=sum((D(x['recognized_dividend_AR']) for x in rr),Z),open_layers=sum(bool(x['qty']) for x in rr))


def group(rr,fields):
 dd=defaultdict(list)
 for x in rr:dd[tuple(x[k] for k in fields)].append(x)
 return [dict(labels=dict(zip(fields,k)),**outcome(v)) for k,v in sorted(dd.items())]


DATA={};DAILY={};SUMMARY={};TAILJOIN={}
for ref,pair,finance in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',B/'risk_constraints/continuation2024_finance/PVR_NO_CONFIRMED60_DAILY.json'),
                       ('strong',B/'pvr_pool_feasibility/runs/2025_26/pair',B/'risk_constraints/absolute_loss_2022_2023/NO60_STRONG_DAILY.json')]:
 rows=read(O/(ref+'_DECISIONS.json'));daily=read(O/(ref+'_DAILY.json'));parts=read(O/(ref+'_SELL_PARTS_REALIZED.json'));oldfinance=read(finance)
 book=read(pair/'B.json.gz',gz=True);native=read(pair/'daily.jsonl.gz',gz=True,lines=True)
 oldcycles=read(T/(ref+'_COMPLETED_STOCK_CYCLES.json'))
 byid={x['layer']:x for x in rows};byday={x['decision_at'][:10]:x for x in daily};buys={t['layer']:t for t in book['trades'] if t['side']=='buy'}
 assert len(daily)==len(oldfinance)==len(native)
 assert len(parts)==len({(p['layer'],p['at'],p['trade_receipt']) for p in parts})
 # No new accounting implementation: quantities only verify whether actual
 # nontrivial per-layer partial sales exist in these saved mothers.
 ev=[(t['at'],1,i,'trade',t) for i,t in enumerate(book['trades'])]
 ev += [(s['at'],0,i,'split',s) for i,s in enumerate(book['audit']) if s['kind']=='split']
 q={};sidmap={};partial=0
 for _,_,_,kind,t in sorted(ev,key=lambda x:x[:3]):
  if kind=='split':
   for lid,qty in list(q.items()):
    if sidmap[lid]==t['sid'] and qty:
     v=D(qty)*D(t['ratio']);assert v==int(v);q[lid]=int(v)
  elif t['side']=='buy':q[t['layer']]=t['shares'];sidmap[t['layer']]=t['security_id']
  else:
   for p in t['parts']:
    lid=p['layer'];assert 0<p['shares']<=q[lid];partial+=p['shares']<q[lid];q[lid]-=p['shares']
 close(sum((D(p['actual_sellfee']) for p in parts),Z),sum((D(t['fees_cny']) for t in book['trades'] if t['side']=='sell'),Z),'total original sellfees')
 if not partial:
  close(sum((D(p['consumed_buyfee']) for p in parts),Z),sum((D(buys[lid]['fees_cny']) for lid,qty in q.items() if qty==0),Z),'closed original buyfees')
 for i,(d,fin,nat) in enumerate(zip(daily,oldfinance,native)):
  assert fin['day']==d['decision_at'][:10]==nat['at'][:10]
  window=oldfinance[max(0,i-20):i+1]
  close(d['A_recent_actual_sell_realized']['strict_realized'],sum((D(f['realized_trade_net']) for f in window),Z),'A independent previous daily strictreal')
  close(d['window_dividend_AR_accrual_separate'],sum((D(f['recognized_dividend']) for f in window),Z),'window AR separate')
  lo=d['window_first'];at=d['decision_at'];day=d['window_last']
  recent=[x for x in rows if lo<=x['actual_fill_at'][:10]<=day and x['actual_fill_at']<at]
  nativeheld={x['id'] for x in nat['layers']}
  closed=[x for x in recent if x['layer'] not in nativeheld]
  openrows=[x for x in recent if x['layer'] in nativeheld]
  assert d['B1_recent_new_complete_layers']['layers']==len(closed) and d['B1_recent_new_still_held_excluded']['layers']==len(openrows)
  close(d['B1_recent_new_complete_layers']['original_buycash'],sum((D(x['cost']) for x in closed),Z),'B1 closed own buycash')
  close(d['B1_recent_new_still_held_excluded']['original_buycash'],sum((D(x['cost']) for x in openrows),Z),'B1 held own buycash')
  # Primary C: SAME actual new-layer cohort's realized PnL, regardless of whether
  # the layer remains open. Count sold parts separately from its monetary sign.
  recentids={x['layer'] for x in recent}
  cp=[p for p in parts if p['layer'] in recentids and p['at']<at]
  cvalue=D(d['recent_new_all']['strict_realized'])
  close(cvalue,sum((D(p['strict_realized']) for p in cp),Z),'C all realized parts of recent opened cohort')
  c=dict(strict_realized=cvalue,actual_sell_parts=len(cp),actual_sell_trades=len({p['trade_receipt'] for p in cp}),
    distinct_realized_layers=len({p['layer'] for p in cp}),state=state(cvalue,len(cp)),
    gross_price_pnl=sum((D(p['gross_price_pnl']) for p in cp),Z),consumed_original_buyfee=sum((D(p['consumed_buyfee']) for p in cp),Z),
    actual_sellfee=sum((D(p['actual_sellfee']) for p in cp),Z),recognized_dividend_AR_separate=d['recent_new_all']['recognized_dividend_AR'],
    new_cohort_actual_buycash=d['recent_new_all']['original_buycash'],new_cohort_layers=d['recent_new_all']['layers'],
    current_unrealized_separate=d['recent_new_all']['unrealized'],
    definition='C: recent actually opened layers, all realized sell.parts strictly before current decision, including partial realization of still-held layers if any; no event distinct from zero PnL.')
  close(c['strict_realized'],c['gross_price_pnl']-c['consumed_original_buyfee']-c['actual_sellfee'],'C fee bridge')
  d['C_recent_new_layers_realized']=c;d['C_state']=c['state']
  # A can contain realizations of positions opened BEFORE the cohort window.
  ap=[p for p in parts if lo<=p['at'][:10]<=day and p['at']<at]
  older=[p for p in ap if p['layer'] not in recentids]
  d['A_from_layers_opened_before_window']=dict(parts=len(older),strict_realized=sum((D(p['strict_realized']) for p in older),Z))
  close(d['A_recent_actual_sell_realized']['strict_realized'],cvalue+d['A_from_layers_opened_before_window']['strict_realized'],'A=C+older-layer realizations')
  cycles=[dict(cc,sid=sid) for sid,hh in oldcycles.items() for cc in hh if cc['closed_at']<at and lo<=min(byid[lid]['actual_fill_at'][:10] for lid in cc['layer_ids'])<=day]
  assert d['B2_recent_new_complete_stockcampaigns']['stock_campaigns']==len(cycles)
  close(d['B2_recent_new_complete_stockcampaigns']['net_trade_cash'],sum((D(cc['net_trade_cash']) for cc in cycles),Z),'B2 independent native completed cycles')
 for x in rows:
  f=byday[x['decision_at'][:10]];c=f['C_recent_new_layers_realized'];old=x['recent21_account']
  close(old['strict_realized'],c['strict_realized'],'exact prior timeline C join')
  x['C_state']=c['state'];x['C_recent_new_layers_realized']=c
  x['realized_feedback']=f
  x['A_C_differ']=x['A_state']!=('no_events' if x['C_state']=='no_realization' else x['C_state'])
  x['C_B1_differ']=x['B1_state']!=('no_events' if x['C_state']=='no_realization' else x['C_state'])
 def cb1diff(d):return d['B1_state']!=('no_events' if d['C_state']=='no_realization' else d['C_state'])
 CHECK[ref]=dict(decisions=len(rows),native_closes=len(daily),actual_nontrivial_partial_layer_sell_parts=partial,
    A_matches_previous_native_finance_daily_rolling=True,C_matches_previous_timeline_and_actual_parts=True,
    B1_native_closed_membership_and_owncapital=True,B2_native_complete_cycles=True,all_actual_sellfees_and_consumed_buyfees_exact=True,
    C_B1_monetary_difference_days=sum(abs(D(d['C_recent_new_layers_realized']['strict_realized'])-D(d['B1_recent_new_complete_layers']['net_trade_cash']))>D('1e-17') for d in daily),
    C_B1_sign_difference_days=sum(cb1diff(d) for d in daily),C_B1_sign_difference_decisions=sum(x['C_B1_differ'] for x in rows),
    A_C_sign_difference_decisions=sum(x['A_C_differ'] for x in rows))
 DATA[ref]=rows;DAILY[ref]=daily
 save(ref+'_C_JOIN.json',[{k:x[k] for k in ['layer','sid','action','role','decision_at','actual_fill_at','A_state','B1_state','B2_state','C_state','C_recent_new_layers_realized','A_C_differ','C_B1_differ','cost','net','qty','strict_realized','open_unrealized','recognized_dividend_AR']} for x in rows])
 save(ref+'_DAILY_ABC.json',daily)
 scopes={'all':rows,'first':[x for x in rows if x['action']=='first_actual_participation']}
 if ref=='2022_2024':
  scopes.update(two_year_first=[x for x in rows if x['actual_fill_at'][:10]<'2024-01-01' and x['action']=='first_actual_participation'],post303=[x for x in rows if '2024-10-09'<=x['actual_fill_at'][:10]<='2024-12-31'])
  for name,lo,hi in [('L02','2022-04-27','2022-07-04'),('L04','2022-11-01','2023-01-30'),('Sep24_Oct8','2024-09-24','2024-10-08')]:
   scopes[name]=[x for x in rows if lo<=x['actual_fill_at'][:10]<=hi];scopes[name+'_first']=[x for x in scopes[name] if x['action']=='first_actual_participation']
 for name,rr in scopes.items():
  SUMMARY[ref+'_'+name]=dict(all=outcome(rr),A=group(rr,['A_state']),B1=group(rr,['B1_state']),B2=group(rr,['B2_state']),C=group(rr,['C_state']),
    action_C=group(rr,['action','C_state']),A_vs_C=group(rr,['A_state','C_state']),C_vs_B1=group(rr,['C_state','B1_state']),
    C_vs_unfinished_new_wealth=group(rr,['C_state','unfinished_new_layer_wealth_state']))
 controls=read(B/'risk_constraints/ma63_information_diagnostic_v1'/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'))
 actual=[byid[lid] for cc in controls for lid in cc['matched_No60_layers']]
 for x in actual:
  y=next(z for z in rows if z['layer']==x['layer']);x.update(C_state=y['C_state'],C_recent_new_layers_realized=y['C_recent_new_layers_realized'])
 SUMMARY[ref+'_fixed_tail_actual_matches']=dict(original_members=len(controls),actual_matches=len(actual),all=outcome(actual),
      A=group(actual,['A_state']),B1=group(actual,['B1_state']),B2=group(actual,['B2_state']),C=group(actual,['C_state']),
      C_vs_unfinished_new_wealth=group(actual,['C_state','unfinished_new_layer_wealth_state']))
 TAILJOIN[ref]=[dict(original_layer=cc['original']['layer'],sid=cc['original']['sid'],original_decision_at=cc['original']['decision_at'],
                       matched_actual_No60_layers=cc['matched_No60_layers'],C_current_No60_at_original_calendar_decision=byday[cc['original']['decision_at'][:10]]['C_recent_new_layers_realized']) for cc in controls]

cases=['000620.SZ','601595.SH','301319.SZ','002969.SZ','688146.SH','300489.SZ']
save('FIXED_CASES_ABC.json',{sid:[dict(reference=ref,**x) for ref,rr in DATA.items() for x in rr if x['sid']==sid] for sid in cases})
save('FIXED_TAIL_C_JOIN.json',TAILJOIN);save('ABC_SUMMARY.json',SUMMARY)
save('C_VALIDATION.json',dict(passed=True,checks=CHECK,accurate_user_concept='C, not completed-only B or sell-time-only A',
   no_window_search=True,new_account_events=0,new_signals=0,sources=SRC,
   limits=['Zero nontrivial partial-layer sales in these saved mothers means C and B1 agree here; do not assume equivalence in another account with partial realization.',
           'C is accurate new-cohort realized PnL but still excludes all unfinished unrealized gains. C negative is not a causal proof of no new opportunity.',
           'No_realization is not zero PnL after an event; original closed-layer/campaign AR is separate from tradecash.',
           'A-C differences can arise from older-than21 layer realizations, not only completion bias.']))
print(json.dumps(CHECK,ensure_ascii=False,indent=2))
