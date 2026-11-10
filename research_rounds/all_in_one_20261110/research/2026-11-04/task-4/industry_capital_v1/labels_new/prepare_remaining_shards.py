"""Resource-only partition of unfinished identities. Never reads PnL for scheduling."""
from pathlib import Path
from collections import defaultdict,Counter
import gzip,hashlib,json,time

O=Path(__file__).resolve().parent
MOTHER=O.parent/'events/CORE_SECTOR_REJECT_EVENTS_WITH_PREFIX.jsonl.gz'
PARTIAL=O/'FIRST_REJECT_SHADOW_LABELS.partial.jsonl.gz'
DEST=O/'remaining_shards'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def readlines(p):
 with gzip.open(p,'rt')as h:
  for line in h:yield json.loads(line)
def main():
 start=time.monotonic();DEST.mkdir(exist_ok=False)
 done=[r['key']for r in readlines(PARTIAL)]
 assert len(done)==len(set(done))==3879
 done=set(done)
 first=[r for r in readlines(MOTHER)if r['is_first_sector_reject_in_original_source_I_epoch']]
 assert len(first)==8335 and done<={r['key']for r in first}
 remaining=[r for r in first if r['key']not in done]
 assert len(remaining)==4456
 bysid=defaultdict(list)
 for r in remaining:bysid[r['sid']].append(r)
 # Provider preparation dominates. A fixed input-only surcharge balances SID
 # counts as well as path counts; this changes no label or strategy parameter.
 groups=[[]for _ in range(4)];loads=[0]*4
 for sid,rows in sorted(bysid.items(),key=lambda x:(-len(x[1]),x[0])):
  j=min(range(4),key=lambda n:(loads[n],len(groups[n]),n))
  groups[j].extend(rows);loads[j]+=40+len(rows)
 manifest=[]
 for j,rows in enumerate(groups):
  rows.sort(key=lambda r:(r['sid'],r['window'],r['signal_day'],r['key']))
  target=DEST/f'shard{j}_events.jsonl.gz'
  with gzip.open(target,'wt')as h:
   for r in rows:h.write(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n')
  keys=[r['key']for r in rows];sids=sorted({r['sid']for r in rows})
  manifest.append(dict(shard=j,events=len(rows),SIDs=len(sids),windows=dict(Counter(r['window']for r in rows)),
      event_file=str(target.resolve()),event_file_sha256=sha(target),keys=keys,sids=sids,input_only_scheduling_weight=loads[j]))
 for j,a in enumerate(manifest):
  for b in manifest[:j]:assert not set(a['sids'])&set(b['sids'])
 allkeys=[k for m in manifest for k in m['keys']]
 assert len(allkeys)==len(set(allkeys))==4456 and not(set(allkeys)&done)
 value=dict(scope='Resource-only continuation plan; no further labels executed. Same native helper, unchanged q_min/fees/exit/CA/mother.',
    original_mother_first_events=8335,already_complete=3879,remaining=4456,shards=manifest,
    schedule_uses_only=['completed keys','SID identity','remaining event counts'],
    no_financial_outcomes_used_for_schedule=True,portfolio_policy_accounts=0,new_single_asset_shadow_paths=0,
    source_sha256={str(p.resolve()):sha(p)for p in [Path(__file__),MOTHER,PARTIAL,O/'native_single_asset.py',O/'FULL_LABEL_TIMING.json']},
    proposed_execution='Four independent processes with disjoint remaining SID sets; root fixes finite per-shard and aggregate compute budget, independent review before execution. No automatic retry.',
    merge_invariants='Original3879 + disjoint new4456 = exactly8335 unique mother keys; preserve every nonfill/unknown/censored result and all original window counts.',
    seconds=time.monotonic()-start)
 (DEST/'REMAINING_SHARD_PLAN.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:value[k]for k in ['already_complete','remaining','seconds']}))
 print(json.dumps([dict(shard=m['shard'],events=m['events'],SIDs=m['SIDs'],windows=m['windows'])for m in manifest]))
if __name__=='__main__':main()
