"""Frozen raw chart selection and input audit. No strategy calculation."""
from sa_common import *
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CASES={
 'TECH': [('688498.SH','2025-09-01','2026-03-01'),('688048.SH','2025-09-01','2026-03-01'),('002987.SZ','2025-06-01','2025-12-01'),('300502.SZ','2026-03-01','2026-10-27'),('002439.SZ','2024-01-01','2024-07-01'),('688041.SH','2026-03-01','2026-10-27')],
 'DRUG': [(s,'2024-01-01','2026-10-27') for s in ['600276.SH','688235.SH','688180.SH','300347.SZ','600566.SH','000661.SZ']],
}

def audit():
 records=[];excluded=[];issues=[];counts={};hashes={}
 for group,prep in PREPS.items():
  manifest=read(prep/'manifest.json');hashes[str(prep/'manifest.json')]=sha(prep/'manifest.json')
  byid={r['series_id']:r for r in manifest['series']}
  expected={r['symbol']:r['sha256'] for r in manifest.get('facts',[])}
  if group=='DRUG':
   old=read(ROOT/'research_rounds/innovative-drug-sfw3-20261028/signal-validation.json')
   expected={r['symbol']:r['facts_hash'] for r in old['records']}
  rows_count=0;group_excluded=0
  for sid in pool(group).symbol:
   signal_path=prep/'signals'/f'{sid}.parquet';facts_path=prep/'facts'/f'{sid}.parquet'
   f=pd.read_parquet(signal_path);facts=pd.read_parquet(facts_path);rec=byid[sid]
   errors=[]
   if not f.index.is_unique or not f.index.is_monotonic_increasing or f.index.hasnans:errors.append('signal_index')
   if not facts.index.is_unique or not facts.index.is_monotonic_increasing or facts.index.hasnans:errors.append('facts_index')
   if len(facts.index.difference(f.index)):errors.append('facts_not_in_signal')
   diff=f.loc[f.index.difference(facts.index)]
   for day,r in diff.iterrows():
    ok=bool(r.synthetic_event_bar) and r.observed_bar is not None and not bool(r.observed_bar) and pd.isna(r.amount)
    excluded.append(dict(group=group,symbol=sid,date=str(day.date()),explicit_synthetic_non_observation=ok))
    if not ok:errors.append('excluded_row_not_explicit_synthetic')
   g=f.reindex(facts.index)
   if not (np.isfinite(g[['close','amount']]).all().all() and g[['close','amount']].gt(0).all().all()):errors.append('invalid_observed_close_or_amount')
   if set(g.amount_unit.dropna())!={'CNY'} or g.amount_unit.isna().any():errors.append('amount_not_CNY')
   if not g.observed_bar.astype(bool).all() or g.synthetic_event_bar.astype(bool).any():errors.append('facts_not_observed')
   if not g.segment_id.equals(facts.segment_id):errors.append('segment_mismatch')
   blocks=g.segment_id.loc[g.segment_id.ne(g.segment_id.shift())]
   if blocks.duplicated().any() or g.segment_id.isna().any():errors.append('invalid_segment')
   if ((g.high < g[['open','close']].max(axis=1)) | (g.low > g[['open','close']].min(axis=1)) | (g.high<g.low)).any():errors.append('invalid_OHLC')
   if (g.index>pd.Timestamp(END)).any():errors.append('beyond_frozen_end')
   raw=Path(rec['raw']['path']);rh=sha(raw)
   if rh!=rec['raw']['sha256']:errors.append('raw_hash_mismatch')
   hashes[str(raw)]=rh
   action=rec.get('adjustment',{}).get('actions')
   if action:
    ah=sha(action['path']);hashes[action['path']]=ah
    if ah!=action['sha256']:errors.append('action_hash_mismatch')
   fh=sha(facts_path)
   if sid not in expected or fh!=expected[sid]:errors.append('facts_hash_mismatch')
   row=dict(group=group,symbol=sid,signal_rows=len(f),facts_rows=len(g),excluded_synthetic_rows=len(diff),
            first=str(g.index[0].date()),last=str(g.index[-1].date()),observations_2024=int((g.index>=pd.Timestamp('2024-01-01')).sum()),
            signal_sha256=sha(signal_path),facts_sha256=fh,raw_sha256=rh,errors=errors)
   records.append(row);rows_count+=len(g);group_excluded+=len(diff)
   if errors:issues.append(row)
  counts[group]=dict(stocks=len(pool(group)),observed_rows=rows_count,excluded_synthetic_rows=group_excluded)
  hashes[str(POOLS[group])]=sha(POOLS[group])
 result=dict(passed=not issues,stocks=len(records),groups=counts,records=records,excluded_rows=excluded,
             issues=issues,raw_and_action_hashes=hashes,
             clock='Exactly signals.reindex(facts.index), matching both original S preparations; only explicit synthetic non-observation bridge rows excluded',
             downloads=0,new_signal_calculations=0,accounts=0)
 save(O/'data-validation.json',result)
 if issues:raise RuntimeError(f'Input validation failed for {len(issues)} stocks; see data-validation.json')
 return result

def graphs():
 out=O/'raw';out.mkdir(exist_ok=False)
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 metadata=[]
 for group,cases in CASES.items():
  prep=PREPS[group];names=pool(group).set_index('symbol')['name']
  fig,axs=plt.subplots(4,3,figsize=(18,12),gridspec_kw={'height_ratios':[3,1,3,1]})
  for k,(sid,start,end) in enumerate(cases):
   full=pd.read_parquet(prep/'signals'/f'{sid}.parquet')
   facts=pd.read_parquet(prep/'facts'/f'{sid}.parquet')
   f=full.reindex(facts.index).loc[start:end];assert len(f)
   i,j=2*(k//3),k%3;ax=axs[i,j]
   ax.plot(f.index,f.close,c='#253747',lw=1)
   ax.fill_between(f.index,f.low,f.high,color='#99a7b5',alpha=.35)
   ax.set_title(f'{names.loc[sid]} {sid}',fontsize=11);ax.set_ylabel('因果复权价格')
   color=np.where(f.close.ge(f.close.shift()),'#c65353','#318579')
   axs[i+1,j].bar(f.index,f.amount/1e8,color=color,width=1.5)
   axs[i+1,j].set_ylabel('实际成交额/亿元')
   for a in [ax,axs[i+1,j]]:a.tick_params(axis='x',rotation=25,labelsize=7);a.grid(alpha=.18)
   metadata.append(dict(group=group,symbol=sid,name=names.loc[sid],start=start,end=end,observations=len(f)))
  fig.suptitle(('科技' if group=='TECH' else '创新药')+'｜固定原始量价窗：收盘线/高低价范围＋实际金额；无算法信号',fontsize=15)
  fig.tight_layout(rect=(0,0,1,.97));fig.savefig(out/f'{group.lower()}-raw.png',dpi=125);plt.close(fig)
 save(out/'cases.json',{'selection':'Same prior raw windows, fixed before new signal or account results','cases':metadata,'source_clock':'facts.index; synthetic corporate-action bridge rows are not trading observations','images':[str(out/'tech-raw.png'),str(out/'drug-raw.png')]})

if __name__=='__main__':
 result=audit();graphs();print(json.dumps({'passed':result['passed'],'groups':result['groups']},ensure_ascii=False))
