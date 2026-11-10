"""Actual failed-checkpoint interface regressions, read-only; no account event."""
import copy, json, unittest
from dataclasses import asdict
import provider_fix1 as F
P=F.P;E=F.E;HERE=F.HERE
FAIL=HERE/'runs/2022-C10/failure-state.pkl'

def prepared():
 r=P.HistoricalRunner.restore(FAIL);at=r.last_completed_event;old=r.close_stages[at.isoformat()]['evidence']
 s,ds,_=r.provider(at,r.account.pending,old)
 r.__class__=F.FixedRunner
 r.legacy_cert_sources={cid:copy.deepcopy(c['source_binding']) for cid,c in r.authority.certificates.items()}
 r.core_rank_metadata=[];r.repair_import=None;r.account.owner=r
 return r,at,s,ds

class ProviderFixTests(unittest.TestCase):
 def test_original_cleanup_failure_reproduced(self):
  r,at,s,ds=prepared();ss,dd,_=E.C.transform(s,ds,r.close_stages[at.isoformat()]['evidence'])
  unknown=[z for z in s['lots'] if z['rank_key'] is None]
  self.assertIn('600664.SH',[z['sid'] for z in unknown])
  self.assertTrue(all(z['role']=='core' and not z['B_donor_eligible'] for z in unknown))
  with self.assertRaises(TypeError):E.B.trim_redundancy(ss,dd,{d['sid']:0 for d in dd},{})
 def test_only_nondonor_core_creation_key_changes(self):
  r,at,old,ods=prepared();before=E.digest(r.account.exported(at));s,ds,_=r.provider(at,r.account.pending,r.industry_input(at))
  self.assertEqual(ds,ods);self.assertEqual(E.digest(r.account.exported(at)),before)
  for a,b in zip(s['lots'],old['lots']):
   if a['rank_key']!=b['rank_key']:
    self.assertFalse(a['B_donor_eligible']);self.assertEqual(a['role'],'core')
    origin=r.account.supports[r.account.capital_meta[a['id']]['order']]
    self.assertEqual(a['rank_key'],list(origin['priority']))
   a['rank_key']=b['rank_key']
  self.assertEqual(s,old)
 def test_nondonor_rank_not_an_allocation_preference(self):
  r,at,_,_=prepared();s,ds,_=r.provider(at,r.account.pending,r.industry_input(at));ss,dd,_=E.C.transform(s,ds,r.industry_input(at))
  q={d['sid']:0 for d in dd};actual=E.B.trim_redundancy(ss,dd,q,{})
  altered=copy.deepcopy(ss)
  for z in altered['lots']:
   if z['role']=='core' and not z['B_donor_eligible']:z['rank_key']=[999999,z['sid']]
  self.assertEqual(actual,E.B.trim_redundancy(altered,dd,q,{}))
 def test_old_authorities_keep_real_original_source(self):
  r,_,_,_=prepared()
  for c in r.authority.certificates.values():
   old=copy.deepcopy(c);r.verify_native(c);self.assertEqual(c,old)
  self.assertTrue(r.authority.certificates)

if __name__=='__main__':unittest.main(verbosity=2)
