"""ACT20_BREAK close decisions driven by the actual journal, no synthetic fills."""
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal as D
from . import admission as A
from .data import TZ, clean
from .store import journal,effective_events,lot_sellable


def advance_risk(state, nav, flat, breakout):
    s = dict(state)
    s['peak'] = str(max(D(s['peak']),nav)) if s['on'] else s['peak']
    dd = D(1)-nav/D(s['peak']); event = None
    if s['on']:
        if dd >= D('.2'): s['on'] = False; event = 'pause'
    elif flat and breakout:
        s.update(on=True,peak=str(nav),episode=s['episode']+1); event='resume'
    return s,dd,event


def packet(data, day):
    at = datetime.fromisoformat(day+'T15:10:00+08:00')
    future = [d for d in data.calendar if d > day]
    next_day = future[0] if future else None
    # Unknown next-session date is never shown as a verified execution date.
    execution = datetime.fromisoformat((next_day or (at+timedelta(days=1)).date().isoformat())+'T09:30:00+08:00')
    clock = A.Clock(at,execution,at.date())
    def fact(v, observed=at): return A.Fact(v,at,at,observed_at=observed,source_id='ACT20_BREAK/THS')
    def rank(v): return A.Rank(v,at,at) if v is not None else None
    sectors = []
    sector_ready = {}
    for sid in data.sectors:
        r = data.row(sid,day)
        sector_ready[sid] = bool(r and r['ready'])
        sectors.append(A.Sector(sid,fact(r['trend_up'] if r else None,datetime.fromisoformat(r['observed_on']+'T15:05:00+08:00') if r else None),rank(r['rs_h1'] if r else None)))
    securities=[]
    for sid,meta in data.meta.items():
        r = data.row(sid,day)
        securities.append(A.Security(sid,fact(sid),fact(meta['sector_id']),fact(bool(r and r['ready'] and sector_ready[meta['sector_id']])),fact(bool(r and r['fresh'] and r['buy_event'])),fact(float(meta['current_cap_cny'])),fact(r['trend_up'] if r and r['ready'] else None),rank(r['rs_h1'] if r else None)))
    return clock,securities,sectors,next_day


