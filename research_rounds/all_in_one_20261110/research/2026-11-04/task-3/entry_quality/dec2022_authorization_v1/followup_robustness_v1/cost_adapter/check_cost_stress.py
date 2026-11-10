"""Native query/fees/preview and empty-book checkpoint checks; no financial run."""
from pathlib import Path
from decimal import Decimal as D
from types import SimpleNamespace
import sys,json,hashlib,time,inspect,pickle
O=Path(__file__).resolve().parent
H=O.parents[1]
T=H.parent/'trend_exit_controls_v1'
sys.path[:0]=[str(T),str(O)]
import load_inputs as V
import cost_stress as C

def main():
 t=time.monotonic();meta=C.apply_cost_stress(V)
 shared,receipts,cp,states,ir,identity=V.inputs('strong')
 bundle,market,facts=shared;J=V.J
 F=market.__class__.__mro__[1].fees.__globals__['FeeSchedule']
 FC=market.__class__.__mro__[1].fees.__globals__['FeeComponent']
 assert F.incremental is C.stressed_incremental
 feechecks=[];partialchecks=[]
 for venue,versions in market.rules['fee_versions'].items():
  for ver in versions:
   spec=ver['schedule'];s=F(spec['schedule_id'],tuple(FC(**x) for x in spec['components']))
   for side in ('buy','sell'):
    # Include the cumulative minimum, rate crossover, share and par-value bases.
    for qty,p in [(100,D('1')),(100,D('10')),(1000,D('100')),(100000,D('1000'))]:
     kw=dict(shares=qty,par_value=D(1));base=C._ORIGINAL_INCREMENTAL(s,side,D(qty)*p,{}, {},1,**kw)
     got=s.incremental(side,D(qty)*p,{}, {},D('1.5'),**kw)
     assert got=={k:v*D('1.5') for k,v in base.items()},(venue,ver['from'],side,qty,got,base)
     assert s.incremental(side,D(qty)*p,{}, {},1,**kw)==base
     feechecks.append(dict(venue=venue,start=ver['from'],side=side,qty=qty,price=str(p),base={k:str(v)for k,v in base.items()},stress={k:str(v)for k,v in got.items()}))
    a=SimpleNamespace(cost_multiplier=D('1.5'))
    order=SimpleNamespace(fees_local={},fee_accrued_local={},local_notional=D(0))
    bp={};ba={};parts=[]
    for qty,p in [(100,D('1')),(100,D('3')),(1000,D('100')),(400,D('25'))]:
     local=D(qty)*p;kw=dict(shares=qty,par_value=D(1))
     b=C._ORIGINAL_INCREMENTAL(s,side,local,bp,ba,1,**kw)
     got=J.BP.L.SectorAccount._fee(a,order,s,side,local,**kw)
     assert got=={k:v*D('1.5') for k,v in b.items()}
     J.BP.L.SectorAccount._remember_fees(a,order,s,side,local,got,**kw)
     for k,v in b.items():bp[k]=bp.get(k,D(0))+v
     for k,v in C._ORIGINAL_ACCRUAL(s,side,local,1,**kw).items():ba[k]=ba.get(k,D(0))+v
     assert order.fees_local=={k:v*D('1.5')for k,v in bp.items()}
     assert order.fee_accrued_local=={k:v*D('1.5')for k,v in ba.items()}
     parts.append(dict(qty=qty,price=str(p),fee={k:str(v)for k,v in got.items()},cumulative={k:str(v)for k,v in order.fees_local.items()}))
    partialchecks.append(dict(venue=venue,start=ver['from'],side=side,parts=parts))
 # Build empty native runner only; no financial event is advanced.
 M=J.W.load('cost_probe_mobile_authorization',H/'native_adapter/mobile_authorization_adapter.py')
 cls=M.build_runner_class(V.A,None,'BASE')
 r=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir)
 config=C.configure_runner(r);r.source_freeze={**M.source_freeze(V.A),**meta['source_freeze']}
 assert C.assert_cost_stress_runner(r)
 querychecks=[]
 for sid,day,nextday in [('000001.SZ','2025-07-01','2025-07-02'),('600000.SH','2025-07-01','2025-07-02'),('688041.SH','2025-07-01','2025-07-02')]:
  if sid not in market.lines:continue
  at=J.M.N.iso(day+'T15:10:00+08:00');op=J.M.N.iso(nextday+'T09:30:00+08:00');quote=market.quote(sid,at);assert quote
  for side in ('buy','sell'):
   base=C._ORIGINAL_WINDOW(market,sid,op,side,1);got=market.window(sid,op,side,1)
   assert (base is None)==(got is None)
   if got:
    expected=base.raw_open*(D(1)+C.SLIPPAGE if side=='buy' else D(1)-C.SLIPPAGE)
    assert got.execution_price==expected
    assert C.replace(got,execution_price=base.execution_price)==base
    querychecks.append(dict(sid=sid,at=str(op),side=side,raw_open=str(base.raw_open),base_price=str(base.execution_price),stress_price=str(got.execution_price),other_fields_exact=True))
  i=dict(sid=sid,quote=quote,floor=quote.raw_price*D('.95')*facts.factor(sid,at),kind='core',weight=1)
  J.LR.resize_core(i,D(1000000),facts.factor(sid,at))
  assert i['reference_price']==quote.raw_price*(D(1)+C.SLIPPAGE)
  win=market.window(sid,op,'buy',1)
  if win:
   pv,why=J.LR.preview(i,win.raw_open,facts.factor(sid,op),market.quantity(sid,op),market.fees(sid,op))
   if pv:
    assert pv['price']==win.execution_price
    qty=pv['minq'];fee=J.LR.fees(qty,pv['price'],pv['schedule'],'buy',quote.par_value)
    order=SimpleNamespace(fees_local={},fee_accrued_local={})
    actual=sum(J.BP.L.SectorAccount._fee(r.accounts['B'],order,pv['schedule'],'buy',D(qty)*pv['price'],shares=qty,par_value=quote.par_value).values(),D(0))
    assert fee==actual
    querychecks.append(dict(sid=sid,core_resize_and_preview_exact=True,reference_price=str(i['reference_price']),actual_open_price=str(pv['price']),preview_and_actual_minimum_fee=str(fee)))
   else:querychecks.append(dict(sid=sid,native_preview_rejection=why))
 # Empty technical serialization has no claimed completed financial event.
 # The ranking-export checkpoint requires a real completed date. This probe
 # deliberately calls its original parent serializer with None, never inventing
 # a completed market event for an empty book.
 dest=O/'cold_checkpoint_probe';assert not dest.exists();V.L.PreparedRunner.checkpoint(r,dest,None)
 cold=pickle.loads((dest/'checkpoint.pkl').read_bytes())
 assert cold['last_completed_event'] is None
 assert cold['runner']['cost_stress_version']==C.VERSION
 assert cold['accounts']['B']['cost_multiplier']==D('1.5')
 r2=cls(shared,receipts,stock_cp=cp,industry_states=states,industry_receipts=ir);C.configure_runner(r2);r2.source_freeze=r.source_freeze
 assert r2.restore(dest/'checkpoint.pkl') is None
 assert C.assert_cost_stress_runner(r2)
 assert not r2.daily and not r2.accounts['B'].trades and r2.accounts['B'].available==D(1000000)
 assert all(C.sha(p)==h for p,h in r.source_freeze.items())
 result=dict(status='PASS_NATIVE_FEE_QUERY_PREVIEW_AND_EMPTY_CHECKPOINT',fee_function_checks=len(feechecks),partial_order_checks=len(partialchecks),query_checks=querychecks,empty_checkpoint_restore=True,new_complete_accounts=0,financial_events_advanced=0,metadata=meta,configuration=config,fee_cases=feechecks,partial_cases=partialchecks,seconds=time.monotonic()-t,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 (O/'CHECKS.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k]for k in ('status','fee_function_checks','partial_order_checks','empty_checkpoint_restore','new_complete_accounts','financial_events_advanced','seconds')},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
