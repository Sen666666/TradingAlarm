"""Narrow launcher for unchanged existing THS collectors; A-only new evidence.

Credentials stay inside the original session loader/authorized socket. The
rejection-latch copy is confined to this study and preserves prior rejections.
No security setting, application process, or historical artifact is modified.
"""
from pathlib import Path
import sys,runpy,json,hashlib,argparse
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parents[1]
OLD=ROOT/'research_rounds/current-pool-20261022/code'
RESEARCH=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research')

def main():
    p=argparse.ArgumentParser();p.add_argument('kind',choices=['snapshot','history','queue']);p.add_argument('arguments',nargs=argparse.REMAINDER);a=p.parse_args()
    sys.path[:0]=[str(RESEARCH),str(OLD)]
    import ths_readonly as ths
    latch=HERE/'audit/rejected-fingerprints.json'
    if not latch.exists():
        original=ths.REJECTION_LATCH
        latch.write_bytes(original.read_bytes() if original.exists() else b'{}')
    ths.REJECTION_LATCH=latch
    target=OLD/({'snapshot':'snapshot_batch.py','history':'history_batch.py','queue':'history_queue.py'}[a.kind])
    arguments=a.arguments[1:] if a.arguments[:1]==['--'] else a.arguments
    # These plans are data-only and all node requests must be9602/A markets.
    if '--plan' in arguments:
        plan=json.loads(Path(arguments[arguments.index('--plan')+1]).read_text())
        assert all(str(i['node'])=='9602' and i['symbol'].startswith(('USHA','USZA','USHT','USTM')) for i in plan['items'])
    arguments+=['--research-root',str(RESEARCH)]
    sys.argv=[str(target),*arguments]
    runpy.run_path(str(target),run_name='__main__')
if __name__=='__main__':main()
