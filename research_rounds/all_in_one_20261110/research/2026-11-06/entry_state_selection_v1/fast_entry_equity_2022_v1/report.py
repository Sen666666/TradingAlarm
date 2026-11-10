"""Postprocess only sealed action ledgers. Never rerun a lifecycle."""
import lifecycle as l
s=l.s
import pandas as pd,numpy as np,re,json
from decimal import Decimal as D
from pathlib import Path
O=Path(__file__).resolve().parent;dest=O/'report';assert not dest.exists();dest.mkdir()
closed='COMPLETE_CONDITIONAL_STOCK_ROUND'
base=pd.read_csv(l.BASE/'report/CORE_AND_FULL_ROUNDS.csv',low_memory=False,float_precision='round_trip');base=base[base.arm.eq('A_UNION_B')].copy()
new=pd.read_csv(O/'economic/ROUNDS.csv',low_memory=False,float_precision='round_trip')
actions=pd.concat([pd.read_csv(l.BASE/'dynamic/ACTIONS.csv',low_memory=False,float_precision='round_trip').query("arm=='A_UNION_B'"),pd.read_csv(O/'economic/ACTIONS.csv',low_memory=False,float_precision='round_trip')],ignore_index=True)
allclaims=s.read(l.BASE/'dynamic/CLAIMS.json')+s.read(O/'economic/CLAIMS.json')
cb={}
for c in allclaims:cb.setdefault(c['owner_round_id'],[]).append(c)
def day(x):return None if x is None or pd.isna(x) else pd.Timestamp(x)
def undated(u):
 row=u.get('row',u) if isinstance(u,dict) else {};v=row.get('1') or row.get('effective_date') or row.get('date')
 if v is None:
  m=re.search(r'\d{4}-\d{2}-\d{2}',str(u));return pd.Timestamp(m.group()) if m else None
 try:return pd.Timestamp(str(v)) if '-' in str(v) else pd.to_datetime(str(v),format='%Y%m%d')
 except:return None
coverage=[]
def cov(r,layer,end,terminal_inclusive):
 sid=r.sid;ent=day(r.get('entry_day'));has=ent is not None;ac=s.local_actions(sid);why=[];unparsed=[];source=[]
 if ac.get('raw_response_empty'):why.append('ACTION_RAW_RESPONSE_EMPTY')
 if not ac.get('coverage_evidence'):why.append('NO_RIGHTS_SOURCE')
 for e in ac.get('coverage_evidence',[]):
  raw=s.read(e['path']);h=s.sha(e['path']);assert h==e['sha256'];s.hashes[e['path']]=h
  source.append(dict(path=e['path'],sha256=h,records=len(raw.get('records',[]))))
  if not raw.get('records'):why.append('RIGHTS_EMPTY')
  unparsed+=raw.get('unparsed',[])
 unparsed+=ac.get('unresolved',[])
 def inside(v):return has and v is not None and end is not None and ent<v and (v<=end if terminal_inclusive else v<end)
 held=[e for e in ac['events'] if inside(day(e['effective_date']))]
 if any(undated(u) is None for u in unparsed):why.append('UNPARSED_UNDATED')
 if any(inside(undated(u)) for u in unparsed):why.append('UNPARSED_IN_HELD_INTERVAL')
 for e in held:
  ee=s.EVENT_AT.get((sid,day(e['effective_date'])))
  own=[c for c in cb.get(r.round_id,[]) if ee and c['economic_event_id']==ee['economic_event_id'] and c['recognized'] and (D(c['core_amount'])>0 if layer=='initial' else D(c['amount'])>0)]
  if ee is None or not ee['entitlement_verified'] or not own:why.append('UNVERIFIED_HELD_ACTION:'+e['effective_date'])
 status='NO_CONFIRMED_HOLDING' if not has else 'COVERAGE_UNKNOWN' if why else 'VERIFIED_ACTIONS_SCENARIO' if held else 'LOCAL_NO_ACTION_EVIDENCE'
 out=dict(arm=r.arm,round_id=r.round_id,layer=layer,entry_day=r.get('entry_day'),interval_end=str(end.date()) if end is not None else None,end_inclusive=terminal_inclusive,coverage_status=status,coverage_reasons=';'.join(sorted(set(why))),held_actions=len(held),source_records=source)
 coverage.append(out);return status
