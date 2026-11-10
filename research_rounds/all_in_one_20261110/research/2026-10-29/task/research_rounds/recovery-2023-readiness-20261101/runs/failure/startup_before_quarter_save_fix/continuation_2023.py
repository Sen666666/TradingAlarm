"""Same frozen Bdiag/C1 policies; explicit verified same-account year extension."""
from pathlib import Path
import sys,pickle,json,gzip,copy,shutil
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'c1-drawdown-capacity-20261101'))
import adapter_c1 as C
E,J,L,BASE,IO=C.E,C.J,C.L,C.BASE,C.IO
START='2023-01-01';END='2023-12-29';PARENT_END='2022-12-30';J.START=START;J.END=END
def save(p,x):IO.write_json(p,J.T.norm(J.W.canon(x)))
def inputs():
 import time
 begun=time.monotonic();complete=L.read(O/'inputs/COMPLETION.json');assert complete['passed'] and complete['stock_receipts']==18781 and complete['industry_receipts']==1270
 manifest=L.read(O/'inputs/MANIFEST.json');new={r['sid']:r for r in manifest};sm=L.read(L.U/'STOCK_MANIFEST.json');im=L.read(L.U/'INDUSTRY_MANIFEST.json');fixed=L.read(L.U/'FREEZE.json')['stocks'];full={};cp={};receipts={}
 for r in sm:
  sid=r['symbol'];rec=new[sid];assert rec['original_output_sha256']==r['output_sha256']
  for p,h in r['output_sha256'].items():assert L.sha(p)==h,('changed numeric cache',sid,p)
  assert L.sha(rec['output_path'])==rec['output_sha256']
  f=pd.read_parquet(r['refs']['facts']).loc[:END];q=pd.read_parquet(r['refs']['CP1_input']).loc[:END];z=pd.read_parquet(r['refs']['CP1']).loc[:END]
  assert f.index.equals(q.index) and q.index.equals(z.index)
  for k in ('close','segment_id','i_target','i_floor'):pd.testing.assert_series_equal(f[k],q[k],check_exact=True,check_dtype=False,check_freq=False)
  assert q.e0_valid.equals(f.i_target.astype(bool))
  rr=L.read(rec['output_path']);assert len(rr)==int(z.loc[START:END].receipt.eq(True).sum());full[sid]=f;cp[sid]=z;receipts[sid]={x['confirmed_day']:x for x in rr}
 shared=J.M.context(END,ids=fixed);bundle,market,facts=shared;assert set(market.lines)==set(fixed)=={l.security_id for l in bundle.lines}
 for sid,f in full.items():facts.f[sid]=f;bundle.series[sid].states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
 states={};ir={}
 for r in im:
  sid=r['series'];rec=new[sid]
  for p,h in r['output_sha256'].items():assert L.sha(p)==h,('changed industry cache',sid,p)
  assert L.sha(rec['output_path'])==rec['output_sha256'];z=pd.read_parquet(r['refs']['state']);states[sid]=J.T.norm(z[z.day<=END].to_dict('records'))
  for x in L.read(rec['output_path']):ir[sid+'|'+x['confirmed_day']]=x
 assert L.sha(J.M.O/'recovery.csv')==L.read(J.BASE/'PAIR_FREEZE.json')['sha256'][str(J.M.O/'recovery.csv')]
 identity=dict(fixed_ids=fixed,sectors=[r['series'] for r in im],window=[START,END],numeric_models_recomputed=0,stocks_with_2023_rows=sum(len(f.loc[START:END])>0 for f in full.values()),source_manifest_SHA=L.sha(L.U/'STOCK_MANIFEST.json'),receipt_manifest_SHA=L.sha(O/'inputs/MANIFEST.json'),ACT_external_SHA=L.sha(J.M.O/'recovery.csv'),H1_SHA=L.sha(J.M.P/'h1.npz'),seconds=time.monotonic()-begun)
 save(O/'INPUT_GATE.json',dict(passed=True,identity=identity));return shared,receipts,cp,states,ir,identity

def instrument_route(original,name):
 """Add one compact row only after original route quantity/reasons are computed."""
 needle='results=[];reasons={}'
 after='q=LR.maximum_quantity(rule,maxq,allowed);results.append((q,pool));reasons[pool]=allowed(rule.buy_minimum,True)'
 selected="q,pool=max(results,key=lambda z:(z[0],z[1]=='probe'))"
 assert all(original.count(x)==1 for x in [needle,after,selected])
 extra=";diagnostic.append(dict(pool=pool,legal_quantity=q,minimum_reasons=reasons[pool],minimum_quantity=rule.buy_minimum,minimum_gross=rule.buy_minimum*p,pool_capital=pc,pool_risk=pr,sector_capital=sc,sector_risk=sr,all_risk=ar,reserve=reserve,pending_fees=pending_fees))"
 log="\n  self.capacity_checks.append(dict(account=a.label,at=at,decision_at=i['clock'].decision_at,sid=sid,role=role,CP1_id=rid,attempt=s.attempt,industry_level=s.level,c=b.confirmed_fraction() if hasattr(b,'c1') else .60,H=str(b.c1.high) if hasattr(b,'c1') else None,decision_NAV=str(a.current_nav),live_budget_NAV=b.nav,cash=b.cash,selected_pool=pool if q else None,selected_quantity=q,confirmed_migration_admitted=('confirmed' in routes),confirmed_migration_reason='not_applicable' if not (role=='mobile' and b.expand and s.level>0) else ('admitted' if 'confirmed' in routes else 'confirmed_unfunded_raw_unknown'),routes=diagnostic))"
 text=original.replace(needle,needle+';diagnostic=[]').replace(after,after+extra).replace(selected,selected+log)
 assert text.replace(needle+';diagnostic=[]',needle).replace(after+extra,after).replace(selected+log,selected)==original
 path=O/(name+'_route_trace.py');IO.write_bytes(path,text.encode());env=dict(J.__dict__);exec(compile(text,str(path),'exec'),env);return env['route'],text
