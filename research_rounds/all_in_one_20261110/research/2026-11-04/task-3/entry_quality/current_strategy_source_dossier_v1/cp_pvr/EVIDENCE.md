# 当前原No60：CP与PVR源码证据

只读源码摘录与调用顺序，不执行任何指标函数、模块初始化、模型、账户、统计或新设计。本件的“当前”指原No60的实际适配路径，不混入已停止的新v2/v3合同，也不把旧PVR rotation策略当当前交易行为。摘录保留原变量名和原行文；行号绑定SOURCE_SHA256.json。

当前继承链是 [No60 native_adapter.Runner](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:16) → [native_rank.Runner](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:94) → 原J.Runner。No60源码明确断言opening是J.Runner.opening、planning是N.Runner.planning；N先调用原J.planning，再仅替换pending的rank键。这里没有通过运行这些断言来验证，只摘读真实代码。

当前No60保留哪一份planning/opening：[原文件第27行](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:27)（摘录27–33行）。

```python
    def assert_native_wiring(self):
        bootstrap=getattr(self,'_cap_bootstrap',False)
        assert self.integration_policy==(N.POLICY if bootstrap else POLICY)+':'+self.rank_mode
        assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
        assert self.opening.__func__ is J.Runner.opening
        assert self.planning.__func__ is N.Runner.planning
        assert self.route.__func__ is P.ROUTES[True]
```

## CP：输入、公式和状态

模型里名字叫e0_valid的股票输入，实际是原I_target；e0_down来自原native event为−1。这两个映射不同于“原E0 target是否刚开启”。

实际股票CP输入frame：[原文件第23行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stock-cp1-warmup-20261031/generate.py:23)（摘录23–27行）。

```python
def frame(sid,f,cut):
 if f.empty:
  return pd.DataFrame({'close':pd.Series(dtype=float),'segment_id':pd.Series(dtype=int),'i_target':pd.Series(dtype=bool),'i_floor':pd.Series(dtype=float),'amount':pd.Series(dtype=float),'e0_down':pd.Series(dtype=bool),'e0_valid':pd.Series(dtype=bool)},index=f.index)
 rec=N.RECORDS[sid];sig=pd.read_parquet(N.OLD/rec['files']['signal']['path']).loc[:cut];ev=pd.read_parquet(N.OLD/rec['files']['events']['path']).reindex(f.index);out=f[['close','segment_id','i_target','i_floor']].copy();out['amount']=sig.amount.reindex(f.index);out['e0_down']=ev.event.eq(-1);out['e0_valid']=f.i_target.astype(bool)
 if not np.isfinite(out[['close','amount']]).all().all() or not out[['close','amount']].gt(0).all().all():raise ValueError('missing/nonpositive same-source CP1 price or amount; no row removal allowed')
```

CP用adjusted close的对数收益r；s是此前63个绝对对数收益的中位数×1.4826，shift排除当前收益，最小1e−8。B是此前21个amount中位数，也排除当前amount。u用r/s，v用当前amount相对B。m=1+.5×abs(u)×v只调新frontier位移的权重；保护距离的z另有S_MIN=log1p(.001)地板，不能把z与u分母s混成同一字段。

CP常数和浮点比较：[原文件第5行](/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py:5)（摘录5–8行）。

```python
A=math.sqrt(5);K=math.sqrt(21);S_MIN=math.log1p(.001)
EPS=4*2**-53/(1-4*2**-53)
def ge(a,b):return a>=b or abs(a-b)<=EPS*max(abs(a),abs(b),1e-300)
def gt(a,b):return a>b and not abs(a-b)<=EPS*max(abs(a),abs(b),1e-300)
```

CP features原公式：[原文件第20行](/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py:20)（摘录20–24行）。

```python
 out=pd.DataFrame(index=f.index,columns=['r','s','z','B','u','v','m'],dtype=float)
 for _,g in f.groupby('segment_id',sort=False):
  r=np.log(g.close).diff();s=r.abs().shift().rolling(63,min_periods=63).median().mul(1.4826).clip(lower=1e-8)
  B=g.amount.shift().rolling(21,min_periods=21).median();u=np.tanh(r/s);v=np.tanh(np.log(g.amount/B))
  out.loc[g.index]=pd.DataFrame(dict(r=r,s=s,z=s.clip(lower=S_MIN),B=B,u=u,v=v,m=1+.5*u.abs()*v),index=g.index)
```

一个CLOSE先读本日q，再处理source change、未准备/I失效、负event重置或SEEK更低anchor；只有严格超过既有frontier才累credit。receipt还要求当次fresh>0、位移与credit都达到sqrt(5)×此前冻结scale。candidate=C×exp(−sqrt(21)×旧scale)，不是后来确认低点。receipt当日先保存used_*，随后清credit、把anchor/frontier设为当日log close，并把当前z留给下一段。

CP calculate的实际前后状态：[原文件第26行](/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py:26)（摘录26–50行）。

