"""Fixed Jan21 physical-forward native integration gate for all four arms."""
from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import sys,json,gzip,hashlib,gc
P=Path(__file__).resolve().parents[1];O=Path(__file__).resolve().parent;sys.path.insert(0,str(P))
import load_inputs as V
from indicator_provider import IndicatorProvider
A,N,J,L,IO=V.A,V.N,V.J,V.L,V.IO
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p)
 with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(x) for x in f] if '.jsonl' in p.name else json.load(f)
prior=read(O/'ADAPTER_NATIVE_PREFIX_AUDIT.json');sources=prior['source_sha256'];assert all(sha(p)==h for p,h in sources.items());shared,receipts,cp,states,ir,identity=V.inputs('2022_2024');cut='2022-01-21';shared=J.W.physical(shared,cut);receipts={s:{d:r for d,r in rr.items() if d<=cut} for s,rr in receipts.items()};cp={s:f.loc[:cut] for s,f in cp.items()};states={s:[r for r in rr if r['day']<=cut] for s,rr in states.items()};ir={k:r for k,r in ir.items() if r['confirmed_day']<=cut};provider=IndicatorProvider();results={};C=Counter();examples=[]
for arm in ['EARLY_EMA20','EARLY_EMA60','EARLY_BOLL20_MID','EARLY_BOLL20_LOWER']:
 out=O/'native_prefix_forward'/arm
 if out.exists():
  assert (out/'DONE.json').exists(),('incomplete own prefix must not rerun',out)
  checkpoint=read(out/'checkpoint.json');assert checkpoint['at'][:10]==cut and checkpoint['source_freeze']==sources;C['completed_own_prefix_readonly_reused']+=1
 else:
  out.mkdir(parents=True);mod=J.W.load('independent_forward_'+arm,P/'native_adapter/trend_exit_adapter.py');cls=mod.build_runner_class(A,provider,arm);r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);r.source_freeze=sources;a=r.accounts['B'];assert a.initial_cash==a.available==a.current_nav==J.D(1000000) and not a.positions and not a.trades and not a.buys and not a.exits;C['fresh_short_accounts']+=1
  with IO.atomic_runner_outputs(r,L,out,canonicalize=J.W.canon):assert r.run_prepared(out,180,end=cut)
  del r,a;gc.collect()
 book=read(out/'pair/B.json.gz');daily=read(out/'pair/daily.jsonl.gz');oldbook=read(O/'native_prefix'/arm/'pair/B.json.gz');olddaily=read(O/'native_prefix'/arm/'pair/daily.jsonl.gz');assert daily[:4]==olddaily and [x for x in book['trades'] if x['at'][:10]<='2022-01-07']==oldbook['trades'];C['Jan7_physical_prefix_exact']+=1
 layers={x['id']:x for x in book['layers']};buys={x['layer']:x for x in book['trades'] if x['side']=='buy'};fills={x['receipt']['receipt_id']:x for x in book['audit'] if x['kind']=='fill' and x['receipt']['side']=='sell'};requests={x['event_id']:x for x in book['audit'] if x['kind']=='exit_request'};tool_logs=read(out/'pair/trend-exit-policy.jsonl.gz');positives=[x for x in tool_logs if x['added_indicator_layer_ids']];actual=[]
 for z in tool_logs:
  at=J.M.N.iso(z['at']);q=provider.at(z['sid'],at,arm[6:]);assert q==z['indicator'];broken=q['status']=='READY' and q['causal_close']<q['line'];assert broken==z['indicator_break'];assert not(set(z['added_indicator_layer_ids'])&set(z['prior_pending_layer_ids']));live={lid for lid,x in layers.items() if x['sid']==z['sid'] and x['opened']<=z['at'] and (not x.get('closed') or z['at']<x['closed'])};assert set(z['added_indicator_layer_ids'])==(live-set(z['prior_pending_layer_ids']) if broken else set());C['all_real_hook_live_membership']+=1
 for t in book['trades']:
  assert t['at'][11:19]=='09:30:00'
  if t['side']!='sell':continue
  f=fills[t['receipt_id']];request=requests[f['order_id']];assert request['at']<t['at'];assert sum((D(v) for v in f['fee_components'].values()),D(0))==D(t['fees_cny']);assert D(t['gross_cny'])==D(f['receipt']['gross_cny']);C['native_actual_sell_fee_clock']+=1
  for part in t['parts']:
   if part['reason']!='trend_early_'+arm[6:]:continue
   lid=part['layer'];b=buys[lid];sid=t['security_id'];market=shared[1].lines[sid].market;lag=shared[1].protocol['sellable_lag_sessions'][market];sellable=shared[1].lag(market,J.M.N.iso(b['at']),lag);assert J.M.N.iso(t['at'])>=sellable;eligible=[z for z in positives if z['sid']==sid and lid in z['added_indicator_layer_ids'] and z['at']<t['at']];assert eligible;z=eligible[0];assert request['at']<=z['at']<t['at'];C['actual_tool_part_Tplus1_and_request']+=1
   rec=dict(arm=arm,layer=lid,sid=sid,buy_at=b['at'],sellable_at=str(sellable),tool_at=z['at'],actual_order_created_at=request['at'],actual_fill_at=t['at'],actual_reason=part['reason'],shares=part['shares'],price=t['price'],gross=t['gross_cny'],fees=t['fees_cny'],part_net_cash=part['net_cash'],receipt_id=t['receipt_id'],indicator=z['indicator'],prior_pending=z['prior_pending_layer_ids']);actual.append(rec)
 if actual:examples.append(actual[0])
 results[arm]=dict(closes=len(daily),trades=len(book['trades']),positive_tool_requests=len(positives),actual_tool_parts=len(actual),ending_NAV=book['ending_NAV'],Jan7prefix_exact=True);print('FORWARD_PREFIX_DONE',arm,results[arm],flush=True)
 if actual:print('POSITIVE_NATIVE_TOOL_GATE',json.dumps(actual[0],ensure_ascii=False),flush=True)
 gc.collect()
assert C['actual_tool_part_Tplus1_and_request']>0 and all(sha(p)==h for p,h in sources.items())
out=dict(status='PASS_POSITIVE_NATIVE_SHORT_PREFIX',checks=dict(C),window=['2022-01-04',cut],results=results,positive_examples=examples,source_sha256=sources,limits=['Four independent short-prefix accounts only; all frozen arms use same physical cutoff and Jan7 states remain exact.','Observed actual tool sales verify native request, OPEN, T+1 and booked fee components. No promise of exchange-realistic fills beyond preserved original proxy.','These short results are integration tests, not full account performance or parameter selection.','Full726/242 baseline identity and alternative account financial/clock audit still required.'])
(O/'ADAPTER_NATIVE_POSITIVE_PREFIX_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps(out,ensure_ascii=False,indent=2))
