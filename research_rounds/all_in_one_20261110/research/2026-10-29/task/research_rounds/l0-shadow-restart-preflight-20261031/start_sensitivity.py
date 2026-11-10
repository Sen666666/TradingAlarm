"""Four approved fixed normal starts; no parameter/date search."""
import shadow as S
from pathlib import Path
import sys,time,signal,traceback,inspect,gzip,json,shutil,collections
import numpy as np,pandas as pd
O=S.O;M=S.M;D=M.D
CASES={'HIST':dict(decision='2019-12-31',first='2020-01-02',end='2023-12-29',ref='l0-history-pressure-2019-2023-20261031'),
       'CURRENT':dict(decision='2024-12-31',first='2025-01-02',end='2026-10-27',ref='lr1-cp1-add-preflight-20261031')}
def read_rows(path):
 with gzip.open(path,'rt') as f:return [json.loads(x) for x in f]
def metrics(rows,initial):
 rows=M.N.encoded(rows)
 nav=np.array([float(x['nav']) for x in rows]);peak=np.maximum.accumulate(np.r_[float(initial),nav])[1:];dd=1-nav/peak
 last=rows[0]['at'][:10];pv=float(initial);maxdays=0
 for x,n in zip(rows,nav):
  if n>=pv:pv=n;last=x['at'][:10]
  maxdays=max(maxdays,(pd.Timestamp(x['at'][:10])-pd.Timestamp(last)).days)
 return dict(initial_nav=str(initial),final_nav=str(rows[-1]['nav']),net_return=float(D(str(rows[-1]['nav']))/D(str(initial))-1),max_drawdown=float(dd.max()),longest_underwater_calendar_days=maxdays,mean_exposure=float(np.mean([float(x['inventory'])/float(x['nav']) for x in rows])),mean_positions=float(np.mean([len(x['positions']) for x in rows])),peak_positions=max(len(x['positions']) for x in rows),observations=len(rows))
