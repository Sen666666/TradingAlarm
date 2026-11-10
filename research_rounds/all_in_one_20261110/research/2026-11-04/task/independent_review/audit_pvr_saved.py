"""Independent saved-PVR arithmetic; imports no account, strategy or runner.

Reads the original pair schema. Marks use only frozen raw_close as of each
saved day; audit labels never feed the strategy. No economic execution.
"""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import defaultdict, Counter
from datetime import datetime
import argparse, bisect, gzip, hashlib, json
import pandas as pd

getcontext().prec=60
HERE=Path(__file__).resolve().parent;TASK=HERE.parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0);INITIAL=D(1000000);EPS=D('0.00000001');SOURCES={};FRAMES={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
    p=Path(p);SOURCES[str(p.resolve())]=sha(p);b=p.read_bytes()
    return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def rows(p):
    p=Path(p);SOURCES[str(p.resolve())]=sha(p)
    return [json.loads(s) for s in gzip.decompress(p.read_bytes()).decode().splitlines()]
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def at(x):return datetime.fromisoformat(str(x))
def exact(x,y,where):assert abs(x-y)<EPS,(where,str(x),str(y))
def audit_at(x):
    if 'at' in x:return at(x['at'])
    if x['kind']=='dividend_accrual':return at(x['receivable']['ex_at'])
    if x['kind']=='fill':return at(x['receipt']['at'])
    raise AssertionError(('unsupported audit clock',x['kind']))
SM={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
META=read('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
def price(sid,d):
    if sid not in FRAMES:
        p=Path(SM[sid]['refs']['facts']);h=sha(p)
        assert h==SM[sid]['output_sha256'][str(p)]
        SOURCES[str(p)]=h;f=pd.read_parquet(p,columns=['raw_close'])
        assert f.index.is_unique and f.index.is_monotonic_increasing
        FRAMES[sid]=(list(f.index.strftime('%Y-%m-%d')),list(f.raw_close))
    days,values=FRAMES[sid];i=bisect.bisect_right(days,d)-1
    assert i>=0 and days[i]<=d
    v=n(values[i]);assert v.is_finite() and v>0
    return v
def drawdown(ds):
    peak=INITIAL;worst=Z;peakday='initial';worstday=None;maxwater=0;under=None
    for r in ds:
        d=day(r['at']);v=n(r['nav'])
        if v>=peak:peak=v;peakday=d;under=None
        elif under is None:under=d
        if under:maxwater=max(maxwater,(datetime.fromisoformat(d)-datetime.fromisoformat(under)).days)
        dd=1-v/peak
        if dd>worst:worst=dd;worstday=d;preceding_peak=peakday
    return dict(close_DD=worst,day=worstday,preceding_peak=locals().get('preceding_peak'),observed_underwater_calendar_days=maxwater)

def audit(root,window):
    root=Path(root);done=read(root/'DONE.json');assert done['completed']
    p=root/'pair';b=read(p/'B.json.gz');ds=rows(p/'daily.jsonl.gz');balances=rows(p/'balances.jsonl.gz')
    end='2022-12-30' if window=='2022' else '2026-06-30';start='2022-01-04' if window=='2022' else '2025-07-01'
    assert len(ds)==len(balances)==242 and day(ds[0]['at'])==start and day(ds[-1]['at'])==end
    assert len({r['at'] for r in ds})==242;cut=at(end+'T15:10:00+08:00')
    assert all(at(t['at'])<=cut for t in b['trades'])
    assert all(audit_at(x)<=cut for x in b['audit'])
    assert all(at(x['at'])<=cut for x in b['journal'])
    ts=b['trades'];assert len({t['receipt_id'] for t in ts})==len(ts)
    divs=[x['receivable'] for x in b['audit'] if x['kind']=='dividend_accrual']
    assert len({x['event_id'] for x in divs})==len(divs)
    assert all(x['paid_at'] is None for x in divs),'paid claims need a distinct allocation bridge'
    splits=[x for x in b['audit'] if x['kind']=='split']
    events=[(at(t['at']),1,i,'trade',t)for i,t in enumerate(ts)]
    events +=[(at(x['at']),0,i,'split',x)for i,x in enumerate(splits)]
    events.sort(key=lambda x:x[:3]);q=defaultdict(int);fee=Z;cash=Z;k=0;daily_values={};fractions=[]
    for d,ba in zip(ds,balances):
        assert ba['at']==d['at']
        while k<len(events) and events[k][0]<=at(d['at']):
            _,_,_,kind,t=events[k];k+=1
            if kind=='split':
                qq=D(q[t['sid']])*n(t['ratio'])
                if qq!=int(qq):fractions.append(dict(at=t['at'],sid=t['sid'],pre=q[t['sid']],exact=qq,post=int(qq)))
                q[t['sid']]=int(qq)
            else:
                q[t['security_id']]+=(1 if t['side']=='buy' else -1)*t['shares'];assert q[t['security_id']]>=0
                fee+=n(t['fees_cny']);cash+=(n(t['gross_cny']) if t['side']=='sell'else -n(t['gross_cny']))-n(t['fees_cny'])
        assert {s:v for s,v in q.items()if v}=={s:v for s,v in d['positions'].items()if v}
        exact(fee,n(d['fees_cny']),'daily cumulative fee')
        vals={s:D(v)*price(s,day(d['at']))for s,v in q.items()if v};daily_values[day(d['at'])]=vals
        inventory=sum(vals.values(),Z);exact(inventory,n(d['inventory']),'independent frozen marks')
        income=sum((n(x['net_local'])for x in divs if at(x['ex_at'])<=at(d['at'])),Z)
        exact(INITIAL+cash+income+inventory,n(d['nav']),'daily trade cash+div+mark NAV')
        exact(n(d['settlement_locked']),n(d['payable']),'native debit offset')
        exact(n(d['available'])+n(d['order_reserved'])+n(d['sale_receivable'])+n(d['dividend_receivable'])+inventory,n(d['nav']),'daily financial components')
        exact(income,n(d['dividend_receivable']),'unpaid-only dividend protocol')
        for name in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']:
            assert abs(n(ba[name]))<D('0.000001'),name
        assert all(abs(n(v))<D('0.000001')for v in ba['pool_occupancy_difference'].values())
    assert k==len(events)
    exact(n(b['ending_cash']),n(ds[-1]['available']),'final available')
    exact(n(b['ending_NAV']),n(ds[-1]['nav']),'final NAV')
    buycost=defaultdict(lambda:Z);layerbuy={};sold=defaultdict(lambda:Z)
    for t in ts:
        if t['side']=='buy':
            buycost[t['layer']]+=n(t['gross_cny'])+n(t['fees_cny']);layerbuy[t['layer']]=t
        else:
            assert sum(x['shares']for x in t['parts'])==t['shares']
            exact(sum((n(x['net_cash'])for x in t['parts']),Z),n(t['gross_cny'])-n(t['fees_cny']),'sell parts')
            for part in t['parts']:sold[part['layer']]+=n(part['net_cash'])
    wealth={};bylayer={};layers=[]
    for l in b['layers']:
        lid=l['id'];exact(n(l['cash']),sold[lid]-buycost[lid],'layer cash')
        v=D(l['qty'])*price(l['sid'],end)if l['qty']else Z
        c=n(l['cash'])+n(l['dividend'])+v
        r=dict(id=lid,sid=l['sid'],qty=l['qty'],buy_cost=buycost[lid],contribution=c,dividend=n(l['dividend']))
        layers.append(r);bylayer[lid]=r;wealth[l['sid']]=wealth.get(l['sid'],Z)+c
    exact(sum(wealth.values(),Z),n(b['ending_NAV'])-INITIAL,'all stock wealth')
    # Actual stock-flat boundaries, not market contexts. No per-layer cost
    # allocation is required for full-campaign wealth and actual buy-cost.
    holdings=defaultdict(int);active={};cs=[];entrytypes={};seen=set()
    for stamp,_,_,kind,t in events:
        sid=t.get('security_id',t.get('sid'))
        if kind=='split':
            qq=D(holdings[sid])*n(t['ratio']);holdings[sid]=int(qq)
            if sid in active and qq!=int(qq):cs[active[sid]]['fractional_split']=True
            if sid in active and not holdings[sid]:cs[active.pop(sid)]['closed']=t['at']
            continue
        if t['side']=='buy':
            if not holdings[sid]:
                active[sid]=len(cs);cs.append(dict(sid=sid,opened=t['at'],closed=None,layers=[],fractional_split=False))
                entrytypes[t['layer']]='reentry'if sid in seen else 'first_stock_entry';seen.add(sid)
            else:entrytypes[t['layer']]='add_while_holding'
            cs[active[sid]]['layers'].append(t['layer']);holdings[sid]+=t['shares']
        else:
            holdings[sid]-=t['shares'];assert holdings[sid]>=0
            if not holdings[sid]:cs[active.pop(sid)]['closed']=t['at']
    for c in cs:
        rr=[bylayer[l]for l in c['layers']]
        c.update(buy_cost=sum((r['buy_cost']for r in rr),Z),contribution=sum((r['contribution']for r in rr),Z),dividend=sum((r['dividend']for r in rr),Z),remaining=sum(r['qty']for r in rr))
        c['cash_closed']=not c['remaining'] and not c['dividend'] and not c['fractional_split']
        c['tail30']=c['cash_closed']and c['contribution']/c['buy_cost']>=D('.3')
    exact(sum((c['contribution']for c in cs),Z),sum(wealth.values(),Z),'campaign total')
    summary=dict(NAV=n(b['ending_NAV']),wealth_PNL=n(b['ending_NAV'])-INITIAL,fees=fee,**drawdown(ds),
        mean_exposure=sum((n(d['inventory'])/n(d['nav'])for d in ds),Z)/242,
        buy_fills=sum(t['side']=='buy'for t in ts),sell_fills=sum(t['side']=='sell'for t in ts),
        closed_layer_positive=sum((max(Z,l['contribution'])for l in layers if not l['qty']),Z),
        closed_layer_negative=sum((min(Z,l['contribution'])for l in layers if not l['qty']),Z),
        open_layer_contribution=sum((l['contribution']for l in layers if l['qty']),Z),
        campaigns=len(cs),cash_closed_campaigns=sum(c['cash_closed']for c in cs),active_campaigns=sum(bool(c['remaining'])for c in cs),
        cash_closed_tail30_count=sum(c['tail30']for c in cs),cash_closed_tail30_net=sum((c['contribution']for c in cs if c['tail30']),Z),
        cash_closed_ordinary_net=sum((c['contribution']for c in cs if c['cash_closed']and not c['tail30']),Z),
        flat_unpaid_claim_contribution=sum((c['contribution']for c in cs if not c['remaining']and c['dividend']),Z),
        entry_types=dict(Counter(entrytypes.values())),daily_bridges=242,independent_price_days=242,fractional_split_floor_events=fractions)
    if window=='2025_26':
        ids={s for s in wealth if META[s]['sector_id']=='URFI881121'};lo='2026-01-01';hi='2026-06-30';dd=[d for d in ds if lo<=day(d['at'])<=hi]
        vv=[sum((v for s,v in daily_values[day(d['at'])].items()if s in ids),Z)for d in dd]
        trades=[t for t in ts if t['security_id']in ids and lo<=day(t['at'])<=hi];buys=[t for t in trades if t['side']=='buy'];sells=[t for t in trades if t['side']=='sell']
        inherit=sum((v for s,v in daily_values['2025-12-31'].items()if s in ids),Z);final=vv[-1]
        cash=sum(((n(t['gross_cny'])if t['side']=='sell'else -n(t['gross_cny']))-n(t['fees_cny'])for t in trades),Z)
        div=sum((n(x['net_local'])for x in divs if x['security_id']in ids and lo<=day(x['ex_at'])<=hi),Z)
        journal={x['layer']:x for x in b['journal']if x['kind']=='real_buy_fill'}
        summary['semiconductor_H1']=dict(sector='URFI881121',actual_buy_cash=sum((n(t['gross_cny'])+n(t['fees_cny'])for t in buys),Z),buy_fills=len(buys),sell_fills=len(sells),unique_bought_stocks=len({t['security_id']for t in buys}),
            first_actual_buy=buys[0]if buys else None,mean_weight=sum((v/n(d['nav'])for d,v in zip(dd,vv)),Z)/len(dd),end_weight=final/n(dd[-1]['nav']),
            inherited_inventory=inherit,terminal_inventory=final,interval_contribution=cash+div+final-inherit,
            actual_buy_entry_types=dict(Counter(entrytypes[t['layer']]for t in buys)),
            actual_buy_roles_pools=dict(Counter(journal[t['layer']]['role']+'|'+journal[t['layer']]['pool']for t in buys)),
            trade_records=trades,interpretation='all sector actual fills, not CP1-stock-day eligible mother; roles/pools at actual fill; interval includes inherited Dec31 holdings')
    return summary,wealth,cs

def main():
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2025_26'],required=True);p.add_argument('--baseline-only',action='store_true');args=p.parse_args()
    roots={'PVR_SLOT1':W/'pvr-slot1-native-readiness-20261101/runs'/args.window}
    if not args.baseline_only:roots['PVR_NO_CONFIRMED60']=TASK/'pvr_pool_feasibility/runs'/args.window
    out={};allstocks={};campaigns={}
    for ref,root in roots.items():out[ref],allstocks[ref],campaigns[ref]=audit(root,args.window)
    if len(out)==2:
        out['delta_NAV']=out['PVR_NO_CONFIRMED60']['NAV']-out['PVR_SLOT1']['NAV']
        delta={s:allstocks['PVR_NO_CONFIRMED60'].get(s,Z)-allstocks['PVR_SLOT1'].get(s,Z)for s in set(allstocks['PVR_SLOT1'])|set(allstocks['PVR_NO_CONFIRMED60'])}
        exact(sum(delta.values(),Z),out['delta_NAV'],'stock delta')
        out['stock_differences']=sorted([dict(sid=s,delta=v)for s,v in delta.items()],key=lambda z:z['delta'],reverse=True)
    SOURCES[str(Path(__file__).resolve())]=sha(__file__)
    out['source_SHA256']=SOURCES;out['account_events']=0
    out['scope']='Independent arithmetic and frozen marks; saved price/execution/data survivorship limitations remain. Tail30 is retrospective per-arm membership, not a fixed-cohort causal decomposition; open layer contribution is not pure unrealized. Fractional split campaigns excluded from trading-tail labels, retained in total wealth.'
    name='PVR_'+args.window+('_BASELINE'if args.baseline_only else '')+'_INDEPENDENT_AUDIT'
    (HERE/(name+'.json')).write_text(json.dumps(out,indent=2,ensure_ascii=False,default=str)+'\n')
    (HERE/(name+'_CAMPAIGNS.json')).write_text(json.dumps(campaigns,indent=2,default=str)+'\n')
    print(json.dumps({k:{kk:vv for kk,vv in v.items()if kk!='semiconductor_H1'}if isinstance(v,dict)else v for k,v in out.items()if k not in ['source_SHA256','stock_differences']},indent=2,default=str))
if __name__=='__main__':main()
