"""Six saved signal points, single-order arithmetic only, no strategy path."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,csv,math
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;Q=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={};Z=D(0);SLIP=D('.0005')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
old=read(Q/'current_strategy_source_dossier_v1/yingxin_chain/ORIGINAL_SIX_LAYER_CHAIN.json');assert [r['layer'] for r in old]==[68,69,75,78,113,122]
manifest=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');m=next(r for r in manifest if r['symbol']=='000620.SZ');sp=Path(next(p for p in m['source_sha256'] if p.endswith('/signal.parquet')));assert sha(sp)==m['source_sha256'][str(sp)];SRC[str(sp)]=sha(sp);bars=pd.read_parquet(sp)
scorecode=W/'pvr-current-v3-information-capital-20261101/original_score_function.py';SRC[str(scorecode)]=sha(scorecode);assert 'r.abs().shift().rolling(63,min_periods=63).median().mul(1.4826)' in scorecode.read_text()
scales={r['layer']:r for r in read(Q/'entry_exit_scale/mechanism_review/2022_2024_ACTUAL_ENTRY_SCALE_JOIN.json')};rules=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
def version(xs,day):return next(r for r in xs if r['from']<=day and (r['to'] is None or day<r['to']))
def fee(q,p,sch,side):
 if q==0:return Z
 v=Z
 for c in sch['components']:
  if c.get('side','both') not in ['both',side]:continue
  assert c.get('maximum_local') is None and c.get('rounding_unit') is None and c.get('amount_basis','notional')=='notional'
  v+=max(D(c.get('minimum_local','0')),D(q)*p*D(c['rate']))
 return v
def legal_floor(n,units):return 0 if n<units['buy_minimum'] else units['buy_minimum']+(n-units['buy_minimum'])//units['buy_step']*units['buy_step']
results=[];windows=[]
for r0 in old:
 day=r0['signal_at'][:10];od=r0['actual_buy']['at'][:10];f=bars.loc[:day].copy();valid=f.close.gt(0)&np.isfinite(f.close)&f.amount.gt(0)&np.isfinite(f.amount)
 for k in ['price_eligible','observed_bar','is_observed_bar']:
  if k in f:valid &=f[k].fillna(False).astype(bool)
 for k in ['source_invalid','synthetic_event_bar']:
  if k in f:valid &=~f[k].fillna(True).astype(bool)
 assert valid.iloc[-1] and pd.notna(f.segment_id.iloc[-1]);block=((~valid)|(~valid.shift(fill_value=False))|f.segment_id.ne(f.segment_id.shift())).cumsum();g=f.loc[valid&block.eq(block.iloc[-1])];logr=np.log(g.close).diff();hist=logr.loc[logr.index<pd.Timestamp(day)].dropna().tail(63);assert len(hist)==63 and str(hist.index[-1].date())<day
 s63=1.4826*float(hist.abs().median());cached=float(scales[r0['layer']]['CP1_current_z']);assert math.isclose(s63,cached,rel_tol=1e-12,abs_tol=1e-14),(day,s63,cached)
 # All six scales are strictly above the original PVR lower clip.
 assert s63>1e-8;buffer_multiplier=D(str(math.exp(-2*s63)));F=D(str(r0['signal_facts']['factor']));Fopen=D(str(r0['actual_fill_factor']));assert abs(F-Fopen)<D('1e-12'),'no CA unit bridge beyond these fixed six points'
 h=D(r0['original_frozen_intent']['floor'])/F;stressH=h*buffer_multiplier;sellprice=stressH*(D(1)-SLIP);nav=D(r0['signal_CLOSE_original_NAV']);beta=D('.0025')*nav;rawclose=D(str(r0['signal_facts']['raw_close']));pclose=rawclose*(D(1)+SLIP);rawopen=D(r0['actual_buy']['raw_open']);popen=rawopen*(D(1)+SLIP);assert popen==D(r0['actual_buy']['price'])
 venue=version(rules['venue_versions']['000620.SZ'],day)['venue'];sclose=version(rules['fee_versions'][venue],day)['schedule'];sopen=version(rules['fee_versions'][venue],od)['schedule'];uclose=version(rules['quantity_versions']['000620.SZ'],day)['rule'];uopen=version(rules['quantity_versions']['000620.SZ'],od)['rule']
 def risk(q,p,sch):return D(q)*(p-sellprice)+fee(q,p,sch,'buy')+fee(q,sellprice,sch,'sell')
 def maxq(p,sch,units,cap=None):
  diff=p-sellprice;assert diff>0
  bound=int(beta/diff)
  if cap is not None:bound=min(bound,cap)
  feasible=[q for q in range(units['buy_minimum'],bound+1,units['buy_step']) if risk(q,p,sch)<=beta]
  return max(feasible,default=0)
 qs_risk=maxq(pclose,sclose,uclose);qopen_risk_unfrozen=maxq(popen,sopen,uopen)
 Qclose=sum(x['qty'] for x in r0['same_stock_at_signal_CLOSE']);Qopen=r0['same_stock_before_reserve_qty'];stock_remaining_close=max(Z,D('.1')*nav-D(Qclose)*rawclose);stockcapclose=legal_floor(int(stock_remaining_close/pclose),uclose);qsignal=min(qs_risk,stockcapclose)
 qopen_risk_frozen=maxq(popen,sopen,uopen,qsignal);stock_remaining_open=max(Z,D('.1')*nav-D(Qopen)*rawopen);stockcapopen=legal_floor(int(stock_remaining_open/popen),uopen);qopen_final_local=min(qopen_risk_frozen,stockcapopen)
 cash_before_original_slot=D(r0['original_OPEN_before_reserve_available_cash']);old_cash_reserve=D('.1')*nav;cash_necessary_spendable=max(Z,cash_before_original_slot-old_cash_reserve);cash_bound=int(cash_necessary_spendable/popen);cash_feasible=[q for q in range(uopen['buy_minimum'],cash_bound+1,uopen['buy_step']) if D(q)*popen+fee(q,popen,sopen,'buy')<=cash_necessary_spendable];qcash=max(cash_feasible,default=0);q_after_cash=min(qopen_final_local,qcash)
 assert qsignal<=qs_risk and qopen_final_local<=qsignal
 first_return=hist.index[0];price_pos=g.index.get_loc(first_return)-1;assert price_pos>=0;anchor=g.index[price_pos];wc=g.loc[anchor:hist.index[-1]];assert len(wc)==64
 windows.append(dict(layer=r0['layer'],signal=day,source_segment=int(f.segment_id.iloc[-1]),valid_block_observations_through_signal=len(g),s63=s63,cached_CP_current_z=cached,current_return_excluded=True,first_return_day=str(first_return.date()),last_return_day=str(hist.index[-1].date()),first_anchor_close_day=str(anchor.date()),absolute_returns=[dict(day=str(t.date()),absolute_log_return=float(abs(v))) for t,v in hist.items()],original_64_price_observations=[dict(day=str(t.date()),causal_signal_close=float(z.close),amount=float(z.amount),source_segment=int(z.segment_id)) for t,z in wc.iterrows()]))
 row=dict(layer=r0['layer'],role=r0['role'],signal=day,OPEN=od,original_actual_q=r0['actual_filled_shares'],original_intent_cap_reference_only=r0['original_intent_max_shares'],original_intent_gross_budget_reference_only=r0['original_frozen_intent']['budget'],original_source_cap_or_mobile_2pct_applied=False,
  signal_NAV=nav,single_order_beta=beta,s63=s63,log_gap_buffer=2*s63,gap_multiplier=buffer_multiplier,raw_h=h,raw_stressH=stressH,raw_gap_buffer=h-stressH,stress_sell_price_after_5bps=sellprice,original_adjusted_floor=r0['original_frozen_intent']['floor'],signal_factor=F,OPEN_factor=Fopen,raw_signal_close=rawclose,p_signal=pclose,raw_OPEN=rawopen,p_OPEN=popen,
  units_CLOSE=uclose,units_OPEN=uopen,fee_schedule_CLOSE=sclose,fee_schedule_OPEN=sopen,q_signal_risk_only=qs_risk,signal_stock_Q=Qclose,signal_stock_10pct_remaining_gross=stock_remaining_close,new_signal_stockcap_qty=stockcapclose,q_signal_frozen=qsignal,
  q_OPEN_risk_only_before_freeze=qopen_risk_unfrozen,q_OPEN_risk_freeze_capped=qopen_risk_frozen,OPEN_stock_Q=Qopen,OPEN_stock_10pct_remaining_gross=stock_remaining_open,OPEN_stockcap_qty=stockcapopen,q_OPEN_conditional_local=qopen_final_local,q_OPEN_conditional_local_scope='risk plus stock cap only; excludes the separate same-original-slot cash necessary gate and final aggregate gates',
  original_OPEN_PVR_reserve_slot_available=cash_before_original_slot,original_cash10pct_reserve_frozen_signal_NAV=old_cash_reserve,same_original_slot_cash_necessary_spendable=cash_necessary_spendable,same_original_slot_cash_necessary_qcap=qcash,q_OPEN_after_known_cash_necessary_gate=q_after_cash,R_OPEN_after_known_cash_necessary_gate=risk(q_after_cash,popen,sopen),cash_cost_at_cashcap=D(qcash)*popen+fee(qcash,popen,sopen,'buy'),cash_next_grid_cost=D(qcash+uopen['buy_step'] if qcash else uopen['buy_minimum'])*popen+fee(qcash+uopen['buy_step'] if qcash else uopen['buy_minimum'],popen,sopen,'buy'),cash_scope='Same original PVR reserve slot only; not a new account cash path or sole cause of original quantity. No signal CLOSE cash is substituted for this original OPEN field.',
  R_signal_at_riskcap=risk(qs_risk,pclose,sclose),R_signal_next_risk_grid=risk(qs_risk+uclose['buy_step'] if qs_risk else uclose['buy_minimum'],pclose,sclose),R_OPEN_at_local=risk(qopen_final_local,popen,sopen),OPEN_local_buyfee=fee(qopen_final_local,popen,sopen,'buy'),OPEN_local_sellfee=fee(qopen_final_local,sellprice,sopen,'sell'),
  minimum_CLOSE_R=risk(uclose['buy_minimum'],pclose,sclose),minimum_CLOSE_fits_beta=risk(uclose['buy_minimum'],pclose,sclose)<=beta,minimum_OPEN_R=risk(uopen['buy_minimum'],popen,sopen),minimum_OPEN_fits_beta=risk(uopen['buy_minimum'],popen,sopen)<=beta,
  final_grant='NOT_IDENTIFIED_NEW_CONCURRENT_STOCK_INDUSTRY_BOOK_AND_OTHER_FINAL_GATES_NOT_REBUILT',scope='independent saved original prefix; single-order beta, not v3 shared B/D; no sequence/returns; original q unchanged',current_concurrent_contract_scope='stock structural concurrent .005*currentNAV and industry .01*currentNAV; no cumulative realized D hard gate; live K includes paid buyfee once; not implemented by this single-order table',consecutive_loss_cap='NOT_CAPPED_BY_SINGLE_ORDER_BETA')
 results.append(row)
save('SIX_SINGLE_ORDER_ARITHMETIC.json',results);save('CAUSAL_S63_WINDOW_EVIDENCE.json',windows)
fields=['layer','role','signal','OPEN','original_actual_q','single_order_beta','s63','raw_h','raw_stressH','raw_gap_buffer','p_signal','p_OPEN','q_signal_risk_only','new_signal_stockcap_qty','q_signal_frozen','q_OPEN_risk_only_before_freeze','q_OPEN_risk_freeze_capped','OPEN_stockcap_qty','q_OPEN_conditional_local','same_original_slot_cash_necessary_spendable','same_original_slot_cash_necessary_qcap','q_OPEN_after_known_cash_necessary_gate','minimum_OPEN_fits_beta','R_OPEN_at_local']
with (O/'SIX_SINGLE_ORDER_TABLE.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in results)
cash_code=Q/'current_strategy_source_dossier_v1/yingxin_chain/NO60_ACTIVE_ROUTE_SOURCE.txt';SRC[str(cash_code)]=sha(cash_code)
save('PROTOCOL.json',dict(status='FIXED_SIX_INDEPENDENT_POINT_ARITHMETIC_ONLY',s63='1.4826 * median(abs(previous63 causal same-valid-block log close returns)); shift excludes current, identical original PVR mask/segment reset',stressH='original intent effective raw h*exp(-2*s63), frozen at signal; sizing stress only, original actual exit h not overwritten',risk='q*(p-stressH*(1-.0005))+datedbuyfee+datedsellfee',beta='.0025*each original signal NAV, independent per single order; no shared D/kappa',close='risk cap and original stock10% remaining gross at known signal reference buyprice; freeze minimum',OPEN='known original OPEN+5bps and dated rules/fees, only shrink<=new frozen q_signal; preserve stock10% remaining check',source_cap='old actual q/cap/budget and mobile2% only reference, not applied to new sizing',known_cash='a.available at the same original PVR reserve slot minus .1*signal a.current_nav; dated gross+buyfee grid only, a necessary cap not a new account cash path',unverified='new concurrent stock .005NAV / industry .01NAV aggregate and other final controls not rebuilt; no cumulative realized D hard gate, repeated realized loss not capped by single beta; conditional local only',new_models=0,new_accounts=0,new_backtests=0,parameter_scan=False))
save('SOURCE_MANIFEST.json',dict(sources=SRC,script_sha256=sha(__file__),single_stock_signal_volatility_read=True,all_other_prior_artifacts_unchanged=True))
save('VALIDATION.json',dict(rows=6,original_layers=[r['layer'] for r in old],all_s63_exact_original_current_z_within_float_tolerance=True,all_windows_previous63_only_same_block=True,all_OPEN_prices_exact_original_actual_fill_prices=True,all_OPEN_q_no_larger_than_new_frozen_CLOSE_cap=True,no_original_2pct_or_original_source_cap_applied=True,no_new_paths_or_account_gains=True))
print(json.dumps([{k:r[k] for k in ['layer','signal','OPEN','original_actual_q','single_order_beta','s63','raw_h','raw_stressH','q_signal_risk_only','new_signal_stockcap_qty','q_signal_frozen','q_OPEN_conditional_local','minimum_OPEN_fits_beta']} for r in results],ensure_ascii=False,default=str))
