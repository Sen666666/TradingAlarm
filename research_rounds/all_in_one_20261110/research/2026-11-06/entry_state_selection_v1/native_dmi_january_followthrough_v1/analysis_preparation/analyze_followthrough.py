"""Sealed-output-only analysis. Never constructs Account/Runner or executes strategy."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import argparse,ast,gzip,json,hashlib,sys,time
import numpy as np,pandas as pd
sys.dont_write_bytecode=True
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
O=R/'native_dmi_january_followthrough_v1';MONTH=R/'native_dmi_two_month_continuous_v1';BASE=R/'act_only_ablation_continuous_v1/run'
OLD=R/'act_only_ablation_continuous_v1/analysis_preparation/analyze_act_only_v2.py'
Z=D(0);EPS=D('1e-8');END='2026-05-15'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False,default=str,allow_nan=False))
def stream(p):
 with gzip.open(p,'rt') as f:
  for l in f:yield json.loads(l)
def gz(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def csv(p,rows):
 df=pd.DataFrame(rows)
 for c in df:
  if df[c].map(lambda v:isinstance(v,(dict,list,tuple))).any():df[c]=df[c].map(lambda v:json.dumps(v,default=str,ensure_ascii=False) if isinstance(v,(dict,list,tuple)) else v)
 df.to_csv(p,index=False)
def decsum(v):return sum((D(str(x)) for x in v),Z)
exec(compile(ast.Module(body=[n for n in ast.parse(OLD.read_text()).body if isinstance(n,ast.FunctionDef) and n.name in ('stats','nav_stats','replay_account')],type_ignores=[]),str(OLD)+':pure_ledger_analysis','exec'),globals())
def stat(rows,layer=False):
 s=stats(rows);tail=[r for r in rows if r['pnl']/r['buy_cost']>=D('.30')]
 s.update(unit='INDEPENDENT_FIRST_BUY_LAYER' if layer else 'COMPLETE_0_TO_0_ROUND',fee_net_30pct_tail_count=len(tail),fee_net_30pct_tail_pnl=sum((r['pnl'] for r in tail),Z))
 if layer:s['return_denominator']='Only first actual BUY layer gross plus its BUY fee; later ADD excluded'
 return s
def sealed(path,manifest_name):
 m=read(path/manifest_name)
 for n,h in m.items():
  p=Path(n) if Path(n).is_absolute() else path/n
  assert sha(p)==h,('sealed output changed',str(p))
 return sha(path/manifest_name)
def main(out, branches):
 started=time.monotonic();assert not out.exists(),('analysis overwrite forbidden',out)
 # Read final completed accounts only. A premature call fails before creating output.
 sources={str(OLD):sha(OLD),str(Path(__file__)):sha(__file__)}
 for label in [y+'Jan_DMI' for y in branches]:
  p=O/label;done=read(p/'DONE.json');assert done.get('completed') is True,(label,'not completed')
  sources[str(p/'OUTPUT_SHA256.json')]=sealed(p,'OUTPUT_SHA256.json')
 assert read(BASE/'DONE.json')['completed'] is True
 sources[str(BASE/'OUTPUT_HASHES.json')]=sealed(BASE,'OUTPUT_HASHES.json')
 for label in [y+'Jan_DMI' for y in branches]:
  sources[str(MONTH/label/'OUTPUT_SHA256.json')]=sealed(MONTH/label,'OUTPUT_SHA256.json')
 out.mkdir(parents=True)
 baseline_daily={r['at'][:10]:r for r in stream(BASE/'pair/daily.jsonl.gz') if r['account']=='PVR'}
 assert len(baseline_daily)==1054 and max(baseline_daily)==END
 sys.path.insert(0,str(R/'account_comparison_continuous_v1/inputs'));import continuous_inputs as C
 ids=read(C.U/'FREEZE.json')['stocks'];assert len(ids)==1709
 bundle,market,_=C.J.M.context(END,ids=ids)
 sectors={l.security_id:l.sector_id for l in bundle.lines};techsectors={sectors[s] for s in ['300666.SZ','301611.SZ']};techsids={s for s in ids if sectors[s] in techsectors}
 marks={};markmeta={}
 def fillmarks(d,r):
  at=C.J.M.N.iso(r['at']);missing=set(r['positions'])-set(marks.setdefault(d,{}))
  if missing:
   mm=market.marks(at,missing)
   marks[d].update({s:m.cny_price(at) for s,m in mm.items()});markmeta.setdefault(d,{}).update(mm)
  inv=sum((D(q)*marks[d][s] for s,q in r['positions'].items()),Z)
  assert abs(inv-D(r['inventory']))<EPS,('inventory mark gap',d,inv,r['inventory'])
  nv=sum((D(r[k]) for k in ['available','order_reserved','settlement_locked','sale_receivable','dividend_receivable','inventory']),Z)-D(r['payable'])
  assert abs(nv-D(r['nav']))<EPS,('NAV identity gap',d)
 allrounds=[];alllayers=[];risks=[];annual=[];cohortrows=[];initialrows=[];eventchains=[];valuations=[];trades=[];cases=[];caseparticipation=[];periodrows=[];funding=[];summary={};cohorts={};lineage={};lcontrib=[];candidatecounts=[];casetrades=[]
 labels=[('PVR_ORIGINAL',BASE,None)]+[('DMI_FROM_'+y+'JAN',O/(y+'Jan_DMI'),y) for y in branches]
 for label,path,birth in labels:
  if label=='PVR_ORIGINAL':ds=baseline_daily
  else:
   native={r['at'][:10]:r for r in stream(path/'pair/daily.jsonl.gz') if r['account']=='PVR'}
   assert max(native)==END and min(native).startswith(birth+'-01'),(label,'expected January plus suffix daily',min(native),max(native))
   monthly={r['at'][:10]:r for r in stream(MONTH/(birth+'Jan_DMI')/'pair/daily.jsonl.gz')}
   assert all(native[d]==r for d,r in monthly.items()),(label,'January prefix daily changed')
   ds=dict({d:r for d,r in baseline_daily.items() if d<'2026-01-01'},**native) if birth=='2026' else native
  days=sorted(ds);assert days==sorted(baseline_daily),(label,'full true ancestry dates differ')
  for d in days:fillmarks(d,ds[d])
  a=gz(path/'pair/PVR.json.gz')
  if birth:
   ma=gz(MONTH/(birth+'Jan_DMI')/'pair/PVR.json.gz');assert a['trades'][:len(ma['trades'])]==ma['trades'],(label,'January actual trade prefix changed');del ma
  rr,ll,bridge=replay_account(a,label,ds,days,marks)
  for row in rr:row['identity']=row['sid']+'|'+row['opened']
  source_account_name=a.get('name','PVR')
  closed=[r for r in rr if r['closed']];op=[r for r in rr if not r['closed']]
  allrounds.extend(rr);alllayers.extend(ll)
  trades.extend(dict(account=label,trade_index=i,**t) for i,t in enumerate(a['trades']))
  ar=[];prev=D(1200000)
  for y in sorted({d[:4] for d in days}):
   yy=[d for d in days if d.startswith(y)];ts=[t for t in a['trades'] if t['at'].startswith(y)];r0=ds[yy[-1]]
   row=dict(account=label,year=y,partial_year=y=='2026',**nav_stats([ds[d] for d in yy],prev),fees=decsum(t['fees_cny'] for t in ts),buy_fills=sum(t['side']=='buy' for t in ts),sell_fills=sum(t['side']=='sell' for t in ts),buy_cost=decsum(D(t['gross_cny'])+D(t['fees_cny']) for t in ts if t['side']=='buy'),final_available=r0['available'],final_inventory=r0['inventory'],final_receivables=D(r0['dividend_receivable'])+D(r0['sale_receivable']),final_stock_count=len(r0['positions']),mean_inventory_fraction=float(np.mean([float(D(ds[d]['inventory'])/D(ds[d]['nav'])) for d in yy])),mean_stock_count=float(np.mean([len(ds[d]['positions']) for d in yy])),rank_policy_scope='INHERITED_ORIGINAL_PVR' if birth=='2026' and y<'2026' else 'DMI_SAME_SECTOR_SAME_ROLE_FROZEN' if birth else 'ORIGINAL_PVR')
   annual.append(row);ar.append(row);prev=D(r0['nav'])
  risk=[]
  for d in days:
   r=ds[d];nav=D(r['nav']);risk.append(dict(account=label,day=d,nav=nav,available=r['available'],inventory=r['inventory'],dividend_receivable=r['dividend_receivable'],sale_receivable=r['sale_receivable'],inventory_fraction=float(D(r['inventory'])/nav),stock_count=len(r['positions']),live_layers=len(r['layers']),ACT_on=r['on'],max_stock_NAV_fraction=max((float(D(q)*marks[d][s]/nav) for s,q in r['positions'].items()),default=0),pending_intents=r['pending_intents']))
  risks.extend(risk)
  summary[label]=dict(**nav_stats([ds[d] for d in days],D(1200000)),**bridge,closed_rounds=stat(closed),independent_closed_initial_layers=stat([l for l in ll if l['initial_layer'] and l['closed']],True),open_rounds=len(op),open_round_marked_pnl=sum((r['pnl'] for r in op),Z),end_stocks=len(ds[END]['positions']),end_layers=len(ds[END]['layers']),mean_inventory_fraction=float(np.mean([r['inventory_fraction'] for r in risk])),max_stock_NAV_fraction=max(r['max_stock_NAV_fraction'] for r in risk),max_inventory_fraction=max(r['inventory_fraction'] for r in risk),internal_source_account_label=source_account_name,ancestry='Original PVR through 2025-12-31 then DMI_FROM_2026JAN; prior rows are exact inherited history, not 2022 DMI' if birth=='2026' else 'Own unbroken branch history',source_path=str(path))
  # Candidate denominator is actual ranking audit rows, not all feature grid cells.
  if birth:
   counts=Counter();candidatepaths=[path/'DMI_RANK_AUDIT.jsonl.gz'];seen_january=False
   for r in stream(candidatepaths[0]):
    seen_january|=r['day'].startswith(birth+'-01');known=r['d'] is not None
    if not known:assert r['rank']==r['original_PVR_rank'] and not r['mutable'],('UNKNOWN slot moved',label,r)
    counts[(r['day'][:7],'candidate_stock_days')]+=1;counts[(r['day'][:7],'known_stock_days' if known else 'UNKNOWN_fixed_slot_stock_days')]+=1
    counts[(r['day'][:7],'known_mutable_stock_days')]+=int(r['mutable']);counts[(r['day'][:7],'actual_moved_stock_days')]+=int(r['rank']!=r['original_PVR_rank'])
   if not seen_january:
    candidatepaths.append(MONTH/(birth+'Jan_DMI')/'DMI_RANK_AUDIT.jsonl.gz')
    for r in stream(candidatepaths[-1]):
     assert r['day'].startswith(birth+'-01');known=r['d'] is not None
     if not known:assert r['rank']==r['original_PVR_rank'] and not r['mutable']
     counts[(r['day'][:7],'candidate_stock_days')]+=1;counts[(r['day'][:7],'known_stock_days' if known else 'UNKNOWN_fixed_slot_stock_days')]+=1;counts[(r['day'][:7],'known_mutable_stock_days')]+=int(r['mutable']);counts[(r['day'][:7],'actual_moved_stock_days')]+=int(r['rank']!=r['original_PVR_rank'])
   metrics=['candidate_stock_days','known_stock_days','UNKNOWN_fixed_slot_stock_days','known_mutable_stock_days','actual_moved_stock_days']
   totals={m:sum(v for (mo,k),v in counts.items() if k==m) for m in metrics};assert totals['candidate_stock_days']==totals['known_stock_days']+totals['UNKNOWN_fixed_slot_stock_days']
   summary[label]['actual_DMI_candidate_counts']=dict(**totals,UNKNOWN_fraction=totals['UNKNOWN_fixed_slot_stock_days']/totals['candidate_stock_days'],scope='January plus continuation actual ranking candidate stock-days; one row can include multiple roles',sources=[str(p) for p in candidatepaths])
   candidatecounts.extend(dict(account=label,month=mo,**{m:counts[(mo,m)] for m in metrics}) for mo in sorted({mo for mo,k in counts}))
  # Fixed January cohorts and disjoint same-stock successor chains.
  for yr in ([birth] if birth else ['2022','2026']):
   mo=yr+'-01';cc=[r for r in rr if r['opened'].startswith(mo)];cids={r['round_id'] for r in cc};sids={r['sid'] for r in cc};init=[l for l in ll if l['initial_layer'] and l['round_id'] in cids];succ=[r for r in rr if r['sid'] in sids and r['opened'][:10]>mo+'-31'];cl=[r for r in cc if r['closed']];il=[l for l in init if l['closed']]
   assert len(init)==len(cc)
   key=label+'_'+yr;cohorts[key]=dict(account=label,January=yr,cohort_rounds=len(cc),unique_stocks=len(sids),within_January_repeated_rounds=len(cc)-len(sids),complete_rounds=stat(cl),January_closed_rounds=stat([r for r in cl if r['closed'].startswith(mo)]),post_January_closed_rounds=stat([r for r in cl if not r['closed'].startswith(mo)]),open_rounds=len(cc)-len(cl),open_marked_pnl=sum((r['pnl'] for r in cc if not r['closed']),Z),closed_first_BUY_layers=stat(il,True),open_first_BUY_layers=len(init)-len(il),first_layer_closed_round_still_open=sum(bool(l['closed']) and any(r['round_id']==l['round_id'] and not r['closed'] for r in cc) for l in init),post_January_reentry_rounds=len(succ),post_January_reentry_unique_stocks=len({r['sid'] for r in succ}),post_January_reentry_closed=stat([r for r in succ if r['closed']]),post_January_reentry_open=sum(not r['closed'] for r in succ),closed_bookkeeping_UNKNOWN=0,external_actual_tradability_and_dividend_payout='UNKNOWN, retained rather than excluded',last_cohort_close=max((r['closed'] for r in cl),default=None))
   cohortrows.extend(dict(cohort=yr,**r) for r in cc);initialrows.extend(dict(cohort=yr,**l) for l in init);lineage[(label,yr)]={(r['sid'],r['opened']):r for r in cc}
   for sid in sorted(sids):
    seq=sorted([r for r in cc+succ if r['sid']==sid],key=lambda r:r['opened'])
    eventchains.extend(dict(cohort=yr,sid_sequence=i+1,chain_role='JANUARY_COHORT' if r['round_id'] in cids else 'POST_JANUARY_REENTRY',**r) for i,r in enumerate(seq))
  # YTD and post-January contribution from inherited live layers, not lifetime closed-round PnL.
  for period,anchor in [('2026_YTD','2025-12-31'),('2026_POST_JANUARY','2026-01-30')]:
   init={l['id']:l for l in ds[anchor]['layers']};parts=[]
   for l in ll:
    if l['id'] in init:
     old=init[l['id']];p0=D(old['cash'])+D(old['dividend'])+D(old['qty'])*marks[anchor][old['sid']];delta=l['pnl']-p0;kind='INHERITED_LIVE_AT_ANCHOR'
    elif l['opened'][:10]>anchor:delta=l['pnl'];kind='NEW_AFTER_ANCHOR'
    else:continue
    row=dict(account=label,period=period,anchor=anchor,layer_id=l['id'],sid=l['sid'],opened=l['opened'],closed=l['closed'],group=kind,period_contribution=delta);lcontrib.append(row);parts.append(row)
   change=D(ds[END]['nav'])-D(ds[anchor]['nav']);assert abs(sum((r['period_contribution'] for r in parts),Z)-change)<EPS
   selected=[d for d in days if d>anchor];ts=[t for t in a['trades'] if t['at'][:10]>anchor]
   periodrows.append(dict(account=label,period=period,anchor=anchor,**nav_stats([ds[d] for d in selected],D(ds[anchor]['nav'])),NAV_change=change,inherited_live_layer_contribution=sum((r['period_contribution'] for r in parts if r['group']=='INHERITED_LIVE_AT_ANCHOR'),Z),new_layer_contribution=sum((r['period_contribution'] for r in parts if r['group']=='NEW_AFTER_ANCHOR'),Z),fees=decsum(t['fees_cny'] for t in ts),bridge_pass=True))
  # Every held security at May-15, and the required January-30 fallback comparison.
  for cutoff in ['2026-01-30',END]:
   row=ds[cutoff]
   for sid,q in sorted(row['positions'].items()):
    mk=markmeta[cutoff][sid];raw=market.raw[sid].loc[:cutoff];eligible=raw[raw.valid_price & raw.observed_bar];last=str(eligible.index[-1].date());stale=sum(last<d<=cutoff for d in days);assert mk.known_at.date().isoformat()==last
    valuations.append(dict(account=label,cutoff=cutoff,sid=sid,shares=q,mark=marks[cutoff][sid],inventory_value=D(q)*marks[cutoff][sid],last_valid_observed_bar=last,stale_common_sessions=stale,stale=stale>0,mark_known_at=str(mk.known_at),mark_source=mk.source_id,latest_raw_row=str(raw.index[-1].date()),missing_same_day_bar_cause='UNKNOWN' if stale else 'NOT_APPLICABLE',intervening_action_adjustment='derived_ex_reference' in mk.source_id))
  # Actual full-account positions, trades, and six-session early participation, no MFE labels.
  windows=[('RALLY_2024','2024-09-23','2024-10-15',None),('TECH_2026','2026-01-01',END,techsids)]
  for case,lo,hi,scope in windows:
   wd=[d for d in days if lo<=d<=hi];observed=set().union(*(set(ds[d]['positions']) for d in wd));observed|={t['security_id'] for t in a['trades'] if lo<=t['at'][:10]<=hi};observed=observed if scope is None else observed & scope
   for d in wd:
    r=ds[d]
    for sid in sorted(observed):
     q=r['positions'].get(sid,0);cases.append(dict(account=label,case=case,day=d,sid=sid,shares=q,position_value=D(q)*marks[d].get(sid,Z),NAV=r['nav'],NAV_fraction=float(D(q)*marks[d].get(sid,Z)/D(r['nav'])),ACT_on=r['on']))
   initialids={r['initial_layer'] for r in rr}
   casetrades.extend(dict(account=label,case=case,actual_event_class=('NEW_0_TO_0_ROUND_FIRST_BUY' if t['layer'] in initialids else 'ADD' if t.get('kind')=='add' else 'OTHER_BUY_WHILE_HELD') if t['side']=='buy' else 'SELL',**t) for t in a['trades'] if t['security_id'] in observed and lo<=t['at'][:10]<=hi)
   if case=='RALLY_2024':
    early=[d for d in days if d>='2024-09-24'][:6];assert early[-1]=='2024-10-08'
    for sid in sorted(observed):
     buys=[t for t in a['trades'] if t['security_id']==sid and t['side']=='buy' and early[0]<=t['at'][:10]<=early[-1]];flags=[ds[d]['positions'].get(sid,0)>0 for d in early]
     caseparticipation.append(dict(account=label,sid=sid,scope='ALL_ACCOUNT_OBSERVED_STOCKS_20240923_1015',held_previous_close=ds['2024-09-23']['positions'].get(sid,0),first_held_day=next((d for d,f in zip(early,flags) if f),None),participated=any(flags),early_held_days=sum(flags),early_BUY_fills=len(buys),early_NEW_rounds=sum(t['layer'] in initialids for t in buys),early_ADD_fills=sum(t.get('kind')=='add' and t['layer'] not in initialids for t in buys),early_native_kind_ADD_fills=sum(t.get('kind')=='add' for t in buys),early_new_round_native_kind_ADD=sum(t.get('kind')=='add' and t['layer'] in initialids for t in buys),early_OTHER_buy_while_held=sum(t['layer'] not in initialids and t.get('kind')!='add' for t in buys),first_early_BUY=min((t['at'] for t in buys),default=None),early_BUY_cost=decsum(D(t['gross_cny'])+D(t['fees_cny']) for t in buys),early_mean_NAV_fraction=float(np.mean([float(D(ds[d]['positions'].get(sid,0))*marks[d].get(sid,Z)/D(ds[d]['nav'])) for d in early]))))
  if (path/'pair/funding.jsonl.gz').exists():
   ff=Counter((r['at'][:4],r.get('role'),r.get('result')) for r in stream(path/'pair/funding.jsonl.gz') if r.get('account','PVR')=='PVR');funding.extend(dict(account=label,year=k[0],role=k[1],result=k[2],rows=n,scope='NATIVE_OUTPUT_WINDOW_ONLY' if birth else 'FULL_ORIGINAL_ACCOUNT') for k,n in ff.items())
  print('ACCOUNT_ANALYZED',label,json.dumps(dict(end_nav=summary[label]['end_nav'],cohorts={k:v for k,v in cohorts.items() if v['account']==label}),default=str),flush=True)
  del a
 # Exact sid+opened January identity comparison; unmatched identities stay unmatched.
 compare=[]
 for year in branches:
  label='DMI_FROM_'+year+'JAN';p=lineage[('PVR_ORIGINAL',year)];d=lineage[(label,year)]
  for key in sorted(set(p)|set(d)):
   row=dict(cohort=year,DMI_account=label,sid=key[0],opened=key[1],presence='BOTH' if key in p and key in d else 'DMI_ONLY' if key in d else 'PVR_ONLY')
   for tag,m in [('PVR',p),('DMI',d)]:
    r=m.get(key);row[tag+'_state']='ABSENT' if r is None else 'CLOSED' if r['closed'] else 'RIGHT_CENSORED';row[tag+'_pnl']=r['pnl'] if r else None;row[tag+'_return']=r['return_on_all_buy_cost'] if r else None;row[tag+'_closed_winner']=bool(r and r['closed'] and r['pnl']>0);row[tag+'_complete_tail30']=bool(r and r['closed'] and r['pnl']/r['buy_cost']>=D('.30'))
   compare.append(row)
 outputs={'ALL_ROUNDS':allrounds,'ALL_LAYERS':alllayers,'ANNUAL_NAV_FEES':annual,'DAILY_EQUITY_RISK':risks,'JANUARY_COHORT_ROUNDS':cohortrows,'JANUARY_FIRST_BUY_LAYERS':initialrows,'JANUARY_STOCK_EVENT_CHAINS':eventchains,'JANUARY_IDENTITY_COMPARISON':compare,'JANUARY_COMPLETE_FEE_NET_30PCT_TAILS':[r for r in cohortrows if r['closed'] and r['pnl']/r['buy_cost']>=D('.30')],'FINAL_AND_JANUARY_VALUATION':valuations,'ALL_ACTUAL_TRADES':trades,'ACTUAL_CASE_DAILY_POSITIONS':cases,'2024_0924_ACTUAL_EARLY_PARTICIPATION':caseparticipation,'2026_PERIOD_CONTRIBUTIONS':periodrows,'2026_LAYER_PERIOD_CONTRIBUTIONS':lcontrib,'NATIVE_FUNDING_COUNTS':funding,'DMI_ACTUAL_CANDIDATE_COUNTS':candidatecounts,'CASE_ACTUAL_TRADES':casetrades,'TECH_SECTOR_ROUNDS':[r for r in allrounds if r['sid'] in techsids and ((r['closed'] or END)>='2026-01-01')],'JIANGFENG_KEMA_ROUNDS':[r for r in allrounds if r['sid'] in ['300666.SZ','301611.SZ']]}
 for n,rows in outputs.items():csv(out/(n+'.csv'),rows)
 stale_summary={label:{cut:dict(held=len(z:=[r for r in valuations if r['account']==label and r['cutoff']==cut]),stale_count=len(s:=[r for r in z if r['stale']]),stale_value=sum((r['inventory_value'] for r in s),Z),max_stale_sessions=max((r['stale_common_sessions'] for r in z),default=0)) for cut in ['2026-01-30',END]} for label,_,_ in labels}
 result=dict(status='COMPLETED_SEALED_OUTPUT_ONLY_ANALYSIS',economic_runs=0,analyzed_DMI_branches=branches,as_of=END,full_accounts=summary,January_cohorts=cohorts,valuation=stale_summary,sources=sources,fee_net_tail_definition='Complete 0-to-0 round PnL including booked dividends divided by every BUY gross+fee, >=30%; no MFE and no forced terminal sale',unknown_semantics='Original bookkeeping only; no new UNKNOWN state latch. Stale inventory and external tradability/payout unknown disclosed separately, no arbitrary dropped closed samples.',tech_case_scope='Current frozen industry IDs shared with 300666.SZ or 301611.SZ; NON-PIT descriptive scope, not a trained technology filter',limitations=['Fixed future-known 1709 stocks and 90 industries, NON-PIT.','2022 and 2026 January cohorts have unequal time-to-May15 horizons.','2026 DMI inherits original PVR 2025 state, never the 2022 DMI state.','OPEN +/-5bp research proxy with frozen native constraints, not actual live fills.','Open marks are right-censored, not winners.','Later same-stock reentries are distinct rounds and never alter original January win rate.','Same sid+opened is an event identity comparison, not proof of isolated causality.','Book dividend receivables are not spendable cash and external historical payout evidence is UNKNOWN.'],seconds=time.monotonic()-started)
 save(out/'SUMMARY.json',result)
 for p,h in sources.items():assert sha(p)==h,('source changed during analysis',p)
 save(out/'OUTPUT_SHA256.json',{p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
 print('ANALYSIS_DONE',str(out),flush=True)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,default=O/'analysis');ap.add_argument('--branches',nargs='*',choices=['2022','2026'],default=['2022','2026']);args=ap.parse_args();main(args.out,args.branches)
