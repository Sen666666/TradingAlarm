"""Prepare immutable full schema or execute only with separate exact root grant."""
from pathlib import Path
import argparse,ast,gzip,hashlib,inspect,json,time,traceback
import full_adapter as F
import inputs_reuse as I
from market_info_v2 import MarketInfo
C,A,N,J,L,IO=F.C,F.A,F.N,F.J,F.L,F.IO
O=Path(__file__).resolve().parent;T=O.parent
WINDOWS={'long':('2022-01-01','2022-01-04','2024-12-31',726,['2021-12-30','2021-12-31']), 'strong':('2025-07-01','2025-07-01','2026-06-30',242,['2025-06-27','2025-06-30'])}
HISTORY={'long':T/'benchmark_2022_2023/continuation2024/inputs/510300_history.csv','strong':T/'capacity_cost_guard_analysis_v1/benchmark_B_2025_26/inputs/510300_history.csv'}
GATES=[T/'market_gross_admission_technical_review_v1/SMALL_TECHNICAL_REVIEW_GATE.json',T/'market_gross_admission_small_ledger_review_v1/FINAL_SMALL_LEDGER_REVIEW.json']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):IO.write_json(p,J.W.canon(x))
def immutable(p,x):
 value=J.W.canon(x)
 if p.exists():assert read(p)==value,('prepared artifact changed',str(p))
 else:save(p,value)
def rows(p):
 with gzip.open(p,'rt')as f:return[json.loads(x)for x in f]
def binding(window):return O/'bindings'/('long-year-dispatch-v2'if window=='long'else'strong-single-source-v2')/'COMBINED_SCORE_BINDING.json'
def calendar(window):
 native_start,start,end,days,warm=WINDOWS[window];root=T/'capacity_cost_guard_v1/runs'/f'{window}-v1';path=root/'arms/B/pair/daily.jsonl.gz'
 ds=rows(path);assert len(ds)==days and ds[0]['at'][:10]==start and ds[-1]['at'][:10]==end
 return dict(source='original native full calendar, every CLOSE independent of ACT/trades',source_path=str(path),source_sha256=sha(path),warm_dates=warm,closes=[d+'T15:10:00+08:00'for d in warm]+[r['at']for r in ds],full_start=start,full_end=end)
def score_ast():
 tree=ast.parse(Path(N.__file__).read_text());nodes=[v for v in tree.body if isinstance(v,(ast.FunctionDef,ast.ClassDef))and v.name in('FrozenScores','priority_plan','apply_priority')]
 return hashlib.sha256(ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False).encode()).hexdigest()
def manifest(window):
 p=O/'prepared'/window;native_start,start,end,days,warm=WINDOWS[window];b=binding(window);assert b.is_file(),'reuse actual private binding from completed small'
 files=[O/'PROTOCOL.txt',O/'FULL_PREPARATION_PROTOCOL.txt',O/'gross_adapter.py',O/'market_info.py',O/'market_info_v2.py',O/'inputs_reuse.py',O/'full_adapter.py',Path(__file__),I.SOURCE,b,HISTORY[window],p/'EXPECTED_CLOSE_CALENDAR.json',p/'MARKET_INFO_FULL_CLOCKS.json',O/'ARCHIVED_B_CONTROL_BINDING.json']+GATES
 for name in('balance','_fee','_remember_fees'):files.append(Path(inspect.getsourcefile(getattr(J.Account,name))))
 mother=A.source_freeze();sources=dict(mother)
 for y in(('2022','2023','2024')if window=='long'else('strong',)):
  files.append(I.SCORE_PATHS[y])
  if y in I.YEARS:files.append(I.YEARS[y][0])
 sources.update({str(f.resolve()):sha(f)for f in files})
 archived=read(O/'ARCHIVED_B_CONTROL_BINDING.json')[window]
 for q,h in archived['source_sha256'].items():assert sha(q)==h
 control_sources=read(T/'capacity_cost_guard_v1/runs'/f'{window}-v1/STARTED.json')['sources']
 for q,h in mother.items():assert q in control_sources and control_sources[q]==h,('No60 mother source differs from archived B',q)
 return dict(scope='FULL_MARKET_GROSS_ADMISSION_CANDIDATE_ONLY',window=window,executed_arms=['D_GROSS10'],archived_B_only_xref=archived,initial_CNY='1000000',native_clock_start=native_start,full_start=start,fixed_end=end,closes=days,own_state_continuous_no_year_reset=True,market_gross_alpha='.10',old_ACT20_BREAK63=True,provider='market_info_v2.MarketInfo',expected_calendar=str((p/'EXPECTED_CLOSE_CALENDAR.json').resolve()),stored_info_path=str(HISTORY[window]),private_score_binding=dict(path=str(b),sha256=sha(b)),score_helper_AST_sha256=score_ast(),mother_original_sources_exact_to_archived_control=len(mother),sources=sources,financial_control_rerun=False,cost_guard_or_new_ledger=False)
