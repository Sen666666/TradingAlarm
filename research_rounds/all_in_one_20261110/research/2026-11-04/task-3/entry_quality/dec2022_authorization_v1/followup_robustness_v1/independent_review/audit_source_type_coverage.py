"""Independent cached Boolean source description; no model/account imports."""
from pathlib import Path
from collections import defaultdict,Counter
from decimal import Decimal as D,getcontext
import json,hashlib
import pandas as pd
getcontext().prec=70
HERE=Path(__file__).resolve().parent;F=HERE.parent;P=F/'entry_mechanism/I_BUY_SOURCE_COVERAGE';H=F.parent;C=H/'account_comparison/results_v1'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');SRC={};Z=D(0);TOL=D('1e-6')
A='A_ONLY_EXISTING_S21_FRONTIER';B='B_E0_ENTERED_OR_NEW_S_UP_CONFIRMATION';CC='C_OTHER_KNOWN_NEW_SOURCE';DD='D_NO_CURRENT_NEW_SOURCE';U='UNKNOWN';CATS=[A,B,CC,DD,U]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p.resolve())]=sha(p);return json.loads(p.read_text())
def eq(a,b,why):assert abs(D(str(a))-D(str(b)))<TOL,(why,str(a),str(b))
def category(e0_entered,reasons):
 """Financial outcome, role, action and future labels are not arguments."""
 reasonset=frozenset(reasons)
 if e0_entered or bool(reasonset.intersection({'new_S21_up_confirmation','new_S63_up_confirmation'})):return B
 if reasonset==frozenset(['new_price_frontier_in_confirmed_up_structure']):return A
 return CC if reasonset else DD
def money(rr,metric):
 vv=[D(x[metric]) for x in rr]
 return dict(layers=len(rr),stocks=len({x['sid'] for x in rr}),cost=sum((D(x['cost']) for x in rr),Z),negative=sum((v for v in vv if v<0),Z),positive=sum((v for v in vv if v>0),Z),net=sum(vv,Z),unknown=0)
TABLES=0;CLASS_GROUPS=0
def verify_table(rr,t):
 global TABLES,CLASS_GROUPS
 metric=t['evaluation_metric'];base=money(rr,metric)
 for k,v in base.items():eq(v,t['mother'][k],'mother '+k)
 assert set(t['classes'])==set(CATS)
 for cat in CATS:
  gg=[r for r in rr if r['_class']==cat];g=t['classes'][cat];mm=money(gg,metric)
  for k,v in mm.items():eq(v,g[k],'class '+cat+' '+k)
  assert g['source_unknown_reasons']=={};assert g['native_i_buy_true']==sum(r['_buy'] for r in gg);assert g['native_i_buy_false']==sum(not r['_buy'] for r in gg)
  for flag,val in [('true',True),('false',False),('unknown',None)]:
   ff=money([r for r in gg if r['_buy'] is val],metric)
   for k,v in ff.items():eq(v,g['by_native_i_buy'][flag][k],'flag '+flag+' '+k)
  for sign in ['negative','positive']:
   if not base[sign]:assert g['fraction_of_mother_'+sign+'_pct'] is None
   else:eq(100*mm[sign]/base[sign],g['fraction_of_mother_'+sign+'_pct'],'percentage '+sign)
  CLASS_GROUPS+=1
 assert t['not_filter_or_policy_profit'];TABLES+=1
def verify_groups(rr,groups):
 assert set(groups)=={'ALL','action=first','action=add','action=reentry','role=core','role=mobile','role=core|action=first','role=core|action=add','role=core|action=reentry','role=mobile|action=first','role=mobile|action=add','role=mobile|action=reentry'}
 for name,t in groups.items():
  selected=rr
  if name!='ALL':
   for clause in name.split('|'):
    field,value=clause.split('=');selected=[r for r in selected if r['role' if field=='role' else 'actual_entry_action']==value]
  verify_table(selected,t)

