"""Bounded saved-cap coverage/threshold contrast, no account/market model."""
from pathlib import Path
from collections import Counter
import hashlib,json
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[1]
DATA=Path('/Users/bytedance/repos/my-quant/data')
BASE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2')
ROSTER=BASE/'roster-dispositions.json';SELECTION=BASE/'selection.json'
GATE=ENTRY/'selection_qualification_closeout_v1/universe_gate_data/CANONICAL5517_MAP_CAP_DATA_AVAILABILITY.csv'
BASIC=DATA/'processed/factors/daily_basic/daily_basic.parquet'
RAW=DATA/'raw/tushare/a_share/daily_basic/daily_basic-MARKET_DAY-20260515-tushare-r2-a2-raw.parquet'
PULL=DATA/'meta/pulls/tushare/a_share/daily_basic/daily_basic-MARKET_DAY-20260515-tushare-r2-a2-raw.json'
PUBLISH=DATA/'meta/runs/daily_basic/daily_basic_20260515_smoke.json'
TARGETS={'300085.SZ':'银之杰','002583.SZ':'海能达','300666.SZ':'江丰电子','603061.SH':'金海通','301611.SZ':'珂玛科技','300604.SZ':'长川科技','301308.SZ':'江波龙','002371.SZ':'北方华创','688012.SH':'中微公司','688498.SH':'源杰科技','301348.SZ':'蓝箭电子','600198.SH':'大唐电信','300925.SZ':'法本信息','688479.SH':'友车科技'}
DAYS=['2022-01-10','2022-01-24','2024-09-24','2024-10-08','2026-01-15','2026-01-20','2026-05-15']
LIMIT=10_000_000_000
MV_CNY_MULTIPLIER=10_000 # Vendor daily_basic market value in 万元, not a strategy parameter.


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    if isinstance(x,(pd.Timestamp,np.datetime64)):return str(pd.Timestamp(x))
    if isinstance(x,np.generic):x=x.item()
    if x is None or x is pd.NA or x is pd.NaT:return None
    return None if isinstance(x,float)and not np.isfinite(x)else x


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(HERE/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def cap_status(v):return'UNKNOWN_CAP'if v is None or not np.isfinite(v)else'GT10BN'if v>LIMIT else'NOT_GT10BN'


def main():
    assert not(HERE/'COMPLETION.json').exists()
    roster=json.loads(ROSTER.read_text());by={r['symbol']:r for r in roster};selection=json.loads(SELECTION.read_text());gate=pd.read_csv(GATE)
    assert len(roster)==5576 and len(by)==5576 and len(gate)==5517
    basic=pd.read_parquet(BASIC);raw=pd.read_parquet(RAW);pull=json.loads(PULL.read_text());publish=json.loads(PUBLISH.read_text())
    assert len(basic)==5495 and basic.symbol.nunique()==5495 and basic.trade_date.nunique()==1
    assert not basic.duplicated(['symbol','trade_date']).any()
    raw=raw.rename(columns={'ts_code':'symbol'});raw['trade_date']=pd.to_datetime(raw.trade_date)
    native=['close','total_share','float_share','free_share','total_mv','circ_mv']
    joined=basic.merge(raw,on=['symbol','trade_date'],how='outer',validate='one_to_one',suffixes=('_processed','_raw'))
    for col in native:
        assert np.array_equal(joined[col+'_processed'].to_numpy(float).view(np.uint64),joined[col+'_raw'].to_numpy(float).view(np.uint64))
    coverage=dict(path=str(BASIC),rows=len(basic),symbols=basic.symbol.nunique(),trade_dates=sorted(basic.trade_date.dt.strftime('%Y-%m-%d').unique()),
        schema=[dict(name=f.name,type=str(f.type))for f in pq.read_schema(BASIC)],null_counts=basic.isna().sum().to_dict(),
        six_cap_share_close_raw_processed_bitexact=True,
        native_cap_or_share_nonfinite={c:int((~np.isfinite(basic[c])).sum())for c in native},
        native_cap_or_share_nonpositive={c:int((basic[c]<=0).sum())for c in native},
        total_mv_minus_close_times_total_share_max_abs=float(np.max(np.abs(basic.total_mv-basic.close*basic.total_share))),
        circ_mv_minus_close_times_float_share_max_abs=float(np.max(np.abs(basic.circ_mv-basic.close*basic.float_share))),
        raw_pull_at=pull['pulled_at'],raw_requested_range=pull['requested_range'],publish_created_at=publish['created_at'],
        publish_complete_means_this_one_day=True,no_historical_known_or_available_columns=True,
        historical_total_mv_unit='vendor native 万元; explicit *10000 for CNY; normalizer has no multiplier or preserved field-unit metadata',
        historical_share_unit='vendor native 万股; source value retained, not filled through missing dates')
    canonical=set(gate.symbol);current=[]
    for sid in sorted(canonical):
        r=by.get(sid);cap=None if r is None else r.get('cap_cny')
        current.append(dict(sid=sid,current_cap_cny=cap,current_cap_status='NOT_IN_CURRENT_ROSTER'if r is None else cap_status(cap),
            current_disposition=None if r is None else r['disposition'],cap_observed_at=None if r is None else r.get('cap_observed_at')))
    current=pd.DataFrame(current)
    counts=dict(full_roster5576_dispositions=dict(Counter(r['disposition']for r in roster)),
        full_roster_cap_status=dict(Counter(cap_status(r.get('cap_cny'))for r in roster)),
        canonical5517_cap_status=current.current_cap_status.value_counts().to_dict(),
        excluded_known_current_roster_count=sum(cap_status(r.get('cap_cny'))=='NOT_GT10BN'for r in roster),
        selection_observed_at=selection['observed_at'],cap_observed_date=selection['cap_observed_date'],roster_asof=selection['roster_asof'],
        vendor_market_value_timestamp_unknown=selection['market_timestamp_unknown'],source_id=selection['source_id'],
        current_selection_not_proof_of_original_runtime_binding=True)
    hist=basic.copy();hist['sid']=hist.symbol;hist['historical_total_cap_cny']=hist.total_mv*MV_CNY_MULTIPLIER
    hist['historical_circ_cap_cny']=hist.circ_mv*MV_CNY_MULTIPLIER;hist['dated_cap_status']=hist.historical_total_cap_cny.map(cap_status)
    cross=current.merge(hist[['sid','trade_date','historical_total_cap_cny','historical_circ_cap_cny','dated_cap_status']],on='sid',how='left',validate='one_to_one')
    cross.to_csv(HERE/'CANONICAL_CURRENT_VS_SINGLE_DATED_CAP.csv',index=False)
    both=cross.current_cap_status.isin(['GT10BN','NOT_GT10BN'])&cross.dated_cap_status.notna()
    counts['two_observed_records_comparable_count']=int(both.sum())
    counts['two_record_threshold_matrix']=cross.loc[both].groupby(['current_cap_status','dated_cap_status']).size().reset_index(name='n').to_dict('records')
    counts['matrix_not_isolated_time_effect']='THS company-total current snapshot vs TuShare daily_basic historical total_mv; date, provider, share/issuer scope and revisions may differ.'
    datecoverage=[];targetrows=[];dated_targets=[]
    for day in DAYS:
        f=basic.loc[basic.trade_date.eq(pd.Timestamp(day))]
        datecoverage.append(dict(day=day,records=len(f),symbols=f.symbol.nunique(),canonical_covered=len(set(f.symbol)&canonical),canonical_uncovered=5517-len(set(f.symbol)&canonical)))
        for sid,name in TARGETS.items():
            f=hist.loc[hist.sid.eq(sid)&hist.trade_date.eq(pd.Timestamp(day))]
            dated_targets.append(dict(sid=sid,name=name,day=day,status='LOCAL_DATED_CAP_ROW'if len(f)==1 else'NO_LOCAL_DATED_CAP_ROW',
                total_mv_native=None if f.empty else f.iloc[0].total_mv,circ_mv_native=None if f.empty else f.iloc[0].circ_mv,
                total_cap_cny=None if f.empty else f.iloc[0].historical_total_cap_cny,total_share_native=None if f.empty else f.iloc[0].total_share,
                close_native=None if f.empty else f.iloc[0].close,dated_threshold=None if f.empty else f.iloc[0].dated_cap_status))
    for sid,name in TARGETS.items():
        r=by.get(sid);h=hist.loc[hist.sid.eq(sid)];cap=None if r is None else r.get('cap_cny')
        targetrows.append(dict(sid=sid,pre_fixed_name=name,current_roster_name=None if r is None else r['name'],current_cap_cny=cap,
            current_cap_100m_cny=None if cap is None else cap/1e8,current_disposition=None if r is None else r['disposition'],
            current_cap_status=cap_status(cap),current_selected=None if r is None else r['disposition']=='selected',
            cap_observed_at=None if r is None else r.get('cap_observed_at'),selection_market_timestamp_unknown=selection['market_timestamp_unknown'],
            local_dated_cap_rows=len(h),local_cap_dates='|'.join(h.trade_date.dt.strftime('%Y-%m-%d')),
            May15_total_cap_cny=None if h.empty else h.iloc[0].historical_total_cap_cny,
            May15_circ_cap_cny=None if h.empty else h.iloc[0].historical_circ_cap_cny,
            May15_total_share_native=None if h.empty else h.iloc[0].total_share,
            May15_native_close=None if h.empty else h.iloc[0].close,
            May15_threshold=None if h.empty else h.iloc[0].dated_cap_status,
            historical_cap_pull_at=None if h.empty else pull['pulled_at'],
            historical_2024_or_Jan2026_cap_available=False,
            backward_reconstructed_cap=False))
    pd.DataFrame(targetrows).to_csv(HERE/'FOURTEEN_PRE_FIXED_NAMES_CURRENT_AND_DATED_CAP.csv',index=False)
    pd.DataFrame(dated_targets).to_csv(HERE/'FOURTEEN_NAMES_SEVEN_DATE_CAP_AVAILABILITY.csv',index=False)
    pd.DataFrame(datecoverage).to_csv(HERE/'FIXED_DATE_CAP_COVERAGE.csv',index=False)
    save('DAILY_BASIC_COVERAGE.json',coverage);save('CURRENT_STATIC_FILTER_COUNTS.json',counts)
    sources=[BASIC,RAW,PULL,PUBLISH,ROSTER,SELECTION,GATE,Path(__file__),DATA.parent/'src/my_quant/data/builders/daily_basic_factors.py']
    save('COMPLETION.json',dict(status='COMPLETE_BOUNDED_CAP_COVERAGE_AND_STATIC_IMPACT_NO_RUNTIME_CAUSAL_CLAIM',
        source_sha256={str(p):sha(p)for p in sources},targets=14,dated_target_rows=98,model_or_account_calls=0,
        original_runtime_snapshot_use_not_decided_here=True,backcast_current_cap_times_historical_price=False,
        named_current_selected=sum(x['current_selected']is True for x in targetrows),
        outputs={p.name:sha(p)for p in HERE.iterdir()if p.suffix in {'.json','.csv'}and p.name!='COMPLETION.json'}))
    print(json.dumps(clean(dict(coverage=coverage,counts=counts,targets=targetrows)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
