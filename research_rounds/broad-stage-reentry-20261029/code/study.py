"""One new BSR-1 path and two unchanged BP-1 complete controls."""
from pathlib import Path
import sys, json, collections, importlib.util
from decimal import Decimal as D
from datetime import datetime
from dataclasses import replace, asdict
import pandas as pd
import numpy as np
ROOT = Path(__file__).resolve().parents[3]
O = Path(__file__).resolve().parents[1]
BASE = ROOT/'research_rounds/probe-pyramid-pilot-20261029'
sys.path.insert(0, str(ROOT/'research_rounds/lot-risk-allocation-20261029/code'))
_spec=importlib.util.spec_from_file_location('bsr_lr_allocator',ROOT/'research_rounds/lot-risk-allocation-20261029/code/study.py')
LR=importlib.util.module_from_spec(_spec);sys.modules[_spec.name]=LR;_spec.loader.exec_module(LR)
BP = LR.BP
C,E,R,L,A,N = BP.C,BP.E,BP.R,BP.L,BP.A,BP.N
ZERO,ONE,INITIAL = BP.ZERO,BP.ONE,BP.INITIAL
SNAP,CP,PV = BP.SNAP,BP.CP,BP.PV
save,sha = BP.save,BP.sha
from policy import support_cache, advance
FINE = ROOT/'research_rounds/intent-support-20261027/signals'

class Account(LR.Account):
    def __init__(self, name, market, facts):
        super().__init__(name, market, facts)
        self.last_flat_exit = {}
        self.episodes = collections.Counter()
    def fill_buy(self, sid, w):
        before = len(self.layers)
        receipt = super().fill_buy(sid,w)
        if receipt:
            assert len(self.layers)==before+1
            z = self.layers[-1]
            if z['kind']=='trial': self.episodes[sid]+=1
            z.update(origin=z['kind'], phase='TRIAL' if z['kind']=='trial' else 'MOBILE',
                     episode=self.episodes[sid], prior_flat_exit=self.last_flat_exit.get(sid),
                     entry_cost=(receipt.gross_cny+receipt.fees_cny)/D(receipt.shares)*self.facts.factor(sid,w.at),
                     bridge_floor=None, promoted_at=None)
        return receipt
    def fill_exit(self, sid, w):
        receipt = super().fill_exit(sid,w)
        if receipt and not self.quantity(sid): self.last_flat_exit[sid]=w.at
        return receipt

def preview(i, op, factor, rule, schedule):
    """Known-open estimate, bounded by last close's gross and share contract."""
    p = op*(ONE+LR.SLIP)
    if op*factor<=i['floor']: return None,'open_at_or_below_protection'
    maxq=LR.maximum_quantity(rule,min(i['cap'],int(i['budget']/p)),lambda q:D(q)*p<=i['budget'])
    if not maxq:return None,'open_minimum_exceeds_frozen_contract'
    cache={}
    def cost(q):
        if q not in cache:cache[q]=D(q)*p+LR.fees(q,p,schedule,'buy',i['quote'].par_value)
        return cache[q]
    return dict(sid=i['sid'],i=i,price=p,rule=rule,schedule=schedule,maxq=maxq,
                minq=rule.buy_minimum,cost=cost,weight=D(str(i['weight'])),qty=0),None

