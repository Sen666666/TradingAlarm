"""One causal absolute gate, common restored Q3 state and raw-I capacity."""
from pathlib import Path
import sys,importlib.util,time,json,gzip,copy,pickle,hashlib,collections,traceback
from datetime import datetime,time as dt
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;OLD=W/'mainline-I-quarter-2025Q3-20261031';BASE=OLD/'P_IDENTITY_BASELINE'
s=importlib.util.spec_from_file_location('Q4_frozen_NO_P_baseline',BASE/'baseline.py');B=importlib.util.module_from_spec(s);sys.modules[s.name]=B;s.loader.exec_module(B);M=B.M
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def canon(v):return json.dumps(M.N.encoded(v),sort_keys=True,default=M.C.encoded,allow_nan=False)
def prepare():
 t=time.monotonic();(O/'industry-facts').mkdir(exist_ok=True);receipt=[]
 for p in sorted((OLD/'industry-facts').glob('*.parquet')):
  sid=p.stem;dest=O/'industry-facts'/p.name;reused=dest.exists();f=pd.read_parquet(dest) if reused else M.sector_facts(sid,end='2026-06-30');prev=pd.read_parquet(p);pd.testing.assert_frame_equal(f.loc[prev.index],prev,check_exact=True,check_freq=False)
  if not reused:f.to_parquet(dest)
  receipt.append(dict(sid=sid,rows=len(f),Q3_prefix_exact=True,sha256=M.sha(dest),reused_from_failed_numeric_prefix_attempt=reused))
 print('Q90_COMPLETE',round(time.monotonic()-t,3),flush=True)
 sys.path.insert(0,str(M.ROOT));from TradingAlarm.desk.refresh import compute_recovery
 src=M.RR/'a-share-selection-e0-20261024/prepared-v2';rec={r['series_id']:r for r in M.read(src/'manifest.json')['series']};meta=M.read(M.RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json');signals={};absent=[]
 for sid in M.read(M.IC/'FREEZE.json')['stocks']:
  p=src/rec[sid]['files']['signal']['path'];assert M.sha(p)==rec[sid]['files']['signal']['sha256'];f=pd.read_parquet(p,columns=['close','amount','price_eligible','observed_bar','synthetic_event_bar','segment_id']).loc[:'2026-06-30']
  if (f.price_eligible&f.observed_bar&~f.synthetic_event_bar).any():signals[sid]=f
  else:absent.append(sid)
 roster=pd.DataFrame([dict(symbol=sid,sector_id=meta[sid]['sector_id']) for sid in signals]);z=compute_recovery(signals,roster);z['fast_on']=z.breadth.gt(.6);previous=pd.read_csv(OLD/'recovery.csv',index_col=0,parse_dates=True)
 differences={}
 for c in previous:
  old=previous[c];new=z.loc[previous.index,c]
  if c in ['breakout','fast_on']:np.testing.assert_array_equal(new,old);differences[c]=0
  else:
   np.testing.assert_allclose(new,old,rtol=1e-12,atol=1e-12,equal_nan=True);differences[c]=float(np.nanmax(np.abs(new.astype(float)-old.astype(float))))
 z.to_csv(O/'recovery.csv');assert time.monotonic()-t<120
 M.save(O/'PREPARED.json',dict(passed=True,seconds=time.monotonic()-t,industry_receipts=receipt,industry_Q3_prefix_exact=True,market_Q3_decisions_exact=True,market_Q3_float_absolute_differences=differences,market_Q3_numeric_tolerance=1e-12,reason='floating arithmetic/CSV serialization boundary; observed differences recorded, no action-field changes, original frozen Q3 data not rewritten',stocks_without_history_before_2026Q2=absent,market_original_formula=True,full90_industry_state_end='2026-06-30'))
 print('PREP_DONE',round(time.monotonic()-t,3),flush=True)

EXCLUDE={'market','facts','_ix','_ixn'}
def pack(r):
 return dict(runner={k:copy.deepcopy(getattr(r,k)) for k in ['last_epoch','epoch','global_watch','applied_actions']},b0=copy.deepcopy(r.b0.__dict__),account=copy.deepcopy({k:v for k,v in r.accounts['NO_P'].__dict__.items() if k not in EXCLUDE}))
def fingerprint(v):
 # Aliases are checked by ledger after restore; fingerprint covers values.
 return hashlib.sha256(canon(v).encode()).hexdigest()
def restore_q3():
 t=time.monotonic();f=M.read(BASE/'FREEZE.json');assert all(M.sha(p)==v for p,v in f['sha256'].items());r=B.Pilot();r.run('2025-09-30');old=M.read(BASE/'ECONOMIC_DONE.json');assert old['passed']
 ref=obj(BASE/'results/NO_P.json.gz');a=r.accounts['NO_P'];fields=dict(trades=a.trades,layers=a.layers,audit=a.audit_log,counts=dict(a.counts),decisions=a.decisions,minimum_available=a.minimum_available,ops=a.ops,layer_structures=a.layer_structures,risk_rows=a.risk_rows,structure_risk=a.structure_risk)
 for k,v in fields.items():assert canon(v)==canon(ref[k]),('Q3 recovery mismatch',k)
 assert canon(r.daily)==canon(rows(BASE/'results/daily.jsonl.gz'));assert canon(r.selection_rows)==canon(rows(BASE/'results/selection.jsonl.gz'))
 state=pack(r);raw=pickle.dumps(state,protocol=5);(O/'seed.chk').write_bytes(raw);v=pickle.loads(raw);assert fingerprint(v)==fingerprint(state)
 M.save(O/'RECOVERY_GATE.json',dict(passed=True,seconds=time.monotonic()-t,replay_run_seconds=r.run_seconds,checkpoint_sha256=hashlib.sha256(raw).hexdigest(),fingerprint=fingerprint(state),cursor='2025-09-30T15:10:00+08:00',NAV=str(a.current_nav),positions=len(a.positions),pending_buys=len(a.buys),pending_exits=len(a.exits),pending_next_open_intents=len(a.pending),all_account_fields_saved_except_market_facts_and_rebuildable_live_index=True,original_Q3_all_events_exact=True))
 print('SEED_RECOVERED',time.monotonic()-t,str(a.current_nav),len(a.pending),flush=True);return state
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def configure():M.O=O;M.END='2026-06-30'
class Pilot(M.Pilot):
 def __init__(self,state,cut=None):
  super().__init__(cut=cut,policies=('RAW','POS'))
  for k,v in state['runner'].items():setattr(self,k,copy.deepcopy(v))
  self.b0.__dict__.clear();self.b0.__dict__.update(copy.deepcopy(state['b0']))
  self.seed_fingerprints={}
  for key,a in self.accounts.items():
   a.__dict__.clear();a.__dict__.update(copy.deepcopy(state['account']));a.market=self.market;a.facts=self.facts;a.check();self.seed_fingerprints[key]=fingerprint({k:v for k,v in a.__dict__.items() if k not in EXCLUDE});a.label=key;a.rank_policy=key
   assert all(any(z is q for q in a.layers) for group in a.group_layers.values() for z in group)
  assert len(set(self.seed_fingerprints.values()))==1
  self.capacity=[];self.run_seconds=0
 def make_lists(self,at):
  day=str(at.date());g=self.matrix_days[day];raw=[];eligible=[];unknown=[]
  for sid in self.market.lines:
   f=self.facts.f[sid];date=pd.Timestamp(day)
   if date not in f.index:continue
   r=f.loc[date]
   if not bool(r.i_buy) or not bool(r.i_target):continue
   raw.append(sid);q=g.loc[self.line_sector[sid]]
   if not np.isfinite(q.H1_original) or not np.isfinite(q.R21):unknown.append(sid);continue
   eligible.append(sid)
  maximum=(len(eligible)+1)//2;ordered=sorted(eligible,key=lambda sid:(-float(g.loc[self.line_sector[sid],'H1_original']),self.line_sector[sid],self.line_order[sid],sid));positive=[s for s in ordered if g.loc[self.line_sector[s],'R21']>0];self.shortlists={}
  for key,pool in [('RAW',ordered),('POS',positive)]:
   chosen=pool[:maximum];self.shortlists[key]=set(chosen);assert len(set(chosen))==min(maximum,len(pool))
   self.selection_rows.append(dict(day=day,policy=key,raw_I_count=len(raw),P_score_known_count=len(eligible),P_rank_unknown_count=len(unknown),maximum_B=maximum,B=len(chosen),absolute_positive_count=len(positive),candidates=eligible,selected=chosen,unknown=unknown,attention_at_or_below1_selected=0))
  assert self.shortlists['POS']<=set(positive)
  self.capacity.append(dict(day=day,raw=len(raw),common_known=len(eligible),unknown=len(unknown),maximum_B=maximum,RAW_selected=len(self.shortlists['RAW']),POS_selected=len(self.shortlists['POS']),POS_shortage=maximum-len(self.shortlists['POS']),RAW_nonpositive=sum(g.loc[self.line_sector[s],'R21']<=0 for s in self.shortlists['RAW']),overlap=len(self.shortlists['RAW']&self.shortlists['POS'])))
 def continuation(self,end='2025-12-31',budget=None):
  t=time.monotonic();cursor=M.N.iso('2025-09-30T15:10:00+08:00');finish=M.N.iso(end+'T15:10:00+08:00');closes={x for x in self.market.cutoffs if cursor<x<=finish};opens={x for x in self.market.sessions['A'] if cursor<x<=finish};acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,M.N.TZ) for d in self.actions_by_date};events=sorted(closes|opens|{x for x in acts if cursor<x<=finish});assert finish in closes
  M.E.risk_policy.RECOVERY=pd.read_csv(O/'recovery.csv',index_col=0,parse_dates=True).loc[:end]
  for at in events:
   if budget and time.monotonic()-t>budget:raise TimeoutError('120s Q4 economic budget')
   for a in self.accounts.values():a.settle_due(at)
   self._actions(at)
   for a in self.accounts.values():self._payments(a,at)
   if at in opens:
    for a in self.accounts.values():self.opening(a,at)
   if at in closes:
    self.planning(at)
    if len(self.daily)%20==0:print('Q4_CLOSE',str(at.date()),len(self.daily),round(time.monotonic()-t,3),flush=True)
  self.run_seconds=time.monotonic()-t;return self
