"""Read-only period/sector attribution of saved PVR books; no account import/run."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import importlib.util, gzip, json, hashlib

HERE=Path(__file__).resolve().parent
OUT=HERE/'absolute_loss_2022_2023'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=W/'pvr-slot1-native-readiness-20261101'
P=W/'c1-drawdown-capacity-20261101/analyze_saved.py'
sp=importlib.util.spec_from_file_location('saved_price_absolute_loss',P)
A=importlib.util.module_from_spec(sp);sp.loader.exec_module(A)
Z=D(0);EPS=D('.000001');SRC={}

def n(x):return D(str(x))
def day(x):return str(x)[:10]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def rows(p):
    SRC[str(p)]=sha(p)
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def book(p):
    SRC[str(p)]=sha(p)
    with gzip.open(p,'rt') as f:return json.load(f)
def zero():return defaultdict(lambda:Z)
def close(x,y,scope):assert abs(x-y)<EPS,(scope,x,y,x-y)

def analyze(ref,root,expected_days):
    b=book(root/'pair/B.json.gz');ds=rows(root/'pair/daily.jsonl.gz');bs=rows(root/'pair/balances.jsonl.gz')
    assert len(ds)==len(bs)==expected_days
    assert json.loads((root/'DONE.json').read_text())['completed'];SRC[str(root/'DONE.json')]=sha(root/'DONE.json')
    cutoff=str(ds[-1]['at']);sidsector={};sectorname={}
    for x in b['layers']:
        sector=b['metadata'][str(x['id'])]['sector'];sid=x['sid']
        assert sid not in sidsector or sidsector[sid]==sector
        sidsector[sid]=sector
        assert A.META[sid]['sector_id']==sector,(sid,'current/native sector mismatch')
        sectorname[sector]=A.META[sid]['industry']
    ev=[]
    for ix,t in enumerate(b['trades']):
        assert str(t['at'])<=cutoff;ev.append((str(t['at']),1,ix,'trade',t))
    for ix,t in enumerate(b['audit']):
        if t['kind']=='split':ev.append((str(t['at']),0,ix,'split',t))
        elif t['kind']=='dividend_accrual':ev.append((str(t['receivable']['ex_at']),2,ix,'dividend',t['receivable']))
    ev.sort(key=lambda x:x[:3]);assert all(t[0]<=cutoff for t in ev)
    layers={};cash=zero();real=zero();div=zero();buy=zero();sell=zero();fees=zero();buycount=defaultdict(int);sellcount=defaultdict(int)
    fraction=[];ei=0;prev={};prev_nav=D(1000000);prev_on=True;daily=[];sector_daily=[]
    for r,cert in zip(ds,bs):
        at=str(r['at']);d=day(at)
        assert day(cert['at'])==d
        for k in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']:close(n(cert[k]),Z,(ref,d,k))
        for x in cert['pool_occupancy_difference'].values():close(n(x),Z,(ref,d,'pool'))
        while ei<len(ev) and ev[ei][0]<=at:
            _,_,_,kind,t=ev[ei];ei+=1
            if kind=='split':
                for lid,l in layers.items():
                    if l['sid']==t['sid'] and l['qty']:
                        exact=D(l['qty'])*n(t['ratio']);q=int(exact)
                        if exact!=q:fraction.append(dict(day=d,layer=lid,exact=exact,qty=q))
                        assert exact==q,'nonzero split fraction requires explicit writeoff accounting'
                        l['qty']=q
            elif kind=='dividend':div[sidsector[t['security_id']]]+=n(t['net_local'])
            else:
                sid=t['security_id'];s=sidsector[sid];fee=n(t['fees_cny']);gross=n(t['gross_cny']);fees[s]+=fee
                if t['side']=='buy':
                    lid=t['layer'];assert lid not in layers
                    layers[lid]=dict(sid=sid,qty=t['shares'],basis=gross+fee)
                    buy[s]+=gross+fee;cash[s]-=gross+fee;buycount[s]+=1
                else:
                    proceeds=Z;basis=Z
                    for part in t['parts']:
                        l=layers[part['layer']];q=part['shares'];assert 0<q<=l['qty'] and l['sid']==sid
                        allocated=l['basis']*D(q)/D(l['qty']);l['basis']-=allocated;l['qty']-=q
                        basis+=allocated;proceeds+=n(part['net_cash'])
                        if not l['qty']:close(l['basis'],Z,(ref,d,'closed_layer_basis'))
                    close(proceeds,gross-fee,(ref,d,'sale parts'))
                    cash[s]+=proceeds;real[s]+=proceeds-basis;sell[s]+=proceeds;sellcount[s]+=1
        q=defaultdict(int);value=zero();basis=zero()
        for lid,l in layers.items():
            if not l['qty']:continue
            sid=l['sid'];s=sidsector[sid];q[sid]+=l['qty'];value[s]+=D(l['qty'])*A.price(sid,d);basis[s]+=l['basis']
        assert dict(q)=={sid:int(qty) for sid,qty in r['positions'].items() if qty},(ref,d,'quantity')
        close(sum(value.values(),Z),n(r['inventory']),(ref,d,'raw inventory'))
        current={};deltas=[]
        for s in sidsector.values():
            if s in current:continue
            cur=dict(cash=cash[s],realized=real[s],dividend=div[s],inventory=value[s],basis=basis[s],unrealized=value[s]-basis[s],buy_cash=buy[s],sell_net=sell[s],fees=fees[s],buy_fills=buycount[s],sell_fills=sellcount[s])
            prior=prev.get(s,{k:Z for k in cur});netcash=cur['cash']-prior['cash'];ivchange=cur['inventory']-prior['inventory'];dvchange=cur['dividend']-prior['dividend'];wealth=netcash+ivchange+dvchange
            realchange=cur['realized']-prior['realized'];urchange=cur['unrealized']-prior['unrealized']
            close(realchange+urchange+dvchange,wealth,(ref,d,s,'strictreal+unreal+AR'))
            z=dict(reference=ref,day=d,sector=s,industry=sectorname[s],net_trade_cash=netcash,inventory_begin=prior['inventory'],inventory_end=cur['inventory'],inventory_change=ivchange,
                realized_trade_net=realchange,unrealized_change=urchange,recognized_dividend=dvchange,wealth_change=wealth,
                actual_buy_cash=cur['buy_cash']-prior['buy_cash'],actual_sell_net=cur['sell_net']-prior['sell_net'],actual_fees=cur['fees']-prior['fees'],
                buy_fills=int(cur['buy_fills']-prior['buy_fills']),sell_fills=int(cur['sell_fills']-prior['sell_fills']),held_cost_basis=cur['basis'],
                market_value=cur['inventory'],exposure_pct=cur['inventory']/n(r['nav'])*100,ACT_at_OPEN=prev_on,ACT_after_CLOSE=r['on'])
            current[s]=cur;deltas.append(z)
        total={k:sum((z[k] for z in deltas),Z) for k in ['net_trade_cash','inventory_begin','inventory_end','inventory_change','realized_trade_net','unrealized_change','recognized_dividend','wealth_change','actual_buy_cash','actual_sell_net','actual_fees','held_cost_basis','market_value']}
        close(total['wealth_change'],n(r['nav'])-prev_nav,(ref,d,'daily NAV wealth'))
        close(D(1000000)+sum(real.values(),Z)+sum(value.values(),Z)-sum(basis.values(),Z)+sum(div.values(),Z),n(r['nav']),(ref,d,'cumulative NAV bridge'))
        close(sum(div.values(),Z),n(r['dividend_receivable']),(ref,d,'unpaid dividend AR'))
        total.update(reference=ref,day=d,NAV_begin=prev_nav,NAV_end=n(r['nav']),exposure_pct=n(r['inventory'])/n(r['nav'])*100,
            nominal_risk=n(r['pool_probe'][1])+n(r['pool_confirmed'][1]),nominal_risk_pct=(n(r['pool_probe'][1])+n(r['pool_confirmed'][1]))/n(r['nav'])*100,
            available_cash=n(r['available']),ACT_at_OPEN=prev_on,ACT_after_CLOSE=r['on'],buy_fills=sum(z['buy_fills'] for z in deltas),sell_fills=sum(z['sell_fills'] for z in deltas))
        daily.append(total);sector_daily.extend(deltas);prev=current;prev_nav=n(r['nav']);prev_on=r['on']
    assert ei==len(ev)
    close(sum((n(t['cash']) for t in b['layers']),Z),sum(cash.values(),Z),(ref,'native cash final'))
    close(sum((n(t['dividend']) for t in b['layers']),Z),sum(div.values(),Z),(ref,'native dividend final'))
    close(prev_nav,n(b['ending_NAV']),(ref,'native final NAV'))
    return dict(reference=ref,daily=daily,sector_daily=sector_daily,fractional_splits=fraction,
        ACT_events=[x for x in b['audit'] if x['kind']=='risk_checkpoint' and x.get('event')],
        source_bounds=[day(ds[0]['at']),day(ds[-1]['at'])],verified_closes=expected_days)

def key(d,grain):
    if grain=='all':return 'all'
    if grain=='year':return d[:4]
    if grain=='month':return d[:7]
    return d[:4]+'Q'+str((int(d[5:7])-1)//3+1)

SUMKEYS=['net_trade_cash','inventory_change','realized_trade_net','unrealized_change','recognized_dividend','wealth_change','actual_buy_cash','actual_sell_net','actual_fees','buy_fills','sell_fills']
def period_summary(rr):
    rec={k:sum((r[k] for r in rr),Z) for k in SUMKEYS}
    nav0=rr[0]['NAV_begin'];nav1=rr[-1]['NAV_end'];count=len(rr)
    rec.update(begin_NAV=nav0,end_NAV=nav1,return_pct=(nav1/nav0-1)*100,closes=count,
        begin_day=rr[0]['day'],end_day=rr[-1]['day'],inventory_begin=rr[0]['inventory_begin'],inventory_end=rr[-1]['inventory_end'],
        mean_held_cost_basis=sum((r['held_cost_basis'] for r in rr),Z)/count,mean_market_value=sum((r['market_value'] for r in rr),Z)/count,
        mean_exposure_pct=sum((r['exposure_pct'] for r in rr),Z)/count,mean_nominal_risk=sum((r['nominal_risk'] for r in rr),Z)/count,
        mean_nominal_risk_pct=sum((r['nominal_risk_pct'] for r in rr),Z)/count,
        active_OPEN_closes=sum(r['ACT_at_OPEN'] for r in rr),paused_OPEN_closes=sum(not r['ACT_at_OPEN'] for r in rr),
        net_per_actual_cumulative_buy_cash=rec['wealth_change']/rec['actual_buy_cash'] if rec['actual_buy_cash'] else None,
        DD=A.dd([('own_period_begin',nav0)]+[(r['day'],r['NAV_end']) for r in rr]))
    close(rec['wealth_change'],nav1-nav0,'period wealth')
    return rec

def main():
    OUT.mkdir(exist_ok=False);summary={};periods=[];sectors=[];states=[]
    specs=[('NO60_2022_2023',HERE.parent/'pvr_pool_feasibility/continuation2023/run-2023',484),
        ('PVR_2022_2023',OLD/'continuation-2023-readiness/run-2023',484),
        ('NO60_STRONG',HERE.parent/'pvr_pool_feasibility/runs/2025_26',242),('PVR_STRONG',OLD/'runs/2025_26',242)]
    for ref,path,count in specs:
        a=analyze(ref,path,count);summary[ref]=dict(period_summary(a['daily']),source_bounds=a['source_bounds'],verified_closes=count,ACT_events=a['ACT_events'],fractional_splits=a['fractional_splits'])
        save(OUT/(ref+'_DAILY.json'),a['daily']);save(OUT/(ref+'_SECTOR_DAILY.json'),a['sector_daily'])
        for grain in ['all','year','quarter','month']:
            for p in sorted({key(r['day'],grain) for r in a['daily']}):
                dr=[r for r in a['daily'] if key(r['day'],grain)==p]
                periods.append(dict(reference=ref,grain=grain,period=p,**period_summary(dr)))
                sectorrows=[]
                for s in sorted({r['sector'] for r in a['sector_daily']}):
                    rr=[r for r in a['sector_daily'] if r['sector']==s and key(r['day'],grain)==p]
                    z={k:sum((r[k] for r in rr),Z) for k in SUMKEYS};num=len(rr)
                    z.update(reference=ref,grain=grain,period=p,sector=s,industry=rr[0]['industry'],closes=num,
                        inventory_begin=rr[0]['inventory_begin'],inventory_end=rr[-1]['inventory_end'],
                        mean_held_cost_basis=sum((r['held_cost_basis'] for r in rr),Z)/num,mean_market_value=sum((r['market_value'] for r in rr),Z)/num,
                        mean_exposure_pct=sum((r['exposure_pct'] for r in rr),Z)/num,
                        net_per_actual_cumulative_buy_cash=z['wealth_change']/z['actual_buy_cash'] if z['actual_buy_cash'] else None)
                    sectorrows.append(z);sectors.append(z)
                close(sum((z['wealth_change'] for z in sectorrows),Z),period_summary(dr)['wealth_change'],(ref,p,'all sectors wealth'))
        for on in [True,False]:
            rr=[r for r in a['daily'] if r['ACT_at_OPEN']==on]
            if rr:
                z={k:sum((r[k] for r in rr),Z) for k in SUMKEYS};z.update(reference=ref,ACT_at_OPEN=on,closes=len(rr),
                    mean_held_cost_basis=sum((r['held_cost_basis'] for r in rr),Z)/len(rr),mean_exposure_pct=sum((r['exposure_pct'] for r in rr),Z)/len(rr))
                states.append(z)
        print('SAVED_ABSOLUTE_LOSS',ref,'wealth',summary[ref]['wealth_change'],'closes',count,flush=True)
        save(OUT/'SUMMARY.json',summary);save(OUT/'PERIODS.json',periods);save(OUT/'SECTORS.json',sectors);save(OUT/'ACT_CLOCK_GROUPS.json',states)
    for sid in A.frames:
        p=Path(A.SM[sid]['refs']['facts']);actual=sha(p);assert actual==A.SM[sid]['output_sha256'][str(p)];SRC[str(p)]=actual
    for p in [P,Path(__file__),Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'),W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json']:SRC[str(p)]=sha(p)
    save(OUT/'SOURCE_MANIFEST.json',dict(sources=SRC,account_events=0,
        trade_cash='net executed trade consideration: sale gross-fee minus buy gross+fee; sale settlement receivable included, not spendable cash',
        wealth_bridge='net trade cash + end inventory - begin inventory + recognized dividend accrual; no dividend payment exists in these saved books',
        strict_bridge='actual sale proceeds minus proportionally consumed cost basis including original buy fees; split preserves basis; all observed fractional conversions zero; unrealized is raw mark minus remaining basis',
        denominator='actual cumulative buycash recycles capital, not unique initial capital; mean heldcost/marketvalue and nominal risk reported; net/buycash descriptive, not alpha/annual return or evidence that less investment fixes loss',
        ACT_clock='OPEN state is previous recorded CLOSE state, before same-day15:10 ACT decision; group mark changes are descriptive, not a causal intervention',
        limitations='current-survivor A-share1709 development universe/current industry; original daily execution proxy; no HK/OOS/live or1.2m capital validation'))
    print('ABSOLUTE_LOSS_COMPLETE',len(periods),'periods',len(sectors),'sector rows',flush=True)

if __name__=='__main__':main()
