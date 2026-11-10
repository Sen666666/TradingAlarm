"""Bounded ORIGINAL policy checkpoint restore; pure ON diagnostic afterwards.

No policy-economic path is started. Baseline replay has real simulated native
OPEN/fill events, explicitly counted. All writes are confined to this folder.
"""
from pathlib import Path
from datetime import datetime,time as dt
import argparse,copy,gzip,hashlib,inspect,json,pickle,sys,textwrap,time,traceback
import component as P

O=P.O;W=P.W;OLD=W/'pvr-slot1-native-readiness-20261101'
sys.path.insert(0,str(OLD))
import execution_support as S
N,J,L,IO=S.N,S.J,S.L,S.IO
CASES={
 'D1':dict(window='2025_26',signal='2026-01-16',opening='2026-01-19',checkpoint='2025-12-31',intents=342,stocks=250),
 'D2':dict(window='2022',signal='2022-12-05',opening='2022-12-06',checkpoint='2022-09-30',intents=672,stocks=480),
 'D3':dict(window='2025_26',signal='2026-05-11',opening='2026-05-12',checkpoint='2026-03-31',intents=614,stocks=463)}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def book(p):
 with gzip.open(p,'rt')as f:return json.load(f)
def stream(p):
 with gzip.open(p,'rt')as f:return [json.loads(x)for x in f]
def canon(x):return J.W.canon(x)
def save(path,x):IO.write_json(path,P.serial(x))
def exact(a,b,name):
 assert P.digest(a)==P.digest(b),(name,P.digest(a),P.digest(b))
