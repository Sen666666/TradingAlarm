"""Paper execution tests use synthetic sessions; no broker or network access."""
import copy
import json
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from desk.paper import Paper
from desk.store import Store, journal
from desk.data import MarketData, TZ

DAYS = ['2026-10-22', '2026-10-23', '2026-10-26', '2026-10-27']
SID = '002439.SZ'


class Fixture:
    def __init__(self, folder, rulebook):
        self.as_of = DAYS[0]; self.identity = 'fixture'; self.integrity = {'passed': True}
        self.calendar = DAYS+['2026-10-28']; self.signals_dir = Path(folder)
        self.meta = {SID:dict(symbol=SID, name='测试股票', industry='测试行业', sector_id='URFI881272', current_cap_cny='20000000000')}
        self.sectors = {'URFI881272':'测试行业'}; self.rulebook = rulebook; self.actions = {}
        self.recovery = pd.DataFrame(dict(market=[1,1.01,1.02,1.03], prior_high63=[1,1,1.01,1.02], breadth=[.7]*4, breakout=[False]*4), index=pd.to_datetime(DAYS))
        self.prices = dict(zip(DAYS, [20,22,23,24])); self.targets = dict.fromkeys(DAYS, True)
        self.buy = {DAYS[0]}; self.opens = dict(zip(DAYS, [19,25,16,24]))
        self.write()

    def write(self, missing=()):
        rows=[dict(date=d, open=self.opens[d], raw_open=self.opens[d], raw_volume=10000, volume=10000, observed_bar=True, price_eligible=True, synthetic_event_bar=False) for d in DAYS if d not in missing]
        pd.DataFrame(rows).set_index('date').set_axis(pd.to_datetime([r['date'] for r in rows])).to_parquet(self.signals_dir/f'{SID}.parquet')

    def expected_close(self, current=None):
        current = current or datetime.now(TZ)
        return max(d for d in DAYS if d < current.date().isoformat() or (d == current.date().isoformat() and current.hour >= 15))

    def row(self, sid, day):
        if sid in self.sectors:
            return dict(symbol=sid, ready=True, trend_up=True, observed_on=day, rs_h1=90)
        return dict(symbol=sid,name='测试股票',industry='测试行业',sector_id='URFI881272',ready=True,fresh=True,observed_on=day,trend_up=self.targets[day],buy_event=day in self.buy,rs_h1=80,raw_close=self.prices[day],floor_raw=15,grade=2)

    def status(self):
        return dict(as_of=self.as_of, current=True)


class PaperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = MarketData('/tmp/paper-test-readonly')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = Fixture(self.tmp.name, self.real.rulebook)
        self.paper = Paper(self.tmp.name, lambda:self.data)
        self.paper.store.initialize('1000000', DAYS[0])

    def tearDown(self):
        self.tmp.cleanup()

    def sync(self, day, hour=16):
        self.paper.sync(datetime.fromisoformat(day+f'T{hour:02d}:00:00+08:00'))

    def test_next_open_exact_price_no_same_close_fill(self):
        self.sync(DAYS[0]); self.assertEqual(self.paper.store.events(), [])
        self.data.as_of = DAYS[1]; self.sync(DAYS[1])
        e = self.paper.store.events()[0]
        self.assertEqual(e['at'],DAYS[1]+'T09:30:00+08:00')
        self.assertEqual(D(e['payload']['price']),D(25))
        self.assertEqual(e['payload']['shares'],6000)
        self.assertNotEqual(D(e['payload']['price']),D(self.data.prices[DAYS[0]]))
        ledger=journal(self.paper.store.account(), self.paper.store.events())
        self.assertEqual(D(ledger['cash']),D('1000000')-D(25)*6000-D(e['payload']['fee']))
        self.assertEqual(len(self.paper.store.days()),2)

    def test_sell_at_next_monday_open_and_t1(self):
        self.data.targets[DAYS[1]]=False; self.data.prices[DAYS[1]]=12
        self.data.as_of=DAYS[2]; self.sync(DAYS[2])
        es=self.paper.store.events(); self.assertEqual([e['kind'] for e in es],['buy','sell'])
        self.assertEqual(es[1]['at'],DAYS[2]+'T09:30:00+08:00')
        self.assertEqual(D(es[1]['payload']['price']),D(16))
        self.assertEqual(self.paper.view()['holdings'],[])
        self.assertTrue(D(self.paper.view()['fees'])>0)

    def test_restart_and_repeated_sync_cannot_duplicate(self):
        self.data.as_of=DAYS[2]; self.sync(DAYS[2]); before=self.paper.store.events(); days=self.paper.store.days()
        restarted=Paper(self.tmp.name,lambda:self.data); restarted.sync(datetime(2026,10,26,16,tzinfo=TZ))
        self.assertEqual(restarted.store.events(),before);self.assertEqual(restarted.store.days(),days)
        self.assertEqual(restarted.view()['nav'],self.paper.view()['nav'])

    def test_concurrent_execution_once(self):
        self.sync(DAYS[0]); self.data.as_of=DAYS[1]
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _:self.sync(DAYS[1]), range(4)))
        self.assertEqual(len(self.paper.store.events()),1)
        self.assertEqual(len(self.paper.store.executions()),1)

    def test_intraday_open_fills_without_future_close_decision(self):
        self.paper.provider=lambda data,day,sids:{SID:dict(symbol=SID,day=day,open='25',source='fixture',actions=[])}
        self.sync(DAYS[1],10)
        self.assertEqual(len(self.paper.store.events()),1)
        self.assertEqual([d['day'] for d in self.paper.store.days()],[DAYS[0]])
        v=self.paper.view();self.assertEqual(v['holdings'][0]['mark_basis'],'开盘')
        self.assertEqual(v['holdings'][0]['mark_day'],DAYS[1]);self.assertEqual(v['curve'][-1]['basis'],'开盘，待收盘')

    def test_before_0935_does_not_fill(self):
        self.paper.provider=lambda *a:self.fail('too early')
        self.sync(DAYS[1],9);self.assertEqual(self.paper.store.events(),[])

    def test_missing_open_waits_and_retries_original_date(self):
        self.paper.provider=lambda *a:{}
        self.sync(DAYS[1],10);self.assertEqual(self.paper.store.events(),[])
        self.assertEqual(self.paper.store.setting('waiting')['day'],DAYS[1])
        self.paper.provider=lambda data,day,sids:{SID:dict(symbol=SID,day=day,open='25',source='late fixture',actions=[])}
        self.sync(DAYS[2],10)
        self.assertEqual(self.paper.store.events()[0]['at'][:10],DAYS[1])

    def test_open_at_support_skipped(self):
        self.data.opens[DAYS[1]]=15;self.data.write();self.data.as_of=DAYS[1]
        self.sync(DAYS[1]);self.assertEqual(self.paper.store.events(),[])
        self.assertIn('保护位',self.paper.store.executions()[0]['outcomes'][0]['reason'])

    def test_lower_open_does_not_exceed_guidance_share_cap(self):
        self.data.opens[DAYS[1]]=16;self.data.write();self.data.as_of=DAYS[1];self.sync(DAYS[1])
        self.assertEqual(self.paper.store.events()[0]['payload']['shares'],7500)

    def test_no_bar_in_completed_session_expires_without_fake_fill(self):
        self.data.write(missing=[DAYS[1]]);self.data.as_of=DAYS[1];self.sync(DAYS[1])
        self.assertEqual(self.paper.store.events(),[])
        self.assertEqual(self.paper.store.executions()[0]['outcomes'][0]['status'],'skipped')

    def test_execution_transaction_rolls_back_on_error(self):
        self.sync(DAYS[0]);self.data.as_of=DAYS[1]
        with patch.object(self.data.rulebook,'fees',side_effect=ValueError('fee error')):
            with self.assertRaisesRegex(ValueError,'fee error'):self.sync(DAYS[1])
        self.assertEqual(self.paper.store.events(),[]);self.assertEqual(self.paper.store.executions(),[])
        self.sync(DAYS[1]);self.assertEqual(len(self.paper.store.events()),1)

    def test_decision_is_immutable_after_data_changes(self):
        self.sync(DAYS[0]);before=self.paper.store.days()[0]
        self.data.prices[DAYS[0]]=100;self.data.buy.clear();self.data.as_of=DAYS[1]
        self.sync(DAYS[1]);self.assertEqual(self.paper.store.days()[0],before)
        self.assertEqual(self.paper.store.events()[0]['payload']['shares'],6000)

    def test_real_account_is_untouched(self):
        real=Store(Path(self.tmp.name)/'account.sqlite3');real.initialize('800000',DAYS[0]);before=real.fingerprint()
        self.data.as_of=DAYS[1];self.sync(DAYS[1]);self.assertEqual(real.fingerprint(),before)

    def test_equity_matches_independent_cash_plus_positions(self):
        self.data.as_of=DAYS[2];self.sync(DAYS[2]);v=self.paper.view()
        nav=D(v['cash'])+D(v['receivable'])+sum(D(h['mark_price'])*h['shares'] for h in v['holdings'])
        self.assertEqual(nav,D(v['nav']));self.assertEqual(D(v['profit']),nav-D(1000000))
        self.assertEqual(D(v['holdings'][0]['cost']),D(150000)+D(v['fees']))

    def test_integrity_failure_stops_execution(self):
        self.data.integrity['passed']=False
        with self.assertRaisesRegex(ValueError,'完整性'):self.sync(DAYS[1])
        self.assertEqual(self.paper.store.events(),[])

    def test_real_four_stock_guidance_is_identical(self):
        from desk.strategy import build_report
        baseline=build_report(self.real,dict(initial_cash='1000000',started_on='2026-10-26'),[])
        p=Paper(Path(self.tmp.name)/'real-guidance',lambda:self.real)
        p.store.initialize('1000000','2026-10-26');p.sync(datetime(2026,10,26,16,tzinfo=TZ))
        result=p.store.days()[0]
        self.assertEqual(result['instructions'],baseline['instructions'])
        self.assertEqual(len(result['instructions']),4)

    def test_start_is_fixed_million_and_idempotent(self):
        fresh=Paper(Path(self.tmp.name)/'new',lambda:self.data)
        with patch.object(fresh,'request_sync',return_value={'state':'queued'}):
            fresh.start(); before=fresh.store.account();fresh.start()
        self.assertEqual(fresh.store.account(),before)
        self.assertEqual(D(before['initial_cash']),D(1000000))
        self.assertEqual(before['started_on'],DAYS[0])
        self.assertEqual(fresh.store.setting('execution_contract')['slippage_bps'],0)

    def test_corporate_entitlement_preserves_value_and_no_fake_available_cash(self):
        self.data.actions[SID]=[dict(effective_date=DAYS[2],classification='ordinary_cash_and_pro_rata_bonus',split_ratio='2',cash_per_old_share='1',paid_at=None,new_shares_sellable_at=None)]
        self.data.as_of=DAYS[2];self.sync(DAYS[2]);v=self.paper.view()
        self.assertEqual(v['holdings'][0]['shares'],12000)
        self.assertEqual(D(v['receivable']),D(6000))
        self.assertEqual(v['holdings'][0]['sellable_shares'],6000)
        self.assertEqual(D(v['holdings'][0]['cost']),D(150000)+D(v['fees']))

    def test_concurrent_view_has_one_coherent_cash_and_fill_snapshot(self):
        self.sync(DAYS[0]);self.data.as_of=DAYS[1]
        with ThreadPoolExecutor(max_workers=2) as pool:
            execution=pool.submit(self.sync,DAYS[1])
            for _ in range(15):
                v=self.paper.view(); buys=[e for e in v['events'] if e['kind']=='buy']
                self.assertEqual(len(buys),len(v['holdings']))
                self.assertEqual(len(buys),sum(o['status']=='filled' for r in v['executions'] for o in r['outcomes']))
                if buys:self.assertLess(D(v['cash']),D(1000000))
            execution.result()


if __name__=='__main__':
    unittest.main()
