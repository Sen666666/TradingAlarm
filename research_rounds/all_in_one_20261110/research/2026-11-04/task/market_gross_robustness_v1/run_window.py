"""Freeze four fixed robustness jobs; full execution requires an exact root grant."""
from pathlib import Path
import argparse,ast,gzip,hashlib,importlib.util,json,time,traceback
import full_adapter as F
from ma_provider import MarketInfo

R,A,N,J,L,IO,K=F.R,F.A,F.N,F.J,F.L,F.IO,F.K
O=Path(__file__).resolve().parent;T=O.parent
# This is the actual input wrapper consumed by the completed small runs. Use
# an explicit unique module identity rather than ambiguous sys.path imports.
INPUT_WRAPPER=T/'market_gross_admission_native_v1/inputs_reuse.py'
spec=importlib.util.spec_from_file_location('robust_full_original_gross_inputs',INPUT_WRAPPER)
I=importlib.util.module_from_spec(spec);spec.loader.exec_module(I)
WINDOWS={'long':('2022-01-01','2022-01-04','2024-12-31',726,['2021-12-30','2021-12-31']),
         'strong':('2025-07-01','2025-07-01','2026-06-30',242,['2025-06-27','2025-06-30'])}
HISTORY={'long':T/'benchmark_2022_2023/continuation2024/inputs/510300_history.csv',
         'strong':T/'capacity_cost_guard_analysis_v1/benchmark_B_2025_26/inputs/510300_history.csv'}
LOGIC_GATE=T/'market_gross_robustness_logic_review_v1/SOURCE_CLOCK_SMALL_TECHNICAL_GATE.json'
PATH_PROOF=T/'market_gross_robustness_logic_review_v1/STRONG_ALPHA5_20_ARCHIVED_PATH_BOUND.json'
RULES=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):IO.write_json(p,J.W.canon(x))
def immutable(p,x):
 value=J.W.canon(x)
 if p.exists():assert read(p)==value,('prepared artifact changed',str(p))
 else:save(p,value)
def binding(window):return I.O/'bindings'/('long-year-dispatch-v2'if window=='long'else'strong-single-source-v2')/'COMBINED_SCORE_BINDING.json'
def score_ast():
 tree=ast.parse(Path(N.__file__).read_text())
 nodes=[v for v in tree.body if isinstance(v,(ast.FunctionDef,ast.ClassDef))and v.name in('FrozenScores','priority_plan','apply_priority')]
 return hashlib.sha256(ast.dump(ast.Module(body=nodes,type_ignores=[]),include_attributes=False).encode()).hexdigest()
def calendar(window):
 p=T/f'market_gross_admission_native_v1/prepared/{window}/EXPECTED_CLOSE_CALENDAR.json'
 cal=read(p);_,start,end,days,warm=WINDOWS[window]
 assert len(cal['closes'])==days+len(warm)and cal['full_start']==start and cal['full_end']==end
 assert[at[:10]for at in cal['closes'][:2]]==warm
 assert sha(cal['source_path'])==cal['source_sha256']
 return dict(cal,previous_reviewed_calendar_path=str(p),previous_reviewed_calendar_SHA256=sha(p))
def archive_binding(window):
 native_start,start,end,days,_=WINDOWS[window]
 old=T/'market_gross_admission_native_v1'
 b=read(old/'ARCHIVED_B_CONTROL_BINDING.json')[window]
 for q,h in b['source_sha256'].items():assert sha(q)==h
 d=old/f'full-{window}-v1'
 files=[d/'pair'/n for n in('D_GROSS10.json.gz','daily.jsonl.gz','balances.jsonl.gz')]
 files +=[d/'STARTED.json',d/'DONE.json',d/'WINDOW_RESULT.json',old/'prepared'/window/'FULL_SOURCE_MANIFEST.json']
 mother=A.source_freeze();control_sources=read(T/f'capacity_cost_guard_v1/runs/{window}-v1/STARTED.json')['sources']
 for q,h in mother.items():assert control_sources.get(q)==h,('archived mother source differs',q)
 return dict(window=window,initial_CNY='1000000',native_clock_start=native_start,full_start=start,fixed_end=end,closes=days,
             B_cost1_reference_only=b,D63_G10_cost1_reference_only=dict(root=str(d),source_sha256={str(p):sha(p)for p in files}),
             score_helper_AST_SHA256=score_ast(),mother_original_source_SHA256_exact=mother,
             no_archived_account_replay_or_synthetic_book=True)
