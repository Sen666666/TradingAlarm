"""Entry-time cached source flags only. No algorithm or account imports/replay."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import json,hashlib,datetime,csv,math
import pandas as pd
getcontext().prec=70
OUT=Path(__file__).resolve().parent;ENTRY=OUT.parent;ROOT=ENTRY.parents[1];COMP=ROOT/'account_comparison/results_v1'
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
CAT=['A_ONLY_EXISTING_S21_FRONTIER','B_E0_ENTERED_OR_NEW_S_UP_CONFIRMATION','C_OTHER_KNOWN_NEW_SOURCE','D_NO_CURRENT_NEW_SOURCE','UNKNOWN']
FRONT='new_price_frontier_in_confirmed_up_structure';SCONF={'new_S21_up_confirmation','new_S63_up_confirmation'}
SOURCES={};FRAMES={};ERRORS={};REQ=defaultdict(set);flat=[]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p,expected=None):
 p=Path(p);h=sha(p)
 if expected:assert h==expected,(str(p),'source hash mismatch')
 SOURCES[str(p)]=h;return json.loads(p.read_text())
def write(n,x):(OUT/n).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
protocol=read(OUT/'PROTOCOL.json')
ixman={r['symbol']:r for r in read(RR/'ix-a-share-entry-20261025/signals/manifest.json')['series']}
nman={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
books={};fixed={}
for w in ['2022_2024','strong']:
 books[w]=read(COMP/f'JOINT_{w}_LAYERS.json');fixed[w]=read(COMP/f'JOINT_{w}_FIXED83_94_TAILS.json')
 for r in books[w]:REQ[r['sid']].add(r['decision_at'][:10])
 for t in fixed[w]['rows']:
  r=t['original_fixed_member'];REQ[r['sid']].add(r['decision_at'][:10])
for sid,days in REQ.items():
 try:
  xp=RR/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet';np=Path(nman[sid]['refs']['facts'])
  assert sha(xp)==ixman[sid]['output_sha256'];assert sha(np)==nman[sid]['output_sha256'][str(np)]
  SOURCES[str(xp)]=sha(xp);SOURCES[str(np)]=sha(np)
  x=pd.read_parquet(xp,columns=['close','segment_id','e0_entered','fresh_up','up_reasons','strength_ready','grade'])
  n=pd.read_parquet(np,columns=['close','segment_id','i_target','i_buy','e0_target','g_fresh_up'])
  idx=pd.DatetimeIndex(sorted(days));FRAMES[sid]=(x.reindex(idx),n.reindex(idx))
 except Exception as e:ERRORS[sid]=type(e).__name__+':'+str(e)

def source(r):
 sid=r['sid'];day=r['decision_at'][:10];unknown=[]
 q=dict(sid=sid,entry_day=day,source_class='UNKNOWN',native_i_buy=None,source_unknown=unknown,
        source_is_current_observation_not_new_I_structure=True)
 if sid not in FRAMES:unknown.append('direct_cache_unavailable:'+ERRORS.get(sid,'unknown'));return q
 x,n=FRAMES[sid];x=x.loc[pd.Timestamp(day)];n=n.loc[pd.Timestamp(day)]
 required=[x.close,x.segment_id,x.e0_entered,x.fresh_up,x.strength_ready,x.grade,n.close,n.segment_id,n.i_target,n.i_buy,n.e0_target,n.g_fresh_up]
 if any(pd.isna(v) for v in required) or pd.isna(x.up_reasons):unknown.append('missing_or_unready_direct_cache_fields');return q
 if not bool(x.strength_ready):unknown.append('G1_source_unready');return q
 if float(x.segment_id)!=float(n.segment_id) or float(x.close)!=float(n.close):unknown.append('native_and_IX_price_source_disagree');return q
 reasons=[s for s in str(x.up_reasons).split('|') if s]
 if len(reasons)!=len(set(reasons)):unknown.append('duplicate_saved_reason');return q
 if bool(x.fresh_up)!=bool(reasons) or bool(x.fresh_up)!=bool(n.g_fresh_up):unknown.append('saved_fresh_up_and_reasons_disagree');return q
 formula=bool(n.i_target) and bool(n.e0_target) and bool(x.strength_ready) and float(x.grade)>=2 and (bool(x.e0_entered) or bool(x.fresh_up))
 if formula!=bool(n.i_buy):unknown.append('native_i_buy_cached_boolean_formula_disagree');return q
 if bool(x.e0_entered) or set(reasons)&SCONF:c=CAT[1]
 elif set(reasons)=={FRONT}:c=CAT[0]
 elif reasons:c=CAT[2]
 else:c=CAT[3]
 q.update(source_class=c,native_i_buy=bool(n.i_buy),native_I_target=bool(n.i_target),native_E0_target=bool(n.e0_target),
          original_E0_entered=bool(x.e0_entered),G1_fresh_up=bool(x.fresh_up),G1_up_reasons=reasons,G1_grade=float(x.grade),
          close=float(x.close),source_segment=int(x.segment_id))
 return q

def attach(r,kind,w):
 q=source(r)
 return dict(window=w,mother=kind,key=r.get('key'),layer=r.get('layer_in_this_book',r.get('layer')),sid=r['sid'],role=r['role'],
             actual_entry_action=r.get('actual_entry_action','original_fixed_member_not_JOINT_action'),decision_at=r['decision_at'],
             cost=r['cost'],net=r['net'],strict_realized=r.get('strict_realized'),open_unrealized=r.get('open_unrealized'),AR=r.get('AR'),
             cached_source=q,source_class=q['source_class'],native_i_buy=q['native_i_buy'],source_unknown=q['source_unknown'])

def money(rs,field):
 vals=[D(r[field]) for r in rs]
 return dict(layers=len(rs),stocks=len({r['sid'] for r in rs}),cost=str(sum((D(r['cost']) for r in rs),D(0))),
  negative=str(sum((v for v in vals if v<0),D(0))),positive=str(sum((v for v in vals if v>0),D(0))),net=str(sum(vals,D(0))),unknown=sum(bool(r['source_unknown']) for r in rs))

def table(rs,label,field='net'):
 denom=money(rs,field);out={}
 for c in CAT:
  group=[r for r in rs if r['source_class']==c];v=money(group,field)
  v['source_unknown_reasons']=dict(Counter(u for r in group for u in r['source_unknown']))
  v['native_i_buy_true']=sum(r['native_i_buy'] is True for r in group);v['native_i_buy_false']=sum(r['native_i_buy'] is False for r in group)
  v['fraction_of_mother_negative_pct']=str(100*D(v['negative'])/D(denom['negative'])) if D(denom['negative']) else None
  v['fraction_of_mother_positive_pct']=str(100*D(v['positive'])/D(denom['positive'])) if D(denom['positive']) else None
  v['by_native_i_buy']={k:money([r for r in group if r['native_i_buy'] is val],field) for k,val in [('true',True),('false',False),('unknown',None)]}
  out[c]=v;flat.append(dict(group=label,source_class=c,metric=field,**{k:v[k] for k in ['layers','stocks','cost','negative','positive','net','unknown','native_i_buy_true','native_i_buy_false','fraction_of_mother_negative_pct','fraction_of_mother_positive_pct']}))
 assert sum(v['layers'] for v in out.values())==denom['layers']
 assert sum((D(v['net']) for v in out.values()),D(0))==D(denom['net'])
 return dict(evaluation_metric=field,mother=denom,classes=out,not_filter_or_policy_profit=True)

def groups(rs,label,field='net'):
 out={'ALL':table(rs,label+'|ALL',field)}
 for action in ['first','add','reentry']:
  out['action='+action]=table([r for r in rs if r['actual_entry_action']==action],label+'|action='+action,field)
 for role in ['core','mobile']:
  out['role='+role]=table([r for r in rs if r['role']==role],label+'|role='+role,field)
  for action in ['first','add','reentry']:
   out['role='+role+'|action='+action]=table([r for r in rs if r['role']==role and r['actual_entry_action']==action],label+'|role='+role+'|action='+action,field)
 return out

summary={};rows={};tail_rows={};tails={}
for w,raw in books.items():
 a=[attach(r,'JOINT_actual_entry',w) for r in raw];rows[w]=a;summary[w]=groups(a,w)
 summary[w]['positive_endpoint_labels']=table([r for r in a if D(r['net'])>0],w+'|positive_endpoint')
 summary[w]['negative_endpoint_labels']=table([r for r in a if D(r['net'])<0],w+'|negative_endpoint')
 if w=='2022_2024':
  dec=read(COMP/'JOINT_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json');dd={r['key']:r for r in dec if r['cohort'].startswith('Dec_new')}
  decrows=[]
  for r in a:
   if r['key'] in dd:q=dict(r);q['Dec_wealth']=dd[r['key']]['Dec_components']['wealth'];decrows.append(q)
  assert len(decrows)==135;summary['Dec_new135']=groups(decrows,'Dec_new135','Dec_wealth');write('DEC135_SOURCE_ROWS.json',decrows)
 else:
  win=[r for r in a if D(r['cost'])>0 and D(r['net'])/D(r['cost'])>=D('.30')]
  assert len(win)==122;summary['strong_own_endpoint_ge30pct']=groups(win,'strong_own_endpoint_ge30pct')
  write('STRONG_OWN122_GE30_SOURCE_ROWS.json',win)
 original=[];joint_exact=[];base_exact_orig=[];ts=[]
 amap={r['key']:r for r in a}
 for t in fixed[w]['rows']:
  orig=attach(t['original_fixed_member'],'original_frozen_tail_member',w);orig['key']=t['entry_key'];original.append(orig)
  if t.get('baseline_current_exact_match') is not None:base_exact_orig.append(orig)
  q=amap.get(t['entry_key'])
  if q is not None:
   assert q['source_class']==orig['source_class'];joint_exact.append(q)
  ts.append(dict(original=orig,original_status=t['status'],BASELINE_exact_entry_present=t.get('baseline_current_exact_match') is not None,
     JOINT_exact_entry=q,absent_JOINT_exact_entry_is_not_unknown_source_or_no_stock_holding=True))
 stocks={r['sid'] for r in original}
 tails[w]=dict(full_original_fixed_members=table(original,w+'|fixed_original_full'),
  BASELINE_45_or67_matched_original_members=table(base_exact_orig,w+'|BASELINE_matched_original'),
  JOINT_46_or54_exact_actual_entries=table(joint_exact,w+'|JOINT_exact_tail_entries'),
  all_JOINT_actual_entries_in_original_fixed_stocks=groups([r for r in a if r['sid'] in stocks],w+'|all_entry_fixed_stocks'))
 tail_rows[w]=ts
 write(w+'_ACTUAL_ENTRY_SOURCE_ROWS.json',a)
write('COVERAGE_SUMMARY.json',summary);write('FIXED83_94_COVERAGE.json',tails);write('FIXED83_94_ALL_MEMBER_SOURCE_ROWS.json',tail_rows)
with (OUT/'COVERAGE_TABLE.csv').open('w',newline='') as f:
 wr=csv.DictWriter(f,fieldnames=list(flat[0]));wr.writeheader();wr.writerows(flat)
validation=dict(status='PASS_DIRECT_CACHE_SOURCE_COVERAGE',cached_stock_series_read=len(FRAMES),requested_stock_series=len(REQ),direct_cache_errors=ERRORS,
 actual_entry_rows=sum(len(a) for a in rows.values()),actual_entry_unknown=sum(bool(r['source_unknown']) for a in rows.values() for r in a),
 original_fixed_members=sum(len(a) for a in tail_rows.values()),original_fixed_unknown=sum(bool(t['original']['source_unknown']) for a in tail_rows.values() for t in a),
 original_models_replayed=0,new_accounts=0,new_trade_rules=0,
 protected_files_unchanged=all(sha(ENTRY/n)==h for n,h in protocol['protected_original_files'].items()),
 closure_checks='All class counts and Decimal net sums exactly reconcile each mother; all known flags satisfy native i_buy cached boolean formula; source price/segment equal IX/native.',
 source_class_is_not_new_I_structure=True,winner_or_negative_sign_used_only_for_evaluation=True)
assert validation['protected_files_unchanged'];assert validation['actual_entry_rows']==3795
write('VALIDATION.json',validation)
write('SOURCE_MANIFEST.json',dict(status=validation['status'],at=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_sha256=SOURCES,
 deliverables={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='SOURCE_MANIFEST.json'},new_accounts=0,original_models_replayed=0))
main={}
for k in ['2022_2024','strong','Dec_new135','strong_own_endpoint_ge30pct']:
 x=summary[k]['ALL'];main[k]=dict(mother=x['mother'],classes={c:{s:v[s] for s in ['layers','negative','positive','net','unknown','native_i_buy_true','native_i_buy_false']} for c,v in x['classes'].items()})
print(json.dumps(dict(validation=validation,main=main),ensure_ascii=False))
