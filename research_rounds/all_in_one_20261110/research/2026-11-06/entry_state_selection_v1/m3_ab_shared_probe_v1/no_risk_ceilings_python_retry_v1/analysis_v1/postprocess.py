"""Read-only sealed account analysis; writes only new analysis directory."""
from pathlib import Path
from decimal import Decimal as D
import json,csv,collections,hashlib
HERE=Path(__file__).resolve().parent;RUN=HERE.parent/'run_no_risk_ceilings_once';BASE=HERE.parent.parent/'tech407_admission_mask_ablation_v1/run_all1709_once'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):
 with (HERE/(n+'.json')).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def csvsave(n,rows):
 with (HERE/(n+'.csv')).open('x') as f:
  if rows:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def verify(p):
 status=read(p/'RUN_STATUS.json');assert status['status']=='COMPLETED_RESOURCE_PASS'
 assert sha(p/'OUTPUT_SEAL.json')==status['output_seal_sha256']
 for n,h in read(p/'OUTPUT_SEAL.json').items():assert sha(p/n)==h,(p,n)
 return status
status=verify(RUN);base_status=verify(BASE)
nd={x['day'][:10]:x for x in read(RUN/'DAY_LEDGER.json')};bd={x['day'][:10]:x for x in read(BASE/'DAY_LEDGER.json')}
archives=read(RUN/'ARCHIVES.json');actions=read(RUN/'ACTIONS.json');audit=read(RUN/'AUDIT.json');decisions=read(RUN/'DECISIONS.json')
rows=[]
for day in ['2024-09-02','2024-09-19','2024-09-23','2024-09-24','2024-10-08','2024-10-31']:
 for arm,ds in [('old_all1709',bd),('no_risk_ceilings',nd)]:
  x=ds[day]['CLOSE'];nav=D(x['NAV']);anchor=D(ds['2024-09-23']['CLOSE']['NAV']);rows.append(dict(day=day,arm=arm,NAV=nav,cash=x['cash'],gross_inventory=x['gross_inventory'],receivable=x['receivable'],stock_weight_pct=D(x['gross_inventory'])/nav*100,seed_return_pct=(nav/D(1200000)-1)*100,sep23_close_return_pct=(nav/anchor-1)*100,certified=x['certified']))
csvsave('KEY_DATE_COMPARISON',rows)
sectorrows=[];holdrows=[]
for day in ['2024-09-19','2024-09-23','2024-09-24']:
 x=read(RUN/('CHECKPOINT_'+day+'.json'));snap=x['snapshot'];nav=D(snap['nav']);sector=collections.defaultdict(lambda:D(0));hold=collections.defaultdict(lambda:dict(q=0,value=D(0)))
 for h in snap['holdings']:
  st=x['archives'][h['round_id']];val=D(h['mark'])*h['qty'];sector[st['industry']]+=val
  z=hold[h['sid']];z.update(name=st['name'],industry=st['industry']);z['q']+=h['qty'];z['value']+=val
 for industry,value in sector.items():sectorrows.append(dict(day=day,industry=industry,value=value,weight_pct=value/nav*100))
 for sid,h in hold.items():holdrows.append(dict(day=day,sid=sid,**h,weight_pct=h['value']/nav*100))
csvsave('CHECKPOINT_SECTORS',sectorrows);csvsave('CHECKPOINT_HOLDINGS',holdrows)
trades=[dict(day=a['day'],sid=a['sid'],name=archives[a['round_id']]['name'],industry=archives[a['round_id']]['industry'],side=a['side'],q=a['q'],price=a['price'],fee=a['fee'],round_id=a['round_id']) for a in actions if a['day']<='2024-10-31']
csvsave('TRADES_THROUGH_OCTOBER',trades)
rejects=[];summ=[]
for a in audit:
 if a['type']=='BUDGET_REJECTED':
  reasons=sorted({r for t in a['trials'] for r in t['reasons']});assert not set(reasons)&{'probe_risk','sector_risk','round_fee_inclusive_risk'}
  st=archives[a['round_id']];rejects.append(dict(day=a['day'][:10],sid=st['sid'],name=st['name'],industry=st['industry'],kind=a['kind'],reasons='|'.join(reasons),before_shared_q=a['before_shared_q'],minimum_buy_quantity=a['minimum_buy_quantity']))
