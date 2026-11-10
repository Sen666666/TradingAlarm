from pathlib import Path
from decimal import Decimal as D
import json,sys,hashlib,collections
import pandas as pd
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');O=Path(__file__).resolve().parent;B=R/'m3_ab_shared_probe_v1'
sys.path.insert(0,str(B/'source_bridge_v1'));import bridge
Z=D(0);rows=[];summaries=[];gaps=[];hashes={};promos=[];identities=0
windows={'2024_924':(B/'indexed_execution_v1/cohort_2024_924',['2024-09-13','2024-09-26','2024-09-27'],['603626.SH','688819.SH','300185.SZ','002636.SZ']),'2022':(B/'known_halt_contract_v1/cohort_2022_recovery_v2',['2022-01-07','2022-01-10','2022-01-11','2022-01-12'],['000876.SZ','002100.SZ','000810.SZ','000592.SZ'])}
def read(p):
 hashes[str(p)]=bridge.sha(p);return json.loads(p.read_text())
def write(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def parts_before(j,day):
 q=collections.defaultdict(lambda:dict(core=0,add=0));cash=collections.defaultdict(lambda:Z);buys={}
 for a in j:
  ad=pd.Timestamp(a['day']);side=a['side'];rid=a['round_id'];qty=int(a['q']);px=D(a['exact_price']);fee=D(a['exact_whole_order_fee'])
  if ad>day or (ad==day and side.startswith('buy')):continue
  if side.startswith('buy'):
   layer='core' if side=='buy_core' else 'add';q[rid][layer]+=qty;cash[rid]-=D(qty)*px+fee;buys[(rid,layer)]=a
  elif side=='sell_add':q[rid]['add']-=qty;cash[rid]+=D(qty)*px-fee
  else:
   assert qty==sum(q[rid].values());q[rid]=dict(core=0,add=0);cash[rid]+=D(qty)*px-fee
 return q,cash,buys
for win,(p,days,sids) in windows.items():
 j=read(p/'EXACT_TRADE_JOURNAL.json');au=read(p/'AUDIT.json');arc=read(p/'ARCHIVES.json');dl={x['day'][:10]:x for x in read(p/'DAY_LEDGER.json')};claims=read(p/'CLAIM_LEDGER.json');layers=read(p/'LAYER_REPORT.json');s=bridge.load_original(win)
 proofs={(x['round_id'],x['day'][:10]):x['proof'] for x in au if x['type']=='PROMOTION_PROOF' and x['reason']=='eligible'}
 for x in au:
  if x['type']=='PROMOTED' and arc[x['round_id']]['sid'] in sids:promos.append(dict(window=win,**x))
 # No entitlement existed for these simple early-day decomposition samples.
 earlier=[x for x in claims if x.get('day','9999')[:10]<=max(days)]
 assert not earlier,(win,earlier[:2])
 for ds in days:
  day=pd.Timestamp(ds);prev=s.cal[s.cal<day][-1];q,rcash,buys=parts_before(j,day);pq,pcash,pbuys=parts_before(j,prev+pd.Timedelta(nanoseconds=1));promoted={x['round_id'] for x in au if x['type']=='PROMOTED' and pd.Timestamp(x['day'])<=day};begin=len(rows);gross=Z
  for rid,qp in q.items():
   nq=sum(qp.values())
   if not nq:continue
   st=arc[rid];sid=st['sid'];s.load(sid);z=s.raw[sid].get(day);op=D(str(z['raw_open']));fac=D(str(z['adjustment_factor']));qr,fs,par=s.getmeta(sid,day);gross+=D(nq)*op
   round_net=rcash[rid]+D(nq)*op*(1-s.SLIP)-s.fee(nq,op*(1-s.SLIP),fs,'sell',par)
   prevz=s.raw[sid].get(prev);pnq=sum(pq[rid].values());_,pfs,ppar=s.getmeta(sid,prev);prevnet=pcash[rid]+D(pnq)*D(str(prevz['raw_close']))*(1-s.SLIP)-s.fee(pnq,D(str(prevz['raw_close']))*(1-s.SLIP),pfs,'sell',ppar)
   fresh=s.true(s.cp[sid].get(prev,{}).get('receipt'));pool='confirmed' if rid in promoted else 'probe'
   for layer,qty in qp.items():
    if not qty:continue
    b=buys[(rid,layer)];bd=pd.Timestamp(b['day']);bfee=D(b['exact_whole_order_fee']);cost=D(b['q'])*D(b['exact_price'])+bfee;assert qty==int(b['q'])
    history=s.cal[(s.cal>=bd)&(s.cal<=day)]
    assert all(D(str(s.raw[sid].get(dt)['adjustment_factor']))==fac for dt in history),(win,sid,ds,'FACTOR_CHANGE_REQUIRES_EXACT_EVENT_BRIDGE')
    if layer=='core':floor=D(str(s.facts[sid].get(prev)['i_floor']))/fac
    else:
     proof=proofs[(rid,str(bd.date()))];floor=D(proof['effective_floor'])
     for dt in history[history<day]:
      fr=s.facts[sid].get(dt);cr=s.cp[sid].get(dt);cl=D(str(s.raw[sid].get(dt)['raw_close']))
      assert cl>floor,(sid,ds,'prior ADD should have exited')
      floor=max(floor,D(str(fr['i_floor']))/fac)
      if s.true(cr.get('receipt')):floor=max(floor,D(str(cr['candidate']))/fac)
    a=D(qty)*op;f=D(qty)*floor;nom=max(Z,a-f);remaining=max(Z,min(a,cost)-f);giveback=max(Z,a-max(f,cost));assert abs(nom-remaining-giveback)<D('1e-20');identities+=1
    sp=op*(1-s.SLIP);lp=floor*(1-s.SLIP);sellnow=s.fee(qty,sp,fs,'sell',par);sellfloor=s.fee(qty,lp,fs,'sell',par);an=D(qty)*sp-sellnow;fn=D(qty)*lp-sellfloor
    netrisk=max(Z,an-fn);np=max(Z,min(an,cost)-fn);ng=max(Z,an-max(fn,cost));assert abs(netrisk-np-ng)<D('1e-20');identities+=1
    rows.append(dict(window=win,open_day=ds,round_id=rid,sid=sid,name=st['name'],pool=pool,layer=layer,qty=qty,open=op,floor=floor,book_cost=cost,buy_fee=bfee,entry_minimum_q=qr.buy_minimum,buy_fee_pct=100*bfee/(cost-bfee),capital=a,nominal_risk=nom,full_cost_to_line_principal=max(Z,cost-f),remaining_principal=remaining,profit_giveback=giveback,already_lost_cost=max(Z,cost-a),protected_profit=max(Z,f-cost),net_liquidation_PnL=an-cost,round_NET80=round_net,previous_CLOSE_round_NET80=prevnet,previous_CLOSE_fresh_CP=fresh,previous_CLOSE_M3=s.sector[st['sector']].get(prev,-1),profitable_no_fresh_CP=pool=='probe' and round_net>0 and prevnet>0 and not fresh,one_layer_floor_sell_fee=sellfloor,gross_mark_to_net_floor=max(Z,a-fn),net_liquidation_risk=netrisk,fee_remaining_principal=np,fee_profit_giveback=ng,full_fee_cost_to_floor_principal=max(Z,cost-fn),same_source_factor_verified=True))
  cur=rows[begin:];probe=[x for x in cur if x['pool']=='probe'];eligible=[x for x in probe if x['profitable_no_fresh_CP']]
  plan=next(x for x in au if x['type']=='ALL_RESERVATIONS_COMPLETE' and x['day'].startswith(ds));cash=D(plan['cash_before_fills']);recv=D(dl[ds]['OPEN']['receivable']);nav=cash+recv+gross
  bc=Z;bm=Z
  for x in j:
   if x['day'].startswith(ds) and x['side'].startswith('buy'):
    sid=arc[x['round_id']]['sid'];s.load(sid);bc+=D(x['q'])*D(x['exact_price'])+D(x['exact_whole_order_fee']);bm+=D(x['q'])*D(str(s.raw[sid].get(day)['raw_open']))
  assert nav-bc+bm==D(dl[ds]['OPEN']['NAV']),(win,ds,'NAV')
  summary=dict(window=win,open_day=ds,original_NAV_certified=True,preallocation_NAV=nav,original_NAV_reconciled_exactly=True,held_names=len({x['rid'] for x in []}) if False else len({x['round_id'] for x in cur}),probe_names=len(probe),profitable_no_fresh_CP_names=len(eligible),probe_capital=sum((x['capital'] for x in probe),Z),probe_nominal_risk=sum((x['nominal_risk'] for x in probe),Z),probe_remaining_principal=sum((x['remaining_principal'] for x in probe),Z),probe_profit_giveback=sum((x['profit_giveback'] for x in probe),Z),probe_full_cost_to_line_principal=sum((x['full_cost_to_line_principal'] for x in probe),Z),probe_gross_mark_to_net_floor=sum((x['gross_mark_to_net_floor'] for x in probe),Z),all_nominal_risk=sum((x['nominal_risk'] for x in cur),Z),all_gross_mark_to_layer_net_floor=sum((x['gross_mark_to_net_floor'] for x in cur),Z),profit_no_CP_nominal=sum((x['nominal_risk'] for x in eligible),Z),profit_no_CP_giveback=sum((x['profit_giveback'] for x in eligible),Z),probe_cap_before_new_fees=nav*D('.005'),risk_released_by_exact_bookkeeping=Z)
  summary['original_nominal_headroom']=summary['probe_cap_before_new_fees']-summary['probe_nominal_risk'];summary['misstated_headroom_if_only_remaining_principal']=summary['probe_cap_before_new_fees']-summary['probe_remaining_principal'];summaries.append(summary)
 for sid in sids:
  b=next(x for x in j if arc[x['round_id']]['sid']==sid and x['side']=='buy_core');rid=b['round_id'];exitrow=next((x for x in j if x['round_id']==rid and x['side']=='sell_all'),None)
  if exitrow is None:gaps.append(dict(window=win,sid=sid,round_id=rid,status='NO_KNOWN_WHOLE_EXIT'));continue
  day=pd.Timestamp(exitrow['day']);prev=s.cal[s.cal<day][-1];s.load(sid);z=s.raw[sid].get(day);fac=D(str(z['adjustment_factor']));op=D(str(z['raw_open']));floor=D(str(s.facts[sid].get(prev)['i_floor']))/fac;ly=next(x for x in layers if x['round_id']==rid and x['layer']=='core')
  gaps.append(dict(window=win,sid=sid,name=arc[rid]['name'],round_id=rid,exit_day=str(day.date()),prior_CLOSE_I_raw=floor,actual_proxy_OPEN=op,previous_raw_CLOSE=s.raw[sid].get(prev)['raw_close'],actual_OPEN_over_previous_CLOSE=op/D(str(s.raw[sid].get(prev)['raw_close']))-1,core_qty=b['q'],gross_below_prior_I_gap=D(b['q'])*max(Z,floor-op),actual_whole_exit_fee=exitrow['exact_whole_order_fee'],actual_CORE_NET80=ly.get('NET80'),actual_CORE_return=ly.get('return_on_layer_buy_cash'),warning='Future observed exit label only. Not a realizable historical stop guarantee or entry input.'))
 if win=='2022':
  boundary=dl['2022-04-15'];assert boundary['OPEN']['NAV'] is None;write('2022_UNKNOWN_BOUNDARY.json',boundary)
 hashes.update(s.hashes)
pd.DataFrame(rows).to_csv(O/'FIXED_LAYER_RISK_DECOMPOSITION.csv',index=False);pd.DataFrame(summaries).to_csv(O/'FIXED_DAY_ACCOUNT_RISK.csv',index=False);pd.DataFrame(gaps).to_csv(O/'FIXED_ACTUAL_EXIT_GAPS.csv',index=False)
write('FIXED_DAY_ACCOUNT_RISK.json',summaries);write('ORIGINAL_PROMOTION_EVENTS.json',promos)
assert all(bridge.sha(p)==h for p,h in hashes.items())
write('QA.json',dict(fixed_snapshots=len(summaries),layer_observations=len(rows),risk_decomposition_identities=identities,original_NAV_exact_days=len(summaries),changed_source_files=0,new_account_runs=0,new_trades=0,new_promotions=0,parameter_searches=0,source_hashes=hashes))
for x in summaries:print(json.dumps(x,ensure_ascii=False,default=str))
print('FIXED_EXITS',json.dumps(gaps,ensure_ascii=False,default=str))
