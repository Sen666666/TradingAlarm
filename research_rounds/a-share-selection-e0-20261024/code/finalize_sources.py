"""Read-only union of stopped old/new batches; invoke unchanged source verifier."""
from pathlib import Path
import sys,json,hashlib

HERE=Path(__file__).resolve().parents[1]
OLD=HERE.parent/'current-pool-20261022'
sys.path.insert(0,str(OLD/'audit-a'))
import finalize_a

def main():
 state=json.loads((HERE/'downloads/supplement-queue-01/queue-state.json').read_text())
 if state['status']!='finished':raise ValueError('All source writers must be stopped: '+state['status'])
 roots=[OLD/'downloads',HERE/'downloads/supplement-queue-01']
 batches=sorted(set(p for r in roots for p in finalize_a.discover_history_batches(r)))
 view=HERE/'source-view-v1';view.mkdir(exist_ok=False)
 for i,b in enumerate(batches): (view/f'{i:04d}-{b.name}').symlink_to(b,target_is_directory=True)
 (view/'sources.json').write_text(json.dumps([str(x) for x in batches],indent=2)+'\n')
 result=finalize_a.finalize(OLD/'audit-a/prepared-current-master-v1',view,HERE/'data-finalized-v1')
 print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
