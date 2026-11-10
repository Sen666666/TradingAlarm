"""Explicit real-account initial gate; original research/paper defaults retained."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desk.data import MarketData
from desk.service import Desk
from desk.strategy import build_report


class InitialParticipationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=MarketData('/tmp/initial-participation-readonly')

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.desk=Desk(self.tmp.name);self.desk._data=self.data
        self.desk.store.initialize('1000000','2026-10-26')

    def tearDown(self):self.tmp.cleanup()

    def test_inactive_initial_gate_prevents_buy_without_recovery(self):
        self.desk.store.set_setting('initial_participation','INACTIVE')
        v=self.desk.overview();self.assertFalse(v['report']['risk']['on'])
        self.assertEqual(v['report']['instructions'],[])
        self.assertEqual(v['report']['cash'],'1000000')
        self.assertEqual(v['report']['risk']['episode'],0)

    def test_first_close_can_activate_only_when_recovery_is_true(self):
        data=copy.copy(self.data);data.recovery=self.data.recovery.copy();day=data.as_of
        data.recovery.loc[day,'market']=data.recovery.market.max()*1.01
        data.recovery.loc[day,'breadth']=.7;data.recovery.loc[day,'breakout']=True
        r=build_report(data,self.desk.store.account(),[],initial_active=False)
        self.assertTrue(r['risk']['on']);self.assertEqual(r['risk']['event'],'resume')
        self.assertEqual(r['risk']['episode'],1)
        self.assertEqual(len(r['instructions']),4)

    def test_state_change_invalidates_cache_and_saves_separate_report_version(self):
        active=self.desk.overview();self.assertTrue(active['report']['risk']['on'])
        self.desk.store.set_setting('initial_participation','INACTIVE')
        inactive=self.desk.overview();self.assertFalse(inactive['report']['risk']['on'])
        with self.desk.store.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM report_versions').fetchone()[0],2)

    def test_restart_preserves_inactive(self):
        self.desk.store.set_setting('initial_participation','INACTIVE');before=self.desk.overview()['report']
        restarted=Desk(self.tmp.name);restarted._data=self.data
        self.assertEqual(restarted.overview()['report'],before)

    def test_new_actual_account_defaults_to_inactive(self):
        with tempfile.TemporaryDirectory() as path:
            desk=Desk(path);desk.initialize({'cash':'1000000'})
            self.assertEqual(desk.store.setting('initial_participation'),'INACTIVE')

    def test_original_paper_research_default_remains_active(self):
        r=build_report(self.data,self.desk.store.account(),[])
        self.assertTrue(r['risk']['on']);self.assertEqual(len(r['instructions']),4)
        self.assertNotIn('initial_participation',r)

    def test_invalid_initial_state_cannot_silently_allow_buy(self):
        self.desk.store.set_setting('initial_participation','UNKNOWN')
        with self.assertRaises(ValueError):self.desk.overview()
        with self.assertRaises(ValueError):build_report(self.data,self.desk.store.account(),[],initial_active='False')


if __name__=='__main__':unittest.main()
