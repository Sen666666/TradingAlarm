"""Trace false aliases inside the first actual flagged field. NO ACTION."""
from pathlib import Path
from dataclasses import is_dataclass
import hashlib,inspect,json,sys,traceback
O=Path(__file__).resolve().parent;A=O.parent/'C-rights-Jan13-action-v1-20261102';UP=O.parent/'C-rights-Jan12-upgrade-v1-20261102'
sys.path[:0]=[str(A),str(UP)];import state_snapshot as S;import serializer_fix as T;import upgrade_runtime as U
line0=inspect.getsourcelines(S.norm)[1]
alias_line=next(line0+i for i,s in enumerate(inspect.getsourcelines(S.norm)[0]) if 'if id(x) in seen:return' in s)
rec=next(x for x in U.read(UP/'UPGRADED_CHECKPOINTS.json') if x['arm']=='2022-C10');r=U.UpgradedRunner.restore(rec['checkpoint'])
results=[]
for label,v in [('account.rejections',r.account.rejections),('runner.goal_intents',r.goal_intents)]:
 history={};false=[]
 def trace(frame,event,arg):
  if event=='line' and frame.f_code is S.norm.__code__ and frame.f_lineno==alias_line:
   loc=frame.f_locals;x=loc['x'];parent=frame.f_back
   if isinstance(x,dict) and parent.f_code is S.norm.__code__ and parent.f_locals.get('d') is x and is_dataclass(parent.f_locals.get('x')):
    owner=parent.f_locals['x'];here=dict(owner_id=id(owner),owner_type=type(owner).__module__+'.'+type(owner).__qualname__,path=loc['path'])
    earlier=history.get(id(x))
    if id(x) in loc['seen'] and earlier and earlier['owner_id']!=here['owner_id'] and len(false)<3:
     false.append(dict(current=here,earlier=earlier,incorrect_alias_target=loc['seen'][id(x)],dict_keys=list(x),call_stack=[dict(file=t.filename,line=t.lineno,function=t.name) for t in traceback.extract_stack(frame)]))
    elif id(x) not in loc['seen']:history[id(x)]=here
  return trace
 sys.settrace(trace);S.norm(v);sys.settrace(None)
 results.append(dict(field=label,type=type(v).__name__,length=len(v),false_aliases=false,diagnostic_hash=T.digest(v)))
(O/'REAL_FIELD_FALSE_ALIASES.json').write_text(json.dumps(dict(no_ACTION=True,fields=results),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(no_ACTION=True,fields=[dict(field=x['field'],type=x['type'],length=x['length'],false_alias_count=len(x['false_aliases'])) for x in results]),indent=2))
