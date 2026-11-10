"""Prepare exact sources and narrowly authorized small cases; no full option."""
from pathlib import Path
import argparse,json,gzip,hashlib,time,traceback,pickle
import robust_adapter as R
import inputs_reuse as I
from ma_provider import MarketInfo
K,A,N,J,L,IO=R.K,R.A,R.N,R.J,R.L,R.IO
O=Path(__file__).resolve().parent;T=O.parent
HISTORY={'long':T/'benchmark_2022_2023/continuation2024/inputs/510300_history.csv','strong':T/'capacity_cost_guard_analysis_v1/benchmark_B_2025_26/inputs/510300_history.csv'}
CASES={'long':[('legacy9','2022-01-04','2022-01-14',9),('fresh_DOWN_technical6','2022-01-07','2022-01-14',6)],'strong':[('strong9','2025-07-01','2025-07-11',9)]}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):IO.write_json(p,J.W.canon(x))
def active(window,family):
 # Fixed matrix rows remain. These two strong rows use the independently
 # proved archived identical path, not an unreported dropped experiment.
 return['MA62_G10','MA64_G10']if window=='strong'and family=='cost1'else list(R.FAMILIES[family])
def calendar(window):return read(T/f'market_gross_admission_native_v1/prepared/{window}/EXPECTED_CLOSE_CALENDAR.json')
def manifest(window,family):
 paths=[O/'PROTOCOL.txt',O/'robust_adapter.py',O/'cost15_compat.py',O/'ma_provider.py',O/'inputs_reuse.py',Path(__file__),I.SOURCE,O/'MA63_RECOMPUTE_CHECK.json',O/'COST15_PURE_CHECKS.json',HISTORY[window],T/f'market_gross_admission_native_v1/prepared/{window}/EXPECTED_CLOSE_CALENDAR.json',Path(N.SCORES.path)]
 proof=T/'market_gross_robustness_logic_review_v1/STRONG_ALPHA5_20_ARCHIVED_PATH_BOUND.json';assert proof.exists();paths.append(proof)
 if family=='cost15':paths +=[Path(p)for p in K.source_receipt()['stored_original_source_SHA256']]
 for y in(('2022','2023','2024')if window=='long'else('strong',)):
  paths.append(I.SCORE_PATHS[y])
  if y in I.YEARS:paths.append(I.YEARS[y][0])
 src=A.source_freeze();src.update({str(p.resolve()):sha(p)for p in paths})
 return dict(stage='ROBUSTNESS_IMPLEMENT_AND_SMALL_ONLY',window=window,family=family,all_fixed_matrix=R.FAMILIES,active_small_arms=active(window,family),archived_strong_alpha5_20_proof=str(proof),no_full_authorization=True,initial_CNY='1000000',small_cases=CASES[window],source_sha256=src,private_score_binding=dict(path=N.SCORES.path,sha256=N.SCORES.manifest_sha256),cost_meaning='original native stress flags, not blanket fee multiplication',archived_cost1_primary_references=T.as_posix()+'/market_gross_admission_native_v1/ARCHIVED_B_CONTROL_BINDING.json')
def prepare(window):
 p=O/'prepared'/window;p.mkdir(parents=True,exist_ok=True);I.configure_scores(window,p)
 assert all(v['all_history_D_classification_exact']for v in read(O/'MA63_RECOMPUTE_CHECK.json')['windows'].values())
 for family in R.FAMILIES:
  d=p/family;d.mkdir(exist_ok=True);m=manifest(window,family);q=d/'SMALL_SOURCE_MANIFEST.json'
  if q.exists():assert read(q)==J.W.canon(m),'prepared source changed; preserve old attempt'
  else:save(q,m)
  proposal=dict(approved=False,stage='ROBUSTNESS_SMALL_TECHNICAL_ONLY',window=window,family=family,small_manifest_sha256=sha(q),full=False)
  if not(d/'PROPOSED_SMALL_AUTHORIZATION.json').exists():save(d/'PROPOSED_SMALL_AUTHORIZATION.json',proposal)
  print('PREPARED_ZERO_ACCOUNTS',window,family,sha(q),flush=True)
