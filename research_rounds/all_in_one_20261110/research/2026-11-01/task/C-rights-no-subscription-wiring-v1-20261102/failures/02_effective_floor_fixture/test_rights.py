from pathlib import Path
import copy,hashlib,json,pickle,subprocess,sys,unittest
from synthetic_runner import *
from rights_wiring import UnsupportedRights,validate_rights,conservation_bytes,state_value,canonical
OUT=HERE/'synthetic-results';OUT.mkdir(exist_ok=True)
def full(r):return hashlib.sha256(canonical(state_value(r)).encode()).hexdigest()

class RightsTests(unittest.TestCase):
 def test01_no_holding_and_exact_duplicate(self):
  r,s=fixture();install(r,s);before=conservation_bytes(r);x=r.corporate_actions('2025-07-03');self.assertEqual(x['status'],'observed_no_subscription');self.assertEqual(before,conservation_bytes(r));self.assertEqual(r.account.quantity(s),0)
  done=full(r);self.assertEqual(r.corporate_actions('2025-07-03')['status'],'already_applied');self.assertEqual(done,full(r));self.assertEqual(len(r.action_log),1)
 def test02_held_both_modes_and_three_coordinate_domains(self):
  for mode in ['C10','C_BATCH20']:
   with self.subTest(mode=mode):
    r,s=fixture(mode);close(r,s,0);r.event(op(1),is_open=True);a=r.account;self.assertGreater(a.quantity(s),0);oldq=a.quantity(s);cash=a.available;z=a.live(s)[0];oldstored=z['floor'];oldraw=a.raw_floor(z);oldratio=a.share_ratio[s]
    e=install(r,s);before=conservation_bytes(r);r.corporate_actions('2025-07-03');self.assertEqual(before,conservation_bytes(r));self.assertEqual(a.quantity(s),oldq);self.assertEqual(a.available,cash);self.assertEqual(a.share_ratio[s],oldratio);self.assertEqual(z['floor'],oldstored)
    self.assertEqual(a.raw_floor(z),oldstored/a.facts.factor(s,r.last_completed_event));self.assertNotEqual(a.facts.factor(s,r.last_completed_event),E.D(e['signal_split_ratio']));self.assertNotEqual(a.raw_floor(z),oldraw/E.D(e['signal_split_ratio']));r.assert_observers()
 def test03_raw_pending_and_unsubmitted_C_authority_preserved(self):
  r,s=fixture('C_BATCH20');close(r,s,0);self.assertTrue(r.account.pending);self.assertTrue(any(r.active['Q'].values()));install(r,s,'2025-07-02');before=conservation_bytes(r);r.corporate_actions('2025-07-02');self.assertEqual(before,conservation_bytes(r));self.assertFalse(r.account.buys);r.assert_observers()
 def test04_reserved_buy_and_deadline_preserved(self):
  r,s=fixture('C_BATCH20');close(r,s,0);r.event(op(1),is_open=True,capacities={s:0});self.assertIn(s,r.account.buys);old=copy.deepcopy(E.asdict(r.account.buys[s]));install(r,s);before=conservation_bytes(r);r.corporate_actions('2025-07-03');self.assertEqual(before,conservation_bytes(r));self.assertEqual(E.asdict(r.account.buys[s]),old);r.assert_observers()
 def test05_pending_sell_locks_and_New_Carry_preserved(self):
  for mode in ['C10','C_BATCH20']:
   with self.subTest(mode=mode):
    r,s=fixture(mode);close(r,s,0);r.event(op(1),is_open=True);close(r,s,1,False);self.assertIn(s,r.account.exits);self.assertTrue(r.account.policy.locks);install(r,s);before=conservation_bytes(r);r.corporate_actions('2025-07-03');self.assertEqual(before,conservation_bytes(r));r.assert_observers()
 def test06_changed_same_identity_atomically_refused(self):
  r,s=fixture();install(r,s);r.corporate_actions('2025-07-03');r.inputs.packets['2025-07-03'][0]['raw_text']='different source packet';before=full(r)
  with self.assertRaises(UnsupportedRights):r.corporate_actions('2025-07-03')
  self.assertEqual(full(r),before)
 def test07_same_batch_duplicates_once(self):
  r,s=fixture();e=install(r,s);r.inputs.packets['2025-07-03']=[e,copy.deepcopy(e)];r.corporate_actions('2025-07-03');self.assertEqual(len(r.action_log),1);self.assertEqual(len(r.no_subscription_actions),1)
 def test08_unknown_metadata_all_rejected_before_refresh(self):
  mutations=[('holder_election',None),('classification','unknown'),('split_ratio','1.30'),('cash_per_old_share','-6'),('rights_ratio',None),('subscription_price','NaN'),('signal_split_ratio','1.15'),('signal_cash_per_old_share','0'),('volume_split_ratio','1.30'),('known_action_date','2025-07-04'),('source_id',''),('modeling_basis',None)]
  for key,value in mutations:
   with self.subTest(field=key):
    r,s=fixture();install(r,s);r.inputs.packets['2025-07-03'][0][key]=value;before=full(r)
    with self.assertRaises((UnsupportedRights,KeyError,UnsupportedInput)):r.corporate_actions('2025-07-03')
    self.assertEqual(full(r),before)
  r,s=fixture();install(r,s);del r.inputs.packets['2025-07-03'][0]['signal_split_ratio'];before=full(r)
  with self.assertRaises(UnsupportedRights):r.corporate_actions('2025-07-03')
  self.assertEqual(full(r),before)
 def test09_unknown_factor_no_position_also_refused(self):
  for factor in [None,'NaN','0','-1']:
   with self.subTest(factor=factor):
    r,s=fixture();install(r,s);r.inputs.facts[s,'2025-07-03']['factor']=factor;before=full(r)
    with self.assertRaises(UnsupportedRights):r.corporate_actions('2025-07-03')
    self.assertEqual(full(r),before)
 def test10_unknown_batch_member_does_not_apply_first(self):
  r,s=fixture();e=install(r,s);other=copy.deepcopy(e);other['source_id']='different';other['subscription_price']=None;r.inputs.packets['2025-07-03'].append(other);before=full(r)
  with self.assertRaises(UnsupportedRights):r.corporate_actions('2025-07-03')
  self.assertEqual(full(r),before)
 def test11_observer_or_coordinate_refusal_rolls_back(self):
  for fault in ['observer','factor']:
   with self.subTest(fault=fault):
    r,s=fixture();install(r,s)
    if fault=='observer':r.observer_fault=True
    else:r.account.market.factor_fault=True
    before=full(r)
    with self.assertRaises(ValueError):r.corporate_actions('2025-07-03')
    self.assertEqual(full(r),before)
 def test12_unknown_live_protection_rejected_atomically(self):
  r,s=fixture();close(r,s,0);r.event(op(1),is_open=True);install(r,s);r.account.facts.floors[s]=None;before=full(r)
  with self.assertRaises(Exception):r.corporate_actions('2025-07-03')
  self.assertEqual(full(r),before)
 def test13_ordinary_delegation_and_mixed_refusal(self):
  r,s=fixture();e=install(r,s);ordinary=dict(e,classification='ordinary_cash_and_pro_rata_bonus',cash_per_old_share='0.10',split_ratio='1')
  self.assertEqual(r.inputs.check_action_support(ordinary,[])['ready'],True);r.inputs.packets['2025-07-03']=[ordinary];self.assertEqual(r.corporate_actions('2025-07-03'),'original_ordinary_delegate')
  r.inputs.packets['2025-07-03']=[ordinary,e];before=full(r)
  with self.assertRaises(UnsupportedRights):r.corporate_actions('2025-07-03')
  self.assertEqual(full(r),before)
 def test14_new_past_action_cannot_rewind(self):
  r,s=fixture();install(r,s);r.last_completed_event=cl(2);before=full(r)
  with self.assertRaises(UnsupportedRights):r.corporate_actions('2025-07-03')
  self.assertEqual(full(r),before)
 def test15_checkpoint_restore_and_crossprocess_duplicate(self):
  for mode in ['C10','C_BATCH20']:
   with self.subTest(mode=mode):
    r,s=fixture(mode);close(r,s,0);r.event(op(1),is_open=True);install(r,s);r.corporate_actions('2025-07-03');path=OUT/(mode+'.pkl');r.checkpoint(path);restored=SyntheticRightsRunner.restore(path);before=full(restored);self.assertEqual(restored.corporate_actions('2025-07-03')['status'],'already_applied');self.assertEqual(full(restored),before);self.assertEqual(conservation_bytes(restored),conservation_bytes(r))
    done=subprocess.run([sys.executable,'-B',str(HERE/'restore_synthetic.py'),str(path)],cwd=HERE,capture_output=True,text=True);self.assertEqual(done.returncode,0,done.stderr);(OUT/(mode+'-crossprocess.json')).write_text(done.stdout)
 def test16_input_adapter_accepts_rights_and_ordinary_guard_unchanged(self):
  r,s=fixture();e=install(r,s);self.assertTrue(r.inputs.check_action_support(e,[101])['ready']);bad=dict(e,classification='ordinary_cash_and_pro_rata_bonus',split_ratio='1.15')
  with self.assertRaises(UnsupportedInput):r.inputs.check_action_support(bad,[101])
 def test17_second_signal_ratio_is_not_share_ratio(self):
  r,s=fixture();close(r,s,0);r.event(op(1),is_open=True);oldq=r.account.quantity(s);install(r,s,ratio='0.15',price='14.43');before=conservation_bytes(r);r.corporate_actions('2025-07-03');self.assertEqual(before,conservation_bytes(r));self.assertEqual(oldq,r.account.quantity(s));self.assertEqual(r.account.share_ratio[s],1)

if __name__=='__main__':unittest.main(verbosity=2)
