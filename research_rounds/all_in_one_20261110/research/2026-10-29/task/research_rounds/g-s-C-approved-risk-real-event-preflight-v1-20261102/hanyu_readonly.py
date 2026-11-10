"""Extra parent-specified winner control; read old authorization/fill ONLY."""
from pathlib import Path
from decimal import Decimal as D
from fractions import Fraction as F
import pickle
import replay_runtime as X
E=X.E;R=X.HERE
SOURCE=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-2022-month-difference-readonly-20261102')
p=X.M.HERE/'runs/2022-C10/2022-01-12-CLOSE.pkl';side=X.read(p.with_suffix('.provenance.json'))
assert X.sha(p)==side['checkpoint_sha256'];r=pickle.loads(p.read_bytes())
assert type(r) is X.M.MonthRunner and r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity']
before=E.digest(X.snapshot(r));c=r.active;sid='300199.SZ';assert c['known_at'].startswith('2022-01-12') and c['Q'][sid]==6700
# Exactly one original trusted verifier call for this requested stock approval.
proof=X.R.approved_payload(r,c['certificate_id'],sid)
chain=X.read(SOURCE/'ACTUAL_CHAINS.json')[sid]
extract=X.read(SOURCE/'2022-C10-EXTRACT.json');check=X.read(SOURCE/'2022-C10-EXTRACT-CHECKS.json')
assert X.sha(SOURCE/'2022-C10-EXTRACT.json')==check['extract_sha256']
layer=next(v for v in chain['actual_layers']['C10'] if v['opened'].startswith('2022-01-13'))
assert layer['C_certificate']==c['certificate_id'] and layer['receipt_event']==proof['receipt']
trade=next(t for t in extract['account']['trades'] if t.get('receipt_id')==layer['buy_receipt'])
at=E.iso('2022-01-13T09:30:00+08:00');close_factor=r.account.facts.factor(sid,r.last_completed_event)
openrow=r.inputs.rows('facts',sid,'2022-01-13');open_factor=D(str(openrow['factor']))
floor=D(trade['floor'])/open_factor;price=D(trade['price']);risk=F(trade['shares'])*max(F(0),F(price)-F(floor))
raw=int(proof['R0']//(F(price)-F(floor))) if price>floor else 0
rule=r.account.market.quantity(sid,at);local_upper=rule.buy_floor(min(proof['Q0'],raw))
assert trade['shares']==6700 and D(trade['gross_cny'])==D(6700)*price
assert E.digest(X.snapshot(r))==before and X.sha(p)==side['checkpoint_sha256']
out=dict(scope='read-only requested winner control, not an actual R0 branch or Jan2022 replay',financial_events=0,
 original_checkpoint=str(p),original_checkpoint_sha256=X.sha(p),approved=proof,actual_entry=trade,close_factor=close_factor,open_factor=open_factor,actual_fill_floor_raw=floor,
 actual_initial_nominal_risk=str(risk),approved_nominal_risk_decimal=str(D(proof['R0'].numerator)/D(proof['R0'].denominator)),risk_multiple=str((D(risk.numerator)/D(risk.denominator))/(D(proof['R0'].numerator)/D(proof['R0'].denominator))),
 risk_only_upper_before_original_qty=raw,legal_upper_with_original_qty=local_upper,would_shrink_original_6700=local_upper<6700,
 original_exit=layer['sell_legs'],original_layer_closed_net=layer['realized_net'],C20_original_specific_C_authorization='no positive Jan12 authorization; R0 cannot invent it',
 no_new_profit_calculated=True,all_original_state_and_files_unchanged=True,sources={str(q):X.sha(q) for q in [p,SOURCE/'ACTUAL_CHAINS.json',SOURCE/'2022-C10-EXTRACT.json',SOURCE/'2022-C10-EXTRACT-CHECKS.json']})
X.save(R/'HANYU_READONLY.json',out);print('HANYU_READ_ONLY',proof['Q0'],local_upper,'risk multiple',out['risk_multiple'],'events0',flush=True)
