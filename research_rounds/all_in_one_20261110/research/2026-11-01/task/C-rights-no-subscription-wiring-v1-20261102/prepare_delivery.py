"""Text patch + dependency/schema verification only. No native runner imports."""
from pathlib import Path
from decimal import Decimal
import ast,difflib,hashlib,json
from rights_wiring import validate_rights
O=Path(__file__).resolve().parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 tests=[]
 def check(n,v,detail=None):tests.append(dict(check=n,passed=bool(v),detail=detail));assert v,(n,detail)
 deps=read(O/'DEPENDENCIES.json')['original_sources'];check('all original source dependencies unchanged',all(sha(p)==h for p,h in deps.items()),len(deps))
 source=W/'g-s-C-month-continuation-20261102/month_runtime.py';before=source.read_text();after=before
 replacements=[('P=C.P;E=C.E;X=C.X;H=C.H\n','P=C.P;E=C.E;X=C.X;H=C.H\nfrom rights_wiring import NoSubscriptionInputsMixin,NoSubscriptionRunnerMixin\n'),('class MonthInputs(X.ExtendedInputs):','class MonthInputs(NoSubscriptionInputsMixin,X.ExtendedInputs):'),('class MonthRunner(C.HorizonRunner):','class MonthRunner(NoSubscriptionRunnerMixin,C.HorizonRunner):'),(' def corporate_actions(self,day):\n',' def _rights_ordinary_dispatch(self,day):\n')]
 for old,new in replacements:check('single original patch site '+old.strip(),after.count(old)==1);after=after.replace(old,new,1)
 ast.parse(after);patch=''.join(difflib.unified_diff(before.splitlines(keepends=True),after.splitlines(keepends=True),fromfile='a/month_runtime.py',tofile='b/month_runtime.py'))
 (O/'integration.patch').write_text(patch)
 check('minimal patch has no strategy/budget function edits',len(replacements)==4 and 'choose_k' not in patch and 'def provider' not in patch)
 oldtree=ast.parse(before);newtree=ast.parse(after)
 def method(tree,name):
  c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='MonthRunner');return next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)
 oldmethod=method(oldtree,'corporate_actions');newmethod=method(newtree,'_rights_ordinary_dispatch')
 check('ordinary original dispatcher body unchanged',ast.dump(ast.Module(body=oldmethod.body,type_ignores=[]))==ast.dump(ast.Module(body=newmethod.body,type_ignores=[])))
 save('PATCH_CHECK.json',dict(original=str(source),original_sha256=sha(source),patched_text_sha256=hashlib.sha256(after.encode()).hexdigest(),patch_sha256=sha(O/'integration.patch'),replacements=4,syntax_only=True,original_file_written=False,patched_module_executed=False))
 # Actual historical source terms are schema-checked only, never dispatched.
 terms=read(W/'g-s-C-month-continuation-20261102/inputs/2022/month/actions.json');proofs=[validate_rights(x,x['effective_date']) for x in terms]
 check('two original source terms schema-ready',len(proofs)==2 and {p['signal_ratio'] for p in proofs}=={'1.30','1.15'} and all(p['actual_cash']=='0' and p['actual_share_ratio']=='1' for p in proofs))
 save('SOURCE_TERMS_SCHEMA_ONLY.json',dict(proofs=proofs,financial_dispatch=False,accounts_instantiated=False,actual_history_events=0))
 loader=W/'g-s-readonly-historical-loader-r2-20261101/loader.py';t=ast.parse(loader.read_text());c=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name=='HistoricalInputs');fn=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='check_action_support')
 class UnsupportedInput(ValueError):pass
 ns={'Decimal':Decimal,'UnsupportedInput':UnsupportedInput};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(loader)+'::pure_original_check','exec'),ns)
 refused=0
 for term in terms:
  try:ns['check_action_support'](None,term,[])
  except UnsupportedInput:refused+=1
 check('original frozen loader still rejects both; no bypass edit',refused==2)
 stderr=(O/'TEST_STDERR.txt').read_text();check('18 synthetic tests passed','Ran 18 tests' in stderr and '\nOK\n' in stderr)
 cross=[read(O/'synthetic-results'/(mode+'-crossprocess.json')) for mode in ['C10','C_BATCH20']]
 check('two independent-process synthetic restores/duplicates exact',all(r['restored'] and r['duplicate']=='already_applied' and r['synthetic_only'] for r in cross))
 for mode in ['C10','C_BATCH20']:
  cp=O/'synthetic-results'/(mode+'.pkl');side=read(cp.with_suffix('.provenance.json'));check('synthetic checkpoint hash exact '+mode,side['checkpoint_sha256']==sha(cp))
 imports=[]
 for n in ast.walk(ast.parse((O/'rights_wiring.py').read_text())):
  if isinstance(n,ast.Import):imports += [a.name for a in n.names]
  if isinstance(n,ast.ImportFrom):imports.append(n.module or '')
 check('wiring module imports no loader/runner/financial implementation',not any(any(s in i for s in ['loader','native','sector_account','policy','selector']) for i in imports),imports)
 check('restore CLI confined to owned synthetic directory',"p.parent!=(HERE/'synthetic-results').resolve()" in (O/'restore_synthetic.py').read_text())
 check('dependencies still unchanged after metadata verification',all(sha(p)==h for p,h in deps.items()))
 save('VERIFICATION.json',dict(passed=True,checks=len(tests),tests=tests,historical_accounts_opened=0,historical_financial_events=0,original_writes=0,current_four_accounts_touched=False))
 save('CODE_FREEZE.json',{p.name:sha(p) for p in sorted(O.iterdir()) if p.suffix=='.py' or p.name in ['CONTRACT.txt','DEPENDENCIES.json','integration.patch']})
 print('DELIVERY_METADATA_VERIFIED',len(tests),'checks')
if __name__=='__main__':main()
