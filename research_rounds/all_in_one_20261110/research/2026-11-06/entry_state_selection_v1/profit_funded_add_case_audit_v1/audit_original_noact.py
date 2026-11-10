"""Frozen NOACT source-only cash/risk arithmetic. No strategy/consumer imports."""
from pathlib import Path
from decimal import Decimal as D, ROUND_CEILING, ROUND_HALF_UP
from collections import defaultdict, Counter
import json, gzip, hashlib, csv, copy, math
import pandas as pd

R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=Path(__file__).resolve().parent
A=R/'act_only_ablation_continuous_v1'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
RAW=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
Z=D(0); TOL=D('0.000001'); END='2026-05-15'
sources={};checks=Counter()
def dec(v):return D(str(v))
def day(v):return str(v)[:10]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def source(p,expected=None):
 p=Path(p); h=sha(p)
 if expected:assert h==expected,('hash mismatch',str(p))
 if str(p) in sources:assert sources[str(p)]==h
 sources[str(p)]=h;return p
def read(p,expected=None):return json.loads(source(p,expected).read_text())
def para(p,expected=None):return pd.read_parquet(source(p,expected))
def eq(a,b,label):
 assert abs(dec(a)-dec(b))<TOL,(label,str(a),str(b));checks[label]+=1
def dump(name,value):
 with (O/name).open('x')as f:json.dump(value,f,ensure_ascii=False,indent=2,default=str,allow_nan=False)
def table(name,rows):
 if not rows:return
 keys=list(dict.fromkeys(k for r in rows for k in r))
 with (O/name).open('x')as f:
  w=csv.DictWriter(f,keys);w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False,default=str)if isinstance(v,(dict,list))else v for k,v in r.items()})
def ver(rows,at):
 rows=[x for x in rows if x['from']<=day(at) and (not x.get('to')or day(at)<x['to'])];assert len(rows)==1;return rows[0]
def schedule(sid,at):return ver(rules['fee_versions'][ver(rules['venue_versions'][sid],at)['venue']],at)['schedule']
def fee(sid,at,side,q,p):
 if not q:return Z
 out=Z
 for c in schedule(sid,at)['components']:
  if c.get('side','both')not in ('both',side):continue
  basis=c.get('amount_basis','notional');base=dec(q)*p if basis=='notional'else dec(q)
  if basis=='par_value':base*=dec(rules['security_metadata'][sid]['par_value'])
  v=max(dec(c.get('minimum_local',0)),base*dec(c['rate']))
  if c.get('maximum_local')is not None:v=min(v,dec(c['maximum_local']))
  if c.get('rounding_unit')is not None:
   u=dec(c['rounding_unit']);v=(v/u).to_integral_value(rounding=ROUND_CEILING if c.get('rounding_mode')=='ceil'else ROUND_HALF_UP)*u
  out+=v
 return out
def latest(df,d):return df.loc[:pd.Timestamp(d)].iloc[-1]
def factor_at(sid,d):
 # Original source's factor is theoretical-ex-price, updated from strict prior
 # closes and preknown action terms. A signal day's later rows are never used.
 f=data[sid]['facts'];return dec(latest(f,d)['factor'])
def rawmark(sid,d,clock):
 raw=data[sid]['raw'];t=pd.Timestamp(d)
 if clock=='OPEN':
  assert t in raw.index and pd.notna(raw.loc[t,'open']) and raw.loc[t,'open']>0
  return dec(raw.loc[t,'open']),d
 v=latest(raw,d);return dec(v['close']),day(v.name)
def newlayer(t):return dict(qty=int(t['shares']),cost=dec(t['gross_cny'])+dec(t['fees_cny']),buy_cost=dec(t['gross_cny'])+dec(t['fees_cny']),cash=-dec(t['gross_cny'])-dec(t['fees_cny']),realized=Z,dividend=Z,sale_net=Z)
def state_at(events,at,before_trade=None):
 state={}
 for kind,e in events:
  et=e['receivable']['ex_at']if kind=='div'else e['at']
  if et>at:break
  if before_trade is not None and kind=='trade'and e['receipt_id']==before_trade:break
  if kind=='div':
   total=sum(s['qty']for s in state.values());assert total>0
   for s in state.values():s['dividend']+=dec(e['receivable']['net_local'])*dec(s['qty'])/dec(total)
  elif e['side']=='buy':state[e['layer']]=newlayer(e)
  else:
   for p in e['parts']:
    if p['layer']not in state:continue
    s=state[p['layer']];q=int(p['shares']);released=s['cost']*dec(q)/dec(s['qty']);s['qty']-=q;s['cost']-=released;s['sale_net']+=dec(p['net_cash']);s['cash']+=dec(p['net_cash']);s['realized']+=dec(p['net_cash'])-released
 return state
