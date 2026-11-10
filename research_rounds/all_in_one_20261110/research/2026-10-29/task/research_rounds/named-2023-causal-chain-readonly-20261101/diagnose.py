"""Saved event/journal accounting only. Never constructs an account or calls a strategy."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,hashlib,time,collections,bisect,traceback,sys,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;W=O.parent;Y=W/'recovery-2023-readiness-20261101';G=W/'g1-current-state-readonly-20261101';R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');Z=D(0)
NAMED=['300308.SZ','300502.SZ'];META=json.loads((R/'a-share-selection-e0-20261024/inputs-v2/metadata.json').read_text());SM={r['symbol']:r for r in json.loads((W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json').read_text())};IM=json.loads((W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json').read_text())
def read(p):return json.loads(Path(p).read_text())
def stream(p):
 with gzip.open(p,'rt') as f:
  for s in f:yield json.loads(s)
def book(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def save(name,x):
 p=O/name;p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');t.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n');t.replace(p)
def n(x):return D(str(x))
def day(x):return str(x)[:10]
frames={};cpframes={};sourcehash={}
def fact(sid):
 if sid not in frames:
  p=SM[sid]['refs']['facts'];frames[sid]=pd.read_parquet(p);sourcehash[p]=hashlib.sha256(Path(p).read_bytes()).hexdigest()
 return frames[sid]
def atrow(sid,d):
 f=fact(sid);i=f.index.searchsorted(pd.Timestamp(d),side='right')-1;return None if i<0 else f.iloc[i]
def cp(sid):
 if sid not in cpframes:cpframes[sid]=pd.read_parquet(SM[sid]['refs']['CP1'])
 return cpframes[sid]
def core_structure(sid,d):
 f=fact(sid);pos=f.index.searchsorted(pd.Timestamp(d),side='right')-1
 if pos<0 or not bool(f.iloc[pos].i_target):return None
 seg=f.iloc[pos].segment_id;j=pos
 while j>0 and f.iloc[j-1].segment_id==seg and bool(f.iloc[j-1].i_target):j-=1
 return f'{sid}|{int(seg)}|{f.index[j].date()}'
def pricepath(sid,start,end):
 f=fact(sid);base=f.loc[:'2022-12-30'].close.iloc[-1];a=f.loc[start:end]
 if a.empty:return None
 return dict(first_close_day=str(a.index[0].date()),last_close_day=str(a.index[-1].date()),first_raw_close=float(a.raw_close.iloc[0]),last_raw_close=float(a.raw_close.iloc[-1]),first_adjusted_index=100*float(a.close.iloc[0]/base),last_adjusted_index=100*float(a.close.iloc[-1]/base),highest_adjusted_index=100*float(a.close.max()/base),highest_day=str(a.close.idxmax().date()),lowest_adjusted_index=100*float(a.close.min()/base),basis='same frozen adjusted close normalized to 2022-12-30=100; raw price separately; descriptive only')
def select_controls(ref,ls,caps):
 selected=[]
 for sec in ['URFI881129','URFI881130']:
  totals=collections.defaultdict(lambda:Z)
  for x in ls:
   if x['sector']==sec and not x['qty'] and x['sid'] not in NAMED:totals[x['sid']]+=n(x['net'])
  ordered=sorted(totals,key=lambda s:(-totals[s],s));sid=next((s for s in ordered if totals[s]>0),None)
  selected.append(dict(policy=ref,role='positive_control',selection='largest aggregate closed-layer net contribution in fixed sector, code tie-break; named stocks excluded',sector=sec,sid=sid,selected_closed_net=totals[sid] if sid else None))
 route={(x['sid'],day(x['decision_at']),x['CP1_id']):x for x in caps if x['role']=='mobile' and x['selected_quantity']>0}
 for pool in ['probe','expanded']:
  totals=collections.defaultdict(lambda:Z)
  for x in ls:
   if x['qty']:continue
   ok=x['pool_at_fill']=='probe' if pool=='probe' else x['pool_at_fill']=='confirmed' and x['role']=='mobile' and route.get((x['sid'],x['signal_day'],x['receipt']),{}).get('industry_level')==2
   if ok:totals[x['sid']]+=n(x['net'])
  ordered=sorted(totals,key=lambda s:(totals[s],s));sid=next((s for s in ordered if totals[s]<0),None)
  selected.append(dict(policy=ref,role='negative_control_'+pool,selection='worst aggregate closed contribution within actual fill pool/stage; code tie-break',sid=sid,selected_closed_net=totals[sid] if sid else None))
 return selected
def coarse(reason):
 if reason=='reserved':return 'reserved'
 if reason in ['ACT_paused','exit_pending','buy_pending','industry_invalidated','no_fresh_stock_CP1']:return reason
 if reason in ['minimum_unit_exceeds_risk_or_nominal_cap','open_minimum_exceeds_frozen_contract','no_nominal_gap','invalid_protection','open_at_or_below_protection']:return reason
 return reason
def main():
 begun=time.monotonic();states={r['series']:pd.read_parquet(r['refs']['state']).set_index('day').to_dict('index') for r in IM};calendar=read(R/'pvr-act-comparison-20261027/execution-rules-v2.json')['calendars']['A'];cal=sorted({x[:10] for x in calendar});calindex={d:i for i,d in enumerate(cal)}
 books={};daily={};caprows={};allselect=[]
 for ref in ['Bdiag','C1']:
  root=Y/'runs'/ref/'pair';books[ref]=book(root/'B.json.gz');daily[ref]={day(x['at']):x for x in stream(root/'daily.jsonl.gz')};caprows[ref]=[x for x in stream(root/'capacity-checks.jsonl.gz') if day(x['at']).startswith('2023')];ls=read(Y/'analysis'/ref/'LAYERS_2023.json');allselect+=select_controls(ref,ls,caprows[ref])
 save('CONTROL_SELECTION.json',allselect);subjects=set(NAMED)|{x['sid'] for x in allselect if x['sid']};outcomes=[];episodes=[];owner_targets=collections.defaultdict(set);all_ops=[]
 for ref in ['Bdiag','C1']:
  b=books[ref];ds=daily[ref];root=Y/'runs'/ref/'pair';ops={(x['sid'],x['day']):x for x in stream(root/'opportunities.jsonl.gz') if x['sid'] in subjects and x['day'].startswith('2023')};fund=collections.defaultdict(list)
  for x in stream(root/'funding.jsonl.gz'):
   if x['sid'] in subjects and day(x['at']).startswith('2023'):fund[(x['sid'],day(x['at']),x['role'])].append(x)
  capmap=collections.defaultdict(list)
  for seq,x in enumerate(caprows[ref]):x['trace_sequence']=seq;capmap[(x['sid'],day(x['decision_at']),x['role'])].append(x)
  intents={(i['sid'],day(d['at']),i['role']):i for d in b['decisions'] if day(d['at']).startswith('2023') for i in d['intents'] if i['sid'] in subjects}
  reserves=collections.defaultdict(list)
  for j in b['journal']:
   if j['kind']=='real_reserve' and day(j['at']).startswith('2023'):reserves[(j['sid'],j['budget_order'].split('|')[1][:10],j['role'])].append(j)
  tx=[t for t in b['trades'] if day(t['at']).startswith('2023')];allrows=[]
  for sid in sorted(subjects):
   f=fact(sid).loc['2023-01-01':'2023-12-29'];z=cp(sid).loc[f.index.intersection(cp(sid).index)];core_days=list(f.index[f.i_buy.eq(True)&f.i_target.eq(True)]);mobile_days=list(z.index[z.receipt.eq(True)])
   assert len({str(d.date()) for d in mobile_days})==len(mobile_days)
   for role,days in [('core',core_days),('mobile',mobile_days)]:
    for date in days:
     d=str(date.date());o=ops.get((sid,d));fr=fact(sid).loc[date];receipt=(o.get('CP1_id') if o else None) if role=='mobile' else None
     if role=='mobile':assert receipt and bool(z.loc[date].receipt)
     sec=META[sid]['sector_id'];st=states[sec][d];action='add' if o and o['held'] else 'reentry' if any(t['security_id']==sid and t['side']=='buy' and day(t['at'])<=d for t in tx) else 'first'
     nx=cal[calindex[d]+1] if d in calindex and calindex[d]+1<len(cal) else None;planned=intents.get((sid,d,role));cr=capmap.get((sid,d,role),[]);rs=reserves.get((sid,d,role),[])
     # A same-day opening belongs to the PREVIOUS close, never this new evidence.
     planning_fund=[q for q in fund.get((sid,d,role),[]) if '15:10:00' in q['at']]
     opening_fund=[q for q in fund.get((sid,nx,role),[]) if '09:30:00' in q['at']] if nx else []
     funding=planning_fund+opening_fund
     actual=[t for t in tx if t['security_id']==sid and t['side']=='buy' and day(t['signal_at'])==d and ('mobile' if t['kind']=='add' else 'core')==role]
     barriers=list(o['barriers']) if o else ['opportunity_log_missing'];qpass=o['mobile_Q'] if role=='mobile' and o else o['core_Q'] if o else None;offered=bool(o and role in o['roles']);reason=None
     if barriers:reason=barriers[0]
     elif not offered:reason='core_held_or_epoch_not_offered' if role=='core' and qpass is True else 'Q_or_signal_not_offered'
     elif rs:reason='reserved'
     elif role=='mobile' and reserves.get((sid,d,'core')):reason='core_reservation_preempts_mobile'
     elif planning_fund:reason=planning_fund[-1]['result']
     elif nx and nx>'2023-12-29':reason='window_end_pending_intent_censored'
     elif opening_fund:reason=opening_fund[-1]['result']
     else:reason='unresolved_no_logged_funding'
     if role=='mobile' and not bool(fr.i_target):reason='I_invalid'
     valid=bool(fr.i_target) and qpass is True and offered
     rec=dict(policy=ref,sid=sid,name=META[sid]['name'],role=role,signal_day=d,opportunity_identity=receipt if role=='mobile' else dict(type='core signal-day key; no canonical CP1 implied',source_segment=int(fr.segment_id),stock_I_episode=core_structure(sid,d),day=d),canonical_receipt=receipt,decision_action=action,stock_I_valid=bool(fr.i_target),fresh_I=bool(fr.i_buy),CP1_receipt=bool(z.loc[date].receipt) if date in z.index else False,raw_I_close=float(fr.raw_close),adjusted_close=float(fr.close),factor=float(fr.factor),original_Q=qpass,original_role_offered=offered,valid_entry_signal_before_ACT_resources=valid,ACT_on=bool(ds[d]['on']),barriers=barriers,market_industry_stage=st['stage_name'],market_industry_attempt=st['attempt_id'],market_E0_episode=st['E0_episode'],market_E0_valid=st['E0_valid'],original_priority_rank=o['rank'] if o else None,planned_original_intent=planned,actual_routes=cr,actual_reservations=rs,actual_fills=actual,funding_records=funding,first_block_or_admission=reason,coexisting_route_reasons={q['pool']:q['minimum_reasons'] for q in cr[0]['routes']} if cr else None,minimum_quantity=cr[0]['routes'][0]['minimum_quantity'] if cr else 100 if sid in NAMED else None,actual_financial_industry_level=cr[0]['industry_level'] if cr else None,actual_financial_attempt=cr[0]['attempt'] if cr else None,maximum_quantity_allowed=cr[0]['selected_quantity'] if cr else None,native_next_session=nx,had_actual_fill=bool(actual))
     allrows.append(rec)
   subject=[r for r in allrows if r['sid']==sid]
   for role in ['core','mobile']:
    rr=sorted([x for x in subject if x['role']==role],key=lambda x:x['signal_day']);groups=[]
    for r in rr:
     key=(r['first_block_or_admission'],r['market_industry_attempt'],r['market_industry_stage'],r['decision_action'],tuple(r['barriers']))
     if not groups or key!=groups[-1]['key']:groups.append(dict(key=key,rows=[]))
     groups[-1]['rows'].append(r)
    for j,g in enumerate(groups,1):
     rs=g['rows'];a,e=rs[0],rs[-1];ep=dict(episode=f'{ref}|{sid}|{role}|{j}',policy=ref,sid=sid,name=META[sid]['name'],role=role,first_signal=a['signal_day'],last_signal=e['signal_day'],distinct_opportunities=len(rs),classification=a['decision_action'],first_block_or_admission=a['first_block_or_admission'],industry_stage=a['market_industry_stage'],industry_attempt=a['market_industry_attempt'],ACT_on=a['ACT_on'],priority_rank_first=a['original_priority_rank'],priority_rank_last=e['original_priority_rank'],first_financial_route=a['actual_routes'][0] if a['actual_routes'] else None,price_progress=pricepath(sid,a['signal_day'],e['signal_day']),actual_fill_count=sum(len(x['actual_fills']) for x in rs),canonical_receipts=[x['canonical_receipt'] for x in rs if x['canonical_receipt']],signal_days=[x['signal_day'] for x in rs],unit='consecutive recorded opportunities under identical reason/attempt/stage/action; non-signal gaps are not daily rejected orders')
     episodes.append(ep)
     if sid in NAMED and a['actual_routes']:owner_targets[ref].add(a['actual_routes'][0]['trace_sequence'])
   outcomes.append(dict(policy=ref,sid=sid,name=META[sid]['name'],core_signals=len(core_days),mobile_receipts=len(mobile_days),valid_core_before_ACT_resources=sum(x['valid_entry_signal_before_ACT_resources'] for x in subject if x['role']=='core'),valid_mobile_before_ACT_resources=sum(x['valid_entry_signal_before_ACT_resources'] for x in subject if x['role']=='mobile'),first_block_counts=dict(collections.Counter((x['role']+':'+x['first_block_or_admission']) for x in subject)),actual_transactions=[t for t in tx if t['security_id']==sid],closed_open_contribution=next((x for x in read(Y/'analysis'/ref/'STOCK_CONTRIBUTIONS.json') if x['sid']==sid),None)))
  save(ref+'/OPPORTUNITIES_NAMED.json',[x for x in allrows if x['sid'] in NAMED]);save(ref+'/CONTROL_OPPORTUNITIES.json',[x for x in allrows if x['sid'] not in NAMED]);all_ops+=allrows
  print('CHAINS',ref,len(allrows),'named',sum(x['sid'] in NAMED for x in allrows),'episode snapshots',len(owner_targets[ref]),flush=True)
 save('EPISODES_NAMED.json',[x for x in episodes if x['sid'] in NAMED]);save('EPISODES_CONTROLS.json',[x for x in episodes if x['sid'] not in NAMED]);save('SUBJECT_SUMMARY.json',outcomes)
 # Protection is read directly from saved lines, never rerun or re-anchor CP1.
 b=books['C1'];ds=daily['C1'];sid='300502.SZ';ls=[x for x in b['layers'] if x['sid']==sid and str(x['opened']).startswith('2023')];liveids={x['id'] for x in ls};trace=[];lastfloors={}
 for d,r in sorted(ds.items()):
  if not ('2023-04-06'<=d<='2023-04-28'):continue
  row=atrow(sid,d);layers=[x for x in r['layers'] if x['id'] in liveids]
  for l in layers:
   line=n(l['floor']);changed=lastfloors.get(l['id'])!=line;lastfloors[l['id']]=line
   trace.append(dict(day=d,layer=l['id'],qty=l['qty'],raw_close=str(row.raw_close),adjusted_close=str(row.close),factor=str(row.factor),I_valid=bool(row.i_target),recorded_after_decision_floor=str(line),raw_line=str(line/n(row.factor)),line_changed=changed,source_CP1_receipt=bool(cp(sid).loc[d].receipt),source_CP1_candidate=str(cp(sid).loc[d].candidate),source_I_floor=str(row.i_floor),sell_pending=sid in r['pending_sells']))
 before=[x for x in trace if x['day']=='2023-04-26'];trigger=[x for x in trace if x['day']=='2023-04-27'];assert len(before)==len(trigger)==2
 assert all(n(x['adjusted_close'])>n(x['recorded_after_decision_floor']) for x in before) and all(n(x['adjusted_close'])<=n(x['recorded_after_decision_floor']) and x['I_valid'] for x in trigger)
 exits=[x for x in b['audit'] if x['kind'] in ['exit_request','pilot_layer_exit'] and x.get('sid')==sid and day(x.get('at','')) in ['2023-04-27','2023-04-28']];sells=[t for t in b['trades'] if t['security_id']==sid and t['side']=='sell' and day(t['at'])=='2023-04-28'];post=[x for x in all_ops if x['policy']=='C1' and x['sid']==sid and x['role']=='mobile' and x['signal_day']>'2023-04-28']
 save('XINYISHENG_EXIT_REENTRY.json',dict(stock_I_did_not_exit_at_trigger=True,trace=trace,prior_known_floor=before,trigger=trigger,actual_exit_requests=exits,actual_sell_fills=sells,later_all_fresh_reentry_receipts=post,not_a_hypothetical_tighter_or_looser_stop=True))
 save('OWNER_TARGETS.json',{k:sorted(v) for k,v in owner_targets.items()});save('PHASE1_COMPLETE.json',dict(passed=True,seconds=time.monotonic()-begun,subjects=sorted(subjects),opportunity_rows=len(all_ops),new_account_replays=0,new_indicators=0));print('PHASE1_DONE',round(time.monotonic()-begun,3),flush=True)

if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(reason=str(e),traceback=traceback.format_exc(),new_accounts=0));raise
