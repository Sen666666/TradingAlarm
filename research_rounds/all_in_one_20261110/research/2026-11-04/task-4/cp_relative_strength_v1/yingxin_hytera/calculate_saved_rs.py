"""Pure reads/scalar log ratios of saved original prices. No native imports/models/accounts."""
from pathlib import Path
import pandas as pd, math, json, hashlib
OUT=Path(__file__).resolve().parent
BASE=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
IM=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/input-manifest.json')
MARKET=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
SM={x['symbol']:x for x in json.loads((BASE/'STOCK_MANIFEST.json').read_text())}
GM={x['series']:x for x in json.loads((BASE/'INDUSTRY_MANIFEST.json').read_text())}
SER={x['series_id']:x for x in json.loads(IM.read_text())['series']}
CASES={'000620.SZ':{'industry':'URFI881153','industry_name':'房地产','start':'2022-01-04','end':'2022-02-08','keys':['2022-01-20','2022-01-21','2022-01-24','2022-01-25']},'002583.SZ':{'industry':'URFI881129','industry_name':'通信设备','start':'2024-09-23','end':'2024-11-27','keys':['2024-09-24','2024-09-30','2024-10-11','2024-10-18']}}
sources={};details={};allrows=[];keyrows=[]
def sha(p):
 p=Path(p);sources[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest();return sources[str(p)]
def table(p):
 sha(p);d=pd.read_parquet(p).copy();d.index=pd.to_datetime(d.index).normalize();assert d.index.is_unique;return d.sort_index()
m=pd.read_csv(MARKET,parse_dates=['date']).set_index('date');sha(MARKET);assert m.index.is_unique
for sid,case in CASES.items():
 gid=case['industry'];ci=table(SM[sid]['refs']['CP1_input']);cp=table(SM[sid]['refs']['CP1']);f=table(SM[sid]['refs']['facts']);i=table(GM[gid]['refs']['CP1_input']);rawi=table(SER[gid]['raw']['path'])
 print(gid,'rawcols',list(rawi.columns),'price_difference_max',float((i['close']-rawi['close'].reindex(i.index)).abs().max()))
 relevant=cp.loc[case['start']:case['end']];signal_dates=relevant.index[relevant.receipt.astype(bool)].tolist()
 selected=sorted(set(signal_dates+[pd.Timestamp(x) for x in case['keys']]))
 for t in selected:
  for h in [5,20,60]:
   r={'sid':sid,'industry_symbol':gid,'industry_name_static_20261022':case['industry_name'],'mapping_PIT_verified':False,'market_symbol':'USHI1B0300','market_name':'沪深300','date':t.strftime('%Y-%m-%d'),'horizon_industry_observations':h,'original_CP_receipt':bool(cp.at[t,'receipt']) if t in cp.index else None,'units':'log return; percent columns = 100 * log return','missing_reasons':[]}
   if t not in i.index or i.index.get_loc(t)<h:
    r['missing_reasons'].append('industry_date_or_history_unavailable');allrows.append(r);continue
   t0=i.index[i.index.get_loc(t)-h];r['start_date']=t0.strftime('%Y-%m-%d')
   for label,d,col in [('stock_cp',ci,'close'),('stock_raw',f,'raw_close'),('stock_factor',f,'factor'),('industry',i,'close'),('market',m,'close')]:
    for end,dt in [('start',t0),('end',t)]:
     v=d.at[dt,col] if dt in d.index else None
     if v is None or pd.isna(v) or float(v)<=0:
      r[label+'_'+end]=None;r['missing_reasons'].append(label+'_'+end+'_missing_or_nonpositive')
     else:r[label+'_'+end]=float(v)
   for label in ['stock_cp','stock_raw','industry','market']:
    a,b=r[label+'_start'],r[label+'_end'];r[label+'_log_return']=math.log(b/a) if a is not None and b is not None else None
   r['stock_factor_endpoint_ratio']=r['stock_factor_end']/r['stock_factor_start'] if r['stock_factor_start'] and r['stock_factor_end'] else None
   fs=f.loc[t0:t,'factor'];r['stock_factor_observed_unique_count']=int(fs.nunique(dropna=True));r['stock_factor_constant_all_observed_interval']=bool(fs.nunique(dropna=True)==1) if len(fs) else None
   r['stock_date_present_at_both_endpoints']=bool(t0 in f.index and t in f.index)
   r['industry_raw_close_matches_original_CP_input_endpoints']=bool(t0 in rawi.index and t in rawi.index and rawi.at[t0,'close']==i.at[t0,'close'] and rawi.at[t,'close']==i.at[t,'close'])
   r['RS_stock_cp_minus_industry']=r['stock_cp_log_return']-r['industry_log_return'] if r['stock_cp_log_return'] is not None and r['industry_log_return'] is not None else None
   r['RS_stock_raw_minus_industry']=r['stock_raw_log_return']-r['industry_log_return'] if r['stock_raw_log_return'] is not None and r['industry_log_return'] is not None else None
   r['RS_industry_minus_market']=r['industry_log_return']-r['market_log_return'] if r['industry_log_return'] is not None and r['market_log_return'] is not None else None
   for name in ['RS_stock_cp_minus_industry','RS_stock_raw_minus_industry','RS_industry_minus_market']:
    r[name+'_pct_log_points']=100*r[name] if r[name] is not None else None
   r['missing_reasons']=';'.join(r['missing_reasons']);allrows.append(r)
   if r['date'] in case['keys']:keyrows.append(r)
 details[sid]={'case':case,'original_CP_dates':[x.strftime('%Y-%m-%d') for x in signal_dates],'original_CP_count':len(signal_dates),'stock_manifest_entry':SM[sid],'industry_manifest_entry':GM[gid],'original_bundle_industry_series':SER[gid],'original_bundle_stock_series':SER[sid]}
for p in [BASE/'STOCK_MANIFEST.json',BASE/'INDUSTRY_MANIFEST.json',IM,Path(__file__)]:sha(p)
for fn,rows in [('ALL_ORIGINAL_CP_RS', [x for x in allrows if x.get('original_CP_receipt')]),('REQUESTED_KEY_DATES_RS',keyrows)]:
 (OUT/(fn+'.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2,allow_nan=False)+'\n');pd.DataFrame(rows).to_csv(OUT/(fn+'.csv'),index=False)
(OUT/'SOURCE_AND_CASE_DETAILS.json').write_text(json.dumps(details,ensure_ascii=False,indent=2)+'\n')
(OUT/'SOURCE_SHA256.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2)+'\n')
print('COUNTS', {sid: x['original_CP_count'] for sid,x in details.items()},'RS_ROWS',sum(bool(x.get('original_CP_receipt')) for x in allrows))
print(pd.DataFrame(keyrows)[['sid','date','horizon_industry_observations','start_date','RS_stock_cp_minus_industry_pct_log_points','RS_industry_minus_market_pct_log_points','stock_factor_observed_unique_count','missing_reasons']].to_string(index=False))
