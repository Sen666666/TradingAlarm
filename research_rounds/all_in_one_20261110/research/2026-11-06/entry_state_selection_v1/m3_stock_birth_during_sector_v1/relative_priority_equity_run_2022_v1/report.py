"""Read-only postprocessing: independent core fees/claims, coverage and attribution.
No market outcomes are fed into the consumers and no economic paths are rerun.
"""
import engine as s
from engine import pd,np,D,Path
import re,math
O=s.O;dest=O/'report';assert not dest.exists();dest.mkdir()
z=pd.read_csv(O/'dynamic/ROUNDS.csv',float_precision='round_trip',low_memory=False)
a=pd.read_csv(O/'dynamic/ACTIONS.csv',float_precision='round_trip',low_memory=False)
d=pd.read_csv(O/'dynamic/DECISIONS.csv',float_precision='round_trip',low_memory=False)
claims=s.read(O/'dynamic/CLAIMS.json');bridges=s.read(O/'dynamic/BRIDGES.json')
closed='COMPLETE_CONDITIONAL_STOCK_ROUND';claimby={};bridgeby={}
for c in claims:claimby.setdefault(c['owner_round_id'],[]).append(c)
for b in bridges:bridgeby.setdefault(b['round_id'],[]).append(b)
def day(v):
 if v is None or pd.isna(v):return None
 return pd.Timestamp(v)
def ud(u):
 row=u.get('row',u) if isinstance(u,dict) else {}
 v=row.get('1') or row.get('effective_date') or row.get('date')
 if v is None:
  m=re.search(r'\d{4}-\d{2}-\d{2}',str(u));return pd.Timestamp(m.group()) if m else None
 try:return pd.Timestamp(str(v)) if '-' in str(v) else pd.to_datetime(str(v),format='%Y%m%d')
 except:return None
cov=[]
for i,r in z.iterrows():
 rid=r.round_id;sid=r.sid;ent=day(r.get('entry_day'));end=day(r.get('exit_day')) if r.status==closed else day(r.get('status_day'));has=ent is not None
 incl=r.status==closed or ('CENSORED' in r.status);phase=r.get('failure_phase');ac=s.local_actions(sid);raws=[];unparsed=[];why=[]
 if ac.get('raw_response_empty'):why.append('ACTION_RAW_RESPONSE_EMPTY')
 if not ac.get('coverage_evidence'):why.append('NO_RIGHTS_SOURCE')
 for e in ac.get('coverage_evidence',[]):
  raw=s.read(e['path']);ok=s.sha(e['path'])==e['sha256'];raws.append(dict(path=e['path'],sha256=e['sha256'],hash_ok=ok,records=len(raw.get('records',[]))))
  if not ok:why.append('RIGHTS_HASH_MISMATCH')
  if not raw.get('records'):why.append('RIGHTS_EMPTY')
  unparsed+=raw.get('unparsed',[])
 unresolved=ac.get('unresolved',[]);allun=unparsed+unresolved
 def in_interval(v):return has and v is not None and ent<v and (v<=end if incl else v<end)
 inside=[e for e in ac['events'] if in_interval(day(e['effective_date']))];terminal=[e for e in ac['events'] if has and not incl and day(e['effective_date'])==end]
 undated=sum(ud(u) is None for u in allun);badinterval=[u for u in allun if in_interval(ud(u))]
 if undated:why.append('UNPARSED_UNDATED')
 if badinterval:why.append('UNPARSED_IN_HELD_INTERVAL')
 for e in inside:
  ee=s.EVENT_AT.get((sid,day(e['effective_date'])));owned=[c for c in claimby.get(rid,[]) if ee and c['economic_event_id']==ee['economic_event_id'] and c['recognized']]
  if ee is None or not ee['entitlement_verified'] or not owned:why.append('UNVERIFIED_HELD_ACTION:'+e['effective_date'])
 for b in bridgeby.get(rid,[]):assert b['economic_event_id'] in s.EVENT_BY_ID
 coverage='NO_CONFIRMED_HOLDING' if not has else 'COVERAGE_UNKNOWN' if why else 'VERIFIED_ACTIONS_SCENARIO' if inside else 'LOCAL_NO_ACTION_EVIDENCE'
 available=r.status==closed and coverage in ('VERIFIED_ACTIONS_SCENARIO','LOCAL_NO_ACTION_EVIDENCE')
 cr=dict(round_id=rid,event_id=r.event_id,arm=r.arm,sid=sid,execution_status=r.status,financial_coverage_status=coverage,evidence_usable_closed=available,coverage_reasons=';'.join(sorted(set(why))),entry_day=r.get('entry_day'),interval_end=str(end.date()) if end else None,end_inclusive=incl,failure_phase=phase,holding_calendar_days=(end-ent).days if has and end is not None else None,birth_quarter=str(pd.Timestamp(r.signal_day).to_period('Q')),parsed_held_actions=len(inside),held_action_dates=[e['effective_date'] for e in inside],terminal_day_actions=terminal,historical_unparsed_count=len(allun),unparsed_inside_count=len(badinterval),unparsed_undated_count=undated,rights_sources=raws,coordinate_entry_bridges=len([b for b in bridgeby.get(rid,[]) if b['kind']=='PENDING_COORDINATE_Q0']))
 cov.append(cr)
 if r.status!=closed:continue
 q=int(r.entry_q);bp=D(str(r.entry_price));sp=D(str(r.exit_price));_,bfs,bpa=s.getmeta(sid,pd.Timestamp(r.entry_day));_,sfs,spa=s.getmeta(sid,pd.Timestamp(r.exit_day));bf=s.fee(q,bp,bfs,'buy',bpa);sf=s.fee(q,sp,sfs,'sell',spa)
 assert abs(float(bf)-r.entry_fee)<1e-7
 cc=sum((D(c['core_amount']) for c in claimby.get(rid,[]) if c['recognized']),D(0));cost=D(q)*bp+bf;net=D(q)*sp-sf-cost+cc
 z.loc[i,['core_net','core_return','core_buy_cash','core_buy_fee','core_sell_fee','core_dividend_net80']]=[float(net),float(net/cost),float(cost),float(bf),float(sf),float(cc)]
