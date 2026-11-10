"""Limited 3-5 native isolated-CORE technical comparisons, not full labels."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from decimal import Decimal as D
import hashlib,json,time,traceback
from native_single_asset import Provider,WORK,O,read,gzread,encoded,SOURCES,COUNTS,N

def save(name,value):
    (O/name).write_text(json.dumps(encoded(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    start=time.monotonic();p=Provider();candidates=[];eligible_counts={}
    for window in ('long','strong'):
        b=gzread(WORK/'new_price_trend_v1/funding/runs'/(window+'_OFF')/'pair/B.json.gz')
        decisions={r['at'][:10]:r for r in b['decisions']}
        buys=defaultdict(list)
        for t in b['trades']:
            if t['side']=='buy':buys[t['security_id']].append(t)
        n=0
        for layer in b['layers']:
            if layer['kind']!='core' or layer['closed']is None:continue
            sid=layer['sid'];opened=layer['opened'];closed=layer['closed']
            other=[t for t in buys[sid]if opened<=t['at']<=closed and t['layer']!=layer['id']]
            if other:continue
            bt=next(t for t in buys[sid]if t['layer']==layer['id'])
            sd=bt['signal_at'][:10];decision=decisions[sd]
            intents=[i for i in decision['intents']if i['sid']==sid and i['role']=='core']
            assert len(intents)==1
            expected=[t for t in b['trades']if t['security_id']==sid and opened<=t['at']<=closed]
            expected=[dict(at=t['at'],side=t['side'],shares=t['shares'],gross_cny=t['gross_cny'],fees_cny=t['fees_cny'])for t in expected]
            record=p.records[sid]
            actions,_=N.read_actions(record,p.markets[sid].bundle.manifest_path.parent if sid in p.markets else __import__('native_single_asset').J.M.P)
            actions=[a for a in actions if opened[:10]<a['effective_date']<=closed[:10]]
            cash=any(D(a['cash_per_old_share'])!=0 for a in actions)
            split=any(D(a['split_ratio'])!=1 for a in actions)
            event=dict(key=f'ACTUAL_CALIBRATION|{window}|{layer["id"]}',window=window,sid=sid,
                       signal_day=sd,OPEN=opened[:10],decision_NAV=decision['nav'],original_intent=intents[0])
            candidates.append(dict(event=event,layer=layer,expected=expected,quantity=int(bt['shares']),
                                   has_cash_CA=cash,has_split_CA=split,CA_terms=actions))
            n+=1
        eligible_counts[window]=n
        del b
    selected=[]
    # Pure interface fixtures: no-pair interference and CA coverage, not profitability.
    def pick(test):
        found=next((x for x in candidates if test(x) and x not in selected),None)
        if found:selected.append(found)
    pick(lambda x:x['event']['window']=='long'and not x['has_cash_CA']and not x['has_split_CA'])
    pick(lambda x:x['event']['window']=='strong'and not x['has_cash_CA']and not x['has_split_CA'])
    pick(lambda x:x['has_cash_CA']and not x['has_split_CA'])
    pick(lambda x:x['has_split_CA'])
    pick(lambda x:True)
    assert 3<=len(selected)<=5
    save('CALIBRATION_SELECTION.json',dict(scope='Original closed CORE with no other same-sid buy layer during holding interval',
          eligible_counts=eligible_counts,selected=selected,selection_uses_profit=False,new_portfolio_policy_accounts=0))
    results=[]
    for j,case in enumerate(selected):
        assert time.monotonic()-start<120,'Technical calibration compute cap'
        save('TECHNICAL_PROGRESS.json',dict(completed=j,total=len(selected),single_asset_shadow_paths=COUNTS['single_asset_shadow_paths'],seconds=time.monotonic()-start))
        out=p.path(case['event'],quantity=case['quantity'],trace=True)
        actual=out['native_trace']['trades'];actual=[dict(at=t['at'],side=t['side'],shares=t['shares'],gross_cny=t['gross_cny'],fees_cny=t['fees_cny'])for t in actual]
        assert len(actual)==len(case['expected']),(case['event']['key'],'fill length',actual,case['expected'])
        for a,b in zip(actual,case['expected']):
            assert a['at']==b['at']and a['side']==b['side']and int(a['shares'])==int(b['shares']),(a,b)
            for k in ('gross_cny','fees_cny'):assert D(a[k])==D(b[k]),(case['event']['key'],k,a,b)
        l=out['native_trace']['layers'][0];ref=case['layer']
        for k in ('cash','dividend','qty'):assert D(str(l[k]))==D(str(ref[k])),(case['event']['key'],k,l[k],ref[k])
        assert out['status']=='closed' and out['horizon_CLOSE_day']==ref['closed'][:10],out
        expected_net=D(ref['cash'])+D(ref['dividend'])
        assert abs(D(out['net_pnl_original_ledger'])-expected_net)<D('.000001'),(out,expected_net)
        results.append(dict(key=case['event']['key'],sid=case['event']['sid'],window=case['event']['window'],
            has_cash_CA=case['has_cash_CA'],has_split_CA=case['has_split_CA'],
            full_fill_sequence_exact=True,layer_cash_dividend_qty_exact=True,
            net_profit_exact=True,expected_net_profit=str(expected_net),result=out))
        save('CALIBRATION_PARTIAL_RESULTS.json',results)
    save('TECHNICAL_CALIBRATION_RESULT.json',dict(passed=True,paths=len(results),results=results,
         single_asset_shadow_paths=COUNTS['single_asset_shadow_paths'],new_portfolio_policy_accounts=0,
         sparse_event_schedule_verified_against_actual_native_CORE=True,
         seconds=time.monotonic()-start,limit_seconds=120,full_labels_executed=False,
         explicit_failure_boundary='Technical isolated sample does not establish independent funding or whole-portfolio counterfactuals.'))
    SOURCES[str(Path(__file__).resolve())]=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save('TECHNICAL_SOURCE_SHA256.json',SOURCES)
    print(json.dumps(dict(passed=True,paths=len(results),single_asset_shadow_paths=COUNTS['single_asset_shadow_paths'],seconds=time.monotonic()-start)))

if __name__=='__main__':
    started=time.monotonic()
    try:main()
    except Exception as exc:
        save('TECHNICAL_FAILURE.json',dict(error=str(exc),traceback=traceback.format_exc(),seconds=time.monotonic()-started,
             single_asset_shadow_paths=COUNTS['single_asset_shadow_paths'],new_portfolio_policy_accounts=0,automatic_retry=False))
        raise
