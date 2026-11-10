"""Read the sealed provider at original query clocks; no account execution."""
from pathlib import Path
from collections import Counter
import sys,json,gzip,hashlib
O=Path(__file__).resolve().parent;A=O.parents[1];EQ=A.parent;B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task')
sys.path.insert(0,str(A));from context_provider import ContextProvider
provider=ContextProvider();SRC={str(A/'context_provider.py'):hashlib.sha256((A/'context_provider.py').read_bytes()).hexdigest()};cache={}
def at(sid,day):
 key=(sid,day)
 if key not in cache:cache[key]=provider.at(sid,day)
 return cache[key]
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
result={};examples=[]
for ref,pair in [('2022_2024',B/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024/no60/run-2024/pair'),('strong',B/'pvr_pool_feasibility/runs/2025_26/pair')]:
 entries=read(EQ/'entry_exit_scale/holding_exit'/(ref+'_LAYERS.json'));c=Counter();e=Counter()
 for row in entries:
  q=at(row['sid'],row['decision_at'][:10]);e['actual_entry_decisions']+=1;e['ready_R']+=q['ready_R'];e['ready_P']+=q['ready_P']
  if not q['ready_R'] or not q['ready_P']:
   examples.append(dict(scope='actual_entry',window=ref,layer=row['layer'],sid=row['sid'],decision=row['decision_at'],context=q,interpretation='H2 UNKNOWN retains original native permission; this is not proof of strong trend.'))
 for d in read(pair/'daily.jsonl.gz',True,True):
  for row in d['layers']:
   q=at(row['sid'],d['at'][:10]);c['held_layer_CLOSE_queries']+=1;c['ready_R']+=q['ready_R'];c['ready_P']+=q['ready_P'];c['current_original_observation_missing']+=q['close'] is None;c['current_present_R_unknown']+=q['close'] is not None and not q['ready_R'];c['current_present_P_unknown']+=q['close'] is not None and not q['ready_P']
   if q['close'] is None and sum(x['scope']=='held_current_absent' for x in examples)<12:examples.append(dict(scope='held_current_absent',window=ref,layer=row['id'],sid=row['sid'],at=d['at'],context=q,interpretation='Price bars alone do not distinguish suspension from missing-source data. H2 cannot infer a current quote from native carried holding marks.'))
 result[ref]=dict(entries=dict(e),held_queries=dict(c))
with (O/'ACTUAL_QUERY_DOMAIN_COUNTS.json').open('x') as f:json.dump(dict(counts=result,examples=examples,provider_manifest_sha256=provider.manifest_sha256,unique_sid_day_queries=len(cache),new_accounts=0,new_events=0),f,ensure_ascii=False,indent=2)
SRC[str(__file__)]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
with (O/'LOOKUP_SOURCE_SHA256.json').open('x') as f:json.dump(SRC,f,ensure_ascii=False,indent=2)
print(json.dumps(result,ensure_ascii=False,indent=2))
