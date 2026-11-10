"""Cold, read-only audit of another agent's baseline stage/campaign artifacts.

Reuses the sealed original snapshot/basis reader, never an Account or Runner.
Period arithmetic and campaign boundary/fee/capital checks are independent here.
"""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import hashlib,importlib.util,json,sys
sys.dont_write_bytecode=True;getcontext().prec=65
HERE=Path(__file__).resolve().parent;S=HERE.parent;E=S.parent;A=S/'accounting/results_v2';H=E/'dec2022_authorization_v1'
SOURCE=H/'followup_robustness_v1/performance/analyze_performance.py'
sp=importlib.util.spec_from_file_location('sealed_snapshot_basis_stage_auditor',SOURCE);P=importlib.util.module_from_spec(sp);sp.loader.exec_module(P)
Z=D(0);SRC={};COUNTS=Counter();MAXRES=Z
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p.resolve())]=sha(p);return P.read(p,gz=gz,lines=lines)
def dec(x):return D(str(x))
def eq(a,b,k):
 global MAXRES
 diff=abs(dec(a)-dec(b));MAXRES=max(MAXRES,diff);assert diff<D('0.000001'),(k,str(a),str(b));COUNTS['numeric_equalities']+=1
def zero():return dict(real=Z,unreal=Z,AR=Z,wealth=Z)
def sumf(rr,k):return sum((dec(x[k]) for x in rr),Z)
def campaign_groups(layers):
 stocks=defaultdict(list);out=[]
 for x in layers:stocks[x['sid']].append(x)
 for sid,ll in stocks.items():
  batches=[];current=[];active_end=None
  for x in sorted(ll,key=lambda z:(z['opened'],z['layer_in_this_book'])):
   if current and active_end is not None and x['opened']>=active_end:batches.append(current);current=[]
   current.append(x);active_end=None if any(y['closed'] is None for y in current) else max(y['closed'] for y in current)
  if current:batches.append(current)
  for number,batch in enumerate(batches,1):out.append((sid,number,batch))
 return out
