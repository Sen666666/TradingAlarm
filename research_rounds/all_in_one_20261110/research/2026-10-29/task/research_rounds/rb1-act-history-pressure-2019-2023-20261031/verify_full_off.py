"""Duplicate native A validation only, no new candidate or economic parameter."""
import adapter as m
from pathlib import Path
import time,signal,traceback,shutil,sys,json,hashlib
w=m.w;O=m.O
identity=w.load('history_full_native_identity',O.parent/'entry-loss-budget-cost2-funnel-20261031/run_cost2.py').identity
def save(p,x):w.K.save(p,x)
def main():
 sec=sys.argv[1];p=O/'COMPUTE_TIME.json';before=w.read(p);used=sum(x['seconds'] for x in before['stages'] if x['sector']==sec);left=min(300-used,600-before['seconds']);assert left>0;assert w.read(O/sec/'full/TIMING.json')['status']=='complete'
 t=time.monotonic();root=O/sec/'off-full-native';root.mkdir(exist_ok=False);shutil.copyfile(w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json');status='started';signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('full native off within sector300/total600')));signal.setitimer(signal.ITIMER_REAL,left)
 try:
  freeze=w.read(O/'FREEZE.json');assert all(w.sha(q)==h for q,h in freeze['sha256'].items());save(root/'VERIFICATION_SOURCE.json',dict(sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),kind='identical-policy technical replication',new_economic_variants=0))
  R,E,core,prep,mode=m.setup(sec,root,['A'],False,None);runner=R.run(root/'accounts-v2',modes=[mode],stresses=['base','cost2','delay1'],start='2018-12-28',end='2023-12-29',technical=True);save(root/'IDENTITY.json',identity(root,O/sec/'full/accounts-v2',list(runner.accounts),'2023-12-29',True));status='complete'
 except BaseException as e:status='failed';save(root/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-t;old=w.read(p);old['seconds']+=elapsed;old['stages'].append(dict(sector=sec,stage='off-full-native',status=status,seconds=elapsed));save(p,old);save(root/'TIMING.json',dict(status=status,seconds=elapsed,sector_seconds=used+elapsed,total_seconds=old['seconds']));print(sec,status,elapsed,'total',old['seconds'],flush=True)
if __name__=='__main__':main()