def manifest(job,finance_gate):
 cfg=F.JOBS[job];window,family=cfg['window'],cfg['family'];p=O/'prepared-full-v1'/job
 native_start,start,end,days,warm=WINDOWS[window];b=binding(window)
 assert b.is_file()and finance_gate.is_file()
 gates=[LOGIC_GATE,finance_gate]
 assert all(read(q).get('passed')is True or read(q).get('status')=='PASS'for q in gates),'both final small gates required'
 files=[O/'PROTOCOL.txt',O/'FULL_PREPARATION_PROTOCOL.txt',O/'robust_adapter.py',O/'cost15_compat.py',O/'ma_provider.py',
        O/'full_adapter.py',Path(__file__),Path(I.__file__),I.SOURCE,b,HISTORY[window],RULES,
        O/'MA63_RECOMPUTE_CHECK.json',O/'COST15_PURE_CHECKS.json',PATH_PROOF,
        T/'market_gross_robustness_logic_review_v1/SMALL_ACTUAL_INPUT_WRAPPER_IDENTITY_ERRATUM.json',
        p/'EXPECTED_CLOSE_CALENDAR.json',p/'MARKET_INFO_FULL_CLOCKS.json',p/'ARCHIVED_BASELINE_BINDING.json']+gates
 files +=[T/'market_gross_admission_native_v1'/n for n in('gross_adapter.py','market_info.py','market_info_v2.py')]
 files +=[Path(q)for q in K.source_receipt()['stored_original_source_SHA256']]
 for y in(('2022','2023','2024')if window=='long'else('strong',)):
  files.append(I.SCORE_PATHS[y])
  if y in I.YEARS:files.append(I.YEARS[y][0])
 sources=A.source_freeze();sources.update({str(q.resolve()):sha(q)for q in files})
 ab=read(p/'ARCHIVED_BASELINE_BINDING.json')
 sources.update(ab['B_cost1_reference_only']['source_sha256'])
 sources.update(ab['D63_G10_cost1_reference_only']['source_sha256'])
 reuse={k:dict(method='ARCHIVED_INDUCTION_SAME_FINANCIAL_PATH_NOT_NEW_BACKTEST',proof_path=str(PATH_PROOF),proof_SHA256=sha(PATH_PROOF),D10_reference=ab['D63_G10_cost1_reference_only'])for k in('MA63_G05','MA63_G20')}if job=='cost1-strong'else{}
 return dict(scope='ROBUSTNESS_FIXED_FULL_NATIVE_JOBS',job=job,window=window,family=family,
             executed_arms=cfg['labels'],executed_arm_config={k:R.FAMILIES[family][k]for k in cfg['labels']},
             archived_same_path_matrix_rows=reuse,all_fixed_matrix=R.FAMILIES,
             initial_CNY='1000000',native_clock_start=native_start,full_start=start,fixed_end=end,closes_per_account=days,
             actual_account_CLOSEs=days*len(cfg['labels']),own_state_continuous_no_year_reset=True,
             old_ACT20_BREAK63_and_stock_exit_unchanged=True,provider='ma_provider.MarketInfo',
             private_score_binding=dict(path=str(b),SHA256=sha(b)),score_helper_AST_SHA256=score_ast(),
             actual_input_wrapper=dict(path=str(INPUT_WRAPPER),SHA256=sha(INPUT_WRAPPER),underlying_source=str(I.SOURCE)),
             archived_control_binding=str(p/'ARCHIVED_BASELINE_BINDING.json'),
             small_gate_SHA256={str(q.resolve()):sha(q)for q in gates},sources=sources,
             cost_profile='ORIGINAL_NATIVE_STRESS_FLAGS_1.5'if family=='cost15'else'ORIGINAL_COST1',
             cost_profiles_separate_process=True,no_new_loader_cache_ledger=True,seen_development_windows_not_OOS=True,
             scheduler='MAX_2_NATIVE_PROCESSES; TWO_LONG_JOBS_FIRST; NEXT_STRONG_ON_SLOT_RELEASE; NO_RESULT_SELECTION')
def prepare(job,finance_gate):
 assert finance_gate is not None,'final small finance gate path required for final full freeze'
 p=O/'prepared-full-v1'/job;p.mkdir(parents=True,exist_ok=True)
 window=F.JOBS[job]['window'];I.configure_scores(window,p)
 cal=calendar(window);immutable(p/'EXPECTED_CLOSE_CALENDAR.json',cal)
 clocks=[]
 for n in(62,63,64):
  info=MarketInfo(HISTORY[window],cal['closes'],n)
  for close in cal['closes'][2:]:
   for phase in('09:30:00','15:10:00'):
    at=J.M.N.iso(close[:10]+'T'+phase+'+08:00');v=info.state(at)
    assert v['state']!='UNKNOWN'and v['available_at']<=at
    assert phase!='09:30:00'or v['day']<close[:10]
    assert v['MA_window']==n
    clocks.append(dict(at=at,**v))
 immutable(p/'MARKET_INFO_FULL_CLOCKS.json',dict(passed=True,independent_calendar_SHA256=sha(p/'EXPECTED_CLOSE_CALENDAR.json'),stored_X_source_SHA256=sha(HISTORY[window]),rows=clocks,new_Accounts=0))
 immutable(p/'ARCHIVED_BASELINE_BINDING.json',archive_binding(window))
 immutable(p/'FULL_SOURCE_MANIFEST.json',manifest(job,finance_gate.resolve()))
 m=read(p/'FULL_SOURCE_MANIFEST.json')
 immutable(p/'PROPOSED_FULL_AUTHORIZATION.json',dict(approved=False,scope=m['scope'],job=job,source_manifest_SHA256=sha(p/'FULL_SOURCE_MANIFEST.json'),small_gate_SHA256=m['small_gate_SHA256'],preparation_has_no_account_events=True))
 print('PREPARED_ZERO_ACCOUNTS',job,sha(p/'FULL_SOURCE_MANIFEST.json'),flush=True)