if __name__=='__main__':
 output=HERE/'SOURCE_TYPE_COVERAGE_AUDIT.json';assert not output.exists()
 report=dict(status='RUNNING',independent_classifier='B E0entry/Sconfirmation first, A exact singleton frontier otherwise; only cached current-observation primitives',original_models_replayed=0,new_accounts=0,new_account_events=0)
 try:
  manifest=read(P/'SOURCE_MANIFEST.json');bad=[]
  for p,h in manifest['source_sha256'].items():
   if sha(p)!=h:bad.append(p)
  for name,h in manifest['deliverables'].items():
   if sha(P/name)!=h:bad.append(str(P/name))
  assert not bad,('SOURCE_MANIFEST disagreement',bad)
  protocol=read(P/'PROTOCOL.json');protected={}
  for name,h in protocol['protected_original_files'].items():assert sha(P.parent/name)==h;protected[name]=h
  summary=read(P/'COVERAGE_SUMMARY.json');tails=read(P/'FIXED83_94_COVERAGE.json');validation=read(P/'VALIDATION.json')
  native_refs={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')};ixrefs={r['symbol']:r for r in read(R/'ix-a-share-entry-20261025/signals/manifest.json')['series']}
  # Check Boolean producer version against its original freeze, not the name.
  cachefreeze=read(W/'native-I-cache-interface-20261031/FREEZE.json')
  for p in [W/'native-I-cache-interface-20261031/cache.py',R/'b5-g1-20261025/code/policies_g1.py',R/'b5-g1-20261025/code/grade.py']:
   assert sha(p)==cachefreeze['source_sha'][str(p)];SRC[str(p)]=sha(p)
  originals={};fixed={};requested=defaultdict(set);lookup={};published={}
  for win in ['2022_2024','strong']:
   originals[win]=read(C/f'JOINT_{win}_LAYERS.json');fixed[win]=read(C/f'JOINT_{win}_FIXED83_94_TAILS.json');published[win]=read(P/f'{win}_ACTUAL_ENTRY_SOURCE_ROWS.json')
   for r in originals[win]:requested[r['sid']].add(r['decision_at'][:10])
   for t in fixed[win]['rows']:r=t['original_fixed_member'];requested[r['sid']].add(r['decision_at'][:10])
  formula_checks=0
  for sid,days in requested.items():
   xp=R/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet';np=Path(native_refs[sid]['refs']['facts']);assert sha(xp)==ixrefs[sid]['output_sha256'];assert sha(np)==native_refs[sid]['output_sha256'][str(np)];SRC[str(xp)]=sha(xp);SRC[str(np)]=sha(np)
   ix=pd.read_parquet(xp,columns=['close','segment_id','e0_entered','fresh_up','up_reasons','strength_ready','grade']);native=pd.read_parquet(np,columns=['close','segment_id','i_target','i_buy','e0_target','g_fresh_up','g_grade','g_ready'])
   for day in days:
    d=pd.Timestamp(day);x=ix.loc[d];n=native.loc[d]
    assert not pd.isna(x).any() and not pd.isna(n).any();assert x.strength_ready and n.g_ready
    assert x.close==n.close and x.segment_id==n.segment_id and x.grade==n.g_grade and x.strength_ready==n.g_ready
    reasons=tuple(r for r in str(x.up_reasons).split('|') if r);assert len(set(reasons))==len(reasons);assert bool(reasons)==bool(x.fresh_up)==bool(n.g_fresh_up)
    expected_buy=bool(n.i_target and n.e0_target and x.strength_ready and x.grade>=2 and (x.e0_entered or x.fresh_up));assert expected_buy==bool(n.i_buy)
    lookup[sid,day]=dict(cat=category(bool(x.e0_entered),reasons),buy=bool(n.i_buy),e0_entered=bool(x.e0_entered),fresh=bool(x.fresh_up),I=bool(n.i_target),E0=bool(n.e0_target),reasons=list(reasons),grade=float(x.grade),close=float(x.close),segment=int(x.segment_id));formula_checks+=1
  # Freeze every source classification before attaching/using any evaluation.
  def attach(r):
   q=lookup[r['sid'],r['decision_at'][:10]];z=dict(r);z['_class']=q['cat'];z['_buy']=q['buy'];return z
  def verify_source(r,pp):
   q=lookup[r['sid'],r['decision_at'][:10]];assert pp['source_class']==q['cat'];assert pp['native_i_buy']==q['buy'];assert pp['source_unknown']==[]
   cc=pp['cached_source'];assert cc['native_i_buy']==q['buy'] and cc['native_I_target']==q['I'] and cc['native_E0_target']==q['E0'] and cc['original_E0_entered']==q['e0_entered'] and cc['G1_fresh_up']==q['fresh'] and cc['G1_up_reasons']==q['reasons'] and cc['G1_grade']==q['grade'] and cc['close']==q['close'] and cc['source_segment']==q['segment']
  populations={};class_counts={};dec=[];winners=[];tail_counts={}
  published_fixed=read(P/'FIXED83_94_ALL_MEMBER_SOURCE_ROWS.json')
  for win in ['2022_2024','strong']:
   rr=[attach(r) for r in originals[win]];auth={x['key']:x for x in published[win]};assert len(auth)==len(rr)=={'2022_2024':2581,'strong':1214}[win]
   assert set(auth)=={r['key'] for r in rr}
   for r in rr:
    pp=auth[r['key']]
    for k in ['sid','role','actual_entry_action','decision_at','cost','net','strict_realized','open_unrealized','AR']:assert pp[k]==r[k],('actual entry identity',k,r['key'])
    verify_source(r,pp)
   regular={k:v for k,v in summary[win].items() if k not in ['positive_endpoint_labels','negative_endpoint_labels']};verify_groups(rr,regular)
   verify_table([r for r in rr if D(r['net'])>0],summary[win]['positive_endpoint_labels']);verify_table([r for r in rr if D(r['net'])<0],summary[win]['negative_endpoint_labels'])
   populations[win]=money(rr,'net');class_counts[win]={cat:dict(money([r for r in rr if r['_class']==cat],'net'),i_buy_true=sum(r['_buy'] for r in rr if r['_class']==cat),i_buy_false=sum(not r['_buy'] for r in rr if r['_class']==cat)) for cat in CATS}
   if win=='2022_2024':
    dec_source=read(C/'JOINT_DEC_OWN_CLOCK_CAPITALTIME_ROWS.json');dmap={x['key']:x for x in dec_source if x['cohort'].startswith('Dec_new')};dec=[dict(r,Dec_wealth=dmap[r['key']]['Dec_components']['wealth']) for r in rr if r['key'] in dmap];assert len(dec)==135
    saved=read(P/'DEC135_SOURCE_ROWS.json');assert {x['key'] for x in saved}==set(dmap)
    for x in saved:assert x['Dec_wealth']==dmap[x['key']]['Dec_components']['wealth'];verify_source(x,x)
    verify_groups(dec,summary['Dec_new135'])
   else:
    winners=[r for r in rr if D(r['net'])/D(r['cost'])>=D('.30')];assert len(winners)==122;assert {x['key'] for x in winners}=={x['key'] for x in read(P/'STRONG_OWN122_GE30_SOURCE_ROWS.json')};verify_groups(winners,summary['strong_own_endpoint_ge30pct'])
   # Distinguish original-label money, candidate actual money and stock universes.
   original=[dict(attach(t['original_fixed_member']),key=t['entry_key']) for t in fixed[win]['rows']];assert len(original)=={'2022_2024':83,'strong':94}[win]
   pf={t['original']['key']:t for t in published_fixed[win]};assert set(pf)=={r['key'] for r in original}
   for r in original:verify_source(r,pf[r['key']]['original'])
   original_keys={x['key'] for x in original};candidate_keys={x['key'] for x in rr};base_keys={t['entry_key'] for t in fixed[win]['rows'] if t['baseline_current_exact_match'] is not None};stockset={x['sid'] for x in original}
   baseline_original=[r for r in original if r['key'] in base_keys];candidate_actual=[r for r in rr if r['key'] in original_keys];candidate_stock=[r for r in rr if r['sid'] in stockset]
   verify_table(original,tails[win]['full_original_fixed_members']);verify_table(baseline_original,tails[win]['BASELINE_45_or67_matched_original_members']);verify_table(candidate_actual,tails[win]['JOINT_46_or54_exact_actual_entries']);verify_groups(candidate_stock,tails[win]['all_JOINT_actual_entries_in_original_fixed_stocks'])
   tail_counts[win]=dict(original_members=len(original),baseline_current_exact=len(baseline_original),candidate_exact=len(candidate_actual),baseline_and_candidate_intersection=len(base_keys&candidate_keys),all_candidate_entries_in_original_stocks=len(candidate_stock),original_A=money([x for x in original if x['_class']==A],'net'),candidate_exact_A=money([x for x in candidate_actual if x['_class']==A],'net'),candidate_all_original_stocks_A=money([x for x in candidate_stock if x['_class']==A],'net'))
  assert len(requested)==validation['cached_stock_series_read']==validation['requested_stock_series']==1260
  assert sum(len(x) for x in originals.values())==validation['actual_entry_rows']==3795 and validation['actual_entry_unknown']==validation['original_fixed_unknown']==0
  assert validation['original_fixed_members']==177 and validation['original_models_replayed']==validation['new_accounts']==validation['new_trade_rules']==0
  ownA=[x for x in winners if x['_class']==A];decA=[x for x in dec if x['_class']==A]
  report.update(status='PASS_DESCRIPTIVE_SOURCE_TYPE_COVERAGE',verified_source_hashes=len(manifest['source_sha256']),verified_deliverable_hashes=len(manifest['deliverables']),cached_stock_series=1260,unique_stock_dates_formula_checks=formula_checks,actual_entry_rows=3795,original_fixed_tail_members=177,source_unknown=0,all_published_actual_entry_keys_and_cached_fields_exact=True,all_role_action_and_i_buy_crossgroups_closed=True,amount_tables_verified=TABLES,class_groups_verified=CLASS_GROUPS,
   populations=populations,classes=class_counts,Dec_A_monthly_wealth=money(decA,'Dec_wealth'),Dec_all_monthly_wealth=money(dec,'Dec_wealth'),strong_own122_A=money(ownA,'net'),strong_own122_all=money(winners,'net'),strong_own122_A_fraction_of_net=D(money(ownA,'net')['net'])/D(money(winners,'net')['net']),fixed_tail_denominators_and_A_money=tail_counts,
   source_semantics='Only contemporaneous saved E0-entry / G1 source reasons; no class is a new I structure, independent CP confirmation, entry approval, win probability or causal effect.',
   C_not_B='A saved new_E0_price_volume_up_event without E0.entered or S21/S63 up confirmation is C, not B.',
   outcome_usage='Net-sign/own>=30% subsets used only after cached classification for evaluation. Dec uses native Dec wealth, actual whole-window entries use endpoint realized+mark+AR. Fixed original labels retain original amounts; candidate exact tail table uses candidate actual amounts.',
   restrictions=['All caches source-hashed to original frozen manifests. Native Boolean producer files are tied to original cache freeze; no cold numeric model replay here.',
    'A83 Dec negatives cannot justify removing A: A includes957 strong actual entries and107/122 own evaluation tails with substantial positive contribution. These are descriptive actual allocations, not a proposed counterfactual filter.',
    'Current industry/universe, observed history, actual account path feedback, marked-open equity and AR limitations remain. No filters, economic path, model or parameter changed.'],protected_original_hashes_verified=protected)
 except BaseException as e:report.update(status='FAIL_PRESERVE_EVIDENCE',error=repr(e));raise
 finally:
  SRC[str(Path(__file__).resolve())]=sha(__file__);report['independent_source_sha256']=SRC;output.open('x').write(json.dumps(report,ensure_ascii=False,indent=2,default=str)+'\n')
 print(report['status'],TABLES,CLASS_GROUPS,formula_checks)
