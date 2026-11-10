"""Nine parent-fixed original entry points: local math/cash checks, no Account/model."""
from pathlib import Path
from decimal import Decimal as D,getcontext
import json,gzip,hashlib
import pandas as pd
getcontext().prec=50
O=Path(__file__).resolve().parent;P=O.parent;E=P.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');S={};C=[];Z=D(0)
def read(p):
 p=Path(p);b=p.read_bytes();S[str(p)]=hashlib.sha256(b).hexdigest()
 if '.jsonl'in p.name:return[json.loads(s)for s in gzip.decompress(b).splitlines()]
 return json.loads(gzip.decompress(b)if p.suffix=='.gz'else b)
def check(n,x):C.append({'name':n,'pass':bool(x)});assert x,n
def eq(n,a,b,tol='1e-8'):check(n,abs(D(str(a))-D(str(b)))<=D(tol))
def version(xs,day):return next(v for v in xs if v['from']<=day and(v['to']is None or day<v['to']))
rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
def fee(q,p,fs,side):
 if not q:return Z
 n=D(q)*p
 return sum((max(D(c.get('minimum_local','0')),n*D(c['rate']))for c in fs['components']if c.get('side','both')in['both',side]),Z)
def R(q,p,x,fs):return max(Z,D(q)*(p-x))+fee(q,p,fs,'buy')+fee(q,x,fs,'sell')
def floorq(n,units):
 return 0 if n<units['buy_minimum']else units['buy_minimum']+(n-units['buy_minimum'])//units['buy_step']*units['buy_step']
def riskq(p,x,B,fs,units):
 check('positive unit gap',p>x);q=floorq(int(B/(p-x)),units)
 while q and R(q,p,x,fs)>B:q=floorq(q-units['buy_step'],units)
 return q
def cashq(p,A,fs,units):
 q=floorq(int(max(Z,A)/p),units)
 while q and D(q)*p+fee(q,p,fs,'buy')>A:q=floorq(q-units['buy_step'],units)
 return q
