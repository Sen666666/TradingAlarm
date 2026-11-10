"""Pure quote/resource proposals; never constructs an Account or calls an event."""
from pathlib import Path
import copy,json,unittest,subprocess,sys
from decimal import Decimal as D
from dataclasses import asdict
import quote_package as P
from prepare_cases import O,load,save

def fixture():
    known='2025-07-01T15:10:00+08:00';at='2025-07-02T09:30:00+08:00';end='2025-07-02T15:10:00+08:00'
    def rec(s):return dict(event_id='synthetic|'+s,sid=s,source='synthetic_explicit_receipt',source_binding='fixture-v1',payload_sha256=P.digest(s),start='2025-06-30T15:10:00+08:00',end=known,confirmed=known,deadline=end,structure=[s,0,'epoch',True],scale='21',market_context='synthetic-context')
    parent=dict(known_at=known,deadline=end,Q={'A':500,'B':500},D={'OLD':3000},receipt_bindings={s:rec(s) for s in ['A','B']});parent['certificate_id']=P.digest(parent)
    fees=asdict(P.N.fees(P.instant(at),False));regular=asdict(P.N.quantity(P.instant(at),False));star=asdict(P.N.quantity(P.instant(at),True))
    h=dict(mark='15',floor='14.5',ratio='1',cursor=known,quantity=3000,source='synthetic_quote_asof')
    lock=dict(eid='opp-1',lot=1,sid='OLD',q0='3000',e0='1500',ratio='1',remaining=3000,h=h,reason='actionable_S_funding',native_exit='old-sell',extinguished_event=None)
    qs={s:dict(price='15' if s=='OLD' else '20',known_at=at,session=at[:10],source='synthetic_open_print',kind='current_open_print') for s in ['OLD','A','B']}
    specs={s:dict(quantity=star if s=='B' else regular,fees=fees) for s in qs}
    demands=[dict(sid=s,sector='NEW',use='S',role='mobile',pool='confirmed',priority=[i,s],receipt=rec(s),deadline=end,i_valid=True,stock_q=True,permission_valid=True,floor='19',industry_target='80000',quantity=specs[s]['quantity'],fees=fees,authority=dict(filled=0,permanent_reduction=0,pending=0,order_bound=False)) for i,s in enumerate(['A','B'])]
    donors=[dict(layer=1,sid='OLD',role='mobile',original_cap=3000,max_remaining=3000,sellable_qty=3000,lock_ids=['opp-1'],mixed_mandatory=False,submitted_unacked=0,quantity=regular,fees=fees,paid={},accrued={})]
    return dict(case='SYNTHETIC_NOT_HISTORICAL',parent=parent,trusted_parent_id=parent['certificate_id'],at=at,quote_session=at[:10],decision_nav='100000',
        state=dict(available='10000',non_inventory_equity='10000',decision_nav='100000',consumed_receipts=[],lots=[dict(id=1,sid='OLD',sector='OLDSEC',pool='confirmed',role='mobile',qty=6000,floor='14.5',locks=[lock])],pending_rows=[],pending_orders={},receiver_responsibilities=[],other_goal_cash_encumbrance='0'),
        quotes=qs,specs=specs,demands=demands,donors=donors,parent_D_layers={1:3000},frozen_donor_order=[1],frozen_priority={d['sid']:d['priority'] for d in demands},permissions={'NEW':{'S':True,'holding_S':True},'G':{}},industry_targets={'NEW':'80000'})

