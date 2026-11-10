"""Independent accounting + eight frozen cells; no new execution paths."""
from pathlib import Path
from decimal import Decimal as D
from datetime import datetime,timezone
import json,gzip,csv,sys,importlib.util,collections,bisect,time
import pandas as pd
import numpy as np
ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');O=ROOT/'research_rounds/n1-structural-finite-20261029';SRC=ROOT/'research_rounds/broad-stage-reentry-20261029';OLD=ROOT/'research_rounds/rs-h1-execution-20261025';t0=time.monotonic();Z=D(0)
sys.path.insert(0,str(OLD/'code'));sp=importlib.util.spec_from_file_location('finite_independent_accounting',OLD/'code/analyze_accounts.py');Q=importlib.util.module_from_spec(sp);sys.modules[sp.name]=Q;sp.loader.exec_module(Q)
from sector_account import FeeSchedule,FeeComponent
from market_rules import market_identity_on,version_on
read=lambda p:json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def csvout(p,rr):
 with Path(p).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
meta=pd.read_csv(ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv').set_index('symbol').to_dict('index');rules=read(ROOT/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');proto=read(OLD/'inputs-v2/economic-protocol.json');prices=Q.Prices.__new__(Q.Prices);prices.records={r['series_id']:r for r in read(ROOT/'research_rounds/pvr-act-comparison-20261027/input/manifest.json')['series']};prices.cache={}
run=read(O/'full/RUN_META.json');assert all(n==681 for n in run['completed_closes'].values()),'partial output; no economic conclusion'
aliases=read(O/'full/ALIASES.json');gate=read(O/'PREFIX_GATE.json');obj={};daily={}
obj['R_base_orig']=read(SRC/'results/N1.json')
with gzip.open(SRC/'results/daily.jsonl.gz','rt') as f:daily['R_base_orig']=[json.loads(l) for l in f if '"account": "N1"' in l]
with gzip.open(O/'full/daily.jsonl.gz','rt') as f:
 for line in f:
  r=json.loads(line);daily.setdefault(r.pop('path'),[]).append(r)
