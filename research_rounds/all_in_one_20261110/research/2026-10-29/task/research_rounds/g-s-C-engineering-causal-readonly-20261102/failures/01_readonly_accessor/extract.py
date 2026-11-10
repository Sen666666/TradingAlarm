"""Read frozen native accounts/inputs. No account construction, event, or policy replay."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D
from datetime import datetime
import json,pickle,hashlib,sys,math,time
HERE=Path(__file__).resolve().parent;W=HERE.parent;R=W/'g-s-C-month-continuation-20261102';sys.path.insert(0,str(R));import month_runtime as M
Z=D(0);READS={};SECTOR='URFI881268'
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,set)):return [clean(v) for v in x]
 if isinstance(x,float) and not math.isfinite(x):return None
 if isinstance(x,(D,datetime,Path)):return str(x)
 if hasattr(x,'item'):return clean(x.item())
 return x
def read(p):
 p=Path(p);b=p.read_bytes();READS[str(p)]=hashlib.sha256(b).hexdigest();return json.loads(b)
def save(n,x):
 p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(clean(x),ensure_ascii=False,sort_keys=True,indent=2)+'\n');t.replace(p)
def snapshot(arm,day):
 paths=[R/'runs'/arm/(day+'-CLOSE.json'),M.C.HERE/'runs'/arm/'full'/(day+'-CLOSE.json'),M.C.OLD/'runs'/arm/(day+'-CLOSE.json')]
 p=next((p for p in paths if p.exists()),None);assert p,day
 return read(p),str(p)
def load(mode):
 p=R/'runs'/('2025_26-'+mode)/'2025-07-31-CLOSE.pkl';side=read(p.with_suffix('.provenance.json'));assert M.P.sha(p)==side['checkpoint_sha256'];r=pickle.loads(p.read_bytes());assert r.binding()==side['binding'];assert r.last_completed_event.date().isoformat()=='2025-07-31';return r
def main():
 start=time.perf_counter();M.guard();meta=read(R/'inputs/2025_26/metadata.json');ids={s for s,z in meta.items() if z['sector']==SECTOR};eng={};cohorts={};contexts={};orders={};protections={};cp_rows={};sources={}
 for mode in ('C10','C_BATCH20'):
  arm='2025_26-'+mode;r=load(mode);a=r.account;rows=[];ee=[];ctx=[];pp=[]
  facts=r.inputs.table('facts').set_index(['sid','day']);cp=r.inputs.table('cp').set_index(['sid','day']);h=r.inputs.table('h1');hby={d:{z['sid']:z['score'] for z in g.to_dict('records')} for d,g in h.groupby('day')}
  bank={k:json.loads(v) for k,v in a.canonical_registry.items()};result={z['at'][:10]:z for z in r.results};supports=[]
  for oid,s in a.supports.items():
   i=s['original_intent'];rece=s.get('receipt');receipt_id=rece.event_id if rece else None;fill=[z for z in a.layers if a.capital_meta[z['id']]['order']==oid]
   supports.append(dict(oid=oid,sid=i['sid'],sector=s['sector'],signal_at=i['clock'].decision_at,created_at=s['created_at'],deadline=s['deadline'],role=s['role'],pool=s['pool'],use=s['use'],qty=s['quantity'],receipt=receipt_id,filled_qty=sum(z['initial_qty'] for z in fill),layers=[z['id'] for z in fill],original_intent=i))
  orders[arm]=supports
  for mapping in r.mapping:
   day=mapping['at'].date().isoformat();snp,path=snapshot(arm,day);sa=snp['account'];pol=sa['policy'];res=result[day];proj=res['projection'];cert=res['certificate'];trusted=r.trusted[cert['trusted_id']];snap=trusted['snapshot'];ds={z['sid']:z for z in trusted['demands']};trace={z['sid']:z for z in proj['trace']};rank={z['sid']:z for z in mapping['priority']};sc=pol['scopes'][SECTOR]
   assert pol['act']['on'] and pol['incident'] is None,'ACT incident requires original unlock evaluation, not guessed authority'
   full_h={s:hby[day].get(s) for s in r.inputs.sectors};full_order=sorted([s for s,v in full_h.items() if v is not None and math.isfinite(float(v))],key=lambda s:(-full_h[s],s));cq=proj['C_rank_binding']['industry_order']
   oldrows=snap['rows'];owners=[]
   for z in sorted(snap['lots'],key=lambda z:-D(str(z['risk'])))[:10]:owners.append(dict(z,name=meta[z['sid']]['name'],C_priority=proj['C_rank_binding']['stock_priority'].get(z['sid'])))
   ctx.append(dict(day=day,saved_CLOSE=path,industry_F1=sc,global_F1=pol['scopes']['G'],ACT=pol['act'],industry_H1=full_h[SECTOR],industry_rank_all90_1based=full_order.index(SECTOR)+1 if SECTOR in full_order else None,industry_C_queue_1based=cq.index(SECTOR)+1 if SECTOR in cq else None,C_queue_industries=len(cq),decision_NAV=snap['decision_nav'],available=snap['available'],old_capital=sum((D(str(z['capital'])) for z in oldrows),Z),old_risk=sum((D(str(z['risk'])) for z in oldrows),Z),account_risk_reference_before_new_fees=D(str(snap['decision_nav']))*D('.06'),top_old_risk_owners=owners,positive_C_plan=[dict(sid=z['sid'],sector=meta[z['sid']]['sector'],q=z['q'],rank=z['priority']) for z in proj['trace'] if z.get('q')],validation=proj['validation'],context_limit='pre-entire-C-batch snapshot; NOT exact per-candidate shadow prefix; raw trace bounds may coexist'))
   for mm in mapping['stocks']:
    sid=mm['sid'];sec=meta[sid]['sector'];canonical=bank.get(mm['CP1_id']) if mm['CP1_id'] else None;fresh=bool(canonical and canonical['confirmed_day']==day);fr=facts.loc[(sid,day)].to_dict() if (sid,day) in facts.index else None
    if not (fresh or (mm['preliminary'] and not mm['CP1_id']) or sec==SECTOR):continue
    scope=pol['scopes'][sec];g=pol['scopes']['G'];Snew=bool(scope['support'] and scope['permit'] and scope['mature']);Gnew=bool(g['support'] and g['permit']);actual_orders=[z for z in supports if z['sid']==sid and str(z['signal_at'])[:10]==day];c_orders=[z for z in actual_orders if z['role']=='mobile' and z['use'] in ('S','G')];t_orders=[z for z in actual_orders if z['use']=='T'];t=trace.get(sid);d=ds.get(sid);locks=[v for v in pol['locks'].values() if v['sid']==sid and v['remaining']];held=sum(z['qty'] for z in sa['layers'] if z['sid']==sid)
    why=None
    if not fresh:why='no_fresh_CP1_for_C_mobile'
    elif mm['stock_Q'] is not True:why='original_stock_Q_unknown' if mm['stock_Q'] is None else 'original_stock_Q_false'
    elif t is not None:why='C_positive_plan' if t['q'] else 'C_zero_plan_with_recorded_bounds'
    elif sid in sa['buys'] or sid in sa['exits'] or locks:why='native_responsibility_blocks_new_order'
    elif sid in snp['local_wait']:why='target_owned_assets_local_WAIT'
    elif not (Snew or Gnew):why='no_current_new_S_or_G_permission'
    else:why='provider_not_requested_unknown_without_replay'
    qmin=d['quantity']['buy_minimum'] if d else None;preview_price=D(str(d['mark']))*D('1.0005') if d else None
    row=dict(day=day,sid=sid,name=meta[sid]['name'],sector=sec,stock_Q=mm['stock_Q'],original_core_qualified=mm['core_event'],preliminary=mm['preliminary'],barriers=mm['barriers'],fresh_CP1=fresh,canonical=canonical,source_facts=fr,source_H1=hby[day].get(sid),original_stock_priority=rank.get(sid),C_stock_priority=proj['C_rank_binding']['stock_priority'].get(sid),S_scope=scope,G_scope=g,S_new_allowed=Snew,G_new_allowed=Gnew,held_qty_at_CLOSE=held,old_native_buy=sa['buys'].get(sid),old_native_exit=sa['exits'].get(sid),local_wait=snp['local_wait'].get(sid),C_demand=d,C_trace=t,C_Q=proj['Q'].get(sid),stage_class=why,minimum_qty=qmin,close_preview_gross_minimum=D(qmin)*preview_price if qmin else None,close_preview_minimum_nominal_risk=D(qmin)*max(Z,preview_price-D(str(d['floor']))) if qmin else None,C_actual_reserved_orders=c_orders,T_actual_reserved_orders=t_orders,execution_evaluation_censored=day=='2025-07-31',context_day_ref=day)
    if sec==SECTOR:
     row['source_structure']=r.inputs.stock(sid,day,'CLOSE')['structure'];row['raw_bar']=r.inputs.rows('raw',sid,day);row['CP1_trace']=cp.loc[(sid,day)].to_dict() if (sid,day) in cp.index else None;ee.append(row)
    if fresh:rows.append(row)
   del snp
  for z in a.layers:
   m=a.capital_meta[z['id']];s=a.supports[m['order']];i=s['original_intent'];sid=z['sid'];signal=i['clock'].decision_at.date().isoformat();opened=z['opened'].date().isoformat();fr=facts.loc[(sid,signal)].to_dict() if (sid,signal) in facts.index else None;factor=D(str(facts.loc[(sid,opened)]['factor']));initial_line=max(i['I_floor'],D(i['cp_floor']))/factor if m['role']=='mobile' else i['I_floor']/factor;tr=next(t for t in a.trades if t.get('layer')==z['id']);buyprice=D(tr['gross_cny'])/tr['shares'];c=i.get('receipt');payload=json.loads(c.payload_json) if c and c.payload_json else None;exits=[]
   for eid,duty in a.exit_duties.items():
    if duty['layer']!=z['id']:continue
    lock=a.policy.locks[eid];h=lock.h;actualparts=[dict(p,at=t['at'],price=t['price'],receipt=t['receipt_id']) for t in a.trades if t['side']=='sell' for p in t['parts'] if p['layer']==z['id'] and any(rr in p['reason'].split(',') for rr in duty['reasons'])];exits.append(dict(id=eid,duty=duty,lock=lock,prior_known_line_snapshot=h,actual_sale_parts=actualparts,snapshot_exact_request_clock=bool(h and str(h['cursor'])==str(duty['requested_at']))))
   pp.append(dict(layer=z['id'],sid=sid,name=meta[sid]['name'],sector=m['sector'],role=m['role'],pool=m['pool'],purpose=m['purpose'],opened=z['opened'],signal_at=i['clock'].decision_at,qty_initial=z['initial_qty'],qty_remaining=z['qty'],entry_price=buyprice,initial_floor_raw=initial_line,initial_distance_fraction=(buyprice-initial_line)/buyprice,signal_facts=fr,source_CP1=payload,exit_evidence=exits,closed=z['closed'],account_layer_cash=z['cash'],booked_dividend=z['dividend']))
  eng[arm]=ee;cohorts[arm]=rows;contexts[arm]=ctx;protections[arm]=pp;cp_rows[arm]=cp.reset_index().query('sid == "688425.SH"').to_dict('records');print('EXTRACTED',arm,'fresh',len(rows),'engineering-stock-days',len(ee),'layers',len(pp),flush=True)
 save('ENGINEERING_DAILY.json',eng);save('ALL_FRESH_CP1_COHORT.json',cohorts);save('DAILY_RESOURCE_CONTEXT.json',contexts);save('ALL_NATIVE_ORDERS.json',orders);save('ALL_PROTECTION_EVENTS.json',protections);save('IRON_CP1_TRACE.json',cp_rows);save('READ_INPUTS.json',READS);save('EXTRACTION_CHECKS.json',dict(passed=True,financial_events=0,account_construction=0,policy_replay=0,seconds=time.perf_counter()-start,market_stock_days_per_window=1709*23))
if __name__=='__main__':main()
