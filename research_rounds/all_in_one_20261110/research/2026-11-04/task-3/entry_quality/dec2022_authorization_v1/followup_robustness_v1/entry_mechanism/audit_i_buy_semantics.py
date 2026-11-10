"""Original-source semantic replay for nine preselected cases. No financial engine."""
from pathlib import Path
import sys,json,hashlib,datetime,math
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=RR/'a-share-selection-e0-20261024/prepared-v2'
B5=RR/'pv-strength-b5-20261025/code';G1=RR/'b5-g1-20261025/code'
sys.path[:0]=[str(B5),str(G1),str(RR/'pv-participation-response-20261020/code')]
from data_utils import eligible_prices
from evidence import build_evidence
from grade import classify
from policy import e0_policy
from policies_g1 import project

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,(int,np.integer)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(float(x)) else None
 if pd.isna(x):return None
 return x

def write(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
seal=json.loads((O/'SOURCE_MANIFEST.json').read_text())['deliverables']
assert all(sha(O/n)==h for n,h in seal.items()),'prior sealed artifact changed before audit'
sources={}
def read(p,expected=None):
 p=Path(p);h=sha(p)
 if expected:assert h==expected
 sources[str(p)]=h
 return json.loads(p.read_text())
records={r['series_id']:r for r in read(OLD/'manifest.json')['series']}
ixrecords={r['symbol']:r for r in read(RR/'ix-a-share-entry-20261025/signals/manifest.json')['series']}
stockrecords={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
cases=read(O/'SYSTEMATIC_CASES.json')
cases=[r for r in cases if any(s.startswith('2022_2024:Dec_new135') and ':negative:' in s for s in r['selection'])]
assert len(cases)==9
by_sid={}
for c in cases:by_sid.setdefault(c['row']['sid'],[]).append(c)
traces=[];audits=[]
for sid,cc in by_sid.items():
 cutoff=max(c['row']['decision_at'][:10] for c in cc)
 rec=records[sid]
 p=OLD/rec['files']['signal']['path'];assert sha(p)==rec['files']['signal']['sha256'];sources[str(p)]=sha(p)
 sig=pd.read_parquet(p).loc[:cutoff]
 p=Path(stockrecords[sid]['refs']['facts']);sources[str(p)]=sha(p);assert sources[str(p)]==stockrecords[sid]['output_sha256'][str(p)]
 native=pd.read_parquet(p).loc[:cutoff]
 p=RR/'ix-a-share-entry-20261025/signals'/f'{sid}.parquet';sources[str(p)]=sha(p);assert sources[str(p)]==ixrecords[sid]['output_sha256']
 saved=pd.read_parquet(p).loc[:cutoff]
 f=eligible_prices(sig)[['open','high','low','close','volume','segment_id']].copy()
 f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
 e,j=build_evidence(f);g,_=classify(e)
 e['decline_candidate']=False;e['candidate_lower']=np.nan;e['candidate_reclaim']=np.nan
 b,_=e0_policy(e);ip=project(e,b,g,'G1_I')
 assert f.index.equals(native.index) and f.index.equals(saved.index)
 for k in ['fresh_up','up_reasons','grade']:
  a=g[k];z=saved[k]
  if k=='grade':np.testing.assert_equal(a.to_numpy(),z.to_numpy())
  else:assert a.tolist()==z.tolist(),(sid,k)
 np.testing.assert_equal(ip.target.to_numpy(float),native.i_target.to_numpy(float))
 assert ip.buy_event.tolist()==native.i_buy.tolist()
 assert g.fresh_up.tolist()==native.g_fresh_up.tolist()
 formula=ip.target.eq(1)&b.target.eq(1)&g.ready&g.grade.ge(2)&(b.entered.eq(1)|g.fresh_up)
 assert formula.tolist()==native.i_buy.tolist()
 retained_on_without_buy=(ip.target.eq(1)&~ip.buy_event)
 prior_ext=e.strength_running_extreme_price_21.where(g.ready).ffill().shift()
 prior_s21=e.strength_S21.where(g.ready).ffill().shift()
 audits.append(dict(sid=sid,through=cutoff,original_valid_observations=len(f),full_prefix_buy_event_formula_exact=True,
   cached_g_fresh_up_up_reasons_grade_exact=True,cached_i_target_and_i_buy_exact=True,
   I_on_but_i_buy_false_observations=int(retained_on_without_buy.sum())))
 for c in cc:
  r=c['row'];day=pd.Timestamp(r['decision_at'][:10]);idx=f.index.get_loc(day);prior=f.index[max(0,idx-5):idx+1];trajectory=[]
  for dt in prior:
   er=e.loc[dt];gr=g.loc[dt];ir=ip.loc[dt];br=b.loc[dt]
   extra={k:er[k] for k in e.columns if k.startswith('strength_') and any(s in k for s in ['anchor','extreme','confirmed_direction','S21','S63'])}
   trajectory.append(dict(day=str(dt.date()),close=er.close,volume=er.volume,source_segment=er.segment_id,
    i_target=ir.target,i_buy=ir.buy_event,i_entered=ir.entered,i_exited=ir.exited,i_floor=ir.floor,
    e0_target=br.target,e0_entered=br.entered,e0_floor=br.floor,
    g_ready=gr.ready,g_grade=gr.grade,g_fresh_up=gr.fresh_up,g_up_reasons=gr.up_reasons,g_phase=gr.phase,
    original_E0_event=er.event,confirmed_pivot_price=er.confirmed_pivot_price,
    confirmed_pivot_date=er.confirmed_pivot_date,developing_extreme_price=er.developing_extreme_price,
    developing_extreme_date=er.developing_extreme_date,
    prior_valid_S21_direction=prior_s21.loc[dt],prior_valid_S21_running_extreme_price=prior_ext.loc[dt],
    current_proof_fields_and_anchors=extra))
  today=trajectory[-1]
  assert today['i_buy'] and today['g_fresh_up'] and today['i_entered']==0 and today['e0_entered']==0
  assert today['g_up_reasons']=='new_price_frontier_in_confirmed_up_structure'
  traces.append(dict(entry_key=r['key'],sid=sid,name=r['name'],actual_action=r['actual_entry_action'],decision_at=r['decision_at'],
    actual_opened=r['opened'],original_CP_receipt_id=r['receipt'],original_CP_formation_start=r['original_receipt']['formation_start_exclusive'],
    original_CP_confirmation_day=r['original_receipt']['confirmed_day'],
    interpretation='I buy opportunity due to a new frontier of existing confirmed S21 up structure; not new I/E0 or S21/S63 confirmation, not independent of price-frontier CP evidence.',
    observations=trajectory))

source_files=[W/'native-I-cache-interface-20261031/cache.py',RR/'../TradingAlarm/desk/refresh.py',G1/'policies_g1.py',G1/'grade.py',B5/'evidence.py',B5/'policy.py',RR/'pv-strength-b4-20261025/code/model.py',RR/'ix-a-share-entry-20261025/code/prepare_ix.py']
for p in source_files:sources[str(p.resolve())]=sha(p)
locations=[]
for p,needles in [(W/'native-I-cache-interface-20261031/cache.py',["keep['i_buy']=out.buy_event"]),(G1/'policies_g1.py',['opportunity=shadow and warm','buy=bool(active and opportunity)']),(G1/'grade.py',["new_E0_price_volume_up_event","new_S{h}_up_confirmation","new_price_frontier_in_confirmed_up_structure"] )]:
 lines=p.read_text().splitlines()
 for needle in needles:
  for n,line in enumerate(lines,1):
   if needle in line:locations.append(dict(file=str(p),line=n,code=line.strip()))
write('I_BUY_NINE_CASE_TRAJECTORIES.json',dict(cases=traces,full_prefix_audits=audits))
clarification=dict(status='SEMANTIC_SCOPE_NARROWED_SEALED_REPORT_PRESERVED',at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 original_wording=['9例i_buy=True叫真正新I买证据/fresh I','据此否定没有fresh I的解释'],
 corrected_wording='这9例在原G1_I公式下有当日buy_event机会，其唯一fresh_up理由均是既有S21上行结构内的新运行价格前沿。它们不是仅i_target维持就自动true，但也不是新I连续结构、新E0结构或新的S21/S63上确认；不能称与CP独立的新趋势证据。',
 formula='i_buy = i_active_after_exit_processing AND E0_shadow_target AND g_ready AND grade>=2 AND (E0_entered_today OR g_fresh_up_today)',
 fresh_up_formula='new E0 up event OR new S21 up confirmation OR new S63 up confirmation OR prior_S21==current_S21==up and current_running_extreme>prior_running_extreme+32eps*max(abs(ext),abs(prior),1)',
 persistent_state_distinction='I_target on need not make i_buy true; i_buy can still be true on consecutive days when each makes a new frontier. New buy opportunity is not a new I structural episode.',
 actual_nine=dict(i_buy_true=9,i_target_on=9,e0_entered=0,i_entered=0,new_E0_up_reason=0,new_S21_S63_up_confirmation_reason=0,only_existing_S21_new_frontier_reason=9),
 conclusion_scope='只能排除这9例完全没有I模块当日认可机会的说法。不能否定全母体存在仅继承I授权的失败，不能证明独立新I结构或入场质量，也不能将原fresh_up与CP前沿当两项独立alpha。',
 unchanged_mechanism_conclusion='形成区间候选的Dec0/三年3/strong0静态作用域、否决结论和所有金额均不受此语义收窄影响。',
 replay='Read original frozen price source and replay the unchanged original B5/G1/I producer through each last selected day solely to expose cached proof fields/anchors and verify equality. No new model variant, indicator formula, signal policy or financial account.',
 original_source_replay_series=len(audits),original_observations_replayed=sum(r['original_valid_observations'] for r in audits),new_models=0,new_accounts=0,
 code_locations=locations,source_sha256=sources,prior_sealed_deliverable_sha256=seal)
assert all(sha(O/n)==h for n,h in seal.items()),'sealed artifact changed during semantic audit'
clarification['all_prior_sealed_hashes_unchanged']=True
write('SEMANTIC_CLARIFICATION.json',clarification)
write('SEMANTIC_SOURCE_SHA256.json',dict(source_sha256=sources,new_files_sha256={n:sha(O/n) for n in ['audit_i_buy_semantics.py','I_BUY_NINE_CASE_TRAJECTORIES.json','SEMANTIC_CLARIFICATION.json']},sealed_files_unchanged=True))
print(json.dumps(dict(status=clarification['status'],cases=9,series=len(audits),observations=clarification['original_observations_replayed'],all9_reason='new_price_frontier_in_confirmed_up_structure',all9_new_I_or_E0_structure=False,sealed_hashes_unchanged=True),ensure_ascii=False))
