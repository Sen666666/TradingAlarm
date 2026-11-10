"""One finite chronological pass, unchanged raw execution and IX targets."""
from common_abcd import *
import collections,gzip,os
sys.path.append(str(OLD/'code'))
import pandas as pd
from current_pool_bridge import load_bundle,load_prepared_states
from runner_abcd import FrozenMarket,HistoryRunner,iso,encoded
from board_abcd import Board,build
import selection_abcd as selection

class Sink:
 def __init__(self,out):
  self.out=Path(out);self.out.mkdir(parents=True,exist_ok=False)
  self.streams={k:gzip.open(self.out/f'{k}.jsonl.gz','wt',encoding='utf-8',compresslevel=1) for k in ['daily','decisions']}
 def emit(self,name,row):
  if name=='decisions':
   ack=row['ack'];first=ack.decisions[0];last=ack.decisions[-1];ids=selection.BUY.get(row['at'].date().isoformat(),set())
   row=dict(account=row['account'],at=row['at'],rotation=row['rotation'],accepted=ack.accepted,rejected=ack.rejected,eligible=tuple(x.security_id for x in first.eligibility if x.q is True),unknown_eligibility=sum(x.q is None for x in first.eligibility),reason_counts=dict(collections.Counter(reason for x in first.eligibility for reason in x.reasons)),event_eligibility=[dict(symbol=x.security_id,sector=x.sector_id,q=x.q,reasons=x.reasons) for x in first.eligibility if x.security_id in ids],first_selected=first.selected,first_rejected=first.rejected,occupancy=ack.occupancy,waiting=last.waiting,continue_buys=last.continue_buys,paused_buys=last.pause_buys,cancel_buys=last.cancel_buys,exit_requests=last.exit_requests,rejected_new=last.rejected,ranking_fallbacks=last.ranking_fallbacks)
  self.streams[name].write(json.dumps(encoded(row),ensure_ascii=False,allow_nan=False)+'\n')
 def close(self):
  for f in self.streams.values():f.close()

def context(cutoff=None):
 b=load_bundle(OLD/'inputs-v2/input-manifest.json');load_prepared_states(b,OLD/'prepared-v2');assert b.signal_ready
 buy=collections.defaultdict(set)
 for sid,item in b.series.items():
  if item.record['kind']!='stock':continue
  f=pd.read_parquet(SRC/'signals'/f'{sid}.parquet',columns=['ix_target']);assert f.index.equals(item.states.index)
  item.states=item.states.copy();item.states['target']=f.ix_target
 for sid,days in read(HERE/'prepared/buy-events.json').items():
  for day in days:
   if cutoff is None or day<=cutoff:buy[day].add(sid)
 if cutoff:
  z=dict(np.load(OLD/'h1/matrix.npz'));d=pd.DatetimeIndex(z['dates']);n=d.searchsorted(pd.Timestamp(cutoff),side='right')
  b._h1_cache=(d[:n],{s:j for j,s in enumerate(z['symbols'])},z['score'][:n])
  truncated={k:(v[:n] if k!='symbols' else v) for k,v in z.items()}
  board=Board(build(truncated,read(OLD/'inputs-v2/metadata.json')))
  for item in b.series.values():
   if item.states is not None:item.states=item.states.loc[:cutoff]
 else:board=Board(np.load(HERE/'prepared/dual-board.npz'))
 m=FrozenMarket(b,read(OLD/'inputs-v2/market-rules.json'),[],read(OLD/'inputs-v2/economic-protocol.json'))
 if cutoff:
  for sid in m.raw:m.raw[sid]=m.raw[sid].loc[:cutoff]
  for sid in m.actions:m.actions[sid]=[e for e in m.actions[sid] if e['effective_date']<=cutoff]
 selection.configure(buy,board);return b,m

def main(kind,cutoff=None):
 assert kind in ['controls','economic','prefix']
 if kind=='controls':os.environ['ABCD_MODES']='A'
 elif kind=='economic':
  os.environ['ABCD_MODES']='B,C,D';f=read(HERE/'freeze.json');verify(f['sha256']);assert read(HERE/'technical/A-controls/comparison.json')['passed']
 else:os.environ['ABCD_MODES']='A,B,C,D';os.environ['ABCD_STRESSES']='base';assert cutoff
 b,m=context(cutoff);package=read(OLD/'inputs-v2/package.json');end=iso(package['end']) if not cutoff else max(x for x in m.cutoffs if x.date().isoformat()<=cutoff)
 out=HERE/({'controls':'technical/A-controls','economic':'accounts','prefix':f'technical/prefix-{cutoff}'}[kind]);sink=Sink(out)
 r=HistoryRunner(b,m,start=iso(package['start']),end=end,sink=sink,synthetic=kind!='economic')
 provenance=dict(recorded_at=now(),technical=kind!='economic',cutoff=cutoff,accounts=[s.account_id for s in r.specs],source='same frozen A-share finance, original IX targets',code=sha(__file__))
 try:
  summary=r.run();r.write(out,summary,provenance)
 except BaseException as e:
  r.write(out,dict(status='failed_partial_run',error=type(e).__name__+':'+str(e),completed_accounts=0),provenance);raise
 finally:sink.close()
 if kind in ['controls','prefix']:
  expected={}
  sources=[SRC/'accounts'] if kind=='controls' else [HERE/'technical/A-controls',HERE/'accounts']
  for source in sources:
   with gzip.open(source/'daily.jsonl.gz','rt') as f:
    for line in f:
     x=json.loads(line);aid='A__'+x['account'].split('__',1)[1] if kind=='controls' and x['account'].startswith('IX__') else x['account']
     if aid in r.accounts and iso(x['at'])<=end:
      x['account']=aid;expected[aid,x['at']]=x
  n=0
  with gzip.open(out/'daily.jsonl.gz','rt') as f:
   for line in f:x=json.loads(line);assert x==expected.pop((x['account'],x['at'])),(x['account'],x['at']);n+=1
  assert not expected
  if kind=='controls':
   for aid in r.accounts:assert read(out/f'{aid}.json')==read(SRC/'accounts'/f'IX__{aid.split("__",1)[1]}.json'),aid
  write(out/'comparison.json',dict(recorded_at=now(),passed=True,accounts=len(r.accounts),daily_rows_exact=n,full_financial_json_exact=kind=='controls',future_states_prices_actions_removed=bool(cutoff)))
 print(dict(done=True,kind=kind,cutoff=cutoff,accounts=len(r.accounts),final_nav=summary['final_nav']),flush=True)

if __name__=='__main__':main(*sys.argv[1:])
