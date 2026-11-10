"""Independent physical Jan2022 prefix; no complete candidate account."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import sys,json,gzip,hashlib,gc
O=Path(__file__).resolve().parent;P=O.parent;R=P.parent/'trend_exit_controls_v1'
sys.path.insert(0,str(R));import load_inputs as V
sys.path.insert(0,str(P));from context_provider import ContextProvider
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
adapter=P/'native_adapter/mobile_authorization_adapter.py'
assert sha(adapter)=='613eb847576398f100db3bf3778d5825a752ce0daf5f5b25ad8a1f0c8b8f4a77'
sources={str(p):sha(p) for p in [adapter,P/'H2_POLICY_FREEZE.json',P/'context_provider.py',P/'relative_context/MANIFEST.json',R/'load_inputs.py',Path(__file__)]}
shared,receipts,cp,states,ir,identity=V.inputs('2022_2024');cut='2022-01-21'
shared=J.W.physical(shared,cut);receipts={s:{d:r for d,r in rr.items() if d<=cut} for s,rr in receipts.items()};cp={s:f.loc[:cut] for s,f in cp.items()};states={s:[r for r in rr if r['day']<=cut] for s,rr in states.items()};ir={k:r for k,r in ir.items() if r['confirmed_day']<=cut}
provider=ContextProvider();di=int(__import__('numpy').datetime64(cut,'D').astype('int64'))
for sid,q in provider.data.items():
 keep=q['days']<=di
 for k,v in list(q.items()):
  if hasattr(v,'shape') and len(v.shape)>0 and len(v)==len(keep):q[k]=v[keep]
C=Counter();results={};examples=[]
for arm in ['ORIGINAL_NATIVE','BASE','R_ONLY','P_ONLY','JOINT']:
 out=O/'h2_physical_prefix'/arm;assert not out.exists();out.mkdir(parents=True)
 if arm=='ORIGINAL_NATIVE':cls=A.Runner
 else:
  mod=J.W.load('I_h2_independent_prefix_'+arm,adapter);cls=mod.build_runner_class(A,provider,arm)
 r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=sources;a=r.accounts['B']
 assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits
 with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out,180,end=cut)
 book=read(out/'pair/B.json.gz');daily=read(out/'pair/daily.jsonl.gz');logs=read(out/'pair/mobile-authorization-policy.jsonl.gz') if arm!='ORIGINAL_NATIVE' else []
 if arm=='ORIGINAL_NATIVE':goldbook=book;golddaily=daily
 if arm=='BASE':assert book==goldbook and daily==golddaily;C['BASE_full_book_daily_exact']+=1
 layers={x['id']:x for x in book['layers']};buys={x['layer']:x for x in book['trades'] if x['side']=='buy'};fills={x['receipt']['receipt_id']:x for x in book['audit'] if x['kind']=='fill' and x['receipt']['side']=='sell'};requests={x['event_id']:x for x in book['audit'] if x['kind']=='exit_request'}
 positives=[];denies=[];actual=[]
 for z in logs:
  q=provider.at(z['sid'],z['at']);assert q==z['context'];rr=(q['RS20']<=0) if q['ready_R'] else None;pp=(q['close']<q['EMA20']) if q['ready_P'] else None
  weak=rr if arm=='R_ONLY' else pp if arm=='P_ONLY' else (rr and pp) if q['ready_R'] and q['ready_P'] else None
  assert z['decision']['denies_mobile']==(weak is True)
  if z['phase']=='new_mobile_role_before_pending':
   assert z['role']=='mobile' and z['allowed']==(weak is not True) and z['CP1_id'];C['native_role_hook_checked']+=1
   if not z['allowed']:denies.append(z)
  else:
   assert z['native_ACT_on'] and z['native_I_target'] and z['core_exit_ids_added']==[]
   live={lid for lid,x in layers.items() if x['sid']==z['sid'] and x['kind']=='add' and x['opened']<=z['at'] and (not x.get('closed') or z['at']<x['closed'])}
   assert set(z['live_mobile_layer_ids'])==live
   assert set(z['added_mobile_exit_layer_ids'])==(live-set(z['prior_pending_layer_ids']) if weak is True else set());C['native_held_hook_checked']+=1
   if z['added_mobile_exit_layer_ids']:positives.append(z)
 for t in book['trades']:
  assert t['at'][11:19]=='09:30:00'
  if t['side']!='sell':continue
  f=fills[t['receipt_id']];rq=requests[f['order_id']];assert rq['at']<t['at'];assert sum((D(v) for v in f['fee_components'].values()),D(0))==D(t['fees_cny']);C['native_sell_fee_clock_checked']+=1
  for part in t['parts']:
   if not part['reason'].startswith('mobile_authorization_'):continue
   lid=part['layer'];b=buys[lid];assert layers[lid]['kind']=='add';market=shared[1].lines[t['security_id']].market;sellable=shared[1].lag(market,J.M.N.iso(b['at']),shared[1].protocol['sellable_lag_sessions'][market]);assert J.M.N.iso(t['at'])>=sellable
   zz=[z for z in positives if lid in z['added_mobile_exit_layer_ids'] and z['sid']==t['security_id'] and z['at']<t['at']];assert zz;C['actual_overlay_part_Tplus1_checked']+=1
   actual.append(dict(layer=lid,sid=t['security_id'],buy_at=b['at'],overlay_at=zz[0]['at'],order_at=rq['at'],fill_at=t['at'],reason=part['reason'],shares=part['shares'],fees=t['fees_cny']))
 results[arm]=dict(closes=len(daily),trades=len(book['trades']),ending_NAV=book['ending_NAV'],overlay_requests=len(positives),mobile_denials=len(denies),actual_overlay_parts=len(actual))
 if actual:examples.append(dict(arm=arm,actual=actual[0]))
 if denies:examples.append(dict(arm=arm,denial=denies[0]))
 print('H2_PREFIX_DONE',arm,results[arm],flush=True);del r,a;gc.collect()
assert C['actual_overlay_part_Tplus1_checked']>0 and C['BASE_full_book_daily_exact']==1
assert sum(v['mobile_denials'] for v in results.values())>0
assert all(sha(p)==h for p,h in sources.items())
result=dict(status='PASS_PHYSICAL_POSITIVE_NATIVE_PREFIX',source_sha256=sources,cut=cut,checks=dict(C),results=results,examples=examples,scope='5 fresh short prefixes only; original and BASE exact full book/daily, all 3 modes same physical source cutoff incl provider. No full candidate effectiveness claim.')
(O/'H2_NATIVE_POSITIVE_PREFIX_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
