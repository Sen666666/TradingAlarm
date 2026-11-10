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
(O/'FINGERPRINT_TESTS.json').write_text(json.dumps(dict(no_ACTION=True,passed=all(tests.values()),tests=tests),indent=2)+'\n')
assert all(tests.values()),tests
print(json.dumps(tests,indent=2))

import rights_wiring_v2 as R
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
