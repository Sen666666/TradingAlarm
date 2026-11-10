"""Read saved JSON only. No account restore, indicator generation or event call."""
from pathlib import Path
from decimal import Decimal as D
from datetime import date
import csv,json,hashlib,collections
O=Path(__file__).resolve().parent
BASE=O.parent/'g-s-historical-native-nextsession-20261101'
PARENT=BASE.parent/'g-s-historical-native-prefix-20261101'
SPECS={'2025_26':('2025-07-03','2025-07-01'),'2022':('2022-01-06','2022-01-04')}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def write_csv(path,rows):
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def main():
 old_index=sha(BASE/'INPUT_OUTPUT_SHA256.json')
 source_evidence={};results={}
 sel=read(BASE/'inputs/2025_26/selection.json');namespath=Path(sel['industry_resolution_evidence']['path'])
 assert sha(namespath)==sel['industry_resolution_evidence']['sha256']
 master=list(csv.DictReader(namespath.open()));names={x['symbol']:x['name'] for x in master};sectors={x['industry_index_symbol']:x['industry_name'] for x in master}
 for k,(day,start) in SPECS.items():
  openpath=BASE/'run'/k/(day+'-OPEN.json');closepath=BASE/'run'/k/'close'/(day+'-CLOSE.json');seedpath=BASE/'inputs'/k/'bootstrap.json'
  op=read(openpath);cl=read(closepath);a=cl['account'];before=op['account'];p=a['policy'];oldp=before['policy'];allocation=cl['lifecycle'][-1]['allocation']
  stock_mapping={r['sid']:r for r in cl['mapping'][-1]['stocks']}
  seeds={s['policy_scope']:s for s in read(seedpath).values()}
  source_evidence.update({str(q):sha(q) for q in (openpath,closepath,seedpath)})
  nd=D(p['nd']);oldnd=D(oldp['nd']);n=len(p['k']);oldn=len(oldp['k']);quota=nd*D('.8')/n;oldquota=oldnd*D('.8')/oldn
  raw_cash=sum((D(x['cash']) for x in allocation['demand']),D(0));available=D(a['balance']['available']);floor_cash=nd*D('.1');spendable=max(D(0),available-floor_cash)
  assert max(D(0),raw_cash-spendable)==D(allocation['needed'])
  reduced=allocation['reductions'];estimated=sum((D(x['estimated_net']) for x in reduced),D(0));covered=D(allocation['covered'])
  assert covered==0 and estimated>=D(allocation['needed'])
  holdings={z['id']:z for z in a['layers'] if z['qty']};meta=a['capital_meta'];marks={sid:D(v) for sid,v in a['market_marks'].items()}
  factors={sid:D(v) for sid,v in a['market_factors'].items()};bysec=collections.defaultdict(list)
  for z in holdings.values():bysec[meta[str(z['id'])]['sector']].append(z)
  krows=[]
  for sec,e in p['k'].items():
   s=p['scopes'][sec];seed=seeds[sec]['market_context'];w=e['witness'];st=cl['last_stock_state'][w]
   inherited=bool(seed['mature'] and seed['context']==s['context'])
   proof=[x for x in p['proof_history'] if x['scope']==sec and x['context']==s['context'] and x['kind']=='price_advance']
   advances_after_start=[x for x in proof if x['confirmed']>=date.fromisoformat(start).toordinal()]
   last=max((x['confirmed'] for x in proof),default=None)
   value=sum((D(z['qty'])*marks[z['sid']] for z in bysec[sec]),D(0));fresh=sum(bool(cl['last_stock_state'][z['sid']].get('receipt')) for z in bysec[sec])
   row=dict(sector=sec,industry=sectors.get(sec,sec),K_reason=e['reason'],witness=w,witness_name=names.get(w,w),
     seed_mature_same_context=inherited,price_advances_since_account_start=len(advances_after_start),last_price_advance_day=date.fromordinal(last).isoformat() if last else None,
     permit=s['permit'],support=s['support'],mature=s['mature'],witness_I_valid=st['i_valid'],witness_original_stock_Q=stock_mapping[w]['stock_Q'],witness_new_intent_eligible=st['q'],witness_fresh_CP1=bool(st['receipt']),
     live_fresh_CP1_stocks=fresh,current_industry_capital=value,current_weight=value/nd,new_authorization_target=quota,
     only_hold_I_witness=e['reason']=='holding' and not st['receipt'],
     warm_hold_without_new_frontier=e['reason']=='holding' and inherited and not advances_after_start,
     warning='holding witness is a narrow logical condition, not proof of price weakness')
   krows.append(row)
  write_csv(O/(k+'-K.csv'),krows)
  newbuys={f['security_id']:f for f in a['fills'] if f['side']=='buy' and f['at'][:10]==day}
  assert len(newbuys)==(7 if k=='2025_26' else 2)
  fresh_sells=[]
  for r in reduced:
   if r['sid'] not in newbuys:continue
   z=holdings[r['lot']];sid=z['sid'];m=meta[str(z['id'])];sec=m['sector'];scope=p['scopes'][sec];st=cl['last_stock_state'][sid]
   prev=before['holding_support'].get(sec);now=a['holding_support'].get(sec);cap=sum((D(x['qty'])*marks[x['sid']] for x in bysec[sec]),D(0));factor=factors[sid]
   # Always convert accepted protection from original factor coordinate to raw.
   effective_line=D(z['floor'])/factor if z['kind']=='add' else D(a['facts_floors'][sid])/factor
   firstorder=a['supports'][m['order']];fill=newbuys[sid];originalK=oldp['k'].get(sec);newK=p['k'].get(sec)
   binding={oid:goals for oid,goals in a['funding_coverage']['order_goals'].items() if oid==a['exits'][sid]['event_id']}
   fresh_sells.append(dict(sid=sid,name=names.get(sid,sid),layer=z['id'],sector=sec,industry=sectors.get(sec,sec),role=m['role'],pool=m['pool'],original_use=m['purpose'],
     actual_bought_qty=fill['shares'],requested_exit_qty=r['q'],exit_class=r['allocation_class'],estimated_net=r['estimated_net'],
     entry_support_scope=firstorder['scope'],entry_support_context=firstorder['context'],
     original_K_target=oldquota if originalK else None,new_K_target=quota if newK else None,
     original_support=prev,current_support=now,industry_value_at_request=cap,new_equal_target_excess=max(D(0),cap-quota) if newK else None,
     stock_I_valid=st['i_valid'],original_stock_Q=stock_mapping[sid]['stock_Q'],current_new_intent_eligible=st['q'],stock_fresh_CP1=bool(st['receipt']),close=marks[sid],actual_line=effective_line,
     close_above_actual_line=marks[sid]>effective_line,current_F1_permit=scope['permit'],current_F1_support=scope['support'],current_F1_mature=scope['mature'],
     global_permit=p['scopes']['G']['permit'],global_support=p['scopes']['G']['support'],all_demand_goal_ids_shared=allocation['demand'],native_order_goal_bindings=binding,
     attribution='shared funding deficit; no unique one-sale-to-one-demand causal allocation is recorded'))
  assert len(fresh_sells)==(4 if k=='2025_26' else 0)
  summaries=collections.Counter({
   'K_total':n,'K_holding':sum(x['K_reason']=='holding' for x in krows),'K_order_or_fresh':sum(x['K_reason']=='order_or_fresh' for x in krows),
   'K_holding_inherited_maturity':sum(x['K_reason']=='holding' and x['seed_mature_same_context'] for x in krows),
   'K_warm_hold_without_new_frontier':sum(x['warm_hold_without_new_frontier'] for x in krows),
   'K_holding_witness_no_fresh_CP1':sum(x['only_hold_I_witness'] for x in krows),
   'K_warm_hold_without_frontier_or_fresh_CP1':sum(x['warm_hold_without_new_frontier'] and not x['witness_fresh_CP1'] for x in krows)})
  results[k]=dict(day=day,previous_K=oldn,current_K=n,previous_S_target_fraction=D('.8')/oldn,current_S_target_fraction=D('.8')/n,
    previous_S_target_cash=oldquota,current_S_target_cash=quota,new_K_sectors=[dict(sector=s,industry=sectors.get(s,s),entry=p['k'][s]) for s in p['k'] if s not in oldp['k']],
    retired_K_sectors=[s for s in oldp['k'] if s not in p['k']],K_counts=dict(summaries),
    fresh_demands=allocation['demand'],all_demand_cash=raw_cash,available_cash=available,cash_floor=floor_cash,spendable=spendable,
    raw_cash_shortfall=allocation['needed'],existing_funding_cover=covered,estimated_new_reduction_proceeds=estimated,
    whole_unit_overshoot=estimated-D(allocation['needed']),pending_reduction_count=len(reduced),new_buy_then_trim=fresh_sells,
    K_rows=krows,source_algorithm='G first then S-excess; mobile before core; proportional caps within class/role/sector; deterministic sid ties, no H1 weakening or new-purchase-age criterion',
    source_refs=dict(K='policy.py:89-113',funding='native_capital.py:348-429',support_withdraw='native_capital.py:430-467'))
 save(O/'RESULTS.json',results)
 save(O/'SOURCE_READS.json',source_evidence)
 assert sha(BASE/'INPUT_OUTPUT_SHA256.json')==old_index
 save(O/'READONLY_VERIFICATION.json',dict(financial_events=0,account_restore=0,model_recomputations=0,old_artifact_index_sha256=old_index,old_index_unchanged=True))
 print(json.dumps({k:{x:r[x] for x in ['previous_K','current_K','K_counts','raw_cash_shortfall','existing_funding_cover','estimated_new_reduction_proceeds']} for k,r in results.items()},ensure_ascii=False,default=str,indent=2))
if __name__=='__main__':main()