def execute(args):
 assert args.authorization is not None,'root small acceptance required; no full entry exists'
 grant=read(args.authorization);assert grant['approved']is True and grant['stage']=='ROBUSTNESS_SMALL_TECHNICAL_ONLY'and not grant['full']
 assert grant['window']==args.window and grant['family']==args.family
 out=args.out.resolve();assert str(out).startswith(str(O.resolve())+'/')and not(out/'STARTED.json').exists();out.mkdir(parents=True)
 I.configure_scores(args.window,out);p=O/'prepared'/args.window/args.family/'SMALL_SOURCE_MANIFEST.json';m=read(p);assert manifest(args.window,args.family)==m and grant['small_manifest_sha256']==sha(p)
 save(out/'STARTED.json',dict(scope='ONLY_FIXED_SMALL_TECHNICAL_CASES_NO_FULL',manifest=m,authorization=str(args.authorization),authorization_SHA256=sha(args.authorization)))
 start=time.monotonic();value=I.load_long(out)if args.window=='long'else I.load_strong(out);loaded=time.monotonic();shared,receipts,cp,states,ir,identity=value;cal=calendar(args.window);results={}
 wanted={R.FAMILIES[args.family][k][0]for k in active(args.window,args.family)}-{None};infos={n:MarketInfo(HISTORY[args.window],cal['closes'],n)for n in wanted}
 for name,begin,end,expected in CASES[args.window]:
  dest=out/name;dest.mkdir();save(dest/'STARTED.json',dict(name=name,begin=begin,end=end,closes_each=expected,arms=active(args.window,args.family),sources=m['source_sha256'],fresh_technical_not_economic_window=name=='fresh_DOWN_technical6'))
  sh,rr,kw=A.S.physical_inputs(shared,receipts,cp,states,ir,end)
  if args.family=='cost15':sh=K.wrap_shared(sh)
  J.START,J.END=begin,end;cls=R.CostRunner if args.family=='cost15'else R.Runner
  run=cls(sh,rr,infos=infos,family=args.family,fixed_end='2024-12-31'if args.window=='long'else'2026-06-30',labels=active(args.window,args.family),**kw);run.source_freeze=m['source_sha256'];save(dest/'INPUT_IDENTITY.json',identity);t=time.monotonic()
  clocks=[];shorts={n:i.prefix(end)for n,i in infos.items()};roundtrips={n:pickle.loads(pickle.dumps(i))for n,i in infos.items()}
  for day in[str(x.date())for x in sh[1].cutoffs if begin<=str(x.date())<=end]:
   for n,info in infos.items():
    short=shorts[n];restored=roundtrips[n]
    for phase in('09:30:00','15:10:00'):
     at=J.M.N.iso(day+'T'+phase+'+08:00');v=info.state(at);assert v==short.state(at)==restored.state(at);assert v['available_at']<=at and(phase!='09:30:00'or v['day']<day);clocks.append(dict(at=at,window=n,**v))
  save(dest/'PROVIDER_CLOCK_CHECKS.json',dict(passed=True,rows=clocks))
  with IO.atomic_runner_outputs(run,L,dest,canonicalize=J.W.canon):done=run.run_prepared(dest,600,end=end)
  assert done and len(run.daily)==expected*len(run.accounts)
  assert all(sha(p)==h for p,h in m['source_sha256'].items())
  result=dict(passed=True,closes_each=expected,seconds=time.monotonic()-t,source_post_exact=True,arms={k:dict(NAV=str(a.current_nav),cost_multiplier=str(a.cost_multiplier),trades=len(a.trades),buyfills=a.counts['buy_fills'],sellfills=a.counts['sell_fills'],alpha=str(getattr(a,'robust_alpha','NO_EXTRA_GUARD')))for k,a in run.accounts.items()},independent_review='PENDING',full=False)
  save(dest/'SMALL_RESULT.json',result);results[name]=result;print('SMALL_COMMITTED',args.window,args.family,name,result,flush=True)
 save(out/'COMPLETED.json',dict(passed=True,family=args.family,window=args.window,input_seconds=loaded-start,total_seconds=time.monotonic()-start,cases=results,full=False))
def main():
 p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True);g.add_argument('--prepare-only',action='store_true');g.add_argument('--small',action='store_true');p.add_argument('--window',choices=CASES,required=True);p.add_argument('--family',choices=R.FAMILIES);p.add_argument('--out',type=Path);p.add_argument('--authorization',type=Path);a=p.parse_args()
 if a.prepare_only:prepare(a.window)
 else:assert a.family and a.out;execute(a)
if __name__=='__main__':
 try:main()
 except BaseException:print(traceback.format_exc());raise