for day in ['2024-09-19','2024-09-23','2024-09-24']:
 rr=[r for r in rejects if r['day']==day];counts=collections.Counter(z for r in rr for z in r['reasons'].split('|'))
 summ.append(dict(day=day,rejected=len(rr),reason_counts=dict(counts),actual_INIT=sum(a['day']==day and a['side']=='buy_core' for a in actions),actual_ADD=sum(a['day']==day and a['side']=='buy_add' for a in actions)))
csvsave('ALL_CAPITAL_REJECTIONS',rejects)
def stats(rows,pnlkey,returnkey,buykey):
 ps=[D(x[pnlkey]) for x in rows];rs=[D(x[returnkey]) for x in rows];wins=[x for x in ps if x>0];loss=[x for x in ps if x<0]
 return dict(n=len(rows),positive=len(wins),negative=len(loss),flat=sum(x==0 for x in ps),win_pct=D(len(wins))/D(len(rows))*100 if rows else None,total_fee_net_pnl=sum(ps,D(0)),total_buy_cash=sum((D(x[buykey]) for x in rows),D(0)),mean_return_pct=sum(rs,D(0))/D(len(rs))*100 if rs else None,amount_payoff_ratio=(sum(wins)/len(wins))/(-sum(loss)/len(loss)) if wins and loss else None,tail_ge30_count=sum(r>=D('.30') for r in rs))
complete=[]
for label,p in [('old_all1709',BASE),('no_risk_ceilings',RUN)]:
 rounds=read(p/'ROUND_REPORT.json');layers=read(p/'LAYER_REPORT.json');closed=[x for x in rounds if x['status']=='EXECUTION_AND_SETTLEMENT_CLOSED']
 entry=dict(arm=label,round_statuses=dict(collections.Counter(x['status'] for x in rounds)),whole_round_closed=stats(closed,'whole_round_NET80','conditional_return_on_actual_buy_cash','whole_round_actual_buy_cash'),layers={})
 for kind in sorted({x['layer'] for x in layers}):
  closedlayers=[x for x in layers if x['layer']==kind and x['execution_closed'] and x['settlement_closed']];entry['layers'][kind]=stats(closedlayers,'NET80','return_on_layer_buy_cash','buy_cash')
 complete.append(entry)
# Requested interval is fully certified in both OPEN and CLOSE, not just endpoints.
for label,ds in [('old',bd),('new',nd)]:
 for day,x in ds.items():
  if day<='2024-10-31':assert x['CLOSE']['certified'] and (x['OPEN'] is None or x['OPEN']['certified']),(label,day)
result=read(RUN/'RESULT.json')
save('SUMMARY',dict(status='SEALED_OUTPUTS_VERIFIED_ANALYSIS_COMPLETE_PENDING_INDEPENDENT_OUTCOME_REVIEW',resource=status,baseline_resource=base_status,key_dates=rows,rejections=summ,complete_rounds_and_layers=complete,first_uncertified=result['first_uncertified'],terminal=result['final_reconciliation'],certified_through_october=True,limitations=['Conditional observed OPEN +/-5bp proxy, not live executability proof.','No R1/CP repair and no changes to source universe/signals or original input evidence.','All monetary risk ceilings removed; original capital ceilings remain.','No full-lifecycle account return: two owned UNKNOWN positions remain.','Whole-round/layer closed outcomes are supplemental; not a substitute for Sep23-to-Oct8 account return.']))
save('ANALYSIS_SEAL',{str(p):sha(p) for p in [*HERE.glob('*.csv'),HERE/'SUMMARY.json',HERE/'postprocess.py',RUN/'OUTPUT_SEAL.json',BASE/'OUTPUT_SEAL.json']})
print(json.dumps({'directory':str(HERE),'summary_sha256':sha(HERE/'SUMMARY.json'),'completed':complete,'rejection_summary':summ},ensure_ascii=False,default=str))
