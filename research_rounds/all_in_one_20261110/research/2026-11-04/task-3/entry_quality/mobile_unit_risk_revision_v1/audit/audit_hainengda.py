"""Parent-fixed original Hainengda chain: scalar reference-risk audit, no engine imports."""
from pathlib import Path
from decimal import Decimal as D, getcontext
import json,hashlib
import pandas as pd
getcontext().prec=50
OUT=Path(__file__).resolve().parent;ENTRY=OUT.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');SRC={};CHECKS=[];Z=D(0);SLIP=D('.0005')
def read(p):
 p=Path(p);data=p.read_bytes();SRC[str(p)]=hashlib.sha256(data).hexdigest();return json.loads(data)
def sha(p):p=Path(p);h=hashlib.sha256(p.read_bytes()).hexdigest();SRC[str(p)]=h;return h
def check(n,x):CHECKS.append({'name':n,'pass':bool(x)});assert x,n
chains=read(ENTRY/'structural_failure_v1/chains/COMPLETE_ORIGINAL_CHAINS.json');chain=next(x for x in chains if x['campaign']['sid']=='002583.SZ')
check('use exactly parent-named existing campaign and layers',chain['campaign']['layer_ids']==[1994,2017,2039])
sm=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');m=next(x for x in sm if x['symbol']=='002583.SZ')
frames={}
for key in ['facts','CP1','CP1_input']:
 p=Path(m['refs'][key]);check('source hash '+key,sha(p)==m['output_sha256'][str(p)]);frames[key]=pd.read_parquet(p)
signal=Path(next(p for p in m['source_sha256']if p.endswith('/signal.parquet')));check('original raw signal bytes',sha(signal)==m['source_sha256'][str(signal)]);bars=pd.read_parquet(signal)
rulespath=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');rules=read(rulespath)
model=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py');sha(model)
check('s63 definition is original shifted zero-centered63, not receipt frozen scale', 'r.abs().shift().rolling(63,min_periods=63).median().mul(1.4826).clip(lower=1e-8)' in model.read_text())
obs={r['day']:r for r in chain['observations']}
def version(xs,day):return next(v for v in xs if v['from']<=day and(v['to']is None or day<v['to']))
def fee(q,p,schedule,side):
 if not q:return Z
 amount=D(q)*p;total=Z
 for c in schedule['components']:
  if c.get('side','both')not in ['both',side]:continue
  check('selected fee components are unrounded notional',c.get('amount_basis','notional')=='notional'and c.get('maximum_local')is None and c.get('rounding_unit')is None)
  total+=max(D(c.get('minimum_local','0')),amount*D(c['rate']))
 return total
def amounts(q,p,h,schedule):
 exit_ref=h*(1-SLIP);bf=fee(q,p,schedule,'buy');sf=fee(q,exit_ref,schedule,'sell')
 return {'q':q,'price_to_stressed_net_line':str(D(q)*(p-exit_ref)),'hypothetical_buyfee':str(bf),'hypothetical_sellfee':str(sf),'all_in_reference_R':str(D(q)*(p-exit_ref)+bf+sf)}
def maxrisk(p,h,B,units,schedule,upper=None):
 gap=p-h*(1-SLIP);check('positive unit reference gap',gap>0)
 bound=int(B/gap)
 if upper is not None:bound=min(bound,upper)
 candidates=range(units['buy_minimum'],bound+1,units['buy_step'])
 return max((q for q in candidates if D(amounts(q,p,h,schedule)['all_in_reference_R'])<=B),default=0)