route_Bdiag,route_Bdiag_source=instrument_route(C.ROUTE_OLD,'Bdiag')
route_C1,route_C1_source=instrument_route(C.ROUTE_NEW,'C1')

class Continued:
 reference=None
 def __init__(self,*args,**kw):
  if self.reference=='Bdiag':
   super().__init__(*args,policies=('B',),**kw);BASE.enable(self.accounts['B'])
  else:super().__init__(*args,**kw)
  self.capacity_checks=[]
 def import_verified(self,root,expected):
  root=Path(root);path=root/'checkpoint-2022-12-30.pkl';meta=L.read(path.with_suffix('.json'));prov=L.read(path.with_suffix('.provenance.json'));assert L.sha(path)==expected==meta['sha256']==prov['checkpoint_sha256']
  p=pickle.loads(path.read_bytes());assert str(p['last_completed_event'])==PARENT_END+' 15:10:00+08:00';assert p['source_freeze']==meta['source_freeze']
  assert all(Path(k).is_file() and L.sha(k)==v for k,v in p['source_freeze'].items()),'original frozen source changed'
  audited=L.read(O/'CHECKPOINT_READINESS.json')['accounts'][self.reference];assert audited['SHA256']==expected and audited['generation_engine_identity']==prov['engine_identity']
  old=p['accounts']['B'];a=self.accounts['B'];assert a.available==a.initial_cash==J.D(1000000) and not a.positions and not a.trades
  assert old['mode']=='ACT' and old['cost_multiplier']==1 and old['delay_events']==0 and not old['add_enabled']
  assert type(old['budget']) is (C.Budget if self.reference=='C1' else BASE.NoAccountBudget)
  with gzip.open(root/'pair/B.json.gz','rt') as f:book=json.load(f)
  fmap={'trades':'trades','layers':'layers','jmeta':'metadata','journal':'journal','buys':'orders','exits':'exits','audit_log':'audit','decisions':'decisions','available':'ending_cash','current_nav':'ending_NAV'}
  bookchecks={k:J.W.canon(old[k])==book[v] for k,v in fmap.items()};assert all(bookchecks.values())
  b=old['budget'];assert J.W.canon(dict(sectors=b.sectors,orders=b.orders,losses={str(k):v for k,v in b.losses.items()},consumed=sorted(b.consumed)))==book['budget']
  streams={}
  for field,file in {'daily':'daily','opportunities':'opportunities','funding':'funding','stage_events':'industry','balance_audit':'balances'}.items():
   left=E.record_digest(x for x in p['runner'][field] if x['account']=='B');right=E.record_digest(E.file_rows(root/'pair'/(file+'.jsonl.gz')));assert left==right;streams[field]=left
  assert self.sector_by_sid==p['runner']['sector_by_sid']==old['sector_by_sid']
  frozen=self.source_freeze;keys=set(p['runner'])-{'source_freeze','run_seconds'}
  for k in keys:setattr(self,k,copy.deepcopy(p['runner'][k]))
  self.source_freeze=frozen
  market,facts=a.market,a.facts;a.__dict__.clear();a.__dict__.update(copy.deepcopy(old));a.market=market;a.facts=facts
  ac={k:E.equal(v,a.__dict__[k]) for k,v in old.items()};rc={k:E.equal(p['runner'][k],getattr(self,k)) for k in keys};assert all(ac.values()) and all(rc.values())
  assert not a.positions and not a.buys and not a.exits
  bal=a.balance(p['last_completed_event'],self.market.marks(p['last_completed_event'],a.positions));assert bal['nav']==a.current_nav==J.D(book['ending_NAV'])
  assert abs(b.nav-float(bal['nav']))<1e-6 and abs(b.cash-b.resources()[2]-float(a.available))<1e-6
  assert all(E.equal(v,a.__dict__[k]) for k,v in old.items()),'verification changed original account'
  if self.reference=='C1':a.budget.c1.validate();assert a.budget.c1.high==J.D(1000000) and a.budget.c1.fraction==J.D('.10')
  self.parent_verified=dict(path=str(path),SHA256=expected,last_event=p['last_completed_event'])
  proof=dict(passed=True,known_generation_identity_verified_not_legacy_backfill=True,original_generation_identity=prov['engine_identity'],parent=self.parent_verified,all_account_fields_equal=ac,all_strategy_fields_equal=rc,final_book_fields_equal=bookchecks,all5_complete_event_streams_exact=streams,initial_balance=bal,C1=getattr(a.budget,'c1',None),actual_new_events=0,new_identity=IO.runner_identity(self),source_freeze_only_extended_explicitly=True)
  return p['last_completed_event'],proof
 def checkpoint(self,out,last_event):
  E.env2['checkpoint'](self,out,last_event);out=Path(out);day=str(last_event.date())
  if day in {'2023-03-31','2023-06-30','2023-09-28','2023-12-29'}:
   for suffix in ('pkl','json'):shutil.copyfile(out/('checkpoint.'+suffix),out/('checkpoint-'+day+'.'+suffix))
 def dump_joint(self,path):
  super().dump_joint(path);IO.write_gzip_jsonl(Path(path)/'capacity-checks.jsonl.gz',(J.W.canon(x) for x in self.capacity_checks))

class Bdiag(Continued,L.PreparedRunner):
 reference='Bdiag';route=route_Bdiag
class C1(Continued,C.Runner):
 reference='C1';route=route_C1