```python
def calculate(f,price_only=False):
 z=features(f);out=[];phase=None;anchor=frontier=scale=None;credit=0.;segment=None
 for day,row in f.iterrows():
  q=z.loc[day];p=math.log(row.close);fresh=0.;receipt=False;candidate=math.nan;reason=None;disp=math.nan
  if row.segment_id!=segment:
   phase=None;segment=row.segment_id;reason='source_reset'
  ready=math.isfinite(q.z)
  if not ready or not row.e0_valid:
   phase=None;anchor=frontier=scale=None;credit=0.;reason='unprepared' if not ready else 'E0_invalid'
  elif phase is None or row.e0_down:
   phase='SEEK';anchor=frontier=p;credit=0.;scale=float(q.z);reason='E0_down_reset' if row.e0_down else 'start'
  elif phase=='SEEK' and gt(anchor,p):
   anchor=frontier=p;credit=0.;scale=float(q.z);reason='lower_anchor'
  else:
   fresh=p-frontier if gt(p,frontier) else 0.
   if fresh:
    frontier=p;credit=math.fsum((credit,fresh*(1. if price_only else float(q.m))))
   disp=frontier-anchor
   receipt=bool(fresh and ge(disp,A*scale) and ge(credit,A*scale))
   if receipt:candidate=float(row.close)*math.exp(-K*scale)
  used_anchor,used_scale,used_credit=anchor,scale,credit
  used_phase=phase
  if receipt:
   phase='UP';anchor=frontier=p;credit=0.;scale=float(q.z);reason='receipt_consumed'
  out.append(dict(ready=ready,phase=used_phase,reset_reason=reason,anchor=used_anchor,frontier=frontier,scale=used_scale,credit=used_credit,delta_frontier=fresh,displacement=disp,receipt=receipt,candidate=candidate,next_anchor=anchor,next_scale=scale,next_credit=credit,next_phase=phase))
```

`scale/credit/phase`为本次使用状态；`next_scale/next_credit/next_phase`为消费后状态。UP阶段不会仅因低于anchor就走SEEK的lower_anchor分支；负native event即使I仍有效也能重新锚定。新receipt因此可在整条持仓链旧高之下形成，但仍须有本局部段新价格frontier，不能称同一位移重复发证。

当前universe缓存生产器实际导入上述G，见[prepare.py:8](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/prepare.py:8)，新链明确调用`q=G.frame(sid,f,END); z=M.calculate(q)`；已存在链则校验并复用原case/兼容旧cache。此处摘读生产源码，没有重新执行calculate。当前loader再按原manifest refs读取facts/CP1_input/CP1，见[loader_2024.py:37](/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/loader_2024.py:37)。因此上述I_target映射有实际缓存生产链依据。

```python
 if case is not None:
  assert all(sha(p)==h for p,h in case['source_sha256'].items())
  assert all(sha(W/'case-stock-cp1-warmup-20261031'/p)==h for p,h in case['output_sha256'].items())
  root=W/'case-stock-cp1-warmup-20261031';refs=dict(facts=str(root/'full-facts'/f'{sid}.parquet'),CP1_input=str(root/'CP1-input'/f'{sid}.parquet'),CP1=str(root/'CP1'/f'{sid}.parquet'));f=pd.read_parquet(refs['facts']).loc[:END];q=pd.read_parquet(refs['CP1_input']).loc[:END];z=pd.read_parquet(refs['CP1']).loc[:END];source_hash=case['source_sha256'];CP_reuse=facts_reuse=True;checks['previous_case_full_chain_verified']=True;mode='verified_case_reuse'
 else:
  f,receipt=N.derive(sid,END);paths=source_paths(sid);source_hash={str(p):sha(p) for p in paths.values()};native=pd.read_parquet(W/'native-I-cache-interface-20261031/facts'/f'{sid}.parquet').loc[BEGIN:END];G.exact(f.loc[BEGIN:END],native);checks['native_I_export_all_fields_exact']=True;q=G.frame(sid,f,END);z=M.calculate(q);old=C.O/'signals'/f'{sid}.parquet';mode='new_fixed_chain'
  if old.exists():
   try:
    G.exact(q,C.frame(sid,END));G.exact(z,pd.read_parquet(old).loc[:END]);refs['CP1']=str(old);CP_reuse=True;old_source_status='full_input_and_CP1_exact';checks['old_CP1_current_source_exact']=True
```

## CP trace：证据身份不是新的交易预算

trace读取已计算的f/z/events/episode，补canonical ID、来源段、真实E0 episode、anchor/confirmation及未重复advance身份。这里episode读的是原E0 target序列，与CP有效性实际读I_target是两件事。

trace的source/E0 episode与anchor状态：[原文件第30行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/cp1-evidence-trace-20261031/trace.py:30)（摘录30–44行）。

```python
def trace(canonical,f,z,events,episode,alias=None):
 assert f.index.equals(z.index);out=[];points=[];anchor_at=anchor_obs=frontier_obs=scale_at=None;anchor_idx=None;last_receipt=None;global_last=None;consumed=set();ep=None;prevtarget=None;seg=None;epknown=True;checks=collections.Counter();allinc=[]
 dates=list(f.index);fr=f.to_dict('records');zr=z.to_dict('records');ev=events.reindex(f.index);epvals=episode.reindex(f.index)
 for i,(day,r,q) in enumerate(zip(dates,fr,zr)):
  d=str(day.date());segment=str(int(r['segment_id']));obs=ident('price-observation',canonical,segment,d);target=bool(epvals.iloc[i]) if pd.notna(epvals.iloc[i]) else None
  if segment!=seg:seg=segment;prevtarget=None;ep=None;last_receipt=None
  if target is None:epknown=False;ep=None
  elif not target:ep=None;epknown=True
  elif prevtarget is False:ep=ident('original-E0-episode',canonical,segment,obs);epknown=True;last_receipt=None
  elif prevtarget is None:epknown=False;ep=None
  prevtarget=target;reason=q['reset_reason'] if pd.notna(q['reset_reason']) else None
  if reason in ['unprepared','E0_invalid']:
   points=[];anchor_at=anchor_obs=frontier_obs=scale_at=None;anchor_idx=None
  elif reason in ['start','E0_down_reset','lower_anchor']:
   points=[];anchor_at=d;anchor_obs=frontier_obs=obs;scale_at=d;anchor_idx=i
```

