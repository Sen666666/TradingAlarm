"""Exactly one C1 path per approved window; old Bdiag books read, never rerun."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,time,gc,argparse,importlib.util
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'execution-pressure-preflight-20261031'));from initialization_guard import IO,initialize
def read(p):return json.loads(Path(p).read_text())
def obj(p):
 with gzip.open(p,'rt') as h:return json.load(h)
def rows(p):
 with gzip.open(p,'rt') as h:return [json.loads(x) for x in h]
def equal_old_files(C,root,old):
 assert obj(root/'B.json.gz')==obj(old/'B.json.gz'),'fixed60 old real book differs'
 for name in ['daily','opportunities','funding','industry','balances']:assert rows(root/(name+'.jsonl.gz'))==rows(old/(name+'.jsonl.gz')),('fixed60 old stream differs',name)
def quick(out):
 b=obj(out/'pair/B.json.gz');ds=rows(out/'pair/daily.jsonl.gz');navs=[D(1000000)]+[D(x['nav']) for x in ds];peak=navs[0];dd=D(0)
 for n in navs:peak=max(peak,n);dd=max(dd,1-n/peak)
 c=obj_json(out/'pair/C1.json');cs=c['decisions'];bridges=rows(out/'pair/balances.jsonl.gz');assert len(ds)==len(cs)==len(bridges)==242
 assert all(D(x['independent_NAV_difference'])==0 and D(str(x['maximum_stock_quantity_difference']))==0 for x in bridges)
 result=dict(return_pct=str((navs[-1]/D(1000000)-1)*100),DD_pct=str(dd*100),mean_exposure_pct=str(sum((D(x['inventory'])/D(x['nav'])*100 for x in ds),D(0))/len(ds)),peak_exposure_pct=str(max(D(x['inventory'])/D(x['nav'])*100 for x in ds)),fees=str(sum((D(x['fees_cny']) for x in b['trades']),D(0))),buy_fills=sum(t['side']=='buy' for t in b['trades']),sell_fills=sum(t['side']=='sell' for t in b['trades']),paused_closes=sum(not x['on'] for x in ds),over_cap_closes=sum(x['over_cap'] for x in cs),c_min=min(float(x['fraction']) for x in cs),H_end=cs[-1]['high'],c_end=cs[-1]['fraction'],daily_journal_NAV_and_quantity_zero=True)
 IO.write_json(out/'QUICK_RESULT.json',result);print('ECONOMIC_RESULT',json.dumps(result),flush=True)
def obj_json(p):return json.loads(Path(p).read_text())
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--window',choices=['2022','2025_26'],required=True);args=parser.parse_args();out=O/'runs'/args.window
 assert not (out/'DONE.json').exists(),'completed C1 path must not rerun'
 C=initialize(lambda:__import__('adapter_c1'),out,'load_C1_adapter');J,L=C.J,C.L
 assert read(O/'SYNTHETIC_GATE.json')['passed']
 if args.window=='2022':
  def year_module():
   p=W/'2022-normal-reference-20261031/adapter.py';s=importlib.util.spec_from_file_location('C1_frozen2022_input_only',p);a=importlib.util.module_from_spec(s);sys.modules[s.name]=a;s.loader.exec_module(a);return a
  Y=initialize(year_module,out,'load_original2022_input_wrapper');start='2022-01-01';end='2022-12-30';cut='2022-01-10';old=W/'2022-normal-reference-20261031/runs/B_diag/short-Jan10/pair'
  def inputs():
   original_save=Y.save
   try:
    Y.save=lambda p,x:IO.write_json(out/'input-readiness'/Path(p).name,J.W.canon(x));return Y.inputs()
   finally:Y.save=original_save
  extra=[Path(Y.__file__),W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'2022-normal-reference-20261031/inputs/COMPLETION.json']
 else:
  start='2025-07-01';end='2026-06-30';cut='2025-07-07';old=W/'account-risk-ablation-20261031/run/prefix-full-source/pair'
  inputs=lambda:C.E.inputs('universe');extra=[Path(C.E.__file__)]
 J.START=start;J.END=end
 begun=time.monotonic();shared,receipts,cp,states,ir,identity=initialize(inputs,out,'read_frozen_inputs_no_regeneration');print('INPUTS_READY',args.window,round(time.monotonic()-begun,2),flush=True)
 kw=dict(stock_cp=cp,industry_states=states,industry_receipts=ir)
 sources=[Path(__file__),Path(C.__file__),O/'CONTRACT.txt',O/'test_c1.py',J.O/'joint_v3.py',J.BASE/'budget_v3/model.py',C.BASE.O/'adapter.py',C.BASE.O/'model_without_account_check.py',C.BASE.O/'route_without_account_check.py',Path(L.__file__),W/'_shared/research_output_io.py',L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',J.M.O/'recovery.csv',J.M.P/'h1.npz']+extra
 freeze={str(p):L.sha(p) for p in sources};IO.write_json(out/'FREEZE.json',dict(before_events=True,window=[start,end],initial_cash=1000000,identity=identity,sources=freeze,baseline_not_rerun=True,C1_only=True,normal=True,R1=False,new_stage=False))
 # Gate fixed60 uses only a short technical prefix and compares already saved
 # baseline economic objects. The old Bdiag account is never initialized/run.
 fixed=initialize(lambda:C.Runner(shared,receipts,mode='fixed60',**kw),out,'fixed60_gate_object');fixed.source_freeze=dict(freeze)
 g=time.monotonic()
 with IO.atomic_runner_outputs(fixed,L,out,canonicalize=J.W.canon):assert fixed.run_prepared(out/'fixed60-prefix',120,end=cut)
 equal_old_files(C,out/'fixed60-prefix/pair',old);print('FIXED60_IDENTICAL',args.window,round(time.monotonic()-g,2),flush=True)
 del fixed;gc.collect()
 r=initialize(lambda:C.Runner(shared,receipts,**kw),out,'fresh1m_C1');r.source_freeze=dict(freeze)
 t=time.monotonic()
 with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out/'prefix-full-source',120,end=cut)
 segment_seconds=r.run_seconds
 restored=initialize(lambda:C.Runner(shared,receipts,**kw),out,'same_C1_identity_restart');restored.source_freeze=dict(freeze)
 at=J.M.N.iso(cut+'T15:10:00+08:00')
 with IO.atomic_runner_outputs(restored,L,out,canonicalize=J.W.canon):assert restored.restore(out/'prefix-full-source/checkpoint.pkl')==at
 assert C.E.equal(C.E.observable(r),C.E.observable(restored)),'C1 restart economic/controller state differs'
 physical=J.W.physical(shared,cut);physical_kw=dict(stock_cp={s:f.loc[:cut] for s,f in cp.items()},industry_states={s:[x for x in z if x['day']<=cut] for s,z in states.items()},industry_receipts={k:x for k,x in ir.items() if x['confirmed_day']<=cut})
 prefix=initialize(lambda:C.Runner(physical,{s:{d:x for d,x in z.items() if d<=cut} for s,z in receipts.items()},**physical_kw),out,'physical_C1_prefix');prefix.source_freeze=dict(freeze)
 with IO.atomic_runner_outputs(prefix,L,out,canonicalize=J.W.canon):assert prefix.run_prepared(out/'prefix-physical-source',120,end=cut)
 assert C.E.equal(C.E.observable(r),C.E.observable(prefix)),'C1 physical prefix differs'
 estimate=segment_seconds*242/len(r.daily)
 IO.write_json(out/'GATES.json',dict(passed=True,fixed60_matches_saved_old_books_and_five_streams=True,restart_all_state_equal=True,identity_guard_enabled=True,physical_prefix_equal=True,source_contract_only_change_confirmed_fraction=True,short_segment_seconds=segment_seconds,linear_242day_replay_estimate_seconds=estimate,gate_wall_seconds=time.monotonic()-g))
 print('GATES_PASS',args.window,'first_segment',round(segment_seconds,2),'full_linear_estimate',round(estimate,2),'prior_global_H',str(r.accounts['B'].budget.c1.high),flush=True)
 del r,prefix;gc.collect();r=restored;t=time.monotonic()
 with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,420,resume_after=at,end=end)
 IO.write_json(out/'TIMING.json',dict(completed=done,load_seconds=time.monotonic()-begun,continuation_seconds=time.monotonic()-t,first_segment_reused_not_restarted=True))
 if not done:print('SAVED_AT_BUDGET',out,flush=True);return
 assert all(L.sha(p)==h for p,h in freeze.items()),'frozen source/input changed during C1'
 quick(out);print('COMPLETE',args.window,round(time.monotonic()-begun,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as error:
  IO.write_json(O/'failure/ENTRY_ERROR.json',dict(action='approved C1 fixed-window normal only',type=type(error).__name__,reason=str(error)));raise
