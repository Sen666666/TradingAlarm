"""Minimal no-event tests. Diagnostic copy only; no runner guard replaced."""
from dataclasses import dataclass
from pathlib import Path
import json,pickle,sys
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'C-rights-Jan13-action-v1-20261102'))
import state_snapshot as old
import fingerprint as fixed
@dataclass
class X:
 qty:int
@dataclass(slots=True)
class Slot:
 qty:int
tests={}
a=[X(11),X(22)];b=[X(11),X(999)]
tests['old_collision_reproduced']=old.digest(a)==old.digest(b)
tests['real_change_detected']=fixed.digest(a)!=fixed.digest(b)
tests['pickle_roundtrip_stable']=fixed.digest(a)==fixed.digest(pickle.loads(pickle.dumps(a)))
x=X(11);shared=[x,x];separate=[X(11),X(11)]
tests['actual_alias_preserved']=fixed.digest(shared)!=fixed.digest(separate)
tests['actual_alias_roundtrip_stable']=fixed.digest(shared)==fixed.digest(pickle.loads(pickle.dumps(shared)))
x.extra='first';h=fixed.digest(x);x.extra='second'
tests['dynamic_dataclass_field_observed']=h!=fixed.digest(x)
tests['slots_real_change_detected']=fixed.digest([Slot(11),Slot(22)])!=fixed.digest([Slot(11),Slot(999)])
tests['repeated_encoding_stable']=len({fixed.digest(a) for _ in range(20)})==1
import numpy as np
class HasDict:pass
@dataclass(slots=True)
class Hybrid(HasDict):
 qty:int
def hybrid(q):
 x=Hybrid(q);x.extra='kept';return x
tests['hybrid_dict_and_slots_real_change_detected']=fixed.digest(hybrid(22))!=fixed.digest(hybrid(999))
tests['object_ndarray_conversion_real_change_detected']=fixed.digest([np.array([11],dtype=object),np.array([22],dtype=object)])!=fixed.digest([np.array([11],dtype=object),np.array([999],dtype=object)])
array=np.array([22],dtype=object)
tests['ndarray_true_alias_preserved']=fixed.digest([array,array])!=fixed.digest([array,array.copy()])
tests['ndarray_true_alias_pickle_stable']=fixed.digest([array,array])==fixed.digest(pickle.loads(pickle.dumps([array,array])))
h=hybrid(22);h.__dict__['qty']=22;before=fixed.digest(h);h.qty=999
tests['slot_shadowed_by_same_named_dict_key_detected']=fixed.digest(h)!=before
tests['mixed_conversion_repeat_stable']=len({fixed.digest([np.array([11],dtype=object),hybrid(22),a]) for _ in range(20)})==1
(O/'FINGERPRINT_TESTS.json').write_text(json.dumps(dict(no_ACTION=True,passed=all(tests.values()),tests=tests),indent=2)+'\n')
assert all(tests.values()),tests
print(json.dumps(tests,indent=2))

import rights_wiring_v3 as R
assert R.state_value is fixed.norm, 'financial guard must use the unique corrected encoder'
assert fixed.ALLOWED==old.ALLOWED, 'field allowlist must not be widened'
import sys
sys.path.insert(0,str(O.parent/'C-rights-Jan12-upgrade-v1-20261102'))
import upgrade_runtime as U
class Probe(R.NoSubscriptionRunnerMixin,U.UpgradedRunner):pass
assert Probe.corporate_actions is R.NoSubscriptionRunnerMixin.corporate_actions
assert Probe.verify_native is U.UpgradedRunner.verify_native
assert Probe.step is U.UpgradedRunner.step
assert Probe.event is U.UpgradedRunner.event
(O/'WIRING_TESTS.json').write_text(json.dumps(dict(no_ACTION=True,passed=True,unique_encoder=True,complete_field_allowlist_unchanged=True,corrected_rights_method_selected=True,genuine_old_certificate_verifier_retained=True,OPEN_CLOSE_native_event_denials_retained=True),indent=2)+'\n')