trace的advance消费和receipt身份：[原文件第45行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/cp1-evidence-trace-20261031/trace.py:45)（摘录45–57行）。

```python
  fresh=float(q['delta_frontier']) if pd.notna(q['delta_frontier']) else 0.
  if fresh>0:
   event=ev.iloc[i];native_sign=int(event.event) if pd.notna(event.get('event')) else None;point=dict(price_event_id=obs,day=d,from_observation_id=frontier_obs,to_observation_id=obs,log_displacement=fresh,log_frontier_to=math.log(r['close']),volume_multiplier=float(q['m']),native_event_known=native_sign is not None,native_event_sign=native_sign,derived_native_event_id=ident('cached-native-event-derived',canonical,segment,d,native_sign) if native_sign in [-1,1] else None,amount_background_start=str(dates[max(0,i-21)].date()),amount_background_end=str(dates[i-1].date()) if i else None);points.append(point);frontier_obs=obs
  if bool(q['receipt']):
   rid=ident('market-CP1-receipt',canonical,SCALE,segment,ep,anchor_obs,obs);unknown=[]
   if not epknown:unknown.append('original_E0_episode_start_unknown')
   if anchor_at is None or anchor_idx is None:unknown.append('CP1_anchor_origin_unknown')
   if any(not p['native_event_known'] for p in points):unknown.append('native_event_row_missing_in_advances')
   assert points and points[-1]['day']==d and fresh>0;assert all(p['price_event_id'] not in consumed for p in points),(canonical,d,'old impulse reused');assert all(p['day']>anchor_at for p in points)
   if last_receipt:assert all(p['day']>last_receipt['confirmed_day'] for p in points)
   checks['new_unconsumed_advance_receipts']+=1;used_ids=[p['price_event_id'] for p in points];signature=ident(canonical,segment,anchor_obs,obs,[(p['price_event_id'],p['log_displacement'],p['volume_multiplier']) for p in points]);row=dict(canonical_series=canonical,source_alias=alias or canonical,scale_id=SCALE,source_segment=segment,original_E0_episode_id=ep,confirmed_day=d,receipt_id=rid,decision_evidence_key=ident('one-series-scale-observation',canonical,SCALE,obs),formation_start_exclusive=anchor_at,formation_end_inclusive=d,anchor_observation_id=anchor_obs,confirmation_observation_id=obs,previous_market_receipt_id=last_receipt['receipt_id'] if last_receipt else None,previous_market_confirmed_day=last_receipt['confirmed_day'] if last_receipt else None,previous_global_market_receipt_id=global_last['receipt_id'] if global_last else None,previous_consumed_frontier_log=last_receipt['frontier_log'] if last_receipt else None,original_candidate=float(q['candidate']),original_scale=float(q['scale']),scale_frozen_at=scale_at,scale_old_return_end_observations=[ident('price-observation',canonical,segment,str(t.date())) for t in dates[max(1,anchor_idx-63):anchor_idx]] if anchor_idx is not None else [],new_advance_price_event_ids=used_ids,new_advance_observations=len(points),new_log_price_displacement=float(q['displacement']),original_credit=float(q['credit']),evidence_signature=signature,trace_unknown=unknown,native_event_id_note='derived from cached event observation; provider supplies no original eventID',live_publication_time='unknown; confirmation day only',stage_controller_consumed=False)
   if BEGIN<=d<=END:out.append(row);allinc.extend(dict(receipt_id=rid,canonical_series=canonical,**p) for p in points)
   consumed.update(used_ids);last_receipt=global_last=dict(receipt_id=rid,confirmed_day=d,frontier_log=math.log(r['close']));points=[];anchor_at=d;anchor_obs=frontier_obs=obs;scale_at=d;anchor_idx=i
```

trace的alias/重复去重：[原文件第59行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/cp1-evidence-trace-20261031/trace.py:59)（摘录59–65行）。

```python
def dedup(rows):
 used={};decisions={}
 for r in rows:
  k=r['receipt_id'];dk=r['decision_evidence_key']
  if k in used:assert used[k]['evidence_signature']==r['evidence_signature'];continue
  assert dk not in decisions or decisions[dk]==k,'same underlying decision evidence has conflicting source receipts';decisions[dk]=k;used[k]=r
 return list(used.values())
```

同一receipt只消费一次advance；不同合法receipt仍可能属于同一原E0 episode。缓存左边界已经on但没有见到off→on时，代码保留episode-start unknown；不是人为开启新段。原row还明确写live_publication_time未知、只有confirmation day；native在研究CLOSE按确认日取缓存，trace本身没有证明实际盘中发布时间。

## 实际运行读缓存；公式生成链另列