rows=[]
for entry in chain['entries']:
 buy=entry['actual_buy'];a=entry['original_signal_and_authorization'];lid=entry['layer'];day=buy['signal_at'][:10];od=buy['at'][:10];t=pd.Timestamp(day);ot=pd.Timestamp(od)
 f,cf,inp=frames['facts'].loc[t],frames['CP1'].loc[t],frames['CP1_input'].loc[t]
 check(str(lid)+': same causal source/price prefix clock',f.segment_id==inp.segment_id and f.close==inp.close and frames['facts'].loc[:t].index.equals(frames['CP1_input'].loc[:t].index))
 i=frames['CP1_input'].index.get_loc(t);window=frames['CP1_input'].iloc[i-64:i]
 check(str(lid)+': prior63 returns use64 prior prices and exclude current',len(window)==64 and window.index[-1]<t and window.segment_id.eq(inp.segment_id).all())
 s=D(str(cf.s));check(str(lid)+': original s ready and positive',s>0 and pd.notna(cf.s))
 NAV=D(a['decision_NAV']);B=NAV*D('.0025');factor=D(str(f.factor));floor_a=D(a['frozen_intent']['floor']);h=floor_a/factor;stress=h*(-2*s).exp()
 C=D(str(f.raw_close));p=C*(1+SLIP);units=version(rules['quantity_versions']['002583.SZ'],day)['rule'];venue=version(rules['venue_versions']['002583.SZ'],day)['venue'];schedule=version(rules['fee_versions'][venue],day)['schedule']
 check(str(lid)+': raw signal quote and frozen floor agree with existing chain',C==D(a['signal_close_raw']) and abs(h-D(a['initial_raw_floor']))<D('1e-12'))
 risk_signal=maxrisk(p,stress,B,units,schedule)
 heldq=sum(int(l['snapshot']['qty'])for l in obs[day]['actual_live_layers'])
 stock_remaining=max(Z,NAV*D('.10')-D(heldq)*C)
 stockq=units['buy_minimum']+max(0,(int(stock_remaining/p)-units['buy_minimum'])//units['buy_step'])*units['buy_step'] if stock_remaining>=D(units['buy_minimum'])*p else 0
 frozen=min(risk_signal,stockq)
 nextfactor=D(str(frames['facts'].loc[ot].factor));open_h=floor_a/nextfactor;open_stress=open_h*(-2*s).exp();rawopen=D(str(bars.loc[ot].raw_open));openp=rawopen*(1+SLIP);openschedule=version(rules['fee_versions'][venue],od)['schedule'];openunits=version(rules['quantity_versions']['002583.SZ'],od)['rule']
 check(str(lid)+': exact actual OPEN and no future CLOSE line',rawopen==D(buy['raw_open']) and floor_a==D(buy['floor']))
 qr=maxrisk(openp,open_stress,B,openunits,openschedule);qo=maxrisk(openp,open_stress,B,openunits,openschedule,upper=frozen)
 check(str(lid)+': OPEN never expands frozen signal quantity',qo<=frozen)
 rows.append({'layer':lid,'role':a['role'],'signal_day':day,'next_OPEN':od,'actual_original_q':buy['shares'],'actual_original_price':buy['price'],'old_source_cap_comparison_only':a['frozen_intent']['cap'],'old_mobile_2percent_budget_comparison_only':a['frozen_intent']['budget'],'signal_NAV':str(NAV),'budget_quarter_percent_signal_NAV':str(B),'original_s63_cached':str(s),'s63_last_return_end_day':str(window.index[-1].date()),'s63_prior_price_window_start':str(window.index[0].date()),'s63_price_count_for63returns':64,'signal_raw_close':str(C),'signal_buy_reference':str(p),'true_frozen_adjusted_h':str(floor_a),'true_raw_signal_h':str(h),'signal_Hstress_raw':str(stress),'risk_only_signal_cap':risk_signal,'actual_existing_signal_q':heldq,'known_stock10_remaining_gross':str(stock_remaining),'stock10_only_quantity_cap':stockq,'new_frozen_signal_cap':frozen,'signal_cost_at_risk_only_cap':amounts(risk_signal,p,stress,schedule),'signal_next_grid_cost':amounts(risk_signal+units['buy_step'],p,stress,schedule),'raw_actual_next_OPEN':str(rawopen),'known_OPEN_buy_reference':str(openp),'same_signal_s63_at_OPEN':str(s),'OPEN_frozen_h_same_unit':str(open_h),'OPEN_Hstress_raw':str(open_stress),'OPEN_risk_only_cap':qr,'OPEN_local_cap_after_new_signal_freeze':qo,'OPEN_reference_cost':amounts(qo,openp,open_stress,openschedule),'OPEN_next_grid_cost':amounts(qo+openunits['buy_step'],openp,open_stress,openschedule),'original_q_stressed_reference_only':amounts(buy['shares'],openp,open_stress,openschedule),'units':units,'fee_schedule':schedule,'scope':'Single-order risk and known stock10 local cap only. Both CORE/MOBILE revised; old mobile2percent/sourcecap are comparison columns. No sector/pool/cash/liquidity or final grant asserted.','final_grant':False})
res={'status':'PARENT_FIXED_HAINENGDA_THREE_LAYER_INDEPENDENT_ARITHMETIC','campaign_id':chain['campaign']['campaign_id'],'existing_selection_field_not_used_as_formula_input':chain['selection'],'role_scope':'Both CORE and MOBILE; no name exemption. New risk sizing replaces old MOBILE fixed2percent primary quantity, old source cap not used as candidate upper bound.','sigma_scope':'Existing original CP .s at decision CLOSE, source code and prior63-return clock bound; not CP .z or receipt used_scale. No original model executed.','math_precision':'Independent Decimal precision50, exponential at precision50; compare float-based production display within1e-8 CNY without changing integer quantity.','rows':rows,'checks':CHECKS,'source_sha256':SRC,'new_accounts':0,'new_models':0,'parameter_scans':0,'new_profit_path':0}
res['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(OUT/'HAINENGDA_INDEPENDENT_REFERENCE_NUMBERS.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{'layer':r['layer'],'role':r['role'],'signal_risk':r['risk_only_signal_cap'],'signal_frozen':r['new_frozen_signal_cap'],'OPEN_risk':r['OPEN_risk_only_cap'],'OPEN_frozen':r['OPEN_local_cap_after_new_signal_freeze'],'old_actual':r['actual_original_q'],'R_OPEN':r['OPEN_reference_cost']['all_in_reference_R']}for r in rows],ensure_ascii=False))
