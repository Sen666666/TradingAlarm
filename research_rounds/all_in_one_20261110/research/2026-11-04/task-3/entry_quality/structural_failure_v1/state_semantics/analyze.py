"""Original E0/I/CP/industry/ACT state semantics; cached actual-entry join only."""
from pathlib import Path
import json,hashlib,math,statistics,gzip
from decimal import Decimal as D
from collections import defaultdict,Counter
import pandas as pd
O=Path(__file__).resolve().parent;E=O.parents[1];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');B=Path('/Users/bytedance/Documents/Codex/2026-11-04/task');RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');S={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);S[str(p)]=sha(p);return json.loads(p.read_text())
def frame(p,expected=None):p=Path(p);s=sha(p);assert expected is None or s==expected;(S.__setitem__(str(p),s));return pd.read_parquet(p)
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def scalar(x):return None if pd.isna(x) else x.item() if hasattr(x,'item') else x
def agg(xs):
 n=lambda x:D(x['net']);c=lambda x:D(x['cost'])
 return dict(layers=len(xs),stocks=len({x['sid'] for x in xs}),cost=sum(map(c,xs),D(0)),net=sum(map(n,xs),D(0)),positive_net=sum((n(x) for x in xs if n(x)>0),D(0)),negative_net=sum((n(x) for x in xs if n(x)<0),D(0)),positive_layers=sum(n(x)>0 for x in xs),negative_layers=sum(n(x)<0 for x in xs),tail_layers=sum(n(x)/c(x)>=D('.3') for x in xs),tail_net=sum((n(x) for x in xs if n(x)/c(x)>=D('.3')),D(0)))
def grouped(xs,keys):
 g=defaultdict(list)
 for x in xs:g[tuple(str(x[k]) for k in keys)].append(x)
 return [dict(labels=dict(zip(keys,k)),**agg(v)) for k,v in sorted(g.items())]
sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
rich={ref:read(E/'local_high'/(ref+'_ROWS.json')) for ref in ['2022_2024','strong']};scales={ref:{x['layer']:x for x in read(E/'entry_exit_scale/mechanism_review'/(ref+'_ACTUAL_ENTRY_SCALE_JOIN.json'))} for ref in rich}
requests=defaultdict(list)
for ref,rows in rich.items():
 for x in rows:requests[x['sid']].append((ref,x))
