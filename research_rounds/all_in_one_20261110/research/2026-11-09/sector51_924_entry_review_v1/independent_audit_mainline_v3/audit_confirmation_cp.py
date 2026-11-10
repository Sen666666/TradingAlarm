"""Independent information/CP confirmation and donor chronology audit. No strategy rerun."""
from pathlib import Path
import sys,json,copy
from decimal import Decimal as D
from collections import defaultdict,Counter
import pandas as pd
O=Path(__file__).resolve().parent;P=O.parent;run=Path(sys.argv[1]);read=lambda p:json.loads(Path(p).read_text())
# Reuse only our independent data/fee definitions. The audit trade loop is not executed.
src=(O/'reconcile_actual_ledger.py').read_text().split('for row in ledger:')[0];exec(compile(src,str(O/'reconcile_actual_ledger.py'),'exec'),globals())
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');K=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet');RT=pd.read_parquet(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/RIGHT3.parquet');pv=pd.read_parquet(R/'pvr_persistence_breadth_v1/STOCK_DAILY.parquet',columns=['sid','day','state']);pv=pv.pivot(index='day',columns='sid',values='state').reindex(index=K.index,columns=K.columns);known=K&pv.ge(0);right=known&RT;cal=K.index
facts={s:pd.read_parquet(manifest[s]['refs']['facts']) for s in raw};sourcecp={s:pd.read_parquet(manifest[s]['refs']['CP1']) for s in raw};evidence=pd.read_csv((O/(run.name+'_INDEPENDENT_M_EVIDENCE.csv') if (O/(run.name+'_INDEPENDENT_M_EVIDENCE.csv')).exists() else P/'independent_audit_mainline_v2/checkpoint_20240930_INDEPENDENT_M_EVIDENCE.csv')).set_index(['day','sector51']);confirm=read(run/'INFORMATION_CONFIRMATIONS.json');transfers=read(run/'TRANSFERS.json');cplog=read(run/'CP_EVENTS.json');proofs={x['proof_id']:x for x in confirm if x['phase']=='CLOSE'};hday=byday(holdings);tday=byday(transfers);cday=byday(confirm);CPday=byday(cplog)
def truth(x):return pd.notna(x) and x in (True,1)
def false(x):return pd.notna(x) and x in (False,0)
def stock(s,t):return int(right.at[pd.Timestamp(t),s]) if known.at[pd.Timestamp(t),s] else -1
def lin(z):return tuple(str(z[c]) for c in ['source_kind','source_path','segment_id'])
def nextday(t):return str(cal[cal.get_loc(pd.Timestamp(t))+1].date())
def applytr(st,flows,tr):
 rid=tr['round_id'];flows[rid]+=D(tr['cash_delta'])
 if tr['side'].startswith('BUY'):st[tr['lot_id']]=dict(sid=tr['sid'],rid=rid,q=tr['qty'],kind=tr['side'][4:],bought=tr['day'])
 else:
  qq=tr.get('lot_quantities') or {lid:st[lid]['q'] for lid in tr['lots']}
  for lid,q in qq.items():st[lid]['q']-=q
  st0={k:v for k,v in st.items() if v['q']};st.clear();st.update(st0)
def quantity(st,rid):return sum(x['q'] for x in st.values() if x['rid']==rid)
def net(st,flows,divs,rid,s,d,field):
 q=quantity(st,rid);p=price(s,d,field)*D('.9995');return flows[rid]+divs[rid]+q*p-fee(s,d,q,p,'sell')
def cpok(rid,cid,s,t,field,state,invalid):
 if state.get(rid)!=cid or cid in invalid:return False
 cp=cpcreated[cid];z=raw[s].loc[pd.Timestamp(t)];return lin(z)==lin(raw[s].loc[pd.Timestamp(cp['day'])]) and price(s,t,field)*price(s,t,'adjustment_factor')>D(cp['candidate'])
st={};flows=defaultdict(lambda:D(0));divs=defaultdict(lambda:D(0));hist=defaultdict(bool);adds=Counter();latest={};invalid=set();pending={};previous_h={};states_by_close={};actual_open={};actual_close={};unfunded=[]
for d in sorted(ld):
 today=od.get(d,[]);mandatory=[x for x in today if x['side'].startswith('SELL') and not x.get('transfer_rank')]
 for tr in mandatory:applytr(st,flows,tr)
 for x in ed.get(d,[]):
  if x['event']=='ACCRUE_NET80':divs[x['round_id']]+=D(x['receivable_delta'])
 for x in CPday.get(d,[]):
  if x['phase']=='OPEN' and x['event']=='INVALIDATED':equal('OPEN_CP_invalidation_current',latest.get(x['round_id']),x['cp_id'],x['cp_id']);invalid.add(x['cp_id'])
 openc={x['proof_id']:x for x in cday.get(d,[]) if x['phase']=='OPEN'}
 equal('next_OPEN_confirms_every_prior_proof',set(openc),set(pending),d)
 for pid,proof in pending.items():
  x=openc.get(pid)
  if x is None:continue
  rid=proof['round_id'];s=proof['sid'];cid=proof['cp_id'];q=quantity(st,rid);left=[h for lid,h in previous_h.items() if lid in st and h['round_id']==rid];reason='PASS';ifloor=next((D(h['protection_signal']) for h in left if h['kind']=='SEED'),D(0));n=net(st,flows,divs,rid,s,d,'raw_open')
  if not q or any(h['locked_exit'] for h in left):reason='EXIT_OR_NO_POSITION'
  elif not cpok(rid,cid,s,d,'raw_open',latest,invalid):reason='CP_INVALID_OR_REPLACED'
  elif price(s,d,'raw_open')*price(s,d,'adjustment_factor')<=max(ifloor,D(cpcreated[cid]['candidate'])):reason='OPEN_BELOW_PROTECTION'
  elif n<=0:reason='OPEN_NET_NOT_POSITIVE'
  equal('OPEN_confirmation_exact_reason',x['reason'],reason,[d,rid]);equal('OPEN_same_proof_and_CP',x['cp_id'],cid,[d,rid]);equal('OPEN_next_common_date',d,nextday(proof['day']),rid)
  if reason=='PASS':hist[rid]=True
  equal('confirmed_history_monotone_and_no_resurrection',x['confirmed_history'],hist[rid],[d,rid]);equal('confirmation_independent_actual_ADD_count',x['actual_add_count'],adds[rid],[d,rid]);equal('confirmation_does_not_require_funding',x['capacity_or_funding_required'],False,[d,rid])
  if reason=='PASS' and not any(t['round_id']==rid and t['side']=='BUY_ADD' for t in today):unfunded.append(dict(day=d,round_id=rid,net=str(n),had_prior_ADD=adds[rid]>0))
 actual_open[d]=dict(st=copy.deepcopy(st),flows=dict(flows),div=dict(divs),hist=dict(hist),adds=dict(adds),latest=dict(latest),invalid=set(invalid))
 for tr in today:
  if tr in mandatory:continue
  if tr['side']=='BUY_ADD':equal('ADD_after_history_confirmation',hist[tr['round_id']],True,tr['order_seq']);adds[tr['round_id']]+=1
  applytr(st,flows,tr)
 for x in CPday.get(d,[]):
  rid=x['round_id'];cid=x['cp_id'];event=x['event']
  if x['phase']=='OPEN' and event=='INVALIDATED':continue
  if event=='CONSUMED_ON_FILL':
   equal('consume_exactly_actual_ADD',sum(t['side']=='BUY_ADD' and t['cp_id']==cid for t in today),1,cid);equal('consume_latest_CP',latest.get(rid),cid,cid);latest[rid]=None
  elif event=='INVALIDATED':equal('CLOSE_CP_invalidation_current',latest.get(rid),cid,cid);invalid.add(cid)
  elif event=='SUPERSEDED':equal('CP_supersedes_current',latest.get(rid),cid,cid);latest[rid]=None
  elif event=='CREATED_AFTER_SEED':
   s=x['sid'];ts=pd.Timestamp(x['day']);equal('CP_source_receipt',truth(sourcecp[s].at[ts,'receipt']),True,cid);equal('CP_source_floor',D(x['candidate']),D(str(sourcecp[s].at[ts,'candidate'])),cid);equal('CP_post_actual_seed',x['day']>=seed[rid]['day'],True,cid);latest[rid]=cid
 hs={h['lot_id']:h for h in hday.get(d,[])};rr=defaultdict(list)
 for h in hs.values():rr[h['round_id']].append(h)
 closec={x['round_id']:x for x in cday.get(d,[]) if x['phase']=='CLOSE'};expected=set()
 for rid,ll in rr.items():
  s=ll[0]['sid'];f=facts[s].loc[pd.Timestamp(d)];c=sourcecp[s].loc[pd.Timestamp(d)];ev=evidence.loc[(d,mapping[s])];cid=latest.get(rid);n=net(st,flows,divs,rid,s,d,'raw_close');legal=not any(h['locked_exit'] for h in ll) and truth(f.get('i_target')) and pd.notna(f.get('i_floor')) and f.i_floor>0 and ev.state!=-1 and ev.M==1 and (truth(c.get('receipt')) or false(c.get('receipt'))) and cid is not None and cpok(rid,cid,s,d,'raw_close',latest,invalid) and n>0
  if legal:
   expected.add(rid);x=closec.get(rid);equal('every_CLOSE_nonfunding_pass_gets_proof',x is not None,True,[d,rid])
   if x:
    equal('CLOSE_CP_matches_current',x['cp_id'],cid,[d,rid]);equal('CLOSE_net_independent',D(x['close_net']),n,[d,rid]);equal('CLOSE_history_not_provisionally_promoted',x['confirmed_history'],hist[rid],[d,rid]);equal('CLOSE_actual_ADD_count',x['actual_add_count'],adds[rid],[d,rid])
  else:equal('no_proof_without_all_nonfunding_conditions',rid in closec,False,[d,rid])
 equal('CLOSE_proof_population_exact',set(closec),expected,d);pending={x['proof_id']:x for x in closec.values()};actual_close[d]=dict(st=copy.deepcopy(st),flows=dict(flows),div=dict(divs),hist=dict(hist),adds=dict(adds),latest=dict(latest),invalid=set(invalid));states_by_close[d]=dict(proofs=set(closec),holdings=hs);previous_h=hs

report=dict(result='PASS' if not errors else 'FAIL',basis='Independent CP receipts, real lots, cashflow, current raw prices, fees, confirmation proof and fill-only CP consumption. Unchanged Q/S/F evidence uses the independently source-reconstructed 19-day table. Does not certify new T/queue/donor semantics.',days=len(ld),checks=dict(checks),error_count=len(errors),errors=errors,confirmed_without_same_open_ADD=unfunded)
(O/(run.name+'_CONFIRMATION_CP_AUDIT.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(result=report['result'],checks=sum(checks.values()),errors=errors[:20]),ensure_ascii=False))
