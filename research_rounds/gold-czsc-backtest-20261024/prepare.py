from pathlib import Path
import hashlib,json,datetime
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
raw=ROOT/'research_rounds/gold-chart-fit-20261024/raw/sina-AU0.response'
a=json.loads(raw.read_text().split('=(',1)[1].rsplit(');',1)[0]);d=pd.DataFrame(a);d.columns=['date','open','high','low','close','volume','hold','settle']
d['date']=pd.to_datetime(d.date)
for col in d.columns[1:]:d[col]=pd.to_numeric(d[col],errors='raise')
d=d.set_index('date').sort_index().loc[:'2026-10-13']
assert not d.index.duplicated().any() and not d.isna().any().any()
assert (d[['open','high','low','close']]>0).all().all() and (d.volume>=0).all()
assert ((d.low<=d[['open','close']].min(axis=1))&(d.high>=d[['open','close']].max(axis=1))).all()
prior=pd.read_csv(ROOT/'research_rounds/gold-chart-fit-20261024/data/sina-AU0.csv',index_col='date',parse_dates=True).loc[:'2026-10-13']
pd.testing.assert_frame_equal(d.reindex(prior.index),prior,check_dtype=False,check_freq=False)
(HERE/'inputs').mkdir(exist_ok=False);d.to_parquet(HERE/'inputs/AU0-all.parquet');d.loc['2020-01-01':].to_parquet(HERE/'inputs/AU0-main.parquet')
record=dict(at=datetime.datetime.now(datetime.timezone.utc).isoformat(),raw_path=str(raw.relative_to(ROOT)),raw_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),raw_total_rows=len(a),main_rows=len(d.loc['2020-01-01':]),prewarm_rows=int(((d.index>='2020-01-01')&(d.index<'2025-01-02')).sum()),backtest_rows=len(d.loc['2025-01-02':'2026-10-13']),old_overlap_rows=len(prior),old_overlap_identical=True,requests=0)
with (HERE/'preparation.json').open('x') as fp:json.dump(record,fp,ensure_ascii=False,indent=2);fp.write('\n')
print(json.dumps(record,ensure_ascii=False))