coverage=pd.DataFrame(cov);z=z.merge(coverage[['round_id','financial_coverage_status','evidence_usable_closed','coverage_reasons','holding_calendar_days','birth_quarter']],on='round_id',validate='one_to_one')
metrics=[]
def metric(g,layer):
 p,ret=('core_net','core_return') if layer=='core' else ('net_pnl','net_return_on_buy_cash');c=g[g.status.eq(closed)];w=c[c[p].gt(0)];loss=c[c[p].le(0)]
 return dict(admitted=len(g),filled=int(g.entry_status.eq('CONDITIONAL_OPEN_PROXY').sum()),closed=len(c),unknown=int(g.status.str.contains('UNKNOWN').sum()),censored=int(g.status.str.contains('CENSORED').sum()),nofill=int(g.status.str.contains('NOFILL').sum()),wins=len(w),win_rate=len(w)/len(c) if len(c) else None,independent_stock_net_sum=float(c[p].sum()),mean_return=float(c[ret].mean()) if len(c) else None,payoff_cny=float(w[p].mean()/-loss[p].mean()) if len(w) and len(loss) else None,tail_ge20=int(c[ret].ge(.2).sum()),tail_ge50=int(c[ret].ge(.5).sum()),coverage_unknown_closed=int((c.financial_coverage_status=='COVERAGE_UNKNOWN').sum()),not_account_return=True)
for arm,g in z.groupby('arm'):
 for layer in ['core','full']:
  for scope,gg in [('CONDITIONAL_EXECUTION',g),('EVIDENCE_USABLE_CLOSED',g[g.evidence_usable_closed])]:metrics.append(dict(arm=arm,layer=layer,scope=scope,**metric(gg,layer)))
