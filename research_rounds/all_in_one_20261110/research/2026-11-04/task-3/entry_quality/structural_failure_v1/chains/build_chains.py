"""Read-only original No60 complete-cycle forensic chains. No model/account calls."""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal as D
import gzip, json, hashlib, bisect, math, sys
import pandas as pd

sys.dont_write_bytecode = True
O=Path(__file__).resolve().parent
Q=O.parents[1]
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
SRC={}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,gz=False,lines=False):
 p=Path(p); SRC[str(p)]=sha(p)
 with (gzip.open(p,'rt') if gz else p.open()) as f: return [json.loads(x) for x in f] if lines else json.load(f)
def frame(p,expected=None):
 p=Path(p);h=sha(p); assert expected is None or h==expected;SRC[str(p)]=h;return pd.read_parquet(p)
def clean(v):
 if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
 if isinstance(v,(tuple,list)):return [clean(x) for x in v]
 if isinstance(v,(pd.Timestamp, D)):return str(v)
 if hasattr(v,'item'):v=v.item()
 if isinstance(v,float) and not math.isfinite(v):return None
 return v
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def scalarrow(r):return clean(r.to_dict())
def zsum(it):return sum((D(str(x)) for x in it),D(0))

cp=Q/'structural_failure_v1/accounting/results_v2/2022_2024_CAMPAIGNS_FULL_ACCOUNTING.json'
allc=read(cp);ordered=sorted(allc,key=lambda c:(D(c['endpoint_net']),c['campaign_id']))
selected=[]
def take(c,why,control=False):
 if any(x['campaign']['campaign_id']==c['campaign_id'] for x in selected):return
 selected.append(dict(selection=why,control=control,campaign=c))
for i,c in enumerate(ordered[:5],1):take(c,f'full_stock_cycle_endpoint_net_rank_{i}')
take(min(allc,key=lambda c:D(c['stage_wealth']['P03_Dec2022']['wealth'])),'worst_Dec2022_stage_wealth_in_complete_cycle')
take(min((c for c in allc if c['opened'][:7]=='2022-12'),key=lambda c:D(c['endpoint_net'])),'worst_Dec2022_new_cycle_endpoint_net')
take(min((c for c in allc if c['opened'][:10]<='2024-10-08'),key=lambda c:D(c['stage_wealth']['P10_after2024Oct8']['wealth'])),'worst_afterOct8_old_cycle_stage_wealth')
take(min((c for c in allc if c['ACT_exit_part_count']),key=lambda c:D(c['endpoint_net'])),'worst_ACT_affected_cycle_endpoint_net')
take(max(allc,key=lambda c:D(c['endpoint_net'])),'largest_positive_complete_cycle_control',True)
assert len(selected)==10
controls=[]
for sid,day,why in [('601595.SH','2023-03-13','2023_repair_multilayer_winner'),('002583.SZ','2024-10-15','postOct8_fresh_start_winner'),('002317.SZ','2022-10-14','Dec2022_old_profitable_giveback_control')]:
 c=next(c for c in allc if c['sid']==sid and c['opened'][:10]==day)
 controls.append(dict(selection=why,control=True,campaign=c))
save('SELECTION_FREEZE.json',dict(selection_clock='descriptive sampling of original realized campaigns and fixed stage wealth; never an input signal',primary=selected,attached_controls=controls,main_cycles=10,account_new_runs=0))

