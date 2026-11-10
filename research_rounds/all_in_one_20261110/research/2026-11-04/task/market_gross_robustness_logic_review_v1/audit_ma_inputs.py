"""Bounded zero-account check of frozen same-X neighbouring market MAs."""
from pathlib import Path
from collections import Counter
import bisect,hashlib,json,math,pickle,sys
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;T=O.parent/'market_gross_robustness_v1';P=T.parent/'market_gross_admission_native_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def state(x,ma,previous):
    known=all(z is not None and math.isfinite(z)and z>0 for z in(x,ma,previous))
    return 'UNKNOWN'if not known else'DOWN'if x<ma and ma<previous else'NOT_DOWN'
def norm(v):
    v=dict(v)
    if v.get('available_at')is not None:v['available_at']=pd.Timestamp(v['available_at']).isoformat()
    return v

def main():
    freeze=read(T/'PRE_MA_CHECK_FREEZE.json')
    for p,h in freeze['source_sha256'].items():assert sha(p)==h
    sys.path.insert(0,str(T));from ma_provider import MarketInfo
    assert 'gross_adapter'not in sys.modules and 'capacity_adapter'not in sys.modules
    producer=read(T/'MA63_RECOMPUTE_CHECK.json');proof={};sources={}
    for win in('long','strong'):
        record=producer['windows'][win];path=Path(record['source_path']);assert sha(path)==record['source_sha256']
        history_sha=sha(path);sources[str(path)]=history_sha;f=pd.read_csv(path,index_col='date',parse_dates=True)
        assert f.index.is_unique and f.index.is_monotonic_increasing
        x=f.signal_close.to_numpy(float);old=f.ma63.to_numpy(float);new=f.signal_close.rolling(63,min_periods=63).mean().to_numpy(float)
        differences=[];numeric_differences=[]
        for i,t in enumerate(f.index):
            before=old[i-1]if i else None;after=new[i-1]if i else None
            if state(x[i],old[i],before)!=state(x[i],new[i],after):differences.append(str(t.date()))
            if np.isfinite(old[i])and np.isfinite(new[i])and old[i]!=new[i]:numeric_differences.append(dict(day=str(t.date()),stored=float(old[i]),recomputed=float(new[i]),difference=float(new[i]-old[i])))
        assert not differences,'recomputed63 silently changes frozen stored-D classification'
        assert record['all_history_D_classification_exact']and record['differences']==differences
        calpath=P/'prepared'/win/'EXPECTED_CLOSE_CALENDAR.json';cal=read(calpath);times=[pd.Timestamp(str(t.date())+'T15:10:00+08:00')for t in f.index];checks={}
        for n in(62,63,64):
            ma=old if n==63 else f.signal_close.rolling(n,min_periods=n).mean().to_numpy(float)
            provider=MarketInfo(path,cal['closes'],n);restarted=pickle.loads(pickle.dumps(provider));count=Counter()
            for close in cal['closes'][2:]:
                for hour in('09:30:00','15:10:00'):
                    at=pd.Timestamp(close[:10]+'T'+hour+'+08:00');i=bisect.bisect_right(times,at)-1
                    expected=state(x[i],ma[i],ma[i-1]if i else None);got=provider.state(at)
                    assert got['state']==expected and got['MA_window']==n
                    assert got['day']==str(f.index[i].date())and got['available_at']==times[i]<=at
                    assert got['source_sha256']==history_sha
                    current_field='MA63'if n==63 else'MA_value';previous_field='previous_MA63'if n==63 else'previous_MA_value'
                    assert got[current_field]==ma[i]and got[previous_field]==ma[i-1]
                    assert norm(got)==norm(restarted.state(at))
                    if hour=='09:30:00':assert got['day']<close[:10]
                    count[expected]+=1
            # Existing prescribed availability boundary, no new native fixture.
            cut='2022-01-07'if win=='long'else'2025-07-04';prefix=provider.prefix(cut)
            prior=[pd.Timestamp(v)for v in cal['closes']if v[:10]<=cut]
            for at in prior[-2:]:assert norm(provider.state(at))==norm(prefix.state(at))
            next_close=next(pd.Timestamp(v)for v in cal['closes']if v[:10]>cut)
            same_day_open=pd.Timestamp(str(next_close.date())+'T09:30:00+08:00')
            assert norm(prefix.state(same_day_open))==norm(provider.state(same_day_open))
            assert prefix.state(next_close)['state']=='UNKNOWN'
            checks[str(n)]=dict(planned_OPEN_CLOSE_checks=sum(count.values()),states=dict(count),prefix_and_pickle_exact=True,stored63_preserved=(n==63),only_same_X_window_changed=(n!=63))
        proof[win]=dict(history_rows=len(f),full_history_recomputed63_D_differences=differences,
            finite_MA63_numeric_difference_count=len(numeric_differences),numeric_MA63_difference_examples=numeric_differences[:8],
            MA_numeric_equal_not_required_when_D_exact_and_main_stored_preserved=True,neighbour_checks=checks)
        sources[str(calpath.resolve())]=sha(calpath)
    for p,h in freeze['source_sha256'].items():assert sha(p)==h;sources[p]=h
    out=dict(passed=True,status='PASS_SAME_STORED_X_MA_NEIGHBOUR_INPUT_CLOCK_SCOPE_NO_ACCOUNT',windows=proof,source_SHA256=sources,
        no_primary63_replacement=True,no_D_acceptance_tolerance=True,no_new_TR_or_stock_indicator=True,accounts_run=0,financial_replay=0,
        limitations=['Same seen development histories, not OOS.','This is the market-input gate only; alpha/fee/window/account implementation and small native receipts require separate review.'])
    path=O/'MA_INPUT_CLOCK_INDEPENDENT_REVIEW.json';assert not path.exists();path.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,output=str(path),SHA256=sha(path),windows=proof),indent=2))

if __name__=='__main__':main()
