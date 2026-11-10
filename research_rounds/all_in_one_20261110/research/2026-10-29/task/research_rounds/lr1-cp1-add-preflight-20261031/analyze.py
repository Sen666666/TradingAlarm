"""Read saved paths only. Original independent ledger audit + exact P&L bridge."""
import adapter as M
from run_stage import rows,obj
from pathlib import Path
from decimal import Decimal as D
import time,json,collections,gzip,sys
import numpy as np,pandas as pd
Z=D(0);O=M.O
def metrics(ds):
 nav=np.array([float(x['nav']) for x in ds]);mv=np.array([float(x['inventory']) for x in ds]);peak=np.maximum.accumulate(np.r_[1e6,nav])[1:];dd=1-nav/peak
 longest=0;lastpeak=0;peakv=1e6;episodes=[];start=None;maxobs=0
 for i,v in enumerate(nav):
  if v>=peakv:
   if start is not None:episodes.append(dict(start=ds[lastpeak]['at'][:10],recovery=ds[i]['at'][:10],observations=i-lastpeak,censored=False))
   peakv=v;lastpeak=i;start=None
  else:
   if start is None:start=i
   maxobs=max(maxobs,i-lastpeak)
 if start is not None:episodes.append(dict(start=ds[lastpeak]['at'][:10],recovery=None,observations=len(ds)-1-lastpeak,censored=True))
 for x in episodes:x['calendar_days']=(pd.Timestamp(x['recovery'] or ds[-1]['at'][:10])-pd.Timestamp(x['start'])).days
 return dict(net_return=float(nav[-1]/1e6-1),max_drawdown=float(dd.max()),longest_underwater_observations=maxobs,longest_underwater_calendar_days=max([x['calendar_days'] for x in episodes],default=0),underwater_at_end=bool(nav[-1]<peak[-1]),mean_exposure=float((mv/nav).mean()),mean_available_fraction=float(np.mean([float(x['available'])/n for x,n in zip(ds,nav)])),episodes=episodes)
