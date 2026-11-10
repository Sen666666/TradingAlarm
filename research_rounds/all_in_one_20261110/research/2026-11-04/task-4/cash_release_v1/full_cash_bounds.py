"""Original ledger cash reconstruction + all cash-rejected minimum-unit bounds.
No Account/Runner/model/state-machine calculation or counterfactual portfolio.
"""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from types import SimpleNamespace as NS
import bisect,gzip,hashlib,json,math,statistics,sys,time
import pandas as pd
O=Path(__file__).resolve().parent;T=O.parent.parent/'task'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
BASE=Path('/Users/bytedance/Documents/ChatGPT/money');SRC={}
sys.path.insert(0,str(BASE/'research_rounds/lot-risk-allocation-20261029/code'))
import study as LR
ROOTS={'long':T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair',
       'strong':T/'pvr_pool_feasibility/runs/2025_26/pair'}
B=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/market-permission-price-only-20261101')
Z=D(0);TOL=D('.0000001')
def bind(p):
 p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest()
 if str(p) in SRC:assert SRC[str(p)]==h
 SRC[str(p)]=h;return p
def read(p):return json.loads(bind(p).read_text())
def gz(p,lines=False):
 with gzip.open(bind(p),'rt') as f:return list(map(json.loads,f)) if lines else json.load(f)
def frame(p,cols):return pd.read_parquet(bind(p),columns=cols)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def day(at):return str(at)[:10]
def eff(vs,d):
 a=[v for v in vs if v['from']<=d and (v.get('to') is None or d<v['to'])];assert len(a)==1;return a[0]
def eq(a,b,tag):assert abs(D(str(a))-D(str(b)))<TOL,(tag,a,b)
def stats(a):
 return dict(count=len(a),minimum=min(a) if a else None,median=statistics.median(a) if a else None,
   mean=statistics.mean(a) if a else None,maximum=max(a) if a else None)

