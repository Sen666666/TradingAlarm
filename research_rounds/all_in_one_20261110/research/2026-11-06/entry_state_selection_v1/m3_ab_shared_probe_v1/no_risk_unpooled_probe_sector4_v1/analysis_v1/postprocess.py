from pathlib import Path
from decimal import Decimal as D
import json,csv,collections,hashlib
HERE=Path(__file__).resolve().parent;B=HERE.parent.parent
RUN=HERE.parent/'run_unpooled_probe_sector4_once';BASE=B/'no_risk_ceilings_python_retry_v1/run_no_risk_ceilings_once';OLD=B/'tech407_admission_mask_ablation_v1/run_all1709_once'
DATES=['2024-09-19','2024-09-23','2024-09-24','2024-09-30','2024-10-08','2024-10-31']
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,x):
 with (HERE/(n+'.json')).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2,default=str)
def csvsave(n,rows):
 with (HERE/(n+'.csv')).open('x') as f:
  if rows:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def verify(p):
 s=read(p/'RUN_STATUS.json');assert s['status']=='COMPLETED_RESOURCE_PASS';assert sha(p/'OUTPUT_SEAL.json')==s['output_seal_sha256']
 for n,h in read(p/'OUTPUT_SEAL.json').items():assert sha(p/n)==h,(p,n)
 return s
def dd(points):
 peak=points[0][1];peakday=points[0][0];worst=D(0);a=z=peakday
 for day,val in points:
  if val>peak:peak=val;peakday=day
  drop=val/peak-1
  if drop<worst:worst=drop;a=peakday;z=day
 return worst*100,a,z
comparison=[];resources={};proof={}
for arm,p in [('original_risk_caps',OLD),('no_risk_baseline',BASE),('capital_combo',RUN)]:
 resources[arm]=verify(p);ds={x['day'][:10]:x for x in read(p/'DAY_LEDGER.json')};actions=read(p/'ACTIONS.json');anchor=D(ds['2024-09-23']['CLOSE']['NAV'])
 for day,x in ds.items():
  if day<='2024-10-31':assert x['CLOSE']['certified'] and (x['OPEN'] is None or x['OPEN']['certified']),(arm,day)
 for day in DATES:
  x=ds[day]['CLOSE'];nav=D(x['NAV']);points=[('SEED',D(1200000))]+[(d,D(r['CLOSE']['NAV'])) for d,r in ds.items() if d<=day];mdd,peak,trough=dd(points)
  sub=[(d,D(r['CLOSE']['NAV'])) for d,r in ds.items() if '2024-09-23'<=d<=day];postdd=dd(sub)[0] if sub else None
  comparison.append(dict(arm=arm,day=day,NAV=nav,cash=x['cash'],gross_inventory=x['gross_inventory'],receivable=x['receivable'],stock_weight_pct=D(x['gross_inventory'])/nav*100,seed_pnl=nav-D(1200000),seed_return_pct=(nav/D(1200000)-1)*100,sep23_return_pct=(nav/anchor-1)*100 if day>='2024-09-23' else None,seed_close_max_drawdown_pct=mdd,drawdown_peak=peak,drawdown_trough=trough,sep23_close_max_drawdown_pct=postdd,cumulative_actual_fees=sum((D(str(a['fee'])) for a in actions if a['day']<=day),D(0)),certified=True))
 proof[arm]=dict(all_open_close_certified_through_oct31=True,source_event_signature=read(p/'RESULT.json')['source_event_signature'])
assert len({p['source_event_signature'] for p in proof.values()})==1
csvsave('KEY_DATE_COMPARISON',comparison)
sectors=[];holds=[];concentration=[]
for day in DATES:
 x=read(RUN/('CHECKPOINT_'+day+'.json'));s=x['snapshot'];nav=D(s['nav']);sec=collections.defaultdict(lambda:D(0));stocks={}
 for h in s['holdings']:
  st=x['archives'][h['round_id']];v=D(h['mark'])*h['qty'];sec[st['industry']]+=v
  z=stocks.setdefault(h['sid'],dict(name=st['name'],industry=st['industry'],q=0,value=D(0)));z['q']+=h['qty'];z['value']+=v
 ranked=sorted(sec.items(),key=lambda v:-v[1]);concentration.append(dict(day=day,held_stocks=len(stocks),held_industries=len(sec),largest_industry=ranked[0][0],largest_weight_pct=ranked[0][1]/nav*100,top5_industry_weight_pct=sum((v for k,v in ranked[:5]),D(0))/nav*100))
 for industry,v in ranked:sectors.append(dict(day=day,industry=industry,value=v,weight_pct=v/nav*100))
 for sid,z in stocks.items():holds.append(dict(day=day,sid=sid,**z,weight_pct=z['value']/nav*100))