base['entry_role']='I_CORE';base['initial_exit_day']=base.exit_day;base['initial_exit_price']=base.exit_price;base['source_mask']='AB';base['AB_event_id']=base.event_id
z=pd.concat([base,new],ignore_index=True);rows=[]
for _,r in z.iterrows():
 q=r.to_dict();rid=r.round_id;fullclosed=r.status==closed;end=day(r.get('exit_day')) if fullclosed else day(r.get('status_day'))
 fc=cov(r,'full',end,fullclosed or 'CENSORED' in r.status)
 q['full_evidence_usable']=fullclosed and fc in ('VERIFIED_ACTIONS_SCENARIO','LOCAL_NO_ACTION_EVIDENCE');q['full_coverage_status']=fc
 ie=day(r.get('initial_exit_day'));ip=r.get('initial_exit_price')
 initialclosed=ie is not None and pd.notna(ip) and pd.notna(r.get('entry_day'))
 ic=cov(r,'initial',ie if initialclosed else end,initialclosed or 'CENSORED' in r.status)
 q['initial_closed']=initialclosed;q['initial_evidence_usable']=initialclosed and ic in ('VERIFIED_ACTIONS_SCENARIO','LOCAL_NO_ACTION_EVIDENCE');q['initial_coverage_status']=ic
 q['initial_closed_full_unclosed']=initialclosed and not fullclosed
 if initialclosed:
  n=int(r.entry_q);bp=D(str(r.entry_price));sp=D(str(ip));_,bfs,bpa=s.getmeta(r.sid,day(r.entry_day));_,sfs,spa=s.getmeta(r.sid,ie);bf=s.fee(n,bp,bfs,'buy',bpa);sf=s.fee(n,sp,sfs,'sell',spa)
  claim=sum((D(c['core_amount']) for c in cb.get(rid,[]) if c['recognized']),D(0));cost=n*bp+bf;net=n*sp-sf-cost+claim
  q.update(initial_net=float(net),initial_return=float(net/cost),initial_buy_cash=float(cost),initial_buy_fee=float(bf),initial_sell_fee=float(sf),initial_net80=float(claim))
  if r.arm=='A_UNION_B':assert np.isclose(float(net),r.core_net,atol=1e-7) and q['initial_evidence_usable']==r.evidence_usable_closed
 rows.append(q)
z=pd.DataFrame(rows);aa=actions
# First-lot actual sell identity and separate fee recomputation independent of output endpoint.
for r in z[z.initial_closed].itertuples():
 g=aa[aa.round_id.eq(r.round_id)];sell=g[g.side.eq('sell_initial')]
 if len(sell):assert len(sell)==1 and int(sell.iloc[0].q)==int(r.entry_q) and day(sell.iloc[0].day)==day(r.initial_exit_day)
 else:
  sell=g[g.side.eq('sell_all')];assert len(sell)==1 and day(sell.iloc[0].day)==day(r.initial_exit_day)
 assert np.isclose(sell.iloc[0].price,r.initial_exit_price)
def metric(g,layer,scope):
 col,ret,cl,usable=('initial_net','initial_return','initial_closed','initial_evidence_usable') if layer=='initial' else ('net_pnl','net_return_on_buy_cash',None,'full_evidence_usable')
 done=g[g[cl]] if cl else g[g.status.eq(closed)]
 if scope=='EVIDENCE_USABLE':done=done[done[usable]]
 win=done[col].gt(0);loss=done[col].le(0)
 return dict(admitted=len(g),confirmed_filled=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),execution_unknown=int(g.status.str.contains('UNKNOWN').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),censored=int(g.status.str.contains('CENSORED').sum()),conditional_closed=int(g[cl].sum()) if cl else int(g.status.eq(closed).sum()),financial_unknown_closed=int(((g[cl] if cl else g.status.eq(closed))&~g[usable]).sum()),usable_closed=len(done),wins=int(win.sum()),losses=int(loss.sum()),win_rate=float(win.mean()) if len(done) else None,net_sum=float(done[col].sum()) if len(done) else None,mean_net=float(done[col].mean()) if len(done) else None,mean_return=float(done[ret].mean()) if len(done) else None,winner_net_sum=float(done.loc[win,col].sum()),loser_net_sum=float(done.loc[loss,col].sum()),tail30=int(done[ret].ge(.3).sum()),tail50=int(done[ret].ge(.5).sum()),initial_closed_full_unclosed=int(g.initial_closed_full_unclosed.sum()))
