"""Frozen input/startup check and prepared commands; no run unless --execute."""
from pathlib import Path
import argparse,collections,copy,gzip,hashlib,json,pickle,time
import numpy as np,pandas as pd
import joint_v3 as J

W=J.W;U=J.BASE.parent/'universe-cp1-inputs-20261031';OUT=J.O/'startup'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(W.canon(x),ensure_ascii=False,indent=2)+'\n')

def inputs(scope):
 """Only read verified original/cache inputs; never derive new indicators."""
 freeze=read(U/'FREEZE.json');sm=read(U/'STOCK_MANIFEST.json');im=read(U/'INDUSTRY_MANIFEST.json')
 fixed=freeze['stocks'];assert len(fixed)==len(set(fixed))==1709
 case=read(W.CACHE/'MANIFEST.json');case_ids={x['sid'] for x in case if x['status']=='complete'}
 assert len(case_ids)==77
 ids=fixed if scope=='universe' else [s for s in fixed if s in case_ids]
 stock={r['symbol']:r for r in sm};industry={r['series']:r for r in im};fullfacts={};cp={};receipts={}
 for sid in ids:
  r=stock[sid]
  assert r['status'] in ('complete','not_applicable_no_local_observation_by_end')
  for path,h in r['output_sha256'].items():assert sha(path)==h,('changed cache',path)
  fullfacts[sid]=pd.read_parquet(r['refs']['facts']).loc[:J.END]
  cp[sid]=pd.read_parquet(r['refs']['CP1']).loc[:J.END]
  receipts[sid]={x['confirmed_day']:x for x in read(r['refs']['receipts']) if J.START<=x['confirmed_day']<=J.END}
  assert len(receipts[sid])==sum(bool(x) for x in cp[sid].loc[J.START:J.END,'receipt'])
  native=pd.read_parquet(J.BASE.parent/'native-I-cache-interface-20261031/facts'/f'{sid}.parquet').loc[J.START:J.END]
  current=fullfacts[sid].loc[J.START:J.END,native.columns]
  aa=current.copy(deep=False);bb=native.copy(deep=False)
  aa.index=aa.index.as_unit('ns');bb.index=bb.index.as_unit('ns')
  pd.testing.assert_frame_equal(aa,bb,check_exact=True,check_dtype=False,check_freq=False)
 shared=J.M.context(J.END,ids=ids);bundle,market,facts=shared
 assert {l.security_id for l in bundle.lines}==set(ids)==set(market.lines)
 for sid,f in fullfacts.items():
  facts.f[sid]=f;bundle.series[sid].states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 sectors={l.sector_id for l in bundle.lines}
 if scope=='universe':assert sectors==set(freeze['industries']) and len(sectors)==90
 else:assert len(sectors)==5
 states={};industry_receipts={}
 for sid in sorted(sectors):
  r=industry[sid];assert r['status']=='complete'
  for path,h in r['output_sha256'].items():assert sha(path)==h,('changed industry cache',path)
  q=pd.read_parquet(r['refs']['state']);states[sid]=J.T.norm(q[q.day<=J.END].to_dict('records'))
  old5=J.BASE.parent/'industry-mobile-stage-20261031'/f'{sid}_STATE.json'
  if old5.exists():assert states[sid]==read(old5),'Parquet state view differs from original case JSON'
  for x in read(r['refs']['receipts']):
   if J.START<=x['confirmed_day']<=J.END:industry_receipts[sid+'|'+x['confirmed_day']]=x
  qfacts=facts.f[sid];assert qfacts.index.max()<=pd.Timestamp(J.END)
  assert set(('e0_ready','e0_target','e0_floor','factor','raw_close'))<=set(qfacts.columns)
 recovery=J.M.O/'recovery.csv';v2freeze=read(J.BASE/'PAIR_FREEZE.json')
 assert sha(recovery)==v2freeze['sha256'][str(recovery)],'ACT external clock changed'
 return shared,receipts,cp,states,industry_receipts,dict(fixed_stock_ids=fixed,account_ids=ids,
  sector_ids=sorted(sectors),scope=scope,ACT_external_file=str(recovery),ACT_external_sha256=sha(recovery),
  stock_manifest_sha256=sha(U/'STOCK_MANIFEST.json'),industry_manifest_sha256=sha(U/'INDUSTRY_MANIFEST.json'))

