"""Independent physical Jan2022 prefix; no complete candidate account."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import sys,json,gzip,hashlib,gc
O=Path(__file__).resolve().parent;F=O.parent;P=F.parent;R=P.parent/'trend_exit_controls_v1'
sys.path.insert(0,str(R));import load_inputs as V
sys.path.insert(0,str(F));from variant_provider import VariantProvider
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
adapter=P/'native_adapter/mobile_authorization_adapter.py'
assert sha(adapter)=='613eb847576398f100db3bf3778d5825a752ce0daf5f5b25ad8a1f0c8b8f4a77'
sources={str(p):sha(p) for p in [adapter,P/'H2_POLICY_FREEZE.json',F/'variant_provider.py',F/'contexts/MANIFEST.json',F/'ROBUSTNESS_FREEZE.json',F/'run_robust_account.py',R/'load_inputs.py',Path(__file__)]}
shared,receipts,cp,states,ir,identity=V.inputs('2022_2024');cut='2022-01-21'
shared=J.W.physical(shared,cut);receipts={s:{d:r for d,r in rr.items() if d<=cut} for s,rr in receipts.items()};cp={s:f.loc[:cut] for s,f in cp.items()};states={s:[r for r in rr if r['day']<=cut] for s,rr in states.items()};ir={k:r for k,r in ir.items() if r['confirmed_day']<=cut}
provider=VariantProvider(20,20);data=provider.data;di=int(__import__('numpy').datetime64(cut,'D').astype('int64'))
for sid,q in provider.data.items():
 keep=q['days']<=di
 for k,v in list(q.items()):
  if hasattr(v,'shape') and len(v.shape)>0 and len(v)==len(keep):q[k]=v[keep]
C=Counter();results={};examples=[]
cost=J.W.load('independent_h2_cost150',F/'cost_adapter/cost_stress.py');extra=cost.apply_cost_stress(V);sources.update(extra['source_freeze']);specs=read(F/'ROBUSTNESS_FREEZE.json')['cost_variants']
for spec in specs:
 arm=spec['label'];provider=VariantProvider.__new__(VariantProvider);provider.data=data;provider.relative=spec['R'];provider.ema=spec['EMA'];provider.manifest_sha256=__import__('hashlib').sha256((sha(F/'contexts/MANIFEST.json')+'|RS'+str(spec['R'])+'|EMA'+str(spec['EMA'])).encode()).hexdigest()
 out=O/'cost_physical_prefix'/arm;assert not out.exists();out.mkdir(parents=True)
 mod=J.W.load('I_h2_independent_parameter_prefix_'+arm,adapter);cls=mod.build_runner_class(A,provider,spec['mode'])
 r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);cost.configure_runner(r);cost.assert_cost_stress_runner(r);r.source_freeze=sources;a=r.accounts['B']
 assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits
 with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out,180,end=cut)
 book=read(out/'pair/B.json.gz');daily=read(out/'pair/daily.jsonl.gz');logs=read(out/'pair/mobile-authorization-policy.jsonl.gz') if arm else []
 cost.assert_cost_stress_runner(r);assert a.cost_multiplier==D('1.5') and J.LR.SLIP==D('.00075')
 paid={};accrued={}
 for event in book['audit']:
  if event['kind']!='fill':continue
  receipt=event['receipt'];oid=event['order_id'];sid=receipt['security_id'];side=receipt['side'];at=J.M.N.iso(receipt['at']);schedule=r.market.fees(sid,at);assert schedule.schedule_id==event['fee_schedule'];gross=D(receipt['gross_cny']);qq=receipt['shares'];par=r.market.rules.get('security_metadata',{}).get(sid,{}).get('par_value');bp=paid.setdefault(oid,{});ba=accrued.setdefault(oid,{})
  base=cost._ORIGINAL_INCREMENTAL(schedule,side,gross,bp,ba,1,shares=qq,par_value=par)
  assert set(base)==set(event['fee_components'])
  for name,v in base.items():assert D(event['fee_components'][name])==D('1.5')*v;bp[name]=bp.get(name,D(0))+v;C['actual_scaled_fee_component']+=1
  for name,v in cost._ORIGINAL_ACCRUAL(schedule,side,gross,1,shares=qq,par_value=par).items():ba[name]=ba.get(name,D(0))+v
  price=D(event['raw_open'])*(1+D('.00075') if side=='buy' else 1-D('.00075'));assert D(event['price'])==price and gross==price*qq;C['actual_7p5bp_gross_price']+=1
 for event in book['audit']:
  if event['kind']!='reserve':continue
  schedule=r.market.fees(event['sid'],J.M.N.iso(event['at']));assert schedule.schedule_id==event['fee_schedule'];q=event['target_shares'];gross=D(event['gross_budget_cny']);par=r.market.rules.get('security_metadata',{}).get(event['sid'],{}).get('par_value');fee=sum(cost._ORIGINAL_INCREMENTAL(schedule,'buy',gross,{}, {},1,shares=q,par_value=par).values(),D(0))*D('1.5');assert fee==D(event['fee_reserved_cny']);C['reserve_actual_scaled_fee']+=1
 layers={x['id']:x for x in book['layers']};buys={x['layer']:x for x in book['trades'] if x['side']=='buy'};fills={x['receipt']['receipt_id']:x for x in book['audit'] if x['kind']=='fill' and x['receipt']['side']=='sell'};requests={x['event_id']:x for x in book['audit'] if x['kind']=='exit_request'}
 positives=[];denies=[];actual=[]
 for z in logs:
  q=provider.at(z['sid'],z['at']);assert q==z['context'];rr=(q['RS20']<=0) if q['ready_R'] else None;pp=(q['close']<q['EMA20']) if q['ready_P'] else None
  weak=(rr and pp) if q['ready_R'] and q['ready_P'] else None;assert q['RS_window']==spec['R'] and q['EMA_span']==spec['EMA'] and q['RS20']==q['RS_value'] and q['EMA20']==q['EMA_value']
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
assert C['actual_overlay_part_Tplus1_checked']>0 and C['actual_scaled_fee_component']>0 and C['reserve_actual_scaled_fee']>0
assert sum(v['mobile_denials'] for v in results.values())>0
assert all(sha(p)==h for p,h in sources.items())
result=dict(status='PASS_PHYSICAL_POSITIVE_NATIVE_PREFIX',source_sha256=sources,cut=cut,checks=dict(C),results=results,examples=examples,scope='2 fresh same-physical-source Jan21 short prefixes BASE_COST150 and JOINT_COST150 only. Originalfee arithmetic independently rescaled at each actual fill and reserve; actual7.5bp OPEN and original native fee/quantity/T+1 paths. No full strategy effectiveness claim.')
(O/'COST_NATIVE_POSITIVE_PREFIX_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
