"""Only three root-authorized native small technical cases; no full option."""
from pathlib import Path
import argparse,gzip,hashlib,json,pickle,sys,time,traceback
import gross_adapter as C
import inputs_reuse as I
from market_info import MarketInfo
A,N,J,L,IO=C.A,C.N,C.J,C.L,C.IO
O=Path(__file__).resolve().parent;T=O.parent
CASES={'long':[('legacy9','2022-01-04','2022-01-14',9,True),('fresh_DOWN_technical6','2022-01-07','2022-01-14',6,False)],'strong':[('strong9','2025-07-01','2025-07-11',9,True)]}
INFOS={'long':T/'benchmark_2022_2023/continuation2024/inputs/510300_history.csv','strong':T/'capacity_cost_guard_analysis_v1/benchmark_B_2025_26/inputs/510300_history.csv'}
GOLDS={'legacy9':T/'capacity_cost_guard_v1/long-unified-small-v2/pair','strong9':T/'capacity_cost_guard_v1/strong-small-v1/pair'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):IO.write_json(p,J.W.canon(x))
def readbook(p):
 with gzip.open(p,'rt')as f:return json.load(f)
def readrows(p):
 with gzip.open(p,'rt')as f:return [json.loads(x)for x in f]
def sources(window):
 files=[O/'PROTOCOL.txt',O/'gross_adapter.py',O/'market_info.py',O/'inputs_reuse.py',Path(__file__),I.SOURCE,T/'MARKET_GROSS_ADMISSION_CARD_V1.txt',T/'MARKET_GROSS_ADMISSION_SMALL_AUTHORIZATION.json',INFOS[window]]
 out={str(p.resolve()):sha(p)for p in files};out.update(A.source_freeze())
 for y in(('2022','2023','2024')if window=='long'else('strong',)):
  p=I.SCORE_PATHS[y];out[str(p.resolve())]=sha(p)
  if y in I.YEARS:p=I.YEARS[y][0];out[str(p.resolve())]=sha(p)
 return out
def info_checks(info,dates,end):
 prefix=info.prefix(end);restored=pickle.loads(pickle.dumps(info));rows=[]
 for day in dates:
  for timepart in('09:30:00','15:10:00'):
   at=J.M.N.iso(day+'T'+timepart+'+08:00');v=info.state(at)
   assert v==prefix.state(at)==restored.state(at),'provider prefix/restart clock changed'
   assert v['available_at']<=at and(timepart!='09:30:00'or v['day']<day)
   rows.append(dict(at=at,**v))
 return dict(passed=True,physical_future_info_removed=True,pickle_provider_clock_roundtrip=True,native_historical_restart_claimed=False,source_sha256=info.sha256,rows=rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('--window',choices=CASES,required=True);p.add_argument('--out',required=True,type=Path);args=p.parse_args();out=args.out.resolve()
 assert str(out).startswith(str(O.resolve())+'/')and not(out/'STARTED.json').exists()
 grant=json.loads((T/'MARKET_GROSS_ADMISSION_SMALL_AUTHORIZATION.json').read_text());assert grant['authorized']and not grant['full_economic_run_authorized']
 for p0,h in grant['bindings'].items():assert sha(T/p0)==h,('small grant binding changed',p0)
 out.mkdir(parents=True);frozen=sources(args.window)
 save(out/'STARTED.json',dict(scope='ONLY_AUTHORIZED_SMALL_NATIVE_TECHNICAL_CASES',window=args.window,cases=CASES[args.window],sources=frozen,arms=['B','D_GROSS10'],full_economic_run=False))
 # No provider or new D export exists before the above source/protocol freeze.
 info=MarketInfo(INFOS[args.window]);I.configure_scores(args.window,out)
 begun=time.monotonic();value=I.load_long(out)if args.window=='long'else I.load_strong(out);loaded=time.monotonic()
 shared,receipts,cp,states,ir,identity=value;results={}
 for name,start,end,expected,gold in CASES[args.window]:
  dest=out/name;dest.mkdir();save(dest/'STARTED.json',dict(name=name,start=start,end=end,expected_closes=expected,source_freeze=frozen,physical_native_inputs=True,baseline_gold_expected=gold))
  # Numerical source arrays reused, original physical-prefix wrapper copies views.
  physical,rr,kw=A.S.physical_inputs(shared,receipts,cp,states,ir,end)
  dates=[str(x.date())for x in physical[1].cutoffs if start<=str(x.date())<=end];assert len(dates)==expected
  save(dest/'MARKET_INFO_CLOCK_CHECKS.json',info_checks(info,dates,end));J.START,J.END=start,end
  runner=C.Runner(physical,rr,info=info,**kw);runner.source_freeze=frozen
  save(dest/'INPUT_IDENTITY.json',identity);IO.write_bytes(dest/'derived_route.py',C.NEW_ROUTE.encode());t=time.monotonic()
  with IO.atomic_runner_outputs(runner,L,dest,canonicalize=J.W.canon):done=runner.run_prepared(dest,360,end=end)
  assert done and len(runner.daily)==expected*2
  b=readbook(dest/'pair/B.json.gz');ds=[r for r in readrows(dest/'pair/daily.jsonl.gz')if r['account']=='B']
  if gold:
   old=GOLDS[name];assert b==readbook(old/'B.json.gz'),('B whole small native book differs',name)
   assert ds==[r for r in readrows(old/'daily.jsonl.gz')if r['account']=='B'],('B daily differs',name)
  events=runner.accounts['D_GROSS10'].gross_events
  result=dict(passed=True,scope='TECHNICAL_SMALL_NOT_ECONOMIC_PROMOTION',closes_each=expected,seconds=time.monotonic()-t,baseline_small_book_and_daily_exact=gold if gold else'NOT_APPLICABLE_FRESH_START',arms={k:dict(NAV=str(a.current_nav),trades=len(a.trades),buyfills=a.counts['buy_fills'],sellfills=a.counts['sell_fills'])for k,a in runner.accounts.items()},gross_event_kinds={k:sum(x['kind']==k for x in events)for k in sorted({x['kind']for x in events})},positive_DOWN_reserves=sum(x['kind']=='reserve_pre'and x['info']['state']=='DOWN'and x['q']>0 for x in events),source_post_exact=all(sha(k)==v for k,v in frozen.items()),independent_ledger_and_logic_review='PENDING')
  assert result['source_post_exact'];save(dest/'SMALL_RESULT.json',result);results[name]=result
  print('SMALL_COMPLETE',name,json.dumps(result),flush=True)
 save(out/'COMPLETED.json',dict(passed=True,window=args.window,input_seconds=loaded-begun,total_seconds=time.monotonic()-begun,cases=results,full_run_authorized=False,no_cost_guard_import=not any(k in sys.modules for k in('capacity_adapter','guard')),source_post_exact=all(sha(k)==v for k,v in frozen.items())))
if __name__=='__main__':
 try:main()
 except BaseException:
  print(traceback.format_exc(),file=sys.stderr);raise
