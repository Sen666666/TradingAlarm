"""Two dates only. Native OPEN/route/account, no original writes and no return path."""
from pathlib import Path
import argparse,sys,time,json,hashlib,traceback,copy,gzip
from decimal import Decimal as D
from datetime import timedelta
import pandas as pd
O=Path(__file__).resolve().parent
OLD=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1')
sys.path.insert(0,str(OLD));import load_inputs as V
from causal_open_adapter import freeze_open_inputs,OpenFacts,build_market,MODES
sys.path.insert(0,str(O/'ranking'));from pending_rank_adapter import rank_pending
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def canon(v):return J.W.canon(v)
def save(p,v):IO.write_json(p,canon(v))
def digest(v):return hashlib.sha256(json.dumps(canon(v),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def account_state(a):
 b=a.budget
 return dict(positions=a.positions,layers=a.layers,metadata=a.jmeta,buys=a.buys,exits=a.exits,settlements=a.settlements,dividends=a.dividends,cash=a.available,fees=a.fees_cny,risk_state=a.risk_state,current_nav=a.current_nav,core_epoch=a.core_epoch,
 budget=dict(sectors=b.sectors,orders=b.orders,losses={str(k):v for k,v in b.losses.items()},consumed=sorted(b.consumed),lots=b.lots,prices=b.prices,cash=b.cash,receivables=b.receivable_equity))
def new_account(base):
 a=copy.copy(base)
 a.__dict__=copy.deepcopy({k:v for k,v in base.__dict__.items() if k not in ('market','facts')})
 return a

def one(base_runner,day,at,factors,states,rank,mode,variant):
 r=copy.copy(base_runner);base=base_runner.accounts['B'];a=new_account(base)
 r.market=build_market(base_runner.market,J.C.L,at,mode,variant)
 r.facts=OpenFacts(factors,base_runner.facts)
 # Physically limit the only per-stock signal map admitted by fill_buy to the decision prefix.
 r.facts.structure_lookup={s:{d:v for d,v in x.items() if d<=base.as_of.date()} for s,x in base_runner.facts.structure_lookup.items()}
 a.market=r.market;a.facts=r.facts;r.accounts={'B':a};r.funding=[]
 original_pending=canon(a.pending);ra=[];rs={}
 if rank=='E31':a.pending,ra,rs=rank_pending(a.pending,states,day)
 assert canon([{k:v for k,v in i.items() if k!='rank'} for i in a.pending])==[{k:v for k,v in i.items() if k!='rank'} for i in original_pending]
 assert not a.buys and not a.settlements, 'Scope needs explicit outstanding-order/settlement event extension'
 assert all(d.paid_at is None or d.paid_at>at for d in a.dividends.values()),'Payment event needs explicit scheduling'
 touched=set(a.positions)|set(a.buys)
 for sid in touched:
  assert not any(day<e['effective_date']<=at.date().isoformat() for e in r.market.actions.get(sid,[])),('Held corporate action outside bounded scope',sid)
 initial=account_state(a);trn=len(a.trades);fn=len(a.fills);an=len(a.audit_log);jn=len(a.journal);sn=len(a.sync_rows)
 before=a.balance(at,r.market.marks(at,a.positions));prior_positions=canon(a.positions)
 # Native event order before native opening, no skipped payments or actions by above gates.
 a.settle_due(at);r._payments(a,at)
 assert r.opening.__func__ is J.Runner.opening and r.route.__func__ is A.P.ROUTES[True] if hasattr(A,'P') else True
 r.opening(a,at)
 after=a.balance(at,r.market.marks(at,a.positions));openstate=account_state(a)
 fills=a.fills[fn:];sells=[x for x in fills if x.side=='sell'];buys=[x for x in fills if x.side=='buy']
 grossbuy=sum((x.gross_cny for x in buys),Z);grosssell=sum((x.gross_cny for x in sells),Z);fees=sum((x.fees_cny for x in fills),Z)
 cashgap=(after['available']+after['order_reserved'])-(before['available']+before['order_reserved']+grosssell-grossbuy-fees)
 markdelta=Z
 for x in fills:
  v=r.market.latest_mark(x.security_id,at).cny_price(at)*x.shares
  markdelta+=(v-x.gross_cny if x.side=='buy' else x.gross_cny-v)-x.fees_cny
 navgap=after['nav']-before['nav']-markdelta
 assert abs(cashgap)<D('1e-8') and abs(navgap)<D('1e-8'),('money conservation',cashgap,navgap)
 if mode=='UNKNOWN_NO_FILL':assert not fills and canon(a.positions)==prior_positions
 close=at.replace(hour=15,minute=10)
 a.expire_day_buys(close);a.sync(close);a.check();expiry=a.balance(close,r.market.marks(close,a.positions))
 assert not a.buys and expiry['order_reserved']==0
 assert expiry['available']==after['available']+after['order_reserved']
 assert expiry['nav']==after['nav'],'No close revaluation in expiry-only branch'
 result=dict(day=day,open_at=at,rank=rank,execution_mode=mode,scope='CONDITIONAL_NEXT_OPEN_FROM_SHARED_ORIGINAL_BIASED_HISTORY_NOT_PORTFOLIO_RETURN',before=before,after_open=after,after_expiry_only=expiry,
 counts=dict(initial_stocks=len(initial['positions']),initial_layers=sum(x['qty']>0 for x in initial['layers']),pending_intents=len(a.pending),pending_stocks=len(set(i['sid'] for i in a.pending)),reservations=sum(x['result']=='reserved' for x in r.funding),buy_fills=len(buys),sell_fills=len(sells),end_stocks=len(a.positions),end_layers=sum(x['qty']>0 for x in a.layers)),
 flows=dict(gross_buy=grossbuy,gross_sell=grosssell,fees=fees,sell_net=grosssell-sum((x.fees_cny for x in sells),Z)),checks=dict(cash_conservation_gap=cashgap,NAV_conservation_gap=navgap,expiry_conservation=True,candidate_membership_and_nonrank_fields_identical=True,native_opening_and_route_unchanged=True,raw_future_rows_removed=True,today_HLCV_unavailable=True,facts_row_and_floor_inaccessible=True),
 funding=r.funding,trades=a.trades[trn:],audit=a.audit_log[an:],journal=a.journal[jn:],sync_rows=a.sync_rows[sn:],execution_audit=r.market.execution_audit,rank_audit=ra,rank_summary=rs,state_before=initial,state_after_open=openstate,state_after_expiry=account_state(a))
 return canon(result)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--day',required=True);z=ap.parse_args();day=z.day;assert day in ['2024-09-24','2026-01-15']
 win='2022_2024' if day=='2024-09-24' else 'strong';p=O/'boundaries'/day;out=O/'bounded'/day
 assert read(p/'VERIFIED_BOUNDARY.json')['passed'];assert not out.exists(),'No implicit overwrite/retry'
 out.mkdir(parents=True);start=time.monotonic()
 try:
  meta=read(p/'checkpoint.json');assert sha(p/'checkpoint.pkl')==meta['sha256']
  for f,h in meta['source_freeze'].items():assert sha(f)==h
  sources={str(f):sha(f) for f in [Path(__file__),O/'causal_open_adapter.py',O/'ranking/pending_rank_adapter.py']}
  save(out/'PREDECLARED.json',dict(day=day,branches=['PVR','E31'],execution_modes=MODES,future_mutations=['MASKED','POISONED'],original_source_freeze=meta['source_freeze'],isolated_source_freeze=sources,boundary_checkpoint_sha256=sha(p/'checkpoint.pkl'),annual_execution=False))
  print('LOAD_INPUTS',day,flush=True);shared,receipts,cp,states,ir,identity=V.inputs(win)
  r=A.Runner(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=dict(meta['source_freeze'])
  with IO.atomic_runner_outputs(r,L,out/'guarded_restore',canonicalize=canon):last=r.restore(p/'checkpoint.pkl')
  assert last.date().isoformat()==day
  a=r.accounts['B'];at=next(x for x in r.market.sessions['A'] if x>last)
  print('RESTORED',day,'next',str(at),flush=True)
  needed=set(i['sid'] for i in a.pending)|set(a.positions)|set(a.exits)|set(a.buys)
  factors,actions=freeze_open_inputs(r.market,r.facts,last,at,needed)
  st=pd.read_parquet(O.parent/'equal_entry_validation_v1/ALL_ORIGINAL_I_BUY_WITH_STATES.parquet');st=st[st.day.astype(str).str[:10].eq(day)].to_dict('records')
  markdiag=[];test=build_market(r.market,J.C.L,at,'OPEN_PROXY')
  for sid in a.positions:
   old=r.market.latest_mark(sid,at);new=test.latest_mark(sid,at)
   markdiag.append(dict(sid=sid,native=old,isolated=new,price_and_clock_equal=(old.raw_price==new.raw_price and old.known_at==new.known_at)))
  save(out/'KNOWN_INPUTS.json',dict(factors=factors,action_assumptions=actions,mark_diagnostic=markdiag,signal_at=last,open_at=at))
  initial_digest=digest(account_state(a));summary=[];invariance=[]
  for rank in ('PVR','E31'):
   for mode in MODES:
    print('BRANCH',day,rank,mode,flush=True)
    primary=one(r,day,at,factors,st,rank,mode,'MASKED');poison=one(r,day,at,factors,st,rank,mode,'POISONED')
    equal=primary==poison;invariance.append(dict(rank=rank,mode=mode,all_outputs_identical=equal,masked_sha256=digest(primary),poisoned_sha256=digest(poison)))
    assert equal,('Future perturbation changed output',rank,mode)
    save(out/(rank+'__'+mode+'.json'),primary)
    summary.append({k:v for k,v in primary.items() if k in ('day','open_at','rank','execution_mode','scope','before','after_open','after_expiry_only','counts','flows','checks','rank_summary')})
    assert digest(account_state(a))==initial_digest,'Shared starting account mutated'
  for f,h in meta['source_freeze'].items():assert sha(f)==h
  for f,h in sources.items():assert sha(f)==h
  save(out/'SUMMARY.json',dict(passed=True,day=day,seconds=time.monotonic()-start,arms=summary,future_perturbation=invariance,original_sources_unchanged=True,source_account_unchanged=True,mark_prices_and_clocks_equal_count=sum(x['price_and_clock_equal'] for x in markdiag),held_mark_count=len(markdiag)))
  print('DONE',day,round(time.monotonic()-start,1),flush=True)
 except BaseException as e:
  save(out/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_retry=False));raise
if __name__=='__main__':main()
