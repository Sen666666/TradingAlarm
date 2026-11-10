"""Independent buffer/occupancy replay from emitted events, no controller import."""
from common_abcd import *
import gzip,collections

def streams(name):
 for folder in [HERE/'technical/A-controls',HERE/'accounts']:
  with gzip.open(folder/(name+'.jsonl.gz'),'rt') as f:
   for line in f:yield json.loads(line)

def main():
 dates=[str(x)[:10] for x in np.load(HERE/'prepared/dual-board.npz')['dates']];idx={d:i for i,d in enumerate(dates)};meta=read(OLD/'inputs-v2/metadata.json');previous={};last={};plans=0;rows=0;occupation=0
 for d in streams('decisions'):
  aid=d['account'];day=d['at'][:10];i=idx[day];r=d['rotation'];rows+=1
  if not r:continue
  counter={};prior=previous.get(aid,{})
  for p in r['observations']:
   key=(p['kind'],p['incoming'],p['outgoing']);n=prior.get(key,0)+1 if last.get(aid)==i-1 else 1
   assert p['confirmations']==n;assert p['rank_out']-p['rank_in']==p['gap']>=2;counter[key]=n
  p=r['plan']
  if p:
   key=(p['kind'],p['incoming'],p['outgoing']);assert counter[key]>=3 and p['fresh_today'] and not r['waiting_for_own_exit'];plans+=1
   outs=[o for o in d['occupancy'] if (o['security_id']==p['outgoing'] if p['kind']=='stock' else o['sector_id']==p['outgoing']) and o['has_position']]
   assert outs and all(o['exit_latched'] for o in outs)
  last[aid]=i;previous[aid]=counter
 for d in streams('daily'):
  ids=set(d['positions'])|set(d['pending_buys'])|set(d['pending_sells']);sectors=collections.Counter(meta[s]['sector_id'] for s in ids)
  assert len(ids)<=6 and len(sectors)<=3 and max(sectors.values(),default=0)<=2,(d['account'],d['at'],ids);occupation+=1
 write(HERE/'technical/portfolio-rules.json',dict(recorded_at=now(),passed=True,decision_rows=rows,all_real_and_pending_occupancy_rows=occupation,rotation_plans=plans,independent_distinct_close_streaks=True,old_exit_slots_not_freed_before_fills=True,initial_slot_sector_caps_preserved=True))
 print(dict(portfolio_rules_passed=True,decisions=rows,plans=plans),flush=True)
if __name__=='__main__':main()