def audit_period(r,m,role_fee_rows):
 start,end=m['start'],m['end'];ix=[j for j,d in enumerate(r['raw']) if start<=d['at'][:10]<=end];assert ix
 lo,hi=ix[0],ix[-1];raw=r['raw'];prev=raw[lo-1] if lo else dict(nav='1000000',inventory='0');last=raw[hi];native=r['daily'];prior=native[lo-1] if lo else dict(strict_realized=Z,open_unrealized=Z,AR=Z)
 actual=dict(NAV_begin=dec(prev['nav']),NAV_end=dec(last['nav']),net_wealth_change=dec(last['nav'])-dec(prev['nav']),return_fraction=dec(last['nav'])/dec(prev['nav'])-1,observations=len(ix),first_observed=raw[lo]['at'][:10],last_observed=raw[hi]['at'][:10])
 for field,out in [('strict_realized','strict_realized_change'),('open_unrealized','open_unrealized_change'),('AR','AR_change')]:actual[out]=dec(native[hi][field])-dec(prior[field])
 trades=[t for t in r['book']['trades'] if start<=t['at'][:10]<=end];buy=[t for t in trades if t['side']=='buy'];sell=[t for t in trades if t['side']=='sell'];actual.update(fees=sumf(trades,'fees_cny'),buy_gross=sumf(buy,'gross_cny'),sell_gross=sumf(sell,'gross_cny'),actual_buycash=sum((dec(t['gross_cny'])+dec(t['fees_cny']) for t in buy),Z),actual_sell_net=sum((dec(t['gross_cny'])-dec(t['fees_cny']) for t in sell),Z),buy_fills=len(buy),sell_fills=len(sell))
 actual['buy_plus_sell_gross']=actual['buy_gross']+actual['sell_gross'];peak=dec(prev['nav']);localDD=Z
 for j in ix:peak=max(peak,dec(raw[j]['nav']));localDD=max(localDD,1-dec(raw[j]['nav'])/peak)
 actual['period_rebased_max_DD']=localDD;actual['maximum_account_DD_from_entire_account_path_peak']=max(dec(native[j]['drawdown_from_full_path_peak']) for j in ix)
 previous=[raw[j-1] if j else dict(nav='1000000',inventory='0') for j in ix]
 actual.update(mean_CLOSE_NAV=sum((dec(raw[j]['nav']) for j in ix),Z)/len(ix),mean_previous_CLOSE_NAV=sum((dec(d['nav']) for d in previous),Z)/len(ix),mean_CLOSE_inventory=sum((dec(raw[j]['inventory']) for j in ix),Z)/len(ix),mean_previous_CLOSE_inventory=sum((dec(d['inventory']) for d in previous),Z)/len(ix),mean_CLOSE_exposure=sum((dec(raw[j]['inventory'])/dec(raw[j]['nav']) for j in ix),Z)/len(ix),mean_previous_CLOSE_exposure=sum((dec(d['inventory'])/dec(d['nav']) for d in previous),Z)/len(ix))
 mean=actual['mean_CLOSE_NAV'];actual.update(buy_gross_over_mean_CLOSE_NAV=actual['buy_gross']/mean,sell_gross_over_mean_CLOSE_NAV=actual['sell_gross']/mean,two_sided_gross_over_mean_CLOSE_NAV=actual['buy_plus_sell_gross']/mean,conventional_oneway_turnover_over_mean_CLOSE_NAV=actual['buy_plus_sell_gross']/2/mean,ACT_paused_closes=sum(not raw[j]['on'] for j in ix),ACT_on_CLOSE_observations=sum(raw[j]['on'] for j in ix),ACT_paused_flat_CLOSE_observations=sum(not raw[j]['on'] and not raw[j]['layers'] for j in ix),ACT_paused_held_CLOSE_observations=sum(not raw[j]['on'] and bool(raw[j]['layers']) for j in ix))
 for k,v in actual.items():
  if isinstance(v,str):assert v==m[k],(m['period'],k,v,m[k])
  else:eq(v,m[k],m['period']+' '+k)
 eq(actual['net_wealth_change'],actual['strict_realized_change']+actual['open_unrealized_change']+actual['AR_change'],'component bridge')
 detail=read(A/f"{r['win']}_{m['period']}_DETAIL.json");stored={x['lid']:x for x in detail['layer_rows']};before=r['components'][lo-1] if lo else {};after=r['components'][hi];old=set(r['caps'][lo-1]) if lo else set();expected={};capital=defaultdict(lambda:dict(previous_CLOSE_mark_yuan_observations=Z,previous_CLOSE_basis_yuan_observations=Z,CLOSE_mark_yuan_observations=Z,held_CLOSE_observations=0))
 for j in ix:
  for lid,c in (r['caps'][j-1].items() if j else []):capital[lid]['previous_CLOSE_mark_yuan_observations']+=c['mark'];capital[lid]['previous_CLOSE_basis_yuan_observations']+=c['basis']
  for lid,c in r['caps'][j].items():capital[lid]['CLOSE_mark_yuan_observations']+=c['mark'];capital[lid]['held_CLOSE_observations']+=1
 for x in r['layers']:
  lid=x['layer_in_this_book'];bb=before.get(lid,zero());cc=after.get(lid,zero());delta={k:cc[k]-bb[k] for k in zero()};new=start<=x['opened'][:10]<=end
  if lid not in old and not new and not any(delta.values()):continue
  cohort='old_inventory_previous_CLOSE' if lid in old else 'new_'+x['actual_entry_action'] if new else 'other_prior_flat';expected[lid]=dict(lid=lid,role=x['role'],cohort=cohort,**delta,actual_new_buycash=dec(x['cost']) if new else Z,capitaltime=capital[lid])
  y=stored[lid];assert y['key']==x['key'] and y['cohort']==cohort and y['role']==x['role'] and y['actual_entry_action']==x['actual_entry_action']
  for k,v in delta.items():eq(v,y[k],'per-layer true period '+k)
  eq(expected[lid]['actual_new_buycash'],y['actual_new_buycash'],'period actual new buycash')
  for k,v in capital[lid].items():eq(v,y['capitaltime'][k],'per-layer actual capital '+k)
 assert set(expected)==set(stored);COUNTS['period_layer_rows']+=len(expected)
 for dimension in ['cohort','role']:
  actualgroups={}
  for group in {x[dimension] for x in expected.values()}:
   rr=[x for x in expected.values() if x[dimension]==group];sg=m['cohort_summary'][dimension][group];assert sg['members']==len(rr)
   for k in ['real','unreal','AR','wealth','actual_new_buycash']:eq(sumf(rr,k),sg['net' if k=='wealth' else k],'period partition '+dimension+' '+group+' '+k)
   eq(sum((max(Z,x['wealth']) for x in rr),Z),sg['positive'],'group positive');eq(sum((min(Z,x['wealth']) for x in rr),Z),sg['negative'],'group negative')
   for k in capital[next(iter(expected))]:eq(sum((x['capitaltime'][k] for x in rr),Z),sg['capitaltime'][k],'group capital '+k)
   actualgroups[group]=dict(layers=len(rr),wealth=sumf(rr,'wealth'),real=sumf(rr,'real'),unreal=sumf(rr,'unreal'),AR=sumf(rr,'AR'))
  assert set(actualgroups)==set(m['cohort_summary'][dimension])
  actual['audited_'+dimension+'_bridge']=actualgroups
 # Buy/sell fee and cash attribution is checked against native parts, not sale
 # net proceeds labelled as period profits.
 byid=r['byid'];rolecash={role:dict(actual_fees=Z,buy_gross=Z,sell_gross=Z,actual_buycash=Z,actual_sell_net=Z,buy_fills=0,sell_parts=0) for role in ['core','mobile']}
 for t in trades:
  if t['side']=='buy':
   v=rolecash[byid[t['layer']]['role']];v['buy_gross']+=dec(t['gross_cny']);v['actual_fees']+=dec(t['fees_cny']);v['actual_buycash']+=dec(t['gross_cny'])+dec(t['fees_cny']);v['buy_fills']+=1
  else:
   for p in t['parts']:
    gross=dec(t['price'])*p['shares'];fee=gross-dec(p['net_cash']);v=rolecash[byid[p['layer']]['role']];v['sell_gross']+=gross;v['actual_fees']+=fee;v['actual_sell_net']+=dec(p['net_cash']);v['sell_parts']+=1
 for role,v in rolecash.items():
  for k,z in v.items():eq(z,role_fee_rows['roles'][role][k],'role cash/fee '+role+' '+k)
 eq(sum(v['actual_fees'] for v in rolecash.values()),actual['fees'],'all role fees')
 COUNTS['periods']+=1;actual.update(window=r['win'],period=m['period'],start=start,end=end);return actual,expected

