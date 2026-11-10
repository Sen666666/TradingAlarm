"""Saved trend-size small audit, reusing unchanged independent finance reader.

No runner, native account, new feature engine or economic replay is imported.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict, Counter
import argparse, hashlib, importlib.util, json

O=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('frozen_independent_native_small_reader',O/'shared_finance_reader_with_ar_snapshot.py')
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
T=O.parents[1];Z=D(0)
def key(at,sid,role):return (M.ts(at),sid,role)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);ap.add_argument('--window',choices=['2022','strong'],required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    assert not a.out.exists();a.out.mkdir(parents=True)
    daily=M.rows(a.run/'pair/daily.jsonl.gz');balances=M.rows(a.run/'pair/balances.jsonl.gz')
    events=M.rows(a.run/'pair/confirmation-size-events.jsonl.gz');start=M.read(a.run/'STARTED.json')
    end=max((M.ts(r['at']) for r in daily));arms=sorted({r['account']for r in daily});assert arms==['A_ONLY','A_OR_B','B','UNIFORM50']
    assert start['cost_guard'] is False and start['ACT20_BREAK63_unchanged'] is True
    report={};counts=Counter();books={};plans={}
    for arm in arms:
        b=M.book(a.run/'pair'/f'{arm}.json.gz');books[arm]=b;dd=[d for d in daily if d['account']==arm]
        assert len(dd)==9
        assert not any(r['kind']=='split_fraction_floor_proxy'for r in b['audit']),'fractional equity cash requires a separate scope'
        assert all(r['receivable']['paid_at']is None for r in b['audit']if r['kind']=='dividend_accrual'),'This observed small-window scope keeps all dividends as unpaid AR'
        layers={x['id']:x for x in b['layers']}
        for d in dd:
            cut=0
            for j,r in enumerate(b['audit']):
                rt=str(r.get('at')or r.get('receipt',{}).get('at')or r.get('receivable',{}).get('ex_at')or '')
                if rt and M.ts(rt)>M.ts(d['at']):break
                cut=j+1
            p=M.prefix(b,cut);q=defaultdict(int)
            for lid,shares in p['q'].items():q[layers[lid]['sid']]+=shares
            assert {s:v for s,v in q.items()if v}==d['positions']
            inv=sum((D(v)*M.mark(s,d['at'])for s,v in q.items()if v),Z)
            M.near(inv,d['inventory'],'independent original mark inventory')
            M.near(p['cash']+p['divincome']+inv,d['nav'],'independent cash+recognizedAR+inventory NAV')
            M.near(p['divincome'],d['dividend_receivable'],'observed unpaid dividend AR not reusable cash')
            M.near(p['cash'],M.n(d['available'])+M.n(d['order_reserved'])+M.n(d['sale_receivable']),'independent liquid accounts')
            M.near(p['fees'],d['fees_cny'],'actual fee prefix')
            dec=next(v for v in b['decisions']if M.ts(v['at'])==M.ts(d['at']))
            assert len(dec['intents'])==d['pending_intents']
        pp={}
        for d in b['decisions']:
            for i in d['intents']:
                k=key(d['at'],i['sid'],i.get('role',i['kind']));assert k not in pp;pp[k]=i
        plans[arm]=pp
        for r in balances:
            if r['account']==arm:
                for f in ['independent_NAV_difference','budget_NAV_difference','spendable_difference','reserved_difference','capital_occupancy_difference','maximum_stock_quantity_difference']:M.near(r[f],0,f)
        M.near(b['ending_NAV'],dd[-1]['nav'],'terminal NAV')
        report[arm]=dict(daily_financial_closes=9,terminal_NAV=b['ending_NAV'],trades=len(b['trades']),fees=dd[-1]['fees_cny'],recognized_unpaid_dividend=dd[-1]['dividend_receivable'],actual_split_events=M.prefix(b,len(b['audit']))['split_events'])
    ee={}
    for e in events:
        arm=e['account'];assert arm!='B';k=key(e['at'],e['sid'],e['role']);assert (arm,k)not in ee;ee[arm,k]=e
        assert M.ts(e['at']).hour==15 and M.ts(e['at'])<=end
        flags=e['flags'];expected=D('.5')if arm=='UNIFORM50'else D(1)if flags['A']is True or(arm=='A_OR_B'and flags['B']is True)else D('.5')
        assert M.n(e['multiplier'])==expected
        assert M.n(e['budget_after'])==M.n(e['budget_before'])*expected
        assert 0<=e['cap_after']<=int(D(e['cap_before'])*expected)
        assert e['effective_after']=='NEXT_LEGAL_OPEN_NO_REAPPLICATION'
        if e['result']=='kept':
            p=plans[arm][k];assert p['cap']==e['cap_after'];assert M.n(p['budget'])==M.n(e['budget_after'])
            assert p['rank']==e['priority_rank']
            assert p.get('risk_budget')==e['risk_budget_unchanged']
            assert p.get('CP1_id')==e['CP1_id'] and p.get('epoch')==e['signal_epoch']
        else:
            assert e['result']=='confirmation_half_below_minimum' and e['cap_after']==0 and k not in plans[arm]
        counts[arm+'_'+str(expected)]+=1
    for arm in arms:
        b=books[arm]
        if arm!='B':assert set(plans[arm])=={k for (aa,k),v in ee.items()if aa==arm and v['result']=='kept'}
        for r in b['journal']:
            if r['kind']!='real_reserve':continue
            aa,at,sid,role=r['budget_order'].split('|');assert aa==arm
            p=plans[arm][key(at,sid,role)];assert r['shares']<=p['cap']
            assert D(r['shares'])*M.n(r['price'])<=M.n(p['budget'])
            assert M.ts(r['at'])>M.ts(at),'same-CLOSE or pre-decision order'
    old=T/'pvr_pool_feasibility/runs'/('2022'if a.window=='2022'else'2025_26')/'pair'
    gold=M.book(old/'B.json.gz');new=books['B']
    assert [t for t in gold['trades']if M.ts(t['at'])<=end]==new['trades']
    assert [d for d in M.rows(old/'daily.jsonl.gz')if M.ts(d['at'])<=end]==[d for d in daily if d['account']=='B']
    assert [d for d in gold['decisions']if M.ts(d['at'])<=end]==new['decisions']
    failures=[]
    for path,h in start['sources'].items():
        if M.sha(path)!=h:failures.append(dict(path=path,start_sha256=h,current_sha256=M.sha(path)))
    result=dict(status='PASS_SAVED_SMALL_FINANCE_AND_MODIFIER_WITH_SOURCE_STATUS_SEPARATE',run=str(a.run),window=a.window,arms=report,
                original_NONE_daily_trade_and_decision_prefix_exact=True,all_modifier_event_counts=dict(counts),modified_decisions_and_pending_counts_match=True,
                real_reserves_within_frozen_modified_plan=True,features_only_at_decision_CLOSE_source_verified=True,no_account_or_feature_replay=True,
                source_post_mismatches=failures,source_failure_preserved=(a.run/'FAILURE.json').exists(),source_sha256=M.SRC,
                reviewer_source_sha256=M.sha(__file__),reader_snapshot_sha256=M.sha(O/'shared_finance_reader_with_ar_snapshot.py'),
                limitations=['This observed nine-CLOSE window contains unpaid dividend AR and one integer split; paid dividend and fractional-cash cases remain outside this narrow receipt.','Feature booleans and clocks have separate source/physical-prefix receipt, not independently rerun here.','A source guard failure remains separately reported, never promoted by financial arithmetic alone.','No full financial run authorization.'])
    (a.out/'AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items()if k!='source_sha256'},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
