import copy
import json
import sys
import tempfile
import unittest
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from desk.store import Store,journal
from desk.strategy import advance_risk,build_report,packet
from desk.data import MarketData,ROOT,TZ


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'test.sqlite3');self.account=self.store.initialize('1000000','2026-10-22')
    def tearDown(self):self.tmp.cleanup()
    def trade(self,eid,side,day,qty,price,fee='5'):
        payload=dict(symbol='300502.SZ',shares=qty,price=price,fee=fee)
        return self.store.record(eid,day+'T09:30:00+08:00',side,payload,lambda es:journal(self.account,es))
    def test_partial_sell_cost_and_cash(self):
        self.trade('b1','buy','2026-10-22',1000,'100');self.trade('b2','buy','2026-10-23',1000,'120')
        self.trade('s1','sell','2026-10-26',1500,'140','10');z=journal(self.account,self.store.events())
        self.assertEqual(D(z['cash']),D('989980'));self.assertEqual(D(z['realized']),D('49982.5'));self.assertEqual(D(z['positions']['300502.SZ']['cost']),D('60002.5'))
    def test_t1_and_transaction_atomicity(self):
        self.trade('b','buy','2026-10-22',100,'100')
        with self.assertRaisesRegex(ValueError,'T\\+1'):self.trade('s','sell','2026-10-22',100,'101')
        self.assertEqual(len(self.store.events()),1)
    def test_overdraw_rejected(self):
        with self.assertRaisesRegex(ValueError,'现金'):self.trade('b','buy','2026-10-22',100000,'100')
        self.assertEqual(self.store.events(),[])
    def test_idempotent_concurrent_submission(self):
        with ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(lambda _:self.trade('same','buy','2026-10-22',100,'100'),range(5)))
        self.assertEqual(len(self.store.events()),1)
        with self.assertRaises(ValueError):self.trade('same','buy','2026-10-22',200,'100')
    def test_reopen_persistence(self):
        self.trade('b','buy','2026-10-22',100,'100');other=Store(self.store.path)
        self.assertEqual(journal(other.account(),other.events()),journal(self.account,self.store.events()))


class StrategyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=MarketData('/tmp/tradingalarm-contract-readonly')
    def test_baseline_risk_replay_all_three_scenarios(self):
        root=ROOT/'research_rounds/actual-risk-recovery-20261027/ACT20_BREAK/accounts-v2'
        count=0
        for path in root.glob('I__*.json'):
            state=dict(on=True,peak='1000000',episode=0)
            for r in json.loads(path.read_text())['audit_log']:
                if r['kind']!='risk_checkpoint':continue
                state,dd,event=advance_risk(state,D(r['nav']),r['flat'],r['breakout'])
                self.assertEqual(state['on'],r['on']);self.assertEqual(state['episode'],r['episode']);self.assertEqual(D(state['peak']),D(r['peak']));self.assertEqual(dd,D(r['episode_drawdown']));self.assertEqual(event,r['event']);count+=1
        self.assertEqual(count,2040)
    def test_no_fill_inferred_from_recommendation(self):
        report=build_report(self.data,dict(initial_cash='1000000',started_on='2026-10-26'),[])
        self.assertTrue(any(x['action']=='BUY' for x in report['instructions']))
        self.assertEqual(report['cash'],'1000000');self.assertEqual(report['holdings'],[]);self.assertEqual(report['nav'],'1000000')
    def test_new_account_not_historical_backtest_state(self):
        self.assertIsNone(build_report(self.data,dict(initial_cash='500000',started_on='2026-10-27'),[]))
        report=build_report(self.data,dict(initial_cash='500000',started_on='2026-10-26'),[])
        self.assertTrue(report['risk']['on']);self.assertEqual(report['risk']['peak'],'500000')
    def test_close_calendar_and_before_close(self):
        self.assertEqual(self.data.expected_close(datetime(2026,10,27,12,tzinfo=TZ)),'2026-10-26')
        self.assertEqual(self.data.expected_close(datetime(2026,10,27,16,tzinfo=TZ)),'2026-10-27')
        self.assertIsNone(self.data.expected_close(datetime(2027,1,2,tzinfo=TZ)))
    def test_pure_rebuild_deterministic(self):
        a=dict(initial_cash='1000000',started_on='2026-10-22')
        self.assertEqual(build_report(self.data,a,[]),build_report(self.data,a,[]))

if __name__=='__main__':unittest.main()