当前No60运行时不调用score(f)。下列loader为两个实际BASELINE窗口选择manifest并调用N.configure_scores；FrozenScores从manifest同目录的scores/{sid}.parquet读取score行，再按sid和决策日取值。原运行RUN_METADATA中记录的loader/native_rank/No60 adapter字节与当前源一致；三年input_identity及strong源冻结分别绑定相应manifest SHA。详见PVR_RUNTIME_CACHE_LINEAGE.json。

当前实际窗口如何选择评分缓存：[原文件第14行](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/load_inputs.py:14)（摘录14–38行）。

```python
def inputs(window):
 if window=='2022_2024':
  # This loader does not import an old account/checkpoint or annual continuation class.
  value=D.inputs();shared,receipts,cp,states,ir,identity=value
  manifests=[W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',D.O/'inputs/MANIFEST.json']
  receipts={sid:{} for sid in receipts};ir={};binding={}
  for mp in manifests:
   binding[str(mp)]=sha(mp)
   for rec in json.loads(mp.read_text()):
    p=Path(rec['output_path']);assert sha(p)==rec['output_sha256'];binding[str(p)]=rec['output_sha256']
    for r in json.loads(p.read_text()):
     sid=rec['sid'];day=r['confirmed_day']
     if sid in receipts:
      assert day not in receipts[sid];receipts[sid][day]=r
     else:
      key=sid+'|'+day;assert key not in ir;ir[key]=r
  for sid,df in cp.items():assert len(receipts[sid])==int(df.loc['2022-01-01':'2024-12-31'].receipt.eq(True).sum())
  J.START='2022-01-01';J.END='2024-12-31';score=D.O/'SCORES_MANIFEST.json'
  identity=dict(identity,window=[J.START,J.END],receipt_union_sources=binding,stock_canonical_receipts=sum(map(len,receipts.values())),industry_canonical_receipts=len(ir),score_manifest_sha256=sha(score),no_account_state_import=True)
 else:
  assert window=='strong';old=A.S.O
  try:A.S.O=O/'input_readiness';shared,receipts,cp,states,ir,identity=A.S.inputs('2025_26')
  finally:A.S.O=old
  J.START='2025-07-01';J.END='2026-06-30';score=W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json'
 N.configure_scores(score)
```

- `2022_2024` active manifest：[SCORES_MANIFEST.json](/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/SCORES_MANIFEST.json)；实际缓存模式 `/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/scores/{sid}.parquet`。

- `strong` active manifest：[SCORES_MANIFEST.json](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json)；实际缓存模式 `/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/scores/{sid}.parquet`。

`original_score_function.py`不是本次重写的等价式：它是[experiment.py](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/code/experiment.py:24)第24–42行score函数的逐字抽取（本任务只用AST定位文本核同，没有exec）。原实验代码在[79行](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/code/experiment.py:79)调用该score生成当时的评分；后续缓存扩展明确复用该抽取源。其无imports，是因为调用器显式提供np/pd环境。

PVR函数的原始实际实现位置：[原文件第24行](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/code/experiment.py:24)（摘录24–42行）。

```python
def score(f):
 """Independent finite-window calculation, no state/account/future input."""
 out=pd.DataFrame(index=f.index,columns=['r','scale','amount_ref','u','b','e','E','score'],dtype=float)
 valid=(f.close.gt(0)&np.isfinite(f.close)&f.amount.gt(0)&np.isfinite(f.amount))
 for k in ['price_eligible','observed_bar','is_observed_bar']:
  if k in f:valid &= f[k].fillna(False).astype(bool)
 for k in ['source_invalid','synthetic_event_bar']:
  if k in f:valid &= ~f[k].fillna(True).astype(bool)
 # Invalid rows and declared source changes restart the full preparation.
 seg=f.segment_id if 'segment_id' in f else pd.Series(0,index=f.index)
 block=((~valid)|(~valid.shift(fill_value=False))|seg.ne(seg.shift())).cumsum()
 weights=.9**np.arange(20,-1,-1);weights/=weights.sum()
 for _,g in f.loc[valid].groupby(block[valid],sort=False):
  r=np.log(g.close).diff();s=r.abs().shift().rolling(63,min_periods=63).median().mul(1.4826).clip(lower=1e-8)
  ar=g.amount.shift().rolling(21,min_periods=21).median()
  u=np.tanh(r/s);b=np.tanh(np.log(g.amount/ar));e=u*(1+.5*u.abs()*b)
  z=e.rolling(21,min_periods=21).apply(lambda x:np.dot(weights,x),raw=True)
  out.loc[g.index]=pd.DataFrame({'r':r,'scale':s,'amount_ref':ar,'u':u,'b':b,'e':e,'E':z,'score':50+50*np.tanh(2*z)},index=g.index)
 return out
```

逐字抽取及保存原函数的生产代码：[原文件第30行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-current-v3-information-capital-20261101/prepare_only.py:30)（摘录30–42行）。

```python
def function(path,name,env):
 s=Path(path).read_text();INPUT[str(path)]=sha(path);n=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name==name)
 text='\n'.join(s.splitlines()[n.lineno-1:n.end_lineno])+'\n';exec(compile(text,str(path),'exec'),env)
 return env[name],text
freeze=read(O/'CONTRACT_FREEZE.json');assert sha(O/'CONTRACT.txt')==freeze['contract_sha256']
assert freeze['version']=='v1.2' and not freeze['new_paired_outcomes_read']
score,scoretext=function(R/'pvr-act-comparison-20261027/code/experiment.py','score',dict(np=np,pd=pd))
digest=lambda x:hashlib.sha256(x.encode()).hexdigest()
match,matchtext=function(R/'pvr-incremental-order-20261029/code/study.py','match',dict(pd=pd,collections=collections,digest=digest))
env=dict(pd=pd,np=np)
_,_=function(R/'pv-participation-response-20261020/code/data_utils.py','boolean_column',env)
eligible,_=function(R/'pv-participation-response-20261020/code/data_utils.py','eligible_prices',env)
(O/'original_score_function.py').write_text(scoretext);(O/'original_match_function.py').write_text(matchtext)
```

