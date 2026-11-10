"""Independent M3 core/reference budget reconstruction; no strategy imports or history runs."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,sys
import pandas as pd
O=Path(__file__).resolve().parent
exec(compile((O/'reconcile_actual_ledger.py').read_text().split('for row in ledger:')[0],str(O/'reconcile_actual_ledger.py'),'exec'),globals())
ref=read(run/'REFERENCE_DAILY.json');caplots=read(run/'CAPITAL_LOTS.json');requests=read(run/'REFERENCE_REQUESTS.json');conf=read(run/'INFORMATION_CONFIRMATIONS.json');trans=read(run/'TRANSFERS.json')
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');known=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet');right=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet');pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']).pivot(index='day',columns='sid',values='state').reindex(index=known.index,columns=known.columns);known=known&pv.ge(0);right=right&known;calendar=known.index
facts={s:pd.read_parquet(manifest[s]['refs']['facts']) for s in raw};sourcecp={s:pd.read_parquet(manifest[s]['refs']['CP1']) for s in raw};bylot={x['lot_id']:x for x in orders if x['side'].startswith('BUY')};bysec={(x['day'],x['sector51']):x for x in sector_daily};confhist=set();flow=defaultdict(lambda:D(0));dividend=defaultdict(lambda:D(0));rd=byday(ref);cld=byday(caplots);cod=byday(conf);rqd=byday(requests);reports=[]
def truth(x):return pd.notna(x) and x in (True,1)
def false(x):return pd.notna(x) and x in (False,0)
def finite(x):return x is not None and pd.notna(x) and abs(float(x))!=float('inf')
def close(label,x,y,ctx,tol=D('0.0000001')):equal(label,abs(D(str(x))-D(str(y)))<=tol,True,dict(context=ctx,actual=str(x),expected=str(y)))
def floor_sell(q,held,qr):
 q=min(max(0,int(q)),held)
 return held if q==held and qr.get('allow_full_exit_odd',False) else q//qr['sell_step']*qr['sell_step']
def analytic_water(lower,e,b):
 if b<sum(lower.values(),D(0)):return {},None,'INFEASIBLE_LOWER_EXCEEDS_BUDGET'
 if not e:return {},None,'NO_POSITIVE_E_M'
 fixed=set()
 while True:
  free=set(e)-fixed
  if not free:return dict(lower),D(0),'PASS'
  lam=(b-sum((lower[s] for s in fixed),D(0)))/sum((e[s] for s in free),D(0))
  new={s for s in free if lower[s]>lam*e[s]}
  if not new:return {s:lower[s] if s in fixed else lam*e[s] for s in e},lam,'PASS'
  fixed|=new
for dt in sorted(ld):
 ts=pd.Timestamp(dt);nxt=str(calendar[calendar.get_loc(ts)+1].date());h=hd.get(dt,[]);hmap={x['lot_id']:x for x in h};rows=cld.get(dt,[]);equal('core_inventory_exact_lot_population',{x['lot_id'] for x in rows},set(hmap),dt)
 for x in cod.get(dt,[]):
  if x['phase']=='OPEN' and x['decision']=='INFORMATION_CONFIRMED':confhist.add(x['round_id'])
 provisional={x['round_id'] for x in cod.get(dt,[]) if x['phase']=='CLOSE'}
 for x in od.get(dt,[]):flow[x['round_id']]+=D(x['cash_delta'])
 for x in ed.get(dt,[]):
  if x['event']=='ACCRUE_NET80':dividend[x['round_id']]+=D(x['receivable_delta'])
 rounds=defaultdict(list)
 for x in h:rounds[x['round_id']].append(x)
 fixed=defaultdict(lambda:D(0));core=defaultdict(lambda:D(0));sector=defaultdict(lambda:D(0));stress=D(0)
 for x in rows:
  lid=x['lot_id'];hh=hmap[lid];s=hh['sid'];rid=hh['round_id'];sec=mapping[s];ss=bysec[(dt,sec)];q=hh['qty'];mark=price(s,dt,'raw_close');ls=rounds[rid];held=sum(v['qty'] for v in ls);sp=mark*D('.9995');net=flow[rid]+dividend[rid]+held*sp-fee(s,dt,held,sp,'sell');winner=rid in confhist and ss['M']==1 and net>0;locked=any(v['locked_exit'] for v in ls);seedq=seed[rid]['qty'];adds=sorted((v for v in ls if v['kind']=='ADD'),key=lambda v:(v['bought'],bylot[v['lot_id']]['order_seq'],v['lot_id']));first=adds[0]['lot_id'] if adds else None;cq=(q if hh['kind']=='SEED' else min(q,seedq) if lid==first else 0) if winner and not locked else 0
  f=facts[s].loc[ts];c=sourcecp[s].loc[ts];z=raw[s].loc[ts];st=int(right.at[ts,s]) if known.at[ts,s] else -1;unknown=[]
  if ss['M']==-1 or not finite(ss['E']):unknown.append('M_OR_E_UNKNOWN')
  if st==-1:unknown.append('STOCK_M3_UNKNOWN')
  valid=all(truth(z.get(k)) for k in ['observed_bar','price_eligible','volume_eligible']) and false(z.get('source_invalid')) and false(z.get('synthetic_event_bar'))
  origin=tuple(str(z.get(k)) for k in ['source_kind','source_path','segment_id']);seed_origin=tuple(str(raw[s].at[pd.Timestamp(seed[rid]['signal_day']),k]) for k in ['source_kind','source_path','segment_id'])
  if not valid or any(z.get(k) is None or pd.isna(z.get(k)) or str(z.get(k))=='' for k in ['source_kind','source_path','segment_id']) or origin!=seed_origin:unknown.append('QUOTE_SOURCE_UNKNOWN')
  if not (truth(f.get('i_target')) or false(f.get('i_target'))) or (truth(f.get('i_target')) and (not finite(f.get('i_floor')) or f.i_floor<=0)):unknown.append('I_UNKNOWN')
  if not (truth(c.get('receipt')) or false(c.get('receipt'))):unknown.append('CP_UNKNOWN')
  adds_count=sum(o['round_id']==rid and o['side']=='BUY_ADD' and o['day']<=dt for o in orders);seed_ok=rid not in confhist and rid not in provisional and adds_count==0 and ss['M']==0 and ss['state'] in [0,1] and st in [0,1] and finite(ss['E']);why='UNCONFIRMED_NON_MAINLINE_SEED' if hh['kind']=='SEED' and seed_ok else 'WEAK_SECTOR_ADD_LAYER' if hh['kind']=='ADD' and ss['M']==0 and ss['W'] else 'MAINLINE_REFERENCE_SURPLUS_ADD' if hh['kind']=='ADD' and ss['M']==1 and finite(ss['E']) else None
  qr=version(rules['quantity_versions'][s],nxt)['rule'];mobile=floor_sell(q-cq,held,qr) if why and not unknown and not locked and nxt>hh['bought'] else 0
  if hh['kind']=='SEED' and mobile!=q:mobile=0
  loss=mobile*mark-(mobile*sp-fee(s,nxt,mobile,sp,'sell')) if mobile else D(0)
  for k,v in dict(qty=q,core_qty=cq,frozen_qty=q-mobile,mobile_qty=mobile,confirmed_history=rid in confhist,current_winner=winner,original_seed_qty=seedq,earliest_surviving_ADD=first,unknown=unknown,locked=locked,donor_reason=why).items():equal('core_inventory_'+k,({'True':True,'False':False}.get(x[k],x[k]) if k in ['current_winner','confirmed_history','locked'] and isinstance(x[k],str) else x[k]),v,[dt,lid])
  for k,v in dict(round_net=net,raw_mark=mark,market_value=q*mark,core_value=cq*mark,frozen_value=(q-mobile)*mark,mobile_value=mobile*mark,mobile_sell_stress=loss).items():equal('core_inventory_'+k,D(x[k]),v,[dt,lid])
  fixed[sec]+=(q-mobile)*mark;core[sec]+=cq*mark;sector[sec]+=q*mark;stress+=loss
 rr={x['sector51']:x for x in rd.get(dt,[])};equal('reference_all_50',set(rr),set(sectors),dt);es={s:D(str(bysec[(dt,s)]['E'])) for s in sectors if bysec[(dt,s)]['M']==1 and finite(bysec[(dt,s)]['E']) and bysec[(dt,s)]['E']>0};outside=sum((fixed[s] for s in sectors if s not in es),D(0));nav=D(ld[dt]['NAV']);budget=nav*D('.9')-D(ld[dt]['receivable'])-outside-stress;target,lam,status=analytic_water({s:fixed[s] for s in es},es,budget)
 for s,x in rr.items():
  for k,v in dict(actual_value=sector[s],core=core[s],other_frozen=fixed[s]-core[s],fixed=fixed[s],budget=budget,stress=stress,receivable=D(ld[dt]['receivable']),outside_fixed=outside).items():equal('reference_'+k,D(x[k]),v,[dt,s])
  equal('reference_status',x['status'],status,[dt,s]);t=target.get(s,fixed[s]);close('reference_analytic_water_T',x['T'],t,[dt,s]);envelope=max(D(0),t-sector[s]) if status=='PASS' and s in es else D(0);close('reference_initial_envelope',x.get('initial_buy_envelope',x['buy_envelope']),envelope,[dt,s])
  equal('reference_lower_core_counted_once',D(x['T'])+D('0.0000001')>=fixed[s],True,[dt,s])
 if status=='PASS':close('reference_sum_T_exact_budget',sum((D(rr[s]['T']) for s in es),D(0)),budget,dt)
 reports.append(dict(day=dt,status=status,NAV=str(nav),budget=str(budget),stress=str(stress),core=str(sum(core.values(),D(0))),fixed=str(sum(fixed.values(),D(0))),positive_E_M=len(es)))
report=dict(result='PASS' if not errors else 'FAIL',days=len(ld),checks=dict(checks),check_count=sum(checks.values()),error_count=len(errors),errors=errors,daily=reports,basis='Actual lots/fees/round cashflow, independent M3 core cap and frozen/mobile inventory; analytic active-set water filling independent from engine binary search. Execution queue and actual financing separately checked.')
(O/(run.name+'_CORE_REFERENCE_AUDIT.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(dict(result=report['result'],checks=report['check_count'],errors=errors[:12]),ensure_ascii=False))
