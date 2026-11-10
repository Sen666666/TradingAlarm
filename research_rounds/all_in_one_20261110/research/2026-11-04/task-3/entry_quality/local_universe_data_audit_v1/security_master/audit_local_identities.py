"""Bounded local table/metadata audit; no network, refresh, model or Account."""
from pathlib import Path
from collections import Counter
import json,hashlib
import pandas as pd
import pyarrow.parquet as pq

O=Path(__file__).resolve().parent;EQ=O.parents[1]
M=Path('/Users/bytedance/repos/my-quant')
T=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research')
C=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022')
sources={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def bind(p):p=Path(p);sources[str(p)]=sha(p);return p
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def jsonread(p):return json.loads(bind(p).read_text())
def csv(p):return pd.read_csv(bind(p))
def ranges(s):
 x=pd.to_datetime(s,errors='coerce').dropna()
 return dict(non_null=len(x),min=None if x.empty else str(x.min().date()),max=None if x.empty else str(x.max().date()))
S=pd.read_parquet(bind(M/'data/processed/securities/securities.parquet'))
bars=csv(EQ/'local_universe_data_audit_v1/bars/BAR_SYMBOL_COVERAGE.csv')
Bset=set(bars.symbol);Sset=set(S.symbol)
X=csv(T/'results/stock-data-audit/master-crosswalk.csv');R=X[X.retired].copy();Rset=set(R.symbol)
rawmaster=jsonread(T/'data/baostock-master.json')
collection=jsonread(T/'results/stock-data-audit/ths-retired-collection.json')
dl={sid:r for sid,r in collection['records'].items()if r['status']=='downloaded'}
rawcheck=[]
for sid,r in dl.items():
 p=T/'data/ths-raw'/(r['ths_symbol']+'.json')
 rawcheck.append(dict(symbol=sid,ths_symbol=r['ths_symbol'],payload_path=str(p),exists=p.is_file(),bytes=p.stat().st_size if p.is_file()else None,
  download_reported_rows=r['rows'],download_first_observation=r['first'],download_last_observation=r['last'],master_out_date=r['master_out_date'],canonical_has_symbol=sid in Bset,
  quality='PAYLOAD_EXISTENCE_ONLY_NO_PER_STOCK_NUMERIC_OR_CA_VERIFICATION'))
save('ALL239_DOWNLOADED_PAYLOAD_EXISTENCE.json',rawcheck)
R['myquant_security_master_has_symbol']=R.symbol.isin(Sset)
R['myquant_canonical_has_symbol']=R.symbol.isin(Bset)
R['ths_downloaded_record']=R.symbol.isin(dl)
R=R.merge(bars,on='symbol',how='left',validate='one_to_one')
R.to_csv(O/'ALL339_PROVIDER_RETIRED_JOIN_CANONICAL.csv',index=False)

master=csv(C/'audit-a/prepared-current-master-v1/master-input.csv');current=set(master.symbol)
prepared=csv(C/'audit-a/prepared-current-master-v1/coverage.csv')
prep_summary=jsonread(C/'audit-a/prepared-current-master-v1/summary.json')
qroot=C/'downloads/a-tail-queue-01';qsummary=jsonread(qroot/'queue-summary.json');state=jsonread(qroot/'queue-state.json')
lookup=dict(zip(master.ths_symbol,master.symbol));checkpoints=[];cp_sources={}
for batch,meta in sorted(state['batches'].items()):
 d=Path(meta['output'])
 for path in sorted((d/'checkpoints').glob('*.json')):
  cp=jsonread(path);pages=cp.get('pages',[])
  first=min((p['first_raw']for p in pages if p.get('first_raw')),default=None)
  last=max((p['last_raw']for p in pages if p.get('last_raw')),default=None)
  sid=lookup.get(cp['symbol'])
  checkpoints.append(dict(batch=batch,batch_status=meta['status'],symbol=sid,ths_symbol=cp['symbol'],history_status=cp.get('history_status'),
   checkpoint_path=str(path),history_path=str(d/'history'/(cp['symbol']+'.json')),
   history_file_exists=(d/'history'/(cp['symbol']+'.json')).is_file(),first_raw=first,last_raw=last,
   decoded_records=sum(p.get('decoded_records',0)for p in pages),updated_at=cp.get('updated_at'),
   range_brackets_2026May18_Jun30=bool(cp.get('history_status')=='complete'and first and first<='20260518'and last and last>='20260630'),
   range_only_not_calendar_completeness=True))
assert len(checkpoints)<=5600
save('A_TAIL_QUEUE_METADATA_INDEX.json',checkpoints)
complete={r['symbol']for r in checkpoints if r['history_status']=='complete'and r['history_file_exists']and r['symbol']}
bracket={r['symbol']for r in checkpoints if r['range_brackets_2026May18_Jun30']and r['history_file_exists']and r['symbol']}
prepared_bracket=set(prepared.loc[(prepared['first']<='2026-05-18')&(prepared['last']>='2026-06-30'),'symbol'])
samples=[]
for sid in ['000001.SZ','300666.SZ','603061.SH']:
 cand=[r for r in checkpoints if r['symbol']==sid and r['history_status']=='complete'and r['history_file_exists']]
 if not cand:
  sample=dict(symbol=sid,status='NO_COMPLETE_QUEUE_PAYLOAD_IN_SAVED_METADATA')
  fallback=C/'audit-a/prepared-current-master-v1/bars'/(sid+'.parquet')
  if sid=='000001.SZ'and fallback.is_file():
   f=pd.read_parquet(bind(fallback));dates=pd.to_datetime(f.trade_date).dt.strftime('%Y-%m-%d')
   w=f[(dates>='2026-05-18')&(dates<='2026-06-30')]
   sample['fallback_prepared_payload']=dict(path=str(fallback),rows=len(f),May18_Jun30_rows=len(w),has_May18=bool((dates=='2026-05-18').any()),has_Jun30=bool((dates=='2026-06-30').any()),first_window_observation=w.head(1).to_dict('records'),last_window_observation=w.tail(1).to_dict('records'),source='Existing old merged prepared cache, not a queue record')
  samples.append(sample);continue
 r=cand[0];j=jsonread(r['history_path']);rows=j['bars'];dates=[x['date']for x in rows]
 window=[x for x in rows if'2026-05-18'<=x['date']<='2026-06-30']
 samples.append(dict(symbol=sid,payload_path=r['history_path'],history_status=j['history_status'],rows=len(rows),first=dates[0]if dates else None,last=dates[-1]if dates else None,
  May18_Jun30_rows=len(window),has_May18='2026-05-18'in dates,has_Jun30='2026-06-30'in dates,
  first_window_row=window[:1],last_window_row=window[-1:],account_ready=j.get('account_ready'),volume_unit=j.get('volume_unit'),adjustment=j.get('adjustment')))
save('THREE_FIXED_ACTUAL_PAYLOAD_EXAMPLES.json',samples)

master_summary=dict(path=str(M/'data/processed/securities/securities.parquet'),rows=len(S),unique_symbols=S.symbol.nunique(),schema=str(pq.ParquetFile(M/'data/processed/securities/securities.parquet').schema_arrow),
 non_null={k:int(v)for k,v in S.notna().sum().items()},exchange_counts=S.exchange.value_counts().to_dict(),market_counts=S.market.value_counts().to_dict(),source_counts=S.source.value_counts().to_dict(),
 list_date=ranges(S.list_date),delist_date=ranges(S.delist_date),available_at_field_present='available_at'in S,board_field_present='board'in S,
 run_manifest=jsonread(M/'data/meta/runs/securities_securities_a_share_code_names_20260518.json'))
save('MYQUANT_SECURITY_MASTER_CONTENT.json',master_summary)
cross_summary=dict(path=str(T/'results/stock-data-audit/master-crosswalk.csv'),rows=len(X),unique_symbols=X.symbol.nunique(),columns=X.columns.tolist(),
 ipoDate=ranges(X.ipoDate),outDate=ranges(X.outDate),status_counts=X.status.value_counts().to_dict(),exchange_counts=X.symbol.str[-2:].value_counts().to_dict(),type_counts=X.type.value_counts().to_dict(),
 raw_source=str(T/'data/baostock-master.json'),raw_rows=len(rawmaster['rows']),raw_fetched_at=rawmaster['fetched_at'],raw_source_limit=rawmaster['limitations'],
 row_available_at_present='available_at'in X,board_field_present='board'in X,
 outDate_after_fetch_calendar_day=X[X.outDate.fillna('')>'2026-10-18'][['symbol','code_name','outDate','status']].to_dict('records'),
 retired339_in_canonical=len(Rset&Bset),retired339_not_in_canonical=len(Rset-Bset),retired339_in_myquant_security_master=len(Rset&Sset),
 examples_covered=R[R.myquant_canonical_has_symbol].head(6).fillna('').to_dict('records'),examples_uncovered=R[~R.myquant_canonical_has_symbol].head(6).fillna('').to_dict('records'))
save('PROVIDER_HISTORICAL_IDENTITY_AND_RETIRED_COVERAGE.json',cross_summary)
summary=dict(status='BOUNDED_LOCAL_IDENTITY_AND_CACHE_METADATA_AUDIT_COMPLETE',
 canonical_symbols=len(Bset),myquant_security_symbols=len(Sset),provider_SH_SZ_Ashare_symbols=len(X),provider_retired=len(Rset),provider_retired_canonical_overlap=len(Rset&Bset),
 ths_retired_download_status_counts=dict(Counter(x['status']for x in collection['records'].values())),downloaded239_actual_payloads_exist=sum(r['exists']for r in rawcheck),
 downloaded239_canonical_overlap=len(set(dl)&Bset),canonical_union_downloaded_identity_symbols=len(Bset|set(dl)),canonical_union_current5576_identity_symbols=len(Bset|current),
 current5576_canonical_overlap=len(current&Bset),current5576_not_canonical=len(current-Bset),canonical_not_current5576=len(Bset-current),
 canonical_union_current_and_provider_retired_symbols=len(Bset|current|Rset),
 current_master=dict(rows=len(master),exchange_counts=master.exchange.value_counts().to_dict(),observed_at_counts=master.observed_at.value_counts().to_dict(),snapshot_date_counts=master.snapshot_date.value_counts().to_dict(),
  security_type_counts=master.security_type.value_counts().to_dict(),list_date_field_present='list_date'in master,delist_date_field_present='delist_date'in master),
 prepared_summary=prep_summary,prepared_last_date_counts=prepared['last'].fillna('MISSING').value_counts().to_dict(),
 queue_summary=qsummary,queue_checkpoint_rows=len(checkpoints),queue_history_status_counts=dict(Counter(r['history_status']for r in checkpoints)),
 queue_complete_payload_unique_symbols=len(complete),queue_complete_range_brackets_May18_Jun30_unique_symbols=len(bracket),
 existing_prepared_range_brackets_May18_Jun30=len(prepared_bracket),union_prepared_plus_queue_range_brackets_May18_Jun30=len(prepared_bracket|bracket),
 range_counts_not_certified_continuous_session_coverage=True,queue_complete_payloads_require_merge_validation=len(complete),
 final_full_pool_merge_status='No completed finalizer receipt in the scoped current-pool directory; exact not-merged count across other workspaces is not established.',
 samples=samples,new_network_calls=0,new_refreshes=0,new_model_or_account_runs=0,
 scope_limit='Provider-current identity snapshots plus recorded delisted identities, not complete historical PIT universe; download status/payload existence not per-stock numeric/corporate-action quality.',source_sha256=sources)
save('AUDIT_RECEIPT.json',summary)
print(json.dumps({k:v for k,v in summary.items()if k not in ['source_sha256','samples','current_master']},ensure_ascii=False,default=str))
