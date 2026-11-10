import pandas as pd,json,sys
from pathlib import Path
from decimal import Decimal as D
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
P=R/'breadth_trade_contract_v1/causal_queue_full_v2'
B=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
sys.path.insert(0,str(B/'code'))
from market_rules import version_on,market_identity_on
from sector_account import QuantityRule,FeeComponent,FeeSchedule
sm={x['symbol']:x for x in json.loads(Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())}
rules=json.loads((B/'inputs-v2/market-rules.json').read_text());proxies=json.loads((B/'inputs-v2/economic-protocol.json').read_text())['approved_proxy_ids'];names=rules['security_metadata']
panel=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet')
cal=pd.DatetimeIndex(sorted(panel.day.unique()));z=pd.read_csv(P/'rounds_clockfixed/ALL_SHADOW_ROUNDS.csv')
def meta(sid,d):
 s=str(pd.Timestamp(d).date());i=market_identity_on(rules,sid,s,proxies);v=version_on(rules['fee_versions'][i['venue']],s,proxies)['schedule'];return QuantityRule(**version_on(rules['quantity_versions'][sid],s,proxies)['rule']),FeeSchedule(v['schedule_id'],tuple(FeeComponent(**x)for x in v['components'])),D(str(names[sid]['par_value']))
def fees(q,p,sid,d,side):
 _,fs,par=meta(sid,d);return sum(fs.incremental(side,D(q)*D(str(p)),{},{},1,shares=int(q),par_value=par).values(),D(0))
def val(q,p,sid,d):return D(q)*p-fees(q,p,sid,d,'sell')
def qty(sid,d,p,S,budget,riskmax):
 qr,_,_=meta(sid,d);q=qr.buy_floor(int(budget/p))
 while q:
  c=D(q)*p+fees(q,p,sid,d,'buy');v=val(q,S*D('.9995'),sid,d)
  if c<=budget and c-v<=riskmax:return q,float(c),float(c-v)
  q=qr.buy_floor(q-1)
 return 0,0.,0.
sids=['688126.SH','605358.SH'];data={}
for sid in sids:
 m=sm[sid];h=pd.read_parquet(next(p for p in m['source_sha256']if p.endswith('/signal.parquet')));f=pd.read_parquet(m['refs']['facts']);cp=pd.read_parquet(m['refs']['CP1']);data[sid]=(h,f,cp,D(str(h.loc[pd.Timestamp('2026-06-11')].adjustment_factor)))
def info(sid,d):
 h,f,cp,fac=data[sid];return h.loc[d],f.loc[d],cp.loc[d],fac
def sized(sid,d,price,floor,budget,risk,cap):
 qr,_,_=meta(sid,d);q=qr.buy_floor(min(cap,int(budget/price)))
 while q:
  bf=fees(q,price,sid,d,'buy');r=q*price+bf-val(q,floor*D('.9995'),sid,d)
  if q*price+bf<=budget and r<=risk:return q,bf,r
  q=qr.buy_floor(q-1)
 return 0,D(0),D(0)
def resources(lots,prices):
 cap=sum(D(x['q'])*prices[x['sid']]for x in lots);risk=sum(D(x['q'])*max(D(0),prices[x['sid']]-x['floor'])for x in lots);return cap,risk
def admit(lots,cash,sid,q,p,floor,d,pool,prices,decisionNAV):
 bf=fees(q,p,sid,d,'buy');nav=cash+resources(lots,prices)[0]-bf;cap=q*p;rr=q*max(D(0),p-floor);sc,sr=resources(lots,prices);pc,pr=resources([x for x in lots if x['pool']==pool],prices);fails=[]
 if cap+bf>cash-decisionNAV*D('.1'):fails.append('cash_reserve')
 if pc+cap>(D('.1')if pool=='probe'else D('.6'))*nav:fails.append('pool_capital')
 if pool=='probe'and pr+rr>D('.005')*nav:fails.append('probe_risk')
 if sc+cap>(D('.02')if pool=='probe'else D('.1'))*nav:fails.append('sector_capital')
 if sr+rr>D('.01')*nav:fails.append('sector_risk')
 if sr+rr>D('.03')*nav:fails.append('account_risk')
 if sum(D(x['q'])*prices[sid]for x in lots if x['sid']==sid)+cap>D('.1')*decisionNAV:fails.append('stock_capital')
 return fails,dict(nav=float(nav),cash_required=float(cap+bf),cash_before=float(cash),capital_before=float(sc),risk_before=float(sr),risk_after=float(sr+rr),sector_cap=float((D('.02')if pool=='probe'else D('.1'))*nav),pool=pool)
