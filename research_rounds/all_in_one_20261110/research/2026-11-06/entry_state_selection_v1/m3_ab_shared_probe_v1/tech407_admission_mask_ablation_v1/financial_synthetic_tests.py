"""Original 13 source-definition synthetic regressions, plus masked-held ownership cases."""
from pathlib import Path
import json
import mask_bridge as M
from runner import save
import test_execution_indexed as T
E=M.E;HERE=Path(__file__).resolve().parent
s=E.bridge.load_original('2022')
results=T.test_suite(s)
# Synthetic source fields were deliberately altered by the above old test suite.
# Fresh source module for additional masked-owned behavior, no real day replay.
s=E.bridge.load_original('2022')
b,st,ds=T.buy_and_close(s)
b.__class__=M.AdmissionMaskBridge;b.admission_members=frozenset();b.mask_audit=[];b.open_mask_audit=[]
b.open_phase(ds[2])
assert st['added'] and st['add']>0 and b.pools[st['round_id']]=='confirmed'
st['exitpending']='SYNTHETIC_EXIT';b.last_close=ds[2];b.open_phase(ds[3])
assert st['core']==st['add']==0 and [a['side'] for a in s.actions]==['buy_core','buy_add','sell_all']
assert not b.open_mask_audit
results.append(dict(name='MASK_EXCLUDES_ALL_MEMBERS_BUT_EXISTING_NONMEMBER_ADD_AND_EXIT_CONTINUE',status='PASS'))
b,st,ds=T.fixture(s)
b.__class__=M.AdmissionMaskBridge;b.admission_members=frozenset({T.SID,'SYNTHETIC_THIRD'});b.mask_audit=[];b.open_mask_audit=[]
s.raw[T.SID][ds[1]]['raw_open']=94.
third=dict(st,sid='SYNTHETIC_THIRD',event_id='THIRD_NOT_SELECTED',PVR_score=-1.)
b.groups={ds[0]:s.pd.DataFrame([third])}
b.open_phase(ds[1])
assert not s.actions and not b.states and len(b.open_mask_audit)==1
assert not b.mask_audit
results.append(dict(name='SELECTED_INIT_OPEN_REJECT_DOES_NOT_REENTER_CLOSE_QUEUE_OR_BACKFILL_THIRD',status='PASS'))
out=HERE/'qa_financial_synthetic_attempt_01';out.mkdir(exist_ok=False)
save(out/'RESULT.json',dict(status='PASS',domain='SYNTHETIC_SOURCE_DEFINITIONS_ONLY_NO_2022_OR_2024_ECONOMIC_REPLAY',tests=results))
print('PASS_FINANCIAL_SYNTHETIC',len(results))
