"""Trading desk service. All writes concern a local journal, never broker orders."""
import json
import hashlib
import threading
import uuid
from datetime import datetime
from decimal import Decimal as D,InvalidOperation
from pathlib import Path
from .store import Store, journal, money, now, TZ,effective_events
from .data import MarketData, clean
from .strategy import build_report


class Desk:
    def __init__(self, runtime):
        self.runtime=Path(runtime);self.store=Store(self.runtime/'account.sqlite3');self.lock=threading.RLock();self._data=None;self.job=dict(state='idle');self.cache=None
        from .paper import Paper
        self.paper=Paper(self.runtime,lambda:self.data)

    @property
    def data(self):
        if self._data is None: self._data=MarketData(self.runtime)
        return self._data

    def overview(self):
        with self.lock:
            account=self.store.account();report=None;tasks=[]
            if account:
                initial=self.store.setting('initial_participation','ACTIVE')
                if initial not in ('ACTIVE','INACTIVE'):
                    raise ValueError('账户初始参与状态无效，请核对账本设置')
                account=dict(account,initial_participation=initial)
                tasks=self.pending_actions(account,self.store.events())
                identity=hashlib.sha256((self.store.fingerprint()+'|'+initial).encode()).hexdigest()
                key=(identity,self.data.identity)
                if not self.cache or self.cache[0]!=key:
                    report=build_report(self.data,account,self.store.events(),initial_active=initial=='ACTIVE') if not tasks else None;self.cache=(key,report)
                    if report:self.store.save_report(report['day'],key[0],report)
                report=self.cache[1]
                if report:
                    active=effective_events(self.store.events());instructions=[]
                    for guide in report['instructions']:
                        side=guide['action'].lower()
                        count=sum(e['payload']['shares'] for e in active if e['kind']==side and e['payload']['symbol']==guide['symbol'] and e['at'][:10]==report['execution_day']) if side in ('buy','sell') else 0
                        instructions.append(dict(guide,recorded_shares=count,remaining_shares=max(0,guide['shares']-count)))
                    report=dict(report,instructions=instructions)
            status=self.data.status()
            current_account=journal(account,self.store.events()) if account else None
            if current_account:
                holdings=[];inventory=D(0)
                for sid,pos in current_account['positions'].items():
                    row=self.data.row(sid,self.data.as_of)
                    value=D(str(row['raw_close']))*pos['shares']
                    inventory+=value
                    holdings.append(dict(**row,**pos,market_value=str(value),unrealized=str(value-D(pos['cost']))))
                current_account.update(holdings=holdings,market_value=str(inventory),nav_estimate=str(D(current_account['cash'])+D(current_account['receivable'])+inventory),mark_day=self.data.as_of)
            last=self.data.recovery.iloc[-1]
            market=clean(dict(price=last.market,prior_high63=last.prior_high63,breadth=last.breadth,breakout=bool(last.breakout),price_up=bool(self.data.recovery.market.diff().iloc[-1]>0)))
            return clean(dict(account=account,actual=current_account,report=report,market=market,corporate_tasks=tasks,market_status=status,job=self.job,stocks=self.data.stocks(),sectors=self.data.sectors,schedule=self.store.setting('schedule',{'enabled':True,'time':'15:30'}),actionable=bool(report and not tasks and status['current'] and report['day']==status['expected_close']),journal_count=len(self.store.events())))

    def pending_actions(self,account,events):
        import datetime as dt
        active=effective_events(events);done={e['payload'].get('action_key') for e in active if e['kind']=='corporate'};pending=[]
        for sid,actions in self.data.actions.items():
            for action in actions:
                day=action['effective_date'];key=sid+':'+day
                if not account['started_on']<=day<=self.data.as_of or key in done:continue
                prior=(dt.date.fromisoformat(day)-dt.timedelta(days=1)).isoformat()
                qty=journal(account,events,prior)['positions'].get(sid,{}).get('shares',0)
                if qty:pending.append(dict(symbol=sid,name=self.data.meta[sid]['name'],action_key=key,day=day,prior_shares=qty,source_text=action.get('raw_text',''),reason='请按券商实际权益记录确认股数、已收和待收现金，再生成指引'))
        return pending

    def initialize(self,payload):
        with self.lock:
            result=self.store.initialize(payload.get('cash'),datetime.now(TZ).date().isoformat(),initial_participation='INACTIVE');self.cache=None
            return result

    def record_trade(self,payload):
        with self.lock:
            account=self.store.account()
            if not account:raise ValueError('请先建立真实账户')
            symbol=payload.get('symbol');side=payload.get('side')
            if symbol not in self.data.meta or side not in ('buy','sell'):raise ValueError('股票或成交方向无效')
            shares=payload.get('shares')
            if type(shares) is not int or not 0<shares<=100000000:raise ValueError('成交数量必须是正整数股数')
            px=money(payload.get('price'));fee=money(payload.get('fee',0),zero=True)
            try:
                at=datetime.fromisoformat(payload['at'])
                if at.tzinfo is None:at=at.replace(tzinfo=TZ)
                at=at.astimezone(TZ)
            except (ValueError,TypeError,KeyError):raise ValueError('请输入有效成交时间') from None
            if at>datetime.now(TZ):raise ValueError('不能录入未来成交')
            if at.date().isoformat() not in self.data.calendar:raise ValueError('成交日期不在已核验交易日历内')
            event=dict(symbol=symbol,price=str(px),fee=str(fee),shares=shares,note=str(payload.get('note',''))[:500],guide_day=payload.get('guide_day'))
            target=payload.get('target_id');kind=side;record_at=at.isoformat()
            if target:
                reason=str(payload.get('correction_reason','')).strip()
                if not reason:raise ValueError('修正成交需要填写原因，原始记录将保留')
                event=dict(target_id=target,reason=reason[:500],replacement=dict(kind=side,at=at.isoformat(),payload=event));kind='amend'
            eid=self.store.record(payload.get('id'),record_at,kind,event,lambda es:journal(account,es));self.cache=None
            return dict(id=eid,actual=journal(account,self.store.events()))

    def record_corporate(self,payload):
        with self.lock:
            account=self.store.account()
            if not account:raise ValueError('请先建立真实账户')
            sid=payload.get('symbol');day=payload.get('day');delta=payload.get('shares_delta',0)
            if sid not in self.data.meta or type(delta) is not int:raise ValueError('股票或权益股数无效')
            datetime.strptime(day,'%Y-%m-%d')
            if not account['started_on']<=day<=now()[:10]:raise ValueError('权益日期不在账户已发生期间')
            values={}
            for key in ['cash_delta','receivable_delta']:
                try:x=D(str(payload.get(key,0)))
                except InvalidOperation:raise ValueError('权益现金金额无效') from None
                if not x.is_finite() or abs(x)>D('1e12'):raise ValueError('权益现金金额无效')
                values[key]=str(x)
            reason=str(payload.get('note','')).strip()
            if not reason:raise ValueError('请填写券商权益记录说明')
            sellable=payload.get('sellable_on') or day;datetime.strptime(sellable,'%Y-%m-%d')
            event=dict(symbol=sid,shares_delta=delta,sellable_on=sellable,action_key=payload.get('action_key'),note=reason[:500],**values)
            kind='corporate';record_at=day+'T08:00:00+08:00'
            if payload.get('target_id'):
                event=dict(target_id=payload['target_id'],reason=reason,replacement=dict(kind='corporate',at=record_at,payload=event));kind='amend'
            elif event['action_key']:
                active=effective_events(self.store.events())
                if any(e['kind']=='corporate' and e['payload'].get('action_key')==event['action_key'] and e['id']!=payload.get('id') for e in active):raise ValueError('该次权益已确认，请使用修正录入')
            eid=self.store.record(payload.get('id'),record_at,kind,event,lambda es:journal(account,es));self.cache=None
            return dict(id=eid)

    def size_open(self,payload):
        with self.lock:
            view=self.overview();report=view['report']
            if not view['actionable']:raise ValueError('请使用最近完整收盘且权益核对完成的指引')
            sid=payload.get('symbol');price=money(payload.get('open'))
            guide=next((g for g in report['instructions'] if g['symbol']==sid and g['action']=='BUY'),None)
            if not guide:raise ValueError('该股票没有当前开仓指引')
            if report['execution_day']!=now()[:10]:raise ValueError('这份买入指引只在指定的下一交易日有效')
            if price<=D(str(guide['support'])):return dict(allowed=False,reason='开盘原价不高于保护位，按规则放弃本次买入',shares=0)
            fills=[e for e in effective_events(self.store.events()) if e['kind']=='buy' and e['payload']['symbol']==sid and e['at'][:10]==report['execution_day']]
            filled=sum(e['payload']['shares'] for e in fills);gross=sum((D(e['payload']['price'])*e['payload']['shares'] for e in fills),D(0))
            if filled>=guide['shares']:return dict(allowed=False,reason='本次计划股数已完成，不再新增买入',shares=0)
            budget=max(D(0),D(guide['max_gross'])-gross);cash=D(view['actual']['cash']);remaining=max(0,guide['shares']-filled)
            execution_price=price*D('1.0005')
            qty,_,fee=self.data.rulebook.size(sid,report['day'],execution_price,budget,cash)
            qty=min(qty,remaining)
            if filled:
                qty=min(remaining,int(min(budget,cash)/execution_price))
                while qty and qty*execution_price+sum(self.data.rulebook.fees(sid,report['day']).incremental('buy',qty*execution_price,{}, {},1,shares=qty,par_value=D(1)).values(),D(0))>cash:qty-=1
            return dict(allowed=bool(qty),shares=qty,estimated_price=str(execution_price),remaining_gross_budget=str(budget),support=guide['support'],partial_order=bool(filled),reason='仅对应原委托未成交余量，勿另开重复委托' if filled else '以原股数上限、预算、现金及数量规则测算；费用为研究估算，实际以券商为准')

    def refresh(self):
        with self.lock:
            if self.job['state'] in ('queued','running'):return self.job
            self.job=dict(state='queued',started_at=now(),message='准备收盘资料更新')
            threading.Thread(target=self._refresh,daemon=True,name='desk-close-refresh').start()
            return self.job

    def _refresh(self):
        try:
            from .refresh import refresh_market
            self.job=dict(state='running',started_at=now(),message='正在增量获取同花顺日线与权益')
            result=refresh_market(self.runtime,progress=lambda message:self.job.update(message=message))
            with self.lock:
                self._data=None;self.cache=None;self.job=dict(state='complete',finished_at=now(),message='收盘资料与策略计算完成',result=result)
            self.overview()
            self.paper.request_sync()
        except Exception as exc:
            # Collector errors contain metadata only; never return session/handshake bytes.
            self.job=dict(state='failed',finished_at=now(),message='更新未完成，保留上一份资料',error=str(exc)[:400])

    def tick(self):
        """Called by the running local server. One bounded run per known session."""
        self.paper.tick()
        schedule=self.store.setting('schedule',{'enabled':True,'time':'15:30'})
        if not schedule['enabled']:return
        t=datetime.now(TZ);day=t.date().isoformat()
        if day not in self.data.calendar or t.strftime('%H:%M')<schedule['time']:return
        if self.store.setting('scheduled_day')==day:return
        self.store.set_setting('scheduled_day',day);self.refresh()
