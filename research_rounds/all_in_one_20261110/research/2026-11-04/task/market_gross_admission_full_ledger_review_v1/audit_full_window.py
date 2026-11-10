"""One read-only native monetary audit of the three authorized small cases.
Uses only the prior audited saved-native reader, raw prices and actual audit/trades.
No strategy/account/provider/fee engine import or account replay.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import importlib.util, json, bisect, argparse, gzip
O=Path(__file__).resolve().parent
S=O.parent/'independent_review/trend_confirmation_full_ledger_v1/generic_saved_finance_reader.py'
spec=importlib.util.spec_from_file_location('audited_pure_saved_finance',S)
R=importlib.util.module_from_spec(spec);spec.loader.exec_module(R)
Z=D(0);SLIP=D('.0005');ALPHA=D('.10');EPS=D('.000001')
parser=argparse.ArgumentParser();parser.add_argument('--window',choices=['long','strong'],required=True);args=parser.parse_args()
CASES=[(args.window,'full-'+args.window+'-v1',726 if args.window=='long' else 242,None)]


def pending_qty(book,cut):
    p={}
    for e in book['audit'][:cut]:
        if e['kind']=='reserve':p[e['order_id']]=int(e['target_shares'])
        elif e['kind']=='release_buy':p.pop(e['order_id'])
        elif e['kind']=='fill'and e['receipt']['side']=='buy':p[e['order_id']]=int(e['share_cap_remaining'])
        elif e['kind']in ('split','split_fraction_floor_proxy'):
            assert not p,'No small actual pending-CA event was pre-authorized as an accounting rewrite'
    return p

def monetary(book,layers,cut,at):
    p=R.prefix(book,cut);quant=defaultdict(int)
    for lid,q in p['q'].items():quant[layers[lid]['sid']]+=q
    inv=sum((D(q)*R.mark(sid,at)for sid,q in quant.items()if q),Z)
    gross=sum((x['gross']for x in p['pending'].values()),Z)
    drag=sum((x['fee']+x['gross']*SLIP/(1+SLIP)for x in p['pending'].values()),Z)
    return p,dict(NAV=p['cash']+p['divincome']+inv,inventory=inv,pending_gross=gross,pending_drag=drag)

report={};examples=[]
for name,folder,closes,gold in CASES:
    out=O.parent/'market_gross_admission_native_v1'/folder
    start=R.read(out/'STARTED.json');done=R.read(out/'WINDOW_RESULT.json');assert done['passed']and done['days']==closes
    schema=start['full_schema'];assert schema['executed_arms']==['D_GROSS10']and done['executed_arms']==['D_GROSS10']
    assert R.read(out/'TIMING.json')['completed']
    ds=R.rows(out/'pair/daily.jsonl.gz');bs=R.rows(out/'pair/balances.jsonl.gz');assert len(ds)==closes and {r['account']for r in ds}=={'D_GROSS10'}
    books={};financial={}
    for arm in ('D_GROSS10',):
        book=R.book(out/'pair'/(arm+'.json.gz'));books[arm]=book;daily=[r for r in ds if r['account']==arm];assert len(daily)==closes
        layers={x['id']:x for x in book['layers']};times=[];last=R.ts(daily[0]['at'])-R.pd.Timedelta(days=10000)
        for e in book['audit']:
            at=e.get('at')or e.get('receipt',{}).get('at')or e.get('receivable',{}).get('ex_at');current=R.ts(at)if at else last
            assert current>=last;times.append(current);last=current
        for d in daily:
            cut=bisect.bisect_right(times,R.ts(d['at']));p,m=monetary(book,layers,cut,d['at']);quant=defaultdict(int)
            for lid,q in p['q'].items():quant[layers[lid]['sid']]+=q
            assert {sid:q for sid,q in quant.items()if q}==d['positions']
            for k in ('inventory','nav'):R.near(m['NAV'if k=='nav'else k],d[k],('daily',name,arm,k))
            R.near(p['cash']+p['divincome'],sum((D(d[k])for k in('available','order_reserved','sale_receivable','dividend_receivable')),Z),'cash+AR liquid bridge')
            R.near(p['fees'],d['fees_cny'],'cumulative actual fee')
        for b in bs:
            if b['account']==arm:
                for k in('independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference'):R.near(b[k],0,k)
        R.near(book['ending_NAV'],daily[-1]['nav'],'terminal wealth')
        peak=D(1000000);drawdown=Z
        for row in daily:
            nav=D(row['nav']);peak=max(peak,nav);drawdown=max(drawdown,1-nav/peak)
        financial[arm]=dict(return_pct=str((D(book['ending_NAV'])/D(1000000)-1)*100),MDD_close_pct=str(drawdown*100),daily_cash_qty_rawmark_fee_AR_bridges=closes,terminal_NAV=book['ending_NAV'],actual_trades=len(book['trades']),actual_fees_CNY=daily[-1]['fees_cny'])
    archive_binding=R.read(O.parent/'market_gross_admission_native_v1/ARCHIVED_B_CONTROL_BINDING.json')
    archived=archive_binding[name];assert archived==schema['archived_B_only_xref']==done['archived_control_xref']
    assert archived['days']==closes and archived['initial_cash']=='1000000'
    for path,h in archived['source_sha256'].items():assert R.sha(path)==h,('archived B file identity changed',path)
    archived_start=next(path for path in archived['source_sha256']if path.endswith('/STARTED.json'))
    oldsource=R.read(archived_start)['sources'];common=set(oldsource)&set(schema['sources'])
    assert all(oldsource[p]==schema['sources'][p]for p in common)
    cached=R.read(O.parent/'independent_review/trend_confirmation_full_ledger_v1/FULL_TWO_WINDOWS_FINANCE_PVR_CA_AUDIT.json')
    archived_metrics=cached['cases'][name]['arms']['B']
    golden=dict(status='REUSED_ARCHIVED_NO60_NO_B_RERUN_NO_FINANCIAL_RECOMPUTATION',file_SHA_exact=len(archived['source_sha256']),common_source_entries_exact=len(common),cached_previous_full_financial_metrics=archived_metrics)
    book=books['D_GROSS10'];layers={x['id']:x for x in book['layers']};event_path=out/'pair/gross-admission-events.jsonl.gz';R.SRC[str(event_path.resolve())]=R.sha(event_path);events=(json.loads(line)for line in gzip.open(event_path,'rt'));counts=Counter();last_pre=None;last_reserve_pre=None;fee_bound_scope=Counter()
    for index,e in enumerate(events):
        kind=e['kind'];cut=int(e['native_audit_count']);assert cut<=len(book['audit'])
        if kind=='route':
            if e['info']['state']=='DOWN'and D(e['inventory'])+D(e['pending_gross'])>ALPHA*(D(e['NAV'])-D(e['pending_drag']))+EPS:
                assert e['selected_q']==0;counts['legacy_passive_overcap_routes_allowed_to_hold_but_zero_new_q']+=1
            continue
        p,m=monetary(book,layers,cut,e['at'])
        for k,v in m.items():R.near(v,e[k],('actual native prefix',name,kind,k))
        qmap=pending_qty(book,cut);assert len(e['orders'])==len(p['pending'])
        for sid,o in e['orders'].items():
            native=p['pending'][o['order_id']];assert native['sid']==sid and qmap[o['order_id']]==o['qty']
            R.near(native['gross'],o['gross'],'true remaining principal');R.near(native['fee'],o['fee'],'true remaining fee')
            R.near(native['fee']+native['gross']*SLIP/(1+SLIP),o['drag'],'pending fee/slip once')
        assert e['native_trade_count']==sum(x['kind']=='fill'for x in book['audit'][:cut])
        state=e['info']['state'];assert R.ts(e['info']['available_at'])<=R.ts(e['at'])
        if R.ts(e['at']).hour<15:assert e['info']['day']<str(e['at'])[:10]
        counts[kind]+=1
        if kind=='reserve_pre':
            q=int(e['q']);price=D(e['execution_price']);mark=R.mark(e['sid'],e['at']);fee=D(e['fee']);R.near(mark,e['mark'],'actual original mark proposed sid')
            projected_gross=m['inventory']+m['pending_gross']+D(q)*price
            projected_nav=m['NAV']-m['pending_drag']-fee-D(q)*max(Z,price-mark)
            R.near(projected_gross,e['projected_gross'],'reserve principal not fee numerator');R.near(projected_nav,e['projected_NAV'],'reserve fee/slip NAV once')
            assert e['allowed']==(state!='UNKNOWN'and(state!='DOWN'or(projected_nav>0 and projected_gross<=ALPHA*projected_nav+EPS)))
            assert e['allowed']and q>0;last_reserve_pre=dict(e=e,cut=cut,m=dict(m),gross=projected_gross,nav=projected_nav)
            if state=='DOWN':counts['positive_DOWN_reserve']+=1
        elif kind=='reserve_post':
            pre=last_reserve_pre;assert pre is not None and pre['e']['sid']==e['sid']and pre['e']['q']==e['q']
            native=next(x for x in book['audit'][pre['cut']:cut]if x['kind']=='reserve'and x['order_id']==e['order_id'])
            R.near(native['fee_reserved_cny'],pre['e']['fee'],'reserved original native fee');R.near(native['gross_budget_cny'],D(e['q'])*D(pre['e']['execution_price']),'real reserve principal')
            R.near(m['NAV'],pre['m']['NAV'],'reservation transfers cash, not an expense');R.near(m['inventory']+m['pending_gross'],pre['gross'],'postreserve total principal')
            R.near(m['NAV']-m['pending_drag'],pre['nav'],'forecast new fee appears once')
        elif kind=='fill_pre':
            order=e['orders'][e['sid']];price=D(e['execution_price']);mark=R.mark(e['sid'],e['at']);R.near(mark,e['mark'],'fill actual raw mark')
            bound=min(order['qty'],int(D(order['gross'])/price));assert bound==e['q_bound']
            fullfee=D(e['fullfee_bound']);fee_bound_scope['native_pure_fullremaining_fee_bound_observations']+=1
            slip=max(D(order['gross'])*SLIP/(1+SLIP),D(bound)*max(Z,price-mark))
            nav=m['NAV']-(m['pending_drag']-D(order['drag']))-(max(D(order['fee']),fullfee)+slip)
            gross=m['inventory']+m['pending_gross'];R.near(nav,e['projected_NAV'],'replace only current fee/slip forecast');R.near(gross,e['projected_gross'],'current full remaining gross retained exactly once')
            assert e['allowed']==(state!='UNKNOWN'and(state!='DOWN'or(nav>0 and gross<=ALPHA*nav+EPS)))
            last_pre=dict(e=e,cut=cut,m=dict(m),cash=p['cash'],gross=gross,nav=nav,order_id=order['order_id'])
        elif kind=='fill_post':
            pre=last_pre;assert pre and pre['e']['sid']==e['sid']and pre['e']['allowed'];actual=book['trades'][int(e['native_trade_count'])-1]
            assert actual['side']=='buy'and actual['security_id']==e['sid']and actual['shares']==e['actual_shares']
            gross=D(actual['gross_cny']);fee=D(actual['fees_cny']);q=int(actual['shares']);mark=R.mark(e['sid'],e['at']);R.near(gross,e['actual_gross'],'actual receipt gross');R.near(fee,e['actual_fee'],'actual receipt fee')
            R.near(m['inventory']-pre['m']['inventory'],D(q)*mark,'actual shares transferred to inventory');R.near(p['cash']-pre['cash'],-gross-fee,'actual cash debit once')
            R.near(m['NAV'],pre['m']['NAV']-fee-(gross-D(q)*mark),'actual fee and slip NAV once')
            releases=sum((D(x['gross_released'])for x in book['audit'][pre['cut']:cut]if x['kind']=='release_buy'),Z)
            R.near(m['pending_gross'],pre['m']['pending_gross']-gross-releases,'executed principal removed; residual retained until ACK')
            if q==pre['e']['q_bound']:R.near(fee,pre['e']['fullfee_bound'],'actual full remaining fee independent receipt');fee_bound_scope['actual_full_remaining_receipt_bindings']+=1
            else:
                assert fee<=max(D(pre['e']['orders'][e['sid']]['fee']),D(pre['e']['fullfee_bound']))+EPS
                fee_bound_scope['actual_partial_receipt_conversion_bridges']+=1
            if state=='DOWN':counts['positive_DOWN_actual_fill']+=1
            if state=='DOWN'and len(examples)<4:examples.append(dict(case=name,at=e['at'],sid=e['sid'],inventory=str(m['inventory']),pending_gross=str(m['pending_gross']),native_NAV=str(m['NAV']),after_pending_fee_slip_NAV=str(m['NAV']-m['pending_drag']),actual_shares=q))
        elif kind=='fill_cancelled':
            assert last_pre and not last_pre['e']['allowed'];counts['original_native_cancel_ACK_path']+=1
        if state=='DOWN'and kind in('reserve_post','fill_post'):
            assert m['inventory']+m['pending_gross']<=ALPHA*(m['NAV']-m['pending_drag'])+EPS
    frozen=schema['sources'];assert all(R.sha(p)==h for p,h in frozen.items()),'case frozen source changed'
    report[name]=dict(finance=financial,baseline_gold=golden,actual_atomic_snapshot_counts=dict(counts),fee_bound_observed_scope=dict(fee_bound_scope),source_post_exact=len(frozen),unconditional_legacy_daily_cap_assertion_applied=False)
assert sum(v['finance'][a]['daily_cash_qty_rawmark_fee_AR_bridges']for v in report.values()for a in v['finance'])==closes
result=dict(status='PASS_FULL_D_ONLY_NATIVE_FINANCE_AND_ACTUAL_GROSS_ATOMIC_REVIEW',window=args.window,cases=report,unique_candidate_daily_bridges=closes,positive_DOWN_examples=examples,B_executed_or_synthesized=False,root_full_run_authorized=True,economic_promotion=False,limits=['Single actual D account; archived No60 B identities/shared sources and previously audited money metrics reused, never rerun/merged.','Same frozen initial1m and window; closing NAV DD, original daily-bar execution proxy.','No unconditional legacy daily gross10% invariant. Actual partial conversion coverage only if actual receipts report it.','Market info and private helper/calendar source equivalence are separately reviewed; PVR actual-use receipt is separate.'],source_sha256=R.SRC,reader_sha256=R.sha(S),checker_sha256=R.sha(__file__))
dest=O/args.window;dest.mkdir(parents=True,exist_ok=True);p=dest/'FINANCE_AND_ATOMIC_AUDIT.json';assert not p.exists();p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items()if k!='source_sha256'}));print('RECEIPT_SHA256',R.sha(p))
