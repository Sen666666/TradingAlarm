"""Four strictly trailing signal-CLOSE cross-sections. No new portfolio run."""
from pathlib import Path
from decimal import Decimal as D
import importlib.util,sys,json,hashlib
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;ROOT=O.parent;P=ROOT/'mainline_candidate_v2_pending_quote_pause/full_20241031_once'
spec=importlib.util.spec_from_file_location('sealed_m2',ROOT/'mainline_candidate_v2_pending_quote_pause/engine.py');m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
pd=m.pd;np=m.np;sha=m.sha;dec=m.dec;Z=D(0);read=lambda p:json.loads(Path(p).read_text());save=lambda p,x:Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
TARGETS=pd.to_datetime(['2024-09-20','2024-09-23','2024-09-26','2024-09-27']);data=m.Data('2024-09-27');cal=data.cal[(data.cal>=pd.Timestamp('2023-11-01'))&(data.cal<=TARGETS.max())];ids=data.ids
px=pd.DataFrame(np.nan,index=cal,columns=ids);known=pd.DataFrame(False,index=cal,columns=ids);changed=known.copy()
for s in ids:
 z=data.raw[s].reindex(cal);v=z[['raw_open','raw_high','raw_low','raw_close','raw_volume','adjustment_factor']].to_numpy(float);lin=z[['source_kind','source_path','segment_id']].astype('string');basic=z.observed_bar.eq(True)&z.price_eligible.eq(True)&z.volume_eligible.eq(True)&z.source_invalid.eq(False)&z.synthetic_event_bar.eq(False);p=z.raw_close*z.adjustment_factor
 ok=basic.to_numpy(bool)&np.isfinite(v).all(axis=1)&(v>0).all(axis=1)&lin.notna().all(axis=1).to_numpy(bool)&lin.ne('').all(axis=1).to_numpy(bool)&np.isclose(p.to_numpy(float),z.close.to_numpy(float),rtol=1e-10,atol=1e-10,equal_nan=False)
 px[s]=p.where(ok);known[s]=ok;changed[s]=lin.ne(lin.shift()).fillna(True).any(axis=1)
bknown=known.astype(int).rolling(21,min_periods=21).sum().eq(21)&changed.astype(int).rolling(20,min_periods=20).sum().eq(0);bvalue=px.gt(px.shift(1).rolling(20,min_periods=20).max())&bknown
cand=read(P/'CANDIDATES.json');tickets=read(P/'RETRY_TICKETS.json');attempts={a['id']:a for a in read(P/'ATTEMPTS.json')};held=read(P/'HOLDINGS.json');sector_rows={(r['day'],r['sector51']):r for r in read(P/'SECTOR_DAILY.json')};ledger={r['day']:r for r in read(P/'DAY_LEDGER.json')};cpdates={r['cp_id']:r['day'] for r in read(P/'CP_EVENTS.json') if r['event']=='CREATED_AFTER_SEED'};requests=[]
for dt in TARGETS:
 day=m.day(dt);nav=dec(ledger[day]['NAV'])
 for c in cand:
  if c['phase']!='CLOSE' or c['day']!=day:continue
  s=c['sid'];q=None;kind=None
  if c['event'] in ['A','B'] and c['decision']=='PASS':q=int(c['planned_q']);kind='NEW_SEED';origin_day=day;key=f'{s}|{day}|{c["event"]}';cp=None
  elif c['event']=='ADD_GATE' and c['decision']=='ADD_PLANNED':
   a=attempts[c['round_id']];qq=sum(h['qty'] for h in held if h['day']==day and h['round_id']==a['id']);budget=min(D('.02')*dec(a['nav0']),max(Z,D('.04')*dec(a['nav0'])-qq*dec(data.z(s,dt)['raw_close'])));q=data.size(s,dt,dec(data.z(s,dt)['raw_close'])*(1+m.v1.SLIP),budget,min(int(data.cap[s].loc[dt]),qq));assert q>0;kind='ADD';origin_day=cpdates[c['cp_id']];key=a['id'];cp=c['cp_id']
  if kind:
   price=dec(data.z(s,dt)['raw_close'])*(1+m.v1.SLIP);requests.append(dict(day=day,sid=s,sector51=data.sid_sector[s],kind=kind,origin_day=origin_day,identity=key,cp_id=cp,close_planned_qty=q,close_estimated_all_in=str(q*price+data.fee(s,dt,q,price,'buy')),source_decision=c['decision']))
 for t in tickets:
  if t['day']!=day or t['event']!='CLOSE_PLAN':continue
  s=t['sid'];q=data.getmeta(s,dt)[0].buy_minimum;price=dec(data.z(s,dt)['raw_close'])*(1+m.v1.SLIP);requests.append(dict(day=day,sid=s,sector51=data.sid_sector[s],kind='RETAINED_SEED',origin_day=t['original_signal_day'],identity=t['ticket_id'],cp_id=None,close_planned_qty=q,close_estimated_all_in=str(q*price+data.fee(s,dt,q,price,'buy')),source_decision=t['event']))