base=z[z.arm.eq('A_UNION_B')].set_index('event_id');fresh=z[z.arm.eq('RELATIVE_UP_PRIORITY')].set_index('event_id');common=sorted(set(base.index)&set(fresh.index));commonclosed=[e for e in common if base.loc[e,'status']==fresh.loc[e,'status']==closed];commonevidence=[e for e in commonclosed if base.loc[e,'evidence_usable_closed'] and fresh.loc[e,'evidence_usable_closed']]
# Strong common-market-event invariant: prior-round claims cannot alter same new round.
checks=[]
for eid in common:
 b=base.loc[eid];f=fresh.loc[eid]
 for c in ['status','entry_day','entry_q','entry_price','exit_day','exit_price','net_pnl','core_net','dividend_net80_total','added_q','financial_coverage_status']:
  x=b.get(c);y=f.get(c)
  if pd.isna(x) and pd.isna(y):continue
  if isinstance(x,(float,np.floating,int,np.integer)) and isinstance(y,(float,np.floating,int,np.integer)):assert np.isclose(x,y,atol=1e-7,rtol=1e-12),(eid,c,x,y)
  else:assert x==y,(eid,c,x,y)
 ba=a[a.round_id.eq(b.round_id)][['day','side','q','price','fee','reason']].reset_index(drop=True);fa=a[a.round_id.eq(f.round_id)][['day','side','q','price','fee','reason']].reset_index(drop=True);pd.testing.assert_frame_equal(ba,fa,check_exact=False,atol=1e-7,rtol=1e-12)
 bc=[{k:c[k] for k in ['economic_event_id','record_q','core_record_q','amount','core_amount','recognized','settled']} for c in claimby.get(b.round_id,[])];fc=[{k:c[k] for k in ['economic_event_id','record_q','core_record_q','amount','core_amount','recognized','settled']} for c in claimby.get(f.round_id,[])];assert bc==fc,(eid,'claims')
 checks.append(dict(event_id=eid,actions_identical=True,claims_identical=True,outcomes_identical=True))
for scope,ids in [('COMMON_CLOSED',commonclosed),('COMMON_EVIDENCE_CLOSED',commonevidence)]:
 for arm,g in [('A_UNION_B',base),('RELATIVE_UP_PRIORITY',fresh)]:
  for layer in ['core','full']:metrics.append(dict(arm=arm,layer=layer,scope=scope,**metric(g.loc[ids],layer)))
newids=sorted(set(fresh.index)-set(base.index));lostids=sorted(set(base.index)-set(fresh.index));attribution=[]
for cohort,g in [('BASELINE_ONLY',base.loc[lostids]),('FRESH_ONLY',fresh.loc[newids]),('COMMON',base.loc[common])]:
 for layer in ['core','full']:attribution.append(dict(cohort=cohort,layer=layer,**metric(g,layer)))
# Join choice receipts across each arm; no score/outcome is used as an input.
for g,label in [(base.loc[lostids],'BASELINE_ONLY'),(fresh.loc[newids],'FRESH_ONLY')]:
 pass
selection=z.merge(s.ev[['event_id','relative_known','relative_event']],on='event_id',validate='many_to_one');selection['selection_cohort']=selection.event_id.map(lambda e:'COMMON' if e in common else 'BASELINE_ONLY' if e in lostids else 'FRESH_ONLY')
# Same-stock intervals use only confirmed prefixes for UNKNOWN, not presumed frozen holdings.
tails=[];overlaps=[]
for layer,p,ret in [('core','core_net','core_return'),('full','net_pnl','net_return_on_buy_cash')]:
 cohort=base[base.status.eq(closed)&base[ret].ge(.5)]
 for eid,b in cohort.iterrows():
  cand=fresh[fresh.sid.eq(b.sid)];os=[]
  for feid,f in cand.iterrows():
   if pd.isna(f.entry_day):continue
   right=day(f.exit_day) if f.status==closed else day(f.status_day);left=day(f.entry_day)
   overlap=right is not None and max(day(b.entry_day),left)<min(day(b.exit_day),right)
   cover=overlap and left<=day(b.entry_day) and right>=day(b.exit_day)
   row=dict(layer=layer,baseline_event_id=eid,fresh_event_id=feid,sid=b.sid,baseline_entry=b.entry_day,baseline_exit=b.exit_day,fresh_entry=f.entry_day,fresh_endpoint=str(right.date()) if right else None,fresh_status=f.status,overlap=overlap,full_interval_cover=cover,same_exit=f.status==closed and day(f.exit_day)==day(b.exit_day),entry_relation='EARLIER' if left<day(b.entry_day) else 'LATER' if left>day(b.entry_day) else 'SAME',baseline_return=b[ret],fresh_return=f[ret] if f.status==closed else None)
   overlaps.append(row)
   if overlap:os.append(row)
  tails.append(dict(layer=layer,baseline_event_id=eid,sid=b.sid,event_retained=eid in fresh.index,overlapping_same_stock_rounds=len(os),any_full_cover=any(x['full_interval_cover'] for x in os),any_same_exit=any(x['same_exit'] for x in os),classification='SAME_EVENT_RETAINED' if eid in fresh.index else 'EARLIER_FULL_COVER' if any(x['full_interval_cover'] for x in os) else 'PARTIAL_OVERLAP' if os else 'NO_CONFIRMED_OVERLAP'))