class PreparedRunner(J.Runner):
 """Same decisions; checkpoint only after a whole original event completes."""
 def checkpoint(self,out,last_event):
  out=Path(out);out.mkdir(parents=True,exist_ok=True)
  immutable={'bundle','market','facts','accounts','cp','pv','matrix','matrix_days','industry_rows','industry_cp','receipts','actions_by_date'}
  runner={k:v for k,v in self.__dict__.items() if k not in immutable}
  accounts={k:{f:v for f,v in a.__dict__.items() if f not in ('market','facts')} for k,a in self.accounts.items()}
  payload=dict(last_completed_event=last_event,runner=runner,accounts=accounts,
   source_freeze=self.source_freeze,quarter_or_budget_reset=False)
  raw=pickle.dumps(payload,protocol=5);r=pickle.loads(raw)
  assert r['last_completed_event']==last_event
  for k,a in self.accounts.items():
   assert r['accounts'][k]['available']==a.available
   assert r['accounts'][k]['budget'].consumed==a.budget.consumed
   assert r['accounts'][k]['positions']==a.positions
  target=out/'checkpoint.pkl';temp=out/'checkpoint.tmp';temp.write_bytes(raw);temp.replace(target)
  save(out/'checkpoint.json',dict(at=last_event,sha256=sha(target),source_freeze=self.source_freeze,
   account_initialization_not_repeated=True,roundtrip_only_not_historical_restart_proof=True))
 def restore(self,path):
  p=pickle.loads(Path(path).read_bytes());assert p['source_freeze']==self.source_freeze,'resume input/code freeze differs'
  self.__dict__.update(p['runner'])
  for k,state in p['accounts'].items():self.accounts[k].__dict__.update(state)
  return p['last_completed_event']
 def run_prepared(self,out,max_seconds,resume_after=None,end=None):
  # Original M.Pilot.run event construction/order. The only clock difference
  # is a strict skip of already completed checkpoint events on explicit resume.
  from datetime import datetime,time as dt
  end=end or J.END
  start=J.M.N.iso(J.START+'T15:10:00+08:00');finish=J.M.N.iso(end+'T15:10:00+08:00')
  cutoffs={x for x in self.market.cutoffs if start<=x<=finish};opens={x for x in self.market.sessions['A'] if start<=x<=finish}
  acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ) for d in self.actions_by_date}
  events=sorted(cutoffs|opens|{x for x in acts if start<=x<=finish});assert finish in cutoffs
  J.M.E.risk_policy.RECOVERY=pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:end]
  t=time.monotonic();last=resume_after
  for at in events:
   if resume_after is not None and at<=resume_after:continue
   if time.monotonic()-t>max_seconds:
    if last is not None:self.checkpoint(out,last)
    self.dump_joint(Path(out)/'partial');return False
   for a in self.accounts.values():a.settle_due(at)
   self._actions(at)
   for a in self.accounts.values():self._payments(a,at)
   if at in opens:
    for a in self.accounts.values():self.opening(a,at)
   if at in cutoffs:self.planning(at)
   last=at
   # Monthly data checkpoint, never a cash/position/ACT reset.
   if at in cutoffs and (pd.Timestamp(at.date())+pd.offsets.BDay()).month!=at.month:self.checkpoint(out,last)
  self.run_seconds=time.monotonic()-t;self.checkpoint(out,last);self.dump_joint(Path(out)/'pair')
  save(Path(out)/'DONE.json',dict(completed=True,run_seconds=self.run_seconds,ending_NAV={k:str(a.current_nav) for k,a in self.accounts.items()}))
  return True

def preflight(scope):
 t=time.monotonic();shared,receipts,cp,states,industry_receipts,identity=inputs(scope)
 r=PreparedRunner(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=industry_receipts)
 for a in r.accounts.values():
  assert a.available==a.initial_cash==a.current_nav==J.D(1000000)
  assert not a.positions and not a.buys and not a.exits and not a.trades and not a.budget.orders
 clocks=[]
 for day in ('2025-07-01','2025-09-30','2025-12-31','2026-03-31'):
  at=J.M.N.iso(day+'T15:10:00+08:00');clock,stocks,sectors=r.facts.packet(at,'I')
  key=lambda s:(-(s.rank.read(clock) if s.rank and s.rank.read(clock) is not None else -1),s.security_id)
  order=[s.security_id for s in sorted(stocks,key=key)]
  reverse=[s.security_id for s in sorted(reversed(stocks),key=key)]
  assert order==reverse and len(order)==len(set(order))
  clocks.append(dict(day=day,stocks_in_packet=len(stocks),sectors_in_packet=len(sectors),H1_code_ties_stable=True,order_sha256=hashlib.sha256('\n'.join(order).encode()).hexdigest()))
 sources=[Path(__file__),J.O/'joint_v3.py',J.BASE/'wire.py',J.BASE/'budget_v3/model.py',J.BASE/'budget_v3/test_contract.py',U/'STOCK_MANIFEST.json',U/'INDUSTRY_MANIFEST.json',J.M.O/'recovery.csv',J.M.P/'h1.npz']
 r.source_freeze={str(p):sha(p) for p in sources}
 payload=dict(passed=True,scope=scope,identity=identity,scope_dates=[J.START,J.END],cash_each=1000000,
  initial_account_state='empty cash/positions/orders/losses; original warm industry market stage inherited, no old stock receipt replay',
  raw_I_audit_all_values_exact=True,Q_function='unchanged BP.A.eligibility; no account run',
  H1_tie_break='descending original individual H1 rank, security code; core before mobile only within same stock',
  signals_priority_not_case_based=True,samples=clocks,seconds=time.monotonic()-t,new_account_paths=0,
  freeze=r.source_freeze,remaining='independent revised source review and physical-prefix/restart engineering gate before economics')
 save(OUT/(scope+'-PREFLIGHT.json'),payload);return r,payload

def main():
 p=argparse.ArgumentParser();p.add_argument('--scope',choices=('case','universe'),required=True)
 p.add_argument('--execute',action='store_true');p.add_argument('--seconds',type=float,default=300)
 p.add_argument('--out',type=Path);p.add_argument('--resume',type=Path)
 args=p.parse_args();r,status=preflight(args.scope)
 print(json.dumps({k:status[k] for k in ('passed','scope','seconds','new_account_paths')},indent=2),flush=True)
 if not args.execute:return
 assert read(J.O/'BRIDGE_GATE.json')['passed'] and read(J.BASE/'budget_v3/results.json')['passed']
 out=args.out or J.O/('run-'+args.scope)
 assert not (out/'DONE.json').exists(),'completed run must not be duplicated'
 resume=r.restore(args.resume) if args.resume else None
 save(out/'FREEZE.json',status)
 r.run_prepared(out,args.seconds,resume)

if __name__=='__main__':main()
