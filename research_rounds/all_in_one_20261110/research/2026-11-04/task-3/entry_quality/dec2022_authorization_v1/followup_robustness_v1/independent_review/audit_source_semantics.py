"""Second-person read-only source/clock/value audit; no account or model run."""
from pathlib import Path
from collections import Counter
import hashlib,json,gzip,pickle,time
import numpy as np,pandas as pd

F=Path(__file__).resolve().parents[1];S=F/'source_semantics';H=F.parent;T=H.parent/'trend_exit_controls_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024')
IDX=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018')
OUT=Path(__file__).with_name('SOURCE_SEMANTICS_AUDIT.json');SRC={}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def read(p):
 p=Path(p);SRC[str(p)]=sha(p);return json.loads(p.read_text())
def pos(x):
 a=np.asarray(x,float);return dict(rows=len(a),nan=int(np.isnan(a).sum()),inf=int(np.isinf(a).sum()),nonpositive=int((np.isfinite(a)&(a<=0)).sum()),zero=int((a==0).sum()))
def cache(mp):
 m=read(mp);p=Path(m['data_file']);assert sha(p)==m['data_sha256'];SRC[str(p)]=sha(p)
 with gzip.open(p,'rb')as f:return pickle.load(f)

def main():
 start=time.monotonic();assert not OUT.exists(),'Preserve independent receipt'
 names=['VALIDATION','CLASSIFICATION_PIT_EVIDENCE','INDUSTRY_PRICE_CHAIN','BENCHMARK_PROVENANCE','VALUE_DOMAIN_AND_CONTEXT_COUNTS','CORPORATE_ACTION_SCOPE','ACTUAL_EDGE_EXAMPLES','SOURCE_SHA256']
 claims={n:read(S/(n+'.json'))for n in names};assert claims['VALIDATION']['passed']
 bindings=claims['SOURCE_SHA256'];bad=[]
 for p,h in bindings.items():
  if sha(p)!=h:bad.append(p)
 assert not bad,bad
 sm=read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json');im=read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
 meta=read(OLD/'inputs-v2/metadata.json');selection=read(OLD/'inputs-v2/selection.json');inputs=read(OLD/'inputs-v2/input-manifest.json');rec={x['series_id']:x for x in inputs['series']}
 cp=claims['CLASSIFICATION_PIT_EVIDENCE'];assert cp['selection']=={k:selection[k]for k in cp['selection']}
 master=Path(selection['industry_resolution_evidence']['path']);assert sha(master)==selection['industry_resolution_evidence']['sha256']
 df=pd.read_csv(master,dtype={'symbol':str});assert not df.symbol.duplicated().any();lookup=df.set_index('symbol')
 for m in sm:assert meta[m['symbol']]['sector_id']==lookup.loc[m['symbol'],'industry_index_symbol']
 assert cp['historical_membership_intervals_proven'] is False and cp['historical_index_constituents_or_weights_proven'] is False
 assert set(cp['master_columns'])==set(df.columns)
 assert not any('valid_from' in x or 'effective_from' in x or 'weight' in x for x in df.columns)
 assert 'not PIT' in selection['universe_limit']
 ck=read(IDX/'checkpoints/USZI399300.json');price=IDX/'canonical/USZI399300.csv';assert sha(price)==ck['canonical_sha256'];SRC[str(price)]=sha(price)
 market=pd.read_csv(price,index_col=0,parse_dates=True);assert market.index.is_unique and market.index.is_monotonic_increasing
 server=read(IDX/'server-names.json');protocol=read(IDX/'protocol.json')
 assert server['USZI']['names']['USZI399300']=='沪深300'
 assert any(x.get('symbol')=='USZI399300' and x.get('probe_name')=='沪深300(深市代码)' for x in protocol['symbols'])
 assert ck['symbol']=='USZI399300' and len(ck['pages'])==8 and len(market)==5288
 for p in ck['pages']:assert sha(IDX/p['file'])==p['body_sha256']
 bm=claims['BENCHMARK_PROVENANCE'];assert bm['rows']==len(market) and bm['download_received_at']==sorted({p['received_at']for p in ck['pages']})
 assert not any('publish' in x or 'revision' in x for x in market.columns)
 assert pos(market.close)==dict(rows=5288,nan=0,inf=0,nonpositive=0,zero=0)
 anchor=pd.Series(market.index,index=market.index).shift(20);mret=market.close/market.close.shift(20)-1
 ctx=cache(H/'relative_context/MANIFEST.json');indicators=cache(T/'indicators/MANIFEST.json')
 inds={};ic=Counter()
 for m in im:
  p=Path(next(p for p in m['source_sha256']if '/industry-facts/'in p));g=pd.read_parquet(p,columns=['close','factor','segment_id']);inds[m['series']]=g
  assert all(pos(g.close)[k]==0 for k in ['nan','inf','nonpositive','zero']);assert (g.factor==1).all()
  ic['facts_close_rows']+=len(g);ic['series']+=1
  r=rec[m['series']];assert r['kind']=='sector_index' and r['adjustment']['method']=='unadjusted_index'
  raw=pd.read_parquet(r['raw']['path']);ic['raw_source_invalid']+=int(raw.source_invalid.sum());ic['raw_rows']+=len(raw)
  assert not any('weight' in x or 'constituent' in x or 'effective' in x for x in raw.columns)
  assert all(pos(raw.close)[k]==0 for k in ['nan','inf','nonpositive','zero'])
 sc=Counter();ac=Counter();rc=Counter();emax=0.;gmax=0.;emadiff=0.
 for j,m in enumerate(sm):
  sid=m['symbol'];f=pd.read_parquet(m['refs']['facts'],columns=['close','raw_close','factor','segment_id']);sc['fixed_symbols']+=1;sc['empty_fact_symbols']+=f.empty;sc['close_rows']+=len(f)
  for k in ['close','raw_close','factor']:
   q=pos(f[k]);assert all(q[z]==0 for z in ['nan','inf','nonpositive','zero']),(sid,k,q)
  if len(f):emax=max(emax,float(np.abs(f.close-f.raw_close*f.factor).max()));assert np.allclose(f.close,f.raw_close*f.factor,rtol=1e-10,atol=1e-10)
  p=next(p for p in m['source_sha256']if p.endswith('/signal.parquet'));sf=pd.read_parquet(p,columns=['close','raw_close','volume','segment_id','price_eligible','observed_bar','source_invalid','synthetic_event_bar']).loc[:'2026-06-30']
  syn=sf.synthetic_event_bar.eq(True);eligible=sf.price_eligible.eq(True)&sf.observed_bar.eq(True)&sf.source_invalid.eq(False)&~syn
  sc['prepared_source_rows_through_Jun30']+=len(sf);sc['synthetic']+=int(syn.sum());sc['eligible']+=int(eligible.sum());sc['synthetic_raw_price_missing']+=int(sf.loc[syn,'raw_close'].isna().sum());sc['synthetic_volume_missing']+=int(sf.loc[syn,'volume'].isna().sum())
  ff=f.loc[:'2026-06-30'];assert ff.index.equals(sf.index[eligible]);assert not sf.loc[ff.index,'synthetic_event_bar'].any();sc['facts_through_Jun30']+=len(ff);sc['facts_after_Jun30']+=len(f)-len(ff)
  # Independent scalar EMA recursion over source observations, reset on segment.
  ema=np.full(len(ff),np.nan);state=None;n=0;oldseg=None
  for k,(c,seg)in enumerate(zip(ff.close.to_numpy(float),ff.segment_id.to_numpy(float))):
   if oldseg is None or seg!=oldseg:state=None;n=0;oldseg=seg
   state=c if state is None else (2/21)*c+(19/21)*state;n+=1
   if n>=20:ema[k]=state
  r=ctx[sid];dates=pd.DatetimeIndex(r['days'].astype('datetime64[D]'));ea=pd.Series(ema,index=ff.index).reindex(dates).to_numpy(float)
  assert np.array_equal(np.isfinite(ea),r['ready_P'])
  if np.isfinite(ea).any():emadiff=max(emadiff,float(np.nanmax(np.abs(ea-r['EMA20']))));assert np.allclose(ea,r['EMA20'],rtol=1e-11,atol=1e-10,equal_nan=True)
  aa=pd.DatetimeIndex(anchor.reindex(dates).to_numpy());s0=f.reindex(aa);s1=f.reindex(dates);g=inds[meta[sid]['sector_id']];i0=g.reindex(aa);i1=g.reindex(dates)
  a,b,c,d=[v.close.to_numpy(float)for v in [s1,s0,i1,i0]];mr=mret.reindex(dates).to_numpy(float)
  ready=(np.isfinite(a)&np.isfinite(b)&np.isfinite(c)&np.isfinite(d)&np.isfinite(mr)&(a>0)&(b>0)&(c>0)&(d>0)&(s1.segment_id.to_numpy()==s0.segment_id.to_numpy())&(i1.segment_id.to_numpy()==i0.segment_id.to_numpy()))
  assert np.array_equal(ready,r['ready_R']);rs=a[ready]/b[ready]-1-np.maximum(c[ready]/d[ready]-1,mr[ready]);assert np.allclose(rs,r['RS20'][ready],rtol=1e-12,atol=1e-12)
  fac=s1.factor.to_numpy(float)/s0.factor.to_numpy(float);rawg=s1.raw_close.to_numpy(float)/s0.raw_close.to_numpy(float)*fac
  if ready.any():gmax=max(gmax,float(np.max(np.abs(rawg[ready]-(1+r['stock_return20'][ready])))))
  rc['rows']+=len(dates);rc['ready_R']+=int(ready.sum());rc['unknown_R']+=int((~ready).sum());rc['ready_P']+=int(np.isfinite(ea).sum());rc['unknown_P']+=int((~np.isfinite(ea)).sum());rc['factor_cross']+=int((ready&~np.isclose(fac,1,rtol=1e-12,atol=1e-12)).sum())
  acts=read(rec[sid]['adjustment']['actions']['path']);ac['files']+=1;ac['certified_pay_files']+=bool(acts.get('exact_pay_dates_certified'));ac['proxy_files']+=acts.get('status')=='declared_research_proxy'
  for e in acts['events']:
   if e['effective_date']<='2026-06-30':ac['events']+=1;ac['paid_at_unknown']+=e.get('paid_at')is None;ac[e['classification']]+=1
  if (j+1)%500==0:print('INDEPENDENT_SOURCE',j+1,flush=True)
 counts=claims['VALUE_DOMAIN_AND_CONTEXT_COUNTS'];scl=counts['stock'];rcl=counts['relative_context']
 for k in ['fixed_symbols','empty_fact_symbols','close_rows','prepared_source_rows_through_Jun30']:assert sc[k]==scl[k]
 assert sc['synthetic']==scl['prepared_synthetic_event_bar_true']==334 and sc['eligible']==sc['facts_through_Jun30']==4049565
 assert sc['synthetic_raw_price_missing']==sc['synthetic_volume_missing']==334
 for k in ['rows','ready_R','unknown_R','ready_P','unknown_P']:assert rc[k]==rcl[k]
 assert rc['factor_cross']==rcl['ready_R_windows_crossing_factor_change']==140440
 assert ic['facts_close_rows']==counts['industry']['facts_close_rows']==364796 and ic['raw_source_invalid']==14
 ca=claims['CORPORATE_ACTION_SCOPE'];assert ac['files']==ca['stock_action_files']==1709 and ac['events']==ca['events_through_Jun30']==15892
 assert ac['certified_pay_files']==0 and ac['proxy_files']==1709 and ac['paid_at_unknown']==15892
 for k in ['ordinary_cash_and_pro_rata_bonus','rights_issue_no_subscription','targeted_non_pro_rata_issuance','public_holder_consideration_share_proxy']:assert ac[k]==ca['classification_'+k]
 SRC[str(Path(__file__))]=sha(__file__)
 result=dict(status='PASS_WITH_EXPLICIT_POINT_IN_TIME_AND_EXECUTION_LIMITS',new_financial_accounts=0,new_account_events=0,reported_source_bindings_verified=len(bindings),classification_mapping_symbols_checked=len(sm),stock_counts=dict(sc),industry_counts=dict(ic),relative_counts=dict(rc),action_counts=dict(ac),maximum_close_raw_factor_error=emax,maximum_adjusted_raw_return_factor_error=gmax,maximum_independent_scalar_EMA20_error=emadiff,benchmark_symbol=ck['symbol'],benchmark_identity_evidence=[str(IDX/'server-names.json'),str(IDX/'protocol.json')],input_PIT_proven=False,historical_industry_constituents_weights_proven=False,historical_15_10_index_release_or_revision_proven=False,zero_division_scope='Current frozen prices positive. Stock and industry endpoints explicitly guarded; benchmark producer only requires finite return, not positive raw endpoint. This audit does not certify arbitrary malformed future benchmark input.',suspension_scope='Missing exact endpoints are UNKNOWN and not forward-filled; price bars alone do not distinguish suspension from source gaps.',adjustment_scope='Prefix-causal signal price=raw_price*factor; synthetic action bars excluded from observations. This is not shareholder total return, and all action paid_at are unknown research proxies.',claims_receipts={n:str(S/(n+'.json'))for n in names},source_bindings=SRC,seconds=time.monotonic()-start)
 with OUT.open('x')as f:json.dump(result,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
 print(json.dumps({k:result[k]for k in ['status','reported_source_bindings_verified','classification_mapping_symbols_checked','maximum_independent_scalar_EMA20_error','new_financial_accounts','seconds']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