# Coverage by event type, entry quarter and duration makes missingness visible, not random.
groups=[]
z['duration_bucket']=pd.cut(z.holding_calendar_days,[-1,5,20,60,120,365,99999],labels=['0-5','6-20','21-60','61-120','121-365','366+']).astype(str)
for field in ['event_type','birth_quarter','duration_bucket','financial_coverage_status']:
 for (arm,value),g in z.groupby(['arm',field],dropna=False):groups.append(dict(arm=arm,group_field=field,group_value=value,coverage_counts=g.financial_coverage_status.value_counts().to_dict(),**metric(g,'full')))
summary=dict(calculation_version='DYNAMIC_2022_NET80_V1',common_admitted=len(common),common_closed=len(commonclosed),common_evidence_closed=len(commonevidence),baseline_only=len(lostids),fresh_only=len(newids),common_rounds_identical=True,metrics=metrics,attribution=attribution,tail_classifications=pd.DataFrame(tails).groupby(['layer','classification']).size().to_dict(),scope='2022 births only, own dynamic FULL state until 2026-06-30; core standalone-fee initial-lot diagnostic at FULL entry/exit, not extra strategy.',limitations=['NON-PIT pool and historical source coordinates','NET80 cash scenario not actual tax','Unknown orderability, not shared account or full quick-entry strategy','436 finite admitted economic events, unverified later events stay UNKNOWN','Conditional results are not fully financially certified; incomplete source coverage may affect whole dynamic queue, not just excluded PnL. Nonrandom UNKNOWN exclusion is not a strategy-effect estimate.'])
summary['tail_classifications']={str(k):v for k,v in summary['tail_classifications'].items()}
for name,frame in [('CORE_AND_FULL_ROUNDS',z),('PERFORMANCE',pd.DataFrame(metrics)),('FINANCIAL_COVERAGE',coverage),('COMMON_EVENT_QA',pd.DataFrame(checks)),('NEW_LOST_ATTRIBUTION',pd.DataFrame(attribution)),('SELECTION_DETAIL',selection),('BASELINE_TAILS',pd.DataFrame(tails)),('TAIL_SAME_STOCK_OVERLAP',pd.DataFrame(overlaps)),('COVERAGE_DISTRIBUTIONS',pd.DataFrame(groups))]:frame.to_csv(dest/(name+'.csv'),index=False)
base.add_prefix('baseline_').join(fresh.add_prefix('fresh_'),how='outer').to_csv(dest/'EVENT_COMPARISON.csv')
s.save(dest/'SUMMARY.json',summary);s.save(dest/'SOURCE_HASHES.json',s.hashes)
print(pd.DataFrame(metrics).query("scope=='CONDITIONAL_EXECUTION'").to_string(index=False));print('COMMON',len(common),len(commonclosed),len(commonevidence),'ONLY',len(lostids),len(newids));print('TAILS',summary['tail_classifications'])
