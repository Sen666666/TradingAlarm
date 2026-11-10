"""Read two original stock timelines, no numeric model or strategy simulation."""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict
import json,gzip,hashlib,csv,math,time
import pandas as pd
O=Path(__file__).resolve().parent;Q=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');SRC={};Z=D(0)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f:return [json.loads(x) for x in f] if lines else json.load(f)
def frame(p,expected=None):
 p=Path(p);h=sha(p);assert expected is None or h==expected;(SRC.__setitem__(str(p),h));return pd.read_parquet(p)
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(D,pd.Timestamp)):return str(x)
 if hasattr(x,'item'):x=x.item()
 return None if isinstance(x,float) and not math.isfinite(x) else x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def closeeq(a,b):return abs(D(str(a))-D(str(b)))<=D('1e-9')*max(D(1),abs(D(str(a))),abs(D(str(b))))
def asof(f,d):
 j=f.index.searchsorted(pd.Timestamp(d),side='right')-1
 return (None,None) if j<0 else (str(f.index[j].date()),f.iloc[j])
def row(r):return {} if r is None else clean(r.to_dict())
def isum(xs):return sum((D(str(x)) for x in xs),Z)

start=time.monotonic();protocol=read(O/'PROTOCOL.json');sm={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};annual={r['sid']:r for r in read(W/'2022-normal-reference-20261031/inputs/MANIFEST.json')};out=[];numeric_checks=0
native=W/'case-stage-ledger-20261031/v3/joint_v3.py';budget=W/'case-stage-ledger-20261031/budget_v3/model.py';SRC[str(native)]=sha(native);SRC[str(budget)]=sha(budget)
assert "if D(str(row.close))<=x['floor']:a.sell" in native.read_text();assert 'self.prices[x.stock]-x.floor' in budget.read_text()
for spec in protocol['selected_cases']:
 w=spec['window'];sid=spec['sid'];ids=set(spec['original_layers']);m=sm[sid];base=Q/'trend_exit_controls_v1/runs/BASELINE'/w/'pair'
 book=read(base/'B.json.gz',True);daily=read(base/'daily.jsonl.gz',True,True);native_layers={r['id']:r for r in book['layers']};buy={r['layer']:r for r in book['trades'] if r['side']=='buy' and r['layer'] in ids};assert set(buy)==ids
 hold={r['layer']:r for r in read(Q/'entry_exit_scale/holding_exit'/(w+'_LAYERS.json')) if r['layer'] in ids};state={r['layer']:r for r in read(Q/'structural_failure_v1/state_semantics'/(w+'_ROWS.json')) if r['layer'] in ids};scales={r['layer']:r for r in read(Q/'entry_exit_scale/mechanism_review'/(w+'_ACTUAL_ENTRY_SCALE_JOIN.json')) if r['layer'] in ids}
 assert all(len(r['actual_sale_parts'])<=1 for r in hold.values()),'partial basis outside these paper inputs'
 f=frame(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]);cp=frame(m['refs']['CP1'],m['output_sha256'][m['refs']['CP1']]);sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));bars=frame(sp,m['source_sha256'][sp]);ep=next(p for p in m['source_sha256'] if p.endswith('/events.parquet'));events=frame(ep,m['source_sha256'][ep]);ip=RR/'ix-a-share-entry-20261025/signals'/(sid+'.parquet');ix=frame(ip,m['source_sha256'][str(ip)])
 if w=='2022_2024':rp=annual[sid]['output_path'];assert sha(rp)==annual[sid]['output_sha256']
 else:rp=m['refs']['receipts'];assert sha(rp)==m['output_sha256'][rp]
 receipts={r['confirmed_day']:r for r in read(rp)}
 logs={}
 for name in ['opportunities','funding','rank-policy']:
  with gzip.open(base/(name+'.jsonl.gz'),'rt') as fh:
   logs[name]=[r for line in fh if (r:=json.loads(line)).get('sid')==sid and spec['start']<=r.get('day',r.get('at',''))[:10]<=spec['end']]
  SRC[str(base/(name+'.jsonl.gz'))]=sha(base/(name+'.jsonl.gz'))
 decisions={r['at'][:10]:[a for a in r['intents'] if a['sid']==sid] for r in book['decisions']};audits=[r for r in book['audit'] if r.get('sid')==sid and spec['start']<=r.get('at','')[:10]<=spec['end']];journal=[r for r in book['journal'] if r.get('sid')==sid and spec['start']<=r.get('at','')[:10]<=spec['end']]
 # Original I-root start is read from the existing boolean/cache, never recomputed policy.
 times=pd.Series(f.index,index=f.index);i_start=times.where(f.i_target.astype(bool)&(~f.i_target.shift(fill_value=0).astype(bool)|f.segment_id.ne(f.segment_id.shift()))).ffill().where(f.i_target.astype(bool))
 prev={};days=[];raises=[];paper_requests=[]
 for d in daily:
  day=d['at'][:10]
  if day<spec['start']:
   prev={r['id']:r for r in d['layers'] if r['id'] in ids};continue
  if day>spec['end']:break
  fd,ff=asof(f,day);bd,bb=asof(bars,day);xd,xx=asof(ix,day);cpnow=cp.loc[pd.Timestamp(day)] if pd.Timestamp(day) in cp.index else None;ev=events.loc[pd.Timestamp(day)] if pd.Timestamp(day) in events.index else None;canonical=receipts.get(day);freshcp=cpnow is not None and bool(cpnow.receipt)
  if freshcp:assert canonical is not None and closeeq(canonical['original_candidate'],cpnow.candidate)
  live=[r for r in d['layers'] if r['id'] in ids];same_day_buys=[r for r in buy.values() if r['at'][:10]==day];same_day_sells=[r for r in book['trades'] if r['side']=='sell' and r['security_id']==sid and r['at'][:10]==day and any(p['layer'] in ids for p in r['parts'])];today_audit=[r for r in audits if r['at'][:10]==day];today_journal=[r for r in journal if r['at'][:10]==day];specific=[r for r in today_audit if r['kind']=='pilot_layer_exit' and ids.intersection(r['layers'])]
  current=D(str(ff.raw_close));factor=D(str(ff.factor));layers=[];released=Z;released_old=Z;before_risk=Z;after_risk=Z;basis_total=Z;mark_total=Z;guard_breaches=[]
  for h in live:
   lid=h['id'];kind=h['kind'];initial=D(str(buy[lid]['floor']));prior=prev.get(lid);old=D(str(prior.get('last_core_line',prior['floor']) if kind=='core' else prior['floor'])) if prior else initial;post=D(str(h.get('last_core_line',h['floor']) if kind=='core' else h['floor']));q=D(h['qty']);rawold=old/factor;rawnew=post/factor;before=q*max(Z,current-rawold);after=q*max(Z,current-rawnew);basis=D(hold[lid]['cost']);mark=q*current
   # Full original sale parts only; these selected live layers have not partially sold.
   assert not any(p['at'][:10]<=day for p in hold[lid]['actual_sale_parts'])
   up=post>old and not closeeq(post,old);sources=[]
   if up:
    if pd.notna(ff.i_floor) and closeeq(post,ff.i_floor):sources.append('original_I_floor')
    if freshcp and closeeq(post,cpnow.candidate):sources.append('original_CP_receipt_candidate')
   pending=[a for a in audits if a['kind']=='pilot_layer_exit' and lid in a['layers'] and a['at']<=d['at']];breached=current<=rawold
   v=dict(layer=lid,role='core' if kind=='core' else 'mobile',qty=h['qty'],fee_aware_remaining_original_basis=basis,cumulative_original_layer_cash=h['cash'],known_dividend_AR=h['dividend'],mark=mark,held_unreal=mark-basis,
    guard_before_CLOSE_check_adjusted=old,guard_before_CLOSE_check_raw=rawold,guard_after_original_CLOSE_adjusted=post,guard_after_original_CLOSE_raw=rawnew,guard_true_numeric_advance=up,matching_same_CLOSE_raise_sources=sources,
    native_mark_to_guard_before_check=before,native_mark_to_guard_after_checks=after,reference_mark_risk_reduced_by_guard_advance=before-after if up else Z,reference_principal_shortfall_to_saved_guard=max(Z,basis-q*rawnew),
    guard_breached_at_old_line=breached,original_layer_exit_latched_at_CLOSE=bool(pending),latched_requests=pending,saved_native_layer=h,newly_filled_this_OPEN=lid in {a['layer'] for a in same_day_buys},reference_quantity_only_not_paper_quantity=True)
   layers.append(v);before_risk+=before;after_risk+=after;basis_total+=basis;mark_total+=mark
   if breached:guard_breaches.append(lid)
   if up:
    released+=before-after
    if prior:released_old+=before-after
    raises.append(dict(day=day,**v))
   numeric_checks+=1
  realized_byday=[];known_ar=Z;wealth=Z
  for lid in ids:
   n=native_layers[lid]
   if n['opened'][:10]>day:continue
   h=next((h for h in live if h['id']==lid),None)
   if h:wealth+=D(h['cash'])+D(h['qty'])*current+D(h['dividend']);known_ar+=D(h['dividend'])
   elif n['closed'] is not None and n['closed'][:10]<=day:wealth+=D(n['cash'])+D(n['dividend']);known_ar+=D(n['dividend']);realized_byday.append(lid)
  reasons=[z for z in str(xx.up_reasons if pd.notna(xx.up_reasons) else '').split('|') if z];new_structure_reasons=[z for z in reasons if z in ['new_S21_up_confirmation','new_S63_up_confirmation']];newroot=bool(ff.i_target) and pd.Timestamp(i_start.loc[pd.Timestamp(fd)]).date().isoformat()==day
  evidence='no_CP_request'
  if freshcp:
   evidence='CP_with_new_original_S21_or_S63_confirmation' if new_structure_reasons else 'CP_with_new_original_I_root' if newroot else 'CP_with_new_up_leg_event_inside_persistent_I' if ev is not None and ev.event==1 else 'CP_new_frontier_inside_existing_structure_only' if reasons==['new_price_frontier_in_confirmed_up_structure'] else 'CP_local_new_frontier_no_other_original_structure_confirmation'
  opp=[r for r in logs['opportunities'] if r['day']==day];fund=[r for r in logs['funding'] if r['at'][:10]==day];ranks=[r for r in logs['rank-policy'] if r['day']==day];request=bool(freshcp and bool(ff.i_target))
  paper='本表原CP路径无新增申请；按原持仓/保护/现金事实观察。这不是完整v2行为，替代库存/身份/预算未建立。'
  if not live and not specific and (not bool(ff.i_target) or not d['on']):paper='原路径flat，等待原资格/原市场许可；没有持仓或真实退出请求，不虚构减仓。v2身份/数量未定。'
  elif specific or not bool(ff.i_target) or not d['on']:paper='真实原持仓硬退出或已锁请求优先；不可用当日CP/新ID取消卖单或直接重新授满。替代减仓数量UNKNOWN。'
  elif request:
   if not live:paper='新机会/当前原路径无持仓：只可记首笔小风险本金申请；没有已持库存保护前推释放量。本金预算与数量UNKNOWN。'
   elif released>0:paper='CP仅给申请；本CLOSE可证实原股数下保护前推减少参考风险。可复用余额、stress/行业/现金预算未识别，grant与数量UNKNOWN；拒绝CP自动再领固定NAV份额。'
   else:paper='CP仅给申请，本CLOSE没有可证实原已持库存保护前推带来的新增风险释放。拒绝仅凭CP自动再领固定NAV份额；既有未使用释放余额未知，不能断言全部拒绝或给定数量。'
  elif layers and released>0:paper='没有CP新增申请，但保护真实前推有原股数参考风险减少；不自动转成现金/新grant，数量UNKNOWN。'
  if bool(ff.i_buy):paper+=' 原i_buy当日新事件成立，可供新增探索申请接口；本表未决定其v2身份/proof/预算，不得将“无CP申请”读成v2也无申请。'
  dayrow=dict(day=day,original_CLOSE_clock=d['at'],source_days=dict(facts=fd,price_volume=bd,G1=xd),original_bar=row(bb),original_stock_facts=row(ff),original_G1=row(xx),original_native_event=row(ev),original_CP_cache=row(cpnow),original_CP_canonical_receipt=canonical,
   original_I_root_start=None if not bool(ff.i_target) else str(pd.Timestamp(i_start.loc[pd.Timestamp(fd)]).date()),new_original_I_root_today=newroot,original_G1_new_structure_confirm_reasons=new_structure_reasons,CP_information_class=evidence,CP_does_not_prove_independent_trend=True,
   original_OPEN_buys=same_day_buys,original_OPEN_sells=same_day_sells,original_CLOSE_specific_exit_requests=specific,original_audit_today=today_audit,original_journal_today=today_journal,original_intents=decisions.get(day,[]),original_opportunities=opp,original_funding=fund,original_ranking=ranks,
   original_account=dict(ACT_on=d['on'],NAV=d['nav'],available_cash=d['available'],order_reserved=d['order_reserved'],settlement_locked=d['settlement_locked'],payable=d['payable'],sale_receivable=d['sale_receivable'],dividend_receivable=d['dividend_receivable'],inventory=d['inventory'],pool_probe=d['pool_probe'],pool_confirmed=d['pool_confirmed'],native_reported_account_mark_risk=D(str(d['pool_probe'][1]))+D(str(d['pool_confirmed'][1])),pending_sell_sids=d['pending_sells'],pending_intents=d['pending_intents']),
   original_live_layers=layers,original_stock_mark=mark_total,original_stock_remaining_basis=basis_total,original_stock_held_unreal=mark_total-basis_total,original_selected_campaign_known_wealth=wealth,original_selected_campaign_known_AR=known_ar,original_mark_to_guard_before_CLOSE=before_risk,original_mark_to_guard_after_CLOSE=after_risk,
   true_guard_advance_reference_risk_reduction=released,true_guard_advance_prior_snapshot_inventory_risk_reduction=released_old,guard_breach_layers=guard_breaches,clipped_zero_risk_does_not_release_cash=bool(guard_breaches),paper_decision_scope='original CP request plus saved holding/protection reference only; not full v2 behavior',original_i_buy_event_for_exploration_interface=bool(ff.i_buy),exploration_event_identity_proof_budget='UNDETERMINED_NOT_COMPUTED',paper_decision=paper,paper_quantity='UNKNOWN',paper_granted_risk_budget='UNKNOWN',paper_unused_released_risk_balance='UNKNOWN',original_quantity_cannot_be_imported_into_paper_state=True)
  days.append(dayrow);prev={h['id']:h for h in live}
  if request:paper_requests.append(dayrow)
 endpoint=isum(native_layers[lid]['cash'] for lid in ids)+isum(native_layers[lid]['dividend'] for lid in ids)
 if any(native_layers[lid]['qty'] for lid in ids):endpoint+=days[-1]['original_stock_mark']
 assert closeeq(endpoint,days[-1]['original_selected_campaign_known_wealth'])
 case=dict(spec=spec,selected_actual_layers=[dict(native=native_layers[lid],original_buy=buy[lid],original_layer_accounting=hold[lid],original_entry_state=state[lid],original_entry_CP_proof=scales[lid]) for lid in sorted(ids)],selected_actual_layers_outcome_fields='retrospective reference only; terminal net/closed/holding peaks are never inputs to per-day paper_decision',days=days,true_saved_guard_advances=raises,actual_original_net_at_case_end=endpoint,original_CP_request_days=len(paper_requests),new_accounts=0,new_candidate_fills=0,quantity='UNKNOWN')
 name=sid.replace('.','_');save(name+'_DAILY_PAPER_INPUTS.json',case)
 # A compact daily sheet; detailed per-layer before/after fields remain in JSON.
 flat=[]
 for a in days:
  b=a['original_bar'];ff=a['original_stock_facts'];c=a['original_CP_cache'];flat.append(dict(day=a['day'],raw_open=b.get('raw_open'),raw_high=b.get('raw_high'),raw_low=b.get('raw_low'),raw_close=b.get('raw_close'),amount=b.get('amount'),adjusted_close=ff.get('close'),factor=ff.get('factor'),E0_on=ff.get('e0_target'),I_on=ff.get('i_target'),I_floor=ff.get('i_floor'),I_root_start=a['original_I_root_start'],G1_reasons=a['original_G1'].get('up_reasons'),native_event=a['original_native_event'].get('event'),CP_receipt=c.get('receipt'),CP_candidate=c.get('candidate'),CP_class=a['CP_information_class'],original_buy_layers=','.join(str(v['layer']) for v in a['original_OPEN_buys']),original_sell_parts=','.join(str(v['parts']) for v in a['original_OPEN_sells']),actual_live_qty=sum(v['qty'] for v in a['original_live_layers']),guard_before_adjusted=json.dumps({v['layer']:str(v['guard_before_CLOSE_check_adjusted']) for v in a['original_live_layers']}),guard_after_adjusted=json.dumps({v['layer']:str(v['guard_after_original_CLOSE_adjusted']) for v in a['original_live_layers']}),genuine_guard_advance_layers=','.join(str(v['layer']) for v in a['original_live_layers'] if v['guard_true_numeric_advance']),reference_risk_released=str(a['true_guard_advance_reference_risk_reduction']),native_mark_risk_before=str(a['original_mark_to_guard_before_CLOSE']),native_mark_risk_after=str(a['original_mark_to_guard_after_CLOSE']),basis=str(a['original_stock_remaining_basis']),held_unreal=str(a['original_stock_held_unreal']),known_campaign_wealth=str(a['original_selected_campaign_known_wealth']),known_AR=str(a['original_selected_campaign_known_AR']),account_available=str(a['original_account']['available_cash']),account_reserved=str(a['original_account']['order_reserved']),ACT_on=a['original_account']['ACT_on'],original_exit_requests=json.dumps(a['original_CLOSE_specific_exit_requests'],ensure_ascii=False),paper_decision=a['paper_decision'],paper_quantity='UNKNOWN',paper_grant='UNKNOWN'))
 for a,b in zip(flat,days):
  a['original_i_buy_event']=b['original_i_buy_event_for_exploration_interface'];a['paper_column_scope']=b['paper_decision_scope'];a['exploration_identity_proof_budget']=b['exploration_event_identity_proof_budget']
 with (O/(name+'_DAILY.csv')).open('w') as fh:
  wr=csv.DictWriter(fh,fieldnames=list(flat[0]));wr.writeheader();wr.writerows(clean(flat))
 out.append(dict(sid=sid,name=spec['name'],window=w,days=len(days),actual_layers=sorted(ids),endpoint_wealth=endpoint,still_open=any(native_layers[lid]['qty'] for lid in ids),CP_request_days=len(paper_requests),true_guard_raise_records=len(raises),file=name+'_DAILY_PAPER_INPUTS.json'))
save('INDEX_AND_VALIDATION.json',dict(status='PASS_READ_ONLY_ORIGINAL_TIMELINES',cases=out,per_layer_snapshot_checks=numeric_checks,new_accounts=0,new_models=0,new_policy_simulations=0,alternative_quantities='UNKNOWN',elapsed_seconds=time.monotonic()-start))
save('SOURCE_MANIFEST.json',dict(sources=SRC,script_sha256=sha(__file__),write_scope=str(O),all_original_sources_unchanged=True))
print(json.dumps(clean(out),ensure_ascii=False))