def execute(args):
 # No configure_scores, original input load or Account before exact grant.
 assert args.authorization is not None,'separate exact root full authorization required before loading'
 grant=read(args.authorization);assert grant['approved']is True and grant['scope']=='ROBUSTNESS_FIXED_FULL_NATIVE_JOBS'and grant['job']==args.job
 p=O/'prepared-full-v1'/args.job;m=read(p/'FULL_SOURCE_MANIFEST.json')
 assert grant['source_manifest_SHA256']==sha(p/'FULL_SOURCE_MANIFEST.json')and grant['small_gate_SHA256']==m['small_gate_SHA256']
 finance=[Path(q)for q in m['small_gate_SHA256']if Path(q)!=LOGIC_GATE.resolve()];assert len(finance)==1
 assert J.W.canon(manifest(args.job,finance[0]))==m
 out=args.out.resolve();assert str(out).startswith(str(O.resolve())+'/')and not out.exists(),'fresh unique output required'
 out.mkdir(parents=True);save(out/'STARTED.json',dict(full_schema=m,authorization=str(args.authorization.resolve()),authorization_SHA256=sha(args.authorization),resume=str(args.resume)if args.resume else None))
 cfg=F.JOBS[args.job];window,family=cfg['window'],cfg['family'];I.configure_scores(window,out)
 assert N.SCORES.manifest_sha256==m['private_score_binding']['SHA256']
 begun=time.monotonic();shared,receipts,cp,states,ir,identity=I.load_long(out)if window=='long'else I.load_strong(out)
 native_start,start,end,days,warm=WINDOWS[window];cal=read(p/'EXPECTED_CLOSE_CALENDAR.json')
 actual=[str(v)for v in shared[1].cutoffs if warm[0]<=str(v.date())<=end]
 assert actual==[str(J.M.N.iso(v))for v in cal['closes']],'native venue calendar changed'
 if family=='cost15':shared=K.wrap_shared(shared)
 ns={R.FAMILIES[family][k][0]for k in cfg['labels']}-{None}
 infos={n:MarketInfo(HISTORY[window],cal['closes'],n)for n in ns}
 J.START,J.END=native_start,end
 run=F.runner(args.job,shared,receipts,infos=infos,fixed_end=end,**A.S.kwargs(cp,states,ir))
 run.source_freeze=dict(m['sources']);save(out/'INPUT_IDENTITY.json',identity);loaded=time.monotonic()
 with IO.atomic_runner_outputs(run,L,out,canonicalize=J.W.canon):
  cursor=run.restore(args.resume)if args.resume else None
  done=run.run_prepared(out,args.seconds,resume_after=cursor,end=end)
 assert all(sha(q)==h for q,h in m['sources'].items())
 save(out/'TIMING.json',dict(completed=done,input_seconds=loaded-begun,total_seconds=time.monotonic()-begun,event_seconds=getattr(run,'run_seconds',None)))
 if done:
  assert len(run.daily)==days*len(cfg['labels'])
  save(out/'WINDOW_RESULT.json',dict(passed=True,job=args.job,days_each=days,executed_arms=cfg['labels'],archived_references_only=m['archived_control_binding'],archived_same_path_rows=m['archived_same_path_matrix_rows'],arms={k:dict(NAV=str(a.current_nav),buyfills=a.counts['buy_fills'],sellfills=a.counts['sell_fills'],trades=len(a.trades))for k,a in run.accounts.items()},source_post_exact=True,independent_review='PENDING'))
 print('FULL_COMMITTED'if done else'CHECKPOINTED_NO_AUTOMATIC_REPLAY',args.job,flush=True)
def main():
 p=argparse.ArgumentParser();m=p.add_mutually_exclusive_group(required=True);m.add_argument('--prepare-only',action='store_true');m.add_argument('--execute',action='store_true')
 p.add_argument('--job',choices=F.JOBS,required=True);p.add_argument('--finance-gate',type=Path);p.add_argument('--out',type=Path);p.add_argument('--authorization',type=Path);p.add_argument('--resume',type=Path);p.add_argument('--seconds',type=int,default=3600);args=p.parse_args()
 if args.prepare_only:prepare(args.job,args.finance_gate)
 else:assert args.out is not None;execute(args)
if __name__=='__main__':
 try:main()
 except BaseException:print(traceback.format_exc());raise