for name in run['paths']:obj[name]=read(O/'full'/(name+'.json'))
for name,rec in aliases.items():obj[name]=read(O/'full'/(name+'.json'));daily[name]=daily[rec['economic_source']]
slots=['R_base_orig','R_base_swap','R_cost2_orig','R_cost2_swap','S_base_orig','S_base_swap','S_cost2_orig','S_cost2_swap'];assert set(slots)==set(obj)==set(daily)
calendar=sorted({pd.Timestamp(r['at']) for r in daily['R_base_orig']});curves=[];summaries=[];audit_reports=[];campaignrows=[];stockrows=[];riskrows=[];cashrows=[];fee_checks=0
for name in slots:
 o=obj[name];ds=daily[name];assert len(ds)==681;cost=2 if 'cost2' in name else 1
 # Independent exact historical fee schedule, cumulative order minimum and accrual.
 state={}
 for e in o['audit']:
  if e['kind']!='fill':continue
  r=e['receipt'];sid=r['security_id'];day=pd.Timestamp(r['at']).date();venue=market_identity_on(rules,sid,day,proto['approved_proxy_ids'])['venue'];record=version_on(rules['fee_versions'][venue],str(day),proto['approved_proxy_ids'])['schedule'];fs=FeeSchedule(record['schedule_id'],tuple(FeeComponent(**a) for a in record['components']));assert fs.schedule_id==e['fee_schedule'];paid,accr=state.get(e['order_id'],({},{}));kw=dict(shares=r['shares'],par_value=rules.get('security_metadata',{}).get(sid,{}).get('par_value'));gross=D(r['gross_cny']);components=fs.incremental(r['side'],gross,paid,accr,cost,**kw);assert components=={k:D(v) for k,v in e['fee_components'].items()};ra=fs.rate_accrual(r['side'],gross,cost,**kw);state[e['order_id']]=({k:paid.get(k,Z)+v for k,v in components.items()},{k:accr.get(k,Z)+v for k,v in ra.items()});fee_checks+=1
 cs,audit=Q.audit_account('B0_'+name+('_cost2' if cost==2 else '_base'),dict(audit_log=o['audit']),ds,prices,meta,calendar)
 audit_reports.append(dict(path=name,**audit));campaignrows.extend(dict(path=name,**{k:v for k,v in c.items() if k!='account'}) for c in cs)
 nav=np.array([float(d['nav']) for d in ds]);mv=np.array([float(d['inventory']) for d in ds]);dd=1-nav/np.maximum.accumulate(nav);layer_pnl=[]
 for x in o['layers']:
  pnl=D(x['cash'])+D(x['dividend'])+D(x['qty'])*prices.mark(x['sid'],'2026-10-27');layer_pnl.append(pnl)
 assert abs(sum(layer_pnl,Z)-(D(ds[-1]['nav'])-D(1000000)))<D('0.00000001')
 stocks=collections.defaultdict(lambda:Z)
 for c in cs:stocks[c['symbol']]+=c['net_pnl']
 for sid,pnl in stocks.items():stockrows.append(dict(path=name,symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],net_pnl=pnl))
 acts=[e for e in o['audit'] if e['kind']=='risk_checkpoint' and e.get('event')]
 riskrows.extend(dict(path=name,**e) for e in acts)
 source='reused_original_681_days' if name=='R_base_orig' else 'full_state_hash_alias:'+aliases[name]['economic_source'] if name in aliases else 'computed_full_path'
 row=dict(path=name,status='complete',source=source,final_nav=ds[-1]['nav'],net_profit=D(ds[-1]['nav'])-D(1000000),net_return=nav[-1]/1000000-1,max_drawdown=float(dd.max()),mean_exposure=float(np.mean(mv/nav)),mean_positions=float(np.mean([len(d['positions']) for d in ds])),peak_positions=max(len(d['positions']) for d in ds),peak_market_value=float(mv.max()),fees_cny=ds[-1]['fees_cny'],slippage=sum((abs(D(t['price'])-D(t['raw_open']))*t['shares'] for t in o['trades']),Z),all_negative_layers=-sum((min(Z,p) for p in layer_pnl),Z),all_negative_cycles=-sum((min(Z,c['net_pnl']) for c in cs),Z),tail30_closed=sum((c['net_pnl'] for c in cs if c['closed'] and c['net_return'] is not None and c['net_return']>=.30),Z),tail30_open_valued=sum((c['net_pnl'] for c in cs if not c['closed'] and c['net_return'] is not None and c['net_return']>=.30),Z),ordinary_cycles=sum((c['net_pnl'] for c in cs if c['net_return'] is None or c['net_return']<.30),Z),open_cycles=sum(not c['closed'] for c in cs),max_stock_weight=audit['max_stock_weight'],max_sector_weight=audit['max_sector_weight'],top5_stock_pnl=sum((v for s,v in sorted(stocks.items(),key=lambda x:-x[1])[:5]),Z),pause_days='|'.join(e['at'][:10] for e in acts if e['event']=='pause'),resume_days='|'.join(e['at'][:10] for e in acts if e['event']=='resume'),active_days=sum(d['on'] for d in ds),buy_fills=sum(t['side']=='buy' for t in o['trades']),sell_fills=sum(t['side']=='sell' for t in o['trades']),stages_promoted=sum(e['kind']=='stage_promote' for e in o['audit']),whole_order_unfunded=o['counts'].get('whole_order_unfunded',0),open_contract_rejected=o['counts'].get('allocation_open_minimum_exceeds_frozen_contract',0),terminal_stock=ds[-1]['inventory'],terminal_claim=ds[-1]['dividend_receivable'],terminal_sale_receivable=ds[-1]['sale_receivable'])
 summaries.append(row)
 for d,v,draw in zip(ds,nav,dd):curves.append(dict(path=name,date=d['at'][:10],nav=d['nav'],inventory=d['inventory'],available=d['available'],reserved=d['order_reserved'],claim=d['dividend_receivable'],on=d['on'],positions=len(d['positions']),drawdown=float(draw)))
 print(json.dumps(dict(path=name,audited_days=681,fills=len(o['trades']),seconds=time.monotonic()-t0)),flush=True)
unique={s['path']:s for s in summaries};comparisons=[]
for cost in ['base','cost2']:
 for order in ['orig','swap']:
  r,s=unique['R_'+cost+'_'+order],unique['S_'+cost+'_'+order];comparisons.append(dict(cost=cost,order=order,net_profit_delta=s['net_profit']-r['net_profit'],max_drawdown_delta=s['max_drawdown']-r['max_drawdown'],max_stock_weight_delta=s['max_stock_weight']-r['max_stock_weight'],max_sector_weight_delta=s['max_sector_weight']-r['max_sector_weight'],mean_exposure_delta=s['mean_exposure']-r['mean_exposure'],negative_layers_delta=s['all_negative_layers']-r['all_negative_layers'],negative_cycles_delta=s['all_negative_cycles']-r['all_negative_cycles'],tail30_closed_delta=s['tail30_closed']-r['tail30_closed']))
# First observable transmission, without selecting winners by future profit.
def first_difference(a,b,fields):
 for x,y in zip(daily[a],daily[b]):
  if any(x[k]!=y[k] for k in fields):return dict(date=x['at'][:10],reference={k:x[k] for k in fields},candidate={k:y[k] for k in fields})
 return None
