"""Original fee engine component/partial checks only; zero Account/window replay."""
from pathlib import Path
from decimal import Decimal as D
from dataclasses import replace
import json,hashlib,datetime
import cost15_compat as K
O=Path(__file__).resolve().parent
RULES=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 assert not(O/'COST15_PURE_CHECKS.json').exists(),'no silent repeated attempt'
 freeze=dict(at_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),before_new_fee_checks=True,sources={str(p):sha(p)for p in[Path(__file__),O/'PROTOCOL.txt',O/'cost15_compat.py',RULES]})
 (O/'PRE_COST_CHECK_FREEZE.json').write_text(json.dumps(freeze,indent=2)+'\n')
 FC=K.NativeFeeSchedule.__post_init__.__globals__['FeeComponent'];records=[];comparisons=0
 for venue,versions in json.loads(RULES.read_text())['fee_versions'].items():
  for version in versions:
   z=version['schedule'];components=tuple(FC(**r)for r in z['components']);base=K.NativeFeeSchedule(z['schedule_id'],components);cost=K.StressFeeSchedule(base.schedule_id,components)
   scaled=tuple(replace(c,rate=D(c.rate)*(D('1.5')if c.stress_rate else 1),minimum_local=D(c.minimum_local)*(D('1.5')if c.stress_minimum else 1),maximum_local=None if c.maximum_local is None else D(c.maximum_local)*(D('1.5')if c.stress_maximum else 1),stress_rate=False,stress_minimum=False,stress_maximum=False)for c in components)
   ref=K.NativeFeeSchedule(base.schedule_id,scaled)
   for side in('buy','sell'):
    for mult in(1,2,D('1.5')):
     paid={};accrued={};rp={};ra={}
     for q in(100,100,2000):
      local=D(q)*D(10);actual=cost.incremental(side,local,paid,accrued,mult,shares=q,par_value=D(1));target=ref.incremental(side,local,rp,ra,1,shares=q,par_value=D(1))if mult==D('1.5')else base.incremental(side,local,rp,ra,mult,shares=q,par_value=D(1));assert actual==target
      ac=cost.rate_accrual(side,local,mult,shares=q,par_value=D(1));rc=ref.rate_accrual(side,local,1,shares=q,par_value=D(1))if mult==D('1.5')else base.rate_accrual(side,local,mult,shares=q,par_value=D(1));assert ac==rc
      for k,v in actual.items():paid[k]=paid.get(k,D(0))+v
      for k,v in target.items():rp[k]=rp.get(k,D(0))+v
      for k,v in ac.items():accrued[k]=accrued.get(k,D(0))+v
      for k,v in rc.items():ra[k]=ra.get(k,D(0))+v
      comparisons+=1
   records.append(dict(venue=venue,from_day=version['from'],to_day=version['to'],schedule_id=base.schedule_id,components=[dict(name=c.name,rate=str(c.rate),stress_rate=c.stress_rate,minimum=str(c.minimum_local),stress_minimum=c.stress_minimum,stress_maximum=c.stress_maximum,amount_basis=c.amount_basis,basis=c.basis,side=c.side)for c in components]))
 assert all(sha(p)==h for p,h in freeze['sources'].items())
 out=dict(status='PURE_FEE_PARTIAL_ALGEBRA_AND_SOURCE_INVERSE_PASS_NO_ACCOUNTS',component_schedule_versions=len(records),incremental_comparisons=comparisons,source_receipt=K.source_receipt(),records=records,native_original_cost1_and_cost2_exact=True,cost15_matches_same_original_engine_on_once_scaled_flagged_components=True,new_accounts=0,actual_stress_execution_window_NOT_YET_TESTED=True)
 (O/'COST15_PURE_CHECKS.json').write_text(json.dumps(out,indent=2)+'\n')
 for name in['FEE_ORIGINAL','FEE_DERIVED','BASE_ORIGINAL','BASE_DERIVED','FAST_ORIGINAL','FAST_DERIVED','OPEN_ORIGINAL','OPEN_DERIVED']:(O/(name+'.py.txt')).write_text(getattr(K,name))
 print('COST15_PURE_PASS',len(records),comparisons)
if __name__=='__main__':main()