def prepare(window):
 p=O/'prepared'/window;p.mkdir(parents=True,exist_ok=True);cal=calendar(window);immutable(p/'EXPECTED_CLOSE_CALENDAR.json',cal)
 info=MarketInfo(HISTORY[window],cal['closes']);v=[]
 for close in cal['closes'][2:]:
  day=close[:10]
  for phase in('09:30:00','15:10:00'):
   at=J.M.N.iso(day+'T'+phase+'+08:00');r=info.state(at);assert r['state']!='UNKNOWN'and r['available_at']<=at
   assert phase!='09:30:00'or r['day']<day
   v.append(dict(at=at,**r))
 immutable(p/'MARKET_INFO_FULL_CLOCKS.json',dict(passed=True,expected_calendar_sha256=sha(p/'EXPECTED_CLOSE_CALENDAR.json'),source_history_sha256=info.sha256,all_scheduled_OPEN_CLOSE=v,new_accounts=0))
 m=manifest(window);immutable(p/'FULL_SOURCE_MANIFEST.json',m)
 proposal=dict(approved=False,scope=m['scope'],window=window,source_manifest_SHA256=sha(p/'FULL_SOURCE_MANIFEST.json'),small_gate_SHA256={str(q):sha(q)for q in GATES},preparation_has_no_account_events=True)
 if not(p/'PROPOSED_FULL_AUTHORIZATION.json').exists():save(p/'PROPOSED_FULL_AUTHORIZATION.json',proposal)
 print('PREPARED_NO_ACCOUNTS',window,sha(p/'FULL_SOURCE_MANIFEST.json'),flush=True)
def execute(args):
 # Reject before any load/Account initialization when grant absent or stale.
 assert args.authorization is not None,'separate root full grant required'
 p=O/'prepared'/args.window;prepared=read(p/'FULL_SOURCE_MANIFEST.json');assert manifest(args.window)==prepared
 grant=read(args.authorization);assert grant['approved']is True and grant['scope']==prepared['scope']and grant['window']==args.window
 assert grant['source_manifest_SHA256']==sha(p/'FULL_SOURCE_MANIFEST.json')
 assert grant['small_gate_SHA256']=={str(q):sha(q)for q in GATES}
 out=args.out.resolve();assert str(out).startswith(str(O.resolve())+'/')and not(out/'STARTED.json').exists()
 out.mkdir(parents=True);save(out/'STARTED.json',dict(full_schema=prepared,authorization=str(args.authorization.resolve()),authorization_sha256=sha(args.authorization),resume=str(args.resume)if args.resume else None))
 I.configure_scores(args.window,out);assert N.SCORES.manifest_sha256==prepared['private_score_binding']['sha256']
 begin=time.monotonic();shared,receipts,cp,states,ir,identity=I.load_long(out)if args.window=='long'else I.load_strong(out)
 native_start,start,end,days,warm=WINDOWS[args.window];cal=read(p/'EXPECTED_CLOSE_CALENDAR.json')
 actual=[str(x)for x in shared[1].cutoffs if warm[0]<=str(x.date())<=end];expected=[str(J.M.N.iso(x))for x in cal['closes']];assert actual==expected,'original native input calendar differs'
 info=MarketInfo(HISTORY[args.window],cal['closes']);J.START,J.END=native_start,end
 runner=F.Runner(shared,receipts,info=info,fixed_end=end,**A.S.kwargs(cp,states,ir));runner.source_freeze=dict(prepared['sources']);save(out/'INPUT_IDENTITY.json',identity);loaded=time.monotonic()
 with IO.atomic_runner_outputs(runner,L,out,canonicalize=J.W.canon):
  cursor=runner.restore(args.resume)if args.resume else None
  done=runner.run_prepared(out,args.seconds,resume_after=cursor,end=end)
 assert all(sha(q)==h for q,h in prepared['sources'].items())
 save(out/'TIMING.json',dict(completed=done,input_seconds=loaded-begin,total_seconds=time.monotonic()-begin,event_seconds=getattr(runner,'run_seconds',None)))
 if done:
  assert len(runner.daily)==days;save(out/'WINDOW_RESULT.json',dict(passed=True,days=days,executed_arms=['D_GROSS10'],archived_control_xref=prepared['archived_B_only_xref'],ending_NAV=str(runner.accounts['D_GROSS10'].current_nav),source_post_exact=True))
 print('FULL_SAVED'if done else'CHECKPOINTED_NO_AUTOMATIC_RESUME',args.window,flush=True)
def main():
 p=argparse.ArgumentParser();m=p.add_mutually_exclusive_group(required=True);m.add_argument('--prepare-only',action='store_true');m.add_argument('--execute',action='store_true');p.add_argument('--window',choices=WINDOWS,required=True);p.add_argument('--out',type=Path);p.add_argument('--authorization',type=Path);p.add_argument('--resume',type=Path);p.add_argument('--seconds',type=int,default=3600);args=p.parse_args()
 if args.prepare_only:prepare(args.window)
 else:assert args.out is not None;execute(args)
if __name__=='__main__':
 try:main()
 except BaseException:print(traceback.format_exc());raise
