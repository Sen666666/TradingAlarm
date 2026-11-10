from common import *
from engine import Runner,Account,Facts,Sink,FastMarket,MODES
from run_first10 import first10_specs as original_specs
from dataclasses import replace
import copy,csv,time

def context(cutoff=None,ids=None):
 roster=list(csv.DictReader((DESIGN/'proposed-pool.csv').open()));ids=set(ids or [r['symbol'] for r in roster]);b=load_bundle(OLD/'inputs-v2/input-manifest.json');b.lines=tuple(l for l in b.lines if l.security_id in ids);sectors={l.sector_id for l in b.lines};needed=ids|sectors;records={r['series_id']:r for r in read(CORE/'manifest.json')['series']};b.series={s:v for s,v in b.series.items() if s in needed};b.sector_series={s:v for s,v in b.sector_series.items() if s in sectors}
 for sid,item in b.series.items():
  item.record=records[sid];f=pd.read_parquet(PREP/'facts'/f'{sid}.parquet');item.states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
  if cutoff:item.states=item.states.loc[:cutoff].copy()
 h1path=PREP/'h1.npz';h1path=h1path if h1path.exists() else OLD/'h1/matrix.npz';z=dict(np.load(h1path));dates=pd.DatetimeIndex(z['dates']);mask=np.ones(len(dates),bool) if not cutoff else dates<=pd.Timestamp(cutoff);b._h1_cache=(dates[mask],{str(s):j for j,s in enumerate(z['symbols'])},z['score'][mask].copy())
 rules=copy.deepcopy(read(OLD/'inputs-v2/market-rules.json'))
 rules['calendars']['A']=sorted(set(rules['calendars']['A'])|{f'2026-10-{d}T09:30:00+08:00' for d in ['27','28','29','30']})
 rules['decision_cutoffs']=sorted(set(rules['decision_cutoffs'])|{'2023-12-29T15:10:00+08:00','2026-10-23T15:10:00+08:00','2026-10-26T15:10:00+08:00'})
 m=FastMarket(b,rules,[],read(OLD/'inputs-v2/economic-protocol.json'))
 if cutoff:
  for sid,f in m.raw.items():
   m.raw[sid]=f.loc[:cutoff].copy();n=len(m.raw[sid]);a=m.arr[sid];m.arr[sid]={k:(v[v<n] if k in ['good','positive'] else v[:n] if isinstance(v,np.ndarray) else v) for k,v in a.items()}
  m.actions={s:[e for e in es if e['effective_date']<=cutoff] for s,es in m.actions.items()}
 return b,m

def benchmark(b):
 dates,col,scores=b._h1_cache;d=dates.get_indexer([pd.Timestamp('2023-12-29')])[0];sectors=list(b.sector_series)
 ordered=sorted([s for s in sectors if np.isfinite(scores[d,col[s]])],key=lambda s:(-scores[d,col[s]],s));chosen=[]
 for sector in ordered:
  ids=[l.security_id for l in b.lines if l.sector_id==sector and np.isfinite(scores[d,col[l.security_id]])]
  if len(ids)<2:continue
  chosen+=sorted(ids,key=lambda s:(-scores[d,col[s]],s))[:2]
  if len(chosen)==6:break
 assert len(chosen)==6;return chosen

def specs(modes=MODES,stresses=('base','cost2','delay1'),variant='S0'):
 return tuple(replace(s,account_id=f'{mode}__{s.account_id}') for mode in modes for s in original_specs() if s.variant==variant and s.stress.name in stresses)

def run(out,modes=MODES,stresses=('base','cost2','delay1'),start='2023-12-29',end='2026-10-26',cutoff=None,ids=None,variant='S0',protect=True,technical=True):
 b,m=context(cutoff,ids);ss=specs(modes,stresses,variant);native.first10_specs=lambda:ss;native.SectorAccount=Account;sink=Sink(out);r=Runner(b,m,start=native.iso(start+'T15:10:00+08:00'),end=native.iso(end+'T15:10:00+08:00'),sink=sink,synthetic=technical);r.facts=Facts(b,m,cutoff);r.benchmark=benchmark(b) if 'BH' in modes else []
 for aid,a in r.accounts.items():a.mode=aid.split('__')[0];a.facts=r.facts;a.market=m;a.protect=protect and a.mode!='BH'
 t=time.time()
 try:
  summary=r.run_tech();r.write(out,summary,dict(recorded_at=now(),seconds=time.time()-t,new_economic=not technical,integer_cash_share_ledger_sha256=sha(OLD/'code/sector_account.py'),benchmark=r.benchmark))
 except BaseException as e:r.write(out,dict(status='failed_partial',error=repr(e)),dict(recorded_at=now()));raise
 finally:sink.close()
 print(dict(done=True,accounts=len(ss),seconds=time.time()-t,output=str(out)),flush=True);return r

def controls():
 scope=read(ROOT/'research_rounds/sector-ix-i-20261026/scope.json');receipts=[]
 for g in ['SEMI','COMM']:
  out=HERE/'technical'/('old-controls-v2-'+g);run(out,modes=['I','IX'],stresses=['base'],start='2021-01-04',end='2021-03-31',ids=scope['groups'][g],variant='S1',protect=False)
  old=ROOT/'research_rounds/sector-ix-i-20261026/accounts-v2';fields=['available','order_reserved','settlement_locked','payable','sale_receivable','dividend_receivable','inventory','nav','fees_cny','positions','pending_buys','pending_sells']
  for mode in ['I','IX']:
   aid=mode+'__S1_base';ref=g+'_'+mode+'__S1_base';a=[x for x in rows(out/'daily.jsonl.gz') if x['account']==aid];z=[x for x in rows(old/'daily.jsonl.gz') if x['account']==ref and x['at'][:10]<='2021-03-31'];assert len(a)==len(z)>0
   for u,v in zip(a,z):
    assert u['at']==v['at']
    for k in fields:assert u[k]==v[k],(g,mode,u['at'],k,u[k],v[k])
   full=read(old/f'{ref}.json')['fills'];prefix=[x for x in full if x['at'][:10]<='2021-03-31'];new=read(out/f'{aid}.json')['fills'];assert new==prefix,(g,mode,'fills')
   receipts.append(dict(group=g,mode=mode,daily_rows=len(a),fill_rows=len(new)))
 write(HERE/'technical/old-control-identity.json',dict(passed=True,receipts=receipts,execution_protection_disabled_only_for_old_identity=True))

def main():
 mode=sys.argv[1]
 if mode=='controls':controls()
 elif mode=='short':run(HERE/'technical/short-v2',end='2024-03-29')
 elif mode=='prefix':run(HERE/'technical/prefix',stresses=['base'],end='2024-12-31',cutoff='2024-12-31')
 elif mode=='economic':
  assert read(HERE/'economic-admission.json')['passed'];files=list((HERE/'code').glob('*.py'))+[HERE/'PROTOCOL.md',HERE/'GRAPH_REVIEW.md',CORE/'manifest.json',HERE/'data/references/manifest.json',PREP/'manifest.json',PREP/'h1.npz',HERE/'economic-admission.json',HERE/'technical/old-control-identity.json']
  write(HERE/'account-freeze.json',dict(recorded_at=now(),paths=21,before_results=True,sha256={str(p.relative_to(ROOT)):sha(p) for p in files}));run(HERE/'accounts',technical=False)
 else:raise ValueError(mode)
if __name__=='__main__':main()
