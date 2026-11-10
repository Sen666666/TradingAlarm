"""Physical source truncation with the frozen runner; compare after main run."""
from common_abcd import *
import os,gc
from run_abcd import context,Sink
from runner_abcd import HistoryRunner,iso

def main(cutoff):
 verify(read(HERE/'freeze.json')['sha256']);os.environ['ABCD_MODES']='A,B,C,D';os.environ['ABCD_STRESSES']='base'
 b,m=context(cutoff);package=read(OLD/'inputs-v2/package.json');end=max(x for x in m.cutoffs if x.date().isoformat()<=cutoff);out=HERE/f'technical/prefix-{cutoff}';sink=Sink(out)
 r=HistoryRunner(b,m,start=iso(package['start']),end=end,sink=sink,synthetic=True)
 try:r.write(out,r.run(),dict(recorded_at=now(),physical_cutoff=cutoff,technical_only=True,driver_sha256=sha(__file__),frozen_runner_sha256=sha(HERE/'code/runner_abcd.py'),future_states_prices_actions_physically_removed=True))
 finally:sink.close()
 print(dict(physical_prefix_captured=cutoff,accounts=4,comparison_pending_until_full_run=True),flush=True)
if __name__=='__main__':main(sys.argv[1])
