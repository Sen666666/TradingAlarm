"""Saved orders plus current-as-of stage/rank linkage; no new account events."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,collections,argparse
import native_rank as N
import analyze_results as A
O=N.O;W=N.W
def read(p):return json.loads(Path(p).read_text())
def obj(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):A.save(p,x)
def run(win):
    N.configure_scores();A.M.industry_state()
    old=W/('2022-normal-reference-20261031' if win=='2022' else 'q2-normal-continuation-20261031')/'runs/B_diag'
    roots={'SC':old,'PVR_SLOT1':O/'runs'/win};books={ref:obj(root/'pair/B.json.gz') for ref,root in roots.items()}
    groups={};first_res={}
    for ref,root in roots.items():
        b=books[ref];di={(x['at'][:10],i['sid'],i['role']):i for x in b['decisions'] for i in x['intents']}
        rolekeys=collections.defaultdict(set)
        for d,s,r in di:rolekeys[d,s].add(r)
        daily={x['at'][:10]:x for x in rows(root/'pair/daily.jsonl.gz')}
        ls={x['layer']:x for x in read(O/'analysis'/win/ref/'LAYERS.json')}
        money=[];orders=set();NAorders=set();domain=collections.Counter()
        for k,i in di.items():
            p=N.SCORES.at(k[1],k[0]);domain[i['role']+'_intents']+=1
            if p is None:domain[i['role']+'_NA']+=1
        for j in b['journal']:
            if j['kind']!='real_buy_fill':continue
            l=ls[j['layer']];signal=l['signal_day'];i=di[signal,l['sid'],l['role']]
            state=A.M.STATE[l['sector']].get(signal);score=N.SCORES.at(l['sid'],signal)
            if l['role']=='mobile':assert l['receipt']==i['CP1_id'] and l['receipt'] is not None
            r=dict(layer=l['layer'],order=j['budget_order'],sid=l['sid'],name=l['name'],role=l['role'],pool=l['pool_at_fill'],
              signal_day=signal,actual_fill_at=j['at'],quantity=j['shares'],price=j['price'],fees=j['fees'],
              original_H1_score=i['score'],original_H1_rank=i.get('original_H1_rank',i['rank']),
              frozen_priority_rank=i.get('priority_rank',i['rank']),PVR=score,PVR_ready=score is not None,
              same_stock_core_mobile_planned=rolekeys[signal,l['sid']]=={'core','mobile'},
              original_target_cap=i['cap'],original_target_gross=i['budget'],original_floor=i['floor'],
              receipt=l['receipt'],financial_attempt=l['attempt'],ACT_on_at_signal=daily[signal]['on'],
              market_industry_stage=state['stage_name'] if state else None,
              market_industry_attempt=state['attempt_id'] if state else None,
              market_E0_valid=state['E0_valid'] if state else None,
              layer_net=l['net'],layer_closed=l['closed'],remaining_qty=l['qty'])
            money.append(r);orders.add(j['budget_order'])
            if score is None:NAorders.add(j['budget_order'])
        save(Path('analysis')/win/ref/'FUNDED_RANK_STAGE_CHAIN.json',money)
        groups[ref]=dict(original_native_domain=dict(domain),actual_filled_orders=len(orders),
          PVR_NA_actual_filled_orders=len(NAorders),
          PVR_NA_filled_core_layers=sum(not r['PVR_ready'] and r['role']=='core' for r in money),
          PVR_NA_filled_mobile_layers=sum(not r['PVR_ready'] and r['role']=='mobile' for r in money),
          filled_core_layers=sum(r['role']=='core' for r in money),filled_mobile_layers=sum(r['role']=='mobile' for r in money))
        closed=collections.defaultdict(lambda:D(0))
        for l in ls.values():
            if not l['qty']:closed[l['sid']]+=D(l['net'])
        worst=sorted(closed,key=lambda s:(closed[s],s))[:3]
        save(Path('analysis')/win/ref/'DETERMINISTIC_WORST3_CLOSED_STOCKS.json',[
          dict(sid=s,name=A.META[s]['name'],closed_layer_net=closed[s],
               funded_chain=[r for r in money if r['sid']==s],
               actual_entry_actions=[x for x in read(O/'analysis'/win/ref/'ENTRY_ACTIONS.json') if x['sid']==s],
               exit_requests_and_fills=[x for x in read(O/'analysis'/win/ref/'EXITS.json') if x['sid']==s]) for s in worst])
        ff=[x for x in rows(root/'pair/funding.jsonl.gz') if x['result']=='reserved']
        first_res[ref]=ff
    left,right=first_res['SC'],first_res['PVR_SLOT1'];fields=['at','sid','role','pool','shares','price']
    fp=lambda r:tuple(str(r.get(k)) for k in fields)
    ix=next((i for i,(a,b) in enumerate(zip(left,right)) if fp(a)!=fp(b)),min(len(left),len(right)))
    save(Path('analysis')/win/'FIRST_ACTUAL_RESERVATION_DIFFERENCE.json',dict(index=ix,
      SC=left[ix] if ix<len(left) else None,PVR_SLOT1=right[ix] if ix<len(right) else None,
      unchanged_prior_actual_reservations=left[:ix],
      scope='first economic reservation sequence difference; not later-stock causal attribution or swappable-capital PnL'))
    if win=='2025_26':
        rank=rows(O/'runs'/win/'pair/rank-policy.jsonl.gz')
        save(Path('analysis')/win/'RANK_INTERVENTION.json',dict(distinct_planned_stock_days=len(rank),
          changed_rank_stock_days=sum(x['original_H1_rank']!=x['priority_rank'] for x in rank),
          NA_fixed_stock_days=sum(not x['PVR_ready'] for x in rank),
          core_only_stock_days=sum(x['roles']==['core'] for x in rank),
          both_roles_stock_days=sum(x['roles']==['core','mobile'] for x in rank)))
    save(Path('analysis')/win/'NATIVE_ROLE_AND_NA_FUNDED_COVERAGE.json',groups)
    print('BEHAVIOR_LINKED',win,'first reservation difference',ix,flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--window',choices=['2022','2025_26'],required=True);a=p.parse_args()
    try:run(a.window)
    except BaseException as e:
        save('failure/BEHAVIOR_ERROR.json',dict(window=a.window,type=type(e).__name__,reason=str(e)));raise
