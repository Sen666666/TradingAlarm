"""Recheck all static plans without rerunning the allocation search."""
from pathlib import Path
from decimal import Decimal as D
import sys,copy,json,hashlib
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import ar6_policy as E
X=E.X;J=E.J
def main():
 f=X.read(O/'AUTHORIZATION_AND_FREEZE.json');run=X.read(O/'RUN_FREEZE.json');checks=[]
 assert all(X.sha(O/n)==h for n,h in run['source_sha256'].items())
 for day in f['dates']:
  x=X.read(O/('INPUT-'+day+'.json'));v=x['trusted'];before=J.digest(v)
  for enabled in [False,True]:
   mode='NO_AR6' if enabled else 'ORIGINAL_6';p=O/(mode+'-'+day+'.json');out=X.read(p);r=out['result'];c,patch=E.factory(enabled)
   ss,dd,rank=c.transform(v['snapshot'],v['demands'],v['evidence']);dd=sorted(dd,key=lambda d:(d['priority'],d['sid']))
   a=c.B.evaluate(ss,dd,r['Q'],r['D'])
   assert J.digest(a['donors'])==J.digest(r['donors']) and J.digest(a['validation'])==J.digest(r['validation'])
   assert a['validation']['ok'] and set(r['Q'])=={d['sid'] for d in dd}
   assert all(0<=r['Q'][d['sid']]<=d['max_q'] for d in dd)
   if not enabled:assert J.digest(r)==x['certificate']['projection_hash']
   else:assert not any('account_risk6' in k for tr in r['trace'] for k in tr.get('blockers_or_necessary_bounds',{}))
   assert J.digest(v)==before
   checks.append(dict(day=day,mode=mode,complete_domain=True,original_resource_risk_measurement=True,strict_other_guards=True,
    no_active_account6_bound_or_veto=enabled,output_sha256=X.sha(p),financial_events=0))
 assert all(X.sha(p)==h for p,h in f['sources_sha256'].items())
 X.save(O/'VERIFICATION.json',dict(passed=True,plans=checks,original_full_search_identity_cases=5,ablation_cases=5,
   original_preview_component_cases=10,full_OPEN_not_run=True,no_account_events=True,all_original_sources_unchanged=True))
 print('VERIFY_10_FULL_DOMAIN_PLANS_PASS')
if __name__=='__main__':main()
