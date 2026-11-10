"""Static source/old-result inventory. Never import or run a research model."""
from pathlib import Path
import ast,hashlib,json
O=Path(__file__).resolve().parent;W=O.parent;R=Path('/Users/bytedance/Documents/ChatGPT/money');RR=R/'research_rounds'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
specs=[
 (RR/'pv-strength-b5-20261025/code/evidence.py',['_event_facts'],True),
 (RR/'pv-strength-b5-20261025/code/policy.py',['e0_policy'],False),
 (RR/'pv-strength-b4-20261025/code/model.py',['run_valid','strength_frame'],True),
 (RR/'b5-g1-20261025/code/grade.py',['classify'],True),
 (RR/'b5-g1-20261025/code/policies_g1.py',['project'],True),
 (RR/'rs-h1-execution-20261025/code/rs_h1_model.py',['raw_momentum','mid_percentile','rank_known'],True),
 (RR/'rs-h1-execution-20261025/code/sector_stock_admission.py',['eligibility'],True),
 (RR/'rs-h1-execution-20261025/code/current_pool_bridge.py',[],False),
 (RR/'continuous-protection-lines-20261028/code/model.py',['features','calculate','project'],True),
 (R/'TradingAlarm/desk/refresh.py',['prepare_facts'],True),
 (RR/'recovery-only-20261027/code/engine.py',['Facts.packet'],True),
 (W/'case-stage-ledger-20261031/v3/joint_v3.py',['Runner.industry','Runner.planning','Runner.route','Runner.opening'],False),
 (W/'migration-admission-native-readiness-20261101/native_adapter.py',['enable','static_contract'],False),
 (RR/'pvr-act-comparison-20261027/code/experiment.py',['score'],True),
 (R/'TradingAlarm/research/strategy_signals.py',['channel_signal'],True),
 (R/'TradingAlarm/research/broad_ths_channel_pilot.py',['main'],False)]
out=[];ex=[]
for p,names,excerpt in specs:
 s=p.read_text();lines=s.splitlines();tree=ast.parse(s)
 funcs={}
 for node in tree.body:
  if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):funcs[node.name]=node
  if isinstance(node,ast.ClassDef):
   for child in node.body:
    if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)):funcs[node.name+'.'+child.name]=child
 selected=[]
 for name in names:
  n=funcs[name];selected.append(dict(function=name,first=n.lineno,last=n.end_lineno))
  if excerpt:ex += [f'FILE {p}',f'SHA256 {sha(p)}',f'FUNCTION {name} lines {n.lineno}-{n.end_lineno}',*['%4d %s'%(i,lines[i-1]) for i in range(n.lineno,n.end_lineno+1)],'']
 out.append(dict(path=str(p),sha256=sha(p),functions=selected))
 # Preserve the complete policy order excerpt, without copying its validation boilerplate.
 if p.name=='policy.py':ex += [f'FILE {p}',f'SHA256 {sha(p)}','EXCERPT e0_policy state-transition order only; lines 100-143',*['%4d %s'%(i,lines[i-1]) for i in range(100,144)],'']
 if p.name=='joint_v3.py':ex += [f'FILE {p}',f'SHA256 {sha(p)}','EXCERPT native hold/exit/new-risk and core-first ordering; lines213-260,299-322',*['%4d %s'%(i,lines[i-1]) for a,b in [(213,260),(299,322)] for i in range(a,b+1)],'']
(O/'SOURCE_INDEX.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');(O/'SOURCE_EXCERPTS.txt').write_text('\n'.join(ex))
evidence=[RR/'b5-g1-20261025/CONCLUSION.md',RR/'rs-h1-execution-20261025/CONCLUSION.md',RR/'pvr-incremental-order-20261029/FINAL_REPORT.txt',RR/'pvr-local-finite-capital-20261029/FINAL_REPORT.txt',RR/'pvr-act-feedback-isolation-20261029/FINAL_REPORT.txt',RR/'continuous-protection-lines-20261028/CONCLUSION.txt',RR/'gradual-recovery-rc1-20261025/CONCLUSION.md',RR/'directional-amount-20261027/CONCLUSION.md',R/'docs/ALGORITHM_S_AMT1.txt',W/'g1-current-state-readonly-20261101/READOUT.txt',W/'opportunity-quality-ranking-20261031/READOUT.txt',W/'e0-density-direction-observation-20261030/FINAL_REPORT.txt']
# Explicitly retain missing lookup paths as unknown rather than silently finding another result.
records=[dict(path=str(p),exists=p.exists(),sha256=sha(p) if p.exists() else None) for p in evidence]
for kind in ['broad-ths-channel-pilot','broad-ths-channel-last100']:
 for name in ['protocol.json','summary.json']:
  p=R/'TradingAlarm/research/results'/kind/name;records.append(dict(path=str(p),exists=p.exists(),sha256=sha(p) if p.exists() else None))
(O/'EVIDENCE_SOURCE_SHA256.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print('STATIC SOURCE INDEX',len(out),'files;',sum(len(x['functions']) for x in out),'located functions; missing evidence paths:',[r['path'] for r in records if not r['exists']])
