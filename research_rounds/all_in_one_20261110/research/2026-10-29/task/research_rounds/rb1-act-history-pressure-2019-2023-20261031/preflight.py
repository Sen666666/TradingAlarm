from pathlib import Path
import json,csv,time,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');TP=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared');DP=RR/'innovative-drug-sfw3-20261028/prepared';T=time.monotonic()
inputs={};annual=[];industries=[];bench=[];warm=[];actions=[]
def note(p):inputs[str(p)]=hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def export(n,x):pd.DataFrame(x).to_csv(O/n,index=False)
rulesp=RR/'pvr-act-comparison-20261027/execution-rules-v2.json';note(rulesp);rules=json.loads(rulesp.read_text());cal=pd.DatetimeIndex(sorted({pd.Timestamp(x[:10]) for x in rules['calendars']['A']}));dec=pd.DatetimeIndex(sorted({pd.Timestamp(x[:10]) for x in rules['decision_cutoffs']}));assert cal[cal>='2019-01-01'][0]==pd.Timestamp('2019-01-02');assert cal[cal<='2023-12-31'][-1]==pd.Timestamp('2023-12-29');assert dec[dec<'2019-01-01'][-1]==pd.Timestamp('2018-12-28');market_days=cal[(cal>='2019-01-01')&(cal<='2023-12-31')];all_dates=dec[(dec>='2018-12-28')&(dec<='2023-12-29')]
mp=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/results/stock-data-audit/master-crosswalk.csv');note(mp);master={r['symbol']:r for r in csv.DictReader(mp.open())}
rpath=RR/'innovative-drug-sfw3-20261028/market-returns.parquet';mpath=rpath.with_name('market-momentum.parquet');note(rpath);note(mpath);r=pd.read_parquet(rpath);mom=pd.read_parquet(mpath)
for sec,prep,pool,rp,minsec in [('TECH',TP,RR/'tech-compound-design-20261026/proposed-pool.csv',TP/'recovery.csv',8),('DRUG',DP,RR/'innovative-drug-sfw3-20261028/pool.csv',RR/'innovative-drug-local-recovery-20261028/recovery.csv',3)]:
 note(pool);note(rp);ro=pd.read_csv(pool);rec=pd.read_csv(rp,index_col=0,parse_dates=True);used=rec.reindex(all_dates);assert not used[['market','prior_high63','breadth','breakout']].isna().any().any();assert set(ro.symbol)<=set(r.columns)
 def calculate(rr,mm):
  sr=[];sb=[];cnt=[]
  for k,g in ro.groupby('sector_id'):
   sr.append(rr[g.symbol].mean(axis=1));v=mm[g.symbol];n=v.notna().sum(axis=1);cnt.append(n.rename(k));sb.append((v.gt(0).sum(axis=1)/n).where(n>=5))
  agg=pd.concat(sr,axis=1).mean(axis=1);price=np.exp(agg.fillna(0)).cumprod();b=pd.concat(sb,axis=1);breadth=b.mean(axis=1).where(b.notna().sum(axis=1)>=minsec);z=pd.DataFrame(dict(market=price,prior_high63=price.shift().rolling(63,min_periods=63).max(),breadth=breadth));z['breakout']=(price>z.prior_high63)&(price.diff()>0)&(breadth>.6);return z,pd.concat(cnt,axis=1)
 z,cov=calculate(r,mom);small,_=calculate(r.loc[:'2021-12-31'],mom.loc[:'2021-12-31']);pd.testing.assert_frame_equal(small,z.loc[:'2021-12-31'],check_exact=True)
 for k in ['market','prior_high63','breadth']:np.testing.assert_allclose(z.reindex(all_dates)[k],used[k],rtol=1e-12,atol=1e-12,equal_nan=True)
 np.testing.assert_array_equal(z.reindex(all_dates).breakout,used.breakout)
 valid=(cov>=5).sum(axis=1).reindex(all_dates);assert valid.ge(minsec).all()
 for year in range(2019,2024):
  ix=all_dates[all_dates.year==year];bench.append(dict(sector=sec,year=year,decision_days=len(ix),benchmark_known=len(ix),valid_sectors_min=int(valid.reindex(ix).min()),valid_sectors_max=int(valid.reindex(ix).max()),breakouts=int(rec.reindex(ix).breakout.sum()),market_min=float(rec.reindex(ix).market.min()),market_max=float(rec.reindex(ix).market.max())))
 manifest=json.loads((prep/'manifest.json').read_text());note(prep/'manifest.json');recs={x['series_id']:x for x in manifest['series']};hz=np.load(prep/'h1.npz');note(prep/'h1.npz');hd=pd.DatetimeIndex(hz['dates']);hc={str(s):i for i,s in enumerate(hz['symbols'])};cols={}
 for sid in ro.symbol:
  fp=prep/'facts'/f'{sid}.parquet';sp=prep/'signals'/f'{sid}.parquet';note(fp);note(sp);f=pd.read_parquet(fp);raw=pd.read_parquet(sp);eligible=raw.observed_bar.fillna(False).astype(bool)&raw.price_eligible.fillna(False).astype(bool)&raw.volume_eligible.fillna(False).astype(bool)&~raw.source_invalid.fillna(True).astype(bool)&~raw.synthetic_event_bar.fillna(True).astype(bool)&raw.close.gt(0);ipo=pd.to_datetime(master.get(sid,{}).get('ipoDate'),errors='coerce');rank=pd.Series(hz['score'][:,hc[sid]],index=hd).reindex(f.index);joint=(eligible.reindex(f.index,fill_value=False)&f.e0_ready.fillna(False).astype(bool)&f.g_ready.fillna(False).astype(bool)&rank.notna())
  assert pd.isna(ipo) or not eligible.loc[(eligible.index>=pd.Timestamp('2019-01-01'))&(eligible.index<ipo)].any(),('preIPO usable price',sid,ipo)
  cols[sid]=(eligible,joint,ipo)
  prior=f.loc[:'2018-12-28'];warm.append(dict(sector=sec,symbol=sid,IPO=str(ipo.date()) if pd.notna(ipo) else None,first_cache=str(f.index.min().date()),pre_start_cached_rows=len(prior),pre_start_valid_rows=int(eligible.loc[:'2018-12-28'].sum()),pre_start_joint_E0_G1_H1=bool(joint.loc[:'2018-12-28'].iloc[-1]) if len(prior) else None,price_not_yet_available=not eligible.loc[:'2018-12-28'].any()))
  ap=Path(recs[sid]['adjustment']['actions']['path']);note(ap);a=json.loads(ap.read_text());ev=[x for x in a.get('events',[]) if '2019-01-01'<=x['effective_date']<='2023-12-29'];actions.append(dict(sector=sec,symbol=sid,events=len(ev),pay_dates_unknown=sum(float(e.get('cash_per_old_share',0))!=0 and not e.get('paid_at') for e in ev),sellable_dates_unknown=sum(float(e.get('split_ratio',1))!=1 and not e.get('new_shares_sellable_at') for e in ev),unresolved=len(a.get('unresolved',[])),exact_pay_dates_certified=a.get('exact_pay_dates_certified',False)))
 for year in range(2019,2024):
  calyear=market_days[market_days.year==year];last=calyear[-1];ys=[];js=[]
  for sid,(pv,jt,ipo) in cols.items():
   ys.append(bool(pv.reindex(calyear,fill_value=False).any()));js.append(bool(jt.reindex(calyear,fill_value=False).any()))
  annual.append(dict(sector=sec,year=year,roster=len(ro),market_days=len(calyear),stocks_with_PV=sum(ys),stocks_with_joint_E0_G1_H1=sum(js),joint_stock_days=sum(int(jt.reindex(calyear,fill_value=False).sum()) for pv,jt,ipo in cols.values()),IPO_date_unknown=sum(pd.isna(ipo) for pv,jt,ipo in cols.values())))
 for sid in sorted(set(ro.sector_id)):
  fp=prep/'facts'/f'{sid}.parquet';sp=prep/'signals'/f'{sid}.parquet';note(fp);note(sp);f=pd.read_parquet(fp);raw=pd.read_parquet(sp);q=f.reindex(all_dates);known=q.e0_ready.fillna(False).astype(bool)&q.e0_target.notna();industries.append(dict(sector=sec,industry=sid,first_source=str(raw.index.min().date()),decision_days=len(all_dates),E0_ready=int(known.sum()),E0_unknown=int((~known).sum()),first_ready_in_window=str(q.index[known][0].date()) if known.any() else None,source_rows=int(raw.index.isin(all_dates).sum()),valid_PV_rows=int((raw.reindex(all_dates).price_eligible&raw.reindex(all_dates).volume_eligible&~raw.reindex(all_dates).source_invalid).sum())))
export('ANNUAL_DATA_COVERAGE.csv',annual);export('INDUSTRY_COVERAGE.csv',industries);export('BENCHMARK_COVERAGE.csv',bench);export('WARMUP_BY_STOCK.csv',warm);export('ACTIONS_COVERAGE.csv',actions);save('INPUT_IDENTITY.json',inputs);save('DATA_GATE.json',dict(passed=True,first_decision='2018-12-28',first_execution='2019-01-02',end='2023-12-29',market_days=len(market_days),decision_days=len(all_dates),reconstructed_market_and_2021_prefix=True,new_indicator_recalculation=False,industry_unknown_retained=[x for x in industries if x['E0_unknown']],annual=annual,seconds=time.monotonic()-T));print('DATA_GATE_PASS',time.monotonic()-T,json.dumps(annual,ensure_ascii=False),flush=True)