def daily_layers(d):return daily[d]['layers']
def floor_info(sid,lid,d):
 s=daily_layers(d).get(lid);assert s is not None,('missing live floor',sid,lid,d)
 f=dec(s['last_core_line'])if s['kind']=='core'else dec(s['floor'])
 return f,'I_last_core_line'if s['kind']=='core'else 'ADD_effective_CP_max_old_I_CP'
def snapshot(r,states,at,clock,floor_day,add=None):
 sid=r['sid'];d=day(at);mark,markday=rawmark(sid,d,clock);factor=factor_at(sid,d)
 # Every selected OPEN having a buy has a fact row; no action between last
 # observed factor and OPEN may silently remain unprocessed.
 if clock=='OPEN':
  lastfact=day(latest(data[sid]['facts'],d).name)
  assert not any(lastfact<a['effective_date']<=d for a in data[sid]['actions'])
 live={k:s for k,s in states.items()if s['qty']};Q=sum(s['qty']for s in live.values());K=sum((s['cost']for s in live.values()),Z)
 cash=sum((s['cash']for s in states.values()),Z);real=sum((s['realized']for s in states.values()),Z);div=sum((s['dividend']for s in states.values()),Z)
 eq(cash,real-K,'cash_equals_realized_minus_K')
 mx=mark*D('.9995');markfee=fee(sid,at,'sell',Q,mx);marknet=dec(Q)*mx-markfee
 floor_net=Z;layer_mark_net=Z;layer_details=[]
 for lid,s in live.items():
  F,kind=floor_info(sid,lid,floor_day);rawF=F/factor;X=rawF*D('.9995');sf=fee(sid,at,'sell',s['qty'],X);mf=fee(sid,at,'sell',s['qty'],mx)
  v=dec(s['qty'])*X-sf;vm=dec(s['qty'])*mx-mf;floor_net+=v;layer_mark_net+=vm
  layer_details.append(dict(layer_id=lid,kind=buys[lid]['kind'],qty=s['qty'],remaining_cost=s['cost'],realized_net=s['realized'],booked_dividend=s['dividend'],floor_adjusted=F,floor_raw=rawF,floor_source=kind,floor_source_close=floor_day,scenario_exit_raw_after_slippage=X,scenario_sell_fee=sf,scenario_net_remaining=v-s['cost'],scenario_full_layer_net=s['cash']+s['dividend']+v,net_mark_layer_order=vm-s['cost'],giveback_mark_to_floor=vm-v,principal_loss_remaining=max(Z,s['cost']-v)))
  eq(s['cash']+v+s['dividend'],s['realized']+(v-s['cost'])+s['dividend'],'layer_cash_bridge')
 full_mark=cash+div+marknet;full_floor=cash+div+floor_net
 eq(full_floor,real+div+floor_net-K,'round_floor_cash_bridge')
 eq(full_floor,sum((x['scenario_full_layer_net']for x in layer_details),Z)+sum((s['cash']+s['dividend']for s in states.values()if not s['qty']),Z),'layer_sum_round_bridge')
 fr=latest(data[sid]['facts'],floor_day)
 row=dict(round_id=r['round_id'],sid=sid,at=at,clock=clock,floor_source_day=floor_day,mark_raw=mark,mark_source_day=markday,factor=factor,known_I_adjusted=fr.i_floor if pd.notna(fr.i_floor)else None,held_qty=Q,remaining_buy_cost_including_fees=K,cumulative_realized_net_sales=real,cumulative_trade_cash_from_zero=cash,booked_dividend_accrual=div,dividend_paid=Z,dividend_status='BOOKED_RECEIVABLE_NO_PAYMENT_EVENT; external payout UNKNOWN',net_liquidation_sale_one_order=marknet,remaining_net_liquidation_profit_one_order=marknet-K,full_round_net_liquidation_profit_one_order=full_mark,remaining_net_liquidation_profit_layer_orders=layer_mark_net-K,full_round_net_liquidation_profit_layer_orders=cash+div+layer_mark_net,old_layer_protection_net_remaining=floor_net-K,old_full_round_protection_net=full_floor,old_mark_to_protection_giveback=marknet-floor_net,old_mark_layer_orders_to_protection_giveback=layer_mark_net-floor_net,old_round_principal_loss_at_protection=max(Z,-full_floor),layer_details=layer_details,fee_scenario='Separate exit order per live layer at each own floor, dated this clock. One-order mark and per-layer-order mark both shown; independent minima are an explicit scenario convention, not actual repeated charges.',scenario_status='LAYERED_PROTECTION_ESTIMATE_NOT_SIMULTANEOUS_EXECUTABLE_EXIT; gaps/T+1/missing OPEN not capped')
 if add:
  q=add['q'];p=add['p'];F=dec(add['floor']);X=F/factor*D('.9995');bf=fee(sid,at,'buy',q,p);sf=fee(sid,at,'sell',q,X);gross=dec(q)*p;cost=gross+bf;risk=dec(q)*(p-X)+bf+sf
  row.update(new_layer_id=add['lid'],new_quantity=q,new_quantity_basis=add['quantity_basis'],new_reference_price=p,new_floor_adjusted=F,new_floor_raw=F/factor,new_scenario_exit_price=X,new_buy_notional=gross,new_buy_fee=bf,new_buy_cost=cost,new_scenario_sell_fee=sf,new_scenario_price_loss=dec(q)*(p-X),new_signed_scenario_risk=risk,new_nonnegative_scenario_risk=max(Z,risk),full_round_protection_net_after=full_floor-risk,round_principal_loss_after=max(Z,risk-full_floor),old_profit_buffer_minus_new_risk=full_mark-risk,full_mark_profit_does_not_reserve_old_giveback=True,original_signal_intent=add.get('intent'))
  eq(row['full_round_protection_net_after'],cash-cost+div+floor_net+dec(q)*X-sf,'add_scenario_cash_bridge')
 return row

