"""Exact prior63 industry rejection audit; saved books only, no candidate engine."""
import json,math
from collections import defaultdict
from decimal import Decimal as D
import pandas as pd
import audit_pvr_saved as I
import audit_ma_information as A
O=I.TASK/'pvr_pool_feasibility/current_evidence_design';Z=D(0);CACHE={}
def main():
 sources=I.read(O/'B_EXACT_SOURCE_SHA256.json')
 for p,h in sources.items():assert I.sha(p)==h
 frozen=I.read(O/'DESIGN_FREEZE.json')
 for p,h in frozen['files'].items():assert I.sha(O/p)==h
 results=I.read(O/'B_EXACT_RESULTS.json')['results'];summary={};root=I.TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024'
 for ref,run in [('2022_2024',root/'no60/run-2024/pair'),('strong',I.TASK/'pvr_pool_feasibility/runs/2025_26/pair')]:
  ee=I.read(O/(ref+'_B_EXACT_ENTRIES.json'));previous=I.read(A.O/(ref+'_ENTRIES.json'));pm={x['layer']:x for x in previous};er={x['layer']:x for x in ee};v=results[ref]
  assert len(ee)==len(pm)==v['overall']['fills']
  for x in ee:
   old=pm[x['layer']]
   for k,val in old.items():assert x[k]==val or (k in ['strict_realized','open_unrealized','recognized_dividend_AR','buy_fee','sell_fee','remaining_basis']and abs(D(x[k])-D(val))<D('1e-8')),(ref,x['layer'],k)
   s=x['sector'];day=x['decision_at'][:10];key=(s,day);b=x['B_exact']
   if key not in CACHE:
    f=A.frame(s);j=f.index.get_loc(pd.Timestamp(day));w=f.iloc[j-63:j];current=f.iloc[j]
    valid=len(w)==63 and pd.notna(current.segment_id)and all(w.segment_id==current.segment_id)and all(math.isfinite(p)and p>0 for p in w.close)and math.isfinite(current.close)and current.close>0
    assert b['known']==valid
    if valid:
     ma=sum(float(p)for p in w.close)/63;c=float(current.close);assert b['pass_B']==(c>ma);A.close(ma,b['prior63_mean']);A.close(c,b['current_close'])
     assert b['prior_first']==str(w.index[0].date())and b['prior_last']==str(w.index[-1].date())<day and b['prior_count']==63
    CACHE[key]=b
   else:assert CACHE[key]==b
   assert x['B_class']==('UNKNOWN'if b['pass_B']is None else'PASS'if b['pass_B']else'FAIL')
  for g in v['groups']['by_B']:
   rr=[x for x in ee if x['B_class']==g['labels']['B_class']];assert len(rr)==g['fills'];A.close(sum((D(x['cost'])for x in rr),Z),g['actual_buy_cash']);A.close(sum((D(x['net'])for x in rr),Z),g['net_lifetime'])
  # Replay native economic events to fixed decision-B groups, no admission intervention.
  b=I.read(run/'B.json.gz');ds=I.rows(run/'daily.jsonl.gz');raw={x['id']:x for x in b['layers']};events=[(t['at'],1,j,'trade',t)for j,t in enumerate(b['trades'])]
  for j,t in enumerate(b['audit']):
   if t['kind']=='split':events.append((t['at'],0,j,'split',t))
   elif t['kind']=='dividend_accrual':events.append((t['receivable']['ex_at'],2,j,'div',t['receivable']))
  events.sort(key=lambda x:x[:3]);ei=0;state={};prior={};history=[]
  for d in ds:
   while ei<len(events)and events[ei][0]<=d['at']:
    _,_,_,kind,t=events[ei];ei+=1
    if kind=='split':
     for x in state.values():
      if x['sid']==t['sid']:
       q=D(x['q'])*D(t['ratio']);assert q==int(q);x['q']=int(q)
    elif kind=='div':
     held=[x for x in state.values()if x['sid']==t['security_id']and x['q']];q=sum(x['q']for x in held)
     for x in held:x['div']+=D(t['net_local'])*D(x['q'])/D(q)
    elif t['side']=='buy':state[t['layer']]={'sid':t['security_id'],'q':t['shares'],'cash':-D(t['gross_cny'])-D(t['fees_cny']),'div':Z}
    else:
     for part in t['parts']:state[part['layer']]['q']-=part['shares'];state[part['layer']]['cash']+=D(part['net_cash'])
   now=defaultdict(lambda:Z);day=d['at'][:10]
   for lid,x in state.items():now[er[lid]['B_class']]+=x['cash']+x['div']+(D(x['q'])*I.price(x['sid'],day)if x['q']else Z)
   A.close(sum(now.values(),Z),D(d['nav'])-1000000)
   for g in ['PASS','FAIL','UNKNOWN']:history.append((day,g,now[g]-prior.get(g,Z)))
   prior=now
  for lid,x in state.items():A.close(x['cash'],raw[lid]['cash']);A.close(x['div'],raw[lid]['dividend']);assert x['q']==raw[lid]['qty']
  phases=I.read(O/(ref+'_B_EXACT_ACTUAL_PHASE_WEALTH.json'))
  for r in phases:A.close(sum((v for day,g,v in history if g==r['B_class']and r['lo']<=day<=r['hi']),Z),r['actual_phase_wealth'])
  oldtails=I.read(A.O/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'));tails=I.read(O/(ref+'_B_EXACT_ORIGINAL_FIXED_TAIL.json'))
  assert {x['original']['layer']for x in oldtails}=={x['original']['layer']for x in tails}
  for t in tails:
   p=next(x for x in oldtails if x['original']['layer']==t['original']['layer']);assert p['original']==t['original']and p['matched_No60_layers']==t['matched_No60_layers']
  post=[x for x in ee if ref=='2022_2024'and x['opened'][:10]>'2024-10-08']
  summary[ref]={'passed':True,'all_fills':len(ee),'daily_group_bridges':len(ds),'phase_rows':len(phases),'full_by_B':v['groups']['by_B'],'original_fixed_tails':v['original_fixed_tail_by_B'],'postOct8_303':{'fills':len(post),'B_PASS':sum(x['B_class']=='PASS'for x in post),'confirmed_B_PASS':sum(x['B_class']=='PASS'and x['pool_at_fill']=='confirmed'for x in post),'net':str(sum((D(x['net'])for x in post),Z))},'changed_vs_inclusive_fills':v['changed_vs_inclusive']['fills']}
 out={'passed':True,'results':summary,'source_SHA_checks':len(sources),'unique_exact_prior63_snapshots':len(CACHE),'reviewer_account_events':0,'reviewer_source_SHA256':I.sha(__file__),'verdict':'STOP_B_AS_CORE_LOSS_REPAIR; NO_B_OR_AB_ECONOMIC_TRIAL_SUPPORTED','scope':'Complete funded actual-fill mothers, exact previous63 excludes current and uses original source segments/decision dates; fixed-at-entry-B monetary partitions, every daily and phase cash/div/rawinventory bridge independently replayed. Complete originalfixedtail identity sets retained from separately audited MA study. Historical False-group loss is not avoidable loss; BFalse newconfirmed subset and industrywide migration coupling differ from all fills. No new Q/migration-domain scan or candidate account. A remains a separate recovery-only hypothesis, not rescued by B.'}
 (I.HERE/'PVR_B_EXACT_FALSIFICATION_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps({k:v for k,v in out.items()if k!='results'},indent=2));print(json.dumps({k:{kk:vv for kk,vv in v.items()if kk not in ['full_by_B','original_fixed_tails']}for k,v in summary.items()},indent=2))
if __name__=='__main__':main()
