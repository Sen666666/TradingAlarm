"""Static original-account extraction only; no account/model/strategy imports."""
from pathlib import Path
from decimal import Decimal as D, getcontext
from collections import Counter
import gzip,json,hashlib,csv,math,sys
import pandas as pd
getcontext().prec=65
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;E=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
SRC={};Z=D(0)
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb')as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v)for v in x]
 if isinstance(x,(D,pd.Timestamp)):return str(x)
 if hasattr(x,'item'):x=x.item()
 if isinstance(x,float)and not math.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def read(p,gz=False):
 p=Path(p);SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt')if gz else p.open())as f:return json.load(f)
def stream(p,predicate=lambda x:True):
 p=Path(p);SRC[str(p)]=sha(p)
 with gzip.open(p,'rt')as f:return [x for l in f if predicate(x:=json.loads(l))]
def frame(p,expected=None):
 p=Path(p);h=sha(p);assert expected is None or h==expected,(p,h,expected);SRC[str(p)]=h;return pd.read_parquet(p)
def norm(x):return str(x).replace('T',' ')
def gradebucket(g):return 'negative'if g<0 else 'zero'if g==0 else 'one'if g==1 else 'warm_ge2'
state={w:read(E/'structural_failure_v1/state_semantics'/f'{w}_ROWS.json')for w in ['2022_2024','strong']}
campaigns={w:read(E/'structural_failure_v1/accounting/results_v2'/f'{w}_CAMPAIGNS_FULL_ACCOUNTING.json')for w in state}
rich={w:{x['layer_in_this_book']:x for x in read(E/'dec2022_authorization_v1/account_comparison/results_v1'/f'BASELINE_{w}_LAYERS.json')}for w in state}
candidate=[]
for w,rows in state.items():
 byid={x['layer']:x for x in rows}
 for c in campaigns[w]:
  hits=[byid[l]for l in c['layer_ids']if byid[l]['role']=='mobile'and byid[l]['original_stock_state']['g_grade']<2]
  if hits:
   candidate.append(dict(window=w,**{k:c[k]for k in ['campaign_id','sid','name','industry','opened','closed','layer_ids','endpoint_net','strict_realized','AR']},cold_layers=[dict(layer=x['layer'],decision_at=x['decision_at'],opened=x['opened'],grade=x['original_stock_state']['g_grade'],grade_bucket=gradebucket(x['original_stock_state']['g_grade']),net=x['net'],action=x['action'])for x in hits],cold_layer_net=sum((D(x['net'])for x in hits),Z)))
closed=[x for x in candidate if x['closed']is not None]
loss=sorted((x for x in closed if D(x['endpoint_net'])<0),key=lambda x:(D(x['endpoint_net']),x['campaign_id']))
selected=[]
for x in loss:
 if x['sid']not in {z['sid']for z in selected}:selected.append(x)
 if len(selected)==2:break
for w in ['strong','2022_2024']:
 selected.append(max((x for x in closed if x['window']==w and D(x['endpoint_net'])>0),key=lambda x:(D(x['endpoint_net']),x['campaign_id'])))
warm=sorted((c for c in campaigns['strong']if c['closed']and c['industry']=='半导体'and D(c['endpoint_net'])>0 and any(rich['strong'][l]['role']=='mobile'and rich['strong'][l]['opened'][:4]=='2026'for l in c['layer_ids'])),key=lambda c:D(c['endpoint_net']),reverse=True)[0]
selection={'clock':'grade at actual fill preceding native market CLOSE = original intent decision CLOSE; no extra one-bar shift','universe':'Original actual MOBILE layers in both BASELINE books; grade<2 split negative/0/1. Endpoint selects forensic examples only, never input to a gate.','loss_selection':'Two distinct-stock lowest endpoint-net completed campaigns containing cold MOBILE','positive_selection':'Largest endpoint-net completed cold-containing campaign in each original window; strong winner is a 2025 fill/2026 exit cross-year reference, not a 2026 new fill','selected_four':selected,'warm_semiconductor_control':{k:warm[k]for k in ['campaign_id','sid','name','industry','opened','closed','layer_ids','endpoint_net']},'2026_cold_semiconductor_actual_entry_count':sum(x['role']=='mobile'and x['opened'][:4]=='2026'and x['industry']=='半导体'and x['original_stock_state']['g_grade']<2 for x in state['strong']),'counts_not_independent_trials':True,'new_accounts':0,'new_models':0,'new_parameters':0}
save('SELECTION_FREEZE.json',selection);save('COLD_CAMPAIGN_CANDIDATES.json',sorted(candidate,key=lambda x:(x['window'],D(x['endpoint_net']))))
print('SELECTION_READY',[(x['sid'],str(x['endpoint_net']),str(x['cold_layer_net']))for x in selected],flush=True)

sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
joint=W/'case-stage-ledger-20261031/v3/joint_v3.py';policy=RR/'b5-g1-20261025/code/policies_g1.py'
SRC[str(joint)]=sha(joint);SRC[str(policy)]=sha(policy)
out=[];checks=Counter();entrytable=[]
for w in state:
 samples=[dict(control=False,selected=x)for x in selected if x['window']==w]
 if w=='strong':samples.append(dict(control=True,selected={**warm,'window':w}))
 if not samples:continue
 sids={x['selected']['sid']for x in samples};base=E/'trend_exit_controls_v1/runs/BASELINE'/w/'pair'
 book=read(base/'B.json.gz',True);daily=stream(base/'daily.jsonl.gz');byid={x['layer']:x for x in state[w]};booklayers={x['id']:x for x in book['layers']};buy={x['layer']:x for x in book['trades']if x['side']=='buy'}
 logs={name:stream(base/(name+'.jsonl.gz'),lambda x:x.get('sid')in sids)for name in ['opportunities','funding','rank-policy']}
 decision={x['at'][:10]:x for x in book['decisions']}
 for sample in samples:
  pick=sample['selected'];sid=pick['sid'];c=next(c for c in campaigns[w]if c['campaign_id']==pick['campaign_id']);ids=set(c['layer_ids']);m=sm[sid]
  f=frame(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]);ip=RR/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet';ix=frame(ip,m['source_sha256'].get(str(ip)))
  entries=[]
  allsid_sells=[t for t in book['trades']if t['side']=='sell'and t['security_id']==sid]
  for lid in c['layer_ids']:
   x=byid[lid];r=rich[w][lid];t=buy[lid];dt=pd.Timestamp(x['decision_at'][:10]);ff=f.loc[dt];ii=ix.loc[dt];g=float(ff.g_grade)
   assert g==x['original_stock_state']['g_grade'];assert bool(ff.g_ready)==bool(x['original_stock_state']['g_ready']);assert norm(t['signal_at'])==norm(x['decision_at']);assert norm(t['at'])==norm(x['opened'])
   prev=max(d['at']for d in daily if norm(d['at'])<norm(t['at']));assert norm(prev)==norm(x['decision_at']),(sid,lid,prev,x['decision_at'])
   prior=[];current_root=book['metadata'].get(str(lid),{}).get('stock_structure')
   for s in allsid_sells:
    if norm(s['at'])>=norm(x['decision_at']):continue
    parts=[]
    for p in s['parts']:
     if booklayers[p['layer']]['kind']!='add':continue
     bindings=[z for z in rich[w][p['layer']]['actual_sale_parts']if norm(z['at'])==norm(s['at'])and z['shares']==p['shares']and D(z['net_cash'])==D(p['net_cash'])and z['reason']==p['reason']]
     assert len(bindings)==1
     oldroot=book['metadata'].get(str(p['layer']),{}).get('stock_structure')
     parts.append(dict(**p,original_stock_structure=oldroot,actual_execution_order_created_at=bindings[0]['order_created_at'],same_as_current_root=(current_root is not None and oldroot==current_root)))
    if parts:prior.append(dict(at=s['at'],receipt_id=s['receipt_id'],reason=s.get('reason'),parts=parts))
   same_root_prior=[dict(s,parts=[p for p in s['parts']if p['same_as_current_root']])for s in prior if any(p['same_as_current_root']for p in s['parts'])]
   mainparts=[]
   for s in allsid_sells:
    pp=[p for p in s['parts']if p['layer']==lid]
    if not pp:continue
    for p in pp:
     q=D(p['shares']);allocated_fee=D(s['price'])*q-D(p['net_cash'])
     bindings=[z for z in r['actual_sale_parts']if norm(z['at'])==norm(s['at'])and z['shares']==p['shares']and D(z['net_cash'])==D(p['net_cash'])and z['reason']==p['reason']]
     assert len(bindings)==1
     mainparts.append(dict(at=s['at'],order_created_at=bindings[0]['order_created_at'],order_clock_source='sealed actual_sale_parts matched by layer+actualfill+shares+net_cash+partreason; not earliest same-reason pilot',receipt_id=s['receipt_id'],part=p,proxy_price=s['price'],raw_open=s.get('raw_open'),allocated_sell_fee=allocated_fee,execution_basis=s.get('execution_basis'),whole_order_fee=s['fees_cny'],whole_order_shares=s['shares']))
   assert D(t['gross_cny'])+D(t['fees_cny'])==D(r['cost']);assert len(mainparts)==len(r['actual_sale_parts']);assert sum((D(p['part']['net_cash'])for p in mainparts),Z)-D(r['cost'])==D(r['strict_realized'])
   dday=x['decision_at'][:10]
   row=dict(layer=lid,role=x['role'],decision_at=x['decision_at'],actual_buy=t,actual_layer_record=booklayers[lid],actual_layer_metadata=book['metadata'].get(str(lid)),actual_layer_accounting=r,original_entry_context=x,original_IX_at_decision=ii.to_dict(),grade=g,grade_bucket=gradebucket(g),cold_mobile=(x['role']=='mobile'and g<2),prior_actual_MOBILE_sell_before_decision=prior,prior_mobile_sell_memory_condition=bool(prior),cold_and_prior_mobile_sell_condition=(x['role']=='mobile'and g<2 and bool(prior)),actual_sale_parts_with_price_fee=mainparts,original_opportunities=[z for z in logs['opportunities']if z['sid']==sid and z['day']==dday],original_funding=[z for z in logs['funding']if z['sid']==sid and z['at'][:10]==dday],original_rank=[z for z in logs['rank-policy']if z['sid']==sid and z['day']==dday])
   row.update(original_stock_structure=current_root,prior_same_root_MOBILE_sells=same_root_prior,prior_same_root_MOBILE_sell_condition=bool(same_root_prior),cold_and_prior_same_root_MOBILE_sell_condition=(x['role']=='mobile'and g<2 and bool(same_root_prior)),memory_scope_note='prior_mobile_sell_memory_condition is any same-stock actual MOBILE sell in the continuous original book before decision; same-root is separate and not the primary all-history memory scope')
   entries.append(row);checks['entry_original_facts_clock_quantity_cash_sale_parts_exact']+=1
   entrytable.append(dict(control=sample['control'],window=w,campaign_id=c['campaign_id'],sid=sid,name=c['name'],layer=lid,role=x['role'],grade=g,grade_bucket=gradebucket(g),cold_mobile=row['cold_mobile'],prior_mobile_sell_memory_condition=bool(prior),cold_and_prior_mobile_sell_condition=row['cold_and_prior_mobile_sell_condition'],original_stock_structure=current_root,prior_same_root_MOBILE_sell_condition=bool(same_root_prior),cold_and_prior_same_root_MOBILE_sell_condition=row['cold_and_prior_same_root_MOBILE_sell_condition'],decision_at=x['decision_at'],actual_buy_at=t['at'],quantity=t['shares'],buy_proxy_price=t['price'],buy_gross=t['gross_cny'],buy_fee=t['fees_cny'],cost=r['cost'],strict_realized=r['strict_realized'],AR=r['AR'],open_unrealized=r['open_unrealized'],net=r['net'],actual_sale_parts=mainparts))
  assert all(rich[w][l]['closed']is not None for l in ids);assert sum((D(rich[w][l]['net'])for l in ids),Z)==D(c['endpoint_net'])
  assert sum((D(rich[w][l]['strict_realized'])for l in ids),Z)==D(c['strict_realized'])
  first=min(byid[l]['decision_at'][:10]for l in ids);last=c['closed'][:10];obs=[]
  for d in daily:
   day=d['at'][:10]
   if not first<=day<=last:continue
   dt=pd.Timestamp(day);ff=f.loc[dt]if dt in f.index else None;ii=ix.loc[dt]if dt in ix.index else None
   live=[h for h in d['layers']if h['sid']==sid]
   sells=[s for s in allsid_sells if s['at'][:10]==day and any(p['layer']in ids for p in s['parts'])]
   buys=[buy[l]for l in ids if buy[l]['at'][:10]==day]
   relevant_audit=[a for a in book['audit']if a.get('sid')==sid and a.get('at','')[:10]==day]
   obs.append(dict(day=day,clock=d['at'],ACT_on=d['on'],account_NAV=d['nav'],available=d['available'],stock_fact=None if ff is None else {k:ff[k]for k in ['close','raw_close','factor','segment_id','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready']if k in ff},IX=None if ii is None else {k:ii[k]for k in ['grade','ready','fresh_up','up_reasons','e0_entered','ix_entered','ix_exited','phase']if k in ii},actual_live_same_stock_layers=live,actual_buys=buys,actual_sells=sells,original_pending_sells=[p for p in d['pending_sells']if(p if isinstance(p,str)else p.get('sid',p.get('security_id')))==sid],original_intents=[z for z in decision.get(day,{}).get('intents',[])if z['sid']==sid],original_opportunities=[z for z in logs['opportunities']if z['sid']==sid and z['day']==day],original_funding=[z for z in logs['funding']if z['sid']==sid and z['at'][:10]==day],original_sid_audit=relevant_audit))
  allstockcampaigns=[z for z in campaigns[w]if z['sid']==sid]
  payload=dict(control=sample['control'],campaign=c,cold_layer_net=sum((D(x['actual_layer_accounting']['net'])for x in entries if x['cold_mobile']),Z),warm_or_other_layer_net=sum((D(x['actual_layer_accounting']['net'])for x in entries if not x['cold_mobile']),Z),all_completed=True,open_mark=Z,entry_grade_buckets=dict(Counter(x['grade_bucket']for x in entries)),entries=entries,daily_original_chain=obs,same_stock_all_original_campaign_summaries=allstockcampaigns,same_stock_all_original_actual_trades=[t for t in book['trades']if t['security_id']==sid],scope='Original fixed realized campaign with complete same-stock book history attached. Proxy execution prices/fees are original simulator records, not real exchange fills. No new position/exit/payoff is computed. Negative/0/1 grade is an input observation; endpoint outcomes only select/describe examples. Cold layer contribution is separate from total campaign contribution. Prior MOBILE sell condition is descriptive, not an implemented gate or account counterfactual.')
  out.append(payload);save(f'{w}_{sid.replace(".","_")}_'+('WARM_CONTROL'if sample['control']else'COLD_CHAIN')+'.json',payload)
  checks['complete_campaign_all_layers_cash_matches']+=1
  print('EXTRACTED',w,sid,len(entries),len(obs),flush=True)
save('FOUR_COLD_CHAINS_AND_WARM_CONTROL.json',out)
save('ENTRY_LAYER_TABLE.json',entrytable)
with (O/'ENTRY_LAYER_TABLE.csv').open('w',newline='')as f:
 fields=[k for k in entrytable[0]if k!='actual_sale_parts'];cw=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');cw.writeheader();cw.writerows(entrytable)
save('VALIDATION.json',dict(status='PASS_STATIC_ORIGINAL_CHAIN_EXTRACTION',checks=checks,primary_cold_chains=4,separate_warm_control=1,source_grade_clock='Actual fill preceding original native market CLOSE equals original decision CLOSE, no extra lag',new_accounts=0,model_runs=0,no_accounting_engine=True,all_five_campaigns_closed=True,sources_hashed_before_read=True,not_a_gate_effect_or_counterfactual=True))
save('SOURCE_MANIFEST.json',dict(source_sha256=SRC,script_sha256=sha(__file__),new_accounts=0,source_strategy_code_read_only=True,no_model_imports=True))
save('DELIVERABLE_SHA256.json',{p.name:sha(p)for p in O.iterdir()if p.is_file()and p.name not in ['DELIVERABLE_SHA256.json','run.log','run.err']})