def audit_campaigns(r,period_layers):
 cc=read(A/f"{r['win']}_CAMPAIGNS_FULL_ACCOUNTING.json");byset={frozenset(c['layer_ids']):c for c in cc};assert len(byset)==len(cc);groups=campaign_groups(r['layers']);assert len(groups)==len(cc);assert {lid for ids in byset for lid in ids}==set(r['byid']);fees=defaultdict(lambda:Z)
 for t in r['book']['trades']:
  if t['side']=='buy':fees[t['layer']]+=dec(t['fees_cny'])
  else:
   for p in t['parts']:fees[p['layer']]+=dec(t['price'])*p['shares']-dec(p['net_cash'])
 for sid,num,batch in groups:
  ids=frozenset(x['layer_in_this_book'] for x in batch);c=byset[ids];assert c['sid']==sid and c['opened']==min(x['opened'] for x in batch);end=max(x['closed'] for x in batch) if all(x['closed'] is not None for x in batch) else None;assert c['closed']==end
  assert c['by_action']==dict(Counter(x['actual_entry_action'] for x in batch)) and c['by_role']==dict(Counter(x['role'] for x in batch))
  assert set(c['entry_keys'])=={x['key'] for x in batch}
  for ck,rk in [('actual_buycash','cost'),('strict_realized','strict_realized'),('open_unrealized','open_unrealized'),('AR','AR'),('endpoint_net','net')]:eq(sumf(batch,rk),c[ck],'campaign endpoint '+ck)
  eq(sum((fees[lid] for lid in ids),Z),c['actual_fees'],'campaign actual fees')
  for label,rows in period_layers.items():
   rr=[rows[lid] for lid in ids if lid in rows];target=c['stage_wealth'][label]
   for k in ['wealth','real','unreal','AR','actual_new_buycash']:eq(sumf(rr,k),target[k],'campaign true stage '+k)
  cap=Z;points=[]
  for j,day in enumerate(r['daily']):
   if j+1<len(r['daily']):cap+=sum((r['caps'][j][lid]['mark'] for lid in ids&r['caps'][j].keys()),Z)
   held=ids&r['caps'][j].keys()
   if not held:continue
   mark=sum((r['caps'][j][lid]['mark'] for lid in held),Z);basis=sum((r['caps'][j][lid]['basis'] for lid in held),Z);known=[r['components'][j][lid] for lid in ids if lid in r['components'][j]]
   points.append(dict(mark=mark,basis=basis,held_close_unreal=mark-basis,known_recognized_wealth=sumf(known,'wealth'),share=mark/dec(day['NAV'])))
  eq(cap,c['capitaltime_previous_CLOSE_mark_yuan_observations'],'campaign prior CLOSE capitaltime');assert len(points)==c['holding_CLOSE_points']
  if points:
   eq(max(x['share'] for x in points),c['maximum_mark_share_of_account_NAV'],'campaign maximum actual exposure')
   for k in ['mark','basis','held_close_unreal','known_recognized_wealth']:eq(max(x[k] for x in points),c['peaks_on_actual_held_CLOSE_only']['values'][k],'campaign descriptive held CLOSE peak')
 COUNTS['campaigns']+=len(cc);return dict(window=r['win'],campaigns=len(cc),layers=sum(len(x[2]) for x in groups),endpoint_net=sumf(cc,'endpoint_net'),actual_fees=sumf(cc,'actual_fees'))