metrics=[]
for arm,g in z.groupby('arm'):
 for layer in ['initial','full']:
  for scope in ['CONDITIONAL','EVIDENCE_USABLE']:metrics.append(dict(arm=arm,layer=layer,scope=scope,**metric(g,layer,scope)))
strata=[]
for arm,g in z.groupby('arm'):
 for field in ['entry_role','source_mask','event_type']:
  for val,gg in g.groupby(field,dropna=False):
   for layer in ['initial','full']:strata.append(dict(arm=arm,field=field,value=val,layer=layer,**metric(gg,layer,'EVIDENCE_USABLE')))
base=z[z.arm.eq('A_UNION_B')].set_index('event_id');new=z[z.arm.eq('AB_FAST_SMALL')].set_index('event_id')
bd=pd.read_csv(l.BASE/'dynamic/DECISIONS.csv',low_memory=False);bd=bd[bd.arm.eq('A_UNION_B')]
nd=pd.read_csv(O/'economic/DECISIONS.csv',low_memory=False);ni=nd.set_index('event_id');newrounds=new.set_index('round_id',drop=False)
attrib=[]
for eid,b in base.iterrows():
 n=ni.loc[eid] if eid in ni.index else None
 if n is None:kind='AB_EVENT_NOT_IN_NEW_INPUT'
 elif n.selected:kind='SAME_AB_INVITATION'
 elif n.decision=='PASS_NOT_TOP2':kind='SAME_CLOSE_NOT_TOP2'
 elif n.decision.startswith('BLOCKED_'):kind=n.decision
 else:kind=n.decision
 out=dict(baseline_event_id=eid,sid=b.sid,name=b.get('name'),baseline_signal=b.signal_day,baseline_entry=b.entry_day,baseline_exit=b.exit_day,baseline_initial_net=b.initial_net,baseline_initial_return=b.initial_return,baseline_evidence_usable=b.initial_evidence_usable,disposition=kind,new_blocking_round_id=n.get('blocking_round_id') if n is not None else None)
 if n is not None:
  selected=nd[nd.day.eq(n.day)&nd.sector.eq(n.sector)&nd.selected]
  out['selected_same_day_sid']=';'.join(selected.sid);out['selected_same_day_sources']=';'.join(selected.source_mask.fillna(''))
  out['new_selected_non_AB_same_day']=int(selected.AB_event_id.isna().sum())
 attrib.append(out)
attrib=pd.DataFrame(attrib);assert not attrib.disposition.eq('AB_EVENT_NOT_IN_NEW_INPUT').any()
tails=[];overlaps=[]
for eid,b in base[base.initial_evidence_usable&base.initial_return.ge(.5)].iterrows():
 candidates=new[new.sid.eq(b.sid)];hit=[]
 for ne,n in candidates.iterrows():
  left=day(n.entry_day);right=day(n.exit_day) if n.status==closed else day(n.status_day);be,bx=day(b.entry_day),day(b.exit_day)
  if left is None or right is None:continue
  overlap=max(be,left)<min(bx,right)
  if not overlap:continue
  initial_right=day(n.initial_exit_day);row=dict(baseline_event_id=eid,new_event_id=ne,sid=b.sid,new_role=n.entry_role,new_status=n.status,new_entry=n.entry_day,new_endpoint=right,any_inventory_full_cover=left<=be and (right>=bx if n.status==closed else right>bx),initial_full_cover=left<=be and initial_right is not None and initial_right>=bx,new_initial_net=n.initial_net if n.initial_evidence_usable else None,new_full_net=n.net_pnl if n.full_evidence_usable else None)
  overlaps.append(row);hit.append(row)
 tails.append(dict(baseline_event_id=eid,sid=b.sid,name=b['name'],baseline_initial_return=b.initial_return,baseline_initial_net=b.initial_net,same_event=eid in new.index,overlapping_rounds=len(hit),any_inventory_full_cover=any(r['any_inventory_full_cover'] for r in hit),initial_full_cover=any(r['initial_full_cover'] for r in hit),new_overlap_known_initial_net=sum(r['new_initial_net'] for r in hit if r['new_initial_net'] is not None),new_overlap_known_full_net=sum(r['new_full_net'] for r in hit if r['new_full_net'] is not None),classification='SAME_EVENT' if eid in new.index else 'EARLIER_FULL_COVER' if any(r['any_inventory_full_cover'] for r in hit) else 'PARTIAL_OVERLAP' if hit else 'NO_CONFIRMED_OVERLAP'))
