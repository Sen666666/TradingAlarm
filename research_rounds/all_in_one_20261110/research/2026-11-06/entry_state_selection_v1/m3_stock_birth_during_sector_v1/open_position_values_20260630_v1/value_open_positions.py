"""As-of close inventory valuation only. No trading, forecast, or lifecycle rerun."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
import json,hashlib,datetime
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;E=O.parent;P=E/'fixed_permit_recovery_2026_v1'
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
MP=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
ASOF=pd.Timestamp('2026-06-30');SLIP=D('.0005')
read=lambda p:json.loads(Path(p).read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources={}
def src(p):
 p=Path(p);sources[str(p)]=sha(p);return p
def save(name,v):
 with (O/name).open('x') as f:json.dump(v,f,ensure_ascii=False,indent=2,default=str,allow_nan=False);f.write('\n')
def near(a,b):return abs(D(str(a))-D(str(b)))<D('0.0000001')
csv=lambda p:pd.read_csv(src(p),float_precision='round_trip',low_memory=False)
for n,h in read(src(P/'FINAL_OUTPUT_HASHES.json')).items():assert sha(P/n)==h,(n,'recovery output drift')
z=csv(P/'report/CORE_AND_FULL_ROUNDS.csv');h=z[z.status.eq('OPEN_CENSORED_AT_2026_06_30')].copy()
assert len(z)==46 and len(h)==15 and h.round_id.is_unique
a=csv(P/'ALL_FIXED46_ACTIONS.csv');assert pd.to_datetime(a.day).le(ASOF).all()
claims=read(src(P/'economic/CLAIMS.json'));events={e['economic_event_id']:e for e in read(src(P/'ECONOMIC_EVENTS.json'))}
rules=read(src(B/'inputs-v2/market-rules.json'));manifest={m['symbol']:m for m in read(src(MP))}
src(Path(__file__))
def version(rows,day):
 v=[x for x in rows if x['from']<=day and (not x.get('to') or day<x['to'])]
 assert len(v)==1;return v[0]
def fee_parts(sid,day,q,px,side):
 ds=str(day.date());venue=version(rules['venue_versions'][sid],ds)['venue']
 sched=version(rules['fee_versions'][venue],ds)['schedule'];out=[]
 for c in sched['components']:
  if c.get('side','both') not in ['both',side]:continue
  basis=c.get('amount_basis','notional');amount=D(q)*px if basis=='notional' else D(q) if basis=='shares' else D(q)*D(str(rules['security_metadata'][sid]['par_value']))
  value=max(D(str(c.get('minimum_local',0))),amount*D(str(c['rate'])))
  if c.get('maximum_local') is not None:value=min(value,D(str(c['maximum_local'])))
  if c.get('rounding_unit') is not None:
   unit=D(str(c['rounding_unit']));value=(value/unit).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil' else ROUND_HALF_UP)*unit
  out.append(dict(schedule_id=sched['schedule_id'],component=c,value=value))
 return out
rows=[];fees=[];ent=[];barchecks=[];actions_checked=0
for r in h.itertuples():
 m=manifest[r.sid];sp=src(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')))
 assert sha(sp)==m['source_sha256'][str(sp)]
 frame=pd.read_parquet(sp).loc[:ASOF]
 assert frame.index.is_unique and ASOF in frame.index
 bar=frame.loc[ASOF];close=D(str(bar.raw_close));assert close.is_finite() and close>0
 for col in ['observed_bar','price_eligible','volume_eligible','source_invalid','synthetic_event_bar']:
  assert isinstance(bar[col],(bool,np.bool_)),(r.sid,col,'nonboolean')
 assert bar.observed_bar and bar.price_eligible and bar.volume_eligible and not bar.source_invalid and not bar.synthetic_event_bar
 assert all(np.isfinite(bar[c]) and bar[c]>0 for c in ['adjustment_factor','volume_factor'])
 tr=a[a.round_id.eq(r.round_id)].to_dict('records')
 core=add=0;buy=buygross=buyfees=sellnet=sellgross=sellfees=D(0);bought_today=0
 for t in tr:
  day=pd.Timestamp(t['day']);assert day<=ASOF;qty=int(t['q']);px=D(str(t['price']));f=D(str(t['fee']))
  assert near(f,sum((x['value'] for x in fee_parts(r.sid,day,qty,px,'buy' if t['side'].startswith('buy') else 'sell')),D(0)))
  if t['side']=='buy_core':core+=qty
  elif t['side']=='buy_add':add+=qty
  elif t['side']=='sell_add':assert qty==add;add=0
  elif t['side']=='sell_all':assert qty==core+add;core=add=0
  else:raise AssertionError(t['side'])
  if t['side'].startswith('buy'):
   buy+=qty*px+f;buygross+=qty*px;buyfees+=f
   if day==ASOF:bought_today+=qty
  else:sellnet+=qty*px-f;sellgross+=qty*px;sellfees+=f
  actions_checked+=1
 q=core+add;assert q==int(r.core_qty+r.add_qty) and near(buy,r.total_buy_cash)
 owned=[c for c in claims if c['owner_round_id']==r.round_id]
 gross=recognized=paid=receivable=reserve=D(0)
 for c in owned:
  ev=events[c['economic_event_id']]
  assert c['sid']==r.sid and pd.Timestamp(c['record_date'])<=ASOF and pd.Timestamp(c['ex_date'])<=ASOF
  assert c['recognized'];g=D(c['record_q'])*D(c['d_cash']);net=D(c['amount'])
  assert net==g*D('.8');recognized+=net;gross+=g;reserve+=g-net
  if pd.Timestamp(c['pay_date'])<=ASOF:assert c['settled'];paid+=net
  else:assert not c['settled'];receivable+=net
  ent.append(dict(round_id=r.round_id,sid=r.sid,economic_event_id=c['economic_event_id'],record_date=c['record_date'],ex_date=c['ex_date'],pay_date=c['pay_date'],record_quantity=c['record_q'],gross_dividend=g,net80_dividend=net,proxy_20pct_reserve=g-net,settled=c['settled'],actual_tax_paid=None,actual_tax_due=None))
 px=close*(1-SLIP);parts=fee_parts(r.sid,ASOF,q,px,'sell');sf=sum((x['value'] for x in parts),D(0))
 for v in parts:fees.append(dict(round_id=r.round_id,sid=r.sid,valuation_day=ASOF,assumed_quantity=q,assumed_sell_price=px,**v))
 liquidation_gross=D(q)*px;liquidation_net=liquidation_gross-sf
 # All cash returned by this isolated permit plus its inventory's assumed net liquidation.
 terminal_resources=sellnet+paid+receivable+liquidation_net
 pnl=terminal_resources-buy;ret=pnl/buy
 assert near(pnl,r.last_mark_net) and near(ret,r.last_mark_fraction) and close==D(str(r.last_raw_close)) and pd.Timestamp(r.last_known_mark_day)==ASOF
 assert near(sellnet-buy+paid,r.cashflow_to_date)
 if pd.notna(r.cash_after_payouts):assert near(sellnet-buy+paid,r.cash_after_payouts)
 tax_status='ACTUAL_PERSONAL_TAX_DUE_UNKNOWN_NET80_PROXY_ONLY' if gross else 'NO_MODELED_DIVIDEND_TAX_RESERVE_NOT_CERTIFIED_PERSONAL_TAX_ZERO'
 cover=r.financial_coverage_status
 rows.append(dict(round_id=r.round_id,sid=r.sid,name=r.name,recovery_origin=r.recovery_origin,valuation_day=ASOF,entry_day=r.entry_day,
  core_quantity=core,add_quantity=add,total_quantity=q,t1_locked_quantity=bought_today,t1_sellable_quantity=q-bought_today,
  full_same_day_liquidation_not_blocked_by_T1=bought_today==0,
  raw_close=close,adjustment_factor=float(bar.adjustment_factor),volume_factor=float(bar.volume_factor),
  raw_source_kind=bar.source_kind,raw_source_path=bar.source_path,
  gross_buy_notional=buygross,buy_fees=buyfees,total_buy_cash_including_fees=buy,
  historic_sell_gross=sellgross,historic_sell_fees=sellfees,historic_sell_net=sellnet,
  gross_known_dividend=gross,net80_dividend_recognized=recognized,net80_dividend_paid=paid,net80_receivable=receivable,proxy_dividend_tax_reserve_20pct=reserve,
  inventory_at_raw_close=D(q)*close,assumed_slippage_cost=D(q)*(close-px),assumed_sell_price=px,
  hypothetical_full_liquidation_gross=liquidation_gross,hypothetical_full_liquidation_fee=sf,hypothetical_full_liquidation_net_proceeds=liquidation_net,
  conditional_terminal_resources=terminal_resources,conditional_net_pnl=pnl,conditional_return_on_all_buy_cash=ret,conditional_resource_multiple=terminal_resources/buy,
  prior_last_mark_net=r.last_mark_net,prior_last_mark_fraction=r.last_mark_fraction,mark_matches_original=True,
  financial_coverage_status=cover,financial_coverage_supported=cover in ['LOCAL_NO_ACTION_EVIDENCE','VERIFIED_ACTIONS_SCENARIO'],
  financial_coverage_reasons=r.coverage_reasons if pd.notna(r.coverage_reasons) else None,
  dividend_tax_status=tax_status,actual_tax_paid=None,actual_tax_due=None,
  exchange_orderability='UNKNOWN_LIMITS_SUSPENSION_QUEUE_AND_CAPACITY_NOT_VERIFIED',
  classification='OPEN_MARK_NOT_CLOSED_WIN_NOT_ACCOUNT_RETURN'))
 barchecks.append(dict(sid=r.sid,day=ASOF,signal_path=str(sp),signal_sha256=sha(sp),bar_present=True,close=close,observed=True,price_and_volume_eligible=True,non_synthetic=True,source_not_invalid=True,decision_uses_no_post_asof_data=True))
out=pd.DataFrame(rows);out.to_csv(O/'OPEN_POSITION_VALUES.csv',index=False)
pd.DataFrame(ent).to_csv(O/'DIVIDEND_AND_TAX_PROXY.csv',index=False)
pd.DataFrame(fees).to_json(O/'LIQUIDATION_FEE_COMPONENTS.json',orient='records',indent=2,force_ascii=False,default_handler=str)
pd.DataFrame(barchecks).to_csv(O/'ASOF_BAR_EVIDENCE.csv',index=False)
summaries=[]
for scope,g in [('ALL15_CONDITIONAL_DIAGNOSTIC',rows),('FINANCIALLY_SUPPORTED13',[x for x in rows if x['financial_coverage_supported']]),('FINANCIAL_UNKNOWN2',[x for x in rows if not x['financial_coverage_supported']])]:
 sums={k:sum((x[k] for x in g),D(0)) for k in ['total_buy_cash_including_fees','historic_sell_net','gross_known_dividend','net80_dividend_paid','net80_receivable','proxy_dividend_tax_reserve_20pct','inventory_at_raw_close','assumed_slippage_cost','hypothetical_full_liquidation_fee','hypothetical_full_liquidation_net_proceeds','conditional_terminal_resources','conditional_net_pnl']}
 summaries.append(dict(scope=scope,permits=len(g),**sums,aggregate_conditional_return=sums['conditional_net_pnl']/sums['total_buy_cash_including_fees'],t1_locked_quantity=sum(x['t1_locked_quantity'] for x in g),not_shared_account_nav=True,not_realized_return=True))
save('SUMMARY.json',dict(asof=ASOF,held_permits=15,original_held=9,recovered_held=6,closed25_excluded=True,execution_unknown3_excluded=True,nofill2_pending1_excluded=True,held_financial_supported=13,held_financial_unknown=2,actions_checked=actions_checked,all15_prior_marks_match=True,aggregates=summaries,economic_runs=0,market_prediction=False,actual_tax_due_known=False,limitations=['NET80 reserves20% from known gross dividends, not proof of actual withheld/paid/outstanding tax; no second deduction of proxy reserve.','Full hypothetical liquidation for688783 is not permitted onJune30 by T+1; quantity278 entered that day.','Observed close and fee arithmetic do not verify exchange limit-down/suspension/orderbook queue/capacity or attainable5bp slippage.','Two held permits retain financial coverage UNKNOWN.','Independent permit cash sums are not NAV or realized return of a shared account.','Frozen signals, queue and allocations were not reconstructed; upstream archival data/static pool NON-PIT.']))
save('SOURCE_HASHES.json',sources)
save('OUTPUT_HASHES.json',{p.name:sha(p) for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print(json.dumps(summaries,ensure_ascii=False,indent=2,default=str))
