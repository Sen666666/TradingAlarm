"""Authorized small native prefix only, outputs confined to independent review."""
from pathlib import Path
from collections import Counter
import sys,json,gzip,hashlib,ast,importlib.util,gc
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;sys.path.insert(0,str(P))
import load_inputs as V
from indicator_provider import IndicatorProvider
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
adapter=P/'native_adapter/trend_exit_adapter.py';assert sha(adapter)=='22ab39fea5ce380d9a40942d21c7a47a5f10ae5b3b127d60c029e75cc90b9df6'
sources={str(p):sha(p) for p in [adapter,P/'run_account.py',P/'run_control.py',P/'load_inputs.py',P/'STATE_MACHINE_FREEZE.json',P/'PROTOCOL.txt',P/'indicator_provider.py',P/'indicators/MANIFEST.json']}
old=ast.parse((P/'run_account.py').read_text());new=ast.parse((P/'run_control.py').read_text());oo=next(x for x in old.body if isinstance(x,ast.FunctionDef) and x.name=='execute');nn=next(x for x in new.body if isinstance(x,ast.FunctionDef) and x.name=='execute')
# Corrected loader must be the only execute-body change: old nonexistent import
# becomes J.W.load + build method, and its source-freeze path follows the real file.
ss=ast.unparse(nn);ss=ss.replace("M = J.W.load('trend_exit_v1_frozen_adapter', O / 'native_adapter/trend_exit_adapter.py')\n            build_runner_class = M.build_runner_class","from native_adapter.early_adapter import build_runner_class").replace("'native_adapter/trend_exit_adapter.py'","'native_adapter/early_adapter.py'")
assert ast.dump(ast.parse(ss),include_attributes=False)==ast.dump(ast.Module(body=[oo],type_ignores=[]),include_attributes=False),'non-loader economic change'
value=V.inputs('2022_2024');shared,receipts,cp,states,ir,identity=value;cut='2022-01-07';shared=J.W.physical(shared,cut);receipts={s:{d:r for d,r in rr.items() if d<=cut} for s,rr in receipts.items()};cp={s:f.loc[:cut] for s,f in cp.items()};states={s:[r for r in rr if r['day']<=cut] for s,rr in states.items()};ir={k:r for k,r in ir.items() if r['confirmed_day']<=cut};provider=IndicatorProvider();results={};C=Counter()
for arm in ['ORIGINAL_NATIVE','BASELINE','EARLY_EMA20','EARLY_EMA60','EARLY_BOLL20_MID','EARLY_BOLL20_LOWER']:
 out=O/'native_prefix'/arm;assert not out.exists();out.mkdir(parents=True)
 if arm=='ORIGINAL_NATIVE':cls=A.Runner
 else:
  mod=J.W.load('independent_prefix_'+arm,adapter);cls=mod.build_runner_class(A,provider,arm)
 r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=sources;a=r.accounts['B'];assert a.available==a.initial_cash==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits;C['fresh_accounts']+=1
 r.assert_native_wiring()
 with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):done=r.run_prepared(out,120,end=cut)
 assert done and len(r.daily)==4 and r.daily[0]['at'].date().isoformat()=='2022-01-04';C['short_prefix_completed']+=1
 book=read(out/'pair/B.json.gz');daily=read(out/'pair/daily.jsonl.gz');results[arm]=dict(closes=len(daily),trades=len(book['trades']),ending_NAV=book['ending_NAV'],tool_policy_records=len(getattr(r,'trend_exit_log',[])),tool_requests=sum(bool(x['added_indicator_layer_ids']) for x in getattr(r,'trend_exit_log',[])),baseline_book_equal=None)
 if arm=='ORIGINAL_NATIVE':goldbook=book;golddaily=daily
 elif arm=='BASELINE':assert book==goldbook and daily==golddaily;results[arm]['baseline_book_equal']=True;C['full_prefix_book_daily_identity']+=1
 if arm.startswith('EARLY_'):
  for z in r.trend_exit_log:
   at=J.M.N.iso(z['at']);q=provider.at(z['sid'],at,arm[6:]);assert z['indicator']==q and z['native_ACT_on'] and z['native_I_target'];broken=q['status']=='READY' and q['causal_close']<q['line'];assert z['indicator_break']==broken;assert not(set(z['added_indicator_layer_ids'])&set(z['prior_pending_layer_ids']));assert bool(z['added_indicator_layer_ids'])==(z['request_reason'] is not None);C['all_real_hook_records']+=1
  for t in book['trades']:
   assert t['at'][11:19]=='09:30:00'
   if t['side']=='sell':
    fill=next(x for x in book['audit'] if x['kind']=='fill' and x['receipt']['receipt_id']==t['receipt_id']);request=next(x for x in book['audit'] if x['kind']=='exit_request' and x['event_id']==fill['order_id']);assert request['at']<t['at'];C['next_legal_clock_actual_sell']+=1
 del r,a;gc.collect();print('PREFIX_DONE',arm,results[arm],flush=True)
assert all(sha(p)==h for p,h in sources.items())
out=dict(status='PASS_SOURCE_AND_NATIVE_SHORT_PREFIX',checks=dict(C),window=['2022-01-04',cut],results=results,source_sha256=sources,v1_v2_only_plugin_loader_change=True,source_insertion='One original planning insertion after old mobile-floor check/ratchets; unchangedACT>I>CP priority, exact original opening/route/account methods asserted at true initialization.',limits=['Six native accounts are deliberately short independent-prefix validation; only four market closes, no full candidate result.','Indicator numerical/source validation reused all-symbol receipt; no recomputation.','Zero requests in a particular short arm is not evidence of zero full-period coverage. Pure current/equality/UNKNOWN/CP-locked branches separately checked.','Full726/242 original baseline identity and full alternative money/clock audit still required.'])
(O/'ADAPTER_NATIVE_PREFIX_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
