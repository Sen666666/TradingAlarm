"""Read-only postprocessing. Never changes selection or feeds outcomes to the engine."""
import engine as s
from engine import pd,np,D,Path
import re
O=s.O;dest=O/'report';assert not dest.exists();dest.mkdir()
z=pd.read_csv(O/'economic/ROUNDS.csv',float_precision='round_trip',low_memory=False)
a=pd.read_csv(O/'economic/ACTIONS.csv',float_precision='round_trip',low_memory=False)
d=pd.read_csv(O/'economic/DECISIONS.csv',float_precision='round_trip',low_memory=False)
claims=s.read(O/'economic/CLAIMS.json');bridges=s.read(O/'economic/BRIDGES.json');closed='COMPLETE_CONDITIONAL_STOCK_ROUND'
claimby={};bridgeby={}
for x in claims:claimby.setdefault(x['owner_round_id'],[]).append(x)
for x in bridges:bridgeby.setdefault(x['round_id'],[]).append(x)
def day(x):return None if x is None or pd.isna(x) else pd.Timestamp(x)
def ud(u):
 row=u.get('row',u) if isinstance(u,dict) else {};v=row.get('1') or row.get('effective_date') or row.get('date')
 if v is None:
  m=re.search(r'\d{4}-\d{2}-\d{2}',str(u));return pd.Timestamp(m.group()) if m else None
 try:return pd.Timestamp(str(v)) if '-' in str(v) else pd.to_datetime(str(v),format='%Y%m%d')
 except:return None
cov=[]
for i,r in z.iterrows():
 rid=r.round_id;sid=r.sid;ent=day(r.get('entry_day'));end=day(r.get('exit_day')) if r.status==closed else day(r.get('status_day'));has=ent is not None;incl=r.status==closed or 'CENSORED' in r.status
 ac=s.local_actions(sid);raws=[];unparsed=[];why=ac.get('_source_issues',[])+ac.get('_source_coverage_issues',[])
 if not ac.get('_source_integrity_ok',False):why+=['ACTION_SOURCE_INTEGRITY_UNKNOWN']
 for e in ac.get('coverage_evidence',[]):
  try:
   raw=s.read(e['path']);ok=s.sha(e['path'])==e['sha256'];raws.append(dict(path=e['path'],sha256=e['sha256'],hash_ok=ok,records=len(raw.get('records',[]))))
   if not ok:why.append('RIGHTS_HASH_MISMATCH')
   if not raw.get('records'):why.append('RIGHTS_EMPTY')
   unparsed+=raw.get('unparsed',[])
  except Exception:why.append('RIGHTS_EVIDENCE_UNREADABLE')
 allun=unparsed+ac.get('unresolved',[])
 def inside(v):return has and v is not None and end is not None and ent<v and (v<=end if incl else v<end)
 acts=[x for x in ac['events'] if inside(day(x['effective_date']))];terminal=[x for x in ac['events'] if has and not incl and day(x['effective_date'])==end]
 undated=sum(ud(x) is None for x in allun);bad=[x for x in allun if inside(ud(x))]
 if undated:why.append('UNPARSED_UNDATED')
 if bad:why.append('UNPARSED_IN_HELD_INTERVAL')
 for e in acts:
  ee=s.EVENT_AT.get((sid,day(e['effective_date'])));owned=[c for c in claimby.get(rid,[]) if ee and c['economic_event_id']==ee['economic_event_id'] and c['recognized']]
  if ee is None or not owned:why.append('UNVERIFIED_HELD_ACTION:'+e['effective_date'])
 coverage='NO_CONFIRMED_HOLDING' if not has else 'COVERAGE_UNKNOWN' if why else 'VERIFIED_ACTIONS_SCENARIO' if acts else 'LOCAL_NO_ACTION_EVIDENCE'
 cov.append(dict(round_id=rid,event_id=r.event_id,sid=sid,execution_status=r.status,financial_coverage_status=coverage,evidence_usable_closed=r.status==closed and coverage in ['VERIFIED_ACTIONS_SCENARIO','LOCAL_NO_ACTION_EVIDENCE'],coverage_reasons=';'.join(sorted(set(why))),entry_day=r.get('entry_day'),interval_end=str(end.date()) if end else None,end_inclusive=incl,parsed_held_actions=len(acts),terminal_day_actions=terminal,unparsed_undated=undated,unparsed_in_interval=len(bad),rights_sources=raws,source_integrity_ok=ac.get('_source_integrity_ok',False)))
 if r.status!=closed:continue
 q=int(r.entry_q);bp=D(str(r.entry_price));sp=D(str(r.exit_price));_,bfm,bpa=s.getmeta(sid,day(r.entry_day));_,sfm,spa=s.getmeta(sid,day(r.exit_day));bf=s.fee(q,bp,bfm,'buy',bpa);sf=s.fee(q,sp,sfm,'sell',spa)
 assert abs(float(bf)-r.entry_fee)<1e-7
 cash=sum((D(c['core_amount']) for c in claimby.get(rid,[]) if c['recognized']),D(0));cost=D(q)*bp+bf;net=D(q)*sp-sf-cost+cash
 z.loc[i,['core_net','core_return','core_buy_cash','core_buy_fee','core_sell_fee','core_dividend_net80']]=[float(net),float(net/cost),float(cost),float(bf),float(sf),float(cash)]