def main():
 global rules,data,daily,buys
 assert O==R/'profit_funded_add_case_audit_v1'
 assert not(O/'SUMMARY.json').exists()
 source(__file__);frozen=read(O/'FROZEN_CASES.json')
 for p,h in frozen['source_sha256'].items():source(p,h)
 orig_hash=read(A/'run/OUTPUT_HASHES.json');source(A/'run/pair/NOACT.json.gz',orig_hash['pair/NOACT.json.gz'])
 a=json.load(gzip.open(A/'run/pair/NOACT.json.gz','rt'))
 rframe=pd.read_csv(A/'analysis/STOCK_ROUNDS.csv');rf=rframe[(rframe.account=='NOACT')&rframe.round_id.isin(frozen['round_ids'])].set_index('round_id').loc[frozen['round_ids']].reset_index()
 selected=rf.to_dict('records');assert len(selected)==26 and not rf.split_events.any()
 for r in selected:r['layer_ids']=json.loads(r['layer_ids'])
 lids={k for r in selected for k in r['layer_ids']};sids={r['sid']for r in selected};buys={t['layer']:t for t in a['trades']if t['side']=='buy'}
 source(A/'run/pair/daily.jsonl.gz',orig_hash['pair/daily.jsonl.gz']);daily={}
 for line in gzip.open(A/'run/pair/daily.jsonl.gz','rt'):
  x=json.loads(line)
  if x['account']=='NOACT':daily[day(x['at'])]=dict(at=x['at'],layers={v['id']:v for v in x['layers']if v['id']in lids},pending_sells=x['pending_sells'])
 cal=sorted(daily)
 cf=read(R/'mobile_first_probe_protection_v1/conditional_paths_v1/run/SOURCE_FREEZE.json');rulespath=next(p for p in cf if p.endswith('/execution-rules-v2.json'));rules=read(rulespath,cf[rulespath])
 manifest={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')};data={}
 for sid in sorted(sids):
  m=manifest[sid];facts=para(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]);raw=para(RAW/f'bars/{sid}.parquet');raw=raw.set_index(pd.DatetimeIndex(pd.to_datetime(raw.trade_date))).sort_index();actions=read(RAW/f'actions/{sid}.json')['events']
  cp=para(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']]);data[sid]=dict(facts=facts.loc[:END],raw=raw.loc[:END],actions=actions,cp=cp.loc[:END])
 intents={}
 for d in a['decisions']:
  for i in d['intents']:
   if i['sid']in sids:intents[(d['at'],i['sid'],i['kind'])]=i
 alayers={l['id']:l for l in a['layers']};auditfills={v['receipt']['receipt_id']:v for v in a['audit']if v['kind']=='fill'}
 rows=[];layerrows=[];summaries=[];bridges=[];traderows=[];dailypaths=[]
 for r in selected:
  sid=r['sid'];rid=r['round_id'];ts=[t for t in a['trades']if t['security_id']==sid and r['opened']<=t['at']<=r['closed']]
  assert all(t['layer']in r['layer_ids'] for t in ts if t['side']=='buy')
  divs=[e for e in a['audit']if e['kind']=='dividend_accrual'and e['receivable']['security_id']==sid and r['opened']<e['receivable']['ex_at']<r['closed']]
  assert not any(e['kind']=='dividend_payment'and e.get('sid')==sid for e in a['audit'])
  events=sorted([('trade',t)for t in ts]+[('div',e)for e in divs],key=lambda v:v[1]['receivable']['ex_at']if v[0]=='div'else v[1]['at'])
  for t in ts:
   p=dec(t['price']);q=t['shares'];eq(dec(q)*p,t['gross_cny'],'actual_fill_gross');eq(p,dec(t['raw_open'])*(D('1.0005')if t['side']=='buy'else D('.9995')),'actual_raw_open_slippage');eq(fee(sid,t['at'],t['side'],q,p),t['fees_cny'],'actual_dated_fee')
   eq(dec(data[sid]['raw'].loc[pd.Timestamp(day(t['at'])),'open']),t['raw_open'],'actual_raw_source_open')
   traderows.append(dict(round_id=rid,**t))
  for lid in r['layer_ids'][1:]:
   b=buys[lid];sig=day(b['signal_at']);op=day(b['at']);prior=cal[cal.index(op)-1];intent=intents[(b['signal_at'],sid,b['kind'])]
   states=state_at(events,b['signal_at']);reference=rawmark(sid,sig,'CLOSE')[0]*D('1.0005')
   # Close-side planned q is known; filled q is intentionally not backfilled.
   close_add=dict(q=int(intent['cap']),p=reference,floor=b['floor'],lid=lid,quantity_basis='SIGNAL_KNOWN_CAP_NOT_PROMISED_FILL',intent=intent)
   z=snapshot(r,states,b['signal_at'],'CLOSE',sig,close_add);z['actual_later_fill_q_for_link_only']=b['shares'];rows.append(z)
   for v in z['layer_details']:layerrows.append(dict(round_id=rid,new_layer_id=lid,clock='CLOSE',at=b['signal_at'],**v))
   states=state_at(events,b['at'],b['receipt_id']);opened_add=dict(q=int(b['shares']),p=dec(b['price']),floor=b['floor'],lid=lid,quantity_basis='ACTUAL_PROXY_FILL_Q_AT_KNOWN_OPEN',intent=intent)
   z=snapshot(r,states,b['at'],'OPEN',prior,opened_add);eq(z['new_buy_fee'],b['fees_cny'],'new_actual_buy_fee');rows.append(z)
   for v in z['layer_details']:layerrows.append(dict(round_id=rid,new_layer_id=lid,clock='OPEN',at=b['at'],**v))
  for d in cal:
   if not day(r['opened'])<=d<=day(r['closed']):continue
   st=state_at(events,daily[d]['at']);Q=sum(v['qty']for v in st.values());saved={k:v for k,v in daily[d]['layers'].items()if k in r['layer_ids']}
   eq(Q,sum(v['qty']for v in saved.values()),'daily_round_quantity')
   for k,v in saved.items():eq(st[k]['qty'],v['qty'],'daily_layer_quantity');eq(st[k]['cash'],v['cash'],'daily_layer_cash');eq(st[k]['dividend'],v['dividend'],'daily_layer_dividend')
   mark,md=rawmark(sid,d,'CLOSE');K=sum((v['cost']for v in st.values()),Z);cash=sum((v['cash']for v in st.values()),Z);real=sum((v['realized']for v in st.values()),Z);div=sum((v['dividend']for v in st.values()),Z);px=mark*D('.9995');net=dec(Q)*px-fee(sid,d,'sell',Q,px)
   eq(cash+net+div,real+net-K+div,'daily_round_cash_bridge')
   dailypaths.append(dict(round_id=rid,sid=sid,day=d,qty=Q,remaining_cost=K,realized_net=real,cumulative_trade_cash=cash,booked_dividend=div,paid_dividend=Z,raw_mark=mark,mark_source_day=md,net_remaining_mark=net-K,full_round_net_liquidation_mark=cash+net+div))
  endstate=state_at(events,r['closed']);endcash=sum((s['cash']for s in endstate.values()),Z);enddiv=sum((s['dividend']for s in endstate.values()),Z);eq(endcash,r['cash'],'closed_round_cash');eq(endcash+enddiv,r['pnl'],'closed_round_pnl')
  outcomes=[]
  for lid in r['layer_ids']:
   st=endstate[lid];l=alayers[lid];eq(st['cash'],l['cash'],'closed_layer_cash');eq(st['dividend'],l['dividend'],'closed_layer_dividend');outcomes.append(dict(layer_id=lid,kind=l['kind'],buy_at=buys[lid]['at'],buy_cost=st['buy_cost'],net_pnl=st['cash']+st['dividend'],cash_pnl=st['cash'],booked_dividend=st['dividend'],closed=l['closed'],reason=l['reason']))
   # Exit decomposition is retrospective only; actual trigger first precedes fill.
   b=buys[lid];q0=int(b['shares']);sells=[(t,p)for t in ts if t['side']=='sell'for p in t['parts']if p['layer']==lid];exits=[e for e in a['audit']if e['kind']=='pilot_layer_exit'and lid in e.get('layers',[])];assert exits
   trigger=min(exits,key=lambda e:e['at']);td=day(trigger['at']);ff,ftype=floor_info(sid,lid,td);tf=factor_at(sid,td);rawfloor=ff/tf;tc,_=rawmark(sid,td,'CLOSE');valid=data[sid]['raw'].loc[pd.Timestamp(td):];valid=valid[(valid.index>pd.Timestamp(td))&valid.open.notna()&(valid.open>0)];first=valid.index[0];firstday=day(first);firstop=dec(valid.iloc[0].open);nextcommon=cal[cal.index(td)+1]
   qsum=sum(int(p['shares'])for _,p in sells);assert qsum==q0
   entryfloor=Z;overshoot=Z;nextgap=Z;delay=Z;slip=Z;sellfees=Z
   for t,p in sells:
    q=dec(p['shares']);sg=q*dec(t['price']);sf=dec(t['fees_cny'])*q/dec(t['shares']);eq(sg-sf,p['net_cash'],'actual_sell_part_net')
    entryfloor+=q*(dec(b['price'])-rawfloor);overshoot+=q*(rawfloor-tc);nextgap+=q*(tc-firstop);delay+=q*(firstop-dec(t['raw_open']));slip+=q*(dec(t['raw_open'])-dec(t['price']));sellfees+=sf
   loss=entryfloor+overshoot+nextgap+delay+slip+dec(b['fees_cny'])+sellfees-st['dividend'];eq(loss,-st['cash']-st['dividend'],'layer_exit_loss_bridge')
   bridges.append(dict(round_id=rid,sid=sid,layer_id=lid,is_initial=lid==r['initial_layer'],buy_at=b['at'],trigger_at=trigger['at'],trigger_reason=trigger['reason'],trigger_floor_adjusted=ff,trigger_floor_kind=ftype,trigger_factor=tf,trigger_floor_raw=rawfloor,trigger_raw_close=tc,first_observed_open_day=firstday,first_observed_open=firstop,immediate_next_common_open_day=nextcommon,missing_common_days=[d for d in cal if td<d<firstday],actual_last_sell=sells[-1][0]['at'],T1_buy_trigger_same_day=day(b['at'])==td,T1_all_sales_later_than_buy=all(day(t['at'])>day(b['at'])for t,p in sells),entry_to_trigger_floor_loss=entryfloor,trigger_floor_to_close_loss=overshoot,trigger_close_to_first_observed_open_loss=nextgap,first_observed_open_to_actual_sale_loss=delay,sell_slippage=slip,buy_fee=dec(b['fees_cny']),allocated_sell_fees=sellfees,negative_dividend=-st['dividend'],total_signed_loss=loss,actual_net_pnl=st['cash']+st['dividend'],residual=loss+st['cash']+st['dividend'],scope='EX_POST_LOSS_ATTRIBUTION_ONLY; never fed into entry risk; first observed open need not be immediate next common open; I floor is risk reference, not guaranteed I invalidation price'))
  eq(sum((v['net_pnl']for v in outcomes),Z),r['pnl'],'layer_final_sum_round_pnl')
  sr=dict(round_id=rid,sid=sid,opened=r['opened'],closed=r['closed'],original14=rid in frozen['original14']['round_ids'],initial_layer=r['initial_layer'],initial_kind=r['initial_kind'],layers=len(outcomes),subsequent_buy_count=len(outcomes)-1,subsequent_ADD_count=sum(v['kind']=='add'for v in outcomes[1:]),round_net_pnl=endcash+enddiv,round_cash_pnl=endcash,booked_dividend=enddiv,paid_dividend=Z,initial_layer_pnl=outcomes[0]['net_pnl'],subsequent_layers_pnl=sum((v['net_pnl']for v in outcomes[1:]),Z),subsequent_buy_cost=sum((v['buy_cost']for v in outcomes[1:]),Z),layer_outcomes=outcomes,partial_sell_fills=r['partial_sell_fills'],deleting_adds_is_not_counterfactual=True)
  summaries.append(sr)
  print('DONE',rid,sid,'later',sr['subsequent_buy_count'],'net',sr['round_net_pnl'],flush=True)
 for name,rr in [('ADD_CLOCK_SNAPSHOTS',rows),('OLD_LAYER_SCENARIOS',layerrows),('ROUND_SUMMARY',summaries),('ACTUAL_TRADES',traderows),('LAYER_EXIT_LOSS_BRIDGE',bridges),('ROUND_DAILY_CASH_BRIDGE',dailypaths)]:table(name+'.csv',rr);dump(name+'.json',rr)
 opens=[x for x in rows if x['clock']=='OPEN'];summary=dict(status='PASS_SOURCE_ONLY_ARITHMETIC',account_runs=0,indicator_recomputations=0,new_coefficients=0,original14=14,supplements=12,rounds=26,subsequent_buy_fills=len(opens),subsequent_ADD_fills=sum(buys[x['new_layer_id']]['kind']=='add'for x in opens),original14_subsequent_ADD=1,checks=dict(checks),open_old_remaining_mark_positive=sum(x['remaining_net_liquidation_profit_one_order']>0 for x in opens),open_entire_round_mark_positive=sum(x['full_round_net_liquidation_profit_one_order']>0 for x in opens),new_risk_exceeds_full_mark_profit=sum(x['new_signed_scenario_risk']>x['full_round_net_liquidation_profit_one_order']for x in opens),post_ADD_protection_net_negative=sum(x['full_round_protection_net_after']<0 for x in opens),limits=['Historical-label examples, not OOS or estimated population efficacy.','Original NOACT did not contain the new V>K profitability gate.','Layer-by-layer floor scenario with separate dated fees; never guaranteed simultaneous executable liquidation.','OPEN factor uses date-known theoretical ex-price mapping, preknown corporate-action terms not independently PIT-verified.','SOURCE_ONLY, no altered account or deleted-ADD alternative path.','T+1, next-open gaps, missing bars, limits and queue not bounded by floor risk.','Booked dividend receivable not available cash. External payment UNKNOWN; no dividend_payment events.','Fixed 1709 background NON-PIT. Actual historical matching/tradability UNKNOWN.'])
 dump('SUMMARY.json',summary)
 for p,h in sources.items():assert sha(p)==h,('source changed',p)
 dump('SOURCE_HASHES.json',sources)
 dump('OUTPUT_HASHES.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name!='OUTPUT_HASHES.json'})
 print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
