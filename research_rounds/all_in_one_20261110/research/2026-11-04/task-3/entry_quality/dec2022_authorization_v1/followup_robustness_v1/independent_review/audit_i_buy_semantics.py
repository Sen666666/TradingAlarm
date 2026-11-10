"""Nine fixed explanatory cases: native i_buy semantics, no model/account run."""
from pathlib import Path
import hashlib,json
from collections import Counter
import pandas as pd
HERE=Path(__file__).resolve().parent;F=HERE.parent;P=F/'entry_mechanism'
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');SRC={}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):p=Path(p);SRC[str(p.resolve())]=sha(p);return json.loads(p.read_text())
def norm(x):
 if hasattr(x,'item'):return x.item()
 return x
if __name__=='__main__':
 output=HERE/'I_BUY_SEMANTICS_AUDIT.json';assert not output.exists()
 sealed=HERE/'ENTRY_MECHANISM_SCOPE_AUDIT.json';before=sha(sealed);assert before=='b081ab4c7c675dc8e688a6614df263c67ea6ada0f5190be26e5c5d622ea219db'
 cases=read(P/'SYSTEMATIC_CASES.json');contexts={x['key']:x for x in read(P/'SELECTED_CASE_I_E0_CONTEXT.json')};nine=[x['row'] for x in cases if any('Dec_new135:' in s and ':negative:top3' in s for s in x['selection'])];assert len(nine)==9
 refs={x['symbol']:x for x in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
 freeze=read(W/'native-I-cache-interface-20261031/FREEZE.json')
 sourcefiles=[W/'native-I-cache-interface-20261031/cache.py',R/'b5-g1-20261025/code/policies_g1.py',R/'b5-g1-20261025/code/grade.py']
 for p in sourcefiles:assert sha(p)==freeze['source_sha'][str(p)];SRC[str(p)]=sha(p)
 ixmanifest=read(R/'ix-a-share-entry-20261025/signals/manifest.json');ixrefs={x['symbol']:x for x in ixmanifest['series']}
 out=[];cache={}
 for r in nine:
  sid=r['sid'];day=pd.Timestamp(r['decision_at'][:10])
  if sid not in cache:
   ref=refs[sid];fp=Path(ref['refs']['facts']);ip=R/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet'
   assert sha(fp)==ref['output_sha256'][str(fp)];assert sha(ip)==ixrefs[sid]['output_sha256'];SRC[str(fp)]=sha(fp);SRC[str(ip)]=sha(ip)
   cache[sid]=(pd.read_parquet(fp),pd.read_parquet(ip))
  facts,ix=cache[sid];q=facts.loc[day];x=ix.loc[day];at=facts.index.get_loc(day);assert at>0
  assert q.i_buy and q.i_target and q.e0_target and q.g_ready
  assert bool(q.g_fresh_up)==bool(x.fresh_up);assert q.g_grade==x.grade;assert bool(q.e0_target)==bool(x.e0_target)
  formula=bool(q.i_target and x.e0_target and x.strength_ready and x.grade>=2 and (x.e0_entered or x.fresh_up));assert formula==bool(q.i_buy)
  j=at
  while j>0 and facts.iloc[j-1].segment_id==q.segment_id and bool(facts.iloc[j-1].i_target):j-=1
  age=at-j+1;assert age==contexts[r['key']]['I_known_observations_through_decision'];assert str(facts.index[j].date())==contexts[r['key']]['I_continuous_start']
  prev=facts.iloc[at-1];newI=bool(q.i_target and (q.segment_id!=prev.segment_id or not prev.i_target))
  history=[]
  for d,qq in facts.iloc[max(0,at-5):at+1].iterrows():
   xx=ix.loc[d];history.append(dict(day=str(d.date()),source_segment=norm(qq.segment_id),I_on=bool(qq.i_target),i_buy=bool(qq.i_buy),E0_on=bool(qq.e0_target),E0_entered=norm(xx.e0_entered),G1_fresh_up=bool(xx.fresh_up),G1_up_reasons=xx.up_reasons,G1_ready=bool(xx.strength_ready),G1_grade=norm(xx.grade),original_IX_entered=norm(xx.ix_entered)))
  assert r['original_receipt']['confirmed_day']==r['decision_at'][:10]
  out.append(dict(key=r['key'],sid=sid,actual_action=r['actual_entry_action'],decision_at=r['decision_at'],I_on=bool(q.i_target),same_close_i_buy=bool(q.i_buy),I_continuous_start=str(facts.index[j].date()),I_continuous_observation_age=age,I_0_to_1_on_this_close=newI,E0_entered=norm(x.e0_entered),G1_fresh_up=bool(x.fresh_up),G1_up_reasons=x.up_reasons,G1_grade=norm(x.grade),formula_exact=True,prior5_and_current_observations=history))
 assert not any(x['I_0_to_1_on_this_close'] for x in out)
 assert sha(sealed)==before
 result=dict(status='PASS_CLARIFY_FRESH_BUY_EVIDENCE_IS_NOT_FRESH_I_STRUCTURE',cases=9,
  native_formula='i_buy = final I active AND E0 target AND G1 ready AND grade >=2 AND (E0 entered OR G1 fresh_up)',
  fresh_up_formula='Any: new E0 positive price-volume event; new S21/S63 up confirmation; or a new running price frontier within already confirmed S21 up structure',
  producer_chain='native-I-cache-interface/cache.py derive sets facts.i_buy=out.buy_event from policies_g1.project(...,G1_I), using saved original IX G1 evidence; no model recomputed here',
  facts_I_on=9,facts_i_buy_true=9,same_close_new_I_0_to_1=0,I_age_min=min(x['I_continuous_observation_age'] for x in out),I_age_max=max(x['I_continuous_observation_age'] for x in out),same_close_G1_fresh_up=sum(x['G1_fresh_up'] for x in out),same_close_E0_entered=sum(bool(x['E0_entered']) for x in out),up_reason_counts=dict(Counter(x['G1_up_reasons'] for x in out)),
  supported_wording='当日原i_buy=True、I on、fresh CP；若解释I买点，称原G1当日买入事件/新增上行证据资格。',
  unsupported_wording=['fresh I / 当天新I连续结构','独立于CP的第二份趋势确认','仅凭I age就断言完全没有当日新上行证据','i_buy仅等于持续I on'],
  explanation='A repeated fresh-up frontier event can occur within an I episode aged14–47 observations. Native i_buy is more selective than target_on, yet does not mean a new I episode or statistically/economically independent new evidence. The existing README sentence calling these fresh I/真正新I买证据 is ambiguous/overbroad and should be narrowed outside sealed bytes.',
  formation_scope_and_financial_conclusions_changed=False,new_account_events=0,new_accounts=0,new_rule=0,sealed_scope_audit_sha256_unchanged=before,rows=out)
 SRC[str(Path(__file__).resolve())]=sha(__file__);result['source_sha256']=SRC;output.open('x').write(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n')
 print(result['status'],result['up_reason_counts'])