class Pilot(BP.Pilot):
    def __init__(self, cut=None, only=None):
        super().__init__(cut,['P0','P1'])
        wanted=only or ['P0','P1','N1']
        self.accounts={k:self.accounts[k] if k!='N1' else Account(k,self.market,self.facts) for k in wanted}
        self.fine={sid:pd.read_parquet(FINE/f'{sid}.parquet').loc[:cut] for sid in self.market.lines}
        self.support={sid:support_cache(self.facts.f[sid],self.fine[sid],self.cp[sid]) for sid in self.market.lines}
    def planning(self, at):
        a=self.accounts.pop('N1',None)
        super().planning(at)
        if a is None:return
        self.accounts['N1']=a
        clock,stocks,sectors=self.facts.packet(at,'I')
        sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors}
        buyable=self.market.market_buyable(at);day=pd.Timestamp(at.date())
        a.expire_day_buys(at)
        a.current_nav=a.balance(at,self.market.marks(at,a.positions))['nav']
        E.risk_policy.step(a,at,'ACT20_BREAK');a.pending=[]
        for sid in tuple(a.positions):
            r=self.facts.row(sid,at);quote=self.market.quote(sid,at);layers=a.live(sid)
            assert quote is not None
            if not a.risk_state['on'] or not bool(r.i_target):
                a.sell(sid,clock,quote,[x['id'] for x in layers],
                       'ACT_pause' if not a.risk_state['on'] else 'I_structure_exit');continue
            e_floor=self.facts.floor(sid,at,'I')
            fine=self.fine[sid].loc[day] if day in self.fine[sid].index else None
            cp=self.cp[sid].loc[day] if day in self.cp[sid].index else None
            for x in layers:
                if x['id'] in a.sell_layers.get(sid,set()):continue
                before=x['floor'];old_kind=x['kind'];event=advance(x,at,D(str(r.close)),e_floor,fine,cp)
                if event=='exit':
                    ids=[z['id'] for z in layers] if old_kind=='core' else [x['id']]
                    a.sell(sid,clock,quote,ids,old_kind+'_local_protection')
                    if old_kind=='core':break
                elif event:
                    a.log('stage_'+event,at,sid=sid,layer=x['id'],old_floor=before,
                          floor=x['floor'],phase=x['phase'],entry_cost=x['entry_cost'],
                          origin=x['origin'],sources=x.get('promotion_sources'))
                    a.counts['stage_'+event]+=1
        if a.risk_state['on']:
            for sid,s in sd.items():
                if sid in a.exits or sid in a.buys:continue
                r=self.facts.row(sid,at);e_floor=self.facts.floor(sid,at,'I')
                if e_floor is None:continue
                event=A.eligibility(s,ss,clock,'S0').q is True
                continuing=A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0').q is True
                cp=self.cp[sid].loc[day] if day in self.cp[sid].index else None
                fine=self.fine[sid].loc[day] if day in self.fine[sid].index else None
                pvs=self.pv[sid];p=float(pvs.loc[day]) if day in pvs.index and np.isfinite(pvs.loc[day]) else None
                warm=bool(continuing and r.g_ready and r.g_grade>=2 and p is not None and p>50)
                epoch=self.global_watch.get(sid)
                confirmed=bool(epoch is not None and warm and cp is not None and bool(cp.receipt))
                held=bool(a.quantity(sid));last_exit=a.last_flat_exit.get(sid)
                fine_reentry=bool(not held and last_exit is not None and epoch is not None and warm
                                  and fine is not None and fine.event==1
                                  and pd.Timestamp(fine.pivot_date).date()>=last_exit.date())
                if held:
                    if not any(x['kind']=='core' for x in a.live(sid)):continue
                    if not confirmed or D(str(r.close))<=a.last_buy[sid]:continue
                    kind='mobile';reason='CP1_mobile'
                else:
                    if not (event or confirmed or fine_reentry):continue
                    assert last_exit is None or at>last_exit
                    kind='trial';reason='reentry_' if last_exit is not None else 'first_'
                    reason+='CP1' if confirmed else 'F' if fine_reentry else 'I'
                quote=self.market.quote(sid,at)
                if quote is None:continue
                factor=self.facts.factor(sid,at)
                budget=min(max(a.current_nav*D('.02'),D(quote.quantity.buy_minimum)*quote.raw_price*(ONE+LR.SLIP)),
                           max(ZERO,a.current_nav*D('.1')-a.quantity(sid)*quote.raw_price))
                cap=quote.quantity.buy_floor(int(budget/(quote.raw_price*(ONE+LR.SLIP))))
                if not cap:a.counts['minimum_exceeds_single_name_cap']+=1;continue
                valid=self.support[sid].loc[day]
                floor=max([e_floor]+[D(str(v)) for v in [valid.f_valid,valid.cp_valid] if np.isfinite(v)])
                confirm=confirmed or fine_reentry
                a.pending.append(dict(sid=sid,clock=clock,quote=quote,budget=budget,cap=cap,
                    weight=p-50 if confirm else 1.,group=0 if confirm else 1,score=p,kind=kind,
                    floor=floor,epoch=epoch,reason=reason,prior_flat_exit=last_exit))
                a.counts['intent_'+kind]+=1
        a.decisions.append(dict(at=at,nav=a.current_nav,on=a.risk_state['on'],
            intents=[{k:v for k,v in i.items() if k not in ('clock','quote')} for i in a.pending],
            global_watches=len(self.global_watch)))
        bal=a.balance(at,self.market.marks(at,a.positions));a.check()
        self.daily.append(dict(account='N1',at=at,**bal,on=a.risk_state['on'],
            positions={s:p.shares for s,p in a.positions.items()},
            layers=[{k:x[k] for k in ['id','sid','kind','qty','floor','phase','origin','episode','bridge_floor']}
                    for x in a.layers if x['qty']],pending_sells=tuple(a.exits),
            pending_intents=len(a.pending),counts=dict(a.counts)))
    def opening(self,a,at):
        if not isinstance(a,Account):return super().opening(a,at)
        for sid in sorted(a.exits):
            w=self.market.window(sid,at,'sell',ONE)
            if w:a.fill_exit(sid,w)
        a.settle_due(at);cash=max(ZERO,a.available-a.current_nav*D('.1'))
        items=[i for i in a.pending if i['clock'].earliest_execution_at==at];previews=[]
        day=pd.Timestamp(at.date())
        for i in items:
            sid=i['sid'];raw=self.market.raw[sid]
            if day not in raw.index or not np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:
                a.counts['allocation_missing_open']+=1;continue
            x,reason=preview(i,D(str(raw.loc[day].open)),self.facts.factor(sid,at),
                             self.market.quantity(sid,at),self.market.fees(sid,at))
            if reason:a.counts['allocation_'+reason]+=1;continue
            previews.append(x)
        for group in (0,1):
            part=[x for x in previews if x['i']['group']==group]
            qty,details=LR.whole_orders(part,cash)
            for x in part:
                if qty[x['sid']]:cash-=x['cost'](qty[x['sid']])
            for r in details:a.log('lot_allocation',at,**r)
            assert cash>=0
        for x in sorted(previews,key=lambda x:(x['i']['group'],x['sid'])):
            if not x['qty']:a.counts['whole_order_unfunded']+=1;continue
            i=x['i'];sid=x['sid']
            a.reserve_quantity(i,x['qty'],x['price'],x['schedule'],at)
            w=self.market.window(sid,at,'buy',ONE)
            if w:
                assert w.execution_price==x['price'];a.fill_buy(sid,w)
            else:a.counts['no_open_window']+=1
        a.settle_due(at);a.minimum_available=min(a.minimum_available,a.available);a.check()
    def write(self,out):
        super().write(out)
        save(out/'stage-meta.json',dict(candidate='BSR-1',new_economic_paths=1,
             note='P0/P1 are complete unchanged controls. New trial/seed/mobile roles are account policy, not new market indicators.'))