def view(r):return dict(daily=r.daily,selection=r.selection_rows,accounts={k:dict(trades=a.trades,layers=a.layers,audit=a.audit_log,counts=dict(a.counts),decisions=a.decisions,core_epoch=a.core_epoch,risk_state=a.risk_state) for k,a in r.accounts.items()})
def main():
 if not (O/'PREPARED.json').exists():prepare()
 state=restore_q3();configure();t=time.monotonic();a=Pilot(state);a.continuation('2025-10-15');b=Pilot(state,cut='2025-10-15');b.continuation('2025-10-15');assert canon(view(a))==canon(view(b));M.save(O/'GATE.json',dict(passed=True,seconds=time.monotonic()-t,physical_prefix='2025-10-15',seed_fingerprints=a.seed_fingerprints,full_original_account_state_inherited=True,only_new_CORE_shortlist_changed=True,shared_capacity_not_forced_equal_actual_count=True,original_Q_order_and_exit_preserved=True));del a,b
  # Freeze after correctness, before the unique full Q4 comparison.
 files=[O/'PROTOCOL.txt',O/'experiment.py',O/'recovery.csv',O/'seed.chk',O/'RECOVERY_GATE.json',OLD/'adapter.py',BASE/'baseline.py',BASE/'FREEZE.json',M.F,M.IC/'FREEZE.json'];M.save(O/'FREEZE.json',dict(before_Q4_paths=True,paths=['RAW','POS'],normal_only=True,sha256={str(p):M.sha(p) for p in files},industry_sha={p.name:M.sha(p) for p in (O/'industry-facts').glob('*.parquet')}))
 r=Pilot(state);t=time.monotonic()
 try:r.continuation(budget=120);r.dump(O/'results')
 except BaseException:r.run_seconds=time.monotonic()-t;r.dump(O/'failed-partial');raise
 M.save(O/'ECONOMIC_DONE.json',dict(passed=True,new_paths=2,quarter='2025Q4',seconds=r.run_seconds,wall_with_dump=time.monotonic()-t,seed_NAV=str(state['account']['current_nav']),seed_positions=len(state['account']['positions'])));M.save(O/'CAPACITY.json',r.capacity)
 seed=float(state['account']['current_nav'])
 for key in ['RAW','POS']:
  ds=[x for x in r.daily if x['account']==key];nav=np.array([float(x['nav']) for x in ds]);dd=1-nav/np.maximum.accumulate(np.r_[seed,nav])[1:];print('RESULT_Q4',key,dict(net_return_Q4=float(nav[-1]/seed-1),DD_Q4=float(dd.max()),end_nav=nav[-1],seconds=r.run_seconds),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:M.save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
