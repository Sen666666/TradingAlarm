"""One-pass saved-small source/parameter/clock check; no native imports/replay."""
from pathlib import Path
from decimal import Decimal as D
from collections import Counter
import argparse, bisect, gzip, hashlib, json, math
import pandas as pd

OUT = Path(__file__).resolve().parent
T = OUT.parent
O = T/'market_gross_robustness_v1'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:
        for line in f: yield json.loads(line)
def ts(v): return pd.Timestamp(v)
def status(x,m,p):
    known=all(z is not None and math.isfinite(z) and z>0 for z in (x,m,p))
    return 'UNKNOWN' if not known else 'DOWN' if x<m and m<p else 'NOT_DOWN'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--run',type=Path,required=True)
    args=ap.parse_args(); run=args.run.resolve()
    assert str(run).startswith(str(O.resolve())+'/')
    completed=read(run/'COMPLETED.json'); assert completed['passed'] and completed['full'] is False
    started=read(run/'STARTED.json'); m=started['manifest']; family=m['family']
    prep=O/'prepared-small87-v4/long'/family/'SMALL_SOURCE_MANIFEST.json'
    assert m==read(prep) and m['window']=='long'
    source_check=read(OUT/'SMALL87_FINAL_PREPARATION_REVIEW.json')
    canonical_fix=read(OUT/'SMALL87_CANONICAL_FIX_SOURCE_SUPPLEMENT.json')
    assert canonical_fix['passed'] and sha(prep)==canonical_fix['new_manifest_binding'][family]['SHA256']
    assert all(sha(p)==h for p,h in m['source_sha256'].items())
    authp=Path(started['authorization']); auth=read(authp)
    assert sha(authp)==started['authorization_SHA256']
    assert auth['approved'] and auth['small_manifest_sha256']==sha(prep) and auth['family']==family and not auth['full']
    history=T/'benchmark_2022_2023/continuation2024/inputs/510300_history.csv'
    f=pd.read_csv(history,index_col='date',parse_dates=True)
    times=[ts(str(v.date())+'T15:10:00+08:00') for v in f.index]
    x=f.signal_close.to_numpy(float)
    config=dict(m['all_fixed_matrix'][family],**m['technical_only_control'])
    mas={n:(f.ma63.to_numpy(float) if n==63 else f.signal_close.rolling(n,min_periods=n).mean().to_numpy(float)) for n in {config[k][0] for k in m['active_small_arms']}-{None}}
    historysha=sha(history); cal=read(T/'market_gross_admission_native_v1/prepared/long/EXPECTED_CLOSE_CALENDAR.json')
    closes=[ts(v) for v in cal['closes']]
    refs=[prep,run/'STARTED.json',run/'COMPLETED.json',authp,history,
          OUT/'MA_INPUT_CLOCK_INDEPENDENT_REVIEW.json',OUT/'SMALL87_FINAL_PREPARATION_REVIEW.json',
          OUT/'SMALL87_CANONICAL_FIX_SOURCE_SUPPLEMENT.json',OUT/'SOURCE_BODY_INDEPENDENT_REVIEW.json']
    result={}; total=0; actual=0
    for name,begin,end,count in m['small_cases']:
        case=run/name; r=read(case/'SMALL_RESULT.json')
        assert r['passed'] and r['source_post_exact'] and not r['full'] and r['closes_each']==count
        assert set(r['arms'])==set(m['active_small_arms'])
        expected_days=[str(v.date()) for v in closes if begin<=str(v.date())<=end]
        assert len(expected_days)==count
        schedule={ts(d+'T'+h+'+08:00') for d in expected_days for h in ('09:30:00','15:10:00')}
        daily=list(rows(case/'pair/daily.jsonl.gz')); assert len(daily)==count*len(m['active_small_arms'])
        assert {r['account'] for r in daily}==set(m['active_small_arms'])
        assert sorted(p.name for p in (case/'pair').glob('*.json.gz'))==sorted(k+'.json.gz' for k in m['active_small_arms'])
        byarm={}
        for label in m['active_small_arms']:
            n,alpha,cost=config[label]; assert D(r['arms'][label]['cost_multiplier'])==D(cost)
            assert D(r['arms'][label]['alpha'])==D(alpha) if alpha is not None else r['arms'][label]['alpha']=='NO_EXTRA_GUARD'
            if n is None: continue
            p=case/'pair'/(label+'-gross-admission-events.jsonl.gz')
            k=Counter(); states=Counter(); unique={}; seq=0
            for e in rows(p):
                assert e['sequence']==seq; seq+=1; at=ts(e['at'])
                assert at in schedule and D(e['alpha'])==D(alpha)
                assert e['kind'] in ('route','reserve_pre','reserve_post','fill_pre','fill_post','fill_cancelled')
                info=e['info']; i=bisect.bisect_right(times,at)-1
                assert i>=1; ma=mas[n]; latest=closes[bisect.bisect_right(closes,at)-1]
                assert times[i]==latest
                assert ts(info['available_at'])==times[i]<=at
                assert info['day']==str(f.index[i].date()) and info['X']==x[i]
                assert info['source']==str(history.resolve()) and info['source_sha256']==historysha and info['MA_window']==n
                a,b=('MA63','previous_MA63') if n==63 else ('MA_value','previous_MA_value')
                assert info[a]==ma[i] and info[b]==ma[i-1]
                assert info['state']==status(x[i],ma[i],ma[i-1])!='UNKNOWN'
                if at.hour<15: assert info['day']<str(at.date())
                key=at.isoformat()
                if key in unique: assert unique[key]==info
                else: unique[key]=info
                k[e['kind']]+=1; states[info['state']]+=1
            byarm[label]=dict(events=seq,unique_clock_infos=len(unique),kind_counts=dict(k),state_counts=dict(states),MA_window=n,alpha=alpha,cost=cost)
            actual+=seq; refs.append(p)
        if family=='cost15':
            p=case/'REAL_WINDOW_PRE_ACCOUNT_CHECK.json'; w=read(p)
            assert w['passed'] and w['new_accounts']==w['new_fills']==0 and len(w['rows'])==2
            for row in w['rows']:
                sign=D(1) if row['side']=='buy' else D(-1); raw=D(row['raw_open'])
                assert D(row['base_execution'])==raw*(1+sign*D('.0005'))
                assert D(row['stress_execution'])==raw*(1+sign*D('.00075'))
                assert row['cost1_then15_then1_same_object_cache_preserved']
            refs.append(p)
        total+=len(daily); result[name]=dict(account_CLOSE_bridges=len(daily),guarded_arms=byarm,scheduled_OPEN_CLOSEs=count*2)
        refs += [case/'SMALL_RESULT.json',case/'pair/daily.jsonl.gz']
    assert total==source_check['manifests'][family]['account_days']
    assert all(sha(p)==h for p,h in m['source_sha256'].items())
    output=dict(passed=True,scope='committed 87-small actual parameter/source/market clock only',family=family,run=str(run),account_CLOSE_bridges=total,all_actual_gross_events=actual,cases=result,
                all_actual_market_X_MA_D_values_and_asof_exact=True,next_OPEN_no_today_CLOSE=True,UNKNOWN_actual_events=0,all_frozen_source_post_exact=len(m['source_sha256']),
                real_cost15_window_1_then_1_5_then_1='PASS_SAVED_ZERO_ACCOUNT_CHECK' if family=='cost15' else 'NOT_APPLICABLE_ORIGINAL_COST1',
                new_Accounts_or_economic_replays_by_reviewer=0,financial_atomic_or_PVR_reaudit=False,financial_review='SEPARATE_LEDGER_OWNER',full_authorization=False,economic_promotion=False,
                evidence_SHA256={str(p.resolve()):sha(p) for p in refs},checker_SHA256=sha(__file__))
    target=OUT/('ACTUAL_SMALL87_'+family.upper()+'_CLOCK_REVIEW.json'); assert not target.exists()
    target.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({'passed':True,'family':family,'account_CLOSE_bridges':total,'all_actual_gross_events':actual,'receipt_SHA256':sha(target)}))

if __name__=='__main__': main()