for policy in ['PROBE_ONLY_FIXED_2PCT','NATIVE_NEW_MOBILE_CONFIRMED_OLD_BREADTH_LAYERS_STAY_PROBE']:
 lots=[];cash=D(1200000);rows=[];qcap={};entrybf={}
 # Initial breadth-only permission is explicit; original industry is not active.
 d=pd.Timestamp('2026-06-11')
 for sid in sids:
  h,f,cp,fac=info(sid,d);p=D(str(h.raw_close))*D('1.0005');floor=D(str(f.i_floor))/fac;qcap[sid]=sized(sid,d,p,floor,D(24000),D(3000),1000000)[0]
 d=pd.Timestamp('2026-06-12');prices={s:D(str(info(s,d)[0].raw_open))for s in sids}
 for sid in sids:
  h,f,cp,fac=info(sid,pd.Timestamp('2026-06-11'));floor=D(str(f.i_floor))/fac;p=prices[sid]*D('1.0005');q,bf,rr=sized(sid,d,p,floor,D(24000),D(3000),qcap[sid]);fails,details=admit(lots,cash,sid,q,p,floor,d,'probe',prices,D(1200000));assert not fails
  cash-=q*p+bf;entrybf[sid]=bf;lots.append(dict(sid=sid,q=q,floor=floor,cost=q*p+bf,pool='probe',role='core',attempt='BREADTH_2026_06_11_NO_NATIVE_ATTEMPT'));rows.append(dict(day=str(d.date()),sid=sid,action='entry_conditional',qcap=qcap[sid],q=q,price=float(p),buyfee=float(bf),planrisk=float(rr),cash_after=float(cash),**details))
 # Native stage first probe June16, confirmed June24. No old layer attempt rewrites.
 sd=pd.Timestamp('2026-06-26');od=pd.Timestamp('2026-06-29')
 for x in lots:x['floor']=D(str(info(x['sid'],sd)[1].i_floor))/info(x['sid'],sd)[3]
 closeprices={s:D(str(info(s,sd)[0].raw_close))for s in sids};decisionNAV=cash+resources(lots,closeprices)[0];qcap={}
 for sid in sids:
  h,f,cp,fac=info(sid,sd);p=closeprices[sid]*D('1.0005');floor=max(D(str(f.i_floor)),D(str(cp.candidate)))/fac;x=next(x for x in lots if x['sid']==sid);existing=D(x['q'])*(p-x['floor']*D('.9995'))+entrybf[sid]+fees(x['q'],x['floor']*D('.9995'),sid,sd,'sell');free=max(D(0),D(3000)-existing);qcap[sid]=sized(sid,sd,p,floor,min(D(24000),D(48000)-x['q']*closeprices[sid]),free,1000000)[0];close_pool='probe' if policy.startswith('PROBE_ONLY') else 'confirmed'; close_min=meta(sid,sd)[0].buy_minimum; close_fails,_=admit(lots,cash,sid,close_min,p,floor,sd,close_pool,closeprices,decisionNAV); rows.append(dict(day=str(sd.date()),sid=sid,action='close_signal',risk_only_qcap=qcap[sid],capital_approved_qcap=0 if close_fails else qcap[sid],close_minimum_failures=close_fails,old_free=float(free),native_stage='confirmed',newfloor=float(floor),corefloor=float(x['floor'])))
 prices={s:D(str(info(s,od)[0].raw_open))for s in sids}
 for sid in sids:
  _,f,cp,fac=info(sid,sd);floor=max(D(str(f.i_floor)),D(str(cp.candidate)))/fac;x=next(x for x in lots if x['sid']==sid);p=prices[sid]*D('1.0005');existing=D(x['q'])*(p-x['floor']*D('.9995'))+entrybf[sid]+fees(x['q'],x['floor']*D('.9995'),sid,od,'sell');free=max(D(0),D(3000)-existing);q,bf,rr=sized(sid,od,p,floor,min(D(24000),D(48000)-x['q']*prices[sid]),free,qcap[sid]);minq=meta(sid,od)[0].buy_minimum;pool='probe'if policy.startswith('PROBE_ONLY')else'confirmed';fails,details=admit(lots,cash,sid,q or minq,p,floor,od,pool,prices,decisionNAV)
  if not q:fails=['minimum_exceeds_unchanged_slot_mark_risk']+fails
  if q and not fails:
   cash-=q*p+bf;lots.append(dict(sid=sid,q=q,floor=floor,cost=q*p+bf,pool=pool,role='add',attempt='native87'))
  rows.append(dict(day=str(od.date()),sid=sid,action='buy_add_conditional'if q and not fails else ('open_diagnostic_only_no_close_order' if policy.startswith('PROBE_ONLY') else 'reject'),q=q if not fails else 0,q_if_risk_only=q,qcap=qcap[sid],old_free=float(free),fails=fails,cash_after=float(cash),**details))
 # Replay only native close protection updates; no exits in these three days.
 for d in [pd.Timestamp('2026-06-29'),pd.Timestamp('2026-06-30')]:
  for x in lots:
   h,f,cp,fac=info(x['sid'],d)
   assert bool(f.i_target)
   if x['role']=='core':x['floor']=D(str(f.i_floor))/fac
   else:
    assert D(str(h.raw_close))>x['floor']
    x['floor']=max(x['floor'],D(str(f.i_floor))/fac)
    if bool(cp.receipt):x['floor']=max(x['floor'],D(str(cp.candidate))/fac)
  prices={s:D(str(info(s,d)[0].raw_close))for s in sids};capital,risk=resources(lots,prices);liq=sum(val(sum(x['q']for x in lots if x['sid']==s),prices[s]*D('.9995'),s,d)for s in sids);rows.append(dict(day=str(d.date()),action='mark',cash=float(cash),nav=float(cash+capital),capital=float(capital),nominal_risk=float(risk),fee_net_liquidation_pnl=float(cash+liq-D(1200000)),probe_capital=float(resources([x for x in lots if x['pool']=='probe'],prices)[0]),confirmed_capital=float(resources([x for x in lots if x['pool']=='confirmed'],prices)[0])))
 print('\nPOLICY',policy);print(json.dumps(rows,ensure_ascii=False,indent=2));print('FINAL_LOTS',json.dumps(lots,default=str))