三年评分扩展所用函数源：[原文件第48行](/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/prepare_data.py:48)（摘录48–49行）。

```python
 assert sha(FORMULA)==oldm['formula_sha256']=='9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
 env=dict(np=np,pd=pd);exec(compile(FORMULA.read_text(),str(FORMULA),'exec'),env);score=env['score']
```

实际调用score并写出三年缓存：[原文件第96行](/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/prepare_data.py:96)（摘录96–108行）。

```python
   if not industry:
    sr=oldscore[sid];src=Path(sr['source']);assert sha(src)==sr['source_sha256']
    oldpath=H/'scores'/(sid+'.parquet');assert sha(oldpath)==sr['output_sha256']
    f=pd.read_parquet(src).loc[:END];v=score(f);past=pd.read_parquet(oldpath)
    pd.testing.assert_frame_equal(v[['score']].reindex(past.index),past,check_exact=True,check_freq=False)
    pd.testing.assert_frame_equal(score(f.loc[:CUT]),v.loc[:CUT],check_exact=True,check_freq=False)
    if sid in samples:
     altered=f.copy();altered.loc[altered.index>CUT,'close']*=7;altered.loc[altered.index>CUT,'amount']*=.013
     pd.testing.assert_frame_equal(score(altered).loc[:CUT],v.loc[:CUT],check_exact=True,check_freq=False)
    keep=v[['score']].reindex(dates);sp=O/'scores'/(sid+'.parquet');sp.parent.mkdir(exist_ok=True)
    tmp=sp.with_name(sp.name+'.tmp');keep.to_parquet(tmp);tmp.replace(sp)
    m['score']=dict(symbol=sid,source=str(src),source_sha256=sha(src),formula_sha256=sha(FORMULA),
      output_sha256=sha(sp),input_cutoff=END,full_warm_start=str(f.index.min())if len(f)else None,
```

strong的export_scores.py在21–25行取得同一函数；72–81行为首次生成分支，55–70行为已存在缓存的校验/复用/日历reindex。不能因为存在调用代码便说每次导出都重算，更不能说资金运行现场重算。该区别在lineage JSON分别记录。

## PVR：r、u、b、e、E、score及ready/reset

下面保留的是逐字抽取的原函数。生成器绑定该函数SHA；当前运行只读已冻结score缓存。公式计算不读取I、E0、持仓或未来结果，原决策CLOSE消费截至当日的缓存score。

实际score导出器固定函数源：[原文件第10行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/export_scores.py:10)（摘录10–12行）。

```python
P = W/'pvr-current-v3-information-capital-20261101'
FORMULA = P/'original_score_function.py'
EXPECTED = '9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
```

导出器返回的真实函数名：[原文件第21行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/export_scores.py:21)（摘录21–25行）。

```python
def original():
    assert sha(FORMULA) == EXPECTED
    env = dict(np=np, pd=pd)
    exec(compile(FORMULA.read_text(), str(FORMULA), 'exec'), env)
    return env['score']
```

原PVR完整score函数：[原文件第1行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-current-v3-information-capital-20261101/original_score_function.py:1)（摘录1–19行）。

```python
def score(f):
 """Independent finite-window calculation, no state/account/future input."""
 out=pd.DataFrame(index=f.index,columns=['r','scale','amount_ref','u','b','e','E','score'],dtype=float)
 valid=(f.close.gt(0)&np.isfinite(f.close)&f.amount.gt(0)&np.isfinite(f.amount))
 for k in ['price_eligible','observed_bar','is_observed_bar']:
  if k in f:valid &= f[k].fillna(False).astype(bool)
 for k in ['source_invalid','synthetic_event_bar']:
  if k in f:valid &= ~f[k].fillna(True).astype(bool)
 # Invalid rows and declared source changes restart the full preparation.
 seg=f.segment_id if 'segment_id' in f else pd.Series(0,index=f.index)
 block=((~valid)|(~valid.shift(fill_value=False))|seg.ne(seg.shift())).cumsum()
 weights=.9**np.arange(20,-1,-1);weights/=weights.sum()
 for _,g in f.loc[valid].groupby(block[valid],sort=False):
  r=np.log(g.close).diff();s=r.abs().shift().rolling(63,min_periods=63).median().mul(1.4826).clip(lower=1e-8)
  ar=g.amount.shift().rolling(21,min_periods=21).median()
  u=np.tanh(r/s);b=np.tanh(np.log(g.amount/ar));e=u*(1+.5*u.abs()*b)
  z=e.rolling(21,min_periods=21).apply(lambda x:np.dot(weights,x),raw=True)
  out.loc[g.index]=pd.DataFrame({'r':r,'scale':s,'amount_ref':ar,'u':u,'b':b,'e':e,'E':z,'score':50+50*np.tanh(2*z)},index=g.index)
 return out
```

