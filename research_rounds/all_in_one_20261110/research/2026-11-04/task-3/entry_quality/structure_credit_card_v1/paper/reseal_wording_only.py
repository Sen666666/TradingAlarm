"""Wording/interface correction only. Read saved artifacts; no numerical work."""
from pathlib import Path
import hashlib,json

O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(name,x):(O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
numeric_names=['NINE_ORIGINAL_PREFIX_ARITHMETIC.json','NINE_POINT_TABLE.csv','ORIGINAL_NINE_INPUTS.json','AGGREGATED_LIQUIDATION_REFERENCE.json','AGGREGATED_LIQUIDATION_REFERENCE.csv','STATIC_ARITHMETIC_CHECKS.json','CALCULATION_RECEIPT.json']
before={n:sha(O/n) for n in numeric_names}
protocol=O/'PROTOCOL_FREEZE.json'
previous_protocol_sha=sha(protocol)
previous_seal_sha=sha(O/'SEAL_RECEIPT.json')
assert not (O/'SUPERSEDED_PROTOCOL_CLOSE_HARDCAP.json').exists()
(O/'SUPERSEDED_PROTOCOL_CLOSE_HARDCAP.json').write_bytes(protocol.read_bytes())
(O/'SUPERSEDED_SEAL_BEFORE_WORDING_FIX.json').write_bytes((O/'SEAL_RECEIPT.json').read_bytes())
p=json.loads(protocol.read_text())
p['status']='EFFECTIVE_FROZEN_PAPER_PROTOCOL_OPEN_ONLY_SHARED_GATE'
p['quantity']='Add the shared credit gate only inside the original OPEN route.allowed/request. Keep the original signal i.cap and all other original gates. CLOSE credit-risk quantity is diagnostic only, not an additional hardcap. The existing nine OPEN values are unchanged because that diagnostic quantity does not bind any row, as established by OPEN_ONLY_GATE_INTERFACE_ADDENDUM.json. Report risk-only, stock10/original-slot cash necessary caps and conservative min(cap, original actually funded qty) separately. Other sector/pool/route grants remain unverified; no original grant is expanded.'
p['supersedes']=dict(path='SUPERSEDED_PROTOCOL_CLOSE_HARDCAP.json',sha256=previous_protocol_sha,reason='Withdraw only the additional CLOSE credit hardcap wording. All formulas, frozen inputs and numerical results are preserved. Historical arithmetic was executed under this older text; saved-table comparison proves its extra cap did not bind any of the nine OPEN results.')
p['effective_interface_addendum']=dict(path='OPEN_ONLY_GATE_INTERFACE_ADDENDUM.json',sha256=sha(O/'OPEN_ONLY_GATE_INTERFACE_ADDENDUM.json'))
p['legacy_numeric_field_labels']='CLOSE_frozen_cap and CLOSE_frozen_cap CSV labels in already-saved numerical artifacts are legacy diagnostic labels, not part of the effective admission interface. Numerical files are left byte-for-byte unchanged.'
save('PROTOCOL_FREEZE.json',p)
old='CLOSE先求整手cap，OPEN只能缩；stock10与同原reserve槽位现金必要门分列。'
new='CLOSE风险cap仅作诊断，主共享门仅在原OPEN route.allowed/request追加，保留原i.cap和其它旧门，不新增CLOSE信用硬cap；九点诊断cap均不绑定，OPEN条件上限不变。stock10与同原reserve槽位现金必要门分列。接口补件见[OPEN_ONLY_GATE_INTERFACE_ADDENDUM.json](OPEN_ONLY_GATE_INTERFACE_ADDENDUM.json)。'
old_footer='文件：PROTOCOL_FREEZE.json冻结主合同；'
new_footer='文件：[PROTOCOL_FREEZE.json](PROTOCOL_FREEZE.json)为有效主协议；[SUPERSEDED_PROTOCOL_CLOSE_HARDCAP.json](SUPERSEDED_PROTOCOL_CLOSE_HARDCAP.json)保留已被替代的额外CLOSE硬cap文字，历史算术与原收据不改；'
for name in ['READOUT.md','write_readout.py']:
 f=O/name;s=f.read_text();assert old in s and 'CLOSE冻结cap→OPEN条件cap' in s and old_footer in s
 s=s.replace(old,new).replace('CLOSE冻结cap→OPEN条件cap','CLOSE诊断cap→OPEN条件cap').replace(old_footer,new_footer)
 f.write_text(s)
after={n:sha(O/n) for n in numeric_names}
assert after==before
receipt=dict(status='PASS_WORDING_ONLY_EFFECTIVE_OPEN_GATE_RESEAL',script_sha256=sha(Path(__file__)),
 previous_protocol_sha256=previous_protocol_sha,previous_seal_sha256=previous_seal_sha,
 effective_protocol_sha256=sha(protocol),interface_addendum_sha256=sha(O/'OPEN_ONLY_GATE_INTERFACE_ADDENDUM.json'),
 byte_unchanged_numeric_sha256=after,numerical_recalculations=0,new_accounts=0,new_models=0,new_backtests=0,new_strategy_paths=0)
save('WORDING_ONLY_RESEAL_RECEIPT.json',receipt)
save('DELIVERABLE_SHA256.json',{f.name:sha(f) for f in sorted(O.iterdir()) if f.is_file() and f.name not in ['DELIVERABLE_SHA256.json','SEAL_RECEIPT.json']})
seal=dict(status='SEALED_NINE_FIXED_ORIGINAL_PREFIX_OPEN_ONLY_WORDING_CORRECTED',readout_sha256=sha(O/'READOUT.md'),
 arithmetic_sha256=sha(O/'NINE_ORIGINAL_PREFIX_ARITHMETIC.json'),protocol_sha256=sha(protocol),
 interface_addendum_sha256=sha(O/'OPEN_ONLY_GATE_INTERFACE_ADDENDUM.json'),wording_only_receipt_sha256=sha(O/'WORDING_ONLY_RESEAL_RECEIPT.json'),
 deliverable_sha256=sha(O/'DELIVERABLE_SHA256.json'),numerical_recalculations=0,new_models=0,new_accounts=0,new_backtests=0,new_paths=0)
save('SEAL_RECEIPT.json',seal)
print(json.dumps(seal,ensure_ascii=False))
print('seal_sha256',sha(O/'SEAL_RECEIPT.json'))