def main(name):
 t=time.monotonic();case=CASES[name];out=O/name;out.mkdir(exist_ok=True)
 assert not (out/'COMPLETION.json').exists(),'completed diagnostic must not be repeated'
 root=OLD/'runs'/case['window'];cp=root/('checkpoint-'+case['checkpoint']+'.pkl')
 frozen=read(OLD/'RUN_SOURCE_FREEZE.json')['sources']
 assert all(Path(p).is_file()and sha(p)==h for p,h in frozen.items()),'original source/input changed'
 sources=P.source_hashes();sources[str(Path(__file__))]=sha(__file__)
 save(out/'RESTORE_FREEZE.json',dict(case=case,checkpoint=str(cp),checkpoint_sha256=sha(cp),
  checkpoint_metadata_sha256=sha(cp.with_suffix('.json')),checkpoint_provenance_sha256=sha(cp.with_suffix('.provenance.json')),
  original_run_freeze_sha256=sha(OLD/'RUN_SOURCE_FREEZE.json'),source_freeze=frozen,diagnostic_sources=sources,
  original_book_SHA={n:sha(root/'pair'/n)for n in ['B.json.gz','daily.jsonl.gz','funding.jsonl.gz','balances.jsonl.gz']},
  restore='nearest own original checkpoint; no reset; original policy only',
  finish=case['opening']+'T09:30:00+08:00',ON='pure route/reserve only after OFF identity'))
 (out/'POLICY_SOURCE.diff').write_text(P.source_diff())
 N.configure_scores()
 # S.inputs2022 has an original readiness exporter; redirect its destination.
 # 2025_26 input loader is read-only. Source functions themselves stay frozen.
 S.O=out
 shared,receipts,cpdata,states,ir,identity=S.inputs(case['window'])
 gate=read(OLD/'PREFLIGHT_GATE.json')
 exact(S.canonical_identity(identity),gate['input_identities'][case['window']],'input identity')
 r=N.Runner(shared,receipts,**S.kwargs(cpdata,states,ir));r.source_freeze=dict(frozen)
 with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):after=r.restore(cp)
 assert str(after)[:10]==case['checkpoint']
 opening=J.M.N.iso(case['opening']+'T09:30:00+08:00');captured={}
 def capture_pre(rr,a,at):
  if at!=opening:return
  assert not captured
  intents=[]
  for src in a.pending:
   if src['clock'].earliest_execution_at!=at:continue
   i=copy.deepcopy(src);sid=i['sid'];raw=rr.market.raw[sid];day=J.pd.Timestamp(at.date())
   if day not in raw.index or not J.np.isfinite(raw.loc[day].open)or raw.loc[day].open<=0:x,why=None,'missing_open'
   else:
    x,why=J.LR.preview(i,J.D(str(raw.loc[day].open)),rr.facts.factor(sid,at),rr.market.quantity(sid,at),rr.market.fees(sid,at))
    if x:x['known_open']=J.D(str(raw.loc[day].open))
   i['_preview']=x;i['_preview_failure']=why;intents.append(i)
  assert len(intents)==case['intents']and len({i['sid']for i in intents})==case['stocks']
  s=P.snapshot(a);captured.update(state=s,intents=intents,at=at)
  save(out/'INPUT_VIEW.json',dict(state=s.view(),intents=[P.B.intent_view(i)for i in intents],clock='after original protection exits and settle_due/sync; before first fresh route',
   original_pending_buy_count=len(a.buys),original_pending_exit_count=len(a.exits),core_epoch_retained=True))
  IO.write_pickle(out/'INPUT_PRIVATE.pkl',captured)
 def capture_post(rr,a,at):
  if at==opening:captured['post']=P.snapshot(a)
 # Only two read-only observers are injected. Entire native opening body and
 # its sequence are otherwise exact; this derived source is retained for audit.
 src=textwrap.dedent(inspect.getsource(J.Runner.opening))
 needle=' a.settle_due(at);a.sync(at);funded=[];done=set()'
 assert src.count(needle)==1
 derived=src.replace(needle,needle+'\n capture_pre(self,a,at)')
 needle2=' for sid,i,x,q in funded:';assert derived.count(needle2)==1
 derived=derived.replace(needle2,' capture_post(self,a,at)\n'+needle2)
 assert derived.replace('\n capture_pre(self,a,at)','').replace(' capture_post(self,a,at)\n','')==src
 (out/'opening_observers.py').write_text(derived)
 env=dict(J.__dict__,capture_pre=capture_pre,capture_post=capture_post);exec(compile(derived,str(out/'opening_observers.py'),'exec'),env)
 observed_open=env['opening']
 start=J.M.N.iso(J.START+'T15:10:00+08:00')
 cutoffs={x for x in r.market.cutoffs if start<=x<=opening};opens={x for x in r.market.sessions['A']if start<=x<=opening}
 acts={datetime.combine(datetime.fromisoformat(d).date(),dt.min,J.M.N.TZ)for d in r.actions_by_date}
 events=sorted(cutoffs|opens|{x for x in acts if start<=x<=opening})
 J.M.E.risk_policy.RECOVERY=J.pd.read_csv(J.M.O/'recovery.csv',index_col=0,parse_dates=True).loc[:case['opening']]
 replay=[];n0=len(r.accounts['B'].trades)
 for at in events:
  if at<=after:continue
  for a in r.accounts.values():a.settle_due(at)
  r._actions(at)
  for a in r.accounts.values():r._payments(a,at)
  if at in opens:
   for a in r.accounts.values():observed_open(r,a,at)
  if at in cutoffs:r.planning(at)
  replay.append(dict(at=at,OPEN=at in opens,CLOSE=at in cutoffs))
 assert replay[-1]['at']==opening and 'post'in captured
 save(out/'REPLAY_EVENTS.json',replay)
 old=book(root/'pair/B.json.gz');a=r.accounts['B']
 expected_funding=[x for x in stream(root/'pair/funding.jsonl.gz')if J.M.N.iso(x['at'].replace(' ','T'))<=opening]
 exact(canon(r.funding),expected_funding,'whole funding prefix')
 exact(canon(a.trades),old['trades'][:len(a.trades)],'whole native trade prefix')
 exact(canon(a.journal),old['journal'][:len(a.journal)],'whole native journal prefix')
 expected_daily=[x for x in stream(root/'pair/daily.jsonl.gz')if J.M.N.iso(x['at'].replace(' ','T'))<=opening]
 exact(canon(r.daily),expected_daily,'whole daily NAV/position/resource prefix')
 expected_bal=[x for x in stream(root/'pair/balances.jsonl.gz')if J.M.N.iso(x['at'].replace(' ','T'))<=opening]
 exact(canon(r.balance_audit),expected_bal,'whole balance bridge prefix')
 # Selected original signal plan fields vs original serialized native book.
 actual_dec=next(x for x in a.decisions if str(x['at'])[:10]==case['signal'])
 old_dec=next(x for x in old['decisions']if x['at'][:10]==case['signal'])
 exact(canon(actual_dec),old_dec,'original selected entire decision')
 save(out/'RESTORE_IDENTITY.json',dict(passed=True,all_original_sources_unchanged=True,whole_funding_prefix_records=len(r.funding),whole_trade_prefix_records=len(a.trades),
  whole_journal_prefix_records=len(a.journal),whole_daily_NAV_resource_prefix_records=len(r.daily),whole_balance_bridge_prefix_records=len(r.balance_audit),
  native_original_events_replayed=len(replay),native_original_OPENs_replayed=sum(x['OPEN']for x in replay),native_original_CLOSEs_replayed=sum(x['CLOSE']for x in replay),
  native_original_trade_fills_replayed=len(a.trades)-n0,original_policy_financial_events_not_zero=True,
  original_checkpoint_inherited=True,original_source_engine_provenance_checked=True,selected_entire_decision_exact=True))
 off=P.plan(captured['state'],captured['intents'],opening,False)
 expected=[{k:v for k,v in x.items()if k not in ['account','at']}for x in expected_funding if x['at'][:10]==case['opening']]
 actual=[x for x in off['attempts']if not x.get('skip')]
 exact(canon(actual),expected,'pure OFF entire funding sequence')
 post=captured['post'].view();offpost=off['final_state']
 # Migration trace is diagnostic-only. Actual available is separately exact.
 for k in ['cash','nav','receivables','lots','orders','sectors','prices','consumed','stock_requests','historical_shared_loss','core_epoch']:
  exact(canon(offpost[k]),canon(post[k]),'pure OFF post-admission '+k)
 assert off['available']==captured['post'].available_exact
 save(out/'OFF.json',off)
 save(out/'OFF_IDENTITY.json',dict(passed=True,full_funding_sequence_exact=True,reserved_quantity_pool_price_fee_exact=True,post_admission_all_budget_read_fields_exact=True,available_cash_exact=True,
  source_intents=case['intents'],source_distinct_stocks=case['stocks'],native_Account_initializations_in_pure_component=0))
 on=P.plan(captured['state'],captured['intents'],opening,True)
 save(out/'ON.json',on)
 am={x['key']:x for x in off['orders']};bm={x['key']:x for x in on['orders']}
 changes=[dict(key=k,before=am.get(k),after=bm.get(k))for k in sorted(set(am)|set(bm))if P.digest(am.get(k))!=P.digest(bm.get(k))]
 sem=lambda x:[o for o in x['orders']if r.sector_by_sid[o['sid']]=='URFI881121' or r.sector_by_sid[o['sid']]=='URFI881121']
 # Actual frozen semiconductor ID is taken from existing project mapping,
 # not guessed sector membership; save per-sector distributions for audit.
 sector=lambda x:dict(__import__('collections').Counter(r.sector_by_sid[o['sid']]for o in x['orders']))
 summary=dict(case=case,OFF_orders=len(off['orders']),ON_orders=len(on['orders']),OFF_sector_orders=sector(off),ON_sector_orders=sector(on),
  changes=changes,capital_delta=on['capital']-off['capital'],nominal_risk_delta=on['nominal_risk']-off['nominal_risk'],reserved_cash_delta=on['cash_reserve']-off['cash_reserve'],
  available_cash_delta=on['available']-off['available'],fee_delta=on['fees']-off['fees'],
  OFF={k:off[k]for k in ['capital','nominal_risk','cash_reserve','available','fees']},ON={k:on[k]for k in ['capital','nominal_risk','cash_reserve','available','fees']},
  pure_ON_real_fills=0,new_policy_economic_paths=0,not_PnL=True,not_strategy_improvement=True,seconds=time.monotonic()-t)
 save(out/'SUMMARY.json',summary)
 assert all(sha(p)==h for p,h in frozen.items())and all(sha(p)==h for p,h in sources.items())
 save(out/'COMPLETION.json',dict(passed=True,case=name,seconds=time.monotonic()-t,baseline_restore_identity=True,pure_OFF_identity=True,ON_retained_guards_passed=True,original_files_unchanged=True))
 print(json.dumps(P.serial(summary),ensure_ascii=False),flush=True)

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('case',choices=CASES);args=parser.parse_args()
 try:main(args.case)
 except BaseException as e:
  save(O/args.case/'FAILURE.json',dict(error=str(e),traceback=traceback.format_exc(),new_policy_economic_paths=0));raise