变量逐字解释：r为当前log收益；scale=s为前63个abs(r)中位数×1.4826；amount_ref=ar为前21个amount中位数。u=tanh(r/s)，b=tanh(log(amount/ar))，e=u×(1+.5×abs(u)×b)。量因子括号为正，所以它调当前e的幅度、不把当前收益方向翻号。E是最近21个e的有限窗口点积，权重.9**[20,…,0]再归一化，最新项权重最高；**不是无限EWMA**。score=50+50×tanh(2E)，不是成功率或资金流金额。E由21项组成，今日r为负时E仍可正，不代表今日负收益被量因子翻成正。

准备与重启就在函数里：close/amount必须正且finite；存在price_eligible/observed_bar/is_observed_bar时逐项AND；source_invalid/synthetic_event_bar逐项排除。无效行或segment变化切新block，重新累足滚动窗口。函数没有ready列；未形成score为NaN，native读取非finite/缺日期返回None。PVR不ready不会在wrapper中自动删掉已生成的合格pending股票，而是保其原slot。

FrozenScores实际读取及缺分返回：[原文件第25行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:25)（摘录25–40行）。

```python
class FrozenScores:
    def __init__(self, path):
        self.path = str(Path(path).resolve()); self.manifest_sha256 = sha(path)
        m = json.loads(Path(path).read_text())
        assert m['stocks'] == len(set(m['fixed_stock_ids'])) == 1709
        self.values = {}
        for r in m['entries']:
            p = Path(path).parent/'scores'/f"{r['symbol']}.parquet"
            assert sha(p) == r['output_sha256']
            f = pd.read_parquet(p)
            assert f.index.is_unique
            self.values[r['symbol']] = MappingProxyType({str(t.date()): float(v) for t, v in f.score.items()})
        self.values = MappingProxyType(self.values)
    def at(self, sid, day):
        v = self.values.get(sid, {}).get(day)
        return v if v is not None and math.isfinite(v) else None
```

## 当前排序：先有原pending，再换股票slot

原J在CLOSE先计算S0资格、CORE/mobile角色、ACT/pending屏障、报价/保护与最小单位，能够留下的才进a.pending。此时原排序键来自sd[sid].rank（原H1），不是后来追加的PVR_score。`continuing`在调用S0前把Security的buy_allowed替换成market buyable；不是跳过其它S0条件。

原J先做S0资格和全股H1次序：[原文件第214行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:214)（摘录214–220行）。

```python
  clock,stocks,sectors=self.facts.packet(at,'I');sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};buyable=self.market.market_buyable(at);day=pd.Timestamp(at.date());event={};continuing={}
  for sid,s in sd.items():
   row=self.facts.row(sid,at);key=(bool(row.i_target),int(row.segment_id)) if row is not None else (False,-1)
   if self.last_epoch.get(sid)!=key:self.epoch[sid]+=1;self.global_watch.pop(sid,None);self.last_epoch[sid]=key
   ep=(key[1],self.epoch[sid]);event[sid]=BP.A.eligibility(s,ss,clock,'S0');continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
   if event[sid].q is True:self.global_watch[sid]=ep
  ordered=sorted(sd,key=lambda sid:(-(sd[sid].rank.read(clock) if sd[sid].rank and sd[sid].rank.read(clock) is not None else -1),sid))
```

原J角色、屏障与pending形成：[原文件第242行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:242)（摘录242–258行）。

```python
   for rank,sid in enumerate(ordered):
    cpr=self.receipts[sid].get(gidday(at));roles=[];why=[];held=bool(a.quantity(sid));epoch=self.global_watch.get(sid);sector=self.sector_by_sid[sid]
    if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
    if cpr and continuing[sid].q is True:roles.append('mobile')
    if not a.risk_state['on']:why.append('ACT_paused')
    if sid in a.exits:why.append('exit_pending')
    if sid in a.buys:why.append('buy_pending')
    if event[sid].q is not True and not (cpr and continuing[sid].q is True):why.extend(event[sid].reasons or ['no_fresh_signal_or_Q'])
    self.opportunities.append(dict(account=a.label,day=gidday(at),sid=sid,sector=sector,rank=rank,core_Q=event[sid].q,mobile_Q=continuing[sid].q,CP1_id=cpr['receipt_id'] if cpr else None,roles=roles,held=held,barriers=why))
    if why or not roles:continue
    q=self.market.quote(sid,at);floor=self.facts.floor(sid,at,'I')
    if q is None or floor is None:continue
    for role in roles:
     fline=max(floor,D(str(self.cp[sid].loc[day,'candidate']))) if role=='mobile' else floor;budget=min(a.current_nav*D('.02'),max(Z,a.current_nav*D('.1')-a.quantity(sid)*q.raw_price));i=dict(sid=sid,clock=clock,quote=q,budget=budget,cap=q.quantity.buy_floor(int(budget/q.raw_price)),weight=1.,group=0,score=sd[sid].rank.read(clock),kind='add' if role=='mobile' else 'core',role=role,floor=fline,epoch=epoch,reason='fresh_CP1_mobile' if role=='mobile' else 'I_early_core',rank=rank,CP1_id=cpr['receipt_id'] if role=='mobile' else None,CP1_trace=cpr if role=='mobile' else None)
     if role=='core':LR.resize_core(i,a.current_nav,self.facts.factor(sid,at))
     if not i.get('size_reject') and i['cap']>0:a.pending.append(i)
     else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=role,result=i.get('size_reject','no_nominal_gap')))
```

