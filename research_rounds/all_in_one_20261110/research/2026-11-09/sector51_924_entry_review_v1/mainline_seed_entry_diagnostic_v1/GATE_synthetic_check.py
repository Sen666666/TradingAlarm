from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import ast,copy,hashlib,json,math
import pandas as pd
import numpy as np
O=Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1/mainline_seed_entry_diagnostic_v1')
source=O/'GATE_diagnose.py'
tree=ast.parse(source.read_text())
names={'dec','finite','tri','OR','lin','valid','make_state','event','preflight','cp_check_price','at_open','at_close','row','receipt_tri','bump','cp_state','failed_preflight'}
module=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
exec(compile(module,'EXTRACTED_EXACT_DIAGNOSTIC_FUNCTIONS','exec'))
MODEL_SHA256='85f21ad1622863645618f570b5f2e832558ebaca218ff2c71d0b4a0b545dd0bf'
Z=D(0);sid='SYNTHETIC';sector='SYNTHETIC_SECTOR';dates=pd.date_range('2024-01-01',periods=10)
raw=pd.DataFrame(index=dates,data=dict(raw_open=10.,raw_close=10.,adjustment_factor=1.,observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False,source_kind='S',source_path='P',segment_id='0'))
raw.loc[dates[0],'raw_open']=8.
fact=pd.DataFrame(index=dates,data=dict(i_target=1,i_floor=5.,close=10.))
cp=pd.DataFrame(index=dates,data=dict(receipt=False,candidate=float('nan')))
cp['receipt']=cp.receipt.astype(object)
cp.loc[dates[0]]=[True,9.];cp.loc[dates[2]]=[True,8.];cp.loc[dates[3]]=[True,11.];cp.loc[dates[4],'receipt']=None;cp.loc[dates[7]]=[True,9.]
frames={sid:raw};facts={sid:fact};cps={sid:cp};actions={sid:{}};admission={};adapter=defaultdict(list)
sec={(str(d.date()),sector):dict(state=1,M=1,S=1,F=0,E=1) for d in dates}
stock=lambda s,d:1
r=dict(sid=sid,signal_day='2024-01-01')
st=make_state(r);checks={}
o=at_close(st,'2024-01-01',sector);checks['receipt_CLOSE_does_not_use_earlier_same_day_OPEN']=o['CP_state']==1
raw.loc[dates[1],'raw_open']=8.
op=at_open(st,'2024-01-02');o=at_close(st,'2024-01-02',sector);checks['OPEN_breach_permanent_despite_CLOSE_rebound']=op['CP_state']==0 and o['CP_state']==0 and st['slot']['invalid']
at_open(st,'2024-01-03');o=at_close(st,'2024-01-03',sector);checks['new_receipt_replaces_invalid_slot']=o['CP_state']==1 and D(o['CP_floor'])==8
keep=st['slot']['id'];at_open(st,'2024-01-04');o=at_close(st,'2024-01-04',sector);checks['already_breached_receipt_keeps_previous_valid_single_slot']=o['CP_state']==1 and st['slot']['id']==keep
at_open(st,'2024-01-05');o=at_close(st,'2024-01-05',sector);checks['unknown_daily_receipt_is_UNKNOWN']=o['CP_state']==-1
at_open(st,'2024-01-06');o=at_close(st,'2024-01-06',sector);checks['explicit_false_does_not_repair_unknown_update_history']=o['CP_state']==-1 and st['slot']['id']==keep and st['cp_update_unknown']
raw.loc[dates[6],'observed_bar']=False;at_open(st,'2024-01-07');raw.loc[dates[6],'observed_bar']=True
sec[('2024-01-07',sector)]['F']=1;o=at_close(st,'2024-01-07',sector);checks['missing_OPEN_stays_CP_UNKNOWN_after_valid_CLOSE']=o['CP_state']==-1
checks['F_true_bypasses_CP_unknown_only_when_base_valid']=o['gate']==1 and o['base']=='PASS'
at_open(st,'2024-01-08');o=at_close(st,'2024-01-08',sector);checks['new_receipt_resets_unverifiable_history_suffix']=o['CP_state']==1 and not st['slot']['history_unknown']
safe=copy.deepcopy(st)
fact.loc[dates[7],'i_target']=0;o=at_close(st,'2024-01-08',sector);checks['original_I_false_cancels_and_clears_CP']=o['base']=='CANCEL' and st['slot'] is None;fact.loc[dates[7],'i_target']=1
st=copy.deepcopy(safe);raw.loc[dates[8],'source_path']='CHANGED';op=at_open(st,'2024-01-09');checks['source_change_cancels_and_clears_CP']=op['base']=='CANCEL' and st['slot'] is None;raw.loc[dates[8],'source_path']='P'
st=copy.deepcopy(safe);raw.loc[dates[8],'adjustment_factor']=1.1;actions[sid]['2024-01-09']={};admission[(sid,'2024-01-09')]={};adapter[(sid,'2024-01-09')]=[dict(factor_old='1',factor_new='1.1')]
floor=st['slot']['floor'];a=preflight(st,'2024-01-09');b=preflight(st,'2024-01-09')
checks['admitted_bridge_applied_once_per_day_and_no_CP_rescale']=a and b and len(st['bridges'])==1 and st['slot']['floor']==floor
st=copy.deepcopy(safe);del admission[(sid,'2024-01-09')];checks['unadmitted_factor_bridge_blocks_not_unknown']=not preflight(st,'2024-01-09') and st['blocked']=='UNADMITTED_EQUITY_OR_FACTOR'
# Boundary regressions do not touch real data or change the formula.
raw.loc[dates[8],'adjustment_factor']=1.;actions[sid]={};admission.clear();adapter.clear()
st=copy.deepcopy(safe);fact.loc[dates[8],'i_floor']=float('nan');o=at_close(st,'2024-01-09',sector)
checks['current_I_floor_missing_pauses_despite_old_ratcheted_I']=o['base']=='UNKNOWN' and st['ifloor']==D(5)
fact.loc[dates[8],'i_floor']=5.
st=copy.deepcopy(safe);raw['source_path']=raw.source_path.astype(object);raw.loc[dates[8],'source_path']=None;o=at_close(st,'2024-01-09',sector)
checks['unknown_source_pauses_not_cancels']=o['base']=='UNKNOWN' and st['cancelled'] is None and st['blocked'] is None
raw.loc[dates[8],'source_path']='P'
st=copy.deepcopy(safe);raw.loc[dates[8],'adjustment_factor']=float('nan');o=at_open(st,'2024-01-09')
checks['missing_factor_pauses_not_blocks']=o['base']=='UNKNOWN' and st['blocked'] is None
fact.loc[dates[8],'i_target']=0;o=at_close(st,'2024-01-09',sector)
checks['known_I_false_wins_over_missing_factor']=o['base']=='CANCEL' and st['slot'] is None
fact.loc[dates[8],'i_target']=1;raw.loc[dates[8],'adjustment_factor']=1.
st=copy.deepcopy(safe);frames[sid]=raw.drop(index=dates[8]);o=at_close(st,'2024-01-09',sector)
checks['missing_raw_row_is_unknown_without_keyerror']=o['base']=='UNKNOWN'
frames[sid]=raw
st=make_state(r);st['slot']=None;cp.loc[dates[0],'receipt']=None;o=at_close(st,'2024-01-01',sector);cp.loc[dates[1],'receipt']=False;raw.loc[dates[1],'raw_open']=10.;op=at_open(st,'2024-01-02');o=at_close(st,'2024-01-02',sector)
checks['unknown_update_without_existing_slot_stays_unknown']=op['CP_state']==-1 and o['CP_state']==-1 and st['slot'] is None
checks['receipt_must_be_explicit_boolean']=receipt_tri(1)==-1 and receipt_tri(0)==-1 and receipt_tri(True)==1 and receipt_tri(np.bool_(False))==0
checks['receipt_identity_binds_actual_model_hash']=safe['slot']['model_sha256']==MODEL_SHA256
checks['tri_OR_cases']=OR(1,-1)==1 and OR(-1,0)==-1 and OR(0,0)==0 and OR(-1,1)==1
assert all(checks.values()),checks
result=dict(result='PASS',checks=checks,exact_diagnostic_source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),synthetic_state_only=True,no_market_replay=True)
(O/'GATE_SYNTHETIC_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
