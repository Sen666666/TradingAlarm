from historical_binding import *
from dataclasses import replace
import argparse,time

def run(out):
 out=Path(out);out.mkdir(exist_ok=False);checks=[];t=time.monotonic()
 for window in ('2022','2025_26'):
  r=HistoricalRunner(window);a=r.account;first=r.inputs.days[0];at=iso(LD.known(first));a.market.refresh(at)
  assert not a.pending and not a.positions and not a.policy.k and not a.policy.losses and a.available==D(1000000)
  assert a.delay_events==0 and r.cursor>700000
  assert N.original_close_clock(first)==at
  assert all(N.original_close_clock(ob.at)<=at for ob in r.observations(first).values())
  assert N.original_close_clock(r.inputs.days[-1])>at
  assert all(r.f1[s['policy_scope']].scope==s['original_F1_scope'] and r.f1seq[s['policy_scope']]==s['scope_observation_sequence'] for s in r.inputs.seeds.values())
  packet=r.stock_packet(at);receipts=[row['receipt'] for row in packet.values() if row['receipt']]
  assert receipts and all(a.receipt_verified(c) for c in receipts)
  c=receipts[0];assert not a.receipt_verified(replace(c,source='original_stock_CP1_fixture_interface'))
  assert not a.receipt_verified(replace(c,payload_json='{}',payload_sha256=hashlib.sha256(b'{}').hexdigest()))
  assert not a.receipt_verified(replace(c,source_binding='0'*64))
  assert all(row['known_at']<=at for row in packet.values())
  assert a.market.quantity('688608.SH',at).buy_minimum==200
  assert a.market.quantity('300308.SZ',at).buy_minimum==100
  assert a.market.fees('300308.SZ',at).schedule_id!=a.market.fees('688608.SH',at).schedule_id
  assert all(s['confirmed_cursor']<at.date().toordinal() for s in r.inputs.seeds.values())
  before=digest(a.policy.exported());assert before==digest(a.policy.exported()) and not a.pending
  checks.append(dict(window=window,real_receipts=len(receipts),stocks=1709,typed_source_payload_guard=True,original_scope_ordinal_bootstrap=True,
   PVR_candidate_domain=len(r.mapping[-1]['priority']),dated_SSE_STAR_SZSE_rules=True,financial_events=0,plans=0))
  if window=='2025_26':
   row=r.inputs.stock('688608.SH','2025-07-02','OPEN');assert D(str(row['floors']['raw_conversion_factor_at_event']))!=D('1.4')
   action=next(a for a in r.inputs.actions('2025-07-02') if a['sid']=='688608.SH');assert D(action['split_ratio'])==D('1.4') and D(action['cash_per_old_share'])==D('1.2') and action['paid_at'] is None
  try:r.opening(None,iso(first+'T09:30:00+08:00'))
  except ValueError as e:assert 'fallback forbidden' in str(e)
  else:raise AssertionError('generated fill path survived real binding')
 IO.write_json(out/'GATE.json',dict(passed=True,checks=checks,seconds=time.monotonic()-t,financial_events=0,plans_created=0),encoder=N.encode)
 print(json.dumps(dict(passed=True,checks=len(checks),seconds=time.monotonic()-t)),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);args=p.parse_args();run(args.out)