PVR wrapper在原planning完成后运行：[原文件第115行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:115)（摘录115–120行）。

```python
    def planning(self, at):
        J.Runner.planning(self, at)
        if self.rank_mode == 'H1': return
        for a in self.accounts.values():
            log = apply_priority(a, SCORES.at, str(at.date()))
            self.rank_log.extend(dict(account=a.label, **r) for r in log)
```

一股一个原slot的PVR替换算法：[原文件第47行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:47)（摘录47–74行）。

```python
def priority_plan(intents, score_at, day):
    """Pure planning: preserve unique-stock original slots, not role slots."""
    ordered = sorted(intents, key=lambda i: (i['rank'], i['role'] != 'core'))
    original = []; rank = {}; roles = {}
    for i in ordered:
        sid = i['sid']
        if sid not in rank:
            original.append(sid); rank[sid] = i['rank']; roles[sid] = []
        assert rank[sid] == i['rank'], ('inconsistent same-stock original key', sid)
        assert i['role'] not in roles[sid], ('duplicate native role', sid)
        roles[sid].append(i['role'])
    assert len(set(rank.values())) == len(rank), 'original stock priority keys must be unique'
    values = {s: score_at(s, day) for s in original}
    values = {s: float(v) if v is not None and math.isfinite(v) else None for s, v in values.items()}
    ready = [s for s in original if values[s] is not None]
    oldpos = {s: n for n, s in enumerate(original)}
    ready.sort(key=lambda s: (-round(values[s], 12), oldpos[s]))
    ready_iter = iter(ready)
    final = [s if values[s] is None else next(ready_iter) for s in original]
    assert set(final) == set(original) and len(final) == len(original)
    assert all(final[n] == s for n, s in enumerate(original) if values[s] is None)
    # Retain original numeric slot keys (including full-universe rank gaps).
    slots = [rank[s] for s in original]
    keys = {s: slots[n] for n, s in enumerate(final)}
    finalpos = {s: n for n, s in enumerate(final)}
    return keys, [dict(sid=s, day=day, original_H1_rank=rank[s], priority_rank=keys[s],
                      original_slot=oldpos[s], final_slot=finalpos[s], PVR=values[s],
                      PVR_ready=values[s] is not None, roles=roles[s]) for s in original]
```

只替rank兼容键，原字段如何保留：[原文件第76行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:76)（摘录76–91行）。

```python
def apply_priority(account, score_at, day):
    """Only rank keys change; original target/price/floor/role/receipt stay exact."""
    keys, log = priority_plan(account.pending, score_at, day)
    before = [{k: v for k, v in i.items() if k != 'rank'} for i in account.pending]
    d = account.decisions[-1]
    assert str(d['at'])[:10] == day
    by = {r['sid']: r for r in log}
    added = {'original_H1_rank', 'priority_rank', 'PVR_score', 'PVR_ready', 'priority_policy'}
    for i in account.pending+d['intents']:
        r = by[i['sid']]
        i.update(original_H1_rank=r['original_H1_rank'], priority_rank=keys[i['sid']],
                 PVR_score=r['PVR'], PVR_ready=r['PVR_ready'], priority_policy=POLICY)
        # Compatibility alias consumed by the UNCHANGED native opening sort.
        # The original H1 key/score and explicit frozen new key remain separate.
        i['rank'] = i['priority_rank']
    assert before == [{k: v for k, v in i.items() if k != 'rank' and k not in added} for i in account.pending]
```

具体规则：先按原(rank, role!=core)把同股角色合在一个股票slot；有PVR者按−round(PVR,12)降序，同分保原slot次序；缺PVR股票留原位置。只在有分的原位置之间替换，复用原数字slot（可含全市场rank空隙）。同股CORE/mobile取得同一priority_rank；原score、floor、cap、budget、role、receipt不因PVR重写。原H1显式保存在original_H1_rank，新PVR标量保存在PVR_score，rank只是新priority_rank的兼容别名。

## 下一OPEN：CORE优先的准确含义

原OPEN真实排序和done时点：[原文件第302行](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:302)（摘录302–323行）。

```python
 def opening(self,a,at):
  C.activate(a)
  for sid in sorted(a.exits):
   win=self.market.window(sid,at,'sell',1)
   if win:a.fill_exit(sid,win)
  a.settle_due(at);a.sync(at);funded=[];done=set()
  for i in sorted([i for i in a.pending if i['clock'].earliest_execution_at==at],key=lambda x:(x['rank'],x['role']!='core')):
   sid=i['sid']
   if sid in done or sid in a.buys or sid in a.exits:continue
   raw=self.market.raw[sid];day=pd.Timestamp(at.date())
   if day not in raw.index or not np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='missing_open'));continue
   x,why=LR.preview(i,D(str(raw.loc[day].open)),self.facts.factor(sid,at),self.market.quantity(sid,at),self.market.fees(sid,at))
   if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
   x['known_open']=D(str(raw.loc[day].open))
   route,why=self.route(a,i,x,at)
   if why:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result=why));continue
   q,pool=route;a.reserve_quantity(i,q,x['price'],x['schedule'],at);a.sync(at);done.add(sid);funded.append((sid,i,x,q));self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='reserved',pool=pool,shares=q,price=x['price'],CP1_id=i.get('CP1_id')))
  # Execution proxies are consulted only after all H1-ranked funding decisions.
  for sid,i,x,q in funded:
   win=self.market.window(sid,at,'buy',1)
   if win:assert win.execution_price==x['price'];a.fill_buy(sid,win)
   else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=i['role'],result='no_execution_window_after_reservation'))
```