csvsave('CHECKPOINT_SECTORS',sectors);csvsave('CHECKPOINT_HOLDINGS',holds);csvsave('CONCENTRATION',concentration)
archives=read(RUN/'ARCHIVES.json');actions=read(RUN/'ACTIONS.json');audit=read(RUN/'AUDIT.json');reject=[];rejsum=[]
for a in audit:
 if a['type']=='BUDGET_REJECTED':
  rr=sorted({r for t in a['trials'] for r in t['reasons']});assert not set(rr)&{'probe_risk','sector_risk','round_fee_inclusive_risk','pool_capital'}
  st=archives[a['round_id']];reject.append(dict(day=a['day'][:10],sid=st['sid'],name=st['name'],industry=st['industry'],kind=a['kind'],reasons='|'.join(rr),before_shared_q=a['before_shared_q']))
for day in DATES:
 rs=[r for r in reject if r['day']==day];rejsum.append(dict(day=day,rejected=len(rs),reason_counts=dict(collections.Counter(x for r in rs for x in r['reasons'].split('|'))),new_INIT=sum(a['day']==day and a['side']=='buy_core' for a in actions),new_ADD=sum(a['day']==day and a['side']=='buy_add' for a in actions)))
csvsave('ALL_REJECTIONS',reject)
trades=[dict(day=a['day'],sid=a['sid'],name=archives[a['round_id']]['name'],industry=archives[a['round_id']]['industry'],side=a['side'],q=a['q'],price=a['price'],fee=a['fee'],round_id=a['round_id']) for a in actions if a['day']<='2024-10-31'];csvsave('TRADES_THROUGH_OCTOBER',trades)
r=read(RUN/'RESULT.json');unknown=[dict(x,name=archives[x['round_id']]['name']) for x in r['final_reconciliation']['unknown']]
save('SUMMARY',dict(status='SEALED_ANALYSIS_PENDING_INDEPENDENT_OUTCOME_REVIEW',comparison=comparison,resources=resources,path_certification=proof,concentration=concentration,rejections=rejsum,first_uncertified=r['first_uncertified'],terminal_unknown=unknown,account_action_counts=r['action_counts'],report_counts=r['reports'],limitations=['Combined capital policy effect only; no separate attribution to pool/industry changes.','No hindsight selections: all original 6878 births, original signals and order priority.','CLOSE-to-CLOSE drawdown with seed; not intraday drawdown.','Industry4% is new-probe admission threshold, confirmed10% and mark changes allow observed industry>4%.','Cash reserve is prior daily planning NAV at reservation; close cash/NAV can be below10% without violation.','Observed OPEN +/-5bp conditional proxy, not certified live executions.','All requested six checkpoints and intervening phases certified; no complete-lifecycle account return after owned UNKNOWN.']))
save('ANALYSIS_SEAL',{str(p):sha(p) for p in [HERE/'postprocess.py',HERE/'SUMMARY.json',*HERE.glob('*.csv'),RUN/'OUTPUT_SEAL.json',BASE/'OUTPUT_SEAL.json',OLD/'OUTPUT_SEAL.json']})
print(json.dumps(dict(directory=str(HERE),summary_hash=sha(HERE/'SUMMARY.json'),analysis_seal_hash=sha(HERE/'ANALYSIS_SEAL.json'),new_comparison=[x for x in comparison if x['arm']=='capital_combo'],baseline_key=[x for x in comparison if x['arm']=='no_risk_baseline' and x['day'] in ['2024-09-23','2024-10-08','2024-10-31']],rejections=rejsum,unknown=unknown,resource=resources['capital_combo']),ensure_ascii=False,default=str))
