"""Synthetic ownership, payout, coordinate inheritance and fail-closed tests only."""
import engine as s
from engine import pd,D,copy,np
checks=[]
def test(name,v):assert v,name;checks.append(name)
rec=pd.Timestamp('2026-05-11');ex=pd.Timestamp('2026-05-12');pay=pd.Timestamp('2026-05-14')
e=dict(sid='UNIT',economic_event_id='UNIT_CASH',evidence_version='SYNTHETIC',coordinate_snapshot_day=rec,record_date=rec,ex_date=ex,pay_date=pay,d_cash=D('.055'),d_source=D('.0548'),factor_old=D(1),factor_new=D(100)/(D(100)-D('.0548')),previous_day=rec,entitlement_verified=True)
s.install_events([e]);s.reset(True)
st=dict(state='HELD',sid='UNIT',arm='A_UNION_B',round_id='UNIT_ROUND',core=100,add=20,cash=D(-12000),receivable=D(0),dividend_total=D(0),dividend_paid=D(0),exitpending='I_STRUCTURE_EXIT')
s.archives['UNIT_ROUND']=st;s.register({'UNIT':st},'A_UNION_B',rec);c=list(s.claims.values())[0]
test('record_close_owner',c['owner_round_id']=='UNIT_ROUND' and c['record_q']==120 and c['core_record_q']==100)
test('cash_amount_not_source',c['amount']==D('5.28') and c['core_amount']==D('4.4'))
s.register({'UNIT':st},'A_UNION_B',rec);test('duplicate_register_idempotent',len(s.claims)==1 and len(s.registrations)==1)
s.accrue_day('A_UNION_B',ex);s.accrue_day('A_UNION_B',ex);test('ex_open_once',st['receivable']==D('5.28') and st['dividend_total']==D('5.28') and len(s.claim_ledger)==1)
# Ownership persists even when live state is UNKNOWN or exited; only owner archive is touched.
st['core']=0;st['add']=0;st['state']='UNKNOWN';before=st['cash']+st['receivable'];s.pay_day('A_UNION_B',pay);s.pay_day('A_UNION_B',pay)
test('pay_after_exit_unknown_once',st['cash']+st['receivable']==before and st['receivable']==0 and c['settled'] and len(s.claim_ledger)==2)
test('pay_close_available_next_session',s.claim_ledger[-1]['available_from']>pay)
s.reset(True);s.register({},'A_UNION_B',rec);test('flat_zero_no_claim',not s.claims and list(s.snapshots.values())[0]['record_q']==0)
s.reset(True);s.register({'UNIT':{'state':'UNKNOWN'}},'A_UNION_B',rec);test('unknown_not_zero',not s.claims and list(s.snapshots.values())[0]['record_q'] is None)
z={'adjustment_factor':float(e['factor_new'])};p={'adjustment_factor':1.,'raw_close':100.}
test('coordinate_formula',s.coordinate_matches(e,z,p))
for col in ['adjustment_factor','raw_close']:
 for v in [np.nan,np.inf]:
  pp=dict(p);pp[col]=v;test('bad_coordinate_'+col+str(v),not s.coordinate_matches(e,z,pp))
# The source gate cannot silently accept hash changes, missing paths, or mutated candidate bytes.
f=s.O/'UNIT_HASH_FIXTURE.txt';f.write_text('frozen');h=s.sha(f);test('hash_match',s.verify_frozen_inputs({str(f):h}));f.write_text('drift')
try:s.verify_frozen_inputs({str(f):h});raise RuntimeError('hash drift accepted')
except AssertionError:checks.append('hash_drift_rejected')
try:s.verify_frozen_inputs({str(f)+'.missing':h});raise RuntimeError('missing hash accepted')
except AssertionError:checks.append('missing_path_rejected')
s.save(s.O/'CASH_UNIT_QA.json',dict(pass_=True,checks=checks,new_recovery_economic_runs=0));print('CASH_UNIT_PASS',len(checks))
