from pathlib import Path
import json,hashlib
import compare_ar6_layers as C
P=Path(__file__).resolve().parent
B=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
cases=[('2022Jan',B/'g-s-C-R0-continuous-january-v1-20261102/baseline_readonly/C10-NATIVE_ACCOUNT.json','2022-01-28',B/'g-s-C-R0-continuous-january-v1-20261102/baseline_readonly/ALL_LAYERS.json',True),('2025JulAug',B/'g-s-C-August-continuation-v1-20261102/runs/C10/2025-08-29-CLOSE.json','2025-08-29',B/'g-s-C-August-continuation-v1-20261102/analysis/C10-LAYERS.json',False)]
checks=[]
for label,path,cut,lp,account_only in cases:
    raw,h=C.read(path);r=C.extract(raw,cut,allow_account_only=account_only);old=json.loads(lp.read_text());old=old['C10'] if isinstance(old,dict) else old;old={z['layer']:z for z in old}
    for z in r['layers']:
        for k in ['buy_gross','buy_fee','buy_cost','realized_trade_PNL','unrealized_net_buy_cost','booked_dividend_income','total_contribution']:C.near(C.D(z[k]),C.D(old[z['layer']][k]),'old exported '+k)
        assert z['entry_class']==old[z['layer']]['entry_class']
    check=dict(window=label,layers=len(old),all_seven_exported_fields_within_1e_minus12_yuan=True,all_entry_classes_exact=True,campaigns=len(r['campaigns']),quantity_closed_campaigns=sum(z['quantity_closed'] for z in r['campaigns']),source_sha256=h)
    if not account_only:
        check['actual_funding_exit_orders']=len(C.funding(raw))
        def rejected(call):
            try:call()
            except ValueError:return True
            raise AssertionError('unsafe fake saved state accepted')
        orig=raw['last_completed'];raw['last_completed']='2025-09-01 15:10:00+08:00';assert rejected(lambda:C.extract(raw,cut));raw['last_completed']=orig
        cb=raw['account']['native_callbacks'];cb.append(dict(kind='split_fraction_floor_proxy',sid='FAKE',cost_writeoff='27.86'));assert rejected(lambda:C.extract(raw,cut));cb.pop()
        cb.append(dict(kind='native_split',sid='FAKE',ratio='1.4'));assert rejected(lambda:C.extract(raw,cut));cb.pop()
        mark=raw['account']['market_asof'];sid=next(iter(mark));orig=mark[sid];mark[sid]='2025-09-01 09:30:00+08:00';assert rejected(lambda:C.extract(raw,cut));mark[sid]=orig
        check['future_cursor_future_mark_fractional_and_integer_split_guards']=4
    else:
        try:C.extract(raw,cut)
        except ValueError:check['missing_cursor_rejected_without_explicit_reference_flag']=True
        else:raise AssertionError('account-only input silently accepted')
    assert hashlib.sha256(path.read_bytes()).hexdigest()==h
    checks.append(check)
C.dump(P/'AR6_EXTRACTOR_BASELINE_CHECK-v2.json',dict(passed=True,financial_events=0,account_restores=0,extractor_sha256=hashlib.sha256((P/'compare_ar6_layers.py').read_bytes()).hexdigest(),checks=checks))
print(json.dumps(checks,ensure_ascii=False,indent=2))
