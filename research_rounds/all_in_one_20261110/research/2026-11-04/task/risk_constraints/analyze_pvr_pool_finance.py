"""Thin saved-PVR finance wrapper around the existing audited account reader.

No strategy/runner import, no account construction, no economic execution.
The original account()/price()/contribution() implementations remain unchanged.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
from datetime import datetime
import importlib.util,json,gzip,hashlib,argparse

ROOT=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=ROOT/'pvr-slot1-native-readiness-20261101';Z=D(0);EPS=D('.00001')
MATH=ROOT/'migration-admission-singlepass-economics-20261101/analyze.py'
spec=importlib.util.spec_from_file_location('NO_CONF60_saved_audited_math',MATH)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M);A=M.A
SRC={str(MATH):hashlib.sha256(MATH.read_bytes()).hexdigest()}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def rows(p):
    p=Path(p);SRC[str(p)]=sha(p)
    with gzip.open(p,'rt') as f:return [json.loads(l) for l in f]
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def at(x):return datetime.fromisoformat(str(x))
def native_saved_audit(a,root,win):
    b=a['book'];daily=a['daily'];end='2022-12-30' if win=='2022' else '2026-06-30';cutoff=at(end+'T15:10:00+08:00')
    assert len(daily)==242 and day(daily[-1]['at'])==end
    checks=rows(root/'pair/balances.jsonl.gz');assert len(checks)==242
    for r in checks:
        for key in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']:
            assert abs(n(r[key]))<D('.000001'),(win,r['at'],key,r[key])
        assert all(abs(n(v))<D('.000001') for v in r['pool_occupancy_difference'].values())
    events=[]
    for i,t in enumerate(b['trades']):assert at(t['at'])<=cutoff;events.append((at(t['at']),1,i,'trade',t))
    for i,s in enumerate(b['audit']):
        timestamp=(s['at'] if 'at' in s else s['receipt']['at'] if s['kind']=='fill' else s['receivable']['ex_at'] if s['kind']=='dividend_accrual' else None)
        assert timestamp is not None,('unknown original audit clock schema',s['kind'])
        assert at(timestamp)<=cutoff,('future audit',s['kind'],timestamp)
        if s['kind']=='split':events.append((at(s['at']),0,i,'split',s))
    quantities=defaultdict(int);fee=Z;idx=0;events.sort(key=lambda e:e[:3])
    for d in daily:
        while idx<len(events) and events[idx][0]<=at(d['at']):
            _,_,_,kind,t=events[idx];idx+=1
            if kind=='split':quantities[t['sid']]=int(D(quantities[t['sid']])*n(t['ratio']))
            else:quantities[t['security_id']]+=(1 if t['side']=='buy' else -1)*t['shares'];fee+=n(t['fees_cny'])
        assert {s:q for s,q in quantities.items() if q}=={s:q for s,q in d['positions'].items() if q}
        assert fee==n(d['fees_cny'])
    return dict(daily_native_financial_bridges=242,independently_rebuilt_daily_quantities=242,daily_fee_prefix_checks=242,
        cutoff=cutoff.isoformat(),no_future_trade_or_audit=True,account_runs=0)

def money_split(a):
    """Reuse the old whole-pipeline interpretation's exact no-open-partial split.

    A new partial-open/fraction case remains explicit rather than being called
    pure unrealized. Detailed allocated basis is owned by loss_correction.
    """
    b=a['book'];end=day(a['daily'][-1]['at']);op=[z for z in b['layers'] if z['qty']]
    partial=[z['id'] for z in op if any(t['side']=='sell' and any(p['layer']==z['id'] for p in t['parts']) for t in b['trades'])]
    nontrade=[j for j in b['journal'] if 'fraction' in j['kind'] or 'writeoff' in j['kind']]
    closed_cash=sum((n(z['cash']) for z in b['layers'] if not z['qty']),Z)
    open_cash_mark=sum((n(z['cash'])+D(z['qty'])*A.price(z['sid'],end) for z in op),Z)
    div=sum((n(z['dividend']) for z in b['layers']),Z);ar=n(a['daily'][-1]['dividend_receivable'])
    assert abs(closed_cash+open_cash_mark+div-(n(b['ending_NAV'])-D(1000000)))<EPS
    exact_simple=not partial and not nontrade
    return dict(position_closed_layer_cash_net=closed_cash,open_layer_cash_plus_mark=open_cash_mark,
        recognized_dividend=div,unpaid_dividend_AR=ar,paid_dividend=div-ar,
        strict_actual_trade_realized_if_no_partial_or_writeoff=(closed_cash if exact_simple else None),
        pure_unrealized_if_no_partial_or_writeoff=(open_cash_mark if exact_simple else None),
        open_layers_with_partial_sales=partial,explicit_nontrade_journal=nontrade,
        strict_split_status=('old audited no-open-partial convention exact' if exact_simple else 'allocated basis required; do not call open cash+mark pure unrealized'),
        no_double_fee_deduction=True)

def themes(a,win):
    if win!='2025_26':return []
    lo='2026-01-01';hi='2026-06-30';before='2025-12-31';result=[]
    for sector,name in [('URFI881121','半导体'),('URFI881172','电子化学品'),('URFI881270','元件')]:
        ids={s for s,v in A.META.items() if v['sector_id']==sector};days=[d for d in a['byday'] if lo<=d<=hi]
        curve=[]
        for d in days:
            buys=[t for t in a['book']['trades'] if t['side']=='buy' and t['security_id'] in ids and day(t['at'])==d]
            sells=[t for t in a['book']['trades'] if t['side']=='sell' and t['security_id'] in ids and day(t['at'])==d]
            capital=sum((v for s,v in a['values'][d].items() if s in ids),Z)
            curve.append(dict(day=d,capital=capital,weight_pct=capital/n(a['byday'][d]['nav'])*100,
                actual_buy_gross=sum((n(t['gross_cny']) for t in buys),Z),actual_sell_gross=sum((n(t['gross_cny']) for t in sells),Z),
                held_stocks=sum(s in ids for s in a['values'][d])))
        buys=[t for t in a['book']['trades'] if t['side']=='buy' and t['security_id'] in ids and lo<=day(t['at'])<=hi]
        sells=[t for t in a['book']['trades'] if t['side']=='sell' and t['security_id'] in ids and lo<=day(t['at'])<=hi]
        inventory_before=sum((v for s,v in a['values'][before].items() if s in ids),Z);inventory_end=sum((v for s,v in a['values'][hi].items() if s in ids),Z)
        div=sum((n(z['receivable']['net_local']) for z in a['book']['audit'] if z['kind']=='dividend_accrual' and z['receivable']['security_id'] in ids and lo<=day(z['receivable']['ex_at'])<=hi),Z)
        bg=sum((n(t['gross_cny']) for t in buys),Z);sg=sum((n(t['gross_cny']) for t in sells),Z)
        fees=sum((n(t['fees_cny']) for t in buys+sells),Z)
        interval=inventory_end-inventory_before+sg-bg-fees+div
        result.append(dict(sector=sector,name=name,window=[lo,hi],daily=curve,
            mean_weight_pct=sum((z['weight_pct'] for z in curve),Z)/len(curve),peak=max(curve,key=lambda z:z['weight_pct']),
            end_weight_pct=curve[-1]['weight_pct'],actual_buy_cash=bg+sum((n(t['fees_cny']) for t in buys),Z),actual_buy_fills=len(buys),
            actual_sell_fills=len(sells),first_actual_buy=buys[0]['at'] if buys else None,interval_net_contribution=interval,
            inventory_before=inventory_before,inventory_end=inventory_end,actual_buy_gross=bg,actual_sell_gross=sg,fees=fees,
            recognized_interval_dividend=div,net_active_gross_funding=bg-sg,
            mark_rights_inventory_residual=inventory_end-inventory_before-bg+sg,
            residual_is_not_pure_passive_return=True))
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--window',choices=['2022','2025_26'],required=True)
    ap.add_argument('--new-root',type=Path);ap.add_argument('--baseline-only',action='store_true');ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=False);A.O=args.out;M.O=args.out
    oldroot=OLD/'runs'/args.window;binding=read(OLD/'analysis'/args.window/'COMPLETION.json')
    assert sha(oldroot/'pair/B.json.gz')==binding['PVR_SLOT1_book_sha256']
    roots={'PVR_SLOT1':oldroot}
    if not args.baseline_only:
        assert args.new_root and read(args.new_root/'DONE.json')['completed'];roots['PVR_NO_CONFIRMED60']=args.new_root
    data={};report={}
    for ref,root in roots.items():
        for name in ['B.json.gz','daily.jsonl.gz','balances.jsonl.gz']:SRC[str(root/'pair'/name)]=sha(root/'pair'/name)
        a=A.account(args.window,ref,root);data[ref]=a
        pool={p:dict(mean_capital_pct=sum((n(r['pool_'+p][0])/n(r['nav'])*100 for r in a['daily']),Z)/242,
            mean_risk_pct=sum((n(r['pool_'+p][1])/n(r['nav'])*100 for r in a['daily']),Z)/242,
            peak_capital_pct=max(n(r['pool_'+p][0])/n(r['nav'])*100 for r in a['daily'])) for p in ['probe','confirmed']}
        report[ref]=dict(metrics=a['metrics'],layer_contributions=M.contribution(a['layers']),money_split=money_split(a),pools=pool,
            total_mean_nominal_risk_pct=sum((n(r['pool_probe'][1])+n(r['pool_confirmed'][1]))/n(r['nav'])*100 for r in a['daily'])/242,
            verification=native_saved_audit(a,root,args.window))
        save(args.out/(ref+'_THEMES.json'),themes(a,args.window))
        save(args.out/(ref+'_DAILY.json'),a['daily'])
    if len(data)==2:
        old=data['PVR_SLOT1'];new=data['PVR_NO_CONFIRMED60'];delta=[]
        for sid in set(old['stock'])|set(new['stock']):delta.append(dict(sid=sid,name=A.META[sid]['name'],old=old['stock'].get(sid,Z),new=new['stock'].get(sid,Z),delta=new['stock'].get(sid,Z)-old['stock'].get(sid,Z)))
        delta.sort(key=lambda x:x['delta'],reverse=True);navdelta=n(new['book']['ending_NAV'])-n(old['book']['ending_NAV'])
        assert abs(sum((z['delta'] for z in delta),Z)-navdelta)<EPS
        save(args.out/'STOCK_WEALTH_DIFFERENCES.json',delta)
        report['delta_NAV']=navdelta
    for sid in A.frames:
        p=Path(A.SM[sid]['refs']['facts']);assert sha(p)==A.SM[sid]['output_sha256'][str(p)];SRC[str(p)]=sha(p)
    for p in [Path(A.__file__),Path(__file__)]:SRC[str(p)]=sha(p)
    save(args.out/'FINANCE_COMPARISON.json',report);save(args.out/'SOURCE_MANIFEST.json',dict(sources=SRC,zero_account_or_strategy_imports=True,new_financial_events=0,
        inherited_audited_account_math=str(Path(A.__file__)),inherited_money_split_convention=str(OLD/'whole-pipeline-interpretation/diagnose_saved.py'),
        no_use_of_old60_as_new_remaining_capacity=True,baseline_only=args.baseline_only))
    print('READONLY_PVR_FINANCE_READY',args.window,list(roots),report.get('delta_NAV'),flush=True)
if __name__=='__main__':main()