def main():
 sec=sys.argv[1];root=O/sec/'full';assert M.read(root/'GATE.json')['passed'];data=rows(root/'results/daily.jsonl.gz');repair=O/sec/'repair-full'
 if repair.exists():
  assert M.read(repair/'GATE.json')['passed'];data=[x for x in data if x['account']!='ADD_delay1']+rows(repair/'results/daily.jsonl.gz')
 meta_path=M.RR/('tech-compound-design-20261026/proposed-pool.csv' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/pool.csv');meta=pd.read_csv(meta_path).set_index('symbol').to_dict('index')
 au=M.BP.C.import_path('add_independent_audit',M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py');prices=au.Prices.__new__(au.Prices);prep=Path(M.read(root/'results/META.json')['prep']);manifest=M.RR/'pvr-act-comparison-20261027/input/manifest.json' if sec=='TECH' else prep/'manifest.json';prices.records={x['series_id']:x for x in M.read(manifest)['series']};prices.cache={}
 rules=M.read(root/'execution-rules-v2.json');calendar=sorted({pd.Timestamp(x) for x in rules['calendars']['A']}|{pd.Timestamp(f'2026-10-{d}T09:30:00+08:00') for d in ['27','28','29','30']})
 summary=[];campaigns=[];stocks=[];layers=[];contributions=[];audits=[];risku=[];ops=[];structures=[];admission=[];allobjects={}
 for name in M.read(root/'results/META.json')['paths']:
  source=repair/'results' if name=='ADD_delay1' and repair.exists() else root/'results';ob=obj(source/f'{name}.json.gz');allobjects[name]=ob;ds=[x for x in data if x['account']==name]
  contrib=[];cs,receipt=au.audit_account('B0_'+name,dict(audit_log=ob['audit']),ds,prices,meta,calendar,contrib);receipt['account']=name;audits.append(receipt)
  for c in cs:c['account']=name;campaigns.append(c)
  for c in contrib:c['account']=name;contributions.append(c)
  rr=metrics(ds);rr.pop('episodes');pnl=Z;kind=collections.defaultdict(lambda:Z);groups=collections.defaultdict(lambda:dict(cost=Z,net=Z,fees=Z,buys=0,final_shares=0))
  for z in ob['layers']:
   mark=prices.mark(z['sid'],'2026-10-27');net=D(z['cash'])+D(z['dividend'])+z['qty']*mark;pnl+=net;kind[z['kind']]+=net
   layers.append(dict(sector=sec,account=name,layer=z['id'],symbol=z['sid'],name=meta[z['sid']]['name'],kind=z['kind'],net_profit=float(net),final_shares=z['qty'],opened=z['opened'],closed=z['closed'],reason=z['reason']))
   g=ob['layer_structures'][str(z['id'])];groups[g]['net']+=net;groups[g]['buys']+=1;groups[g]['final_shares']+=z['qty']
  assert abs(pnl-(D(ds[-1]['nav'])-D(1_000_000)))<D('.00000001'),(name,'layer attribution')
  trade_to_layer={t['receipt_id']:t.get('layer') for t in ob['trades'] if t['side']=='buy'}
  for t in ob['trades']:
   if t['side']=='buy':
    g=ob['layer_structures'][str(t['layer'])];groups[g]['cost']+=D(t['gross_cny'])+D(t['fees_cny']);groups[g]['fees']+=D(t['fees_cny'])
   else:
    for p in t['parts']:
     g=ob['layer_structures'][str(p['layer'])];groups[g]['fees']+=D(t['fees_cny'])*D(p['shares'])/t['shares']
  for g,d in groups.items():structures.append(dict(sector=sec,account=name,structure=g,**{k:float(v) if isinstance(v,D) else v for k,v in d.items()},**ob['structure_risk'].get(g,{})))
  lr=[z for z in layers if z['account']==name];risk=pd.DataFrame(ob['risk_rows']);ops.extend(dict(sector=sec,account=name,**x) for x in ob['ops'])
  for sid in meta:
   cc=[c for c in cs if c['symbol']==sid];stocks.append(dict(sector=sec,account=name,symbol=sid,name=meta[sid]['name'],industry=meta[sid]['industry'],net_profit=float(sum((c['net_pnl'] for c in cc),Z)),cycles=len(cc)))
  slip=sum((D(t['shares'])*abs(D(t['price'])-D(t['raw_open'])) for t in ob['trades']),Z)
  rr.update(sector=sec,account=name,final_nav=float(ds[-1]['nav']),fees=float(ds[-1]['fees_cny']),slippage=float(slip),buy_fills=sum(t['side']=='buy' for t in ob['trades']),add_fills=sum(t['side']=='buy' and t['kind']=='add' for t in ob['trades']),cycles=len(cs),open_cycles=sum(not c['closed'] for c in cs),all_negative_cycle_loss=float(-sum((c['net_pnl'] for c in cs if c['net_pnl']<0),Z)),tail30_closed_profit=float(sum((c['net_pnl'] for c in cs if c['closed'] and c['net_return'] is not None and c['net_return']>=.3),Z)),ordinary_closed_profit=float(sum((c['net_pnl'] for c in cs if c['closed'] and (c['net_return'] is None or c['net_return']<.3)),Z)),open_profit=float(sum((c['net_pnl'] for c in cs if not c['closed']),Z)),core_profit=float(kind['core']),add_profit=float(kind['add']),negative_add_layers_loss=-sum(z['net_profit'] for z in lr if z['kind']=='add' and z['net_profit']<0),negative_add_layers=sum(z['kind']=='add' and z['net_profit']<0 for z in lr),add_layers=sum(z['kind']=='add' for z in lr),max_stock_weight=receipt['max_stock_weight'],max_sector_weight=receipt['max_sector_weight'],max_nominal_to_floor_rate=float(risk.nominal_rate.astype(float).max()),mean_nominal_to_floor_rate=float(risk.nominal_rate.astype(float).mean()),max_active_structure_positive_capital_loss=float(risk.active_structure_positive_capital_loss.astype(float).max()),floor_unknown_layer_days=int(risk.unknown_floor_layers.sum()),price_unknown_position_days=int(risk.price_or_observation_unknown_positions.sum()),floor_crossed_layer_days=int(risk.at_or_below_floor_layers.sum()),credit_created=sum(x['kind']=='ADD_credit_created' for x in ob['ops']),credit_consumed=sum(x['kind']=='ADD_credit_consumed' for x in ob['ops']))
  for x in ob['risk_rows']:risku.append(dict(sector=sec,account=name,**x))
  funding=collections.defaultdict(dict)
  for x in ob['audit']:
   if x['kind']=='lot_risk_funded':funding[x['signal_at']][x['sid']]=x['shares']
  for d in ob['decisions']:
   ints=d['intents'];funded=funding[d['at']]
   for i in ints:admission.append(dict(sector=sec,account=name,decision=d['at'],sid=i['sid'],kind=i['kind'],group=i['group'],weight=i['weight'],budget=i['budget'],cap=i['cap'],size_reject=i.get('size_reject'),funded_shares=funded.get(i['sid'],0)))
  summary.append(rr);print(sec,name,'audited',rr['net_return'],rr['max_drawdown'],rr['add_fills'],flush=True)
 out=O/sec/'analysis';out.mkdir(exist_ok=False)
 for n,x in [('summary',summary),('campaigns',campaigns),('stocks',stocks),('layers',layers),('structures',structures),('risk',risku),('operations',ops),('intents',admission)]:pd.DataFrame(M.N.encoded(x)).to_csv(out/f'{n}.csv',index=False)
 with gzip.open(out/'stock-daily-contributions.jsonl.gz','wt',compresslevel=1) as f:
  for x in contributions:f.write(json.dumps(M.N.encoded(x))+'\n')
 bridge=[]
 for stress in ['base','cost2','delay1']:
  a={x['symbol']:x['net_profit'] for x in stocks if x['account']=='L0_'+stress};b={x['symbol']:x['net_profit'] for x in stocks if x['account']=='ADD_'+stress}
  for sid in meta:bridge.append(dict(sector=sec,stress=stress,symbol=sid,name=meta[sid]['name'],baseline=a[sid],candidate=b[sid],difference=b[sid]-a[sid]))
  delta=sum(x['difference'] for x in bridge if x['stress']==stress);s0=next(x for x in summary if x['account']=='L0_'+stress);s1=next(x for x in summary if x['account']=='ADD_'+stress);assert abs(delta-(s1['final_nav']-s0['final_nav']))<.01
 pd.DataFrame(bridge).to_csv(out/'stock-bridge.csv',index=False);M.save(out/'ACCOUNTING.json',dict(passed=True,receipts=audits,layer_contribution_reconciled=True,stock_difference_bridge_reconciled=True,legacy_B0_prefix_only_skips_count_limits=True));M.save(out/'SUMMARY.json',summary)
 print('COMPLETE',sec,flush=True)
if __name__=='__main__':
 t=time.monotonic();main();prior=M.read(O/'COMPUTE_TIME.json');elapsed=time.monotonic()-t;prior['seconds']+=elapsed;prior['stages'].append(dict(sector=sys.argv[1],stage='independent_analysis',status='complete',seconds=elapsed));M.save(O/'COMPUTE_TIME.json',prior);print('ANALYSIS_SECONDS',elapsed,flush=True)