chainrows=read(E/'structural_failure_v1/chains/COMPLETE_ORIGINAL_CHAINS.json');chains={r['campaign']['sid']:r for r in chainrows if r['campaign']['sid']in['000620.SZ','002583.SZ']}
selected={'000620.SZ':[68,69,75,78,113,122],'002583.SZ':[1994,2017,2039]}
weak=read(P/'yingxin/SIX_SINGLE_ORDER_ARITHMETIC.json');strong=read(P/'hainengda/THREE_ENTRY_PAPER_RESULTS.json')['rows'];cashstrong=read(P/'hainengda/ORIGINAL_OPEN_SLOT_CASH_BOUNDS.json')['rows'];cm={r['layer']:r for r in cashstrong}
sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
pair=E/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair';book=read(pair/'B.json.gz');daily=read(pair/'daily.jsonl.gz');bt={t['layer']:t for t in book['trades']if t['side']=='buy'}
frames={};auditrows=[]
card=P/'CARD.md';cardtext=card.read_text();S[str(card)]=hashlib.sha256(card.read_bytes()).hexdigest()
check('current scope no D historical hardgate; shared calculation not performed','D_k'not in cardtext and '.005' in cardtext and '.01' in cardtext)
for sid,ids in selected.items():
 chain=chains[sid];entries={r['layer']:r for r in chain['entries']};obs={r['day']:r for r in chain['observations']};m=sm[sid]
 for k in ['facts','CP1_input','CP1']:
  p=Path(m['refs'][k]);h=hashlib.sha256(p.read_bytes()).hexdigest();S[str(p)]=h;check(sid+': source '+k,h==m['output_sha256'][str(p)]);frames[sid,k]=pd.read_parquet(p)
 for lid in ids:
  a=entries[lid]['original_signal_and_authorization'];buy=bt[lid];day=buy['signal_at'][:10];od=buy['at'][:10];f=frames[sid,'facts'];ci=frames[sid,'CP1_input'];cp=frames[sid,'CP1'];t=pd.Timestamp(day);ot=pd.Timestamp(od);row=f.loc[t];orow=f.loc[ot]
  r=next(v for v in(weak if sid=='000620.SZ'else strong)if v['layer']==lid);isw=sid=='000620.SZ'
  check(str(lid)+': original buy and fixed role/source unchanged',buy==entries[lid]['actual_buy']and(a['role']=='core')==(buy['kind']=='core'))
  check(str(lid)+': original/source rawprice prefix',f.loc[:t].index.equals(ci.loc[:t].index)and row.close==ci.loc[t,'close']and row.segment_id==ci.loc[t,'segment_id'])
  i=ci.index.get_loc(t);win=ci.iloc[i-64:i];check(str(lid)+': exactly64 prior prices for63 prior returns',len(win)==64 and win.index[-1]<t and win.segment_id.eq(row.segment_id).all())
  s=D(str(cp.loc[t,'s']));eq(str(lid)+': sigma is current original CP.s, not receipt scale',r['s63'],s,'1e-16')
  NAV=D(a['decision_NAV']);B=NAV*D('.0025');ha=D(a['frozen_intent']['floor']);hc=ha/D(str(row.factor));ho=ha/D(str(orow.factor));mult=(-2*s).exp();xc=hc*mult*D('.9995');xo=ho*mult*D('.9995');pc=D(str(row.raw_close))*D('1.0005');po=D(buy['raw_open'])*D('1.0005')
  us=version(rules['quantity_versions'][sid],day)['rule'];uo=version(rules['quantity_versions'][sid],od)['rule'];venue=version(rules['venue_versions'][sid],od)['venue'];fs=version(rules['fee_versions'][venue],day)['schedule'];fo=version(rules['fee_versions'][venue],od)['schedule']
  check(str(lid)+': reported original quantity and role exact',(r['original_actual_q'] if isw else r['original_qty'])==buy['shares'] and(r['role'] if isw else r['original_role'])==a['role'])
  eq(str(lid)+': reported signal NAV',r['signal_NAV'] if isw else r['signal_NAV_frozen'],NAV,'1e-20');eq(str(lid)+': reported beta budget',r['single_order_beta']if isw else r['budget_0_0025_signalNAV'],B,'1e-20')
  eq(str(lid)+': reported frozen raw true h',r['raw_h'],hc,'1e-12');eq(str(lid)+': reported raw stress h',r['raw_stressH']if isw else r['raw_stress_floor'],hc*mult,'1e-12')
  check(str(lid)+': reported dated units and all fee components exact',(r['units_CLOSE']if isw else r['dated_quantity_signal'])==us and(r['units_OPEN']if isw else r['dated_quantity_OPEN'])==uo and(r['fee_schedule_CLOSE']if isw else r['dated_fee_signal'])==fs and(r['fee_schedule_OPEN']if isw else r['dated_fee_OPEN'])==fo)
  check(str(lid)+': selected schedules simple notional without extra round/max',all(c.get('amount_basis','notional')=='notional'and c.get('maximum_local')is None and c.get('rounding_unit')is None for c in fs['components']+fo['components']))
  qsig=riskq(pc,xc,B,fs,us);held=sum(int(v['snapshot']['qty'])for v in obs[day]['actual_live_layers']);rem=max(Z,D('.1')*NAV-D(held)*D(str(row.raw_close)));stock=floorq(int(rem/pc),us);frozen=min(qsig,stock);qopen=riskq(po,xo,B,fo,uo);osrem=max(Z,D('.1')*NAV-D(held)*D(buy['raw_open']));ostock=floorq(int(osrem/po),uo);local=min(qopen,frozen,ostock)
  if isw:
   check(str(lid)+': all six quantity levels agree',(r['q_signal_risk_only'],r['new_signal_stockcap_qty'],r['q_signal_frozen'],r['q_OPEN_risk_only_before_freeze'],r['OPEN_stockcap_qty'],r['q_OPEN_conditional_local'])==(qsig,stock,frozen,qopen,ostock,local))
   eq(str(lid)+': risk at signal cap',r['R_signal_at_riskcap'],R(qsig,pc,xc,fs));eq(str(lid)+': next risk signal grid',r['R_signal_next_risk_grid'],R(qsig+us['buy_step'],pc,xc,fs));eq(str(lid)+': risk at OPEN local',r['R_OPEN_at_local'],R(local,po,xo,fo));check(str(lid)+': old cap and mobile2percent not applied',not r['original_source_cap_or_mobile_2pct_applied'])
  else:
   check(str(lid)+': all three quantity levels agree',(r['risk_only_CLOSE_cap'],r['stock10_signal_quantity_cap'],r['new_frozen_signal_cap'],r['risk_only_OPEN_cap_without_signal_freeze'],r['stock10_OPEN_quantity_cap'],r['OPEN_cap_with_new_signal_freeze_and_stock10'])==(qsig,stock,frozen,qopen,ostock,local))
   eq(str(lid)+': risk at signal cap',r['R_risk_only_CLOSE_cap'],R(qsig,pc,xc,fs));eq(str(lid)+': next risk signal grid',r['R_next_CLOSE_legal_q'],R(qsig+us['buy_step'],pc,xc,fs));eq(str(lid)+': risk at OPEN local',r['R_OPEN_candidate'],R(local,po,xo,fo));check(str(lid)+': old cap and mobile2percent not applied',r['old_mobile_2pct_not_applied_to_candidate'])
  check(str(lid)+': chosen/next legal risk grid and no upward freeze',R(qsig,pc,xc,fs)<=B and R(qsig+us['buy_step'],pc,xc,fs)>B and local<=frozen and R(local,po,xo,fo)<=B)
  check(str(lid)+': OPEN risk-only maximum and minimum grid independently proven',R(qopen,po,xo,fo)<=B and R(qopen+uo['buy_step'],po,xo,fo)>B and R(us['buy_minimum'],pc,xc,fs)<=B and R(uo['buy_minimum'],po,xo,fo)<=B)
  eq(str(lid)+': original actual buy fee crosscheck',buy['fees_cny'],fee(buy['shares'],D(buy['price']),fo,'buy'),'1e-20')
  eq(str(lid)+': OPEN candidate buy fee',r['OPEN_local_buyfee']if isw else r['candidate_OPEN_buy_fee'],fee(local,po,fo,'buy'));eq(str(lid)+': OPEN hypothetical sell fee',r['OPEN_local_sellfee']if isw else r['candidate_OPEN_sell_reference_fee'],fee(local,xo,fo,'sell'))
  pre=max((d for d in daily if d['at'][:10]<od),key=lambda d:d['at']);ix=next(n for n,z in enumerate(book['audit'])if z['kind']=='reserve'and z['at']==buy['at']and z['sid']==sid and z['decision_at']==buy['signal_at']);before=[(n,z)for n,z in enumerate(book['audit'][:ix])if pre['at']<str(z.get('at')or z.get('receipt',{}).get('at')or'')<=buy['at']]
  check(str(lid)+': original cash prefix has only supported real events',all(z['kind']in['fill','settle','reserve','lot_risk_funded']for _,z in before)and all(D(pre[k])==0 for k in['order_reserved','settlement_locked','payable','sale_receivable']))
  settled=sum((D(z['settlement']['cny_amount'])*(-1 if z['settlement']['debit'] else 1)for _,z in before if z['kind']=='settle'),Z);reserved=sum((D(z['gross_budget_cny'])+D(z['fee_reserved_cny'])for _,z in before if z['kind']=='reserve'),Z);available=D(pre['available'])+settled-reserved;spend=available-D('.1')*NAV;cashcap=cashq(po,spend,fo,uo);aftercash=min(local,cashcap)
  if isw:reportedavailable=r['original_OPEN_PVR_reserve_slot_available'];reportedcash=r['same_original_slot_cash_necessary_qcap'];reportedafter=r['q_OPEN_after_known_cash_necessary_gate']
  else:cr=cm[lid];reportedavailable=cr['available_at_original_reserve_slot'];reportedcash=cr['cash_only_legal_quantity_upper'];reportedafter=cr['local_cap_after_cash_necessary_only'];check(str(lid)+': exact target reserve event',cr['original_reserve_audit_index']==ix and cr['original_reserve']==book['audit'][ix])
  eq(str(lid)+': actual OPEN slot cash, not signal cash',reportedavailable,available,'1e-20');check(str(lid)+': cash cap/aftercash agrees',reportedcash==cashcap and reportedafter==aftercash);check(str(lid)+': cash chosen/next grid',D(cashcap)*po+fee(cashcap,po,fo,'buy')<=spend and D(cashcap+uo['buy_step'])*po+fee(cashcap+uo['buy_step'],po,fo,'buy')>spend)
  auditrows.append({'sid':sid,'layer':lid,'role':a['role'],'signal':day,'OPEN':od,'original_q':buy['shares'],'sigma_source':'original CP.s','s63':str(s),'prior_return_end':str(win.index[-1].date()),'budget':str(B),'q_signal_risk':qsig,'q_new_signal_frozen':frozen,'q_OPEN_risk_and_stock_frozen':local,'actual_original_reserve_audit_index':ix,'cash_at_original_slot':str(available),'cash_after_10pct_signalNAV':str(spend),'cash_only_qcap':cashcap,'q_after_known_cash_only':aftercash,'final_grant':False,'concurrent_stock_industry_pool_and_other_native_gates':'NOT_VERIFIED'})
res={'status':'PASS_NINE_FIXED_SINGLE_ORDER_LOCAL_ARITHMETIC_AND_ORIGINAL_SLOT_CASH','checks':C,'rows':auditrows,'source_sha256':S,'scope':['Both roles use proposed single-order stress metric; old mobile2percent/sourcecap only comparison.','Cached current CP.s, not receipt used_scale/z; 64 prior same-segment prices exclude current return.','Local source caps/actual original slot cash do not form a replacement account or final grant.','No D historical hardgate applied; current stock/industry concurrent rho and pool/other gates not calculated.','Cash uses each exact original reserve slot, after actual settlements/prior successful reservations; no CLOSE cash substitution.'],'math':'Independent Decimal precision50 exponential; monetary comparison tolerance1e-8CNY for float-based exp display, exact integer q/fee schedules/source clocks.','new_accounts':0,'new_models':0,'parameter_scans':0,'new_PnL_paths':0,'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()};(O/'NINE_FIXED_POINT_AUDIT.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':res['status'],'checks':len(C),'q_before_cash':[r['q_OPEN_risk_and_stock_frozen']for r in auditrows],'q_after_cash':[r['q_after_known_cash_only']for r in auditrows]},ensure_ascii=False))
