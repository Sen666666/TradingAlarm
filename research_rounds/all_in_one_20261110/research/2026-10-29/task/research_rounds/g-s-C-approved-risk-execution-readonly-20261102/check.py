"""Read original C authorization/reserve/fill evidence. No event/preview invocation."""
from pathlib import Path
from decimal import Decimal as D
from dataclasses import asdict
from collections import defaultdict
import sys,pickle,inspect,json,hashlib,time
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-month-continuation-20261102'));import month_runtime as M
sys.path.insert(0,str(W/'g-s-C-cp1-reset-capital-readonly-20261102'));import analyze as A
Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def save(n,x):M.E.IO.write_json(HERE/n,A.clean(x),encoder=M.E.encode)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 start=time.perf_counter();M.guard();rows={};trials={};stats={};source={};prot=read(W/'g-s-C-engineering-causal-readonly-20261102/ALL_PROTECTION_EVENTS.json');layers=read(W/'g-s-C-month-continuation-20261102/july_end_analysis/ALL_LAYERS.json');meta=read(W/'g-s-C-month-continuation-20261102/inputs/2025_26/metadata.json')
 for mode in ['C10','C_BATCH20']:
  arm='2025_26-'+mode;p=W/'g-s-C-month-continuation-20261102/runs'/arm/'2025-07-31-CLOSE.pkl';side=read(p.with_suffix('.provenance.json'));assert sha(p)==side['checkpoint_sha256'];source[str(p)]=sha(p);r=pickle.loads(p.read_bytes());assert r.binding()==side['binding'];a=r.account;before=M.E.digest(M.C.prefix_view(r));smap=defaultdict(list)
  for oid,m in a.supports.items():
   if m.get('C_certificate'):smap[(m['C_certificate'],m['original_intent']['sid'])].append((oid,m))
  lmap={z['layer']:z for z in layers[arm]};pp={z['layer']:z for z in prot[arm]};out=[]
  for res in r.results:
   cert=res['certificate'];v=r.trusted[cert['trusted_id']];ds={d['sid']:d for d in v['demands']}
   assert cert['certificate_id']==M.E.digest({k:v for k,v in cert.items()if k!='certificate_id'})
   for sid,q in cert['Q'].items():
    if not q:continue
    d=ds[sid];pc=D(d['mark'])*D('1.0005');fc=D(d['floor']);Rc=D(q)*max(Z,pc-fc);orders=smap.get((cert['certificate_id'],sid),[]);assert len(orders)<=1
    z=dict(mode=mode,sid=sid,name=meta[sid]['name'],sector=d['sector'],signal_at=cert['known_at'],deadline=cert['deadline'],certificate_id=cert['certificate_id'],receipt_id=d['receipt_id'],use=d['use'],role='mobile',pool='confirmed',
     approved_qty=q,decision_mark=d['mark'],decision_preview_price=pc,decision_effective_floor=fc,approved_nominal_risk=Rc,approved_preview_gross=D(q)*pc,original_dated_quantity_rule=d['quantity'],
     actual_order=None,status='terminal_no_OPEN_in_window'if cert['known_at'][:10]=='2025-07-31'else 'no_native_reservation',actual_layers=[])
    if orders:
     oid,m=orders[0];om=a.order_meta[oid];day=m['created_at'].date().isoformat();factor=D(str(r.inputs.rows('facts',sid,day)['factor']));fo=D(om['floor'])/factor
     audits=[v for v in a.audit_log if v.get('kind')=='reserve'and v.get('order_id')==oid];assert len(audits)==1;au=audits[0];qr=int(au['target_shares']);pr=D(au['gross_budget_cny'])/qr;assert qr==m['quantity']
     cb=[v for v in a.native_callbacks if v.get('kind')=='amend_before_fill'and v.get('order')==oid];qa=int(cb[-1]['q'])if cb else qr;pa=D(cb[-1]['gross'])/qa if cb and qa else pr;auth=r.authority.orders[oid]
     assert auth['ratio']==1,'quantity conversion needs explicit source mapping; never silently compare'
     ownlayers=[lmap[lid]for lid,cm in a.capital_meta.items()if cm['order']==oid];fillq=sum(l['initial_qty']for l in ownlayers);Rfill=Z
     for l in ownlayers:
      assert D(pp[l['layer']]['initial_floor_raw'])==fo and l['opened'][:10]==day;Rfill+=D(l['initial_qty'])*max(Z,D(l['fill_price'])-fo)
     assert qr<=q and qa<=qr and fillq<=qa
     rule=M.C.H.T.QuantityRule(**d['quantity']);raw_cap=int(Rc/(pa-fo))if pa>fo else 0;cap=rule.buy_floor(min(q,qa,raw_cap));Ra=D(qa)*max(Z,pa-fo)
     z['actual_order']=dict(order_id=oid,reserved_at=m['created_at'],reserved_qty=qr,reserved_price=pr,effective_floor=fo,factor_at_creation=factor,original_signal_coordinate_floor=om['floor'],
       reserved_nominal_risk=D(qr)*max(Z,pr-fo),pre_fill_amend_qty=qa,pre_fill_preview_price=pa,pre_fill_nominal_risk=Ra,fill_qty=fillq,actual_filled_initial_risk=Rfill,
       pre_fill_risk_multiple=Ra/Rc if Rc else None,filled_risk_multiple=Rfill/Rc if Rc else None,static_risk_keep_upper_qty=cap,static_bound_below_original_min=0<raw_cap<rule.buy_minimum,
       static_bound_would_reduce_actual_filled_qty=fillq>cap,amend_callbacks=cb,reserve_audit=au,authority_quantity=auth,
       floor_derived_from_original_order_and_dated_factor=True,source_protection_corrobates_all_actual_fills=True,nominal_field_risk_budget_in_meta=om.get('risk_budget'),
       local_bound_only_no_new_account_path=True)
     z['status']='actual_fill'if fillq else 'reserved_zero_fill';z['actual_layers']=ownlayers
    out.append(z)
  rows[arm]=out;tt=[]
  for oid,m in a.supports.items():
   if m.get('C_certificate')or m['original_intent']['sid']not in ['688585.SH','002373.SZ','001267.SZ']:continue
   sid=m['original_intent']['sid'];own=[lmap[lid]for lid,cm in a.capital_meta.items()if cm['order']==oid]
   tt.append(dict(order=oid,sid=sid,name=meta[sid]['name'],signal_at=m['original_intent']['clock'].decision_at,role=m['role'],pool=m['pool'],use=m['use'],CLOSE_approved_qty=None,CLOSE_approved_specific_risk=None,why='independent T/core eligible intent; quantity is created at OPEN, no C quantity certificate',OPEN_reserved_qty=m['quantity'],actual_layers=own,original_intent=m['original_intent']))
  trials[arm]=tt
  actual=[z for z in out if z['actual_order']];fills=[z for z in actual if z['actual_order']['fill_qty']];increased=[z for z in fills if z['actual_order']['filled_risk_multiple']>1];profit=[z for z in increased if sum((D(l['total_contribution'])for l in z['actual_layers']),Z)>0];profit.sort(key=lambda z:(-sum((D(l['total_contribution'])for l in z['actual_layers']),Z),z['sid']))
  stats[arm]=dict(positive_C_certificates=len(out),native_reserved_orders=len(actual),filled_orders=len(fills),reserved_zero_fill=len(actual)-len(fills),filled_risk_increased=len(increased),positive_increased_risk_orders=len(profit),
    largest_positive_increased_risk_control=profit[0]if profit else None,
    actual_filled_risk_total=sum((z['actual_order']['actual_filled_initial_risk']for z in fills),Z),
    source_function_files={n:inspect.getsourcefile(getattr(a,n))for n in ['reserve_quantity','_preview','revalidate']})
  assert before==M.E.digest(M.C.prefix_view(r))and sha(p)==source[str(p)];print(arm,len(out),len(actual),len(fills),'risk_increased',len(increased),flush=True)
 save('ALL_POSITIVE_C_AUTHORIZATIONS.json',rows);save('INDEPENDENT_TRIAL_CONTROLS.json',trials);save('SUMMARY.json',stats);save('SOURCE_READS.json',source);save('CHECKS.json',dict(passed=True,account_events=0,new_preview_calls=0,source_guard=True,complete_saved_state_unchanged=True,seconds=time.perf_counter()-start))
 print('STATIC_READY',round(time.perf_counter()-start,3),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:
  import traceback
  save('ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),account_events=0));raise
