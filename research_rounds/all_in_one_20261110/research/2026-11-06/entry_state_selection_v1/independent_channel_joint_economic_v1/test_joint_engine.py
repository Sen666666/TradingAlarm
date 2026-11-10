"""G1 fictitious-policy and scheduling tests. No historical PRICE lifecycle runs."""
from copy import deepcopy
from decimal import Decimal as D
from pathlib import Path
import json
import hashlib
import unittest
import ast
import numpy as np
import pandas as pd

from joint_engine import JointConsumer, run_joint
from joint_policy import PriceSizing, OpenView, industry_gate, rank_key, price_protection_close
from execution_book import ExecutionBook,EvidenceDomain,Clock,Receipt,OpenPermission

CAL=pd.date_range('2022-01-03',periods=5,freq='B')
ROOT=('SYN_A','fixture|fixture|0.0','2022-01-03')


class QR:
    def buy_floor(self,q):return max(0,int(q)//100*100)


class DayFrame:
    def __init__(self,frame):self.frame=frame
    def get(self,d,default=None):return self.frame.loc[d] if d in self.frame.index else default


class FakeEngine:
    RuleUnavailable=RuntimeError
    SLIP=D('.0005');END=CAL[-1]
    def __init__(self):
        self.cal=CAL;self.rounds=[];self.actions=[];self.decisions=[];self.ranking_audit=[]
        self.archives={};self.blocks=[];self.trace=[];self.claims={};self.EVENTS=[];self.EVENT_AT={}
        self.raw={};self.closecache={};self.current_actions=[];self.integrity=True;self.cash_events=[]
        self.CURRENT_PHASE='UNSET'
    def getmeta(self,sid,day):return QR(),None,None
    def fee(self,q,p,fs,side,par):return D(5) if q else D(0)
    def size(self,sid,day,price,floor,budget,riskmax,cap):
        q=QR().buy_floor(min(int(budget/price),int(cap)))
        while q:
            bf=sf=D(5);risk=max(D(0),D(q)*(price-floor*(1-self.SLIP))+bf+sf)
            if D(q)*price+bf<=budget and risk<=riskmax:return q,bf,risk,None,None
            q-=100
        return 0,D(0),D(0),None,None
    def load(self,sid):
        if sid not in self.raw:
            self.raw[sid]=DayFrame(pd.DataFrame([dict(raw_open=20.,raw_close=20.,adjustment_factor=1.,
                source_kind='fixture',source_path='fixture',segment_id=0.) for _ in CAL],index=CAL))
    def lineage(self,z):return tuple(str(z.get(k)) for k in ('source_kind','source_path','segment_id'))
    def checkclose(self,r):
        key=(r['sid'],r['day'])
        if key not in self.closecache:
            self.trace.append(('checkclose',r['sid'],str(r['day'])))
            self.load(r['sid'])
            q,bf,risk,_,_=self.size(r['sid'],r['day'],D(20)*(1+self.SLIP),D(str(r['i_floor'])),D(24000),D(3000),100000)
            if r.get('force_ab_reject'):q=0
            self.closecache[key]=dict(close_check='PASS' if q else 'MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE',
                close_q=q,close_fee=float(bf),close_plan_risk=float(risk),prior20_capacity=100000)
        return dict(self.closecache[key])
    def new_state(self,r,arm,rid,check):
        st=dict(r,state='BUY_PENDING',arm=arm,round_id=rid,signal_day=r['day'],birth_end=CAL[-1],
                close_q=check['close_q'],prior20_capacity=check['prior20_capacity'],receivable=D(0),
                dividend_total=D(0),dividend_paid=D(0))
        self.archives[rid]=st;return st
    def pending_bridge(self,*args):return False
    def before_held(self,*args):return True
    def local_actions(self,sid):return dict(events=self.current_actions,_source_integrity_ok=self.integrity)
    def unadmitted_action_at(self,sid,day):return not self.integrity
    def mark(self,st,px,day):return st['cash']+st.get('receivable',D(0))+D(st['core']+st['add'])*px-D(5)
    def act(self,st,d,side,q,px,fee,reason,**extra):
        self.actions.append(dict(round_id=st['round_id'],sid=st['sid'],day=str(d.date()),side=side,
                                 q=q,price=float(px),fee=float(fee),reason=reason,**extra))
    def record(self,st,status,d=None,**extra):
        self.rounds.append(dict(round_id=st['round_id'],sid=st['sid'],status=status,day=d,
                                core_qty=st.get('core',0),add_qty=st.get('add',0),**extra))
        st['_output_index']=len(self.rounds)-1
    def freeze_unknown(self,states,sid,st,reason,d):
        self.record(st,reason,d);states[sid]=dict(state='UNKNOWN',round_id=st['round_id'],unknown_reason=reason)
    def accrue_day(self,arm,d):
        self.trace.append(('accrue',str(d)))
        for key,c in self.claims.items():
            if c['ex']==d and not c['recognized']:
                c['recognized']=True;st=self.archives[c['round_id']];st['receivable']+=c['amount'];st['dividend_total']+=c['amount']
    def register(self,states,arm,d):
        self.trace.append(('register',str(d)))
        for e in self.cash_events:
            if e['record']!=d or e['id'] in self.claims:continue
            st=states.get(e['sid']);q=st['core']+st['add'] if st and st['state']=='HELD' else 0
            if q:self.claims[e['id']]=dict(round_id=st['round_id'],amount=D(q)*e['cash']*D('.8'),
                                         ex=e['ex'],pay=e['pay'],recognized=False,settled=False)
    def pay_day(self,arm,d):
        self.trace.append(('pay',str(d)))
        for c in self.claims.values():
            if c['pay']==d and c['recognized'] and not c['settled']:
                st=self.archives[c['round_id']];st['cash']+=c['amount'];st['receivable']-=c['amount'];c['settled']=True
    def entry_open(self,states,sid,st,d):
        self.trace.append(('original_AB_entry_open',sid,str(d)))
        if st.get('reject_open'):
            self.record(st,'PRECHECK_AB_REJECT',d);states.pop(sid);return
        st.update(state='HELD',core=100,add=0,cash=D(-2005),spent=D(2005),fees=D(5),entry_day=d,
                  exitpending=None,origin=('fixture','fixture','0.0'),factor=1.,fac=D(1))
        self.act(st,d,'buy_core',100,D(20),D(5),'ORIGINAL_AB')
    def held_open(self,states,sid,st,d,prev):
        self.trace.append(('original_AB_held_open',sid,str(d)))
        if st['exitpending']:
            self.act(st,d,'sell_all',100,D(20),D(5),'ORIGINAL_AB_EXIT');st['core']=0
            self.record(st,'COMPLETE_CONDITIONAL_STOCK_ROUND',d);states.pop(sid)
    def held_close(self,states,sid,st,d):
        self.trace.append(('original_AB_held_close',sid,str(d)))
        if st.get('exit_on')==d:st['exitpending']='ORIGINAL_I_EXIT'


def price_row(sid='SYN_A',day=CAL[0],score=70,known=True):
    root=(sid,'fixture|fixture|0.0','2022-01-03')
    return dict(sid=sid,day=day,name=sid,industry='FICTITIOUS',sector='SYN_SECTOR',window='2022',
        root_id=root,receipt_id=(root,str(day.date())),phase='PROBE',price_valid=True,root_unknown=False,
        raw_close=20.,close=20.,adjustment_factor=1.,S_old=18.,S_new=18.,capacity_shares=100000,
        PVR_known=known,PVR_score=score,receipt=True,sector_known=True,sector_observed_today=True,
        sector_rs_ready_fresh=True,sector_up=True)


def ab_row(sid='SYN_A',day=CAL[0],score=70,**extra):
    return dict(sid=sid,day=day,name=sid,industry='FICTITIOUS',sector='SYN_SECTOR',window='2022',
        event_id='AB|'+sid+'|'+str(day.date()),event_type='A_SECTOR_BIRTH',I_qualified=True,
        PVR_known=True,PVR_score=score,i_floor=18.,**extra)


class FakeMarket:
    def __init__(self,e):self.e=e;self.rows={};self.open_calls=0;self.close_calls=0
    def open(self,sid,d):
        self.open_calls+=1;self.e.load(sid);return self.e.raw[sid].get(d).to_dict()
    def close(self,sid,d):
        self.close_calls+=1;return dict(self.rows.get((sid,d),price_row(sid,d)))


class JointTests(unittest.TestCase):
    def make(self):
        e=FakeEngine();m=FakeMarket(e);return e,m,JointConsumer(e,m,'2022')
    def test_rank_unknown_price_not_gate(self):
        e,m,c=self.make();a=ab_row('SYN_AB',score=60)
        c.select_close(CAL[0],[a],[price_row('SYN_HIGH',score=80),price_row('SYN_UNKNOWN',score=float('nan'),known=False)])
        self.assertEqual([r['sid'] for r in e.decisions if r['selected']],['SYN_HIGH','SYN_AB'])
        z=[r for r in c.offer_audit if r['sid']=='SYN_UNKNOWN']
        self.assertEqual([r['result'] for r in z],['APPLICATION','PASS_NOT_TOP2'])
        self.assertTrue(all(r['PVR_known'] is False for r in z))
        e,m,c=self.make();c.select_close(CAL[0],[],[price_row('SYN_UNKNOWN',known=False,score=None)])
        self.assertEqual(e.decisions[0]['decision'],'SELECTED_PENDING')
    def test_unknown_other_blocks_not_rank_loss(self):
        e,m,c=self.make();p=price_row(known=False,score=None);p['sector_up']=False
        c.select_close(CAL[0],[],[p]);self.assertEqual(c.offer_audit[-1]['result'],'INDUSTRY_FALSE')
        c.states[p['sid']]=dict(state='UNKNOWN',round_id='locked')
        c.select_close(CAL[0],[],[p]);self.assertEqual(c.offer_audit[-1]['result'],'BLOCKED_UNKNOWN')
    def test_ab_precedence_requires_original_close_pass(self):
        e,m,c=self.make();c.select_close(CAL[0],[ab_row(force_ab_reject=True)],[price_row()])
        self.assertEqual(c.states['SYN_A']['owner_lane'],'PRICE')
        e,m,c=self.make();c.select_close(CAL[0],[ab_row(reject_open=True)],[price_row()])
        self.assertEqual(c.states['SYN_A']['owner_lane'],'AB')
        c.process_day(CAL[1],CAL[0],[],[])
        self.assertNotIn('SYN_A',c.states);self.assertFalse(c.books);self.assertFalse(e.actions)
    def test_volume_unknown_not_price_gate_and_cache_order(self):
        results=[]
        for order in ('AB_FIRST','PRICE_FIRST'):
            e=FakeEngine();p=price_row();p.update(S_new=19.5,volume_eligible=False,amount=float('nan'))
            sizing=PriceSizing(e);a=ab_row();a['i_floor']=14.
            if order=='AB_FIRST':ab=e.checkclose(a);pr=sizing.close_check(p,window='2022')
            else:pr=sizing.close_check(p,window='2022');ab=e.checkclose(a)
            self.assertEqual(pr['close_check'],'PASS');results.append((ab,pr))
        self.assertEqual(results[0],results[1]);self.assertNotEqual(results[0][0]['close_q'],results[0][1]['close_q'])
    def test_open_hlc_phase_mutation_invariant_and_no_current_close_read(self):
        outcomes=[]
        for altered in (False,True):
            e,m,c=self.make();p=price_row();c.select_close(CAL[0],[],[p]);e.load('SYN_A')
            if altered:
                m.rows[('SYN_A',CAL[1])]=dict(price_row(day=CAL[1]),close=1,raw_close=1,S_new=999,phase='CONFIRMED',root_unknown=True,root_id=None)
                for col,value in dict(raw_close=1.,raw_high=999.,raw_low=.01,amount=np.nan,raw_volume=0.,volume_eligible=False,observed_bar=False,price_eligible=False,source_invalid=True,synthetic_event_bar=True).items():
                    e.raw['SYN_A'].frame.loc[CAL[1],col]=value
            c.price_entry_open('SYN_A',c.states['SYN_A'],CAL[1])
            self.assertEqual(m.close_calls,0)
            outcomes.append((e.actions,c.books[next(iter(c.books))].parent('PROBE').target_Q))
        self.assertEqual(outcomes[0],outcomes[1])
    def test_actual_pending_cash_bridge_open_mutation_invariance(self):
        outcomes=[]
        source=(Path(__file__).resolve().parent.parent/'m3_stock_birth_during_sector_v1/relative_priority_equity_run_2022_v1/engine.py').read_text()
        for changed in (False,True):
            e,m,c=self.make();p=price_row();p.update(raw_close=10.,close=10.,S_new=8.)
            c.select_close(CAL[0],[],[p]);st=c.states['SYN_A']
            e.raw['SYN_A'].frame.loc[CAL[0],['raw_close','adjustment_factor']]=[10.,1.]
            e.raw['SYN_A'].frame.loc[CAL[1],['raw_open','adjustment_factor']]=[9.2,10/9]
            event=dict(sid='SYN_A',economic_event_id='CASH',d_source=D(1),factor_old=D(1),factor_new=D(str(10/9)))
            e.EVENT_AT={('SYN_A',CAL[1]):event}
            env=dict(D=D,np=np,finite=lambda v:np.isfinite(v),EVENT_AT=e.EVENT_AT,enabled=lambda x:True,
                     snapshots={('A_UNION_B_PLUS_PRICE','CASH'):{'record_q':0}},
                     claim_key=lambda arm,event:(arm,event['economic_event_id']),bridges=[])
            for node in ast.parse(source).body:
                if isinstance(node,ast.FunctionDef) and node.name in ('coordinate_matches','pending_bridge'):
                    exec(compile(ast.get_source_segment(source,node),'original_cash_bridge_definition','exec'),env)
            e.pending_bridge=env['pending_bridge']
            if changed:
                for col,value in dict(raw_close=1000.,raw_high=2000.,raw_low=.01,amount=np.nan,raw_volume=0.,volume_eligible=False,price_eligible=False,observed_bar=False,source_invalid=True).items():
                    e.raw['SYN_A'].frame.loc[CAL[1],col]=value
                m.rows[('SYN_A',CAL[1])]=dict(root_unknown=True,phase='FAILED')
            c.price_entry_open('SYN_A',st,CAL[1])
            self.assertEqual(m.close_calls,0);self.assertEqual(len(env['bridges']),1)
            outcomes.append((e.actions,env['bridges']))
        self.assertEqual(outcomes[0],outcomes[1])
    def test_add_and_exit_open_current_bar_mutation_invariance(self):
        outcomes=[]
        for changed in (False,True):
            e,m,c=self.make();c.process_day(CAL[0],None,[],[price_row()]);e.load('SYN_A')
            e.raw['SYN_A'].frame.loc[CAL[2],'raw_open']=24.;e.raw['SYN_A'].frame.loc[CAL[3],'raw_open']=22.
            m.rows[('SYN_A',CAL[1])]=dict(price_row(day=CAL[1]),close=24.,raw_close=24.,S_new=23.,phase='CONFIRMED')
            c.process_day(CAL[1],CAL[0],[],[])
            if changed:
                for d in (CAL[2],CAL[3]):
                    for col,value in dict(raw_close=1.,raw_high=999.,raw_low=.01,amount=np.nan,raw_volume=0.,volume_eligible=False,observed_bar=False,price_eligible=False,source_invalid=True).items():
                        e.raw['SYN_A'].frame.loc[d,col]=value
                    m.rows[('SYN_A',d)]=dict(root_unknown=True,phase='FAILED')
            before=m.close_calls;c.price_held_open('SYN_A',c.states['SYN_A'],CAL[2]);self.assertEqual(m.close_calls,before)
            # This close is now legitimately visible, and establishes next-OPEN exit.
            m.rows[('SYN_A',CAL[2])]=dict(price_row(day=CAL[2]),close=22.,raw_close=22.,S_old=23.,S_new=np.nan,phase='FAILED',receipt=False)
            c.price_held_close('SYN_A',c.states['SYN_A'],CAL[2]);before=m.close_calls
            c.price_held_open('SYN_A',c.states['SYN_A'],CAL[3]);self.assertEqual(m.close_calls,before)
            outcomes.append(e.actions)
        self.assertEqual(outcomes[0],outcomes[1])
    def test_no_submit_no_parent(self):
        for op,expected in [(17.,'PRECHECK_OPEN_AT_OR_BELOW_S_NO_SUBMIT'),(200000.,'PRECHECK_Q0_NO_SUBMIT')]:
            e,m,c=self.make();c.select_close(CAL[0],[],[price_row()]);e.raw['SYN_A'].frame.loc[CAL[1],'raw_open']=op
            c.price_entry_open('SYN_A',c.states['SYN_A'],CAL[1])
            self.assertEqual(e.rounds[-1]['status'],expected);self.assertFalse(c.books);self.assertFalse(e.actions)
    def test_fictitious_full_probe_one_add_exit(self):
        e,m,c=self.make();c.process_day(CAL[0],None,[],[price_row()]);e.load('SYN_A')
        e.raw['SYN_A'].frame.loc[CAL[2],'raw_open']=24.;e.raw['SYN_A'].frame.loc[CAL[3],'raw_open']=22.
        m.rows[('SYN_A',CAL[1])]=dict(price_row(day=CAL[1]),close=24.,raw_close=24.,S_new=23.,phase='CONFIRMED')
        m.rows[('SYN_A',CAL[2])]=dict(price_row(day=CAL[2]),close=22.,raw_close=22.,S_old=23.,S_new=float('nan'),phase='FAILED',receipt=False)
        for i in (1,2,3):c.process_day(CAL[i],CAL[i-1],[],[])
        self.assertEqual([a['side'] for a in e.actions],['buy_core','buy_add','sell_all'])
        self.assertNotIn('SYN_A',c.states);b=next(iter(c.books.values()))
        self.assertEqual(b.held_qty,0);self.assertEqual(len(b.parents),2)
        self.assertEqual(e.rounds[-1]['status'],'COMPLETE_CONDITIONAL_STOCK_ROUND')
    def test_source_switch_locks_not_sells(self):
        e,m,c=self.make();c.select_close(CAL[0],[],[price_row()]);c.price_entry_open('SYN_A',c.states['SYN_A'],CAL[1])
        e.raw['SYN_A'].frame.loc[CAL[2],'source_path']='new_source'
        before=len(e.actions);c.price_held_open('SYN_A',c.states['SYN_A'],CAL[2])
        self.assertEqual(c.states['SYN_A']['state'],'UNKNOWN');self.assertEqual(len(e.actions),before)
        self.assertGreater(next(iter(c.books.values())).held_qty,0)
    def test_bad_action_source_with_empty_events_fails_closed(self):
        e,m,c=self.make();c.select_close(CAL[0],[],[price_row()]);e.integrity=False
        c.price_entry_open('SYN_A',c.states['SYN_A'],CAL[1])
        self.assertEqual(c.states['SYN_A']['state'],'UNKNOWN');self.assertFalse(e.actions)
    def test_old_s_before_new_s(self):
        f=price_row();f.update(close=18,S_new=19)
        self.assertEqual(price_protection_close(held_root=ROOT,prior_s=D(18),fact=f)[0],'EXIT')
        f.update(close=20,S_new=19)
        self.assertEqual(price_protection_close(held_root=ROOT,prior_s=D(18),fact=f),('HOLD',D(19)))
    def test_probe_remainder_no_add_profit_gate(self):
        p=PriceSizing(FakeEngine());v=OpenView(20.,1.,'fixture','fixture',0.)
        z=p.probe_remaining('SYN_A',CAL[2],v,floor=19.,capacity=100000,filled_qty=100,
                            entry_fees=D(5),probe_spent=D(2005),remaining_qty=200)
        self.assertEqual(z['result'],'PASS');self.assertEqual(z['q'],200)
        z=p.probe_remaining('SYN_A',CAL[2],v,floor=19.,capacity=100000,filled_qty=100,
                            entry_fees=D(5),probe_spent=D(23999),remaining_qty=200)
        self.assertEqual(z['result'],'PRECHECK_FIXED_REMAINDER_NOT_FUNDED_NO_SUBMIT')
    def test_synthetic_partial_budget_queue_receipt_book_connection(self):
        e,m,c=self.make();sizing=PriceSizing(e);b=ExecutionBook(ROOT,EvidenceDomain.SYNTHETIC_TEST)
        v=OpenView(20.,1.,'fixture','fixture',0.)
        initial=sizing.initial_open('SYN_A',CAL[1],v,floor=18.,capacity=400)
        r=Receipt(ROOT,str(CAL[0].date()),Clock(str(CAL[0].date()),100),str(CAL[1].date()))
        p=OpenPermission(r,str(CAL[1].date()),Clock(str(CAL[1].date()),20),20.,18.,initial['q'],float(initial['budget']),'fixture',True)
        o=b.open_target('PROBE',p)
        b.synthetic_fill(o.order_id,fill_id='F1',quantity=200,price=float(initial['price']),fee=5.,trade_day=str(CAL[1].date()),known_at=Clock(str(CAL[1].date()),30))
        b.terminal_ack(o.order_id,cumulative_filled=200,known_at=Clock(str(CAL[1].date()),40))
        self.assertEqual(b.remaining('PROBE'),200);self.assertEqual(b.parent('PROBE').target_Q,400)
        rows=[dict(price_row('SYN_A',CAL[1],known=False,score=None),owner_lane='PRICE'),
              dict(price_row('SYN_B',CAL[1],score=90),owner_lane='PRICE'),
              dict(ab_row('SYN_C',CAL[1],score=80),owner_lane='AB')]
        winners=sorted(rows,key=rank_key)[:2]
        self.assertNotIn('SYN_A',[x['sid'] for x in winners]);self.assertEqual(b.remaining('PROBE'),200)
        c.states['SYN_A']=dict(state='HELD',owner_lane='PRICE',round_id='PARTIAL_ROOT')
        c.select_close(CAL[1],[ab_row(day=CAL[1])],[])
        self.assertEqual(c.offer_audit[-1]['result'],'BLOCKED_HELD')
        v=OpenView(24.,1.,'fixture','fixture',0.)
        later=sizing.probe_remaining('SYN_A',CAL[3],v,floor=23.,capacity=100000,filled_qty=b.held_qty,
                                     entry_fees=D(5),probe_spent=D(str(b.spent('PROBE'))),remaining_qty=b.remaining('PROBE'))
        self.assertEqual(later['result'],'PASS');self.assertLess(later['budget'],D(24000))
        r2=Receipt(ROOT,str(CAL[2].date()),Clock(str(CAL[2].date()),100),str(CAL[3].date()))
        p2=OpenPermission(r2,str(CAL[3].date()),Clock(str(CAL[3].date()),20),24.,23.,later['q'],float(later['budget']),'fixture',True)
        o2=b.submit_remaining('PROBE',p2)
        self.assertEqual(o2.quantity,200);self.assertEqual(b.parent('PROBE').target_Q,400)
    def test_ab_new_scheduler_uses_original_methods_in_order(self):
        e,m,c=self.make();a=ab_row(exit_on=CAL[1]);c.process_day(CAL[0],None,[a],[])
        c.process_day(CAL[1],CAL[0],[],[]);c.process_day(CAL[2],CAL[1],[],[])
        methods=[r[0] for r in e.trace]
        self.assertEqual(methods,['accrue','register','checkclose','pay','accrue',
            'original_AB_entry_open','original_AB_held_close','register','pay','accrue',
            'original_AB_held_open','register','pay'])
        self.assertEqual([a['reason'] for a in e.actions],['ORIGINAL_AB','ORIGINAL_AB_EXIT'])
        self.assertFalse(c.books)
    def test_future_unregistered_actions_do_not_change_prefix_claims_preserved(self):
        outputs=[]
        for future in ('2025-06-01','2026-05-18'):
            e,m,c=self.make();e.current_actions=[dict(effective_date=future,split_ratio='2')]
            e.cash_events=[dict(id='KNOWN',sid='SYN_A',record=CAL[1],ex=CAL[3],pay=CAL[4],cash=D('.1'))]
            c.process_day(CAL[0],None,[ab_row()],[])
            c.process_day(CAL[1],CAL[0],[],[]);c.process_day(CAL[2],CAL[1],[],[])
            self.assertIn('KNOWN',e.claims);self.assertFalse(e.claims['KNOWN']['recognized'])
            outputs.append((e.actions,e.claims,c.states))
        self.assertEqual(outputs[0],outputs[1])
    def test_real_price_economic_entry_is_locked(self):
        with self.assertRaises(PermissionError):run_joint('2022')
    def test_industry_unknown_dominates_false(self):
        p=price_row();p.update(sector_up=False,sector_rs_ready_fresh=None)
        self.assertEqual(industry_gate(p),'INDUSTRY_UNKNOWN')


if __name__=='__main__':
    unittest.main(verbosity=2)