rows=[];stockaudit=[]
for dt in TARGETS:
 day=m.day(dt);prev=cal[cal.get_loc(dt)-1]
 for sec in data.sector_ids:
  ss=[s for s in ids if data.sid_sector[s]==sec];N=len(ss);k=bknown.loc[dt,ss]&bknown.loc[prev,ss];J=int(k.sum());now=bvalue.loc[dt,ss];before=bvalue.loc[prev,ss];ent=int((k&now&~before).sum());left=int((k&~now&before).sum());G=(ent-left)/N if J else np.nan;ev=data.main[sec].loc[dt];pe=data.main[sec].loc[prev];delta=ev.rs5-pe.rs5 if np.isfinite(ev.rs5) and np.isfinite(pe.rs5) else np.nan;rr=[r for r in requests if r['day']==day and r['sector51']==sec];account=sector_rows[(day,sec)];h=[r for r in held if r['day']==day and data.sid_sector[r['sid']]==sec];reason=[]
  if ev.M!=1:reason.append('M_NOT_TRUE')
  if not np.isfinite(ev.E):reason.append('E_UNKNOWN')
  elif ev.E<=0:reason.append('E_NOT_POSITIVE')
  if not np.isfinite(G):reason.append('G_UNKNOWN')
  elif G<=0:reason.append('G_NOT_POSITIVE')
  if not np.isfinite(delta):reason.append('DELTA_RS5_UNKNOWN')
  elif delta<=0:reason.append('DELTA_RS5_NOT_POSITIVE')
  if not rr:reason.append('NO_REAL_CLOSE_PLANNED_REQUEST')
  row=dict(day=day,sector51=sec,N=N,M=int(ev.M),S=int(ev.S),F=int(ev.F),M_streak=int(ev.M_streak),E=float(ev.E) if np.isfinite(ev.E) else None,rs5=float(ev.rs5) if np.isfinite(ev.rs5) else None,previous_rs5=float(pe.rs5) if np.isfinite(pe.rs5) else None,delta_rs5=float(delta) if np.isfinite(delta) else None,previous_common_day=m.day(prev),breakout_paired_K=J,breakout_paired_coverage=J/N,breakout_entered=ent,breakout_left=left,breakout_net=ent-left,G=float(G) if np.isfinite(G) else None,current_weight_pct=account['account_weight_pct'],market_value=account['market_value'],seed_core_value=str(sum((dec(r['market_value']) for r in h if r['kind']=='SEED'),Z)),ADD_layer_value=str(sum((dec(r['market_value']) for r in h if r['kind']=='ADD'),Z)),new_seed_requests=sum(r['kind']=='NEW_SEED' for r in rr),retained_seed_requests=sum(r['kind']=='RETAINED_SEED' for r in rr),ADD_requests=sum(r['kind']=='ADD' for r in rr),total_requests=len(rr),request_stocks=len({r['sid'] for r in rr}),planned_qty=sum(r['close_planned_qty'] for r in rr),close_planned_all_in=str(sum((dec(r['close_estimated_all_in']) for r in rr),Z)),frontier_eligible=not reason,eligibility_failures=reason,dominated_by=[],on_frontier=False)
  rows.append(row)
  for s in ss:stockaudit.append(dict(day=day,previous_common_day=m.day(prev),sector51=sec,sid=s,known_now=bool(bknown.at[dt,s]),known_previous=bool(bknown.at[prev,s]),paired_known=bool(k[s]),breakout_now=bool(now[s]) if bknown.at[dt,s] else None,breakout_previous=bool(before[s]) if bknown.at[prev,s] else None,entered=bool(k[s] and now[s] and not before[s]),left=bool(k[s] and before[s] and not now[s])))