def freeze():
    files=[O/'RULES.txt',O/'SCOPE.txt',O/'RAW_REVIEW.txt']+list((O/'code').glob('*.py'))
    inherited=json.loads((BASE/'FREEZE.json').read_text())['sha256']
    files += [ROOT/k for k in inherited]
    files += [ROOT/'research_rounds/lot-risk-allocation-20261029/code/study.py']
    files += list(FINE.glob('*.parquet'))+list((O/'charts').glob('raw-*.png'))
    save(O/'FREEZE.json',dict(recorded_at=datetime.now().astimezone().isoformat(),
        before_new_results=True,new_economic_paths=1,controls=['P0','P1'],parameter_search=False,
        sha256={str(p.relative_to(ROOT)):sha(p) for p in files}))
if __name__=='__main__':
    if sys.argv[1]=='freeze':freeze()
    elif sys.argv[1] in ('economic','prefix'):
        active=O/'FREEZE-v2.json' if (O/'FREEZE-v2.json').exists() else O/'FREEZE.json'
        assert all(sha(ROOT/k)==v for k,v in json.loads(active.read_text())['sha256'].items())
        prefix=sys.argv[1]=='prefix'
        run=Pilot('2025-12-31',['N1']) if prefix else Pilot()
        try:run.run('2025-12-31' if prefix else '2026-10-27').write(O/('technical-prefix' if prefix else 'results'))
        except BaseException as err:
            dest=O/('failed-'+datetime.now().strftime('%H%M%S'));run.write(dest)
            save(dest/'FAILURE.json',dict(error=repr(err)));raise
    else:raise ValueError(sys.argv[1])
