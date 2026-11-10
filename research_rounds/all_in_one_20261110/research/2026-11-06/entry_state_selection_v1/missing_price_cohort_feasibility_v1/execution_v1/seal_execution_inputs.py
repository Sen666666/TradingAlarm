from pathlib import Path
import hashlib,json,ast
O=Path(__file__).resolve().parent;R=O.parent.parent;J=R/'independent_channel_joint_economic_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 with (O/n).open('x') as f:json.dump(x,f,indent=2,ensure_ascii=False);f.write('\n')
assert (O/'INPUTS_COMPLETE.json').exists()
code={p.name:sha(p) for p in O.glob('*.py')};code['PROTOCOL.md']=sha(O/'PROTOCOL.md')
for p in O.glob('*.py'):ast.parse(p.read_text())
old=json.loads((O.parent/'OLD_TREE_SHA256_BEFORE.json').read_text());assert all(sha(p)==h for p,h in old.items())
plan=json.loads((J/'ROOT_ECONOMIC_AUTHORIZATION.json').read_text())['input_sha256'].copy()
for n in ['PREPARED_SOURCE_SHA256.json','PREPARED_OUTPUT_SHA256.json']:
 for p,h in json.loads((O/n).read_text()).items():
  p=str((O/p).resolve()) if not Path(p).is_absolute() else str(Path(p).resolve());assert p not in plan or plan[p]==h,(p,'hash conflict');plan[p]=h
for n in code:plan[str(O/n)]=code[n]
for p in [O.parent/'MISSING_WINDOW_AB_EVENTS.csv',O.parent/'AB_EVENT_FEASIBILITY_QA.json',O.parent/'PROTOCOL.json',O.parent/'OLD_TREE_SHA256_BEFORE.json',J/'market_adapter.py',R/'m3_stock_birth_during_sector_v1/freeze_events.py']:plan[str(p)]=sha(p)
for p,h in plan.items():assert sha(p)==h,(p,'prelaunch drift')
save('FROZEN_CODE_SHA256.json',code);save('FROZEN_INPUT_SHA256.json',plan)
save('FREEZE_QA.json',dict(protocol_sha256=sha(O/'PROTOCOL.md'),code_files=len(code),input_files=len(plan),all_inputs_current_hash_exact=True,old_files_unchanged=len(old),no_economic_loop_started=True))
print('FROZEN',sha(O/'PROTOCOL.md'),len(code),len(plan),flush=True)