def main():
 target=HERE/'ACCOUNTING_STAGE_AUDIT.json';assert not target.exists();before={str(p):sha(p) for p in A.iterdir() if p.is_file()};matrix=read(A/'STAGE_WEALTH_CAPITAL_MATRIX.json');assert len(matrix)==19
 P.META_ROWS=read(P.META);P.MANIFEST={x['symbol']:x for x in read(P.W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};P.VALID=read(H/'account_comparison/results_v1/VALIDATION.json')
 fee=read(A/'ROLE_FEES_AND_ACTUAL_TRADED_CASH_BY_STAGE.json');fee={(x['window'],x['period']):x for x in fee};summaries=[];camps=[];act={};layers=0;closes=0
 for win in ['2022_2024','strong']:
  r=P.load('BASELINE',win);layers+=len(r['layers']);closes+=len(r['daily']);stages=[m for m in matrix if m['window']==win];period_layers={}
  # Native actual interval classification independently matches sealed labels.
  prior=defaultdict(list)
  for x in sorted(r['layers'],key=lambda x:(x['opened'],x['layer_in_this_book'])):
   old=prior[x['sid']];action='first' if not old else 'add' if any(p['closed'] is None or p['closed']>x['opened'] for p in old) else 'reentry';assert x['actual_entry_action']==action;prior[x['sid']].append(x)
  for m in stages:
   s,rr=audit_period(r,m,fee[win,m['period']]);summaries.append(s);period_layers[m['period']]=rr
  camps.append(audit_campaigns(r,period_layers))
  if win=='2022_2024':
   partition=[m for m in stages if m['is_disjoint_partition_member']];assert len(partition)==10;assert [m['period'][:3] for m in partition]==[f'P{i:02d}' for i in range(1,11)]
   for d in r['raw']:assert sum(m['start']<=d['at'][:10]<=m['end'] for m in partition)==1
   full=next(m for m in stages if m['period']=='FULL_2022_2024')
   for k in ['net_wealth_change','strict_realized_change','open_unrealized_change','AR_change','fees','buy_gross','sell_gross','actual_buycash','actual_sell_net']:eq(sum((dec(m[k]) for m in partition),Z),full[k],'10 disjoint stages '+k)
   paused=[d for d in r['raw'] if not d['on']];flat=[d for d in paused if not d['layers']];assert len(paused)==234 and len(flat)==230
   episodes=read(A/'ACTUAL_ACT_EPISODES.json');assert sum(x['paused_CLOSE_observations'] for x in episodes)==234 and sum(x['paused_flat_CLOSE_observations'] for x in episodes)==230
   events=[x for x in r['book']['audit'] if x['kind']=='risk_checkpoint' and x.get('event')];actual_pauses=[x for x in events if x['event']=='pause'];assert len(actual_pauses)==len(episodes)==3
   for ep,event in zip(episodes,actual_pauses):
    assert ep['pause_request']==event;resume=next((q for q in events if q['event']=='resume' and q['at']>event['at']),None);assert ep['resume_close']==resume
    end=resume['at'][:10] if resume else r['raw'][-1]['at'][:10];days=[q for q in r['raw'] if event['at'][:10]<=q['at'][:10]<=end];off=[q for q in days if not q['on']];ff=[q for q in off if not q['layers']]
    assert len(off)==ep['paused_CLOSE_observations'] and len(ff)==ep['paused_flat_CLOSE_observations']
    intents={x['at'][:10]:x['intents'] for x in r['book']['decisions']};assert sum(len(intents[q['at'][:10]]) for q in off)==ep['recorded_paused_native_intents']==0
   act=dict(paused_closes=234,paused_actual_inventory_flat_closes=230,paused_held_closes=4,pause_episodes=3,unrecorded_counterfactual_opportunity_cost_not_identified=True)
 assert layers==3436 and closes==968 and sum(x['campaigns'] for x in camps)==2540 and len(summaries)==19
 for p,h in before.items():assert sha(p)==h,'Other agent sealed accounting bytes changed'
 SRC.update(P.SRC);SRC[str(Path(__file__).resolve())]=sha(__file__);SRC[str(SOURCE)]=sha(SOURCE)
 result=dict(status='PASS_INDEPENDENT_NATIVE19_STAGE10_PARTITION2540_CAMPAIGNS',original_layers=3436,original_CLOSEs=968,actual_campaigns=2540,all_observation_views=19,mutually_exclusive_three_year_stages=10,disjoint_three_year_net='-362010.3876489761400',ACT=act,checks=dict(COUNTS),maximum_numeric_residual=MAXRES,period_summaries=summaries,campaign_summaries=camps,new_accounts=0,new_account_events=0,accounting_files_unchanged=True,source_sha256=SRC,limits=['Only P01..P10 partition the weak calendar; FULL/YEAR/H2/ACT/924 views overlap and cannot be added. Strong starts another1m independently.','Actual sell cash is not period profit. Old/new layer wealth is actual endpoint component difference, not avoidable loss or causal allocation improvement.','CORE/mobile, entry actions and campaign names are actual account participation. They do not equal first market signal or independently fresh structure.','Held-CLOSE peak checks are descriptive and not executable same-CLOSE exits. ACT-off blank planning does not identify missing fundable trades or foregone profit.','Original consumed history, current membership/industry snapshot and native execution/corporate-action proxy limits remain.'])
 with target.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2,default=str);f.write('\n')
 print(result['status'],dict(COUNTS),str(MAXRES),flush=True)
if __name__=='__main__':main()
