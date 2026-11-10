"""Actual event loop on synthetic data only, not historical economic results."""
from dataclasses import replace
from datetime import datetime, timedelta, time
from pathlib import Path
import tempfile
import gzip
import json
from types import SimpleNamespace
import unittest

import pandas as pd
import numpy as np

import sector_stock_admission as admission
from current_fixed_pool import PoolLine, SelectionEvidence
from current_pool_bridge import Bundle, SeriesData, TZ
from sector_account import FXQuote, QuantityRule, FeeSchedule, FeeComponent, DecisionQuote, Mark, FillWindow, dec
from history_runner import (HistoryRunner, FrozenMarket, StreamingSink, run_frozen_package,
                            RuleUnavailable, validate_calendar, prepared_directory)

RULE = QuantityRule('synthetic-lot', 100, 100, 100, True, 1)
FEES = FeeSchedule('synthetic-variable', (FeeComponent('commission', dec('.001'), basis='fill'),))


def at(day, hour):
    return datetime.combine(pd.Timestamp(day).date(), time(hour), TZ)


class SyntheticMarket:
    def __init__(self, bundle, dates, prices=None):
        self.bundle = bundle
        self.lines = {x.security_id:x for x in bundle.lines}
        self.cutoffs = tuple(at(d,17) for d in dates)
        # Includes future scheduled sessions without supplying future prices.
        self.sessions = {'A':tuple(at(d,9) for d in dates)+ (at(pd.Timestamp(dates[-1])+pd.Timedelta(days=1),9),)}
        self.prices = prices or {sid:{str(pd.Timestamp(d).date()):dec(10) for d in dates} for sid in self.lines}
        self.actions, self.notices = {}, []
        self.protocol = {'dividend_net_factor':{'A':'1'}, 'bonus_sellable_lag_sessions':{'A':1}}

    def currency(self,sid):return 'CNY'
    def rate(self,currency,when):return FXQuote(dec(1),when,'synthetic-unit')
    def currency_fx(self,when):return {'CNY':self.rate('CNY',when)}
    def market_buyable(self,when):
        return {sid:admission.Fact(True,when,when,source_id='synthetic-calendar') for sid in self.lines}
    def price(self,sid,when):return self.prices[sid][str(when.date())]
    def marks(self,when,ids):
        return {sid:Mark(self.price(sid,when),when,self.rate('CNY',when),'synthetic-raw') for sid in ids}
    def quotes(self,when,ids=None):
        return {sid:DecisionQuote(sid,self.lines[sid].issuer_id,self.lines[sid].sector_id,'CNY',
            self.price(sid,when),when,self.rate('CNY',when),RULE,FEES,'synthetic-raw') for sid in (ids if ids is not None else self.lines)}
    def lag(self,market,when,count):
        return when if count==0 else [x for x in self.sessions[market] if x>when][count-1]
    def window(self,sid,when,side,cost_multiplier):
        return FillWindow(f'{sid}:{when.isoformat()}:{side}',sid,when,self.price(sid,when),
            self.price(sid,when),self.rate('CNY',when),RULE,FEES,10**8,True,True,True,
            self.lag('A',when,1),when,'synthetic-observation','synthetic-daily-proxy')


def fixture(count=1, dates=None, targets=None):
    dates = dates or pd.date_range('2020-12-28', periods=6, freq='B')
    targets = targets or [True]*len(dates)
    lines = tuple(PoolLine(f'S{i}', 'A', f'I{i}', f'G{i//2}', 20e9, True) for i in range(count))
    evidence=SelectionEvidence('synthetic', 'a'*64, at('2026-10-22',17),'synthetic')
    series={}
    for sid in [x.security_id for x in lines]+sorted({x.sector_id for x in lines}):
        frame=pd.DataFrame({'ready':True,'target':targets if sid.startswith('S') else True,
                            'rs':.5,'segment_id':0},index=pd.DatetimeIndex(dates))
        series[sid]=SeriesData({'close_available_time':'17:00:00','raw':{'sha256':'a'*64},
                                'currency':'CNY'},states=frame)
    bundle=Bundle({},Path('/synthetic/manifest.json'),evidence,lines,series,
                  {g:g for g in sorted({x.sector_id for x in lines})},True)
    ids=list(series)
    bundle._h1_cache=(pd.DatetimeIndex(dates),{sid:j for j,sid in enumerate(ids)},np.full((len(dates),len(ids)),50.0))
    market=SyntheticMarket(bundle,dates)
    runner=HistoryRunner(bundle,market,start=at(dates[0],17),end=at(dates[-1],17),synthetic=True)
    return runner, bundle, market


