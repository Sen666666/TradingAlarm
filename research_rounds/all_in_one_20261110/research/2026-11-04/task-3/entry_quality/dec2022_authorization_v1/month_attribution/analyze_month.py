"""Original Dec2022 wealth/authorization readout from existing native records."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import bisect,csv,gzip,hashlib,json
import pandas as pd
import numpy as np
getcontext().prec=60
O=Path(__file__).parent;E=O.parents[1]
ROOT=E/'trend_exit_controls_v1';V=ROOT/'execution_review/account_comparison/results_v2'
B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
SRC={};FF={};Z=D(0);START='2022-11-30 15:10:00+08:00';END='2022-12-30 15:10:00+08:00'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def rowscsv(p):
 SRC[str(p)]=sha(p)
 return list(csv.DictReader(Path(p).open()))
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
def eq(a,b,k):assert abs(D(str(a))-D(str(b)))<D('1e-6'),(k,a,b)
def iso(s):return pd.Timestamp(s).isoformat()
SM={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
META=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
def fact(sid,day):
 if sid not in FF:
  p=Path(SM[sid]['refs']['facts']);h=sha(p);assert h==SM[sid]['output_sha256'][str(p)];SRC[str(p)]=h
  FF[sid]=pd.read_parquet(p,columns=['raw_close','close','i_target','i_floor','e0_target','e0_floor'])
 f=FF[sid];i=f.index.searchsorted(pd.Timestamp(day),side='right')-1;assert i>=0
 return f.iloc[i],str(f.index[i].date())
proof=read(ROOT/'independent_review/FULL_BASELINE_AUDIT.json');assert proof['status']=='PASS_FULL_BASELINE'
book=read(ROOT/'runs/BASELINE/2022_2024/pair/B.json.gz',gz=True);daily=read(ROOT/'runs/BASELINE/2022_2024/pair/daily.jsonl.gz',gz=True,lines=True)
vr=read(V/'BASELINE_2022_2024_LAYERS.json');byid={r['layer_in_this_book']:r for r in vr};bykey={r['key']:r for r in vr};native={x['id']:x for x in book['layers']}
buys={x['layer']:x for x in book['trades'] if x['side']=='buy'};journal={x['layer']:x for x in book['journal'] if x['kind']=='real_buy_fill'}
dmap={d['at']:d for d in daily};times=[d['at'] for d in daily];s=dmap[START];e=dmap[END];si=times.index(START);ei=times.index(END);month=daily[si+1:ei+1];assert len(month)==22
fin=read(B/'risk_constraints/continuation2024_finance/PVR_NO_CONFIRMED60_DAILY.json');fin={x['day']:x for x in fin}
ma=read(B/'risk_constraints/ma63_information_diagnostic_v1/2022_2024_ENTRIES.json');ma={r['layer']:r for r in ma}
for lid,r in byid.items():assert ma[lid]['sid']==r['sid'] and iso(ma[lid]['opened'])==r['opened'] and iso(ma[lid]['decision_at'])==r['decision_at'];eq(ma[lid]['cost'],r['cost'],'old enriched row cost')
def components(d):
 at=iso(d['at']);held={x['id']:x for x in d['layers']};out={}
 for r in vr:
  lid=r['layer_in_this_book']
  if r['opened']>at:real=unreal=ar=Z
  elif r['closed'] is not None and r['closed']<=at:real=D(native[lid]['cash']);unreal=Z;ar=D(native[lid]['dividend'])
  else:
   x=held[lid];eq(x['cash'],-D(r['cost']),'original no partial at boundary');q,qd=fact(r['sid'],d['at'][:10]);real=Z;unreal=D(x['qty'])*D(str(q.raw_close))-D(r['cost']);ar=D(x['dividend'])
  out[lid]=dict(real=real,unreal=unreal,AR=ar,wealth=real+unreal+ar)
 eq(sum((x['wealth'] for x in out.values()),Z),D(d['nav'])-D(1000000),'month boundary exactwealth')
 return out
cs,ce=components(s),components(e);oldids={x['id'] for x in s['layers']};endids={x['id'] for x in e['layers']};rr=[]
for r in vr:
 lid=r['layer_in_this_book'];delta={k:ce[lid][k]-cs[lid][k] for k in ['real','unreal','AR','wealth']}
 if not delta['wealth'] and not (iso(START)<r['opened']<=iso(END)) and lid not in oldids:continue
 cohort='old_inventory_at_Nov30' if lid in oldids else 'Dec_new_'+r['actual_entry_action'] if iso(START)<r['opened']<=iso(END) else 'old_flat_or_other'
 oldunrl=cs[lid]['unreal'];z=dict(r,name=META[r['sid']]['name'],industry=META[r['sid']]['industry'],sector=META[r['sid']]['sector_id'],cohort=cohort,
  month_components=delta,Nov30_components=cs[lid],Dec30_components=ce[lid],pool_at_actual_fill=journal[lid]['pool'],
  Nov30_unrealized_sign='positive' if oldunrl>0 else 'negative' if oldunrl<0 else 'zero',
  actual_entry_quote_context={k:ma[lid].get(k) for k in ['stock','industry_state','MA63_class','probe_progress']})
 rr.append(z)
def total(rows):
 return dict(layers=len(rows),stocks=len({x['sid'] for x in rows}),month_wealth=sum((x['month_components']['wealth'] for x in rows),Z),
  month_positive=sum((max(Z,x['month_components']['wealth']) for x in rows),Z),month_negative=sum((min(Z,x['month_components']['wealth']) for x in rows),Z),
  realized_change=sum((x['month_components']['real'] for x in rows),Z),unrealized_change=sum((x['month_components']['unreal'] for x in rows),Z),AR_change=sum((x['month_components']['AR'] for x in rows),Z),
  Dec_actual_new_buycash=sum((D(x['cost']) for x in rows if iso(START)<x['opened']<=iso(END)),Z))
def group(rows,key):
 g=defaultdict(list)
 for r in rows:g[str(r[key])].append(r)
 return {k:total(v) for k,v in sorted(g.items())}
agg=total(rr);eq(agg['month_wealth'],D(e['nav'])-D(s['nav']),'Dec wealth');stock=group(rr,'sid');industries=group(rr,'industry');cohorts=group(rr,'cohort')
for sid,x in stock.items():x.update(sid=sid,name=META[sid]['name'],industry=META[sid]['industry'])
dayrows=[]
for i,d in enumerate(month,si+1):
 prev=daily[i-1];at=d['at'];day=at[:10];ts=[t for t in book['trades'] if t['at'][:10]==day];buyrows=[r for r in rr if r['opened'][:10]==day]
 for x in d['layers']:eq(x['cash'],-D(byid[x['id']]['cost']),'no native held partial in Dec')
 f=fin[day];eq(D(d['nav'])-D(prev['nav']),f['wealth_change'],'existing finance daily');eq(sum((D(t['fees_cny']) for t in ts),Z),f['actual_fees'],'native fees vs finance')
 dayrows.append(dict(day=day,previous_CLOSE_at=prev['at'],NAV_begin=prev['nav'],NAV_end=d['nav'],wealth=D(d['nav'])-D(prev['nav']),
  previous_CLOSE_exposure=D(prev['inventory'])/D(prev['nav']),CLOSE_exposure=D(d['inventory'])/D(d['nav']),previous_CLOSE_inventory=prev['inventory'],CLOSE_inventory=d['inventory'],
  held_basis=f['held_cost_basis'],available_cash=d['available'],realized=f['realized_trade_net'],unrealized_change=f['unrealized_change'],recognized_AR=f['recognized_dividend'],
  fees=f['actual_fees'],actual_buycash=f['actual_buy_cash'],actual_sell_net=f['actual_sell_net'],buy_fills=f['buy_fills'],sell_fills=f['sell_fills'],
  ACT_at_OPEN=prev['on'],ACT_after_CLOSE=d['on'],pending_intents=d['pending_intents'],new_buy_cohorts=group(buyrows,'cohort'),
  actual_new_entry_keys=[r['key'] for r in buyrows],actual_prior_decision_times=sorted({r['decision_at'] for r in buyrows})))
calendar=[d['at'][:10] for d in daily];calix={day:i for i,day in enumerate(calendar)}
requests={x['event_id']:x for x in book['audit'] if x['kind']=='exit_request'};fills={a['receipt']['receipt_id']:(i,a) for i,a in enumerate(book['audit']) if a['kind']=='fill'}
sales=defaultdict(list)
for t in book['trades']:
 if t['side']=='sell':
  fi,a=fills[t['receipt_id']];req=requests[a['order_id']]
  for p in t['parts']:sales[p['layer']].append(dict(actual_fill=t['at'],order_created_at=req['at'],order_id=a['order_id'],reason=p['reason'],shares=p['shares'],net_cash=p['net_cash'],
   raw_open=t['raw_open'],price=t['price'],whole_native_fill_fee=t['fees_cny'],request_to_fill_market_steps=calix[t['at'][:10]]-calix[req['at'][:10]]))
def context(r):
 lid=r['layer_in_this_book'];entry=ma[lid];exitctx=[]
 for p in sales[lid]:
  at=p['order_created_at'];q,qd=fact(r['sid'],at[:10]);j=bisect.bisect_left(times,at)-1;old=None if j<0 else next((x for x in daily[j]['layers'] if x['id']==lid),None)
  oldfloor=old['floor'] if old is not None else buys[lid]['floor']
  exitctx.append(dict(p,request_close=str(q.close),quote_day=qd,I_target=bool(q.i_target),I_floor=None if not np.isfinite(q.i_floor) else str(q.i_floor),E0_target=bool(q.e0_target),
   pre_CLOSE_layer_floor=oldfloor,CP_floor_broken=(D(str(q.close))<=D(oldfloor)) if r['role']=='mobile' else None))
 return dict(r,actual_buy_receipt=buys[lid],actual_sell_parts=exitctx)
camps=read(V/'BASELINE_2022_2024_STOCK_CAMPAIGNS.json');rm={r['key']:r for r in rr};affected=[]
for c in camps:
 rows=[rm[k] for k in c['entry_keys'] if k in rm]
 if not rows:continue
 affected.append(dict(c,name=META[c['sid']]['name'],industry=META[c['sid']]['industry'],month=total(rows),entries=[context(r) for r in rows]))
affected.sort(key=lambda c:c['month']['month_wealth']);prior=[]
for r in rr:
 if r['cohort']!='Dec_new_reentry':continue
 cc=[c for c in camps if c['sid']==r['sid'] and c['closed'] is not None and c['closed']<r['decision_at']];assert cc
 c=max(cc,key=lambda c:c['closed']);lidset=[bykey[k]['layer_in_this_book'] for k in c['entry_keys']];cash=sum((D(native[lid]['cash']) for lid in lidset),Z)
 prior.append(dict(entry=context(r),prior_completed_stock_campaign_opened=c['opened'],prior_completed_stock_campaign_closed=c['closed'],prior_known_tradecash=cash,
  prior_recognized_AR=sum((D(native[lid]['dividend']) for lid in lidset),Z),prior_known_tradecash_sign='negative' if cash<0 else 'nonnegative'))
addold=read(E/'coverage_audit/add_preprofit_current_no60_v2/ADD_PREPROFIT_ROWS.json');addm={x['layer']:x for x in addold};adds=[]
for r in rr:
 if r['cohort']=='Dec_new_add':
  x=addm[r['layer_in_this_book']];assert iso(x['decision_at'])==r['decision_at'];adds.append(dict(month_entry=context(r),prior_known_held_unrealized=x['pre_close_unrealized'],prior_current_stock_campaign_wealth=x['pre_close_campaign_wealth']))
monthtrades=[t for t in book['trades'] if t['at'][:7]=='2022-12'];slip=sum((D(t['shares'])*abs(D(t['price'])-D(t['raw_open'])) for t in monthtrades),Z)
summary=dict(month='2022-12',dates=[START,END],native_days=22,NAV_begin=s['nav'],NAV_end=e['nav'],return_fraction=D(e['nav'])/D(s['nav'])-1,**agg,cohorts=cohorts,
 old_inventory_start_unrealized_sign=group([r for r in rr if r['cohort']=='old_inventory_at_Nov30'],'Nov30_unrealized_sign'),
 mean_previous_CLOSE_exposure=sum((d['previous_CLOSE_exposure'] for d in dayrows),Z)/22,mean_CLOSE_exposure=sum((d['CLOSE_exposure'] for d in dayrows),Z)/22,
 mean_previous_CLOSE_inventory=sum((D(d['previous_CLOSE_inventory']) for d in dayrows),Z)/22,fees=sum((D(d['fees']) for d in dayrows),Z),adverse_slippage_same_actual_qty=slip,
 direct_cost_before_same_executed_trades_wealth=agg['month_wealth']+sum((D(d['fees']) for d in dayrows),Z)+slip,
 ACT_active_OPEN=sum(d['ACT_at_OPEN'] for d in dayrows),ACT_active_CLOSE=sum(d['ACT_after_CLOSE'] for d in dayrows),actual_buys=len([t for t in monthtrades if t['side']=='buy']),actual_sell_fills=len([t for t in monthtrades if t['side']=='sell']),
 original_exit_part_reasons=dict(Counter(p['reason'] for t in monthtrades if t['side']=='sell' for p in t['parts'])),
 new_add_predecision_held_unrealized_positive=sum(D(x['prior_known_held_unrealized'])>0 for x in adds),new_add_layers=len(adds),
 reentry_past_completed_negative=total([x['entry'] for x in prior if x['prior_known_tradecash_sign']=='negative']),reentry_past_completed_nonnegative=total([x['entry'] for x in prior if x['prior_known_tradecash_sign']=='nonnegative']))
save('MONTH_SUMMARY.json',summary);save('ALL_AFFECTED_LAYERS.json',rr);save('DAILY_WEALTH_EXPOSURE_AND_FLOWS.json',dayrows);save('INDUSTRY_WEALTH.json',sorted(industries.items(),key=lambda x:x[1]['month_wealth']));save('STOCK_WEALTH.json',sorted(stock.values(),key=lambda x:x['month_wealth']));save('COMPLETE_STOCK_CAMPAIGNS.json',affected);save('FULL_FLAT_REENTRY_PREDECESSORS.json',prior);save('ADD_PREDECISION_HELD_STATE.json',adds)
# Existing benchmark aggregation, no exposure-matched counterfactual account.
axis=rowscsv(B/'ma63_monthly_axis_v1/MONTHLY_TIDY.csv');bm=[x for x in axis if x['month']=='2022-12'];assert len(bm)==4
ref=rowscsv(B/'benchmark_2022_2023/PERIODS.csv');hs=[x for x in ref if x['benchmark']=='HS300_PRICE_INDEX' and x['frequency']=='M' and x['period']=='2022-12'];assert len(hs)==1
nod=next(x for x in bm if x['policy']=='No60');eq(nod['net_PnL_CNY'],agg['month_wealth'],'published Dec month');eq(D(nod['mean_previous_close_exposure_pct'])/100,summary['mean_previous_CLOSE_exposure'],'published previous-exposure')
bench=dict(existing_observed_rows=bm,HS300_price_reference=hs[0],same_high_mean_exposure_claim_supported=True,exact_same_exposure_or_same_month_cash_capital_control=False,
 correction='No60/MA average previous-close exposure 87.2444%/90.1304% are similar high means, not equal daily weights. Each carries a different true month-start NAV, stocks/ETF universes and fee contracts differ. Raw yuan gap is not alpha or a single-factor result.',
 no_new_equal_exposure_simulation=True,existing_source=str(B/'ma63_monthly_axis_v1/READOUT.md'))
save('EXISTING_BENCHMARK_AND_EQUAL_EXPOSURE_LIMITS.json',bench)
# Actual cash release -> later same-OPEN full-flat reentry, traceable indices.
aud=book['audit'];settles={a['settlement']['settlement_id']:(i,a) for i,a in enumerate(aud) if a['kind']=='settle'};reserve={a['order_id']:(i,a) for i,a in enumerate(aud) if a['kind']=='reserve'}
chains=[];seen=set()
for x in sorted(prior,key=lambda x:D(x['entry']['cost']),reverse=True):
 r=x['entry'];lid=r['layer_in_this_book'];t=buys[lid];at=t['at'];day=at[:10]
 if day in seen:continue
 bi,ba=fills[t['receipt_id']];ri,res=reserve[ba['order_id']];sells=[t for t in monthtrades if t['at']==at and t['side']=='sell']
 if not sells:continue
 sources=[]
 for st in sells:
  fi,fa=fills[st['receipt_id']];sj,se=settles[st['settlement_id']];assert fi<sj<ri<bi
  sources.append(dict(sid=st['security_id'],name=META[st['security_id']]['name'],sell_receipt=st,settle_event=se,audit_fill_index=fi,audit_settle_index=sj))
 j=calendar.index(day);p=daily[j-1];d=daily[j];tt=[t for t in monthtrades if t['at'][:10]==day];sellnet=sum((D(t['gross_cny'])-D(t['fees_cny']) for t in tt if t['side']=='sell'),Z);buycash=sum((D(t['gross_cny'])+D(t['fees_cny']) for t in tt if t['side']=='buy'),Z);eq(D(p['available'])+sellnet-buycash,d['available'],'December native cash bridge')
 chains.append(dict(day=day,actual_sell_then_settle=sources,target_reentry=x,native_reserve_event=res,audit_reserve_index=ri,audit_fill_index=bi,previous_CLOSE_available=p['available'],day_sellnet=sellnet,day_buycash=buycash,end_CLOSE_available=d['available'],
  limitation='Cash is fungible; prior cash/other sales and freed permission/resources coexist. Sequence is not unique causal funding or evidence removing reentry saves its P&L.'))
 seen.add(day)
 if len(chains)==3:break
save('ACTUAL_EXIT_TO_REENTRY_CASH_CHAINS.json',chains)
save('VALIDATION.json',dict(status='PASS',original_cold_baseline_identity_receipt=str(ROOT/'independent_review/FULL_BASELINE_AUDIT.json'),month_boundary_and_existing_finance_exact=True,
 original_enriched_entry_rows_key_time_cost_exact=2265,no_original_partial_held_in_month=True,new_accounts=0,new_rules=0,no_counterfactual_equal_exposure_account=True))
SRC[str(Path(__file__).resolve())]=sha(__file__);save('SOURCE_SHA256.json',SRC);save('DELIVERABLE_SHA256.json',{str(p.resolve()):sha(p) for p in O.iterdir() if p.is_file() and p.name!='DELIVERABLE_SHA256.json'})
print(json.dumps(summary,ensure_ascii=False,default=str));print('WORST_STOCKS',sorted(stock.values(),key=lambda x:x['month_wealth'])[:10]);print('WORST_INDUSTRIES',sorted(industries.items(),key=lambda x:x[1]['month_wealth'])[:10])
