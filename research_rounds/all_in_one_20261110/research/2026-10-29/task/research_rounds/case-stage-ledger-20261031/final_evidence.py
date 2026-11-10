"""Small joins on saved orders/fills/pools only; no strategy execution."""
import joint as J
from pathlib import Path
import gzip,json,collections,inspect
import pandas as pd
O=J.O;D=J.D;Z=D(0)
def rows(n):return [json.loads(x) for x in gzip.open(O/'pair'/(n+'.jsonl.gz'),'rt')]
def save(n,x):
 J.save(n,x)
 if isinstance(x,list) and x:pd.DataFrame(J.W.M.N.encoded(x)).to_csv(O/(n+'.csv'),index=False)
daily=rows('daily');fund=rows('funding');exitrows=[];restores=[];oldprobe=[];summary=[];stage={}
for sector in ['URFI881107','URFI881128','URFI881155','URFI881267','URFI881276']:
 r=J.T.read(O.parent/'industry-mobile-stage-20261031'/f'{sector}_STATE.json');first={}
 for x in r:
  if x['action']=='probe':first[x['attempt_id']]=x
 stage[sector]={x['day']:(x['E0_episode']+':'+first[x['attempt_id']]['receipt_id'] if x['attempt_id'] else None) for x in r}
_,market,facts=J.W.context()
for policy in ['A','B']:
 book=json.load(gzip.open(O/'pair'/(policy+'.json.gz'),'rt'));buys=[t for t in book['trades'] if t['side']=='buy'];sells=[t for t in book['trades'] if t['side']=='sell'];native=[x for x in book['audit'] if x['kind']=='exit_request'];pilots=[x for x in book['audit'] if x['kind']=='pilot_layer_exit'];mobilemap={x['layer']:x for x in book['journal'] if x['kind']=='real_buy_fill'};groups={x['event_id']:dict(account=policy,sid=x['sid'],request_at=x['at'],native_exit_id=x['event_id'],layer_requests=[],fills=[]) for x in native}
 for p in pilots:
  ns=[x for x in native if x['sid']==p['sid'] and x['at']<=p['at']];assert ns;groups[ns[-1]['event_id']]['layer_requests'].append(p)
 for t in sells:
  ns=[x for x in native if x['sid']==t['security_id'] and x['at']<=t['at']];assert ns;groups[ns[-1]['event_id']]['fills'].append(t)
 for g in groups.values():
  g['actual_sold_shares']=sum(t['shares'] for t in g['fills']);g['actual_fees']=sum((D(t['fees_cny']) for t in g['fills']),Z);g['first_fill_at']=g['fills'][0]['at'] if g['fills'] else None;g['reasons']=sorted({p['reason'] for p in g['layer_requests']});exitrows.append(g)
 for t in buys:
  older=[x for x in book['layers'] if x['sid']==t['security_id'] and x['closed'] and x['closed']<t['at']];held=any(x['sid']==t['security_id'] and x['opened']<t['at'] and (not x['closed'] or x['closed']>t['at']) for x in book['layers'])
  if older and not held:
   prior=max(older,key=lambda x:x['closed']);old=book['metadata'][str(prior['id'])];new=book['metadata'][str(t['layer'])];restores.append(dict(account=policy,sid=t['security_id'],previous_exit_at=prior['closed'],signal_at=t['signal_at'],reentry_at=t['at'],shares=t['shares'],price=t['price'],fees=t['fees_cny'],role=new['role'],pool_at_fill=mobilemap[t['layer']]['pool'],same_original_stock_E0=old['stock_structure']==new['stock_structure'],CP1_id=mobilemap[t['layer']]['CP1_id']))
 for r in [x for x in daily if x['account']==policy]:
  day=r['at'][:10];at=J.W.M.N.iso(day+'T15:10:00+08:00');cap=Z;risk=Z;corecap=Z;corerisk=Z;n=0
  for x in r['layers']:
   if x['pool']!='probe' or x['attempt']==stage[x['sector']][day]:continue
   value=D(x['qty'])*market.latest_mark(x['sid'],at).cny_price(at);factor=facts.factor(x['sid'],at);line=D(str(x['last_core_line'])) if x['role']=='core' else D(x['floor']);riskval=D(x['qty'])*max(Z,market.latest_mark(x['sid'],at).cny_price(at)-line/factor);cap+=value;risk+=riskval;n+=1
   if x['role']=='core':corecap+=value;corerisk+=riskval
  oldprobe.append(dict(account=policy,day=day,old_attempt_probe_layers=n,old_attempt_probe_capital=cap,old_attempt_probe_risk=risk,old_core_probe_capital=corecap,old_core_probe_risk=corerisk,total_probe_capital=r['pool_probe'][0],total_probe_risk=r['pool_probe'][1],NAV=r['nav']))
 op=[x for x in oldprobe if x['account']==policy];pf=[x for x in fund if x['account']==policy and 'probe_risk' in x['result']];byday={x['day']:x for x in op};coexist=[]
 for x in pf:
  prior=[r for r in op if r['day']<x['at'][:10]];o=prior[-1] if prior else None
  if o and o['old_attempt_probe_risk']>0:coexist.append(dict(funding_refusal=x,preceding_close_old_probe=o))
 summary.append(dict(account=policy,actual_exit_requests=len(groups),actual_sell_fills=len(sells),requests_unfilled_by_end=sum(not g['fills'] for g in groups.values()),same_structure_mobile_reentries=sum(r['account']==policy and r['same_original_stock_E0'] and r['role']=='mobile' for r in restores),all_reentries=sum(r['account']==policy for r in restores),days_old_probe_occupied=sum(x['old_attempt_probe_capital']>0 for x in op),maximum_old_probe_capital=max(x['old_attempt_probe_capital'] for x in op),maximum_old_probe_risk=max(x['old_attempt_probe_risk'] for x in op),probe_risk_refusals_with_old_probe_risk_coexisting=len(coexist),not_claimed_exclusive_cause=True,coexisting_examples=coexist[:3]))
save('EXIT_REQUEST_TO_ACTUAL_FILL',exitrows);save('ACTUAL_REENTRY_FUNNEL',restores);save('OLD_ATTEMPT_PROBE_OCCUPANCY',oldprobe);save('EXIT_REENTRY_OLD_PROBE_SUMMARY',summary)
(O/'KEY_ADAPTER_FUNCTIONS.txt').write_text('\n\n'.join(inspect.getsource(fn) for fn in [J.Budget.industry,J.Account.cancel_buy,J.Account.fill_buy,J.Account.sync,J.Runner.industry,J.Runner.route]))
print('FINAL_EVIDENCE',[(r['account'],r['actual_exit_requests'],r['same_structure_mobile_reentries'],r['days_old_probe_occupied'],str(r['maximum_old_probe_capital'])) for r in summary],flush=True)