sm={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
im={x['series']:x for x in read(W/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
base=Q/'trend_exit_controls_v1/runs/BASELINE/2022_2024/pair'
book=read(base/'B.json.gz',True); daily=read(base/'daily.jsonl.gz',True,True)
entry={x['layer']:x for x in read(Q/'structural_failure_v1/state_semantics/2022_2024_ROWS.json')}
scales={x['layer']:x for x in read(Q/'entry_exit_scale/mechanism_review/2022_2024_ACTUAL_ENTRY_SCALE_JOIN.json')}
rich={x['layer_in_this_book']:x for x in read(Q/'dec2022_authorization_v1/account_comparison/results_v1/BASELINE_2022_2024_LAYERS.json')}
valid=read(Q/'dec2022_authorization_v1/account_comparison/results_v1/VALIDATION.json')
partial=valid['native_daily_mark_wealth_and_partial_basis']['BASELINE|2022_2024']['partial_basis_state_points']
sids={x['campaign']['sid'] for x in selected+controls}
logs={}
for fn in ['opportunities','funding','rank-policy','industry']:
 rows=read(base/(fn+'.jsonl.gz'),True,True)
 logs[fn]=rows if fn=='industry' else [x for x in rows if x.get('sid') in sids]
decision_byday={x['at'][:10]:x for x in book['decisions']}
buy={x['layer']:x for x in book['trades'] if x['side']=='buy'}
fact={};ixs={};events={};bars={};industries={}
for sid in sids:
 m=sm[sid];fact[sid]=frame(m['refs']['facts'],m['output_sha256'][m['refs']['facts']]);ip=RR/'ix-a-share-entry-20261025/signals'/(sid+'.parquet');ixs[sid]=frame(ip,m['source_sha256'][str(ip)])
 ep=next(p for p in m['source_sha256'] if p.endswith('/events.parquet'));events[sid]=frame(ep,m['source_sha256'][ep])
 sp=next(p for p in m['source_sha256'] if p.endswith('/signal.parquet'));bars[sid]=frame(sp,m['source_sha256'][sp])
for x in selected+controls:
 sector=x['campaign']['sector']
 if sector not in industries:
  m=im[sector];f=frame(m['refs']['state'],m['output_sha256'][m['refs']['state']]);f['day']=f.day.astype(str).str[:10];industries[sector]=f.set_index('day',drop=False)
def asof(df,day):
 j=df.index.searchsorted(pd.Timestamp(day),side='right')-1
 return (None,None) if j<0 else (str(df.index[j].date()),df.iloc[j])
def same(log,sid,day):return [x for x in logs[log] if x.get('sid')==sid and x.get('day',x.get('at',''))[:10]==day]
def live_state(d,ids,sid,day):
 fd,ff=asof(fact[sid],day);rr=[]
 for h in d['layers']:
  if h['id'] not in ids:continue
  ps=partial.get(str(h['id']),[]);j=bisect.bisect_right([x['at'] for x in ps],d['at'])-1
  basis=D(ps[j]['basis']) if j>=0 else D(rich[h['id']]['cost'])
  mark=D(str(ff.raw_close))*D(h['qty']);rr.append(dict(snapshot=h,basis=basis,mark=mark,held_unreal=mark-basis,known_quote_day=fd,raw_close=ff.raw_close))
 return rr

chains=[];triggers=[]
for sample in selected+controls:
 c=sample['campaign'];sid=c['sid'];ids=set(c['layer_ids']);sector=c['sector'];f=fact[sid];ix=ixs[sid];ev=events[sid]
 first_dec=min(rich[lid]['decision_at'] for lid in ids)[:10];opened=c['opened'][:10];closed=c['closed'][:10]
 observations=[];previous={}
 for d in daily:
  day=d['at'][:10]
  if not first_dec<=day<=closed:continue
  fd,ff=asof(f,day);id_,ii=asof(ix,day);bd,bb=asof(bars[sid],day);e=ev.loc[pd.Timestamp(day)] if pd.Timestamp(day) in ev.index else None
  sf=industries[sector];ss=sf.loc[day] if day in sf.index else None
  live=live_state(d,ids,sid,day)
  all_sid=[h for h in d['layers'] if h['sid']==sid]
  decision=decision_byday.get(day);intents=[] if decision is None else [x for x in decision['intents'] if x['sid']==sid]
  fields=['close','raw_close','factor','segment_id','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready']
  ixf=['e0_entered','e0_exited','ix_entered','ix_exited','phase','up_reasons','z5','z21','e0_age']
  holds_before_new_decision=[h['id'] for h in all_sid if h['opened'][:10]<=day and h['kind']=='core']
  pend=[x for x in d['pending_sells'] if (x if isinstance(x,str) else x.get('sid',x.get('security_id')))==sid]
  sold=[t for t in book['trades'] if t['side']=='sell' and t['security_id']==sid and t['at'][:10]==day and any(p['layer'] in ids for p in t['parts'])]
  o=dict(day=day,clock=d['at'],original_ACT_on=d['on'],account_NAV=d['nav'],available=d['available'],original_snapshot_after_CLOSE_checks=True,
   fact_source_day=fd,stock={k:ff[k] for k in fields if k in ff},raw_price_volume_source_day=bd,original_raw_and_adjusted_bar=scalarrow(bb),IX_source_day=id_,IX={k:ii[k] for k in ixf if k in ii},native_event=None if e is None else scalarrow(e),industry=None if ss is None else scalarrow(ss),
   actual_live_layers=live,prior_observed_original_protection=previous,core_actually_funded_and_held_before_new_CLOSE_decision=holds_before_new_decision,
   original_pending_sells=pend,original_intents=intents,original_rank_policy=same('rank-policy',sid,day),original_opportunities=same('opportunities',sid,day),original_funding=same('funding',sid,day),
   actual_buys=[t for lid,t in buy.items() if lid in ids and t['at'][:10]==day],actual_sells=sold,
   held_basis=zsum(x['basis'] for x in live),held_mark=zsum(x['mark'] for x in live),held_unreal=zsum(x['held_unreal'] for x in live),
   decision_clock_new_intent_not_yet_filled=True)
  observations.append(o);previous={str(h['snapshot']['id']):dict(floor=h['snapshot']['floor'],last_core_line=h['snapshot'].get('last_core_line'),snapshot_day=day) for h in live}
 neg=[o for o in observations if opened<=o['day']<closed and o['native_event'] is not None and o['native_event'].get('event')==-1]
 t=neg[0] if neg else None
 trigger=dict(campaign_id=c['campaign_id'],sid=sid,layer_ids=c['layer_ids'],selection=sample['selection'],first_negative_native_event_after_actual_first_fill=None if t is None else t['day'],
  trigger_event_source=next(p for p in sm[sid]['source_sha256'] if p.endswith('/events.parquet')),trigger_column='event == -1',trigger_known_clock=None if t is None else t['clock'],event_is_not_E0_target_off=True,
  T_inventory_layer_ids=[] if t is None else [x['snapshot']['id'] for x in t['actual_live_layers']],T_pending_sells=[] if t is None else t['original_pending_sells'],
  later_original_mobile_contracts=[] if t is None else [dict(layer=lid,decision_at=rich[lid]['decision_at'],opened=rich[lid]['opened'],cost=rich[lid]['cost'],endpoint_net=rich[lid]['net'],actual_sale_parts=rich[lid]['actual_sale_parts']) for lid in c['layer_ids'] if rich[lid]['role']=='mobile' and rich[lid]['decision_at'][:10]>t['day']],
  scope='descriptive local diagnostic, not a proposed policy; outcome-dependent campaign end only evaluation horizon')
 entries=[]
 for lid in c['layer_ids']:
  r=rich[lid];es=entry[lid]
  entries.append(dict(layer=lid,actual_buy=buy[lid],actual_layer_accounting=r,original_signal_and_authorization=es,original_CP_and_scale_proof=scales[lid]))
 chains.append(dict(selection=sample['selection'],attached_control=sample in controls,campaign=c,entries=entries,observations=observations,local_diagnostic_trigger=trigger));triggers.append(trigger)
save('COMPLETE_ORIGINAL_CHAINS.json',chains);save('LOCAL_DIAGNOSTIC_TRIGGERS.json',triggers)
save('PRIMARY_TEN_COMPACT.json',[dict(selection=x['selection'],**{k:x['campaign'][k] for k in ['campaign_id','sid','name','industry','opened','closed','layer_ids','by_role','by_action','actual_buycash','endpoint_net','actual_fees','stage_wealth']},trigger=x['local_diagnostic_trigger']) for x in chains[:10]])
selectedids={lid for x in selected for lid in x['campaign']['layer_ids']}
totalneg=zsum(min(D(c['endpoint_net']),D(0)) for c in allc);selneg=zsum(min(D(x['campaign']['endpoint_net']),D(0)) for x in selected)
save('VALIDATION.json',dict(status='PASS_READONLY_FORENSIC_EXTRACTION',primary_cycles=10,attached_controls=3,primary_layers=len(selectedids),primary_negative_cycle_net=selneg,all_1677_cycle_negative_net=totalneg,selected_negative_share=selneg/totalneg,
 all_selected_layers_have_original_actual_fills=len(selectedids&buy.keys())==len(selectedids),all_entry_state_join_exact=set(selectedids)<=entry.keys(),model_replays=0,new_accounts=0,new_rules=0,
 caveat='selection uses realized results only to choose representative forensic examples; all candidate observations are as-of CLOSE. No diagnostic local payoff yet. Previous guard and post-CLOSE ratchet are separately labeled. Held unreal includes actual fee-aware remaining basis, no hypothetical peak sale.'))
save('SOURCE_MANIFEST.json',dict(source_sha256=SRC,script_sha256=sha(__file__),write_scope=str(O),original_files_changed=False))
print(json.dumps(dict(primary_cycles=10,controls=3,primary_layers=len(selectedids),trigger_days=[(x['sid'],x['first_negative_native_event_after_actual_first_fill']) for x in triggers],selected_negative_share=str(selneg/totalneg)),ensure_ascii=False))
