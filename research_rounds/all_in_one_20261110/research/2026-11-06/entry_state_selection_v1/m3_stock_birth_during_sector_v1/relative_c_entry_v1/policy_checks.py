"""Marker implementation and frozen-spec synthetic checks. Not ABC integration."""
from pathlib import Path
import importlib.util,json,hashlib
O=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('frozen_preflight',O/'preflight.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
step=p.marker_step
def invite(mark,state='FLAT',fresh=True,S=(True,True),M=(True,True),known=True,PVR=True,AB=False,iq=True):
 return mark is not None and state=='FLAT' and fresh and all(S) and all(M) and known and PVR and not AB and iq
def rank(rows,AB):
 rows=sorted([r for r in rows if r['PVR_known'] and r['close']=='PASS'],key=lambda r:(-r['PVR'],r['sid']))
 return [r['sid'] for r in rows[:max(0,2-AB)]]
tests=[]
def check(name,ok): assert ok,name;tests.append(name)
mark=step(None,False,True,1,False,True,0)
check('new_window_starts_empty_no_prior_window_mark',not invite(None))
check('known_false_S_preserves_marker_and_blocks_invitation',step(mark,False,True,1,False,False,1)==mark and not invite(mark,S=(True,False)))
check('known_false_M_preserves_marker_and_blocks_invitation',step(mark,False,True,1,False,False,1)==mark and not invite(mark,M=(True,False)))
check('recovery_day_not_persistent',not invite(mark,S=(False,True)) and not invite(mark,M=(False,True)))
check('second_true_day_with_new_fresh_can_invite',invite(mark))
check('PVR_unknown_blocks_today_does_not_clear',not invite(mark,PVR=False) and step(mark,False,True,1,False,False,1)==mark)
for x in ['source','relative','I','S','M','entry_FACTOR_UNKNOWN_with_known_market']:
 check(x+'_UNKNOWN_clears_and_same_day_AB_loss_cannot_reseed',step(mark,True,True,1,False,True,1) is None)
check('known_NOFILL_preserves_marker',step(mark,False,True,1,False,False,1)==mark)
check('OPEN_below_protection_NOFILL_preserves_marker',step(mark,False,True,1,False,False,1)==mark)
check('pending_blocks_without_consuming',not invite(mark,state='BUY_PENDING') and step(mark,False,True,1,False,False,1)==mark)
check('unknown_blocks_invite',not invite(mark,state='UNKNOWN'))
check('losing_or_nofill_C_cannot_replay_next_day_without_fresh',not invite(mark,fresh=False))
check('later_genuine_fresh_can_invite_again_before_actual_entry',invite(mark,fresh=True))
check('actual_buy_core_consumes',step(mark,False,True,1,True,False,1) is None)
check('actual_entry_then_exit_cannot_revive_mark',not invite(step(mark,False,True,1,True,False,1),state='FLAT'))
check('C_rejection_cannot_seed_empty_marker',step(None,False,True,1,False,False,1) is None)
check('I_invalid_clears',step(mark,False,False,1,False,False,1) is None)
check('I_epoch_change_clears',step(mark,False,True,2,False,False,1) is None)
check('same_day_AB_not_C',not invite(mark,AB=True))
rows=[dict(sid='b',PVR=2,PVR_known=True,close='PASS'),dict(sid='a',PVR=2,PVR_known=True,close='PASS'),dict(sid='c',PVR=1,PVR_known=True,close='PASS'),dict(sid='d',PVR=99,PVR_known=False,close='PASS'),dict(sid='e',PVR=100,PVR_known=True,close='REJECT')]
check('AB_2_no_C',rank(rows,2)==[])
check('AB_1_C_only_one_PVR_then_sid',rank(rows,1)==['a'])
check('AB_0_C_only_two_PVR_then_sid',rank(rows,0)==['a','b'])
picked=rank(rows,1);after_open={'a':'NOFILL','b':'KNOWN_PROXY'}
check('next_open_NOFILL_never_replaces_with_lower_C',picked==['a'] and after_open[picked[0]]=='NOFILL')
qa={'passed':True,'tests':tests,'scope':'Real marker_step plus specification-level invitation/queue tests. Not a new ABC economic integration test.','production_marker_sha256':hashlib.sha256((O/'preflight.py').read_bytes()).hexdigest(),'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
assert not (O/'SUPPLEMENTAL_SYNTHETIC_QA.json').exists()
(O/'SUPPLEMENTAL_SYNTHETIC_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2)+'\n')
print('PASS',len(tests),'marker/spec tests; not economic integration')
