"""Fixed2023 read-only input coverage and rights audit. No models/accounts."""
from pathlib import Path
from decimal import Decimal as D
import json,collections,time,hashlib,csv
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;START='2023-01-01';END='2023-12-31'
U=W/'universe-cp1-inputs-20261031';P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 p=O/name;t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def quant(s):
 s=pd.Series(s,dtype=float).dropna();return {'n':len(s),**{str(q):float(s.quantile(q)) for q in [0,.5,1]}} if len(s) else {'n':0}
def main():
 begun=time.monotonic();sm=read(U/'STOCK_MANIFEST.json');im=read(U/'INDUSTRY_MANIFEST.json');fixed=read(U/'FREEZE.json')['stocks'];assert len(fixed)==1709 and len(im)==90
 records={r['series_id']:r for r in read(P/'manifest.json')['series']};rulespath=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json');rules=read(rulespath);cal=pd.DatetimeIndex(sorted({pd.Timestamp(d[:10]) for d in rules['calendars']['A']}));days=cal[(cal>=START)&(cal<=END)];assert len(days)>0
 masterpath=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/results/stock-data-audit/master-crosswalk.csv');master={r['symbol']:r for r in csv.DictReader(masterpath.open())}
 with np.load(P/'h1.npz') as z:hdates=pd.DatetimeIndex(z['dates']);symbols=[str(s) for s in z['symbols']];mask=(hdates>=days[0])&(hdates<=days[-1]);hs=pd.DataFrame(z['score'][mask],index=hdates[mask],columns=symbols).reindex(days)
 counts=pd.DataFrame(0,index=days,columns=['facts_observed','raw_valid_OHLC','positive_volume','CP1_ready','stock_I_H1_ready']);stocks=[];rights=[];preipo=[]
 for k,r in enumerate(sm,1):
  sid=r['symbol'];f=pd.read_parquet(r['refs']['facts'],columns=['raw_close','factor','e0_ready','g_ready','i_target','i_buy']);cp=pd.read_parquet(r['refs']['CP1'],columns=['ready','receipt']);q=f.loc[START:END];cq=cp.loc[START:END]
  raw=pd.read_parquet(records[sid]['raw']['path'],columns=['trade_date','open','high','low','close','volume','observed_bar','price_eligible']);raw.index=pd.DatetimeIndex(pd.to_datetime(raw.trade_date)).normalize();rq=raw.loc[START:END]
  good=rq[['open','high','low','close']].apply(np.isfinite).all(axis=1)&rq[['open','high','low','close']].gt(0).all(axis=1)&rq.high.ge(rq.low)&rq.observed_bar.eq(True)&rq.price_eligible.eq(True)
  ready=q.e0_ready.eq(True)&q.g_ready.eq(True)&hs[sid].notna().reindex(q.index).eq(True)
  fields=dict(facts_observed=pd.Series(True,index=q.index),raw_valid_OHLC=good,positive_volume=good&rq.volume.gt(0)&np.isfinite(rq.volume),CP1_ready=cq.ready.eq(True),stock_I_H1_ready=ready)
  for name,v in fields.items():counts[name]+=v.reindex(days).eq(True).fillna(False).astype(int)
  ipo=pd.to_datetime(master.get(sid,{}).get('ipoDate'),errors='coerce')
  if pd.notna(ipo) and int(good.loc[good.index<ipo].sum()):preipo.append(dict(sid=sid,IPO=str(ipo.date()),valid_rows_before_IPO=int(good.loc[good.index<ipo].sum())))
  rr=read(r['refs']['receipts']);cached=sum(START<=x['confirmed_day']<=END for x in rr);native=int(cq.receipt.eq(True).sum())
  stocks.append(dict(sid=sid,IPO=str(ipo.date()) if pd.notna(ipo) else None,warm_observations=int((f.index<days[0]).sum()),facts_2023=len(q),first_2023=str(q.index[0].date()) if len(q) else None,last_2023=str(q.index[-1].date()) if len(q) else None,missing_observation_sessions=len(days)-len(q.index.intersection(days)),raw_valid_2023=int(good.sum()),CP1_ready=int(cq.ready.eq(True).sum()),native_CP1_receipts=native,cached_canonical_receipts=cached,I_fresh_true=int((q.i_target.eq(True)&q.i_buy.eq(True)).sum()),joint_ready=int(ready.sum()),factor_unknown=int(q.factor.isna().sum())))
  ap=records[sid].get('adjustment',{}).get('actions',{}).get('path')
  if ap:
   for e in read(ap).get('events',[]):
    if not START<=e['effective_date']<=END:continue
    rights.append(dict(sid=sid,**e,paid_time_unknown=e.get('paid_at') is None,sellable_time_unknown=e.get('new_shares_sellable_at') is None,known_at_unknown=e.get('known_at') is None))
  if k%500==0:print('READ_STOCKS',k,round(time.monotonic()-begun,2),flush=True)
 industries=[]
 for r in im:
  sid=r['series'];q=pd.read_parquet(r['refs']['CP1_input']).loc[START:END];z=pd.read_parquet(r['refs']['CP1'],columns=['ready','receipt']).loc[START:END];s=pd.read_parquet(r['refs']['state']);s=s[(s.day>=START)&(s.day<=END)];rr=read(r['refs']['receipts']);industries.append(dict(sector=sid,input_observations=len(q),CP1_observations=len(z),CP1_ready=int(z.ready.eq(True).sum()),state_observations=len(s),state_unknown=int(s.action.eq('unknown').sum()),H1_known=int(hs[sid].notna().sum()),native_CP1_receipts=int(z.receipt.eq(True).sum()),cached_canonical_receipts=sum(START<=x['confirmed_day']<=END for x in rr)))
 recoverypath=W/'mainline-absolute-Q4-20261031/recovery.csv';recovery=pd.read_csv(recoverypath,index_col=0,parse_dates=True).reindex(days);counts.index.name='day';counts.to_csv(O/'DAILY_INPUT_COUNTS.csv')
 cash=[r for r in rights if D(str(r.get('cash_per_old_share',0)))>0];split=[r for r in rights if D(str(r.get('split_ratio',1)))!=1];ipos=pd.to_datetime(pd.Series([s['IPO'] for s in stocks]),errors='coerce');present=[s for s in stocks if s['facts_2023']]
 result=dict(read_only=True,new_account_runs=0,new_numeric_cache_generated=0,fixed_identities=1709,fixed_industries=90,calendar_first=str(days[0].date()),calendar_last=str(days[-1].date()),market_sessions=len(days),stocks_with_2023_facts=len(present),no_2023_facts_ids=[s['sid'] for s in stocks if not s['facts_2023']],CP1_ready_ever=sum(s['CP1_ready']>0 for s in stocks),joint_ready_ever=sum(s['joint_ready']>0 for s in stocks),IPO_unknown=int(ipos.isna().sum()),IPO_during2023=int((ipos.ge(START)&ipos.le(END)).sum()),IPO_after2023=int(ipos.gt(END).sum()),valid_preIPO_anomalies=preipo,stock_receipts_native=sum(s['native_CP1_receipts'] for s in stocks),stock_receipts_cached=sum(s['cached_canonical_receipts'] for s in stocks),stock_receipt_series_to_export=sum(s['native_CP1_receipts']>s['cached_canonical_receipts'] for s in stocks),industry_receipts_native=sum(s['native_CP1_receipts'] for s in industries),industry_receipts_cached=sum(s['cached_canonical_receipts'] for s in industries),all90_complete=all(s['state_observations']==len(days) and s['CP1_observations']==len(days) and s['input_observations']==len(days) for s in industries),industry_unknown_rows=sum(s['state_unknown'] for s in industries),market_clock_rows=len(recovery),market_missing=recovery.isna().sum().to_dict(),daily_qualification_count=counts.apply(quant).to_dict(),rights=dict(total_events=len(rights),cash_events=len(cash),cash_paid_time_unknown=sum(r['paid_time_unknown'] for r in cash),split_events=len(split),split_sellable_time_unknown=sum(r['sellable_time_unknown'] for r in split),known_at_missing=sum(r['known_at_unknown'] for r in rights)),current_snapshot_not_PIT=True,no_future_IPO_imputation=True,seconds=time.monotonic()-begun)
 # apply(quant) can make a nested dataframe; keep column-oriented dictionaries.
 result['daily_qualification_count']={c:quant(counts[c]) for c in counts}
 save('STOCK_COVERAGE.json',stocks);save('INDUSTRY_COVERAGE.json',industries);save('RIGHTS_2023.json',rights);save('INPUT_READINESS.json',result);save('SOURCE_FREEZE.json',dict(new_account_runs=0,source_SHA256={str(p):sha(p) for p in [Path(__file__),U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',U/'FREEZE.json',P/'manifest.json',P/'h1.npz',recoverypath,rulespath,masterpath]}))
 print('READINESS',json.dumps(result,ensure_ascii=False,default=str),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e),new_account_runs=0));raise
