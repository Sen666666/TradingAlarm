"""Read-only full-warm industry attempt progress and actual funded layers."""
from pathlib import Path
from decimal import Decimal as D
import sys,json,gzip,time,hashlib,collections,math
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'q2-normal-continuation-20261031'));import continuation as E
J,L=E.J,E.L;Z=D(0)
WINDOWS={'2022':('2022-01-01','2022-12-30'),'2025_26':('2025-07-01','2026-06-30')}
META=L.read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json'))
def read(p):return json.loads(Path(p).read_text())
def obj(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def save(n,x):E.IO.write_json(O/n,J.T.norm(J.W.canon(x)))
def n(x):return D(str(x))
def day(x):return str(x)[:10]
def valid(x):return x is not None and pd.notna(x) and math.isfinite(float(x))
def ratio(price,attempt):
 if not valid(price) or not valid(attempt['fixed_R']) or attempt['fixed_R']<=0:return None
 return (float(price)-attempt['probe_close'])/attempt['fixed_R']
def bucket(x):return 'N/A' if x is None else '<0R' if x<0 else '0_to_1R' if x<1 else '1_to_2R' if x<2 else '>=2R'
def dist(v):
 s=pd.Series(v,dtype=float).dropna();return {'n':len(s),**{str(q):float(s.quantile(q)) for q in [0,.25,.5,.75,.9,1]}} if len(s) else {'n':0}
def main():
 started=time.monotonic();im=read(L.U/'INDUSTRY_MANIFEST.json');attempts={};known={};opens={};events=[];original_files={str(O/'PROTOCOL.txt'):L.sha(O/'PROTOCOL.txt'),str(Path(__file__)):L.sha(__file__)}
 runtime={r['series_id']:r for r in read(J.M.P/'manifest.json')['series']}
 for rec in im:
  sid=rec['series'];st=pd.read_parquet(rec['refs']['state']);raw=pd.read_parquet(runtime[sid]['raw']['path']);raw.index=pd.DatetimeIndex(pd.to_datetime(raw.trade_date)).normalize();opens[sid]={str(d.date()):float(r.open) for d,r in raw.iterrows() if valid(r.open) and r.open>0 and r.observed_bar is True and r.price_eligible is True}
  # All industry prices/floors are already the same unadjusted index units.
  f=pd.read_parquet(J.M.O/'industry-facts'/f'{sid}.parquet',columns=['factor','raw_close']);assert f.factor.dropna().eq(1).all(),(sid,'industry units need explicit conversion')
  original_files[rec['refs']['state']]=L.sha(rec['refs']['state']);original_files[runtime[sid]['raw']['path']]=runtime[sid]['raw']['sha256'];by={};active={}
  for idx,r in enumerate(J.T.norm(st.to_dict('records'))):
   date=r['day'];aid=r['attempt_id']
   if r['action']=='probe':
    assert aid and r['receipt_id'];initial=max(r['E0_floor'],r['candidate_floor']);assert r['mobile_after']==initial
    financial=r['E0_episode']+':'+r['receipt_id'];a=dict(sector=sid,market_attempt_id=aid,financial_attempt_id=financial,episode=r['E0_episode'],probe_day=date,probe_idx=idx,probe_close=float(r['close']),initial_line=float(initial),initial_raw_CP1_floor=r['candidate_floor'],fixed_R=float(r['close'])-float(initial),probe_receipt=r['receipt_id'],events=[],fresh_receipts=0,windows=set());attempts[financial]=a;active[aid]=a
   a=active.get(aid) if aid else None
   if a:
    if r['receipt'] and r['new_receipt']:a['fresh_receipts']+=1
    rr=ratio(r['close'],a);snapshot=dict(day=date,close=r['close'],stage=r['stage_name'],financial_attempt_id=a['financial_attempt_id'],market_attempt_id=aid,R=rr,net_price_pct=(r['close']/a['probe_close']-1)*100,elapsed_observations=idx-a['probe_idx'],fresh_receipt_count=a['fresh_receipts'],raw_CP1_floor=r['candidate_floor'],current_mobile=r['mobile_after'])
    for win,(lo,hi) in WINDOWS.items():
     if lo<=date<=hi:a['windows'].add(win);by[date]=snapshot
    if r['action'] in ['probe','confirmed','expanded']:
     e=dict(**snapshot,action=r['action'],probe_day=a['probe_day'],probe_close=a['probe_close'],initial_line=a['initial_line'],fixed_R=a['fixed_R'],R_bin=bucket(rr),below_probe=r['close']<a['probe_close'],in_windows=[w for w,(lo,hi) in WINDOWS.items() if lo<=date<=hi]);a['events'].append(e);events.append(e)
   else:
    for lo,hi in WINDOWS.values():
     if lo<=date<=hi:by[date]=dict(day=date,close=r['close'],stage=r['stage_name'],financial_attempt_id=None,market_attempt_id=None,R=None,elapsed_observations=None,fresh_receipt_count=None,raw_CP1_floor=r['candidate_floor'],current_mobile=r['mobile_after'])
  known[sid]=by
 attempts_out=[]
 for a in attempts.values():
  if a['windows']:attempts_out.append(dict(a,windows=sorted(a['windows'])))
 save('ATTEMPTS.json',attempts_out);save('UPGRADE_EVENTS.json',[r for r in events if r['in_windows'] or attempts[r['financial_attempt_id']]['windows']])
 stage_summary={}
 for win,(lo,hi) in WINDOWS.items():
  all_a=[a for a in attempts.values() if win in a['windows']];ev=[r for r in events if win in r['in_windows']];stage_summary[win]=dict(attempts_intersect_window=len(all_a),attempts_inherited_from_warmup=sum(a['probe_day']<lo for a in all_a),attempts_started_in_window=sum(lo<=a['probe_day']<=hi for a in all_a),invalid_initial_R=sum(not valid(a['fixed_R']) or a['fixed_R']<=0 for a in all_a),upgrade_event_counts=dict(collections.Counter(r['action'] for r in ev)),upgrade_below_probe_counts=dict(collections.Counter(r['action'] for r in ev if r['below_probe'])),upgrade_R_bins={k:dict(collections.Counter(r['R_bin'] for r in ev if r['action']==k)) for k in ['probe','confirmed','expanded']},elapsed_by_upgrade={k:dist([r['elapsed_observations'] for r in ev if r['action']==k]) for k in ['confirmed','expanded']})
 save('STAGE_DENOMINATORS.json',stage_summary);save('SOURCE_FREEZE.json',dict(readonly=True,source_SHA256=original_files,new_account_paths=0,new_model_calculations=0))
 print('STAGE_2022',json.dumps(stage_summary['2022'],ensure_ascii=False),flush=True)
 # Only terminal pricing of the existing 2025-26 books; no account is initialized.
 currentbooks={r:obj(W/'q2-normal-continuation-20261031/runs'/r/'pair/B.json.gz') for r in ['B3','B_diag']};terminalids=sorted({x['sid'] for b in currentbooks.values() for x in b['layers'] if x['qty']});_,market,_=J.M.context('2026-06-30',ids=terminalids)
 terminal={sid:market.latest_mark(sid,J.M.N.iso('2026-06-30T15:10:00+08:00')).cny_price(J.M.N.iso('2026-06-30T15:10:00+08:00')) for sid in terminalids}
 all_summary=[]
 for win in ['2022','2025_26']:
  for ref in ['B3','B_diag']:
   base=W/'2022-normal-reference-20261031' if win=='2022' else W/'q2-normal-continuation-20261031';p=base/'runs'/ref/'pair/B.json.gz';b=obj(p) if win=='2022' else currentbooks[ref];original_files[str(p)]=L.sha(p);meta=b['metadata'];js={r['layer']:r for r in b['journal'] if r['kind']=='real_buy_fill'};cost={}
   for t in b['trades']:
    if t['side']=='buy':cost[t['layer']]=cost.get(t['layer'],Z)+n(t['gross_cny'])+n(t['fees_cny'])
   prior2022={r['layer']:r for r in read(base/'analysis'/ref/'LAYER_PARTITIONS.json')} if win=='2022' else None
   nets={x['id']:(n(prior2022[x['id']]['net']) if win=='2022' else n(x['cash'])+n(x['dividend'])+(D(x['qty'])*terminal[x['sid']] if x['qty'] else Z)) for x in b['layers']};assert abs(sum(nets.values(),Z)-(n(b['ending_NAV'])-D(1000000)))<D('.00000001')
   order_action={};before=collections.defaultdict(list);entry_action={}
   for x in sorted(b['layers'],key=lambda x:(x['opened'],x['id'])):
    j=js[x['id']];bid=j['budget_order'];older=before[x['sid']]
    if bid not in order_action:
     held=any(z['closed'] is None or z['closed']>x['opened'] for z in older);order_action[bid]='add' if held else 'reentry' if older else 'first'
    entry_action[x['id']]=order_action[bid];before[x['sid']].append(x)
   entries=[];unknown=[]
   for x in b['layers']:
    j=js[x['id']]
    if j['role']!='mobile' or j['pool']!='confirmed':continue
    m=meta[str(x['id'])];a=attempts.get(m['attempt']);signal=day(x['signal_at']);fill=day(x['opened']);sid=x['sid'];sector=m['sector'];ks=known[sector].get(signal);why=[]
    if a is None:why.append('attempt_probe_not_found')
    elif a['sector']!=sector or a['episode']!=m['episode']:why.append('attempt_identity_conflict')
    if not ks or ks['financial_attempt_id']!=m['attempt']:why.append('decision_known_state_does_not_match_actual_attempt')
    px=opens[sector].get(fill);rr=ratio(px,a) if a else None
    if px is None:why.append('fill_open_industry_price_unknown')
    if why:unknown.append(dict(layer=x['id'],sid=sid,reasons=why))
    ev=a['events'] if a else [];last_upgrade=next((v for v in reversed(ev) if v['day']<=signal and v['action'] in ['confirmed','expanded']),None)
    r=dict(window=win,reference=ref,layer=x['id'],sid=sid,name=META[sid]['name'],industry=META[sid]['industry'],sector=sector,attempt=m['attempt'],market_attempt_id=a['market_attempt_id'] if a else None,probe_day=a['probe_day'] if a else None,probe_close=a['probe_close'] if a else None,initial_line=a['initial_line'] if a else None,fixed_R=a['fixed_R'] if a else None,signal_day=signal,fill_at=x['opened'],industry_open_at_fill=px,fill_open_R=rr,fill_open_bin='unknown_mapping' if why else bucket(rr),fill_open_below_probe=bool(a and px is not None and px<a['probe_close']),decision_close_R=ks['R'] if ks else None,decision_close_bin='unknown_mapping' if why else bucket(ks['R'] if ks else None),decision_close_below_probe=bool(a and ks and ks['close']<a['probe_close']),elapsed_completed_observations=ks['elapsed_observations'] if ks else None,fresh_industry_receipts_at_decision=ks['fresh_receipt_count'] if ks else None,decision_known_stage=ks['stage'] if ks else None,raw_CP1_floor_at_decision=ks['raw_CP1_floor'] if ks else None,latest_actual_upgrade=last_upgrade,entry_action=entry_action[x['id']],budget_order=j['budget_order'],canonical_stock_receipt=j['CP1_id'],actual_buy_cash=cost[x['id']],net_contribution=nets[x['id']],closed=not x['qty'],terminal_quantity=x['qty'],tail_layer=nets[x['id']]/cost[x['id']]>=D('.3'),unknown_reasons=why)
    entries.append(r)
   def aggregate(key):
    out=[]
    for bin in ['<0R','0_to_1R','1_to_2R','>=2R','N/A','unknown_mapping']:
     es=[r for r in entries if r[key]==bin];out.append(dict(bin=bin,layers=len(es),unique_receipts=len({r['canonical_stock_receipt'] for r in es}),buy_cash=sum((r['actual_buy_cash'] for r in es),Z),closed_positive=sum((r['net_contribution'] for r in es if r['closed'] and r['net_contribution']>=0),Z),closed_negative=sum((r['net_contribution'] for r in es if r['closed'] and r['net_contribution']<0),Z),open_net=sum((r['net_contribution'] for r in es if not r['closed']),Z),actions=dict(collections.Counter(r['entry_action'] for r in es)),elapsed=dist([r['elapsed_completed_observations'] for r in es if r['elapsed_completed_observations'] is not None])))
    return out
   selected_net=sum((r['net_contribution'] for r in entries),Z);result=dict(window=win,reference=ref,new_confirmed_mobile_layers=len(entries),unknown_mappings=len(unknown),entry_below_probe_open_count=sum(r['fill_open_below_probe'] for r in entries),entry_below_probe_decision_close_count=sum(r['decision_close_below_probe'] for r in entries),selected_layer_net=selected_net,excluded_other_roles_or_probe_net=sum(nets.values(),Z)-selected_net,whole_NAV_net=sum(nets.values(),Z),fill_open_bins=aggregate('fill_open_bin'),authorization_close_bins=aggregate('decision_close_bin'),entry_open_below_probe_with_nonnegative_latest_upgrade=sum(r['fill_open_below_probe'] and r['latest_actual_upgrade'] is not None and not r['latest_actual_upgrade']['below_probe'] for r in entries),entry_open_nonnegative_with_below_probe_latest_upgrade=sum(not r['fill_open_below_probe'] and r['latest_actual_upgrade'] is not None and r['latest_actual_upgrade']['below_probe'] for r in entries),layer_and_receipt_units_not_independent_trials=True)
   save(Path(win)/ref/'ENTRIES.json',entries);save(Path(win)/ref/'SUMMARY.json',result);save(Path(win)/ref/'UNKNOWN.json',unknown);all_summary.append(result);print('FUNDED',win,ref,'layers',len(entries),'unknown',len(unknown),'belowprobe',result['entry_below_probe_open_count'],'bins',J.W.canon(result['fill_open_bins']),flush=True)
 save('SUMMARY.json',dict(stage=stage_summary,funding=all_summary));save('COMPLETION.json',dict(read_only=True,new_account_paths=0,new_policy=0,seconds=time.monotonic()-started,source_SHA256=original_files));print('READONLY_DONE',round(time.monotonic()-started,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save('ERROR.json',dict(type=type(e).__name__,reason=str(e)));raise