def finish_saved(period,sec,init=None,simulation=None):
 cfg=CASES[period];root=O/'sensitivity'/period/sec;data=read_rows(root/'results/daily.jsonl.gz');ob=json.load(gzip.open(root/'results/L0_base.json.gz','rt'));meta0=M.read(root/'results/META.json')
 au=M.BP.C.import_path('shadow_saved_independent_ledger',M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py');prices=au.Prices.__new__(au.Prices)
 manifest=M.RR/'pvr-act-comparison-20261027/input/manifest.json' if sec=='TECH' else Path(meta0['prep'])/'manifest.json';prices.records={x['series_id']:x for x in M.read(manifest)['series']};prices.cache={}
 pool=M.RR/('tech-compound-design-20261026/proposed-pool.csv' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/pool.csv');meta=pd.read_csv(pool).set_index('symbol').to_dict('index');rules=M.read(root/'execution-rules-v2.json');calendar=sorted({pd.Timestamp(x) for x in rules['calendars']['A']}|{pd.Timestamp(f'2026-10-{d}T09:30:00+08:00') for d in ['27','28','29','30']})
 cs,receipt=au.audit_account('B0_L0_base',dict(audit_log=ob['audit']),data,prices,meta,calendar,[])
 residual=sum((D(z['cash'])+D(z['dividend'])+(D(z['qty'])*prices.mark(z['sid'],cfg['end']) if z['qty'] else D(0)) for z in ob['layers']),D(0))-(D(data[-1]['nav'])-D(1000000));assert abs(residual)<D('.000001')
 extra=dict(layer_pnl_residual=str(residual),fees=data[-1]['fees_cny'],buy_fills=sum(t['side']=='buy' for t in ob['trades']),sell_fills=sum(t['side']=='sell' for t in ob['trades']),closed_cycles=sum(c['closed'] for c in cs),open_cycles=sum(not c['closed'] for c in cs),tail30_closed_contribution=str(sum((c['net_pnl'] for c in cs if c['tail_closed']),D(0))),ordinary_closed_contribution=str(sum((c['net_pnl'] for c in cs if c['closed'] and not c['tail_closed']),D(0))),open_contribution=str(sum((c['net_pnl'] for c in cs if not c['closed']),D(0))))
 ref=read_rows(O.parent/cfg['ref']/sec/'full/results/daily.jsonl.gz');suffix=[x for x in ref if x['account']=='L0_base' and cfg['decision']<=x['at'][:10]<=cfg['end']];assert suffix[0]['at'][:10]==cfg['decision'];assert [x['at'][:10] for x in data]==[x['at'][:10] for x in suffix]
 new=metrics(data,D(1000000));inherited=metrics(suffix,D(suffix[0]['nav']));first=suffix[0]
 M.save(root/'GATE.json',dict(passed=True,independent_NAV_audit=receipt,layer_accounting=extra,input_time_warmup_unchanged=True,new_empty_account=True,all_fill_dates_within_window=all(cfg['first']<=t['at'][:10]<=cfg['end'] for t in ob['trades']),only_L0_normal=True,simulation_seconds=simulation,initialization_seconds=init,read_only_postprocessing=True))
 M.save(root/'COMPARISON.json',dict(period=period,sector=sec,config=cfg,fresh=new,inherited_matched_suffix=inherited,return_difference_percentage_points=100*(new['net_return']-inherited['net_return']),DD_difference_percentage_points=100*(new['max_drawdown']-inherited['max_drawdown']),inherited_start=dict(nav=first['nav'],cash=first['available'],stocks=len(first['positions']),ACT_on=first['on'],pending_sells=len(first['pending_sells']),pending_intents=first['pending_intents']),fresh_trading=extra,ACT_events=[x for x in ob['audit'] if x['kind']=='risk_checkpoint' and x.get('event')],initialization_effect_is_not_single_causal_component=True))
 print(period,sec,'RESULT',new,'INHERITED',inherited,flush=True)
def audit(r,root,sec,rows,end):
 au=M.BP.C.import_path('shadow_sensitivity_independent_ledger',M.RR/'rs-h1-execution-20261025/code/analyze_accounts.py');prices=au.Prices.__new__(au.Prices)
 manifest=M.RR/'pvr-act-comparison-20261027/input/manifest.json' if sec=='TECH' else r.prep/'manifest.json'
 prices.records={x['series_id']:x for x in M.read(manifest)['series']};prices.cache={}
 pool=M.RR/('tech-compound-design-20261026/proposed-pool.csv' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/pool.csv');meta=pd.read_csv(pool).set_index('symbol').to_dict('index')
 calendar=sorted({pd.Timestamp(x) for x in r.market.rules['calendars']['A']});a=r.accounts['L0_base'];cs,receipt=au.audit_account('B0_L0_base',dict(audit_log=M.N.encoded(a.audit_log)),M.N.encoded(rows),prices,meta,calendar,[])
 residual=sum((z['cash']+z['dividend']+(D(z['qty'])*r.market.latest_mark(z['sid'],M.N.iso(end+'T15:10:00+08:00')).raw_price if z['qty'] else D(0)) for z in a.layers),D(0))-(a.current_nav-D(1000000));assert abs(residual)<D('.000001'),residual
 assert all(t['kind']=='core' for t in a.trades if t['side']=='buy') and not a.ops and not a.cp_used
 return receipt,dict(layer_pnl_residual=str(residual),fees=str(a.fees_cny),buy_fills=sum(t['side']=='buy' for t in a.trades),sell_fills=sum(t['side']=='sell' for t in a.trades),closed_layers=sum(not z['qty'] for z in a.layers),open_layers=sum(bool(z['qty']) for z in a.layers),tail30_closed_contribution=float(sum((z['cash']+z['dividend'] for z in a.layers if not z['qty'] and z['cash']+z['dividend']>=-next(t['gross_cny']+t['fees_cny'] for t in a.trades if t['side']=='buy' and t['layer']==z['id'])*D('-.3')),D(0))))
def main(period,sec):
 assert M.read(O/'ENGINEERING_GATE.json')['passed'];cfg=CASES[period];root=O/'sensitivity'/period/sec;root.mkdir(parents=True,exist_ok=False)
 prior=M.read(O/'SENSITIVITY_COMPUTE.json') if (O/'SENSITIVITY_COMPUTE.json').exists() else dict(seconds=0,stages=[]);left=180-prior['seconds'];assert left>0
 start=time.monotonic();status='failed';r=None;signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('four fixed starts total180s')));signal.setitimer(signal.ITIMER_REAL,left)
 try:
  freeze=M.read(O/'SENSITIVITY_FREEZE.json');assert freeze['wrapper_sha']==S.sha(__file__) and freeze['state_wrapper_sha']==S.sha(O/'shadow.py')
  old=M.read(O.parent/'lr1-cp1-add-preflight-20261031/FREEZE.json');assert all(S.sha(p)==h for p,h in old['sha256'].items())
  source=inspect.getsource(M.BP.Pilot.run);assert source.count('2023-12-29T15:10:00+08:00')==1
  source=source.replace('2023-12-29T15:10:00+08:00',cfg['decision']+'T15:10:00+08:00');env=dict(M.BP.__dict__);exec(source.strip(),env)
  class Run(M.Pilot):run=env['run']
  shutil.copyfile(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json')
  r=Run(sec,root,stresses=['base'],policies=['L0']);init=time.monotonic()-start
  assert all(not a.positions and not a.buys and not a.exits and not a.core_epoch and a.available==D(1000000) for a in r.accounts.values());sim=time.monotonic();r.run(cfg['end']);simulation=time.monotonic()-sim
  assert min(str(t['at'])[:10] for a in r.accounts.values() for t in a.trades)>=cfg['first']
  M.dump(r,root/'results');finish_saved(period,sec,init,simulation);status='complete'
 except BaseException as e:
  M.save(root/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()))
  if r is not None and not (root/'results').exists():M.dump(r,root/'failed-results')
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-start;prior['seconds']+=elapsed;prior['stages'].append(dict(period=period,sector=sec,status=status,seconds=elapsed));M.save(O/'SENSITIVITY_COMPUTE.json',prior);print('TIMING',period,sec,status,elapsed,'TOTAL',prior['seconds'],flush=True)
if __name__=='__main__':main(*sys.argv[1:3])
