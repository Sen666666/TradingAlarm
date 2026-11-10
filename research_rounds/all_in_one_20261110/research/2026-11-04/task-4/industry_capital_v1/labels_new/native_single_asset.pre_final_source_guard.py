"""Isolated native LR.Account labels; no portfolio policy or new CA ledger.

Account construction and hypothetical fills are counted. The native market,
fees, lots, T+1, CA and settlement methods are reused unchanged.
"""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, time as daytime
from collections import defaultdict
from bisect import bisect_right, bisect_left
from decimal import Decimal as D
import gzip, hashlib, inspect, json, sys

sys.dont_write_bytecode = True
O = Path(__file__).resolve().parent
WORK = O.parent.parent
sys.path.insert(0, str(WORK/'new_price_trend_v1/funding'))
import entry_adapter as E
J, LR = E.J, E.J.LR
N, L = J.M.N, LR.L
FastMarket = J.M.E.FastMarket
SOURCES = {}
COUNTS = defaultdict(int)

def bind(path):
    path = Path(path).resolve()
    SOURCES[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return path

def read(path):
    return json.loads(bind(path).read_text())

def gzread(path, lines=False):
    with gzip.open(bind(path), 'rt') as h:
        return list(map(json.loads,h)) if lines else json.load(h)

def encoded(x):
    return N.encoded(x)

class Provider:
    def __init__(self):
        import pandas as pd
        self.pd = pd
        self.rules = read(J.M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json')
        self.protocol = read(J.BP.C.OLD/'inputs-v2/economic-protocol.json')
        self.records = {r['series_id']:r for r in read(J.M.P/'manifest.json')['series']}
        self.sm = {r['symbol']:r for r in read('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
        self.meta = read(J.M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json')
        input_manifest=read(J.BP.C.OLD/'inputs-v2/input-manifest.json')
        selection_path=bind(input_manifest['selection']['path'])
        assert SOURCES[str(selection_path)]==input_manifest['selection']['sha256']
        self.selection={r['security_id']:r for r in json.loads(selection_path.read_text())['lines']}
        self.markets, self.facts, self.environment, self.stop_cache = {}, {}, {}, {}
        for w in ('long','strong'):
            ds = gzread(WORK/'new_price_trend_v1/funding/runs'/(w+'_OFF')/'pair/daily.jsonl.gz',True)
            self.environment[w] = {r['at'][:10]:bool(r['on']) for r in ds}
        for method in (LR.Account.reserve_quantity, LR.Account.fill_buy, LR.Account.fill_exit,
                       LR.Account.split, LR.Account.accrue_dividend, N.HistoryRunner._actions,
                       N.HistoryRunner._payments, FastMarket.__init__, FastMarket.window,
                       FastMarket.latest_mark, LR.preview, LR.fees):
            bind(inspect.getsourcefile(method))
        bind(__file__); bind(O.parent/'MATCHED_PROTOCOL.txt')

    def for_sid(self, sid):
        if sid not in self.markets:
            meta = self.meta[sid]
            line = SimpleNamespace(**self.selection[sid])
            assert line.sector_id==meta['sector_id'] and line.market=='A'
            record = self.records[sid]
            bundle = SimpleNamespace(lines=(line,), series={sid:SimpleNamespace(record=record)},
                                     manifest_path=J.M.P/'manifest.json')
            # The unchanged constructor reads only this one identified security.
            market = FastMarket(bundle,self.rules,[],self.protocol)
            rawpath = N.checked_ref(record['raw'],J.M.P)
            bind(rawpath); bind(record['adjustment']['actions']['path'])
            fpath = bind(self.sm[sid]['refs']['facts'])
            assert SOURCES[str(fpath)] == self.sm[sid]['output_sha256'][str(fpath)]
            f = self.pd.read_parquet(fpath)
            facts = J.M.E.Facts.__new__(J.M.E.Facts)
            facts.f = {sid:f}; facts.market = market; facts.cache = {}; facts.day = None
            self.markets[sid],self.facts[sid] = market,facts
            COUNTS['single_security_native_market_providers'] += 1
        return self.markets[sid],self.facts[sid]

    def stop(self, window, sid, opened, initial_source):
        """Find the frozen-environment first close invalidation, never an entry input."""
        import numpy as np
        _, facts = self.for_sid(sid)
        env = self.environment[window]
        key=window,sid,initial_source
        if key not in self.stop_cache:
            f=facts.f[sid];days=list(env)
            p=f.index.searchsorted(self.pd.DatetimeIndex(days),side='right')-1
            indices=np.maximum(p,0)
            source=self.pd.to_numeric(f.segment_id,errors='coerce').to_numpy(dtype=float,na_value=np.nan)[indices]
            target=self.pd.to_numeric(f.i_target,errors='coerce').to_numpy(dtype=float,na_value=np.nan)[indices]
            known=(p>=0)&np.isfinite(source)&np.isfinite(target)
            bad=(~known)|(source!=initial_source)|(target!=1)|~np.array(list(env.values()),dtype=bool)
            result=[]
            for j in np.flatnonzero(bad):
                if p[j]<0 or not np.isfinite(source[j])or source[j]!=initial_source:reason,unknown='source_boundary',True
                elif not np.isfinite(target[j]):reason,unknown='I_unknown',True
                elif not env[days[j]]:reason,unknown='baseline_ACT_pause',False
                else:reason,unknown='I_structure_exit',False
                result.append((days[j],datetime.fromisoformat(days[j]+'T15:10:00+08:00'),reason,unknown))
            self.stop_cache[key]=([r[0]for r in result],result)
        days,rows=self.stop_cache[key]
        i=bisect_left(days,opened.date().isoformat())
        return rows[i][1:]if i<len(rows)else(None,None,False)

    def path(self, event, quantity=None, trace=False):
        """One isolated shadow. q_min normally; explicit q only for actual calibration."""
        sid,window = event['sid'],event['window']
        market,facts = self.for_sid(sid)
        signal = datetime.fromisoformat(event['signal_day']+'T15:10:00+08:00')
        opened = datetime.fromisoformat(event['OPEN']+'T09:30:00+08:00')
        finalday = next(reversed(self.environment[window]))
        finish = datetime.fromisoformat(finalday+'T15:10:00+08:00')
        source = int(facts.row(sid,signal).segment_id)
        stop_at,stop_reason,unknown_source = self.stop(window,sid,opened,source)
        quote = market.quotes(signal,[sid]).get(sid)
        if quote is None:
            return dict(key=event['key'],status='unknown_signal_quote',known_net=False)
        i = dict(event['original_intent'])
        for k in ('budget','floor','risk_budget','frozen_floor_raw','signal_price','reference_price'):
            if k in i:i[k]=D(str(i[k]))
        i['clock'] = J.BP.A.Clock(signal,opened,signal.date()); i['quote']=quote
        op = D(str(market.raw[sid].loc[self.pd.Timestamp(opened.date()),'open']))
        preview,why = LR.preview(i,op,facts.factor(sid,opened),market.quantity(sid,opened),market.fees(sid,opened))
        if why:return dict(key=event['key'],status='preview_'+why,known_net=False)
        q = market.quantity(sid,opened).buy_minimum if quantity is None else int(quantity)
        assert 0<q<=preview['maxq'],(event['key'],q,preview['maxq'])
        gross = D(q)*preview['price']; fee = LR.fees(q,preview['price'],preview['schedule'],'buy',quote.par_value)
        capital = gross+fee
        a = LR.Account('SINGLE_ASSET_SHADOW',market,facts)
        COUNTS['single_asset_shadow_paths'] += 1
        # Explicit initial funding of a unit-cost evaluation, before any event.
        a.available=a.initial_cash=capital
        a.current_nav=D(str(event.get('decision_NAV','1000000')))
        harness=SimpleNamespace(market=market,accounts={'shadow':a},applied_actions=set(),
            actions_by_date=defaultdict(list),b0=N.B0Controller())
        for n,action in enumerate(market.actions.get(sid,())):
            harness.actions_by_date[action['effective_date']].append((sid,n,action))
        opens = market.sessions['A']
        # No-op passive hold times can be skipped: no interest or reinvestment.
        # At every retained event, native settlements/payments process all due cash.
        event_times={opened,datetime.fromisoformat(event['OPEN']+'T15:10:00+08:00'),finish}
        for day in harness.actions_by_date:
            at=datetime.combine(datetime.fromisoformat(day).date(),daytime.min,N.TZ)
            if opened<=at<=finish:event_times.add(at)
        if stop_at is not None:
            event_times.add(stop_at)
            event_times.update(t for t in opens if stop_at<t<=finish)
            event_times.update(datetime.fromisoformat(t.date().isoformat()+'T15:10:00+08:00')
                               for t in opens if stop_at<t<=finish)
        complete_at=None;common_close=None;entry=None;exit_proposed=None;last_quote=quote
        for at in sorted(event_times):
            if common_close is not None and at>common_close:break
            a.settle_due(at)
            N.HistoryRunner._actions(harness,at)
            N.HistoryRunner._payments(harness,a,at)
            if at==opened:
                a.reserve_quantity(i,q,preview['price'],preview['schedule'],at)
                w=market.window(sid,at,'buy',D(1))
                if w:entry=a.fill_buy(sid,w)
                a.settle_due(at)
            elif at in opens and sid in a.exits:
                w=market.window(sid,at,'sell',D(1))
                if w:a.fill_exit(sid,w)
                a.settle_due(at)
                if entry and not a.quantity(sid):
                    complete_at=at
                    common_close=datetime.fromisoformat(at.date().isoformat()+'T15:10:00+08:00')
            if at.hour==15 and at.minute==10:
                a.expire_day_buys(at)
                if entry is None and at.date()==opened.date():
                    common_close=at
                    break
                if at==stop_at and entry and a.quantity(sid) and sid not in a.exits:
                    try:last_quote=market.quotes(at,[sid]).get(sid) or last_quote
                    except Exception:unknown_source=True
                    a.sell(sid,J.BP.A.Clock(at,opens[bisect_right(opens,at)],at.date()),last_quote,
                           [x['id']for x in a.live(sid)],stop_reason)
                    exit_proposed=at
        terminal=common_close or finish
        if not entry:
            # The day lease expires even if no native window could fill it.
            a.expire_day_buys(terminal)
            out=dict(key=event['key'],status='entry_nonfill',known_net=False,
                     window=window,sid=sid,signal_day=event['signal_day'],OPEN=event['OPEN'],
                     source_I_epoch=event['original_intent']['epoch'],filled_shares=0,
                     entry_cash_actual='0',initial_seed_cash=str(a.initial_cash),
                     hypothetical_entry_shares=0,horizon_CLOSE=terminal.date().isoformat(),
                     horizon_CLOSE_day=terminal.date().isoformat(),terminal_qty=0,
                     terminal_censored=False,unknown_reason='Original daily entry window did not fill')
        else:
            try:marks=market.marks(terminal,a.positions)
            except Exception as exc:
                return dict(key=event['key'],window=window,sid=sid,status='unknown_terminal_mark',
                    known_net=False,horizon_CLOSE=terminal.date().isoformat(),remaining_shares=a.quantity(sid),
                    error_type=type(exc).__name__,error=str(exc),single_asset_shadow_path=True,
                    new_portfolio_policy_account=False)
            balance=a.balance(terminal,marks)
            remaining=a.quantity(sid);drag=D(0);estimate_fee=D(0);mark=None
            if remaining:
                mark=marks[sid].cny_price(terminal)
                px=mark*(D(1)-LR.SLIP)
                schedule=market.fees(sid,terminal)
                if sid in a.exits:
                    costs=a._fee(a.exits[sid],schedule,'sell',D(remaining)*px,
                                 shares=remaining,par_value=quote.par_value)
                    estimate_fee=sum(costs.values(),D(0))
                else:estimate_fee=LR.fees(remaining,px,schedule,'sell',quote.par_value)
                drag=D(remaining)*(mark-px)+estimate_fee
            actual_cost=entry.gross_cny+entry.fees_cny
            pnl=balance['nav']-a.initial_cash
            net=pnl-drag
            out=dict(key=event['key'],status='unknown_source'if unknown_source else'closed'if not remaining else'censored_open',
                known_net=not unknown_source,window=window,sid=sid,signal_day=event['signal_day'],OPEN=event['OPEN'],
                requested_shadow_shares=q,hypothetical_entry_shares=entry.shares,
                entry_partial=entry.shares<q,entry_buy_cash=str(actual_cost),
                full_exit_at=str(complete_at)if complete_at else None,
                exit_proposal_at=str(exit_proposed)if exit_proposed else None,exit_reason=stop_reason,
                horizon_CLOSE=terminal.date().isoformat(),remaining_shares=remaining,
                native_nav=str(balance['nav']),seed_cash=str(a.initial_cash),
                gross_native_profit=str(pnl),net_liquidation_profit=str(net),
                net_return_pct=str(net/actual_cost*100)if not unknown_source else None,
                estimated_terminal_sale_fee=str(estimate_fee),terminal_liquidation_drag=str(drag),
                terminal_mark=str(mark)if mark is not None else None,
                terminal_mark_derived=bool(remaining and ':derived_ex_reference:'in marks[sid].source_id),
                actual_shadow_fees=str(a.fees_cny),
                dividend_net_recognized=str(sum((x['dividend']for x in a.layers),D(0))),
                cash_or_receivables_balance={k:str(v)for k,v in balance.items()},
                fractional_action_proxy_count=sum(x['kind']=='split_fraction_floor_proxy'for x in a.audit_log),
                CA_events=sum(x['kind']in('dividend_accrual','split','split_fraction_floor_proxy')for x in a.audit_log),
                single_asset_shadow_path=True,new_portfolio_policy_account=False,
                environment='Frozen original baseline ACT; no shared-capital counterfactual')
            out.update(source_I_epoch=event['original_intent']['epoch'],filled_shares=entry.shares,
                entry_cash_actual=str(actual_cost),initial_seed_cash=str(a.initial_cash),
                net_pnl_original_ledger=str(pnl),terminal_NAV=str(balance['nav']),
                horizon_CLOSE_day=terminal.date().isoformat(),terminal_qty=remaining,
                terminal_net_liquidation_estimate=str(balance['nav']-drag),
                wealth_from_invested_Cn_excluding_unspent_seed=str(actual_cost+pnl),
                wealth_from_invested_Cn_net_liquidation=str(actual_cost+net),
                terminal_censored=bool(remaining),unknown_reason=None)
            if unknown_source:
                out['gross_native_profit']=None
                out['net_liquidation_profit']=None
                out['unknown_economic_reason']='Source/structure continuity cannot be safely joined'
                out['unknown_reason']=out['unknown_economic_reason']
                out['net_pnl_original_ledger']=None
                out['wealth_from_invested_Cn_excluding_unspent_seed']=None
                out['wealth_from_invested_Cn_net_liquidation']=None
        if trace:
            out['native_trace']=encoded(dict(trades=a.trades,layers=a.layers,audit=a.audit_log,
                                             fills=a.fills,positions=a.positions))
        return out
