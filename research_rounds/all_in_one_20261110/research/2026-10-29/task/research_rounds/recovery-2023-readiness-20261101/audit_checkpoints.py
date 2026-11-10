"""Read saved state and its original output; no runner init, restore, or event replay."""
from pathlib import Path
from decimal import Decimal as D
import sys,pickle,json,gzip,hashlib,importlib.util,time,collections,traceback
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'c1-drawdown-capacity-20261101'))
import adapter_c1 as C
E,J,IO=C.E,C.J,C.IO
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):IO.write_json(O/name,J.W.canon(x))
def loadclass():
 p=W/'2022-normal-reference-20261031/adapter.py'
 spec=importlib.util.spec_from_file_location('fixed_calendar2022_original_normal',p)
 m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m);return m.Bdiag
def main():
 started=time.monotonic();cls=loadclass();output={}
 configs=[('Bdiag',W/'2022-normal-reference-20261031/runs/B_diag',cls,'6e1ab631d549535eb762d84422659ab8f33459ddb5c07c6fe649eb47c091bdcd'),('C1',W/'c1-drawdown-capacity-20261101/runs/2022',C.Runner,'2d7d3a8bc7490c7db466e376959bfd85f5991d19b82092cf731c90f15c056929')]
 for ref,root,kls,expected in configs:
  path=root/'checkpoint-2022-12-30.pkl';meta=read(path.with_suffix('.json'));prov=read(path.with_suffix('.provenance.json'))
  assert sha(path)==expected==meta['sha256']==prov['checkpoint_sha256']
  p=pickle.loads(path.read_bytes());a=p['accounts']['B'];b=a['budget'];at=p['last_completed_event']
  assert str(at)=='2022-12-30 15:10:00+08:00' and str(prov['last_completed_event'])==str(at)
  assert p['source_freeze']==meta['source_freeze']
  changed=[k for k,v in p['source_freeze'].items() if not Path(k).is_file() or sha(k)!=v];assert not changed,changed
  identity=IO.runner_identity(object.__new__(kls));old=prov['engine_identity']
  assert identity['trading_class']==old['trading_class'] and identity['functions']==old['functions']
  assert sha(old['runtime_class']['module_path'])==old['runtime_class']['module_sha256']
  with gzip.open(root/'pair/B.json.gz','rt') as f:book=json.load(f)
  fmap={'trades':'trades','layers':'layers','jmeta':'metadata','journal':'journal','buys':'orders','exits':'exits','audit_log':'audit','decisions':'decisions','available':'ending_cash','current_nav':'ending_NAV'}
  exact={k:J.W.canon(a[k])==book[v] for k,v in fmap.items()};assert all(exact.values()),exact
  budget=dict(sectors=b.sectors,orders=b.orders,losses={str(k):v for k,v in b.losses.items()},consumed=sorted(b.consumed))
  assert J.W.canon(budget)==book['budget']
  streams={}
  for field,file in {'daily':'daily','opportunities':'opportunities','funding':'funding','stage_events':'industry','balance_audit':'balances'}.items():
   left=E.record_digest(x for x in p['runner'][field] if x['account']=='B');right=E.record_digest(E.file_rows(root/'pair'/(file+'.jsonl.gz')))
   assert left==right,(ref,field);streams[field]=left
  # Explicit flat state and non-spendable dividend equity; no residual adjustment.
  ar=sum((x.net_local for x in a['dividends'].values()),D(0));settlement=sum((x.net_local for x in a['settlements'].values()),D(0))
  assert not a['positions'] and not a['buys'] and not a['exits'] and not b.lots
  assert a['available']+ar+settlement==a['current_nav']
  pending=[x for x in b.orders.values() if x.qty>0 and x.status in ('open','cancel_pending')];assert not pending
  assert abs(b.cash-float(a['available']))<1e-6 and abs(b.receivable_equity-float(ar+settlement))<1e-6
  sectors=collections.Counter(s.status for s in b.sectors.values())
  state=dict(last_completed_event=at,NAV=a['current_nav'],available_cash=a['available'],nonspendable_dividend_receivable=ar,settlement_receivable=settlement,
   positions=len(a['positions']),inventory_shares=0,live_buy_orders=len(a['buys']),exit_obligations=len(a['exits']),budget_pending=len(pending),budget_reserve=b.resources()[2],budget_lots=len(b.lots),
   ACT=a['risk_state'],C1=getattr(b,'c1',None),budget_gross_negative_realized_plus_fees_record_only=sum(b.losses.values()),budget_loss_keys=len(b.losses),loss_policy=b.exhausted_policy,
   canonical_consumed=len(b.consumed),stock_request_ids=len(b.stock_requests),core_epoch_locks=len(a['core_epoch']),used_events=len(a['used_events']),paid_dividend_ids=len(a['paid_dividends']),unpaid_dividend_count=len(a['dividends']),
   strategy_watch=len(a['watch']),pending_intents=len(a['pending']),sector_states=dict(sectors),active_attempts=sum(s.active for s in b.sectors.values()),total_sector_states=len(b.sectors),
   runner_epoch=len(p['runner']['epoch']),runner_last_epoch=len(p['runner']['last_epoch']),global_watch=len(p['runner']['global_watch']),applied_actions=len(p['runner']['applied_actions']),
   trades=len(a['trades']),cumulative_fees=a['fees_cny'])
  if ref=='C1':b.c1.validate();assert b.c1.high==D(1000000) and b.c1.fraction==D('.10') and b.c1.decision_nav==a['current_nav']
  output[ref]=dict(checkpoint=str(path),SHA256=expected,generation_provenance=str(path.with_suffix('.provenance.json')),generation_engine_identity=old,
   original_frozen_sources_unchanged=len(p['source_freeze']),current_trading_class_and_all3_functions_exact=True,shared_export_runtime_source_exact=True,
   final_book_fields_exact=exact,budget_final_book_exact=True,all5_complete_event_streams_exact=streams,state=state,
   account_fields_preserved=len(a),runner_fields_preserved=len(p['runner']),full_state_stays_in_original_checkpoint=True,
   prefix_or_restore_not_run_now=True,no_old_provenance_backfill=True,no_new_account_or_market_event=True)
 save('CHECKPOINT_READINESS.json',dict(passed=True,read_only=True,accounts=output,seconds=time.monotonic()-started,
  future_extension_import='Explicit verified import of these known-identity saved objects into separately frozen 2023 input horizon; compare every account/strategy field before first event, bind new identity. Do not disable existing source/identity guard or rewrite old provenance.',
  Bdiag_has_no_C1_H_field=True,new_accounts=0,new_account_events=0))
 print(json.dumps(J.W.canon({k:v['state'] for k,v in output.items()}),ensure_ascii=False,default=str),flush=True)
 print('CHECKPOINT_PASS',round(time.monotonic()-started,3),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('CHECKPOINT_ERROR.json',dict(reason=str(e),traceback=traceback.format_exc(),new_accounts=0));raise