def main():
 begin=time.monotonic();bind(__file__);bind(O/'PROTOCOL.txt')
 sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
 market=BASE/'TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared'
 mr={x['series_id']:x for x in read(market/'manifest.json')['series']}
 rules=read(BASE/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
 meta=read(BASE/'research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
 globalf=frame(B/'historical-shadow/run-v1/NATIVE1709_global_daily.parquet',['permit_next_open'])
 globalf.index=pd.DatetimeIndex(globalf.index)
 cat=read(B/'industry-coverage/run-v1/NODE_CATALOGUE.json')
 f1nodes={x['sector']:x for x in cat if x['domain']=='NATIVE1709'}
 pricecache={};stagecache={};f1cache={};feecache={};allsummary={};dayrows=[];grouprows=defaultdict(list)
 captured=read(O.parent/'reentry_v1/funding_agent/PREOPEN_EXACT_STATE.json')
 pre=read(O.parent/'reentry_v1/funding_agent/PRE_CANDIDATE_EXACT_STATE.json')
 exactpre={(x['at'][:10],x['intent']['sid'],x['intent']['role']):x for x in pre}
 cross_s0=[];cross_pre=[]
 with gzip.open(O/'ALL_ORIGINAL_CASH_REJECTS.jsonl.gz','wt') as output:
  for label,root in ROOTS.items():
   b=gz(root/'B.json.gz');daily=gz(root/'daily.jsonl.gz',True);dd={day(x['at']):x for x in daily};dates=sorted(dd)
   funding=gz(root/'funding.jsonl.gz',True);op=[x for x in funding if '09:30:00' in x['at']]
   assert len({(x['at'],x['sid'],x['role']) for x in op})==len(op)
   assert all(D(x[k])==0 for x in daily for k in ['order_reserved','settlement_locked','payable','sale_receivable'])
   atypes=Counter(x['kind'] for x in b['audit'])
   allowed={'fill','settle','reserve','lot_risk_funded','release_buy','pilot_layer_exit','exit_request','risk_checkpoint','dividend_accrual','buy_day_expiry','split'}
   assert not set(atypes)-allowed,(label,atypes)
   assert all('09:30:00' in t['at'] for t in b['trades'])
   assert all(x['settlement']['fx_rate']=='1' and x['settlement']['due_at']==x['at'] for x in b['audit'] if x['kind']=='settle')
   assert all('15:10:00' in x['at'] for x in b['journal'] if x['kind']=='cancel_ack')
   buys=defaultdict(lambda:Z);sells=defaultdict(lambda:Z);buyq=defaultdict(int);tradeby=defaultdict(list);firstbuy={}
   for t in b['trades']:
    d=day(t['at']);tradeby[d].append(t)
    if t['side']=='buy':
     buys[d]+=D(t['gross_cny'])+D(t['fees_cny']);buyq[d,t['security_id']]+=t['shares'];firstbuy.setdefault(t['security_id'],d)
    else:sells[d]+=D(t['gross_cny'])-D(t['fees_cny'])
   cash=D(1000000);s0={}
   for d in dates:
    cash+=sells[d]-buys[d];eq(cash,dd[d]['available'],label+' all-day pure-cash ledger '+d)
    s0[d]=D(dd[d]['available'])+buys[d]
    assert all(int(q)-buyq[d,sid]>=0 for sid,q in dd[d]['positions'].items())
   eq(cash,b['ending_cash'],label+' ending cash')
   reserves={};residx=defaultdict(list);buyfillidx=defaultdict(list);releaseidx=defaultdict(list);settles={}
   for n,a in enumerate(b['audit']):
    if a['kind']=='settle':settles[a['settlement']['settlement_id']]=(n,a)
    if a['kind']=='reserve':
     key=(day(a['at']),a['sid']);assert key not in reserves;reserves[key]=a;residx[key[0]].append(n)
    if a['kind']=='fill' and a['receipt']['side']=='buy':buyfillidx[day(a['receipt']['at'])].append(n)
    if a['kind']=='release_buy' and '09:30:00' in a['at']:releaseidx[day(a['at'])].append(n)
   for d,ii in residx.items():
    if buyfillidx[d]:assert max(ii)<min(buyfillidx[d]),('all funding precedes buy fills',label,d)
    if releaseidx[d]:assert max(ii)<min(releaseidx[d]),('no intra-funding release feedback',label,d)
   for t in b['trades']:
    if t['side']!='sell':continue
    n,a=settles[t['settlement_id']];assert a['at']==t['at'] and not a['settlement']['debit']
    eq(a['settlement']['cny_amount'],D(t['gross_cny'])-D(t['fees_cny']),'sale net settles')
    if residx[day(t['at'])]:assert n<min(residx[day(t['at'])]),('sale settles before fresh reservations',label,t)
   reserve_ids={a['order_id'] for a in reserves.values()}
   release_ids={a['order_id'] for a in b['audit'] if a['kind']=='release_buy'}
   assert reserve_ids==release_ids
   decisions={day(x['at']):x for x in b['decisions']};decdays=sorted(decisions)
   prefix=defaultdict(lambda:Z);cnt=Counter();rows=[];days=set()
   for r in op:
    d=day(r['at']);sid=r['sid'];role=r['role'];j=bisect.bisect_left(decdays,d)-1;assert j>=0
    signal=decdays[j];dec=decisions[signal];i=next((i for i in dec['intents'] if i['sid']==sid and i['role']==role),None);assert i is not None
    A=s0[d]-prefix[d];assert A>=-TOL
    if label=='strong' and d+' 09:30:00+08:00' in captured and d not in days:
     eq(s0[d],captured[d+' 09:30:00+08:00']['state']['available_exact'],'exact13 S0 '+d);cross_s0.append(d)
    days.add(d)
    if label=='strong' and (d,sid,role) in exactpre:
     z=exactpre[d,sid,role];eq(A,z['state']['available_exact'],'exact15 pre-candidate '+str((d,sid,role)));cross_pre.append((d,sid,role))
    if r['result']=='reserved':
     a=reserves[d,sid];assert day(a['decision_at'])==signal
     assert a['target_shares']==r['shares'];prefix[d]+=D(a['gross_budget_cny'])+D(a['fee_reserved_cny']);continue
    if 'cash_or_original_reserve' not in r['result']:continue
    cnt['cash_rejects']+=1
    if sid not in pricecache:
     fp=Path(sm[sid]['refs']['facts']);rp=Path(mr[sid]['raw']['path'])
     assert hashlib.sha256(fp.read_bytes()).hexdigest()==sm[sid]['output_sha256'][str(fp)]
     assert hashlib.sha256(rp.read_bytes()).hexdigest()==mr[sid]['raw']['sha256']
     ff=frame(fp,['factor']);rr=frame(rp,['trade_date','open']);rr.index=pd.to_datetime(rr.trade_date)
     pricecache[sid]=(ff,rr)
    ff,rr=pricecache[sid];dt=pd.Timestamp(d);assert dt in rr.index and math.isfinite(rr.loc[dt,'open']) and rr.loc[dt,'open']>0
    factor=D(str(ff.iloc[ff.index.searchsorted(dt,side='right')-1].factor));price=D(str(rr.loc[dt,'open']))*(D(1)+LR.SLIP)
    if (sid,d) not in feecache:
     qv=eff(rules['quantity_versions'][sid],d)['rule'];qr=LR.L.QuantityRule(**qv)
     venue=eff(rules['venue_versions'][sid],d)['venue'];fsv=eff(rules['fee_versions'][venue],d)['schedule'];fs=LR.L.FeeSchedule(fsv['schedule_id'],tuple(LR.L.FeeComponent(**v) for v in fsv['components']))
     par=D(rules['security_metadata'][sid]['par_value']);fee=LR.fees(qr.buy_minimum,price,fs,'buy',par)
     feecache[sid,d]=(qr,fs,par,fee)
    qr,fs,par,fee=feecache[sid,d];qmin=qr.buy_minimum;gross=D(qmin)*price;cost=gross+fee;floor=D(i['floor'])/factor
    assert int(i['cap'])>=qmin and gross<=D(i['budget']) and price/(D(1)+LR.SLIP)>floor
    if role=='core':assert LR.protection_risk(qmin,price,floor,fs,par)<=D(i['risk_budget'])
    nav=D(dec['nav']);R=nav*D('.1');assert cost>min(A-R,A)-TOL,('recorded cash reject must fail original predicate',label,r)
    physical=cost<=A+TOL
    sec=meta[sid]['sector_id']
    if sec not in stagecache:stagecache[sec]=frame(im[sec]['refs']['state'],['day','stage_name']).set_index('day')
    stage=stagecache[sec].loc[signal,'stage_name'] if signal in stagecache[sec].index else None
    if sec not in f1cache:
     t=frame(f1nodes[sec]['daily_result_path'],['permit_next_open']);t.index=pd.DatetimeIndex(t.index);f1cache[sec]=t
    st=pd.Timestamp(signal);fg=bool(globalf.loc[st,'permit_next_open']) if st in globalf.index else None
    fi=bool(f1cache[sec].loc[st,'permit_next_open']) if st in f1cache[sec].index else None
    mature=stage in ['confirmed','expanded'];act=bool(dec['on']);eligible=act and mature
    held=int(dd[d]['positions'].get(sid,0))-buyq[d,sid]
    kind='existing_hold_ADD' if held else 'flat_reentry' if firstbuy.get(sid,d)>=dates[0] and firstbuy.get(sid,d)<d else 'first_participation'
    row=dict(window=label,OPEN=d,signal_day=signal,sid=sid,name=meta[sid]['name'],sector=sec,industry=meta[sid]['industry'],role=role,
      original_raw_merged_reasons=r['result'],raw_cash_only=r['result']=='cash_or_original_reserve',ACT_on=act,original_industry_stage=stage,
      original_permission_eligible=eligible,F1_global_permit=fg,F1_industry_permit=fi,F1_joint_permit=fg and fi if fg is not None and fi is not None else None,
      entry_kind=kind,held_quantity_before_fresh=held,S0_available=s0[d],prior_real_submitted_reserve=prefix[d],available_already_net_of_orders=A,
      original_extra10_buffer=R,known_extra_unreserved_liability_U=0,minimum_quantity=qmin,known_OPEN_buy_price=price,
      minimum_gross=gross,minimum_buy_fee=fee,minimum_cash_required=cost,physical_cash_can_afford_minimum=physical,
      required_release_to_afford_minimum=max(Z,cost-(A-R)),spendable_after_original_buffer=A-R,
      max_extra_buffer_cash_stock=min(A,R),cash_remaining_after_one_minimum=A-cost if physical else None,
      original_decision_NAV=nav,decision_CLOSE_inventory=decisions[signal].get('inventory',dd[signal]['inventory']),
      scope='one original frozen-prefix cash-only necessary bound; not all risk checks, not shared new plan or return')
    output.write(json.dumps(row,ensure_ascii=False,default=str)+'\n');rows.append(row)
   assert cnt['cash_rejects']==(74185 if label=='long' else 58557)
   assert len(reserves)==sum(r['result']=='reserved' for r in op)
   for d in sorted({day(x['at']) for x in op}):
    signal=decdays[bisect.bisect_left(decdays,d)-1];nav=D(decisions[signal]['nav']);R=nav*D('.1')
    z=dict(window=label,OPEN=d,signal_day=signal,year=d[:4],quarter=f'{d[:4]}Q{(int(d[5:7])-1)//3+1}',
      S0_available=s0[d],prior_existing_submitted_order_reserve=0,decision_NAV=nav,original_extra10_buffer=R,
      maximum_discussable_release_cash=min(s0[d],R),maximum_discussable_release_pct_decisionNAV=float(min(s0[d],R)/nav*100),
      S0_cash_pct_decisionNAV=float(s0[d]/nav*100),ACT_on=bool(decisions[signal]['on']),
      decision_CLOSE_inventory=dd[signal]['inventory'],actual_same_OPEN_protection_sale_net=sells[d],
      actual_original_buy_cash=buys[d],original_final_cash=dd[d]['available'],
      original_day_buy_fees=sum((D(t['fees_cny']) for t in tradeby[d] if t['side']=='buy'),Z),
      original_day_sell_fees=sum((D(t['fees_cny']) for t in tradeby[d] if t['side']=='sell'),Z),
      known_extra_unreserved_liability_U=0)
    dayrows.append(z)
   sub={}
   for role in ['all','mobile','core']:
    a=rows if role=='all' else [r for r in rows if r['role']==role]
    sub[role]=dict(events=len(a),stocks=len({r['sid'] for r in a}),OPENs=len({r['OPEN'] for r in a}),physical_cash_can_afford_min=sum(r['physical_cash_can_afford_minimum'] for r in a),
      actual_permission_eligible=sum(r['original_permission_eligible'] for r in a),eligible_physical_min=sum(r['original_permission_eligible'] and r['physical_cash_can_afford_minimum'] for r in a),
      eligible_F1_joint=sum(r['original_permission_eligible'] and r['F1_joint_permit'] is True for r in a),eligible_F1_joint_physical_min=sum(r['original_permission_eligible'] and r['F1_joint_permit'] is True and r['physical_cash_can_afford_minimum'] for r in a),
      raw_cash_only_physical_min=sum(r['raw_cash_only'] and r['physical_cash_can_afford_minimum'] for r in a),
      by_entry_kind={k:dict(events=sum(r['entry_kind']==k for r in a),eligible_physical_min=sum(r['entry_kind']==k and r['original_permission_eligible'] and r['physical_cash_can_afford_minimum'] for r in a)) for k in ['first_participation','flat_reentry','existing_hold_ADD']})
   allsummary[label]=dict(original_days=len(daily),cash_flow_and_obligation_assertions_passed=True,audit_types=dict(atypes),source_OPEN_records=len(op),cash_rejected=sub)
   for r in rows:grouprows[label,r['OPEN'][:4],r['industry'],r['role']].append(r)
 save('FULL_CASH_NECESSARY_BOUNDS_SUMMARY.json',allsummary);save('ORIGINAL_DAILY_LIQUIDITY_STOCKS.json',dayrows)
 grouped=[]
 for (w,y,industry,role),a in sorted(grouprows.items()):grouped.append(dict(window=w,year=y,industry=industry,role=role,events=len(a),physical_min=sum(r['physical_cash_can_afford_minimum'] for r in a),eligible_min=sum(r['original_permission_eligible'] and r['physical_cash_can_afford_minimum'] for r in a),F1_joint_eligible_min=sum(r['original_permission_eligible'] and r['F1_joint_permit'] is True and r['physical_cash_can_afford_minimum'] for r in a)))
 save('YEAR_INDUSTRY_ROLE_BOUNDS.json',grouped)
 liquidity=[]
 for w in ROOTS:
  for y in sorted({r['year'] for r in dayrows if r['window']==w}):
   a=[r for r in dayrows if r['window']==w and r['year']==y]
   liquidity.append(dict(window=w,year=y,OPEN_days=len(a),S0_cash_pct=stats([r['S0_cash_pct_decisionNAV'] for r in a]),potential_extra_release_pct=stats([r['maximum_discussable_release_pct_decisionNAV'] for r in a]),
     original_cash_below_extra10_days=sum(r['S0_available']<r['original_extra10_buffer'] for r in a),original_day_buy_fees=stats([float(r['original_day_buy_fees']) for r in a]),
     interpretation='Independent original daily liquidity stocks; no summation as new capital, no released-policy losses/returns'))
 save('ADVERSE_YEAR_LIQUIDITY_STOCK_SUMMARY.json',liquidity)
 assert len(set(cross_s0))==13 and len(cross_pre)==15
 save('LEDGER_RECONSTRUCTION_AUDIT.json',dict(passed=True,exact_13_S0_crosschecks=sorted(set(cross_s0)),exact_15_candidate_cash_crosschecks=cross_pre,
   all_968_original_daily_cash_balances_reconciled=True,no_existing_reserved_settlement_payable_sale_AR_at_any_original_CLOSE=True,known_extra_U_zero_under_original_book=True,
   individual_cash_ability_not_portfolio_admission=True))
 assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in SRC.items())
 save('SOURCE_SHA256.json',SRC);save('COMPLETION.json',dict(seconds=time.monotonic()-begin,new_accounts=0,new_restores=0,new_signals=0,new_financial_paths=0,source_files=len(SRC),cash_reject_events=132742))
 print(json.dumps(allsummary,ensure_ascii=False,indent=2,default=str));print(json.dumps(liquidity,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()
