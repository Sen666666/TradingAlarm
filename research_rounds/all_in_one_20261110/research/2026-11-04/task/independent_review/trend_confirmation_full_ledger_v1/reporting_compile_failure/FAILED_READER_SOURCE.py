"""One saved-output aggregation: native period denominators, fixed924, observed flag join.
No account, signal, price-feature or CA model is run.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,csv,gzip,importlib.util
O=Path(__file__).resolve().parent;T=O.parents[1];AN=T/'trend_confirmation_outcome_analysis_v1';Z=D(0);ARMS=['B','UNIFORM50','A_ONLY','A_OR_B']
s=importlib.util.spec_from_file_location('pure_saved_native_reader',O/'generic_saved_finance_reader.py');R=importlib.util.module_from_spec(s);s.loader.exec_module(R)
def day(x):return str(x)[:10]
def csvread(p):R.SRC[str(p.resolve())]=R.sha(p);return list(csv.DictReader(p.open()))
def flow_cash(b,cut=None):
 out=defaultdict(lambda:Z)
 for t in b['trades']:
  if cut and day(t['at'])>cut:continue
  if t['side']=='buy':out[t['layer']]-=D(t['gross_cny'])+D(t['fees_cny'])
  else:
   for p in t['parts']:out[p['layer']]+=D(p['net_cash'])
 return out
flags={};support=defaultdict(set);roles=defaultdict(set);reports={};postgroups={};Bbook=None;Blongdaily=None
for win,n in [('long',726),('strong',242)]:
 root=T/'trend_confirmation_native_v1'/('full-'+win+'-v1');out=AN/('full_'+win+'_v1');summary=R.read(out/'SUMMARY.json');ph=R.read(out/'FIXED_PHASE_WEALTH.json');periods=csvread(out/'ALL_YEARS.csv')+csvread(out/'ALL_MONTHS.csv');daily=R.rows(root/'pair/daily.jsonl.gz');ep=root/'pair/confirmation-size-events.jsonl.gz';R.SRC[str(ep.resolve())]=R.sha(ep);counts=defaultdict(Counter);zeros=defaultdict(Counter)
 with gzip.open(ep,'rt')as f:
  for line in f:
   e=json.loads(line);arm=e['account'];counts[arm][e['result']]+=1
   if e['result']=='confirmation_half_below_minimum':zeros[arm][e['role']]+=1
   if win=='long'and arm in ('A_ONLY','A_OR_B'):
    k=day(e['at']),e['sid'];v={z:e['flags'].get(z)for z in ('A','B','A_known','B_known','price_known')}
    if k in flags:assert flags[k]==v,('same sid/day flags differ',k)
    flags[k]=v;support[k].add(arm);roles[k].add(e['role'])
 reports[win]={}
 for arm in ARMS:
  b=R.book(root/'pair'/(arm+'.json.gz'));dd=[d for d in daily if d['account']==arm];assert len(dd)==n;byday={day(d['at']):d for d in dd};idx={day(d['at']):i for i,d in enumerate(dd)};pr=[r for r in periods if r['arm']==arm];months=[r for r in pr if r['grain']=='month'];assert len(months)==(36 if win=='long'else12)
  for r in pr:
   rr=[d for d in dd if day(d['at']).startswith(r['period'])];assert len(rr)==int(r['days'])and day(rr[0]['at'])==r['start']and day(rr[-1]['at'])==r['end'];pos=idx[r['start']];begin=D(dd[pos-1]['nav'])if pos else D(1000000);end=D(rr[-1]['nav']);wealth=end-begin
   R.near(begin,r['initial_own_NAV'],'period own starting equity');R.near(end,r['end_NAV'],'periodend');R.near(wealth,r['wealth_change'],'period wealth');R.near((end/begin-1)*100,r['return_pct'],'own denominator return')
   ts=[t for t in b['trades']if r['start']<=day(t['at'])<=r['end']];buys=[t for t in ts if t['side']=='buy'];sells=[t for t in ts if t['side']=='sell'];assert len(buys)==int(r['buy_fills'])and len(sells)==int(r['sell_fills'])
   R.near(sum((D(t['fees_cny'])for t in ts),Z),r['actual_fees'],'period actual fees');R.near(sum((D(t['gross_cny'])+D(t['fees_cny'])for t in buys),Z),r['actual_buy_cash'],'periodbuycash');R.near(sum((D(t['gross_cny'])-D(t['fees_cny'])for t in sells),Z),r['actual_sell_net'],'periodsellnet')
  R.near(sum((D(r['wealth_change'])for r in months),Z),D(dd[-1]['nav'])-D(1000000),'monthly telescope')
  lag=[Z]+[D(d['inventory'])/D(d['nav'])*100 for d in dd[:-1]];lagmean=sum(lag,Z)/D(n);whole=summary[arm]['whole_calendar'];R.near(lagmean,whole['mean_lag_exposure_pct'],'lag uses n execution days incl first0')
  held=[sum(bool(q)for q in d['positions'].values())for d in dd];p=summary[arm]['actual_positions'];R.near(D(sum(held))/D(n),p['mean_held_stocks'],'mean actual holdings');assert max(held)==p['max_held_stocks']and len({t['security_id']for t in b['trades']if t['side']=='buy'})==p['unique_actual_bought_stocks'];assert p['lag_exposure_denominator']==n and p['lag_exposure_includes_initial_empty_close']is True
  metrics=summary[arm]['account_metrics'];bc=sum(t['side']=='buy'for t in b['trades']);sc=len(b['trades'])-bc;assert bc==metrics['buy_fills']and sc==metrics['sell_fills'];R.near(sum((D(t['fees_cny'])for t in b['trades']),Z),metrics['fees'],'wholeactualfees');assert dict(counts[arm])==summary[arm]['plan_event_counts']['result'];assert sum(counts[arm].values())==summary[arm]['plan_event_counts']['total'];assert dict(zeros[arm])==summary[arm]['plan_event_counts']['minlot_zero_by_role']
  reports[win][arm]=dict(period_rows_checked=len(pr),monthly_rows_checked=len(months),mean_lag_exposure_pct=str(lagmean),mean_held_stocks=str(D(sum(held))/D(n)),max_held_stocks=max(held),unique_actual_bought_stocks=p['unique_actual_bought_stocks'],buy_fills=bc,sell_fills=sc,fees=metrics['fees'],actual_drop_below_minimum_events=dict(zeros[arm]))
  if win=='long':
   bound=byday['2024-10-08'];active={l['id']:l for l in bound['layers']};cash=flow_cash(b);groups=defaultdict(lambda:dict(layers=0,wealth=Z))
   for l in b['layers']:
    R.near(cash[l['id']],l['cash'],'layer cash from actual parts');net=D(l['cash'])+D(l['dividend'])+(D(l['qty'])*R.mark(l['sid'],dd[-1]['at'])if l['qty']else Z)
    if day(l['opened'])>'2024-10-08':g='new_fill_after_boundary';before=Z
    elif l['id']in active:
     g='actually_held_at_boundary';x=active[l['id']];before=D(x['cash'])+D(x['dividend'])+D(x['qty'])*R.mark(l['sid'],bound['at'])
    else:g='already_closed_at_boundary';before=net
    groups[g]['layers']+=1;groups[g]['wealth']+=net-before
   R.near(sum((g['wealth']for g in groups.values()),Z),D(dd[-1]['nav'])-D(bound['nav']),'post924nativewealth')
   for g,v in groups.items():assert v['layers']==ph[arm]['post924_old_vs_new_layers']['groups'][g]['layers'];R.near(v['wealth'],ph[arm]['post924_old_vs_new_layers']['groups'][g]['wealth'],'fixedcohort')
   for name in ['924_six_closes','post924']:
    p=ph[arm][name];rr=[d for d in dd if p['start']<=day(d['at'])<=p['end']];prev=idx[day(rr[0]['at'])]-1;startnav=D(dd[prev]['nav'])if prev>=0else D(1000000);delta=D(rr[-1]['nav'])-startnav;R.near(delta,p['interval_wealth'],'fixed924interval');R.near(startnav,p['account_own_NAV_period']['initial_own_NAV'],'fixedphase own denominator');R.near((D(rr[-1]['nav'])/startnav-1)*100,p['account_own_NAV_period']['return_pct'],'fixedphase own return')
   postgroups[arm]={g:dict(layers=v['layers'],wealth=str(v['wealth']))for g,v in groups.items()}
   if arm=='B':Bbook=b;Blongdaily=byday
# Main failed-buy coverage: join only existing other-arm same sid/day feature logs.
cov=R.read(AN/'ORIGINAL_B_BUY_CONFIRMATION_COVERAGE.json');assert len(flags)==cov['existing_observed_sid_days'];assert R.sha(T/'trend_confirmation_native_v1/full-long-v1/pair/B.json.gz')==cov['source_book_sha256'];tx={t['layer']:t for t in Bbook['trades']if t['side']=='buy'};bydetail={(r['cohort'],r['layer']):r for r in cov['detail']};cashcuts={c:flow_cash(Bbook,c)for c in ['2023-12-29','2024-12-31']};coverage={}
for cohort,lo,hi,cut,expectedn in [('entry2022_2023_through2023','2022-01-04','2023-12-29','2023-12-29',1557),('post924_new303_through2024','2024-10-09','2024-12-31','2024-12-31',303)]:
 active={l['id']:l for l in Blongdaily[cut]['layers']};groups=defaultdict(lambda:dict(actual_buy_layers=0,actual_buy_cash=Z,actual_buy_gross=Z,contribution_through_cutoff=Z,negative_layer_contribution=Z,positive_layer_contribution=Z,negative_layers=0,positive_layers=0,open_at_cutoff_layers=0));selected=[l for l in Bbook['layers']if lo<=day(l['opened'])<=hi];assert len(selected)==expectedn
 for l in selected:
  lid=l['id'];t=tx[lid];signalday=day(t['signal_at']);meta=Bbook['metadata'][str(lid)];bo=meta['budget_order'];label,at,sid,role=bo.split('|');assert label=='B'and day(at)==signalday and sid==l['sid'];k=signalday,sid;v=flags.get(k)
  if v is None:g='UNMATCHED_existing_modifier_log'
  elif v['A_known']and v['A']is True:g='A_TRUE'
  elif v['A_known']and v['A']is False and v['B_known']and v['B']is True:g='A_FALSE_B_ONLY_TRUE'
  elif v['A_known']and v['A']is False and v['B_known']and v['B']is False:g='A_FALSE_B_FALSE'
  else:g='UNKNOWN_A_OR_B'
  if lid in active:x=active[lid];net=D(x['cash'])+D(x['dividend'])+D(x['qty'])*R.mark(sid,Blongdaily[cut]['at']);isopen=bool(x['qty']);R.near(cashcuts[cut][lid],x['cash'],'cutoffactualcash')
  else:assert l['closed']and day(l['closed'])<=cut;net=cashcuts[cut][lid]+D(l['dividend']);isopen=False;R.near(cashcuts[cut][lid],l['cash'],'no futureexitcash at cutoff')
  r=bydetail[cohort,lid];assert r['sid']==sid and r['signal_day']==signalday and r['role']==role and r['group']==g and r['flags']==v;assert r['support_accounts']==sorted(support[k])and r['exact_same_role_flag_observed']==(role in roles[k]);R.near(net,r['contribution_through_cutoff'],'coverage layercontribution');buycash=D(t['gross_cny'])+D(t['fees_cny']);R.near(buycash,r['actual_buy_cash'],'coverage actualbuyfee')
  z=groups[g];z['actual_buy_layers']+=1;z['actual_buy_cash']+=buycash;z['actual_buy_gross']+=D(t['gross_cny']);z['contribution_through_cutoff']+=net;z['open_at_cutoff_layers']+=isopen
  if net<0:z['negative_layer_contribution']+=net;z['negative_layers']+=1
  elif net>0:z['positive_layer_contribution']+=net;z['positive_layers']+=1
 for g,v in groups.items():
  for name,val in v.items():R.near(val,cov['totals'][cohort]['groups'][g][name],'coverage group '+g+name)
 total=sum((v['contribution_through_cutoff']for v in groups.values()),Z);R.near(total,cov['totals'][cohort]['total_contribution'],'cohorttotal');assert sum(v['actual_buy_layers']for v in groups.values())==expectedn
 if cut=='2023-12-29':R.near(total,D(Blongdaily[cut]['nav'])-D(1000000),'full1557motherbody NAV')
 else:R.near(total,postgroups['B']['new_fill_after_boundary']['wealth'],'fullstrict303postbridge')
 coverage[cohort]={g:{k:str(vv)if isinstance(vv,D)else vv for k,vv in v.items()}for g,v in groups.items()}
x={'status':'PASS_SAVED_DERIVED_PERIOD_DENOMINATOR_FIXED924_AND_ORIGINAL_B_COVERAGE','period_and_reporting':reports,'fixed_post924_old_new_native_layer_bridges':postgroups,'original_B_buy_confirmation_coverage':coverage,'original_B_existing_flag_sid_days':len(flags),'new_feature_or_signal_calculations':0,'new_account_events':0,'scope':'Actual frozen pandas classifications matched to original B fills; association only, not avoided-loss or realizable deletion counterfactual. Unmatched/unknown retained. Source strict20-key37m FAIL remains separately recorded.','source_sha256':R.SRC,'checker_sha256':R.sha(__file__)}
p=O/'DERIVED_PERIODS_924_AND_COVERAGE_AUDIT.json';p.write_text(json.dumps(x,indent=2)+'\n');print(p,R.sha(p));print(json.dumps(coverage))