class HistoryTests(unittest.TestCase):
    def test_shared_bundle_ten_accounts_and_no_same_close_fill(self):
        runner,bundle,market=fixture()
        summary=runner.run()
        self.assertEqual(summary['historical_account_runs'],0)
        self.assertEqual(summary['technical_accounts'],13)
        self.assertEqual(len(runner.accounts),13)
        for account in runner.accounts.values():
            self.assertTrue(account.fills)
            self.assertGreater(account.fills[0].at,market.cutoffs[0])
        self.assertEqual(len({id(runner.bundle) for _ in runner.accounts}),1)

    def test_future_close_signal_cannot_trigger_morning_order(self):
        runner,_,market=fixture(targets=[False,True,True,True,True,True])
        runner.run()
        first=runner.accounts['S0_base'].fills[0]
        self.assertEqual(first.at.date(),market.cutoffs[2].date())
        self.assertGreater(first.at,market.cutoffs[1])

    def test_cost_and_delay_variants_share_signal_but_change_execution(self):
        runner,_,market=fixture()
        runner.run()
        base=runner.accounts['T0_base']; cost=runner.accounts['T0_cost2']; delay=runner.accounts['T0_delay1']
        self.assertEqual(base.fills[0].shares,cost.fills[0].shares)
        self.assertEqual(cost.fills[0].fees_cny,base.fills[0].fees_cny*2)
        self.assertEqual(delay.fills[0].at.date(),market.cutoffs[2].date())

    def test_b0_has_no_six_slot_limit_and_yearly_targets_only(self):
        runner,_,_=fixture(count=8)
        runner.run()
        self.assertEqual(len(runner.accounts['S0_base'].positions),6)
        self.assertEqual(len(runner.accounts['B0_base'].positions),8)
        freezes=[x for x in runner.b0.audit_log if x['kind']=='annual_targets_frozen']
        self.assertEqual([x['year'] for x in freezes],[2020,2021])

    def test_recovered_state_does_not_cancel_latched_exit(self):
        runner,_,market=fixture(targets=[True,True,False,True,True,True])
        original=market.window
        def blocked_one(sid,when,side,mult):
            w=original(sid,when,side,mult)
            return replace(w,sell_allowed=False) if side=='sell' and when.date()==market.cutoffs[3].date() else w
        market.window=blocked_one
        runner.run()
        sales=[x for x in runner.accounts['S0_base'].fills if x.side=='sell']
        self.assertEqual(sales[0].at.date(),market.cutoffs[4].date())

    def test_end_positions_are_marked_without_inventing_liquidation(self):
        runner,_,_=fixture()
        summary=runner.run()
        self.assertFalse(summary['final_positions_closed'])
        self.assertTrue(runner.accounts['S0_base'].positions)
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'result'
            runner.write(out,summary,{'synthetic':True})
            self.assertTrue((out/'daily.jsonl').is_file())
            self.assertTrue((out/'B0_annual_targets.json').is_file())
            with self.assertRaises(FileExistsError):runner.write(out,summary,{})

    def test_production_entry_rejects_unfrozen_package_before_running(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'package.json';p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Explicit frozen'):
                run_frozen_package(p,Path(d)/'out')
            self.assertFalse((Path(d)/'out').exists())

    def test_end_after_last_cutoff_is_rejected_before_orders(self):
        runner,_,_=fixture()
        runner.end += timedelta(hours=1)
        with self.assertRaisesRegex(ValueError,'final common'):
            runner.run()
        self.assertTrue(all(not a.fills for a in runner.accounts.values()))

    def test_streaming_retains_exact_daily_accounting_without_growing_daily_list(self):
        runner,_,_=fixture()
        with tempfile.TemporaryDirectory() as d:
            runner.sink=StreamingSink(Path(d)/'result')
            summary=runner.run()
            runner.sink.close()
            with gzip.open(Path(d)/'result/daily.jsonl.gz','rt') as f:
                rows=[json.loads(x) for x in f]
            self.assertEqual(len(rows),summary['daily_rows'])
            self.assertEqual(runner.daily,[])
            self.assertEqual(runner.decisions,[])
            last={x['account']:x['nav'] for x in rows}
            self.assertEqual(last,summary['final_nav'])

    def test_dividend_paid_at_ex_midnight_is_available_before_same_day_trading(self):
        runner,_,market=fixture()
        day=market.cutoffs[2].date()
        midnight=datetime.combine(day,time.min,TZ)
        event=dict(effective_date=str(day),cash_per_old_share='1',split_ratio='1',
                   source_id='synthetic-cash',paid_at=midnight.isoformat())
        market.actions={'S0':[event]}
        runner.actions_by_date={str(day):[('S0',0,event)]}
        runner.run()
        payments=[x for x in runner.accounts['S0_base'].audit_log if x['kind']=='dividend_payment']
        self.assertEqual(payments[0]['at'],midnight)
        self.assertFalse(runner.accounts['S0_base'].dividends)


class FeePrecisionTests(unittest.TestCase):
    def test_hk_settlement_minimum_maximum_and_stamp_ceiling(self):
        fee=FeeSchedule('historical-example',(
            FeeComponent('settlement',dec('.00002'),dec('2'),basis='fill',maximum_local=dec('100')),
            FeeComponent('stamp',dec('.001'),basis='fill',rounding_unit=dec(1),rounding_mode='ceil')))
        low=fee.incremental('buy',dec('100.01'),{},{},1)
        high=fee.incremental('buy',dec('10000000'),{},{},1)
        self.assertEqual(low,{'settlement':dec(2),'stamp':dec(1)})
        self.assertEqual(high['settlement'],dec(100))

    def test_nearest_cent_and_par_value_are_not_market_value(self):
        fee=FeeSchedule('par-example',(
            FeeComponent('levy',dec('.000027'),basis='fill',rounding_unit=dec('.01')),
            FeeComponent('transfer',dec('.0003'),basis='fill',amount_basis='par_value')))
        result=fee.incremental('buy',dec(10000),{},{},1,shares=100,par_value=1)
        self.assertEqual(result['levy'],dec('.27'))
        self.assertEqual(result['transfer'],dec('.03'))
        with self.assertRaisesRegex(ValueError,'Par-value'):
            fee.incremental('buy',dec(10000),{},{},1,shares=100)


class FrozenMarketTests(unittest.TestCase):
    def market(self):
        dates=pd.date_range('2020-01-01',periods=24,freq='B')
        m=object.__new__(FrozenMarket)
        m.lines={'A':PoolLine('A','A','I','G',20e9,True)}
        m.sessions={'A':tuple(at(d,9) for d in dates)}
        m.cutoffs=tuple(at(d,17) for d in dates)
        m.raw={'A':pd.DataFrame({'open':10.,'high':1001.,'low':1.,'close':1000.,
                                'volume':10000.,'valid_price':True},index=dates)}
        m.raw['A'].loc[dates[20],'volume']=1e9
        m.bundle=SimpleNamespace(series={'A':SimpleNamespace(record={
            'close_available_time':'17:00:00','currency':'CNY','raw':{'sha256':'a'*64}})})
        base={'from':'2019-01-01','to':None,'source_id':'synthetic','basis':'explicit_research_proxy','proxy_id':'synthetic'}
        m.rules={'quantity_versions':{'A':[dict(base,rule=as_quantity())]},
            'fee_versions':{'SSE_MAIN':[dict(base,schedule={'schedule_id':'synthetic','components':[]})]},
            'availability_versions':{'A':[dict(base,buy_allowed=True,sell_allowed=True)]},
            'venue_versions':{'A':[dict(base,venue='SSE_MAIN')]}}
        m.protocol={'approved_proxy_ids':['synthetic'],'fx_max_age_days':7,'participation_rate':'.01',
            'daily_execution':{'A':{'price_limit_policy':'conservative_hl_proxy','reject_flat_day':True,
                                    'slippage_bps':'0','stress_slippage':True}},
            'sellable_lag_sessions':{'A':1},'settlement_lag_sessions':{'A':0}}
        m.fx={};m._fx_times={};m._fx_cache={};m.notices=[];m._notice_keys={};m.actions={}
        return m,dates

    def test_intraday_mark_uses_open_not_future_close(self):
        m,dates=self.market()
        self.assertEqual(m.latest_mark('A',at(dates[20],9)).raw_price,dec(10))
        self.assertEqual(m.latest_mark('A',at(dates[20],17)).raw_price,dec(1000))
        self.assertEqual(m.latest_mark('A',at(dates[20],8)).known_at,at(dates[19],17))

    def test_future_invalid_hlc_does_not_change_observed_open(self):
        m,dates=self.market()
        old=m.latest_mark('A',at(dates[20],9))
        m.raw['A'].loc[dates[20],['high','low','close','valid_price']]=[0,0,0,False]
        self.assertEqual(m.latest_mark('A',at(dates[20],9)),old)
        self.assertEqual(m.latest_mark('A',at(dates[20],17)).known_at,at(dates[19],17))

    def test_unobserved_open_is_not_a_mark(self):
        m,dates=self.market()
        m.raw['A']['observed_bar']=True
        m.raw['A'].loc[dates[20],'observed_bar']=False
        self.assertEqual(m.latest_mark('A',at(dates[20],9)).known_at,at(dates[19],17))

    def test_split_and_dividend_do_not_create_nav_from_suspended_old_units(self):
        m,dates=self.market()
        m.raw['A'].loc[:,'close']=10.
        m.raw['A']=m.raw['A'].drop(dates[20])
        m.actions={'A':[dict(effective_date=str(dates[20].date()), cash_per_old_share='2',
                            split_ratio='2',source_id='synthetic-action')]}
        with self.assertRaisesRegex(RuleUnavailable,'valuation policy'):
            m.latest_mark('A',at(dates[20],17))
        m.protocol['stale_action_mark_policy']='theoretical_ex_reference'
        mark=m.latest_mark('A',at(dates[20],17))
        self.assertEqual(mark.raw_price,dec(4))
        self.assertEqual(200*mark.raw_price+100*dec(2),dec(1000))
        self.assertEqual(mark.known_at,at(dates[19],17))
        self.assertIn('derived_ex_reference',mark.source_id)

    def test_before_own_market_open_action_reference_then_observed_raw_open(self):
        m,dates=self.market()
        m.raw['A'].loc[:,'close']=10.
        m.raw['A'].loc[dates[20],'open']=5.
        m.sessions['A']=tuple(x+timedelta(hours=1) for x in m.sessions['A'])
        m.actions={'A':[dict(effective_date=str(dates[20].date()),cash_per_old_share='0',
                            split_ratio='2',source_id='synthetic-action')]}
        m.protocol['stale_action_mark_policy']='theoretical_ex_reference'
        before=m.latest_mark('A',at(dates[20],9));after=m.latest_mark('A',at(dates[20],10))
        self.assertEqual(before.raw_price,after.raw_price)
        self.assertIn('derived_ex_reference',before.source_id)
        self.assertNotIn('derived_ex_reference',after.source_id)

    def test_fee_schedule_uses_dated_venue_without_ah_fallback(self):
        m,dates=self.market();now=at(dates[20],9)
        row=m.rules['fee_versions']['SSE_MAIN'][0]
        m.rules['fee_versions']['BSE']=[dict(row,schedule={'schedule_id':'synthetic-BSE','components':[]})]
        self.assertEqual(m.fees('A',now).schedule_id,'synthetic')
        m.rules['venue_versions']['A'][0]['venue']='BSE'
        self.assertEqual(m.fees('A',now).schedule_id,'synthetic-BSE')
        del m.rules['fee_versions']['BSE']
        m.rules['fee_versions']['A']=[row]
        with self.assertRaises(RuleUnavailable):m.fees('A',now)

    def test_unavailable_prefix_and_source_gap_stop_execution_and_inventory_valuation(self):
        for kind in ('prefix','gap'):
            m,dates=self.market();now=at(dates[20],9)
            record=m.bundle.series['A'].record
            if kind=='prefix':record['unavailable_from']=str(dates[20].date())
            else:record['segments']=[dict(start=str(dates[0].date()),end=str(dates[19].date())),
                                    dict(start=str(dates[21].date()),end=str(dates[-1].date()))]
            with self.assertRaises(RuleUnavailable):m.latest_mark('A',now)
            self.assertIsNone(m.window('A',now,'sell',1))
            self.assertIsNone(m.window('A',now,'buy',1))
            self.assertIsNone(m.market_buyable(now)['A'].value)

    def test_capacity_uses_prior_twenty_not_today_volume(self):
        m,dates=self.market()
        w=m.window('A',at(dates[20],9),'buy',1)
        self.assertEqual(w.capacity_shares,100)
        m.raw['A'].loc[dates[20],'volume']=50
        self.assertEqual(m.window('A',at(dates[20],9),'buy',1).capacity_shares,50)

    def test_neeeq_history_is_not_an_a_share_execution_line(self):
        m,dates=self.market()
        m.rules['venue_versions']['A'][0]['venue']='NEEQ'
        now=at(dates[20],9)
        self.assertIsNone(m.market_buyable(now)['A'].value)
        self.assertIsNone(m.window('A',now,'buy',1))

    def test_calendar_rejects_duplicate_or_two_same_day_session_opens(self):
        now=at('2020-01-02',9)
        for opens in ((now,now),(now,now+timedelta(hours=4))):
            with self.assertRaisesRegex(ValueError,'unique open'):
                validate_calendar((at('2020-01-02',17),),{'A':opens})

    def test_action_before_own_open_lag_one_means_next_local_session_date(self):
        m,dates=self.market()
        m.sessions['H']=tuple(x+timedelta(minutes=30) for x in m.sessions['A'])
        self.assertEqual(m.lag('H',at(dates[20],9),1),at(dates[21],9)+timedelta(minutes=30))

    def test_prepared_manifest_cannot_authenticate_different_file_from_bridge_load(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'certified-other.json';path.write_text('{}')
            with self.assertRaisesRegex(ValueError,'exact manifest.json'):
                prepared_directory(path)
            self.assertEqual(prepared_directory(Path(d)/'manifest.json'),Path(d).resolve())

    def test_future_fx_and_unapproved_proxy_cannot_fill(self):
        m,dates=self.market()
        now=at(dates[20],9)
        m.fx={'HKD':[FXQuote(dec('.9'),at(dates[21],9),'future')]}
        m._fx_times={'HKD':[at(dates[21],9)]}
        with self.assertRaises(RuleUnavailable):m.rate('HKD',now)
        m.protocol['approved_proxy_ids']=[]
        self.assertIsNone(m.window('A',now,'buy',1))


def as_quantity():
    return dict(rule_id=RULE.rule_id,buy_minimum=RULE.buy_minimum,buy_step=RULE.buy_step,
                sell_step=RULE.sell_step,allow_full_exit_odd=RULE.allow_full_exit_odd,fill_step=RULE.fill_step)


if __name__=='__main__':unittest.main()
