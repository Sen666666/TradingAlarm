"""Saved actual branch JSON only; never advances/replays any financial event."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib
R=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text())
rows=[];details={};pending=[]
for mode in ['C10','C_BATCH20']:
 for day in ['2025-07-22','2025-07-23','2025-07-04','2025-07-30']:
  case=mode+'-'+day;on=R/'runs'/(case+'-on')/'ACTUAL_OPEN_COMPARISON.json'
  off=R/'runs'/(case+'-off')/'ACTUAL_OPEN_COMPARISON.json'
  if not off.exists():off=off.with_name('OFF_IDENTITY_READONLY.json')
  if not on.exists() or not off.exists():pending.append(case);continue
  x=read(on);b=read(off);assert b['off_complete_original_state_identity'] is True
  for bridge in [x['actual_bridge'],x['baseline_bridge']]:
   assert all(D(bridge[k])==0 for k in ['independent_nav_difference','cash_asset_difference','layer_cash_difference'])
  assert x['original_D_not_recomputed']
  def sums(fs,side):return sum((D(f['gross_cny']) for f in fs if f['side']==side),D(0))
  def fees(fs):return sum((D(f['fees_cny']) for f in fs),D(0))
  new=x['actual_all_fills'];old=x['baseline_all_fills']
  assert [f for f in new if f['side']=='sell']==[f for f in old if f['side']=='sell'],'R0 unexpectedly changed prior exits'
  crows=[]
  for z in x['C_authorization_rows']:
   q=z['original_approved'];nb=z['actual_branch'];ob=z['baseline'];risk=z['permanent_risk']
   if risk:
    from fractions import Fraction as F
    assert F(risk['spent'])<=F(risk['approved']['R0'])
   crows.append(dict(sid=z['sid'],Q0=q['Q0'],R0=q['R0'],old_reserved=ob['reserved'],new_reserved=nb['reserved'],old_fill=ob['filled'],new_fill=nb['filled'],old_order=ob['order'],new_order=nb['order'],spent=risk['spent'] if risk else None))
  details[case]=crows
  row=dict(case=case,source_close=day,actual_open=x['cursor'],OFF_original_identity=True,C_authorization_entries=len(crows),buygross_off=str(sums(old,'buy')),buygross_on=str(sums(new,'buy')),buygross_change=str(sums(new,'buy')-sums(old,'buy')),sellgross_unchanged=str(sums(new,'sell')),fees_off=str(fees(old)),fees_on=str(fees(new)),
    account_risk_off=x['baseline_bridge']['resources']['risk'],account_risk_on=x['actual_bridge']['resources']['risk'],capital_off=x['baseline_bridge']['resources']['capital'],capital_on=x['actual_bridge']['resources']['capital'],reserve_off=x['baseline_bridge']['resources']['reserve'],reserve_on=x['actual_bridge']['resources']['reserve'],buy_receipts_off=sum(f['side']=='buy' for f in old),buy_receipts_on=sum(f['side']=='buy' for f in new),new_funded_stocks=sorted({f['security_id'] for f in new if f['side']=='buy'}-{f['security_id'] for f in old if f['side']=='buy'}),lost_funded_stocks=sorted({f['security_id'] for f in old if f['side']=='buy'}-{f['security_id'] for f in new if f['side']=='buy'}),proof_source=str(on),not_continuous_strategy_return=True)
  rows.append(row)
(R/'PARTIAL_ACTUAL_READOUT.json').write_text(json.dumps(dict(completed_pairs=rows,C_stock_differences=details,pending_pairs=pending,no_financial_events_invoked=True),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(completed_pairs=len(rows),pending=pending),ensure_ascii=False))
for q in rows:print(q['case'],'buy',q['buygross_off'],'->',q['buygross_on'],'risk',q['account_risk_off'],'->',q['account_risk_on'])
