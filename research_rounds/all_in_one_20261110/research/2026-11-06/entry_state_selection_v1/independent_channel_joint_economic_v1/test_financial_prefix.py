"""Original equity functions on fictitious events, no historical lifecycle."""
from pathlib import Path
from decimal import Decimal as D
from copy import deepcopy
import ast
import unittest
import pandas as pd

BASE=Path(__file__).resolve().parent.parent/'m3_stock_birth_during_sector_v1'
CAL=pd.date_range('2022-01-03',periods=12,freq='B')


def env_for(window, future_variant=False):
    folder='relative_priority_equity_run_2022_v1' if window=='2022' else 'cash_equity_baseline_2024_v1'
    path=BASE/folder/'engine.py';text=path.read_text()
    st=dict(state='HELD',sid='SYN_FIN',arm='SYN_ARM',round_id='SYN_ROUND',core=100,add=50,
            cash=D(-1505),receivable=D(0),dividend_total=D(0),dividend_paid=D(0),exitpending=None)
    e=dict(sid='SYN_FIN',economic_event_id='KNOWN_BEFORE_CUT',evidence_version='frozen',
           coordinate_snapshot_day=CAL[0],record_date=CAL[0],ex_date=CAL[5],pay_date=CAL[8],
           entitlement_verified=True,d_cash=D('.1'))
    other=dict(e,economic_event_id='NOT_REGISTERED_AT_CUT',coordinate_snapshot_day=CAL[9],
               record_date=CAL[9],ex_date=CAL[10],pay_date=CAL[11],d_cash=D(999) if future_variant else D('.2'))
    g=dict(D=D,pd=pd,WINDOW='2024_924',NET=D('.8'),BRIDGE=True,ALLOWED_EVENT_IDS=None,
           snapshots={},registrations=[],claims={},claim_ledger=[],archives={'SYN_ROUND':st},cal=CAL,
           BY_RECORD={CAL[0]:[e],CAL[9]:[other]},BY_EX={CAL[5]:[e],CAL[10]:[other]},
           BY_PAY={CAL[8]:[e],CAL[11]:[other]})
    for node in ast.parse(text).body:
        if isinstance(node,ast.FunctionDef) and node.name in ('enabled','claim_key','register','accrue_day','pay_day'):
            exec(compile(ast.get_source_segment(text,node),str(path)+':definition_only','exec'),g)
    return g,{'SYN_FIN':st}


class OriginalFinancialPrefix(unittest.TestCase):
    def test_original_functions_future_event_perturbation_no_prefix_change(self):
        for window in ('2022','2024'):
            values=[]
            for variant in (False,True):
                g,states=env_for(window,variant)
                for d in CAL[:4]:
                    g['accrue_day']('SYN_ARM',d);g['register'](states,'SYN_ARM',d);g['pay_day']('SYN_ARM',d)
                claim=next(iter(g['claims'].values()))
                self.assertEqual(claim['amount'],D(12));self.assertFalse(claim['recognized']);self.assertFalse(claim['settled'])
                self.assertEqual(claim['ex_date'],CAL[5]);self.assertEqual(claim['pay_date'],CAL[8])
                values.append((g['registrations'],g['claims'],g['claim_ledger'],states))
            self.assertEqual(values[0],values[1])
    def test_registered_claim_survives_exit_unknown_and_pay_is_transfer(self):
        for window in ('2022','2024'):
            g,states=env_for(window);g['register'](states,'SYN_ARM',CAL[0]);old=g['archives']['SYN_ROUND']
            states['SYN_FIN']=dict(state='UNKNOWN',round_id='SYN_ROUND')
            g['accrue_day']('SYN_ARM',CAL[5]);self.assertEqual(old['receivable'],D(12));self.assertEqual(old['dividend_total'],D(12))
            before=old['cash']+old['receivable'];g['pay_day']('SYN_ARM',CAL[8]);g['pay_day']('SYN_ARM',CAL[8])
            self.assertEqual(old['cash']+old['receivable'],before);self.assertEqual(old['receivable'],0)
            self.assertEqual(len(g['claim_ledger']),2)
    def test_known_zero_and_unknown_registration_are_distinct(self):
        for window in ('2022','2024'):
            g,states=env_for(window);g['register']({},'SYN_ARM',CAL[0])
            self.assertEqual(g['registrations'][0]['record_q'],0);self.assertFalse(g['claims'])
            g,states=env_for(window);g['register']({'SYN_FIN':{'state':'UNKNOWN','round_id':'R'}},'SYN_ARM',CAL[0])
            self.assertIsNone(g['registrations'][0]['record_q']);self.assertFalse(g['claims'])
    def test_new_round_does_not_inherit_old_claim(self):
        for window in ('2022','2024'):
            g,states=env_for(window);g['register'](states,'SYN_ARM',CAL[0]);old=g['archives']['SYN_ROUND']
            new=dict(old,round_id='NEW_ROUND',core=20,add=0,cash=D(-400),receivable=D(0),dividend_total=D(0),dividend_paid=D(0))
            g['archives']['NEW_ROUND']=new;states['SYN_FIN']=new
            g['accrue_day']('SYN_ARM',CAL[5]);g['pay_day']('SYN_ARM',CAL[8])
            self.assertEqual(new['cash'],D(-400));self.assertEqual(new['dividend_total'],0);self.assertEqual(old['dividend_paid'],D(12))


if __name__=='__main__':unittest.main(verbosity=2)
