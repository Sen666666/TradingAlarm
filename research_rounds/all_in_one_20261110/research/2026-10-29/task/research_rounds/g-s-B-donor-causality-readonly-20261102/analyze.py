from pathlib import Path
from decimal import Decimal as D
import sys,json,copy,collections,csv,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent/'g-s-B-joint-target-v2-20261102';sys.path.insert(0,str(ROOT))
import selector as B
J=B.J;Z=D(0)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def types(v):return sorted({x.split(':')[-1] for x in v['violations']})
def minimum(v):
 out={}
 for c in v['checks']:
  k=c['constraint']
  if k not in out or D(c['residual'])<D(out[k]['residual']):out[k]=c
 return out
def sold_cap(s,Dmap):return sum((D(q)*D(next(z['mark'] for z in s['lots'] if z['sid']==sid)) for sid,q in Dmap.items()),Z)
def new_sold_options(s,sid,q):
 values=[0];z=next(z for z in s['lots'] if z['sid']==sid);step=J.rule(z['quantity']).sell_step
 values+=list(range(step,q,step));return values
def alternative(s,ds,r,comp):
 final=r['D'];positive=[sid for sid,q in r['Q'].items() if q];earliest=min(comp[s]['competition_rank'] for s in positive)
 extra=[]
 for sid in sorted({z['sid'] for z in s['lots']}):
  lots=[z for z in s['lots'] if z['sid']==sid]
  if r['Q'].get(sid,0) or sid not in comp or comp[sid]['competition_rank']<=earliest:continue
  allowed=[z for z in lots if z.get('B_donor_eligible') and z['role']=='mobile']
  if not allowed:continue
  available=sum(min(z['qty'],z['sellable_qty']) for z in allowed)-final.get(sid,0);step=J.rule(allowed[0]['quantity']).sell_step
  if available>=step:extra.append((sid,step))
 checks=0;beforecap=sold_cap(s,final);beforeplan=B.make_plan(s,ds,r['Q'],final);trace=[]
 for add,step in extra:
  for restore in sorted(final):
   if restore==add:continue
   for less in new_sold_options(s,restore,final[restore]):
    trial=dict(final);trial[add]=trial.get(add,0)+step;trial[restore]=less
    cap=sold_cap(s,trial)
    if cap>=beforecap:continue
    checks+=1
    if checks>10000:raise RuntimeError('bounded alternative search limit; do not infer no alternative')
    x=B.evaluate(s,ds,r['Q'],trial)
    if x['validation']['ok']:
     original_net=sum((D(o['net']) for o in beforeplan['orders']),Z);new_net=sum((D(o['net']) for o in x['donors']['orders']),Z)
     original_fee=sum((D(o['fees']) for o in beforeplan['orders']),Z);new_fee=sum((D(o['fees']) for o in x['donors']['orders']),Z)
     return dict(found=True,checks=checks,add_sid=add,add_name=comp[add]['name'],extra_sell=step,add_rank=comp[add]['competition_rank'],
       restore_sid=restore,restore_name=comp[restore]['name'],restored=final[restore]-less,restore_rank=comp[restore]['competition_rank'],D=trial,
       original_sold_mark=beforecap,alternative_sold_mark=cap,less_sold_mark=beforecap-cap,original_net=original_net,alternative_net=new_net,original_fee=original_fee,alternative_fee=new_fee,
       conditional_terminal=x['validation']['terminal'],minima=minimum(x['validation']),
       scope='fixed Q full resource witness only; changed donor order; not proven original-B prefix executable; no counterfactual PnL')
 return dict(found=False,checks=checks,extra_donors_considered=extra,scope='bounded one added sell-step / one restored stock; global minimum unknown')

