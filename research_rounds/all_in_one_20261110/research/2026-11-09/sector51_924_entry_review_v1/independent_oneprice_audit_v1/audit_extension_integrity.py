"""Independent immutable-prefix, disabled-gate and path-accounting cross-checks."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,hashlib,ast,sys
O=Path(__file__).resolve().parent;P=O.parent;R=P/'oneprice_execution_stress_v1';V=sys.argv[1] if len(sys.argv)>1 else 'facts_v5';F=R/V;S=F/'full_20241031_once';read=lambda p:json.loads(Path(p).read_text());sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
f=read(F/'FREEZE.json');B=Path(f['source_facts']);base=B/'full_20241031_once';G=R/('gateoff_validation_'+V)/'full_20241031_once';GFACT=B
if not G.exists():
 G=R/'gateoff_validation_facts_v5/full_20241031_once';GFACT=P/'joint51_candidate_v5_facts'
checks=Counter();errors=[]
def ck(label,a,b,context=None):
 checks[label]+=1
 if a!=b:errors.append(dict(check=label,actual=str(a),expected=str(b),context=context))
names=['ORDERS','CANDIDATES','CP_EVENTS','DAY_LEDGER','HOLDINGS','EQUITY_EVENTS','SECTOR_DAILY','ATTEMPTS','PENDING_AT_END'];extra=['OPEN_INTENTS','OPEN_RESERVATIONS','NO_FILLS']
prior=R/('facts_v'+str(int(V.split('v')[-1])-1))/'full_20241031_once';prior_day=read(prior/'DAY_LEDGER.json')[-1]['day'];prefix=F/('checkpoint_'+prior_day.replace('-',''));counts={}
for name in names+extra:
 x=read(prior/(name+'.json'));y=read(prefix/(name+'.json'));ck('independent_12_family_prefix',x,y,name);counts[name]=len(x)
for name in names:
 x=read(G/(name+'.json'));y=read(GFACT/'full_20241031_once'/(name+'.json'))
 if name=='CANDIDATES':x=[{k:v for k,v in z.items() if k not in ['original_intended_q','reserved_q','fill_status']} for z in x]
 ck('independent_disabled_gate_baseline_exact',x,y,name)
ck('disabled_gate_no_nofills',read(G/'NO_FILLS.json'),[])
for p,h in {**f['source_hashes'],**f['scenario_hashes']}.items():ck('frozen_source_or_scenario_hash',sha(p),h,p)
for folder in [S,prefix,G]:
 for n,h in read(folder/'OUTPUT_HASHES.json').items():ck('output_hash',sha(folder/n),h,str(folder/n))
def methods(p):
 out={}
 for n in ast.parse(Path(p).read_text()).body:
  if isinstance(n,ast.FunctionDef):out[n.name]=ast.dump(n,include_attributes=False)
  if isinstance(n,ast.ClassDef):
   for fn in n.body:
    if isinstance(fn,ast.FunctionDef) and not(n.name=='Engine' and fn.name=='run'):out[n.name+'.'+fn.name]=ast.dump(fn,include_attributes=False)
 return out
ck('v4_v5_all_economic_functions_AST_exact',methods(B/'engine.py'),methods(P/'joint51_candidate_v4_facts/engine.py'))
root=ast.parse((R/'stress_engine.py').read_text());klass=next(x for x in root.body if isinstance(x,ast.ClassDef));own={x.name for x in klass.body if isinstance(x,ast.FunctionDef)}
ck('override_scope',own,{'__init__','no_fill','record_nofill','freeze_intent','exit_open','alloc_open','run','export'})
# Separately aggregate economic order changes, ignoring incidental round/lot sequence IDs.
so=read(S/'ORDERS.json');bo=read(base/'ORDERS.json');SL=read(S/'DAY_LEDGER.json');BL=read(base/'DAY_LEDGER.json');SH=read(S/'HOLDINGS.json');BH=read(base/'HOLDINGS.json');SE=read(S/'EQUITY_EVENTS.json');BE=read(base/'EQUITY_EVENTS.json')
def aggregate(orders):
 a={}
 for t in orders:
  key=(t['day'],t['sid'],t['side']);x=a.setdefault(key,dict(qty=0,cash=D(0),fees=D(0),count=0));x['qty']+=t['qty'];x['cash']+=D(t['cash_delta']);x['fees']+=D(t['fee']);x['count']+=1
 return a
sa=aggregate(so);ba=aggregate(bo);diff=[]
for key in sorted(set(sa)|set(ba)):
 zero=dict(qty=0,cash=D(0),fees=D(0),count=0);x=sa.get(key,zero);y=ba.get(key,zero)
 if x!=y:diff.append(dict(day=key[0],sid=key[1],side=key[2],scenario={k:str(v) if isinstance(v,D) else v for k,v in x.items()},baseline={k:str(v) if isinstance(v,D) else v for k,v in y.items()},delta_qty=x['qty']-y['qty'],delta_cash=str(x['cash']-y['cash']),delta_fees=str(x['fees']-y['fees'])))
ck('independent_all_trade_differences',diff,read(F/'ALL_TRADE_PATH_DIFFERENCES.json'))
barred={x['sid'] for x in read(S/'NO_FILLS.json') if x['side']=='BUY_SEED'}
def pnl_by_symbol(orders,holdings,equity,dt):
 out=defaultdict(lambda:D(0))
 for x in orders:
  if x['day']<=dt:out[x['sid']]+=D(x['cash_delta'])
 for x in holdings:
  if x['day']==dt:out[x['sid']]+=D(x['market_value'])
 for x in equity:
  if x['day']<=dt and x['event']=='ACCRUE_NET80':out[x['sid']]+=D(x['receivable_delta'])
 return out
daily=[];symbols=[]
for s,b in zip(SL,BL):
 ck('daily_comparison_date_match',s['day'],b['day']);dt=s['day'];sp=pnl_by_symbol(so,SH,SE,dt);bp=pnl_by_symbol(bo,BH,BE,dt);delta={sid:sp.get(sid,D(0))-bp.get(sid,D(0)) for sid in set(sp)|set(bp)};total=sum(delta.values(),D(0));nav=D(s['NAV'])-D(b['NAV']);ck('symbol_PNL_changes_sum_NAV_delta',total,nav,dt);direct=sum((v for sid,v in delta.items() if sid in barred),D(0));other=total-direct
 daily.append(dict(day=dt,baseline_NAV=b['NAV'],scenario_NAV=s['NAV'],NAV_delta=str(nav),barred_symbols_entire_path_delta=str(direct),other_symbols_path_delta=str(other),cash_delta=str(D(s['cash'])-D(b['cash'])),market_value_delta=str(D(s['market_value'])-D(b['market_value'])),receivable_delta=str(D(s['receivable'])-D(b['receivable'])),fees_delta=str(D(s['fees_paid'])-D(b['fees_paid']))))
 symbols += [dict(day=dt,sid=sid,delta=str(v),barred_symbol=sid in barred) for sid,v in sorted(delta.items()) if v]
lineage=[]
for nf in read(S/'NO_FILLS.json'):
 if nf['side']!='BUY_SEED':continue
 matches=[t for t in bo if t['day']==nf['day'] and t['sid']==nf['sid'] and t['side']=='BUY_SEED'];ck('barred_seed_has_unique_baseline_seed',len(matches),1,nf['sid']);r=matches[0]['round_id'];children=[t for t in bo if t['round_id']==r and t['side']=='BUY_ADD'];lineage.append(dict(sid=nf['sid'],baseline_round_id=r,baseline_descendant_ADDs=len(children),baseline_descendant_ADD_qty=sum(t['qty'] for t in children),certified_through=SL[-1]['day']))
block=read(S/'UNCERTIFIED_DAY.json')
for name in names+extra:
 for row in read(S/(name+'.json')):
  if 'day' in row:ck('blocked_day_absent_all_families',row['day']<block['day'],True,name)
ck('certified_ledger_stops_before_block',SL[-1]['day']<block['day'],True)
report=dict(status='PASS' if not errors else 'FAIL',scenario=str(S),check_count=sum(checks.values()),checks=dict(checks),errors=errors,certified_through=SL[-1]['day'],blocker=block,prefix_rows=counts,gateoff_compared_families=names,gateoff_compared_through=read(G/'DAY_LEDGER.json')[-1]['day'],gateoff_path=str(G),trade_path_difference_count=len(diff),barred_seed_lineages=lineage,last=daily[-1],limitations=['Exact-prefix and gate-disabled comparisons use independent reads of already executed outputs; this audit runs no historical strategy.','SELL and ADD no-fill paths have no observed historical example through this certificate; separately validated by 47 independent adversarial synthetic cases.','OHLC equality is an ex-post conditional execution stress gate, not reconstructed auction/queue/price-limit proof and not a return lower bound.','2%/4% and OPEN cash reservation caps are unchanged; close cash ratios can drift below 10% during market appreciation.','The fixed 1692-member/current-industry universe is not point-in-time.'])
for name,v in [('INTEGRITY_AND_DIFFERENCES',report),('INDEPENDENT_DAILY_DECOMPOSITION',daily),('INDEPENDENT_SYMBOL_DIFFERENCES',symbols),('INDEPENDENT_TRADE_DIFFERENCES',diff)]:
 p=O/V/(name+'.json');assert not p.exists();p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['checks']},ensure_ascii=False,indent=2))