for day in sorted({r['day'] for r in rows}):
 eligible=[r for r in rows if r['day']==day and r['frontier_eligible']]
 for r in eligible:
  r['dominated_by']=[s['sector51'] for s in eligible if s['G']>=r['G'] and s['delta_rs5']>=r['delta_rs5'] and (s['G']>r['G'] or s['delta_rs5']>r['delta_rs5'])]
  r['on_frontier']=not r['dominated_by']
for name,rr in [('ALL50_FOUR_CLOSE_STATIC',rows),('ALL_M_FOUR_CLOSE_STATIC',[r for r in rows if r['M']==1]),('REAL_CLOSE_REQUESTS',requests),('BREAKOUT_PAIR_STOCK_AUDIT',stockaudit)]:save(O/(name+'.json'),rr);pd.DataFrame(rr).to_csv(O/(name+'.csv'),index=False)
summary=[]
for dt in TARGETS:
 day=m.day(dt);rr=[r for r in rows if r['day']==day];summary.append(dict(day=day,all_M=sum(r['M']==1 for r in rr),eligible_candidates=sum(r['frontier_eligible'] for r in rr),frontier=[{k:r[k] for k in ['sector51','N','breakout_paired_K','G','delta_rs5','current_weight_pct','new_seed_requests','retained_seed_requests','ADD_requests']} for r in rr if r['on_frontier']],semiconductor=next(r for r in rr if r['sector51']=='半导体')))
save(O/'STATIC_SUMMARY.json',summary)
inputs={str(P/(n+'.json')):sha(P/(n+'.json')) for n in ['CANDIDATES','RETRY_TICKETS','ATTEMPTS','HOLDINGS','SECTOR_DAILY','DAY_LEDGER','CP_EVENTS']};inputs.update(data.hashes);inputs[str(O/'build_static_frontier.py')]=sha(O/'build_static_frontier.py');save(O/'STATIC_SOURCE_HASHES.json',inputs)
save(O/'STATIC_QA.json',dict(result='PASS_STATIC_NO_NEW_ACCOUNT',target_days=[m.day(d) for d in TARGETS],rows=len(rows),M_rows=sum(r['M']==1 for r in rows),stock_pair_rows=len(stockaudit),real_close_requests=len(requests),all50_each_day=all(sum(r['day']==m.day(d) for r in rows)==50 for d in TARGETS),price_data_cutoff='2024-09-27',G_definition='same member known at t and previous common day; (FALSE->TRUE minus TRUE->FALSE)/fixed N; J0 UNKNOWN',frontier_definition='M TRUE,E>0,G>0,delta_RS5>0,actual legal CLOSE planned demand; two-dimensional nondominated; no threshold change after outcomes',actual_M2_weights_only_not_new_policy_weights=True,next_OPEN_outcomes_not_used=True,no_new_portfolio_run=True))
print(json.dumps(summary,ensure_ascii=False,indent=2))