class AmendmentAndEntitlementTests(JournalTests):
    def test_amend_retains_original_and_rebuilds_cost(self):
        self.trade('b','buy','2026-10-22',100,'100')
        replacement=dict(kind='buy',at='2026-10-22T09:30:00+08:00',payload=dict(symbol='300502.SZ',shares=200,price='100',fee='5'))
        self.store.record('fix','2026-10-22T09:30:00+08:00','amend',dict(target_id='b',reason='券商成交数量核对',replacement=replacement),lambda es:journal(self.account,es))
        z=journal(self.account,self.store.events());self.assertEqual(z['positions']['300502.SZ']['shares'],200);self.assertEqual(D(z['cash']),D('979995'));self.assertEqual(len(self.store.events()),2)
    def test_invalid_amend_rolls_back(self):
        self.trade('b','buy','2026-10-22',100,'100');self.trade('s','sell','2026-10-23',100,'110')
        replacement=dict(kind='buy',at='2026-10-22T09:30:00+08:00',payload=dict(symbol='300502.SZ',shares=50,price='100',fee='5'))
        with self.assertRaises(ValueError):self.store.record('fix','2026-10-22T09:30:00+08:00','amend',dict(target_id='b',reason='错误修正',replacement=replacement),lambda es:journal(self.account,es))
        self.assertEqual(len(self.store.events()),2)
    def test_bonus_cost_conservation_and_listing_date(self):
        self.trade('b','buy','2026-10-22',1000,'100')
        self.store.record('bonus','2026-10-23T08:00:00+08:00','corporate',dict(symbol='300502.SZ',shares_delta=1000,cash_delta='0',receivable_delta='1000',sellable_on='2026-10-26'),lambda es:journal(self.account,es))
        z=journal(self.account,self.store.events());self.assertEqual(D(z['positions']['300502.SZ']['cost']),D('100005'));self.assertEqual(z['positions']['300502.SZ']['shares'],2000);self.assertEqual(D(z['receivable']),D('1000'))
        self.trade('s1','sell','2026-10-23',1000,'50')
        with self.assertRaises(ValueError):self.trade('s2','sell','2026-10-23',1000,'50')
        self.trade('s3','sell','2026-10-26',1000,'50')
    def test_dividend_payment_moves_receivable_without_double_count(self):
        self.store.record('due','2026-10-23T08:00:00+08:00','corporate',dict(symbol='300502.SZ',shares_delta=0,cash_delta='0',receivable_delta='1000'),lambda es:journal(self.account,es))
        before=journal(self.account,self.store.events())
        self.store.record('paid','2026-10-26T08:00:00+08:00','corporate',dict(symbol='300502.SZ',shares_delta=0,cash_delta='1000',receivable_delta='-1000'),lambda es:journal(self.account,es))
        after=journal(self.account,self.store.events());self.assertEqual(D(before['cash'])+D(before['receivable']),D(after['cash'])+D(after['receivable']))

class OperationalFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.data=MarketData('/tmp/tradingalarm-contract-readonly')
    def setUp(self):
        from desk.service import Desk
        self.tmp=tempfile.TemporaryDirectory();self.desk=Desk(self.tmp.name);self.desk._data=self.data
    def tearDown(self):self.tmp.cleanup()
    def test_actual_trade_does_not_rewrite_previous_close(self):
        self.desk.store.initialize('1000000','2026-10-26')
        initial=self.desk.overview();buy=next(x for x in initial['report']['instructions'] if x['action']=='BUY')
        self.desk.record_trade(dict(id='actual',symbol=buy['symbol'],side='buy',at='2026-10-27T09:30:00+08:00',price='10',shares=100,fee='5'))
        current=self.desk.overview()
        self.assertEqual(current['report']['nav'],'1000000');self.assertEqual(current['actual']['cash'],'998995');self.assertEqual(current['actual']['positions'][buy['symbol']]['shares'],100)
    def test_open_below_support_is_rejected(self):
        from unittest.mock import patch
        self.desk.store.initialize('1000000','2026-10-26');view=self.desk.overview();g=next(x for x in view['report']['instructions'] if x['action']=='BUY')
        with patch.object(self.data,'expected_close',return_value='2026-10-26'),patch('desk.service.now',return_value='2026-10-27T10:00:00+08:00'):
            bad=self.desk.size_open(dict(symbol=g['symbol'],open=str(g['support'])))
            self.assertFalse(bad['allowed'])
            good=self.desk.size_open(dict(symbol=g['symbol'],open=str(g['reference_price'])))
            self.assertTrue(good['allowed']);self.assertLessEqual(good['shares'],g['shares'])
    def test_entitlement_requires_actual_reconciliation(self):
        account=self.desk.store.initialize('1000000','2026-01-01')
        sid,action=next((s,a) for s,actions in self.data.actions.items() for a in actions if '2026-02-01'<a['effective_date']<'2026-10-01')
        day=action['effective_date'];prior=max(d for d in self.data.calendar if d<day)
        self.desk.store.record('buy',prior+'T09:30:00+08:00','buy',dict(symbol=sid,price='10',shares=100,fee='5'),lambda es:journal(account,es))
        tasks=self.desk.pending_actions(account,self.desk.store.events());self.assertTrue(any(t['action_key']==sid+':'+day for t in tasks))
        self.desk.record_corporate(dict(id='right',symbol=sid,day=day,shares_delta=0,cash_delta='0',receivable_delta='100',note='核对券商待收分红',action_key=sid+':'+day))
        tasks=self.desk.pending_actions(account,self.desk.store.events());self.assertFalse(any(t['action_key']==sid+':'+day for t in tasks))
    def test_real_record_amendment_retains_audit(self):
        self.desk.store.initialize('1000000','2026-10-26')
        item=dict(id='first',symbol='300502.SZ',side='buy',at='2026-10-26T09:30:00+08:00',price='100',shares=100,fee='5')
        self.desk.record_trade(item)
        change=dict(item,id='correct',target_id='first',correction_reason='以券商成交回报为准',shares=200)
        self.desk.record_trade(change);self.desk.record_trade(change)
        self.assertEqual(len(self.desk.store.events()),2)
        self.assertEqual(journal(self.desk.store.account(),self.desk.store.events())['positions']['300502.SZ']['shares'],200)

class UpdateRecoveryTests(unittest.TestCase):
    def test_failed_update_resumes_same_staging_directory(self):
        from unittest.mock import patch
        from desk.refresh import refresh_market
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            fake=SimpleNamespace(as_of='2026-10-26',identity='fixed-old-snapshot',integrity={'passed':True},expected_close=lambda:'2026-10-27')
            calls=[]
            def fail(old,end,run,progress):calls.append(run);raise ValueError('模拟连接中断')
            with patch('desk.refresh.MarketData',return_value=fake),patch('desk.refresh._update',side_effect=fail):
                with self.assertRaises(ValueError):refresh_market(tmp)
            self.assertFalse((Path(tmp)/'market/current.json').exists())
            def succeed(old,end,run,progress):calls.append(run);return {'as_of':end}
            with patch('desk.refresh.MarketData',return_value=fake),patch('desk.refresh._update',side_effect=succeed):refresh_market(tmp)
            self.assertEqual(calls[0],calls[1]);self.assertEqual(json.loads((Path(tmp)/'market/active-update.json').read_text())['state'],'complete')
    def test_current_snapshot_does_not_redownload(self):
        from unittest.mock import patch
        from desk.refresh import refresh_market
        from types import SimpleNamespace
        fake=SimpleNamespace(as_of='2026-10-26',identity='fixed',integrity={'passed':True},expected_close=lambda:'2026-10-26')
        with tempfile.TemporaryDirectory() as tmp,patch('desk.refresh.MarketData',return_value=fake),patch('desk.refresh._update') as updater:
            result=refresh_market(tmp);updater.assert_not_called();self.assertEqual(result['network_requests'],0)

class CloseSchedulerTests(unittest.TestCase):
    def test_after_close_once_per_session_and_persisted_across_restart(self):
        from unittest.mock import patch,Mock
        from types import SimpleNamespace
        from desk.service import Desk
        class Clock(datetime):
            hour=15;minute=29
            @classmethod
            def now(cls,tz=None):return datetime(2026,10,27,cls.hour,cls.minute,tzinfo=TZ)
        with tempfile.TemporaryDirectory() as tmp,patch('desk.service.datetime',Clock):
            d=Desk(tmp);d._data=SimpleNamespace(calendar=['2026-10-27']);d.refresh=Mock()
            d.tick();d.refresh.assert_not_called()
            Clock.minute=30;d.tick();d.tick();d.refresh.assert_called_once()
            restarted=Desk(tmp);restarted._data=d._data;restarted.refresh=Mock();restarted.tick();restarted.refresh.assert_not_called()