def build_report(data, account, events, *, initial_active=True):
    """Replay each close since real-account inception; deterministic and idempotent."""
    if type(initial_active) is not bool:
        raise ValueError('账户初始参与状态必须明确为布尔值')
    events=effective_events(events)
    days = [str(d.date()) for d in data.recovery.index if account['started_on'] <= str(d.date()) <= data.as_of]
    if not days: return None
    risk=dict(on=initial_active,peak=account['initial_cash'],episode=0); previous=(); exits=set(); reports=[]; prior_positions=set()
    for day in days:
        ledger=journal(account,events,day); positions=ledger['positions']; market_value=D(0); holdings=[]; missing=[]
        for sid,p in positions.items():
            row=data.row(sid,day)
            if not row or row['raw_close'] is None: missing.append(sid); continue
            value=D(str(row['raw_close']))*p['shares']; market_value+=value
            holdings.append(dict(**row,**p,market_value=str(value),unrealized=str(value-D(p['cost'])),sellable_shares=sum(l['shares'] for l in p['lots'] if l['day']<day)))
        nav=D(ledger['cash'])+D(ledger['receivable'])+market_value
        if missing:
            raise ValueError('持仓缺少有效估值：'+','.join(missing))
        m=data.recovery.loc[day]
        risk,dd,risk_event=advance_risk(risk,nav,not positions,bool(m.breakout))
        clock,stocks,sectors,next_day=packet(data,day)
        occupied=tuple(A.Occupancy(s,s,data.meta[s]['sector_id'],clock.decision_at,has_position=True,exit_latched=s in exits) for s in positions)
        completed=[]
        for sid in prior_positions-set(positions):
            sells=[e for e in events if e['kind']=='sell' and e['payload']['symbol']==sid and e['at'][:10]<=day]
            if sells:
                e=sells[-1];completed.append(A.ExitCompletion(sid,e['id'],datetime.fromisoformat(e['at'])))
        if not risk['on']:
            stocks=[replace(s,trend_up=A.Fact(False,clock.decision_at,clock.decision_at),buy_allowed=A.Fact(False,clock.decision_at,clock.decision_at)) for s in stocks]
        decision=A.decide(clock=clock,variant='S0',securities=stocks,sectors=sectors,previous=previous,occupied=occupied,bootstrap=not reports,completed_exits=completed)
        previous=decision.memories
        exits=(exits|set(decision.exit_requests))&set(positions)
        budget_cash=D(ledger['cash']); inventory=market_value; instructions=[]
        inactive_reason='账户尚未启用（INACTIVE），退出持仓' if not initial_active and risk['episode']==0 else '账户阶段回撤达到20%，暂停退出'
        for h in holdings:
            action='SELL' if h['symbol'] in exits else 'HOLD'
            qty=sum(l['shares'] for l in h['lots'] if next_day and lot_sellable(l,next_day)) if action=='SELL' else h['shares']
            instructions.append(dict(symbol=h['symbol'],name=h['name'],action=action,shares=qty,total_shares=h['shares'],blocked_shares=h['shares']-qty if action=='SELL' else 0,reason=inactive_reason if action=='SELL' and not risk['on'] else '结构退出已锁定，等待实际卖出' if action=='SELL' else '趋势资料尚未准备，持仓待核对' if not h['ready'] else '原I结构存续，继续持有' if h['fresh'] else '沿用最近结构，今日暂无新价格观察',support=h['floor_raw'],reference_price=h['raw_close']))
        rejected=[dict(symbol=s,reason=r) for s,r in decision.rejected]
        pending=list(decision.selected);planned=list(occupied);blocked=set();accepted=set()
        for _ in range(len(stocks)+1):
            if not pending: break
            for sid in pending:
                if not next_day:
                    blocked.add(sid);rejected.append(dict(symbol=sid,reason='下一交易日历未核验'));continue
                r=data.row(sid,day);budget=max(D(0),min(nav*D('.15'),nav*D('.90')-inventory,budget_cash))
                px=D(str(r['raw_close']));qty,budget,fee=data.rulebook.reserve(sid,day,px,budget,budget_cash)
                if not qty or r['floor_raw'] is None or r['raw_close']<=r['floor_raw']:
                    blocked.add(sid);rejected.append(dict(symbol=sid,reason='现金/最小数量/保护位不满足'));continue
                budget_cash-=budget+fee;inventory+=budget;accepted.add(sid)
                planned.append(A.Occupancy(sid,sid,data.meta[sid]['sector_id'],clock.decision_at,pending_buy=True))
                instructions.append(dict(symbol=sid,name=r['name'],action='BUY',shares=qty,max_gross=str(budget),reference_price=r['raw_close'],estimated_fee=str(fee),support=r['floor_raw'],reason='原I新事实事件＋行业上行＋RS-H1排序及容量通过',execution_note='下一交易日开盘核对原价与保护位；开盘价不高于保护位则放弃。股数按实际开盘价和费用重算；未成交当日到期。'))
            temporary=tuple(replace(m,waiting=False) if m.security_id in blocked else m for m in decision.memories)
            again=A.decide(clock=clock,variant='S0',securities=stocks,sectors=sectors,previous=temporary,occupied=tuple(planned))
            pending=[s for s in again.selected if s not in blocked and s not in accepted]
        rejected=[x for x in rejected if x['symbol'] not in accepted]
        report=dict(strategy='ACT20_BREAK',day=day,execution_day=next_day,nav=str(nav),cash=ledger['cash'],market_value=str(market_value),realized=ledger['realized'],fees=ledger['fees'],risk=dict(risk,drawdown=str(dd),event=risk_event),market=clean(dict(price=m.market,prior_high63=m.prior_high63,breadth=m.breadth,breakout=bool(m.breakout),price_up=bool(data.recovery.market.diff().loc[day]>0))),holdings=holdings,instructions=instructions,rejected=rejected,eligible=sum(e.q is True for e in decision.eligibility),snapshot_id=data.identity,positions_are_actual=True)
        if not initial_active:
            report['initial_participation']='INACTIVE'
        reports.append(report);prior_positions=set(positions)
    latest=reports[-1];latest['history']=[dict(day=r['day'],nav=r['nav'],drawdown=r['risk']['drawdown'],on=r['risk']['on'],event=r['risk']['event']) for r in reports]
    return clean(latest)