states={};out={r:[] for r in rich};checks=Counter()
for sid,reqs in sorted(requests.items()):
 m=sm[sid];fp=m['refs']['facts'];f=frame(fp,m['output_sha256'][fp]);ip=RR/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet';ix=frame(ip)
 for ref,e in reqs:
  d=e['decision_at'][:10];dt=pd.Timestamp(d);q=f.loc[dt];g=ix.loc[dt];sector=e['sector']
  if sector not in states:
   m=im[sector];p=m['refs']['state'];s=frame(p,m['output_sha256'][p]);s['day']=s.day.astype(str).str[:10];states[sector]=s.set_index('day',drop=False)
  sf=states[sector];s=sf.loc[d];z=scales[ref][e['layer']];cp=z['CP1_cached'];trace=z.get('CP1_canonical_trace');reasons=str(g.up_reasons or '').split('|')
  assert bool(q.i_target) and bool(q.g_fresh_up)==bool(g.fresh_up) and q.g_grade==g.grade and abs(float(q.close)-float(g.close))<1e-10
  e=dict(e);e['original_stock_state']={k:scalar(q[k]) for k in ['close','segment_id','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready']};e['G1_up_reasons']=reasons;e['G1_phase']=scalar(g.phase);e['G1_z5']=scalar(g.z5);e['G1_z21']=scalar(g.z21)
  e['I_buy_now']=bool(q.i_buy);e['CP_receipt_now']=bool(cp['receipt']);e['I_CP_same_confirmation_CLOSE']=bool(q.i_buy) and bool(cp['receipt']);e['I_G1_frontier_and_CP_new_frontier_same_CLOSE']=e['I_CP_same_confirmation_CLOSE'] and 'new_price_frontier_in_confirmed_up_structure' in reasons and cp['delta_frontier']>0;e['I_new_E0_and_CP_same_CLOSE']=e['I_CP_same_confirmation_CLOSE'] and 'new_E0_price_volume_up_event' in reasons;e['CP_new_unconsumed_frontier']=None if e['role']=='core' else bool(trace and trace['new_advance_price_event_ids'] and len(trace['new_advance_price_event_ids'])>0 and not trace['trace_unknown']);e['CP_formation_start_exclusive']=None if trace is None else trace['formation_start_exclusive'];e['CP_delta_frontier']=cp['delta_frontier'];e['CP_displacement']=cp['displacement'];e['CP_credit']=cp['credit'];e['CP_used_scale']=cp['scale'];e['CP_candidate']=cp['candidate'];e['stock_floor_binding']=z['initial_order_floor_binding']
  e['industry_state']={k:scalar(s[k]) for k in ['stage','stage_name','attempt_id','attempt_number','E0_valid','E0_episode','E0_floor','mobile_before','mobile_after','action','receipt','receipt_id','authorization_id','authorization_usable']};e['industry_stage']=str(s.stage_name);e['industry_new_receipt_now']=bool(s.receipt);e['industry_attempt']=scalar(s.attempt_id);e['industry_auth_id']=scalar(s.authorization_id)
  receipts=sf[(sf.day<=d)&sf.receipt.astype(bool)];assert len(receipts);lr=receipts.iloc[-1];e['industry_last_receipt_day']=str(lr.day);e['industry_last_receipt_age_observations']=sf.index.get_loc(d)-sf.index.get_loc(lr.day);e['industry_first_in_actual_stock']=e['action']=='first_actual_participation';e['unknown']=[]
  out[ref].append(e);checks['all_entry_cache_joins']+=1
for ref,rows in out.items():
 prior={}
 for e in sorted(rows,key=lambda x:(x['opened'],x['layer'])):
  p=prior.get(e['sid']);e['prior_actual_buy_layer']=None if p is None else p['layer'];e['prior_actual_buy_fill_at']=None if p is None else p['opened'];e['prior_actual_buy_decision']=None if p is None else p['decision_at'];e['new_industry_receipt_since_prior_actual_buy']=None if p is None else e['industry_last_receipt_day']>p['opened'][:10];e['industry_authorization_same_as_prior_actual_buy_decision']=None if p is None else e['industry_auth_id']==p['industry_auth_id'];e['CP_anchor_on_or_after_prior_actual_buy_fill']=None if p is None or e['CP_formation_start_exclusive'] is None else e['CP_formation_start_exclusive']>=p['opened'][:10]
  e['new_stock_close_above_prior_buy_decision_close']=None if p is None else float(e['original_stock_state']['close'])>float(p['original_stock_state']['close']);e['new_stock_close_above_known_postbuy_high']=None if e['post_entry_high_excluding_current'] is None else float(e['original_stock_state']['close'])>float(e['post_entry_high_excluding_current']);prior[e['sid']]=e
 rows.sort(key=lambda x:x['layer']);save(ref+'_ROWS.json',rows)
