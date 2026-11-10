"""Original-path static resource screen. No new reservations or fills; each CP independent."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import json,hashlib,ast,sys
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;R=O.parent;B=R/'m3_ab_shared_probe_v1/indexed_execution_v1/cohort_2024_924'
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025')
S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):
 p=Path(p);S[str(p)]=sha(p);return json.loads(p.read_text())
def source(p,h=None):
 p=Path(p);S[str(p)]=sha(p)
 if h:assert S[str(p)]==h
 return p
sys.path[:0]=[str(M/'code'),str(R/'m3_ab_shared_probe_v1/shared_feasibility_v1')]
from market_rules import version_on,market_identity_on,RuleUnavailable
from sector_account import QuantityRule,FeeComponent,FeeSchedule
from limits_v3 import Exposure,Snapshot,ReserveBook
for p in [M/'code/market_rules.py',M/'code/sector_account.py',R/'m3_ab_shared_probe_v1/shared_feasibility_v1/limits_v3.py']:source(p)
src=source(R/'m3_stock_birth_during_sector_v1/relative_priority_v1/simulate.py');wanted={'finite','true','false','lineage','flags','fee','getmeta','size'}
nodes=[n for n in ast.parse(src.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in wanted];assert {n.name for n in nodes}==wanted
env=dict(D=D,np=np,pd=pd,RuleUnavailable=RuleUnavailable,QuantityRule=QuantityRule,FeeComponent=FeeComponent,FeeSchedule=FeeSchedule,version_on=version_on,market_identity_on=market_identity_on,rules=read(M/'inputs-v2/market-rules.json'),proxies=read(M/'inputs-v2/economic-protocol.json')['approved_proxy_ids'],meta={},SLIP=D('.0005'))
exec(compile(ast.Module(body=nodes,type_ignores=[]),'ORIGINAL_SIZE_ONLY','exec'),env)
mm={x['symbol']:x for x in read(U/'STOCK_MANIFEST.json')}
cache={}
def data(sid):
 if sid not in cache:
  m=mm[sid];rp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'))
  cache[sid]=(pd.read_parquet(source(rp,m['source_sha256'][rp])),pd.read_parquet(source(m['refs']['facts'],m['output_sha256'][m['refs']['facts']])),pd.read_parquet(source(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']])))
 return cache[sid]
j=read(B/'EXACT_TRADE_JOURNAL.json');audit=read(B/'AUDIT.json');arc=read(B/'ARCHIVES.json');dec=read(B/'DECISIONS.json')
ledger={x['day'][:10]:x for x in read(B/'DAY_LEDGER.json')}
snap={x['day'][:10]:x for x in audit if x['type']=='CLOSE_SNAPSHOT'}
panel=pd.read_parquet(source(R/'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/COMMON_K_COMPARISON.parquet'))
cal=pd.DatetimeIndex(sorted(panel.day.unique()))
cand=pd.read_csv(source(O/'NEW_SIGNAL_PERMISSIONS.csv'),parse_dates=['day','next_common_open','seed_signal_day'])
assert not cand.duplicated(['sid','day','cp_id']).any()
AB=Counter((x['day'][:10],x['sector']) for x in dec if x['decision']=='SELECTED_PENDING')
cand['original_AB_slots']=cand.apply(lambda x:AB[(str(x.day.date()),x.sector)],axis=1)
cand['remaining_sector_slots']=2-cand.original_AB_slots
assert cand.remaining_sector_slots.ge(0).all()
cand=cand.sort_values(['day','sector','PVR_score','sid'],ascending=[True,True,False,True])
# A diagnostic of compatibility with spare slots, not an implemented consumer.
cand['CP_rank_within_spare']=cand.groupby(['day','sector']).cumcount()+1
cand['spare_slot_compatible']=cand.CP_rank_within_spare.le(cand.remaining_sector_slots)
# Keep primary seed separately so the two zero-original-size cases cannot change primary C ranking.
cand['primary_CP_rank']=np.nan
cand.loc[cand.probe_primary,'primary_CP_rank']=cand[cand.probe_primary].groupby(['day','sector']).cumcount()+1
cand['primary_spare_slot_compatible']=cand.probe_primary&cand.primary_CP_rank.le(cand.remaining_sector_slots)
summ=[];holdrows=[];result=[]
for t,g in cand.groupby('day'):
 sd=str(t.date());opday=cal[cal.get_loc(t)+1];day=str(opday.date())
 if day>'2024-10-16':
  for x in g.to_dict('records'):result.append(x|dict(resource_status='NEXT_OPEN_OUTSIDE_FIXED_WINDOW'))
  continue
 q=defaultdict(lambda:dict(core=0,add=0))
 for a in j:
  ad=a['day'][:10]
  if ad>day or (ad==day and a['side'].startswith('buy')):continue
  z=q[a['round_id']]
  if a['side']=='buy_core':z['core']+=int(a['q'])
  elif a['side']=='buy_add':z['add']+=int(a['q'])
  elif a['side']=='sell_add':z['add']-=int(a['q'])
  else:assert sum(z.values())==int(a['q']);q[a['round_id']]=dict(core=0,add=0)
 promoted={a['round_id'] for a in audit if a['type']=='PROMOTED' and a['day'][:10]<=day}
 proofs={(a['round_id'],a['day'][:10]):a['proof'] for a in audit if a['type']=='PROMOTION_PROOF' and a.get('reason')=='eligible'}
 holdings=[]
 for rid,parts in q.items():
  if not sum(parts.values()):continue
  st=arc[rid];sid=st['sid'];raw,f,cp=data(sid);op=D(str(raw.at[opday,'raw_open']));fac=D(str(raw.at[opday,'adjustment_factor']))
  assert np.isclose(float(fac),raw.at[t,'adjustment_factor'],rtol=1e-11)
  fl=D(str(f.at[t,'i_floor']))/fac
  for kind,qty in parts.items():
   if not qty:continue
   floor=fl
   if kind=='add':
    fill=next(a for a in j if a['round_id']==rid and a['side']=='buy_add')
    ad=pd.Timestamp(fill['day']);proof=proofs[(rid,str(ad.date()))]
    floor=D(proof['effective_floor'])
    # Reconstruct only original announced protection ratchets on already-filled add layer.
    ff=f.loc[ad:t];cc=cp.loc[ad:t]
    for d in ff.index:
     floor=max(floor,D(str(ff.at[d,'i_floor']))/fac)
     if cc.at[d,'receipt']:floor=max(floor,D(str(cc.at[d,'candidate']))/fac)
   e=Exposure(sid,rid,st['sector'],'confirmed' if rid in promoted else 'probe',int(qty),op,floor)
   holdings.append(e);holdrows.append(dict(signal_day=sd,open_day=day,sid=sid,round_id=rid,kind=kind,q=qty,pool=e.pool,open=str(op),floor=str(floor)))
 batch=next(a for a in audit if a['type']=='ALL_RESERVATIONS_COMPLETE' and a['day'][:10]==day)
 cash=D(batch['cash_before_fills']);recv=D(ledger[day]['OPEN']['receivable']);nav=cash+recv+sum((x.capital for x in holdings),D(0));nd=D(snap[sd]['Nd'])
 book=ReserveBook(Snapshot(cash,recv,nav,nd,tuple(holdings),(),(),'ORIGINAL_PATH_PREBUY_ONLY'))
 for a in audit:
  if a['type']!='RESERVED' or a['day'][:10]!=day:continue
  rid=a['round_id'];st=arc[rid];sid=st['sid'];raw,f,cp=data(sid);fac=D(str(raw.at[opday,'adjustment_factor']));px=D(str(raw.at[opday,'raw_open']))*D('1.0005')
  floor=D(str(f.at[t,'i_floor']))/D(str(raw.at[t,'adjustment_factor'])) if a['kind']=='INIT' else D(proofs[(rid,day)]['effective_floor'])
  if a['kind']=='INIT':assert pd.Timestamp(st['signal_day'])==t
  fee=D(a['trials'][-1]['fee'])
  e=Exposure(sid,rid,st['sector'],'probe' if a['kind']=='INIT' else 'confirmed',int(a['shared_q']),px,floor,fee,'live')
  book.orders.append(e)
 assert book.reserved_cash==D(batch['reserved_cash'])
 assert book.unbooked_buy_fees==D(batch['unbooked_buy_fees'])
 originalbuys=[a for a in j if a['day'][:10]==day and a['side'].startswith('buy')]
 assert {a['round_id'] for a in originalbuys}=={e.round_id for e in book.orders}
 newcash=sum((D(a['q'])*D(a['exact_price'])+D(a['exact_whole_order_fee']) for a in originalbuys),D(0))
 newmark=sum((D(a['q'])*D(str(data(arc[a['round_id']]['sid'])[0].at[opday,'raw_open'])) for a in originalbuys),D(0))
 residual=nav-newcash+newmark-D(ledger[day]['OPEN']['NAV']);assert residual==0
 pc,pr=book.resources(pool='probe')
 summ.append(dict(signal_day=sd,open_day=day,original_cp_permissions=len(g),primary_permissions=int(g.probe_primary.sum()),original_prebuy_NAV=nav,original_planning_NAV=nd,
  original_reserved_cash=book.reserved_cash,original_buy_fees=book.unbooked_buy_fees,original_probe_capital_after_reservations=pc,original_probe_nominal_risk_after_reservations=pr,
  original_probe_headroom_after_reservations=(nav-book.unbooked_buy_fees)*D('.005')-pr,nav_bridge_residual=residual))
 for x in g.to_dict('records'):
  sid=x['sid'];raw,f,cp=data(sid);out=x|dict(open_day=day,original_probe_headroom=str(summ[-1]['original_probe_headroom_after_reservations']))
  if opday not in raw.index:
   out['resource_status']='MISSING_NEXT_OPEN_UNKNOWN';result.append(out);continue
  p=raw.loc[t];z=raw.loc[opday]
  if env['lineage'](z)!=env['lineage'](p) or not env['flags'](z) or not np.isclose(z.adjustment_factor,p.adjustment_factor,rtol=1e-11):
   out['resource_status']='SOURCE_FACTOR_OR_FLAGS_UNKNOWN_AT_OPEN';result.append(out);continue
  op=D(str(z.raw_open));floor=D(str(x['I_floor']))/D(str(p.adjustment_factor));px=op*D('1.0005')
  if op<=floor:out['resource_status']='NEXT_OPEN_BELOW_I_NOFILL';result.append(out);continue
  qr,fs,par=env['getmeta'](sid,opday);formula,bf,risk,_,_=env['size'](sid,opday,px,floor,nd*D('.02'),nd*D('.0025'),int(x['prior20_capacity']))
  originalq=qr.buy_floor(min(formula,int(x['close_q'])));out.update(conditional_open_formula_q=formula,before_shared_q=originalq,min_buy_qty=qr.buy_minimum,next_raw_open=float(op),I_floor_raw=float(floor))
  if originalq<qr.buy_minimum:out['resource_status']='ORIGINAL_MINIMUM_LOT_OR_ROUND_RISK_NOFILL';result.append(out);continue
  qmin=int(qr.buy_minimum);fee=env['fee'](qmin,px,fs,'buy',par);risk=max(D(0),D(qmin)*(px-floor*D('.9995'))+fee+env['fee'](qmin,floor*D('.9995'),fs,'sell',par))
  reasons=[]
  if D(qmin)*px+fee>nd*D('.02'):reasons.append('original_round_budget')
  if risk>nd*D('.0025'):reasons.append('original_round_fee_risk')
  e=Exposure(sid,'STATIC_CP_ONLY|'+x['cp_id'],x['sector'],'probe',qmin,px,floor,fee,'live')
  reasons+=book.reasons(e)
  out.update(resource_status='MINIMUM_POSSIBLY_FUNDABLE_ORIGINAL_PATH' if not reasons else 'MINIMUM_HARD_REJECT_ORIGINAL_PATH',minimum_reasons='|'.join(reasons),minimum_probe_risk=str(e.nominal_risk),minimum_fee=str(fee))
  # No reserve call: every question is independent against unchanged original book.
  result.append(out)
res=pd.DataFrame(result);res.to_csv(O/'ORIGINAL_PATH_RESOURCE_SCREEN.csv',index=False)
pd.DataFrame(summ).to_csv(O/'ORIGINAL_PATH_RESOURCE_SNAPSHOTS.csv',index=False);pd.DataFrame(holdrows).to_csv(O/'ORIGINAL_PATH_HOLDING_FLOORS.csv',index=False)
summary={'statuses':dict(res.resource_status.value_counts()),'primary_statuses':dict(res[res.probe_primary].resource_status.value_counts()),
'all_remaining_slot_compatible':int(res.spare_slot_compatible.sum()),'primary_remaining_slot_compatible':int(res.primary_spare_slot_compatible.sum()),
'primary_spare_and_minimum_pass':int((res.primary_spare_slot_compatible&res.resource_status.eq('MINIMUM_POSSIBLY_FUNDABLE_ORIGINAL_PATH')).sum()),
'primary_spare_and_minimum_pass_unique_stocks':res.loc[res.primary_spare_slot_compatible&res.resource_status.eq('MINIMUM_POSSIBLY_FUNDABLE_ORIGINAL_PATH'),'sid'].nunique(),
'original_nav_reconciliations':len(summ),'no_new_reservations':True,'no_new_fills':True,'independent_checks_not_cumulative':True}
(O/'RESOURCE_SUMMARY.json').write_text(json.dumps(summary,default=lambda x:int(x),ensure_ascii=False,indent=2))
assert all(sha(p)==h for p,h in S.items())
(O/'RESOURCE_SOURCE_SHA256.json').write_text(json.dumps(S,ensure_ascii=False,indent=2))
print(json.dumps(summary,default=lambda x:int(x),ensure_ascii=False,indent=2))
print(res.groupby(['day','resource_status']).size().to_string())
print(res[res.primary_spare_slot_compatible&res.resource_status.eq('MINIMUM_POSSIBLY_FUNDABLE_ORIGINAL_PATH')][['day','sid','name','PVR_score','primary_CP_rank','remaining_sector_slots','minimum_probe_risk']].to_string(index=False))
