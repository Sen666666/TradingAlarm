"""Authorized combined capital policy: no probe pool cap, new-probe industry 4%."""
from pathlib import Path
import ast,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'no_risk_ceilings_python_retry_v1'))
import no_risk_bridge as N
E=N.E;merge_hashes=N.merge_hashes
BASE_REASONS=N.DERIVATION['reasons']['derived_source']
def change_capital(t):
 body=t.body[0].body
 hits=[n for n in body if isinstance(n,ast.If) and any(isinstance(v,ast.Constant) and v.value=='pool_capital' for v in ast.walk(n))]
 assert len(hits)==1;body.remove(hits[0])
 assignments=[n for n in body if isinstance(n,ast.Assign) and ast.unparse(n.targets[0])=='frac']
 assert len(assignments)==1 and ast.unparse(assignments[0].value)=="D('.02') if proposal.pool == 'probe' else D('.10')"
 assignments[0].value.body.args[0]=ast.Constant(value='.04')
class CapitalPolicyBook(N.NoRiskBook):
 reasons=N.from_text(BASE_REASONS,change_capital,N.V.__dict__)
DERIVATION={'base_reasons':BASE_REASONS,'new_reasons':N.DERIVATION['reasons']['derived_source']}
_env=dict(E.__dict__);_env['ReserveBook']=CapitalPolicyBook
class CapitalPolicyBridge(N.NoRiskBridge):
 open_phase=N.derive(E.ExecutionBridge.open_phase,lambda t:None,_env)
def make_bridge(source,arm):
 assert arm=='unpooled_probe_sector4'
 return CapitalPolicyBridge(source,seed_cash=E.D('1200000'))