# Fixed 9 mechanism dates: original candidate/decision and actual new path separately.
cases=pd.read_csv(l.R/'dynamic_entry_formation_mechanism_v1/POSTHOC_TIMING_CASES.csv',usecols=['sid','C_signal']).rename(columns={'C_signal':'day'}).drop_duplicates()
bounds=pd.read_csv(l.R/'dynamic_entry_formation_mechanism_v1/FIXED_CLOCK_BOUNDARY_CASES.csv',usecols=['sid','day']);cases=pd.concat([cases,bounds],ignore_index=True)
cases=cases.merge(nd,on=['sid','day'],how='left',validate='one_to_one').merge(z[z.arm.eq('AB_FAST_SMALL')].drop(columns=['sid','arm','event_id','day'],errors='ignore'),on='round_id',how='left',suffixes=('','_outcome'),validate='many_to_one')
# Common I-role same-event economics should remain identical except explicit event/consumption metadata.
common=[]
for eid in set(base.index)&set(new.index):
 b,n=base.loc[eid],new.loc[eid]
 if n.entry_role!='I_CORE':continue
 for c in ['status','entry_day','entry_q','entry_price','exit_day','exit_price','net_pnl','initial_net','dividend_net80_total','added_q']:
  x,y=b.get(c),n.get(c)
  if pd.isna(x) and pd.isna(y):continue
  if isinstance(x,(int,float,np.number)) and isinstance(y,(int,float,np.number)):assert np.isclose(x,y,atol=1e-7,rtol=1e-12),(eid,c,x,y)
  else:assert str(x)==str(y),(eid,c,x,y)
 common.append(dict(event_id=eid,unchanged_I_role_economics=True))
period=[]
for arm,g in z.groupby('arm'):
 for layer in ['initial','full']:
  col='initial_exit_day' if layer=='initial' else 'exit_day'
  gg=g[pd.to_datetime(g[col]).le(pd.Timestamp('2022-12-31'))]
  full_scope=metric(g,layer,'EVIDENCE_USABLE')
  period.append(dict(arm=arm,layer=layer,scope='CLOSED_DURING_2022_NOT_ACCOUNT',year_closed_selected=len(gg),**{'full_arm_'+k:v for k,v in full_scope.items() if k in ['admitted','confirmed_filled','execution_unknown','nofill','censored','initial_closed_full_unclosed','conditional_closed','financial_unknown_closed']},**metric(gg,layer,'EVIDENCE_USABLE')))
for name,frame in [('INITIAL_AND_FULL_ROUNDS',z),('PERFORMANCE',pd.DataFrame(metrics)),('STRATA',pd.DataFrame(strata)),('FINANCIAL_COVERAGE',pd.DataFrame(coverage)),('BASELINE_AB_DISPOSITION',attrib),('BASELINE_44_TAILS',pd.DataFrame(tails)),('TAIL_OVERLAPS',pd.DataFrame(overlaps)),('FIXED_2022_CASES',cases),('COMMON_I_EVENT_QA',pd.DataFrame(common)),('CLOSED_2022',pd.DataFrame(period))]:frame.to_csv(dest/(name+'.csv'),index=False)
summary=dict(metrics=metrics,common_I_identical=len(common),AB_dispositions=attrib.disposition.value_counts().to_dict(),tail_classes=pd.DataFrame(tails).classification.value_counts().to_dict(),scope='One new small-entry lifecycle arm, frozen original dynamic baseline; no shared account/annualization; original current-fixed pool and NET80 admitted 436 action scope only.')
s.save(dest/'SUMMARY.json',summary);s.save(dest/'SOURCE_HASHES.json',s.hashes)
print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
