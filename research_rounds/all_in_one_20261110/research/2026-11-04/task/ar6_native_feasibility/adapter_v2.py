"""Memo-context/source binding addendum over immutable, gated adapter v1.

No quantity, risk, accounting, execution or signal expression is changed.
The v1 source remains intact so its original prefix identity is auditable.
"""
from pathlib import Path
from decimal import getcontext
import adapter as V1
for _name in dir(V1):
    if not _name.startswith('_'):globals()[_name]=getattr(V1,_name)

def decimal_semantics():
    c=getcontext()
    return dict(prec=c.prec,rounding=c.rounding,Emin=c.Emin,Emax=c.Emax,clamp=c.clamp,traps={str(k):v for k,v in c.traps.items()})
def bind_memo_context(owner):
    context=decimal_semantics()
    if getattr(owner,'_memo_decimal_context',None)!=context:
        owner._memo=None;owner._memo_decimal_context=context
    return context

class Runner(V1.Runner):
    def _solve(self,*args):
        bind_memo_context(self)
        return super()._solve(*args)
    def source_binding(self):
        x=super().source_binding();x[str(Path(__file__).resolve())]=sha(__file__);return x
    def bind_grant(self,path):
        g=read(path)
        E.require(g['parent_approved'] and g['runtime_sha256']==sha(__file__) and g['base_adapter_sha256']==sha(V1.__file__) and g['window']==self.window and g['ablation_enabled']==self.ablation_enabled and g['branch']==self.branch,'v2 grant source/scope mismatch')
        E.require(g['start']==('2022-01-04' if self.window=='2022' else '2025-07-01') and g['end']<=('2022-01-28' if self.window=='2022' else '2025-08-29'),'bounded window required')
        self.execution_grant=dict(path=str(Path(path).resolve()),sha256=sha(path))
    def execution_guard(self,day):
        E.require(self.execution_grant is not None,'PREPARATION ONLY: no account event authorized')
        g=read(self.execution_grant['path'])
        E.require(sha(self.execution_grant['path'])==self.execution_grant['sha256'] and g['runtime_sha256']==sha(__file__) and g['base_adapter_sha256']==sha(V1.__file__),'v2 grant changed')
        E.require(g['start']<=day<=g['end'] and (day in self.inputs.days or day in M.P.EXPECTED[self.window]),'outside local bounded grant')
