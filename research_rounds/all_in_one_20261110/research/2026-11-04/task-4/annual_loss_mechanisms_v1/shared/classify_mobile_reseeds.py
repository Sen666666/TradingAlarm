"""Separate MOBILE inventory episodes from whole-stock cycles over saved fills."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import gzip,json
O=Path(__file__).resolve().parent;ROOT=O.parents[1];B=ROOT/'new_price_trend_v1/funding/runs/long_OFF/pair';Z=D(0)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
with gzip.open(B/'B.json.gz','rt')as f:b=json.load(f)
with gzip.open(B/'daily.jsonl.gz','rt')as f:daily=list(map(json.loads,f))
ls={l['id']:l for l in b['layers']};annual=json.loads((O/'ANNUAL_LAYER_WEALTH_CHANGES.json').read_text());av={(r['year'],r['layer']):D(r['annual_wealth_change'])for r in annual}
tx=defaultdict(list);spl=defaultdict(list);divs=defaultdict(list);byday={r['at'][:10]:i for i,r in enumerate(daily)}
for t in b['trades']:tx[t['at'][:10]].append(t)
for a in b['audit']:
 if a['kind']=='split':spl[a['at'][:10]].append(a)
 if a['kind']=='dividend_accrual':
  rec=a['receivable'];day=rec['ex_at'][:10];prev=daily[byday[day]-1];el=[l for l in prev['layers']if l['sid']==rec['security_id']and l['qty']];q=sum(l['qty']for l in el)
  for l in el:
   if ls[l['id']]['kind']=='add':divs[day].append((l['sid'],D(rec['net_local'])*D(l['qty'])/D(q)))
qby=defaultdict(int);active={};last={};cycles=[];rows=[];cid=0
for r in daily:
 day=r['at'][:10]
 for a in spl[day]:
  for lid in qby:
   if ls[lid]['sid']==a['sid']:qby[lid]=int(D(qby[lid])*D(a['ratio']))
 for sid,v in divs[day]:
  assert sid in active;active[sid]['dividend']+=v
 for t in tx[day]:
  sid=t['security_id'];core_before=sum(q for lid,q in qby.items()if ls[lid]['sid']==sid and ls[lid]['kind']=='core');mob_before=sum(q for lid,q in qby.items()if ls[lid]['sid']==sid and ls[lid]['kind']=='add')
  if t['side']=='buy':
   if t['kind']=='add':
    previous=last.get(sid)
    if not mob_before:
     cid+=1;active[sid]={'mobile_inventory_episode':cid,'sid':sid,'opened':t['at'],'signal_at':t['signal_at'],'closed':None,'buy_cash':Z,'sale_net':Z,'dividend':Z,'layers':[],'epoch':t.get('epoch'),'previous_mobile_episode_closed':previous['closed']if previous else None,'previous_mobile_episode_net':previous['net']if previous else None,'previous_mobile_epoch':previous['epoch']if previous else None};cycles.append(active[sid])
    cy=active[sid];priorloss=cy['previous_mobile_episode_net']is not None and cy['previous_mobile_episode_net']<0
    label='continue_existing_MOBILE'if mob_before else 'MOBILE_reseed_after_loss_CORE_remaining'if priorloss and core_before else 'MOBILE_reseed_after_loss_stock_flat'if priorloss else 'MOBILE_reseed_after_nonloss_or_first'
    rows.append({'year':int(day[:4]),'layer':t['layer'],'sid':sid,'signal_at':t['signal_at'],'opened':t['at'],'core_qty_before_fill':core_before,'mobile_qty_before_fill':mob_before,'label':label,'mobile_inventory_episode':cy['mobile_inventory_episode'],'episode_after_previous_mobile_loss':priorloss,'previous_mobile_episode_closed':cy['previous_mobile_episode_closed'],'previous_mobile_episode_net':cy['previous_mobile_episode_net'],'current_epoch':t.get('epoch'),'previous_mobile_epoch':cy['previous_mobile_epoch'],'same_saved_I_watch_epoch_as_previous_mobile_episode':t.get('epoch')==cy['previous_mobile_epoch']if cy['previous_mobile_epoch']is not None else None,'annual_wealth_change':av.get((int(day[:4]),t['layer']))})
    cy['buy_cash']+=D(t['gross_cny'])+D(t['fees_cny']);cy['layers'].append(t['layer'])
   qby[t['layer']]+=t['shares']
  else:
   for part in t['parts']:
    lid=part['layer'];assert qby[lid]>=part['shares'];qby[lid]-=part['shares']
    if ls[lid]['kind']=='add':active[sid]['sale_net']+=D(part['net_cash'])
   mob_after=sum(q for lid,q in qby.items()if ls[lid]['sid']==sid and ls[lid]['kind']=='add')
   if mob_before and not mob_after:
    cy=active[sid];cy['closed']=t['at'];cy['exit_reason']=t.get('reason');cy['net']=cy['sale_net']+cy['dividend']-cy['buy_cash'];last[sid]=cy;del active[sid]
 assert {l['id']:l['qty']for l in r['layers']}=={lid:q for lid,q in qby.items()if q},('qty',day)
summary={}
for year in [2022,2023]:
 yr=[r for r in rows if r['year']==year];group={}
 for row in yr:
  key=row['label'];g=group.setdefault(key,{'fills':0,'annual_change':Z,'negative_layer_sum':Z,'positive_layer_sum':Z,'same_I_watch_epoch_as_previous_mobile_episode':0});g['fills']+=1;v=row['annual_wealth_change']or Z;g['annual_change']+=v
  if v<0:g['negative_layer_sum']+=v
  else:g['positive_layer_sum']+=v
  if row['same_saved_I_watch_epoch_as_previous_mobile_episode']:g['same_I_watch_epoch_as_previous_mobile_episode']+=1
 wavegroup={}
 for row in yr:
  key='after_previous_mobile_loss' if row['episode_after_previous_mobile_loss'] else 'first_or_after_nonloss'
  g=wavegroup.setdefault(key,{'fills_including_seed_and_later_adds':0,'annual_change':Z,'negative_layer_sum':Z,'positive_layer_sum':Z});g['fills_including_seed_and_later_adds']+=1;v=row['annual_wealth_change']or Z;g['annual_change']+=v
  if v<0:g['negative_layer_sum']+=v
  else:g['positive_layer_sum']+=v
 summary[str(year)]={'individual_buy_classification':group,'whole_mobile_episode_origin_including_later_buys':wavegroup}
save('ORIGINAL_MOBILE_RESEED_CLASSIFICATIONS.json',rows);save('ORIGINAL_MOBILE_INVENTORY_EPISODES.json',cycles);save('MOBILE_RESEED_ANNUAL_SUMMARY.json',{'years':summary,'scope':'MOBILE-zero episodes are distinct from stock-flat cycles. Prior episode net is already realized at later buy; original trade epoch is an I-watch/source-key epoch, NOT a canonical E0 episode. Reseed row annual values are seed layers only; continued buys belong to continue_existing_MOBILE. Whole-episode-origin grouping includes those later buys, not a newly simulated wave. Annual P&L uses fixed as-of layer wealth, no future outcome in classification.','all_original_726_CLOSE_layer_quantities_exact':True,'new_accounts':0,'new_backtests':0})
print(json.dumps(summary,ensure_ascii=False,default=str))