cov=pd.DataFrame(cov);z=z.merge(cov[['round_id','financial_coverage_status','evidence_usable_closed','coverage_reasons']],on='round_id',validate='one_to_one')
def metric(g,layer):
 p,ret=('core_net','core_return') if layer=='core' else ('net_pnl','net_return_on_buy_cash');c=g[g.status.eq(closed)];w=c[c[p]>0];l=c[c[p]<=0]
 return dict(admitted=len(g),filled=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),closed=len(c),unknown=int(g.status.str.contains('UNKNOWN').sum()),censored=int(g.status.str.contains('CENSORED').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),wins=len(w),win_rate=len(w)/len(c) if len(c) else None,mean_return=float(c[ret].mean()) if len(c) else None,payoff_cny=float(w[p].mean()/-l[p].mean()) if len(w) and len(l) else None,tail_ge20=int(c[ret].ge(.2).sum()),tail_ge50=int(c[ret].ge(.5).sum()),coverage_unknown_closed=int(c.financial_coverage_status.eq('COVERAGE_UNKNOWN').sum()),not_account_return=True)
metrics=[dict(window=s.WINDOW,arm='A_UNION_B',layer=l,scope=scope,**metric(g,l)) for l in ['core','full'] for scope,g in [('CONDITIONAL_EXECUTION',z),('EVIDENCE_USABLE_CLOSED',z[z.evidence_usable_closed])]]
old=pd.read_csv(s.E/'relative_priority_v1/baseline/ROUNDS.csv',low_memory=False);old=old[old.window.eq(s.WINDOW)];join=old[['event_id','status','round_id']].merge(z[['event_id','status','round_id']],on='event_id',how='outer',suffixes=('_old','_new'),indicator=True)
prev2022=pd.read_csv(s.E/'relative_priority_equity_run_2022_v1/report/PERFORMANCE.csv');prev2022=prev2022[prev2022.arm.eq('A_UNION_B')&prev2022.scope.isin(['CONDITIONAL_EXECUTION','EVIDENCE_USABLE_CLOSED'])].copy();prev2022['window']='2022';comparison=pd.concat([prev2022,pd.DataFrame(metrics)],ignore_index=True);comparison=comparison.drop(columns=['independent_stock_net_sum'],errors='ignore')
summary=dict(version='2024_AB_165_NET80_V1',original_rounds=len(old),new_rounds=len(z),status_counts=z.status.value_counts().to_dict(),old_status_counts=old.status.value_counts().to_dict(),selection_event_overlap=join['_merge'].value_counts().to_dict(),financial_coverage_counts=cov.financial_coverage_status.value_counts().to_dict(),evidence_usable_closed=int(z.evidence_usable_closed.sum()),claims=len(claims),claim_events=len({c['economic_event_id'] for c in claims}),held_bridges=sum(b['kind']=='HELD_COORDINATE' for b in bridges),pending_zero_bridges=sum(b['kind']=='PENDING_COORDINATE_Q0' for b in bridges),all_claims_settled=all(c['settled'] for c in claims),metrics=metrics,limitations=['Current historical data and static pool NON_PIT','NET80 scenario not actual account tax/receipts','Historical orderability UNKNOWN; not shared account','Only165 events, later393 and shares unadmitted','Coverage and UNKNOWN nonrandom; not a selection-effect estimate','2022 vs2024 descriptive contexts with finite, different evidence sets, not complete equal-coverage claim'])
for name,frame in [('CORE_AND_FULL_ROUNDS',z),('PERFORMANCE',pd.DataFrame(metrics)),('FINANCIAL_COVERAGE',cov),('OLD_NEW_EVENT_STATUS',join),('YEAR_CONTEXT_COMPARISON',comparison)]:frame.to_csv(dest/(name+'.csv'),index=False)
s.save(dest/'SUMMARY.json',summary);s.save(dest/'SOURCE_HASHES.json',{str(p):s.sha(p) for p in [Path(__file__),O/'engine.py',O/'economic/OUTPUT_HASHES.json',s.E/'relative_priority_equity_run_2022_v1/report/PERFORMANCE.csv']});print('REPORT_DONE',summary)