def main():
 indexsha=sha(ROOT/'ARTIFACT_SHA256.json');out=HERE/'results';out.mkdir(exist_ok=False);summary={}
 for k in ('2025_26','2022'):
  x=read(ROOT/'inputs'/(k+'.json'));s=x['snapshot'];ds=x['B_demands'];r=read(ROOT/'results'/k/'B.json');comp={z['sid']:z for z in x['evidence']['full_union']};by={d['sid']:d for d in ds}
  frozen=(J.digest(s),J.digest(r));Q={sid:0 for sid in r['Q']};previousD={};per=[];layers=[]
  for t in r['trace']:
   sid=t['sid'];q=t['q'];now=t.get('D',previousD)
   if not q:previousD=copy.deepcopy(now);continue
   d=by[sid];Q[sid]=q;new=B.evaluate(s,ds,Q,now);assert new['validation']['ok'];without=B.evaluate(s,ds,Q,previousD)
   plus={z:max(0,now.get(z,0)-previousD.get(z,0)) for z in set(now)|set(previousD)};positive={z:n for z,n in plus.items() if n}
   cap=Z;released=Z;step_layers=[]
   for old,n in positive.items():
    zs=[z for z in s['lots'] if z['sid']==old and z['role']=='mobile'];assert len(zs)==1,'current two cases single mobile layer per stock'
    z=zs[0];mark=D(z['mark']);floor=D(z['floor']);risk=D(z['risk'])*n/z['qty'];cap+=D(n)*mark;released+=risk
    row=dict(recipient=sid,recipient_name=comp[sid]['name'],old_sid=old,old_name=comp[old]['name'],old_rank=comp[old]['competition_rank'],recipient_rank=comp[sid]['competition_rank'],layer=z['id'],incremental_sold=n,
      mark=mark,floor=floor,mark_floor_per_share=mark-floor,line_fraction=(mark-floor)/mark,risk_release=risk,capital=D(n)*mark,pool=z['pool'],role=z['role'],purpose=z['purpose'])
    step_layers.append(row);layers.append(row)
   marginal={}
   if positive:
    last=min(positive,key=lambda z:comp[z]['competition_rank']);trial=dict(now);trial[last]=B.less_sale(s,last,now[last]);test=B.evaluate(s,ds,Q,trial)
    marginal=dict(sid=last,name=comp[last]['name'],less_by=now[last]-trial[last],still_feasible=test['validation']['ok'],violations=types(test['validation']))
   old_plan=B.make_plan(s,ds,Q,previousD);new_plan=new['donors'];p=D(d['mark'])*(D(1)+B.SLIP);floor=D(d['floor']);risk=D(q)*(p-floor)
   more='independent_stock_target_or_legal_rounding' if q==d['max_q'] else types(B.evaluate(s,ds,{**Q,sid:q+J.rule(d['quantity']).buy_step},now)['validation'])
   per.append(dict(sid=sid,name=comp[sid]['name'],rank=comp[sid]['competition_rank'],q=q,raw_max=d['max_q'],price=p,floor=floor,new_line_fraction=(p-floor)/p,new_reserved_risk=risk,new_buy_cash=J.buy_cost(d,q),
    without_this_step_D_violations=types(without['validation']),accepted_minima=minimum(new['validation']),last_increment_donor_one_step=marginal,quantity_upper_reason=more,
    incremental_positive_donor_mark=cap,incremental_positive_donor_risk=released,positive_donor_weighted_line_fraction=released/cap if cap else None,
    net_sold_mark_change=sold_cap(s,now)-sold_cap(s,previousD),net_estimated_sale_cash_change=sum((z['net'] for z in new_plan['orders']),Z)-sum((z['net'] for z in old_plan['orders']),Z),
    layers=step_layers,source_donor_priority='lower joint rank first; fixed FIFO within mobile; one aggregate fee per stock; no core or more-front donor'))
   previousD=copy.deepcopy(now)
  assert Q==r['Q']
  self_conflict=[sid for sid,q in r['Q'].items() if q and r['D'].get(sid,0)]
  actual=read(ROOT.parent/'g-s-historical-native-nextsession-20261101/run'/k/'close'/((('2025-07-03' if k=='2025_26' else '2022-01-06'))+'-CLOSE.json'))
  actual_exits=actual['account']['exits'];real_conflict=[dict(sid=sid,name=comp[sid]['name'],new_q=q,actual_old_exit=actual_exits[sid]) for sid,q in r['Q'].items() if q and sid in actual_exits]
  alt=alternative(s,ds,r,comp);assert frozen==(J.digest(s),J.digest(r))
  save(out/(k+'-PER_NEW_DEMAND.json'),per);save(out/(k+'-DONOR_LAYERS.json'),layers);save(out/(k+'-LOCAL_ALTERNATIVE.json'),alt)
  with (out/(k+'-DONOR_LAYERS.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(layers[0]));w.writeheader();w.writerows(layers)
  summary[k]=dict(per_new_demand=per,within_projection_buy_sell_conflict=self_conflict,actual_legacy_A_exit_conflict=real_conflict,local_alternative=alt,financial_events=0)
  print(k,[(p['name'],p['without_this_step_D_violations'],float(p['new_line_fraction']),float(p['positive_donor_weighted_line_fraction'])) for p in per],flush=True)
  print('ALT',k,alt,flush=True)
 save(out/'SUMMARY.json',summary)
 assert sha(ROOT/'ARTIFACT_SHA256.json')==indexsha
 for rel,h in read(ROOT/'ARTIFACT_SHA256.json').items():assert sha(ROOT/rel)==h
 save(HERE/'VERIFICATION.json',dict(financial_events=0,frozen_B_artifact_index_sha256=indexsha,all_original_B_files_hash_unchanged=True,selector_code_unchanged=True,source_inputs_unchanged=True))
if __name__=='__main__':main()