class Cases(unittest.TestCase):
    evidence={}
    def runpure(self,name,x,on=True):
        before=P.digest(x);r=P.proposal(x,expected_sha256=before,enabled=on)
        self.assertEqual(before,P.digest(x));self.assertFalse(r['submit_allowed']);self.assertEqual(r['financial_events'],0)
        save(O/'results'/(name+'.json'),r);self.evidence[name]=dict(state=r['state'],Q=r.get('Q'),D=r.get('D'),input_unchanged=True)
        return r
    def test_real_Aug25(self):
        x=load(O/'inputs/Aug25_C20.json');off=self.runpure('Aug25_C20-OFF',x,False);on=self.runpure('Aug25_C20-ON',x)
        self.assertEqual(off['Q'],{'600536.SH':0,'002065.SZ':0});self.assertEqual(sum(off['D'].values()),9300)
        self.assertEqual(on['D'],{});self.assertEqual(on['Q'],off['Q'])
        self.assertGreater(D(on['bound']['minimum_old_risk']),D(on['bound']['frictionless_upper_risk_capacity']))
        self.assertEqual(on['actual_resource_totals']['risk'],'78539.81286427339004711359069')
    def test_real_Jan13(self):
        x=load(O/'inputs/Jan13_C10.json');off=self.runpure('Jan13_C10-OFF',x,False);on=self.runpure('Jan13_C10-ON',x)
        expected={'688800.SH':679,'002739.SZ':5800,'000719.SZ':9300,'003018.SZ':8100,'300199.SZ':6700,'600216.SH':100}
        self.assertEqual(off['Q'],expected);self.assertEqual(on['Q'],expected)
        self.assertTrue(all(D(v)>=0 for v in on['residuals'].values()));self.assertLess(sum(on['D'].values()),sum(off['D'].values()))
    def test_partial_minfee_STAR(self):
        x=fixture();x['demands'][0]['stock_q']=False
        # One existing aggregate donor order across two old layers. Each needed
        # sale is small enough to invoke the original 5-yuan commission floor.
        z=x['state']['lots'][0];z['qty']=3000;z['locks'][0].update(q0='1500',e0='750',remaining=200)
        other=copy.deepcopy(z);other['id']=2;other['locks'][0].update(eid='opp-2',lot=2);x['state']['lots'].append(other)
        x['parent_D_layers']={1:1500,2:1500};x['frozen_donor_order']=[1,2]
        first=x['donors'][0];first.update(original_cap=1500,max_remaining=200,sellable_qty=200)
        second=copy.deepcopy(first);second.update(layer=2,lock_ids=['opp-2']);x['donors'].append(second)
        r=self.runpure('partial_STAR_minimum_fee',x)
        self.assertEqual(r['Q']['A'],0);self.assertGreaterEqual(r['Q']['B'],200);self.assertLess(r['Q']['B'],500)
        self.assertEqual(len(r['D']),2);self.assertTrue(all(D(v)>=0 for v in r['residuals'].values()))
        q=sum(r['D'].values());p=D('15')*(1-P.N.LR.SLIP)
        actual=sum((D(v['fee']) for v in r['conditional_parts']),D(0))
        self.assertEqual(actual,P.fee(q,p,first['fees'],'sell'))
        self.assertLess(actual,sum((P.fee(v,p,first['fees'],'sell') for v in r['D'].values()),D(0)))
        self.assertFalse(P.donor_prefix_ok(x,{1:100,2:200}))
        y=copy.deepcopy(x);y['quotes']['B']['price']='60'
        z=self.runpure('STAR_below_200_rejected',y);self.assertEqual(z['Q']['B'],0);self.assertEqual(z['D'],{})
    def test_unacked_mandatory_and_failures(self):
        x=fixture();x['demands'][0]['stock_q']=False;x['demands'][1]['permission_valid']=False;x['donors'][0]['submitted_unacked']=3000
        z=copy.deepcopy(x['state']['lots'][0]);z.update(id=7,sid='STOP',sector='STOPSEC',qty=100)
        z['locks'][0].update(eid='mandatory-7',lot=7,sid='STOP',q0='100',e0='50',remaining=100,reason='CP1_old_line_exit',native_exit='stop-sell');x['state']['lots'].append(z)
        x['quotes']['STOP']=dict(x['quotes']['OLD']);x['specs']['STOP']=x['specs']['OLD']
        r=self.runpure('unacked_opportunity_mandatory_kept',x)
        self.assertEqual(r['D'],{});self.assertEqual(r['cancel_ack_required'],{'1':3000});self.assertEqual(r['mandatory_exit_obligations'][0]['remaining'],100)
        self.assertGreater(D(r['actual_resource_totals']['risk']),0);self.assertEqual(r['actual_releases'],{'cash':'0','risk':'0'})
        # A proposed donor fill is never actual cash. A failed sale keeps the
        # original snapshot, while a known invalid receiver stops further D.
        self.assertEqual(x['state']['available'],'10000')
        y=copy.deepcopy(x);y['donors'][0]['mixed_mandatory']=True
        u=self.runpure('mixed_partial_explicit_unsupported',y);self.assertIn('UNSUPPORTED',u['state']);self.assertEqual(len(u['mandatory_exit_obligations']),1)
    def test_authority_pending_not_double_subtracted(self):
        p={'Q':{'S':1000}};s=dict(filled=200,permanent_reduction=0,pending=500)
        self.assertEqual(P.authority_remaining(p,'S',s),dict(total_remaining=800,pending_commitment=500,new_quantity_cap=300))
        x=fixture();d=x['demands'][1];d['authority']=dict(filled=200,permanent_reduction=0,pending=500,order_bound=True)
        x['parent']['Q']['B']=1000;x['parent']['certificate_id']=P.digest({k:v for k,v in x['parent'].items() if k!='certificate_id'});x['trusted_parent_id']=x['parent']['certificate_id']
        x['state']['pending_orders']={'B':dict(order_id='original-pending',remaining_shares=500,fee_reserved_cny='5',parent_id=x['parent']['certificate_id'],receipt_id=d['receipt']['event_id'])}
        x['state']['pending_rows']=[dict(id='original-pending',sid='B',sector='NEW',pool='confirmed',role='mobile',qty=500,capital='9000',risk='500',reserve='9005')]
        x['demands'][0]['stock_q']=False
        r=self.runpure('pending_500_retained_new_300',x)
        self.assertEqual(r['authority_remaining']['B']['total_remaining'],800);self.assertEqual(r['authority_remaining']['B']['new_quantity_cap'],300)
        self.assertEqual(r['retained_pending']['B']['remaining_shares'],500);self.assertEqual(r['Q']['B'],0)
        bad=copy.deepcopy(x);bad['state']['pending_orders']['B']['remaining_shares']=300
        with self.assertRaises(ValueError):P.proposal(bad,expected_sha256=P.digest(bad))
    def test_unknown_tamper_and_restart(self):
        x=fixture();x['quotes']['B']['kind']='stale_valuation'
        u=self.runpure('UNKNOWN_no_cap_freeze',x);self.assertIsNone(u['Q']);self.assertFalse(u['freeze_quantity_caps']);self.assertFalse(u['receipt_consumed'])
        missing=fixture();missing['demands'][0]['stock_q']=None
        self.assertFalse(self.runpure('UNKNOWN_Q_not_false',missing)['freeze_quantity_caps'])
        x['quotes']['B']['kind']='current_open_print';r=self.runpure('UNKNOWN_later_quote_can_recheck',x);self.assertGreater(r['Q']['B'],0)
        self.assertEqual(P.proposal(x,expected_sha256=P.digest(x)),r)
        bad=copy.deepcopy(x);bad['parent']['Q']['B']+=1
        with self.assertRaises(ValueError):P.proposal(bad,expected_sha256=P.digest(x))
        with self.assertRaises(ValueError):P.proposal(bad,expected_sha256=P.digest(bad))
        future=copy.deepcopy(x);future['quotes']['B']['known_at']='2025-07-03T09:30:00+08:00'
        self.assertEqual(self.runpure('future_quote_UNKNOWN',future)['state'],'UNKNOWN')
        bad=copy.deepcopy(x);bad['quotes']['B']['volume']=1234
        with self.assertRaises(ValueError):P.proposal(bad,expected_sha256=P.digest(bad))
        used=fixture();used['state']['consumed_receipts']=[d['receipt']['event_id'] for d in used['demands']]
        self.assertEqual(sum(self.runpure('consumed_receipts_no_new_grant',used)['Q'].values()),0)
        save(O/'inputs/restore_fixture.json',x)
        subprocess.run([sys.executable,'-B',str(O/'verify_one.py'),str(O/'inputs/restore_fixture.json'),P.digest(x),str(O/'results/restored_fixture.json')],check=True,capture_output=True,text=True)
        self.assertEqual(json.loads((O/'results/restored_fixture.json').read_text()),r)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Cases);result=unittest.TextTestRunner(verbosity=2).run(suite)
    save(O/'TEST_RESULTS.json',dict(success=result.wasSuccessful(),tests_run=result.testsRun,failures=[str(v) for v in result.failures],errors=[str(v) for v in result.errors],cases=Cases.evidence,financial_events=0,native_order_callbacks_tested=False))
    raise SystemExit(0 if result.wasSuccessful() else 1)
