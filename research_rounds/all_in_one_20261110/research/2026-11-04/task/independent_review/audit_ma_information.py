"""Independent entry-context prices, whole-book and phase wealth groups; no engine."""
from pathlib import Path
from decimal import Decimal as D,getcontext
from collections import defaultdict,Counter
import json,math,bisect
import pandas as pd
import audit_pvr_saved as I
getcontext().prec=60
O=I.TASK/'risk_constraints/ma63_information_diagnostic_v1';Z=D(0);FR={};SN={};CHECKS=0
IM={r['series']:r for r in I.read(I.W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
def close(a,b):assert abs(D(str(a))-D(str(b)))<D('.000001'),(a,b)
def frame(s):
 if s not in FR:
  m=IM[s]if s.startswith('URFI')else I.SM[s];p=m['refs']['CP1_input']if s.startswith('URFI')else m['refs']['facts'];assert I.sha(p)==m['output_sha256'][p]
  FR[s]=pd.read_parquet(p,columns=['close','segment_id']if s.startswith('URFI')else['close','segment_id','raw_close','factor'])
 return FR[s]
def snapshot(x):
 global CHECKS
 s=x['series'];day=x['decision_day'];k=(s,day)
 if k in SN:assert SN[k]==x;return
 f=frame(s);t=pd.Timestamp(day);assert f.index.is_unique and f.index.is_monotonic_increasing
 if t not in f.index:assert x['above']is None;SN[k]=x;return
 j=f.index.get_loc(t);w=f.iloc[max(0,j-62):j+1];segment=f.iloc[j].segment_id
 valid=len(w)==63 and pd.notna(segment)and all(w.segment_id==segment)and all(math.isfinite(v)and v>0 for v in w.close)
 assert (x['above']is not None)==valid
 if valid:
  price=float(f.iloc[j].close);ma=sum(float(v)for v in w.close)/63
  assert x['above']==(price>ma);close(x['close'],price);close(x['MA63'],ma)
  assert x['window_first']==str(w.index[0].date())and x['window_last']==x['source_max_used_day']==day and x['window_observations']==63
  if not s.startswith('URFI'):
   assert all(abs(a-b*c)<1e-8*max(1,abs(a))for a,b,c in zip(w.close,w.raw_close,w.factor))
  if j>=63:
   wr=f.iloc[j-63:j+1]
   if all(wr.segment_id==segment)and all(math.isfinite(v)and v>0 for v in wr.close):
    ret=price/float(wr.iloc[0].close)-1;close(ret,x['return63']);assert x['return63_sign']==('+'if ret>0 else'-'if ret<0 else'0')
 SN[k]=x;CHECKS+=1
def cls(x):return 'S'+('+'if x['stock']['above']else'-')+'I'+('+'if x['industry_state']['above']else'-')
def cross(x):return x['sid'],x['decision_at'],x['role'],x.get('receipt'),tuple(x.get('watch_epoch')or[])if x['role']=='core'else()
def main():
 source=I.read(O/'SOURCE_MANIFEST.json')
 for p,h in source['sources'].items():assert I.sha(p)==h,p
 results=I.read(O/'RESULTS.json');out={};root=I.TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024'
 configs=[('2022_2024',root/'no60/run-2024/pair',root/'original/run-2024/pair'),('strong',I.TASK/'pvr_pool_feasibility/runs/2025_26/pair',I.W/'pvr-slot1-native-readiness-20261101/runs/2025_26/pair')]
 for ref,newroot,oldroot in configs:
  ee=I.read(O/(ref+'_ENTRIES.json'));b=I.read(newroot/'B.json.gz');ds=I.rows(newroot/'daily.jsonl.gz');er={x['layer']:x for x in ee};raw={x['id']:x for x in b['layers']};buy={x['layer']:x for x in b['trades']if x['side']=='buy'};jr={x['layer']:x for x in b['journal']if x['kind']=='real_buy_fill'}
  assert len(ee)==len(buy)==len(jr)==len(raw);money=defaultdict(lambda:Z);groups=defaultdict(list)
  for x in ee:
   lid=x['layer'];j=jr[lid];t=buy[lid];assert x['budget_order']==j['budget_order']
   stamp=j['budget_order'].split('|')[1];assert pd.Timestamp(stamp)==pd.Timestamp(x['decision_at'])<pd.Timestamp(t['at'])
   assert any(d['at']==x['decision_at']and any(i['sid']==x['sid']and i['role']==x['role']and i.get('CP1_id')==x.get('receipt')for i in d['intents'])for d in b['decisions'])
   snapshot(x['stock']);snapshot(x['industry_state']);assert x['MA63_class']==cls(x)
   cost=D(t['gross_cny'])+D(t['fees_cny']);l=raw[lid];net=D(l['cash'])+D(l['dividend'])+(D(l['qty'])*I.price(l['sid'],ds[-1]['at'][:10])if l['qty']else Z)
   close(cost,x['cost']);close(net,x['net']);groups[x['MA63_class']].append(x)
  for g in results[ref]['groups']['by_MA']:
   ll=groups[g['labels']['MA63_class']];assert len(ll)==g['fills'];close(sum((D(x['cost'])for x in ll),Z),g['actual_buy_cash']);close(sum((D(x['net'])for x in ll),Z),g['net_lifetime'])
  close(sum((D(x['net'])for x in ee),Z),D(b['ending_NAV'])-1000000)
  # Independent quantity/cash/dividend event replay into FIXED AT ENTRY labels.
  events=[(t['at'],1,j,'trade',t)for j,t in enumerate(b['trades'])]
  for j,t in enumerate(b['audit']):
   if t['kind']=='split':events.append((t['at'],0,j,'split',t))
   if t['kind']=='dividend_accrual':events.append((t['receivable']['ex_at'],2,j,'div',t['receivable']))
  events.sort(key=lambda v:v[:3]);ei=0;state={};prior={};hist=[]
  for d in ds:
   day=d['at'][:10]
   while ei<len(events)and events[ei][0]<=d['at']:
    _,_,_,kind,t=events[ei];ei+=1
    if kind=='split':
     for l in state.values():
      if l['sid']==t['sid']:
       q=D(l['q'])*D(t['ratio']);assert q==int(q);l['q']=int(q)
    elif kind=='div':
     held=[l for l in state.values()if l['sid']==t['security_id']and l['q']];q=sum(l['q']for l in held);assert q>0
     for l in held:l['div']+=D(t['net_local'])*D(l['q'])/D(q)
    elif t['side']=='buy':state[t['layer']]={'sid':t['security_id'],'q':t['shares'],'cash':-D(t['gross_cny'])-D(t['fees_cny']),'div':Z}
    else:
     for p in t['parts']:state[p['layer']]['q']-=p['shares'];state[p['layer']]['cash']+=D(p['net_cash'])
   now=defaultdict(lambda:Z)
   for lid,l in state.items():now[er[lid]['MA63_class']]+=l['cash']+l['div']+(D(l['q'])*I.price(l['sid'],day)if l['q']else Z)
   close(sum(now.values(),Z),D(d['nav'])-1000000)
   for g in groups:hist.append((day,g,now[g]-prior.get(g,Z)))
   prior=now
  for lid,l in state.items():close(l['div'],raw[lid]['dividend']);assert l['q']==raw[lid]['qty'];close(l['cash'],raw[lid]['cash'])
  phase=I.read(O/(ref+'_ACTUAL_PHASE_WEALTH.json'))
  for r in phase:close(sum((v for day,g,v in hist if g==r['MA63_class']and r['lo']<=day<=r['hi']),Z),r['actual_phase_wealth'])
  # Complete original tail membership, then identity-only cross-arm matching.
  tails=I.read(O/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'));ob=I.read(oldroot/'B.json.gz');oj={x['layer']:x for x in ob['journal']if x['kind']=='real_buy_fill'};ot={t['layer']:t for t in ob['trades']if t['side']=='buy'}
  expected=[]
  for l in ob['layers']:
   t=ot[l['id']];cost=D(t['gross_cny'])+D(t['fees_cny']);net=D(l['cash'])+D(l['dividend'])+(D(l['qty'])*I.price(l['sid'],ds[-1]['at'][:10])if l['qty']else Z)
   if net/cost>=D('.3'):expected.append(l['id'])
  assert set(expected)=={r['original']['layer']for r in tails};bykey=defaultdict(list)
  for x in ee:bykey[cross(x)].append(x['layer'])
  for r in tails:
   x=r['original'];assert x['budget_order']==oj[x['layer']]['budget_order'];snapshot(r['original_stock']);snapshot(r['original_industry'])
   assert sorted(r['matched_No60_layers'])==sorted(bykey[cross(x)])and r['unmatched']==(not bykey[cross(x)])
  post=[x for x in ee if ref=='2022_2024'and x['opened'][:10]>'2024-10-08'];out[ref]={'passed':True,'all_actual_fills':len(ee),'daily_wealth_bridges':len(ds),'entry_label_phase_rows':len(phase),'original_fixed_tail_members':len(tails),'postOct8_new_fills':len(post),'postOct8_newfill_context':{g:{'fills':len([x for x in post if x['MA63_class']==g]),'net':str(sum((D(x['net'])for x in post if x['MA63_class']==g),Z))}for g in groups}if post else None}
 out.update(passed=True,source_SHA_checks=len(source['sources']),independent_price_snapshots=CHECKS,reviewer_account_events=0,reviewer_source_SHA256=I.sha(__file__),scope='Current-inclusiveMA63 observational diagnostic only; NOT proposed prior63industry B. Complete funded2265/1171 fills, independent direct63 sums/price-factor coordinate, decision-before-fill and originaldecision membership, all daily fixed-entry-context cash/div/rawinventory wealth and phase group bridges; full originaltail membership and crossarm SID/decision/role/CP1/coreepoch matching. Probe-R/ETFmacro and strictreal group detail source-reviewed, not independently rerun here. Entrycontext phasewealth is not dynamically reclassified daily context or deletion-PnL. No implication MAtrue guarantees trend/return or that fewer buys fixes strategy.')
 (I.HERE/'PVR_MA63_INFORMATION_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