financial=first_difference('R_base_orig','S_base_orig',['positions','available','inventory','nav']);intent=first_difference('R_base_orig','S_base_orig',['pending_sells']);date=financial['date'];prev=max(d['at'][:10] for d in daily['R_base_orig'] if d['at'][:10]<date)
transmission=dict(first_pending_exit_difference=intent,first_financial_difference=financial,previous_decision_date=prev,reference_exit_requests=[e for e in obj['R_base_orig']['audit'] if e['kind']=='pilot_layer_exit' and e['at'][:10]==prev],reference_fills=[t for t in obj['R_base_orig']['trades'] if t['at'][:10]==date],candidate_fills=[t for t in obj['S_base_orig']['trades'] if t['at'][:10]==date])
alloc={name:{(e['at'][:10],e['sid']):e for e in obj[name]['audit'] if e['kind']=='lot_allocation'} for name in ['R_base_orig','S_base_orig']}
for key in sorted(set(alloc['R_base_orig'])&set(alloc['S_base_orig'])):
 a,b=alloc['R_base_orig'][key],alloc['S_base_orig'][key]
 if key[0]>=date and a['minimum_selected']!=b['minimum_selected']:
  transmission['first_same_candidate_allocation_difference']=dict(date=key[0],symbol=key[1],reference=a,candidate=b,note='Both passed their actual legal preview; minimum_selected is explicit whole-order cash allocation, not inferred missed-profit attribution');break
# Exposure of the single corrected perturbation, including actual financial effect.
perturb_rows=[]
for prefix in ['R_base','R_cost2','S_base','S_cost2']:
 name=prefix+'_swap';log=next((p for p in gate['perturbation'] if p['path']==name),None);a,b=obj[prefix+'_orig'],obj[name];day='2024-03-14';buy=lambda o:[dict(sid=t['security_id'],shares=t['shares'],gross=t['gross_cny'],fees=t['fees_cny']) for t in o['trades'] if t['side']=='buy' and t['at'][:10]==day]
 perturb_rows.append(dict(path=name,attempt=log,full_state_proof=next(p for p in gate['proofs'] if p['paths'][1]==name),original_buys=buy(a),swapped_buys=buy(b),actual_buy_difference=buy(a)!=buy(b),financial_alias=name in aliases))
proof_index=gate['proofs'];base_deltas=[c['net_profit_delta'] for c in comparisons];allpos=all(v>0 for v in base_deltas);allneg=all(v<=0 for v in base_deltas);risk_worse=any(c['max_drawdown_delta']>0 or c['max_stock_weight_delta']>0 or c['max_sector_weight_delta']>0 for c in comparisons)
verdict='not_supported' if allneg else 'explicit_tradeoff_not_promoted' if risk_worse or not allpos else 'conditional_candidate_not_promoted'
result=dict(verdict=verdict,summary=summaries,comparisons=comparisons,perturbation=perturb_rows,accounting=audit_reports,independent_fee_fills=fee_checks,no_product_changes=True,only_one_protection_module_changed=True)
csvout(O/'EIGHT_CELLS.csv',summaries);csvout(O/'POLICY_DIFFERENCES.csv',comparisons);csvout(O/'campaigns.csv',campaignrows);csvout(O/'stocks.csv',stockrows);csvout(O/'curves.csv',curves);save(O/'RESULTS.json',result);save(O/'TRANSMISSION.json',transmission);save(O/'PERTURBATION_EFFECT.json',perturb_rows);save(O/'ACCOUNTING.json',dict(passed=True,paths=8,unique_financial_paths=1+len(run['paths']),audited_daily_rows=8*681,independent_fee_fills=fee_checks,receipts=audit_reports,layer_pnl_reconciled=True,all_input_hashes_checked_by_driver=True))
now=datetime.now(timezone.utc);start=datetime(2026,10,29,17,19,4,tzinfo=timezone.utc);budget=read(O/'REMAINING_BUDGET_TRACKER.json');timing=dict(start=start.isoformat(),finished=now.isoformat(),total_wall_seconds=(now-start).total_seconds(),successful_run_process_seconds=run['total_process_seconds'],failed_hash_attempt_seconds=budget['failed_date_serialization_attempt_wall_seconds'],post_accounting_seconds=time.monotonic()-t0,remaining_budget_used_seconds=run['total_process_seconds']+budget['failed_date_serialization_attempt_wall_seconds']+time.monotonic()-t0,authorized_remaining_seconds=900,earlier_300s_partial_archive=True)
save(O/'TIMING.json',timing);save(O/'COMPLETION.json',dict(status='complete',verdict=verdict,slots=8,computed_new_full_paths=len(run['paths']),reused_original=1,hash_reused_aliases=len(aliases),not_run_slots=[],next_experiment_started=False,remaining_budget_used_seconds=timing['remaining_budget_used_seconds']))
print(json.dumps(dict(verdict=verdict,comparisons=comparisons,summary=[{k:r[k] for k in ['path','source','net_return','max_drawdown','mean_exposure','max_stock_weight','max_sector_weight','whole_order_unfunded']} for r in summaries],transmission=transmission,timing=timing),ensure_ascii=False,default=str))
