"""Read-only postprocessing. Never changes selection or feeds outcomes to the engine."""
import engine as s
from engine import pd,np,D,Path
import re
O=s.O;dest=O/'report';assert not dest.exists();dest.mkdir()
s.install_events(s.load_cash_candidates())
z=pd.read_csv(O/'ALL_FIXED46_ROUNDS.csv',float_precision='round_trip',low_memory=False)
a=pd.read_csv(O/'ALL_FIXED46_ACTIONS.csv',float_precision='round_trip',low_memory=False)
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
 p,ret=('core_net','core_return') if layer=='CORE' else ('net_pnl','net_return_on_buy_cash')
 closed_all=g[g.status.eq(closed)];c=g[g.evidence_usable_closed];w=c[c[p]>0];l=c[c[p]<=0]
 return dict(fixed_permits=len(g),filled=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),closed=len(closed_all),covered_closed=len(c),coverage_unknown_closed=len(closed_all)-len(c),wins=len(w),losses=len(l),covered_closed_win_rate=len(w)/len(c) if len(c) else None,covered_closed_mean_return=float(c[ret].mean()) if len(c) else None,payoff_cny=float(w[p].mean()/-l[p].mean()) if len(w) and len(l) and l[p].mean()<0 else None,tail_ge20=int(c[ret].ge(.2).sum()),tail_ge50=int(c[ret].ge(.5).sum()),not_account_return=True)
metrics=[dict(layer=l,scope=scope,**metric(g,l)) for l in ['CORE','FULL'] for scope,g in [('ALL_FIXED46',z),('RECOVERED_FIXED20',z[z.recovery_origin.eq('ORIGINAL_UNKNOWN_FIXED_PERMIT_RECOVERY')])]]
for name,frame in [('CORE_AND_FULL_ROUNDS',z),('PERFORMANCE',pd.DataFrame(metrics)),('FINANCIAL_COVERAGE',cov)]:frame.to_csv(dest/(name+'.csv'),index=False)
summary=dict(fixed_permits=46,recovered_permits=20,retained_permits=26,status_counts=z.status.value_counts().to_dict(),financial_coverage_counts=cov.financial_coverage_status.value_counts().to_dict(),claims=len(claims),all_claims_settled=all(c['settled'] for c in claims),metrics=metrics,limitations=['NON-PIT archived data and original frozen signals','Fixed permits only, not complete strategy or new selection','Original occupancy and reselection not rebuilt; restored fixed permits may overlap and the46 are not jointly realizable account trades','Independent stocks, not account return','NET80 conditional scenario, not actual account tax','Held, UNKNOWN, pending and nofill are not winners','CORE uses actual FULL entry/exit times and independently recomputed initial-layer fees'])
s.save(dest/'SUMMARY.json',summary)
lines=['# Fixed original 2026 H1 semiconductor permits','',f"46 original permits; 20 originally UNKNOWN paths examined. Status counts: {summary['status_counts']}",'','Only financially covered closed rounds count as winners. CORE is the initial layer on FULL actual timings, not a separately rerun strategy.','']
for m in metrics:lines.append(str(m))
lines+=['',*summary['limitations']];(dest/'READOUT.md').write_text('\n'.join(lines)+'\n')
s.save(dest/'OUTPUT_HASHES.json',{p.name:s.sha(p) for p in dest.iterdir() if p.is_file() and p.name!='OUTPUT_HASHES.json'})
print('REPORT_DONE',summary['status_counts'])