subsets={'2022_2024':out['2022_2024'],'2022_2023':[x for x in out['2022_2024'] if x['opened'][:4]<'2024'],'post_Oct8_303':[x for x in out['2022_2024'] if x['opened'][:10]>'2024-10-08'],'strong':out['strong']}
summary={}
for label,rows in subsets.items():
 mobile=[x for x in rows if x['role']=='mobile'];follow=[x for x in mobile if x['prior_actual_buy_layer'] is not None]
 summary[label]=dict(all=agg(rows),mobile=agg(mobile),by_role_action=grouped(rows,['role','action']),same_CLOSE_I_CP=agg([x for x in rows if x['I_CP_same_confirmation_CLOSE']]),mobile_same_CLOSE_I_CP=agg([x for x in mobile if x['I_CP_same_confirmation_CLOSE']]),G1_frontier_CP_same_CLOSE=agg([x for x in rows if x['I_G1_frontier_and_CP_new_frontier_same_CLOSE']]),mobile_no_I_buy_now=agg([x for x in mobile if not x['I_buy_now']]),mobile_new_industry_receipt_now=agg([x for x in mobile if x['industry_new_receipt_now']]),mobile_no_new_industry_receipt_now=agg([x for x in mobile if not x['industry_new_receipt_now']]),mobile_followup=agg(follow),followup_no_new_industry_receipt_since_last_buy=agg([x for x in follow if not x['new_industry_receipt_since_prior_actual_buy']]),followup_same_industry_auth_as_last_buy=agg([x for x in follow if x['industry_authorization_same_as_prior_actual_buy_decision']]),followup_CP_anchor_before_prior_fill=agg([x for x in follow if not x['CP_anchor_on_or_after_prior_actual_buy_fill']]),by_industry_stage=grouped(rows,['industry_stage']),followup_by_stock_and_industry_progress=grouped(follow,['new_stock_close_above_known_postbuy_high','new_industry_receipt_since_prior_actual_buy']),mobile_industry_receipt_age_observations=dict(min=min(x['industry_last_receipt_age_observations'] for x in mobile),median=statistics.median(x['industry_last_receipt_age_observations'] for x in mobile),max=max(x['industry_last_receipt_age_observations'] for x in mobile)),all_actual_mobile_canonical_new_frontier=all(x['CP_new_unconsumed_frontier'] for x in mobile))
save('RESULTS.json',summary)
controls={}
for ref in out:
 rr={x['layer']:x for x in out[ref]};controls[ref]=[]
 for c in read(E/'local_high'/(ref+'_FIXED_TAILS.json')):
  matches=[rr[x['layer']] for x in c['matched_actual_No60_rows']];controls[ref].append(dict(original=c['original'],unmatched=c['unmatched'],matched_No60_rows=[{k:x[k] for k in ['layer','sid','decision_at','role','action','cost','net','I_buy_now','I_CP_same_confirmation_CLOSE','I_G1_frontier_and_CP_new_frontier_same_CLOSE','industry_stage','industry_new_receipt_now','industry_last_receipt_day','industry_last_receipt_age_observations','new_industry_receipt_since_prior_actual_buy']} for x in matches]))
 save(ref+'_FIXED_TAIL_CONTROLS.json',controls[ref]);mm=[x for c in controls[ref] for x in c['matched_No60_rows']];summary[ref]['fixed_tail_controls']=dict(original_members=len(controls[ref]),matched_original_members=sum(bool(c['matched_No60_rows']) for c in controls[ref]),matched_actual=agg(mm),matched_mobile_sameI_CP=agg([x for x in mm if x['role']=='mobile' and x['I_CP_same_confirmation_CLOSE']]),matched_mobile_no_industryreceipt_now=agg([x for x in mm if x['role']=='mobile' and not x['industry_new_receipt_now']]),matched_mobile_followup_no_newindustry_since_lastbuy=agg([x for x in mm if x['role']=='mobile' and x['new_industry_receipt_since_prior_actual_buy'] is False]))
save('RESULTS.json',summary);save('VALIDATION.json',dict(checks=checks,rows={k:len(v) for k,v in out.items()},subsets={k:len(v) for k,v in subsets.items()},unknown=0,no_model_calls=True,no_accounts=True,all_original_G1_close_grade_fresh_exact=True,caveat='same confirmation CLOSE/frontier observation is shared price evidence, not proof of identical algorithms or identical formation intervals; independent progress is not statistical independence'))
save('SOURCES.json',dict(sources=S,script_sha256=sha(__file__),no_models_or_accounts=True))
print(json.dumps({k:{z:v[z] for z in ['all','mobile_same_CLOSE_I_CP','G1_frontier_CP_same_CLOSE','followup_no_new_industry_receipt_since_last_buy','mobile_no_new_industry_receipt_now']} for k,v in summary.items()},ensure_ascii=False,default=str),flush=True)
