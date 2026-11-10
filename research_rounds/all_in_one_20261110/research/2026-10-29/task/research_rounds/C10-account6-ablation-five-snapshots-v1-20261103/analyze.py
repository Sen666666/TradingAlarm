"""Join completed static plans to old observations; never feeds the solver."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip,hashlib,csv
O=Path(__file__).resolve().parent;R=O.parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 f=read(O/'AUTHORIZATION_AND_FREEZE.json');meta_path=R/'g-s-C-AugSep-continuation-readiness-20261102/inputs/metadata.json';meta=read(meta_path)
 label_path=R/'opportunity-quality-ranking-20261031/2025_26/PRICE_LABELS.jsonl.gz';labels={}
 with gzip.open(label_path,'rt') as stream:
  for line in stream:
   z=json.loads(line)
   if z['day'] in f['dates']:labels[z['sid'],z['day'],z['receipt']]=z['labels']
 layers_path=R/'g-s-C-August-continuation-v1-20261102/analysis/C10-LAYERS.json';layers=read(layers_path)
 by_signal=defaultdict(list);by_stock=defaultdict(list)
 for z in layers:by_signal[z['sid'],z['signal_at'][:10]].append(z);by_stock[z['sid']].append(z)
 sectors=read(R/'g-s-C-month-continuation-20261102/july_end_analysis/MARKET_SECTORS.json');sn={z['sector']:z['name'] for z in sectors}
 results=[];flat=[];identity=[]
 for day in f['dates']:
  x=read(O/('INPUT-'+day+'.json'));v=x['trusted'];s=v['snapshot'];ds={d['sid']:d for d in v['demands']};lots={z['id']:z for z in s['lots']};before=read(O/('ORIGINAL_6-'+day+'.json'));after=read(O/('NO_AR6-'+day+'.json'));a=before['result'];b=after['result'];modes={}
  for name,r in [('ORIGINAL_6',a),('NO_AR6',b)]:
   cap=defaultdict(lambda:D(0));risk=defaultdict(lambda:D(0));stockcap=defaultdict(lambda:D(0))
   for z in s['rows']:cap[z['sector']]+=D(z['capital']);risk[z['sector']]+=D(z['risk']);stockcap[z['sid']]+=D(z['capital'])
   for z in r['donors']['rows']:
    lot=lots[z['layer']];q=z['q'];cap[lot['sector']]-=D(q)*D(lot['mark']);risk[lot['sector']]-=D(z['risk_release']);stockcap[lot['sid']]-=D(q)*D(lot['mark'])
   for sid,q in r['Q'].items():
    d=ds[sid];cap[d['sector']]+=D(q)*D(d['mark']);risk[d['sector']]+=D(q)*max(D(0),D(d['mark'])-D(d['floor']));stockcap[sid]+=D(q)*D(d['mark'])
   term=r['validation']['terminal'];nav=D(term['nav'])
   assert abs(sum(cap.values(),D(0))-D(term['capital']))<D('1e-15')
   assert abs(sum(risk.values(),D(0))-D(term['risk']))<D('1e-15')
   industry=sorted([dict(sector=sec,name=sn.get(sec,sec),capital=str(value),nominal_risk=str(risk[sec]),capital_pct=float(value/nav*100),risk_pct=float(risk[sec]/nav*100)) for sec,value in cap.items() if value],key=lambda z:-D(z['capital']))
   buys=sum((D(q)*D(ds[sid]['mark'])*D('1.0005') for sid,q in r['Q'].items()),D(0));sells=sum((D(z['capital']) for z in r['donors']['rows']),D(0));net=sum((D(z['net']) for z in r['donors']['rows']),D(0))
   modes[name]=dict(Q_positive=sum(q>0 for q in r['Q'].values()),D_positive=len(r['D']),new_buy_gross=str(buys),D_mark_gross=str(sells),D_estimated_net=str(net),
    nominal_risk=str(term['risk']),nominal_risk_pct=float(D(term['risk'])/nav*100),capital=str(term['capital']),capital_pct=float(D(term['capital'])/nav*100),
    conditional_available=str(term['available']),conditional_cash_pct=float(D(term['available'])/nav*100),industry=industry,
    stock_weights=[dict(sid=sid,name=meta[sid]['name'],capital=str(value),weight_pct=float(value/nav*100)) for sid,value in sorted(stockcap.items(),key=lambda z:-z[1]) if value],
    risk6_observed_negative_residuals=sum(D(z['residual'])<0 for z in r['validation']['checks'] if z['constraint']=='account_risk6'))
  changes=[]
  for sid in a['Q']:
   if a['Q'][sid]==b['Q'][sid]:continue
   d=ds[sid];lab=labels.get((sid,day,d['receipt_id']));actual=by_signal.get((sid,day),[])
   z=dict(day=day,sid=sid,name=meta[sid]['name'],sector=d['sector'],sector_name=sn.get(d['sector'],d['sector']),use=d['use'],old_Q=a['Q'][sid],new_Q=b['Q'][sid],raw_max=d['max_q'],
    original_priority=d['priority'],decision_price=d['mark'],actual_floor=d['floor'],receipt=d['receipt_id'],
    label_status='exact_sid_day_canonical_receipt' if lab else 'N_A_not_in_old_market_qualified_label_mother',original_price_labels=lab,
    original_actual_same_signal_layers=[{k:t[k] for k in ['layer','role','pool','purpose','initial_qty','buy_gross','realized_trade_PNL','unrealized_net_buy_cost','total_contribution']} for t in actual],
    original_full_window_stock_contribution=str(sum((D(t['total_contribution']) for t in by_stock.get(sid,[])),D(0))),
    contribution_scope='original C10 July-August observation, not this new hypothetical risk or signal return',
    original_trace=next(t for t in a['trace'] if t['sid']==sid),ablation_trace=next(t for t in b['trace'] if t['sid']==sid))
   changes.append(z);flat.append(z)
  donor_changes=[]
  for sid in sorted(set(a['D'])|set(b['D'])):
   if a['D'].get(sid,0)==b['D'].get(sid,0):continue
   donor_changes.append(dict(sid=sid,name=meta[sid]['name'],old_D=a['D'].get(sid,0),new_D=b['D'].get(sid,0),
    same_original_held_stock_context=True,original_full_window_stock_contribution=str(sum((D(t['total_contribution']) for t in by_stock.get(sid,[])),D(0))),not_a_hold_counterfactual=True))
  focus={}
  for sid in ['000425.SZ','600031.SH','601100.SH','000680.SZ','603338.SH','603516.SH','300308.SZ','600410.SH']:
   if sid not in ds and sid not in a['D'] and sid not in b['D']:continue
   focus[sid]=dict(name=meta[sid]['name'],old_Q=a['Q'].get(sid),new_Q=b['Q'].get(sid),old_D=a['D'].get(sid,0),new_D=b['D'].get(sid,0),
    ablation_trace=next((t for t in b['trace'] if t['sid']==sid),None))
  results.append(dict(day=day,full_C_candidates=len(ds),original_zero_Q_included=True,modes=modes,Q_changes=changes,D_changes=donor_changes,focus=focus,
    original_mode_full_identity=before['original_full_identity'],financial_events=0))
 save(O/'SUMMARY.json',dict(cases=results,changes=flat,new_price_labels=0,financial_events=0,not_continuous_PNL=True,
   label_source_sha256=sha(label_path),label_reuse_only=True,strict_join_no_missing_imputation=True,
   changed_events=len(flat),changed_events_with_existing21_labels=sum(bool(z['original_price_labels']) for z in flat)))
 with (O/'ALL_Q_CHANGES.csv').open('w') as stream:
  writer=csv.writer(stream);writer.writerow(['day','sid','name','sector','old_Q','new_Q','raw_max','decision_price','floor','label21_pct','label63_pct','original_C10_stock_JulAug_contribution_NOT_counterfactual'])
  for z in flat:
   lab=z['original_price_labels'] or {};writer.writerow([z[k] for k in ['day','sid','name','sector_name','old_Q','new_Q','raw_max','decision_price','actual_floor']]+[lab.get(str(h),{}).get('return_pct') for h in [21,63]]+[z['original_full_window_stock_contribution']])
 save(O/'ANALYSIS_SOURCE_BINDING.json',dict(only_after_projection=True,sources={str(p.resolve()):sha(p) for p in [meta_path,label_path,layers_path]},
  output_plan_hashes={p.name:sha(p) for p in sorted(O.glob('NO_AR6-*.json'))},new_price_labels=0,new_selection_outcomes=0))
 print('SUMMARY_READY',len(flat),'changed event rows;',sum(bool(z['original_price_labels']) for z in flat),'old exact label matches')
if __name__=='__main__':main()