下一OPEN先处理原退出、settlement/sync，再按冻结(rank,role!=core)逐意图；因此同股CORE先试。CORE若preview/route失败且未成功预留，同股mobile后续仍可被尝试。任何角色reserve成功就立即done.add(sid)，发生在真实buy fill之前；即使随后没有execution window，不能当同OPEN又有一个mobile补买slot。所有资金预留结束后才查执行代理，不在OPEN重算当天未来CLOSE的PVR。

## S0行业资格与行业排序不是同一次调用

当前J调用的是eligibility(...,S0)，因此行业当日观察、行业RS ready/fresh、行业trend_up仍是资格条件。它不等于调用原通用_priority。

S0资格中的行业条件：[原文件第201行](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py:201)（摘录201–220行）。

```python
    stock_up = _bool_fact(s.trend_up, clock)
    checks = {'common_ready': common, 'buy_allowed': buy,
              'cap_above_10bn': None if cap is None else cap > 10_000_000_000,
              'stock_up': stock_up,
              'issuer_known': True if issuer is not None else None,
              'sector_known': True if sector is not None and sector in sectors else None}
    checks['stock_rs_ready_fresh'] = True if s.rank and s.rank.read(clock) is not None else None
    if variant != 'T0':
        sector_object=sectors.get(sector)
        trend_at=sector_object.trend_up.observed_at if sector_object else None
        checks['sector_observed_today'] = True if trend_at and trend_at.date()==clock.session_date else None
        if variant in ('S0','S1'):
            checks['sector_rs_ready_fresh'] = True if sector_object and sector_object.rank and sector_object.rank.read(clock) is not None else None
        checks['sector_up'] = (None if sector not in sectors
                               else _bool_fact(sectors[sector].trend_up, clock))
    unknown = tuple(k + ':unknown' for k, v in checks.items() if v is None)
    failed = tuple(k + ':false' for k, v in checks.items() if v is False)
    # Unknown is retained even if a separate known component is false.
    q = None if unknown else not failed
    return Eligibility(s.security_id, issuer, sector, q, unknown + failed)
```

通用S0/S1行业RS排序与轮转函数：[原文件第230行](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py:230)（摘录230–248行）。

```python
def _priority(ids: Iterable[str], securities: Mapping[str, Security],
              sectors: Mapping[str, Sector], resolved: Mapping[str, Eligibility],
              clock: Clock, variant: Variant, fallbacks: list[str], batch: str) -> list[str]:
    ids = sorted(ids)
    stock_scores = {i: securities[i].rank.read(clock) if securities[i].rank else None for i in ids}
    if variant not in ('S0', 'S1'):
        return _ordered(ids, stock_scores, batch + ':stocks', fallbacks)
    groups: dict[str, list[str]] = defaultdict(list)
    for i in ids:
        groups[resolved[i].sector_id].append(i)
    sector_scores = {g: sectors[g].rank.read(clock) if sectors[g].rank else None for g in groups}
    sector_order = _ordered(groups, sector_scores, batch + ':sectors', fallbacks)
    queues = {g: _ordered(groups[g], stock_scores, batch + ':stocks:' + g, fallbacks)
              for g in sector_order}
    result = []
    # First stock from each sector, then second; capacity is applied separately.
    for n in range(max((len(v) for v in queues.values()), default=0)):
        result.extend(queues[g][n] for g in sector_order if n < len(queues[g]))
    return result
```

通用`decide`在 [365行](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py:365)对continuing调用_priority，在 [382行](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py:382)对waiting调用_priority；在那里S0/S1才按行业RS顺序、每行业第一股后第二股轮转。当前J.planning的实际代码则是本件上方214–220行的eligibility加全股H1 ordered，再由PVR_SLOT1换slot；该函数体没有调用`decide`或`_priority`。行业仍影响资格和后续资金/风险门，不能据此声称当前资金优先级先按行业RS轮转。

## 状态与时钟小表

| 时点 | 之前状态 | 本步动作 | 之后保存 |
|---|---|---|---|
| 市场CP某CLOSE | phase/anchor/frontier/冻结scale/credit | 原分支reset或新frontier累credit，判断receipt | used_*与next_*分开 |
| PVR某CLOSE | 同有效block此前滚动观察 | 原r/u/b/e，有限21项E与score | 缺准备仍NaN；不使用账户状态 |
| 原J同CLOSE | 旧持仓线、ACT、epoch和原intent资源 | 先退出/旧线检查，再角色与size，形成pending | 原H1 rank及冻结订单字段 |
| N同CLOSE结束 | 原pending已完成 | unique-stock slot间替换PVR rank | 冻结priority_rank与原H1/PVR字段 |
| 下一合法OPEN | 原pending和旧退出/现金责任 | 先退出结算，再CORE优先预留，成功即done；最后实际fill | 实际成交/未成交及现金账，非当日新score |

本件只读代码，不报告新统计、胜率、候选效果或改进方案。源文件逐字摘录由EXCERPT_INDEX.json定位；SOURCE_SHA256.json绑定全文。
