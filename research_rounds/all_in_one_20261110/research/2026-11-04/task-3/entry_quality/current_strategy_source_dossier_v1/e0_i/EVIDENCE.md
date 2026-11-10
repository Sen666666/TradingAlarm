# 当前No60：E0实际生成到I_target/i_buy源码证据

范围：仅摘录当前缓存实际调用链和原公式；未导入或执行模型、账户、指标重算或新统计。每段原文10–35行，左侧数字是源文件实际行号。完整SHA与既有freeze/manifest绑定见SOURCE_SHA256.json。

当前缓存并非直接采用prepared旧participation.target：cache.py:26固定decline_candidate=False，再以同事件重建base E0；当前I采用G1_I，非旧IX_target。下列片段按实际数据流排列。

## 01 当前两窗口入口

来源：[/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/load_inputs.py:14](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/trend_exit_controls_v1/load_inputs.py:14)；原文范围 14–39。

```python
  14 def inputs(window):
  15  if window=='2022_2024':
  16   # This loader does not import an old account/checkpoint or annual continuation class.
  17   value=D.inputs();shared,receipts,cp,states,ir,identity=value
  18   manifests=[W/'2022-normal-reference-20261031/inputs/MANIFEST.json',W/'recovery-2023-readiness-20261101/inputs/MANIFEST.json',D.O/'inputs/MANIFEST.json']
  19   receipts={sid:{} for sid in receipts};ir={};binding={}
  20   for mp in manifests:
  21    binding[str(mp)]=sha(mp)
  22    for rec in json.loads(mp.read_text()):
  23     p=Path(rec['output_path']);assert sha(p)==rec['output_sha256'];binding[str(p)]=rec['output_sha256']
  24     for r in json.loads(p.read_text()):
  25      sid=rec['sid'];day=r['confirmed_day']
  26      if sid in receipts:
  27       assert day not in receipts[sid];receipts[sid][day]=r
  28      else:
  29       key=sid+'|'+day;assert key not in ir;ir[key]=r
  30   for sid,df in cp.items():assert len(receipts[sid])==int(df.loc['2022-01-01':'2024-12-31'].receipt.eq(True).sum())
  31   J.START='2022-01-01';J.END='2024-12-31';score=D.O/'SCORES_MANIFEST.json'
  32   identity=dict(identity,window=[J.START,J.END],receipt_union_sources=binding,stock_canonical_receipts=sum(map(len,receipts.values())),industry_canonical_receipts=len(ir),score_manifest_sha256=sha(score),no_account_state_import=True)
  33  else:
  34   assert window=='strong';old=A.S.O
  35   try:A.S.O=O/'input_readiness';shared,receipts,cp,states,ir,identity=A.S.inputs('2025_26')
  36   finally:A.S.O=old
  37   J.START='2025-07-01';J.END='2026-06-30';score=W/'pvr-slot1-native-readiness-20261101/SCORES_MANIFEST.json'
  38  N.configure_scores(score)
  39  return shared,receipts,cp,states,ir,identity
```

**变量：** window选择2022_2024或strong；shared内含同一market/facts对象。

**时钟：** 加载既有缓存；不在OPEN或每个账户重算信号。

**前后状态：** 2022_2024调D.inputs；strong调A.S.inputs；最后只configure既有rank scores。

## 02 2022—24实际facts安装

来源：[/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/loader_2024.py:31](/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/loader_2024.py:31)；原文范围 31–50。

```python
  31 def inputs():
  32  begun=time.monotonic();assert_data()
  33  sm=read(L.U/'STOCK_MANIFEST.json');im=read(L.U/'INDUSTRY_MANIFEST.json')
  34  fixed=read(L.U/'FREEZE.json')['stocks'];manifest=read(O/'inputs/MANIFEST.json');new={r['sid']:r for r in manifest}
  35  assert len(sm)==len(fixed)==1709 and len(im)==90 and len(new)==1799
  36  full={};cp={};receipts={}
  37  for r in sm:
  38   sid=r['symbol'];rec=new[sid];assert rec['original_output_sha256']==r['output_sha256']
  39   for p,h in r['output_sha256'].items():assert sha(p)==h,('numeric cache changed',p)
  40   assert sha(rec['output_path'])==rec['output_sha256']
  41   f=pd.read_parquet(r['refs']['facts']).loc[:END];q=pd.read_parquet(r['refs']['CP1_input']).loc[:END];z=pd.read_parquet(r['refs']['CP1']).loc[:END]
  42   assert f.index.equals(q.index)and q.index.equals(z.index)
  43   for k in ['close','segment_id','i_target','i_floor']:pd.testing.assert_series_equal(f[k],q[k],check_exact=True,check_dtype=False,check_freq=False)
  44   rr=read(rec['output_path']);assert len(rr)==int(z.loc[START:END].receipt.eq(True).sum())
  45   full[sid]=f;cp[sid]=z;receipts[sid]={x['confirmed_day']:x for x in rr}
  46  # The unchanged original context loads price/action/H1/execution inputs.
  47  shared=J.M.context(END,ids=fixed);bundle,market,facts=shared
  48  assert set(market.lines)==set(fixed)=={x.security_id for x in bundle.lines}
  49  for sid,f in full.items():
  50   facts.f[sid]=f;bundle.series[sid].states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
```

**变量：** sm=STOCK_MANIFEST；r.refs.facts是full warm历史facts；f.i_target/i_floor须与CP1_input逐值一致。

**时钟：** 账户构造前read_parquet并截END。

**前后状态：** facts.f[sid]=f；bundle的E0 ready/target view同源替换。

## 03 strong入口只调用原inputs

来源：[/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/execution_support.py:16](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/execution_support.py:16)；原文范围 16–31。

```python
  16 def inputs(window):
  17     start, end, cut = WINDOWS[window]
  18     sys.path.insert(0, str(W/'q2-normal-continuation-20261031'))
  19     import continuation as E
  20     if window == '2022':
  21         Y = J.W.load('PVR_SLOT1_frozen_2022_input_loader', W/'2022-normal-reference-20261031/adapter.py')
  22         old = Y.save
  23         try:
  24             Y.save = lambda path, value: IO.write_json(O/'input-readiness'/window/Path(path).name, J.W.canon(value))
  25             value = Y.inputs()
  26         finally: Y.save = old
  27     else:
  28         J.START, J.END = start, end
  29         value = E.inputs('universe')
  30     J.START, J.END = start, end
  31     return value
```

**变量：** E为q2-normal-continuation；2025_26调用E.inputs(universe)。

**时钟：** 加载输入时，不调用Continuation.import_verified_legacy。

**前后状态：** 当前BASELINE RUN_METADATA声明fresh_cash/no_checkpoint_import，不能把这个inputs别名误作旧账户续接。

## 04 strong inputs别名真实生成处

来源：[/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/q2-normal-continuation-20261031/continuation.py:1](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/q2-normal-continuation-20261031/continuation.py:1)；原文范围 1–18。

```python
   1 """Original normal policies, explicit verified legacy import, Q2 input horizon."""
   2 from pathlib import Path
   3 import sys,inspect,textwrap,copy,pickle,json,gzip,hashlib,math
   4 from dataclasses import is_dataclass,fields
   5 import numpy as np,pandas as pd
   6 O=Path(__file__).resolve().parent;END='2026-06-30';PARENT_END='2026-03-31'
   7 sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'))
   8 import pressure_runner as R
   9 from initialization_guard import IO
  10 J=R.J;L=R.L;BASE=R.BASE
  11 
  12 INPUT_SOURCE=textwrap.dedent(inspect.getsource(L.inputs))
  13 assert INPUT_SOURCE.count('J.END')==10
  14 INPUT_SOURCE=INPUT_SOURCE.replace('J.END','END')
  15 old="if old5.exists():assert states[sid]==read(old5),'Parquet state view differs from original case JSON'"
  16 new="if old5.exists():\n   previous=read(old5);old_end=max(x['day'] for x in previous);assert [x for x in states[sid] if x['day']<=old_end]==previous,'Legacy case state prefix changed'"
  17 assert INPUT_SOURCE.count(old)==1;INPUT_SOURCE=INPUT_SOURCE.replace(old,new)
  18 env=dict(L.__dict__,END=END);exec(INPUT_SOURCE,env);inputs=env['inputs']
```

**变量：** L来自pressure_runner引用的BASE.L；INPUT_SOURCE是L.inputs原函数源码。

**时钟：** 只将输入函数中J.END替换为END=2026-06-30。

**前后状态：** inputs=env[inputs]仍是下段launch_v3.inputs的缓存读取体。

## 05 strong缓存读取体

来源：[/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/launch_v3.py:14](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/launch_v3.py:14)；原文范围 14–38。

```python
  14 def inputs(scope):
  15  """Only read verified original/cache inputs; never derive new indicators."""
  16  freeze=read(U/'FREEZE.json');sm=read(U/'STOCK_MANIFEST.json');im=read(U/'INDUSTRY_MANIFEST.json')
  17  fixed=freeze['stocks'];assert len(fixed)==len(set(fixed))==1709
  18  case=read(W.CACHE/'MANIFEST.json');case_ids={x['sid'] for x in case if x['status']=='complete'}
  19  assert len(case_ids)==77
  20  ids=fixed if scope=='universe' else [s for s in fixed if s in case_ids]
  21  stock={r['symbol']:r for r in sm};industry={r['series']:r for r in im};fullfacts={};cp={};receipts={}
  22  for sid in ids:
  23   r=stock[sid]
  24   assert r['status'] in ('complete','not_applicable_no_local_observation_by_end')
  25   for path,h in r['output_sha256'].items():assert sha(path)==h,('changed cache',path)
  26   fullfacts[sid]=pd.read_parquet(r['refs']['facts']).loc[:J.END]
  27   cp[sid]=pd.read_parquet(r['refs']['CP1']).loc[:J.END]
  28   receipts[sid]={x['confirmed_day']:x for x in read(r['refs']['receipts']) if J.START<=x['confirmed_day']<=J.END}
  29   assert len(receipts[sid])==sum(bool(x) for x in cp[sid].loc[J.START:J.END,'receipt'])
  30   native=pd.read_parquet(J.BASE.parent/'native-I-cache-interface-20261031/facts'/f'{sid}.parquet').loc[J.START:J.END]
  31   current=fullfacts[sid].loc[J.START:J.END,native.columns]
  32   aa=current.copy(deep=False);bb=native.copy(deep=False)
  33   aa.index=aa.index.as_unit('ns');bb.index=bb.index.as_unit('ns')
  34   pd.testing.assert_frame_equal(aa,bb,check_exact=True,check_dtype=False,check_freq=False)
  35  shared=J.M.context(J.END,ids=ids);bundle,market,facts=shared
  36  assert {l.security_id for l in bundle.lines}==set(ids)==set(market.lines)
  37  for sid,f in fullfacts.items():
  38   facts.f[sid]=f;bundle.series[sid].states=f[['e0_ready','e0_target','segment_id']].rename(columns={'e0_ready':'ready','e0_target':'target'})
```

**变量：** U为universe-cp1-inputs；refs.facts和CP1等输出SHA逐项核；native比对用同字段。

**时钟：** 读取全warm缓存后截原END；不是当日运行模型。

**前后状态：** fullfacts安装到facts.f；原e0_ready/e0_target进入bundle view。

## 06 STOCK_MANIFEST输出的真实生产分支

来源：[/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/prepare.py:20](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/prepare.py:20)；原文范围 20–40。

```python
  20 def emit_stock(sid,case,prefix_sample):
  21  start=time.monotonic();refs={};checks={};old_source_status=None;CP_reuse=False;facts_reuse=False
  22  if case is not None:
  23   assert all(sha(p)==h for p,h in case['source_sha256'].items())
  24   assert all(sha(W/'case-stock-cp1-warmup-20261031'/p)==h for p,h in case['output_sha256'].items())
  25   root=W/'case-stock-cp1-warmup-20261031';refs=dict(facts=str(root/'full-facts'/f'{sid}.parquet'),CP1_input=str(root/'CP1-input'/f'{sid}.parquet'),CP1=str(root/'CP1'/f'{sid}.parquet'));f=pd.read_parquet(refs['facts']).loc[:END];q=pd.read_parquet(refs['CP1_input']).loc[:END];z=pd.read_parquet(refs['CP1']).loc[:END];source_hash=case['source_sha256'];CP_reuse=facts_reuse=True;checks['previous_case_full_chain_verified']=True;mode='verified_case_reuse'
  26  else:
  27   f,receipt=N.derive(sid,END);paths=source_paths(sid);source_hash={str(p):sha(p) for p in paths.values()};native=pd.read_parquet(W/'native-I-cache-interface-20261031/facts'/f'{sid}.parquet').loc[BEGIN:END];G.exact(f.loc[BEGIN:END],native);checks['native_I_export_all_fields_exact']=True;q=G.frame(sid,f,END);z=M.calculate(q);old=C.O/'signals'/f'{sid}.parquet';mode='new_fixed_chain'
  28   if old.exists():
  29    try:
  30     G.exact(q,C.frame(sid,END));G.exact(z,pd.read_parquet(old).loc[:END]);refs['CP1']=str(old);CP_reuse=True;old_source_status='full_input_and_CP1_exact';checks['old_CP1_current_source_exact']=True
  31     oldfacts=C.PREP/'facts'/f'{sid}.parquet';ff=pd.read_parquet(oldfacts)
  32     if set(N.COLS)<=set(ff):G.exact(f,ff.loc[:END,N.COLS]);refs['facts']=str(oldfacts);facts_reuse=True
  33    except (AssertionError,ValueError,FileNotFoundError) as e:old_source_status='incompatible_or_unavailable:'+str(e)[:350]
  34   if 'facts' not in refs:
  35    path=O/'facts'/f'{sid}.parquet';f.to_parquet(path);refs['facts']=str(path)
  36   path=O/'CP1-input'/f'{sid}.parquet';q.to_parquet(path);refs['CP1_input']=str(path)
  37   if 'CP1' not in refs:
  38    path=O/'CP1'/f'{sid}.parquet';z.to_parquet(path);refs['CP1']=str(path)
  39   if sid in prefix_sample and not f.empty:
  40    short,_=N.derive(sid,CUT);G.exact(short,f.loc[:CUT]);G.exact(M.calculate(G.frame(sid,short,CUT)),z.loc[:CUT]);checks['physical_I_CP1_prefix_exact']=True
```

**变量：** 已核case分支复用原full-facts；其它分支N.derive(sid,END)，并与原native-I导出对比。

**时钟：** 生成市场缓存时使用全warm历史；账户只读取输出。

**前后状态：** facts路径和SHA写入manifest；没有新账户state。

## 07 N.derive与缓存复用的模块绑定

来源：[/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stock-cp1-warmup-20261031/generate.py:1](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stock-cp1-warmup-20261031/generate.py:1)；原文范围 1–27。

```python
   1 """Frozen case stock inputs and market CP1 only; no account runner."""
   2 from pathlib import Path
   3 import sys,time,json,importlib.util,hashlib
   4 import numpy as np,pandas as pd
   5 O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');BEGIN='2025-07-01';END='2026-06-30';CUT='2025-12-31'
   6 def load(n,p):
   7  s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
   8 N=load('case79_original_native_cache',W/'native-I-cache-interface-20261031/cache.py');M=load('case79_original_CP1',RR/'continuous-protection-lines-20261028/code/model.py');C=load('case79_original_common',RR/'continuous-protection-lines-20261028/code/common.py')
   9 def norm(x):
  10  if isinstance(x,dict):return {str(k):norm(v) for k,v in x.items()}
  11  if isinstance(x,(list,tuple)):return [norm(v) for v in x]
  12  if isinstance(x,np.generic):return norm(x.item())
  13  if isinstance(x,float) and not np.isfinite(x):return None
  14  return x
  15 def save(n,x):
  16  x=norm(x);(O/(n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
  17  if isinstance(x,list) and x:pd.DataFrame(x).to_csv(O/(n+'.csv'),index=False)
  18 def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
  19 def exact(a,b):
  20  # Parquet stores the same calendar timestamps at s or ms precision. Normalize
  21  # comparison copies only; never change prices, states or persisted source data.
  22  aa=a.copy(deep=False);bb=b.copy(deep=False);aa.index=a.index.as_unit('ns');bb.index=b.index.as_unit('ns');pd.testing.assert_frame_equal(aa,bb,check_exact=True,check_dtype=False,check_freq=False)
  23 def frame(sid,f,cut):
  24  if f.empty:
  25   return pd.DataFrame({'close':pd.Series(dtype=float),'segment_id':pd.Series(dtype=int),'i_target':pd.Series(dtype=bool),'i_floor':pd.Series(dtype=float),'amount':pd.Series(dtype=float),'e0_down':pd.Series(dtype=bool),'e0_valid':pd.Series(dtype=bool)},index=f.index)
  26  rec=N.RECORDS[sid];sig=pd.read_parquet(N.OLD/rec['files']['signal']['path']).loc[:cut];ev=pd.read_parquet(N.OLD/rec['files']['events']['path']).reindex(f.index);out=f[['close','segment_id','i_target','i_floor']].copy();out['amount']=sig.amount.reindex(f.index);out['e0_down']=ev.event.eq(-1);out['e0_valid']=f.i_target.astype(bool)
  27  if not np.isfinite(out[['close','amount']]).all().all() or not out[['close','amount']].gt(0).all().all():raise ValueError('missing/nonpositive same-source CP1 price or amount; no row removal allowed')
```

**变量：** N显式load native-I-cache/cache.py；M是CP model，C是CP common。

**时钟：** 生成缓存的静态模块绑定。

**前后状态：** frame为CP输入映射；I/E0事实本身由N.derive提供，不由CP模型生成。

## 08 当前E0→I的决定性生产体

来源：[/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/native-I-cache-interface-20261031/cache.py:16](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/native-I-cache-interface-20261031/cache.py:16)；原文范围 16–34。

```python
  16 def derive(sid,cut=END):
  17  start=time.monotonic();rec=RECORDS[sid];paths={k:OLD/rec['files'][k]['path'] for k in ['signal','events','states']}
  18  for k,p in paths.items():assert sha(p)==rec['files'][k]['sha256'],(sid,k)
  19  ip=IX/'signals'/f'{sid}.parquet';assert sha(ip)==IXRECORDS[sid]['output_sha256']
  20  signal=pd.read_parquet(paths['signal']).loc[:cut];x=pd.read_parquet(ip).loc[:cut];event=pd.read_parquet(paths['events']).reindex(x.index);state=pd.read_parquet(paths['states']).reindex(x.index);valid=eligible_prices(signal);assert valid.index.equals(x.index),(sid,'same price-observation clock')
  21  if x.empty:return pd.DataFrame(columns=COLS,index=pd.DatetimeIndex([],name=signal.index.name)),dict(sid=sid,status='no_observation_before_cut',rows=0,seconds=time.monotonic()-start)
  22  for c in ['open','high','low','close','volume','segment_id']:np.testing.assert_equal(x[c].to_numpy(),valid[c].to_numpy(),err_msg=sid+'/'+c)
  23  e=x[['segment_id','open','high','low','close','volume']].copy();e['valid_price_observation']=True;e['price_observation']=e.groupby('segment_id',sort=False).cumcount();e['event']=event.event;e['confirmed_pivot_price']=event.confirmed_pivot_price;e['ready']=state.ready;e['previous_close']=e.groupby('segment_id',sort=False).close.shift()
  24  v=e.volume.where(np.isfinite(e.volume)&e.volume.gt(0));e['volume_baseline']=v.groupby(e.segment_id,sort=False).transform(lambda q:q.shift().rolling(21,min_periods=21).median())
  25  for c in ['volume_ratio','high_effort','declined']:e[c]=state[c]
  26  e['decline_candidate']=False;e['candidate_lower']=np.nan;e['candidate_reclaim']=np.nan
  27  base,_=e0_policy(e);assert not base.pending.fillna(0).any()
  28  g=x[['grade','strength_ready','fresh_up','acute_down']].rename(columns={'strength_ready':'ready'});out=project(e,base,g,'G1_I')
  29  keep=x[['close','segment_id']].copy()
  30  for mode,frame in [('e0',base),('i',out)]:
  31   for c in ['target','floor']:keep[mode+'_'+c]=frame[c]
  32  keep['i_buy']=out.buy_event
  33  for c in ['grade','fresh_up','acute_down','ready']:keep['g_'+c]=g[c]
  34  keep['e0_ready']=base.ready;keep['factor']=signal.adjustment_factor.reindex(keep.index);keep['raw_close']=signal.raw_close.reindex(keep.index);keep=keep[COLS]
```

**变量：** events/state来自prepared-v2；x来自IX已有signals；decline_candidate在这里固定False。

**时钟：** 按cut截取历史；每个index是已完成的价格观察CLOSE。

**前后状态：** base=e0_policy(e)，assert无pending；project G1_I输出target/floor存为i_target/i_floor，buy_event存i_buy。

## 09 原prepared事件文件的写出

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/prepare_states.py:7](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/prepare_states.py:7)；原文范围 7–20。

```python
   7 def worker(args):
   8  n,record,base,scope,output=args
   9  item=build_series(record,Path(base),scope)
  10  directory=Path(output)/f'{n:06d}';directory.mkdir()
  11  files={}
  12  for name in ('signal','events','states','memories'):
  13   frame=getattr(item,name)
  14   if frame is not None:
  15    p=directory/(name+'.parquet');frame.to_parquet(p)
  16    files[name]={'path':str(p.relative_to(output)),'sha256':sha256(p)}
  17  return dict(series_id=record['series_id'],blocked_reason=item.blocked_reason,
  18   raw_rows=len(item.raw) if item.raw is not None else 0,
  19   signal_observations=len(item.states) if item.states is not None else 0,
  20   synthetic_action_rows=int(item.signal.synthetic_event_bar.sum()) if item.signal is not None else 0,files=files)
```

**变量：** build_series产item.signal/events/states/memories；各文件单独SHA。

**时钟：** 离线一次生成原prepared缓存。

**前后状态：** 不是每个交易账户分别运行事件模型。

## 10 原prepared的每source段调用

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py:361](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py:361)；原文范围 361–384。

```python
 361 def build_series(record, base, scope_date):
 362     """Build exactly one input; failure stays attached to its original identity."""
 363     item = SeriesData(record)
 364     try:
 365         if record.get('status') != 'ready':
 366             raise ValueError(record.get('blocked_reason', 'Input coverage is not ready'))
 367         time.fromisoformat(record['close_available_time'])
 368         item.raw = read_raw(checked_ref(record['raw'], base), record)
 369         if item.raw.index[-1] > pd.Timestamp(scope_date):
 370             raise ValueError('Raw input extends beyond frozen round end')
 371         actions, policy = read_actions(record, base)
 372         item.action_policy = policy
 373         signals, events, states, memories = [], [], [], []
 374         for segment_id, part in enumerate(source_segments(item.raw, record)):
 375             raw_part = item.raw.loc[part['start']:part['end']]
 376             signal = prepare_signal(raw_part, record, actions)
 377             _, event, state, memory = state_frame(signal)
 378             for frame in (signal, event, state, memory):
 379                 frame['segment_id'] = segment_id
 380             signals.append(signal); events.append(event); states.append(state); memories.append(memory)
 381         item.signal = pd.concat(signals)
 382         item.events = pd.concat(events)
 383         item.states = pd.concat(states)
 384         item.memories = pd.concat(memories, ignore_index=True)
```

**变量：** 每个source segment分别prepare_signal、state_frame；四种输出均附segment_id。

**时钟：** 完整有界源历史；源段切换在这里分段。

**前后状态：** 每段的事件/参与状态重新开始，再拼成该series缓存。

## 11 保存事件的实际数学入口

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py:224](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py:224)；原文范围 224–237。

```python
 224 def state_frame(signal):
 225     eligible = eligible_prices(signal)
 226     if eligible.empty:
 227         raise ValueError('No eligible price observations')
 228     if not (eligible.volume.gt(0) & np.isfinite(eligible.volume)).any():
 229         raise ValueError('No real positive-volume observations for frozen joint model')
 230     events = event_frame_numeric(eligible.close, eligible.volume, joint=True, event_exit=False)
 231     state, memories = participation_frame(eligible, events, mode='volume')
 232     # Call the frozen formula only for the 253-observation rolling window.
 233     closes = eligible.close.to_numpy()
 234     state['rs'] = pd.Series(
 235         [admission.rs_score(closes[max(0, i-252):i+1]) for i in range(len(closes))],
 236         index=state.index, dtype='float64')
 237     return eligible, events, state, memories
```

**变量：** eligible_prices是价格观察；event_frame_numeric参数joint=True,event_exit=False。

**时钟：** 日线CLOSE序列；RS与事件同段但为不同字段。

**前后状态：** prepared events来自numeric；prepared states来自participation_frame；当前cache只选用其指定列。

## 12 价格观察mask

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/data_utils.py:26](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/data_utils.py:26)；原文范围 26–58。

```python
  26 def eligible_prices(frame, symbol="", exclude_dates=()):
  27     """Return valid price observations without inferring volume or intraday order."""
  28     out = frame.copy()
  29     if "date" in out:
  30         out["date"] = pd.to_datetime(out["date"])
  31         out = out.set_index("date")
  32     out.index = pd.to_datetime(out.index)
  33     if not out.index.is_unique or not out.index.is_monotonic_increasing:
  34         raise ValueError("price input must have unique increasing dates")
  35     ohlc = out[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
  36     finite = np.isfinite(ohlc).all(axis=1) & ohlc.gt(0).all(axis=1)
  37     geometry = (
  38         ohlc.high.ge(ohlc.low)
  39         & ohlc.high.ge(ohlc[["open", "close"]].max(axis=1))
  40         & ohlc.low.le(ohlc[["open", "close"]].min(axis=1))
  41     )
  42     anomaly = (
  43         out.source_anomaly.fillna("").astype(str).str.strip().ne("")
  44         if "source_anomaly" in out else pd.Series(False, index=out.index)
  45     )
  46     keep = (
  47         finite & geometry
  48         & boolean_column(out, "observed_bar", True)
  49         & ~boolean_column(out, "synthetic_event_bar", False)
  50         & ~boolean_column(out, "source_invalid", False)
  51         & ~anomaly
  52         & ~out.index.isin(pd.to_datetime(list(exclude_dates)))
  53     )
  54     out.loc[:, ["open", "high", "low", "close"]] = ohlc
  55     if "volume" not in out:
  56         out["volume"] = np.nan
  57     out["volume"] = pd.to_numeric(out.volume, errors="coerce")
  58     return out.loc[keep].copy()
```

**变量：** 保留有限正OHLC且几何正确、observed、非synthetic、非invalid/anomaly；volume不决定价格保留。

**时钟：** 过滤历史源观察，缺量不等于删除有效价格。

**前后状态：** 返回的index是price clock；后续event clock另筛正且finite C/V。

## 13 signal坐标：权息与原raw字段

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py:170](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py:170)；原文范围 170–195。

```python
 170     declared_observed = boolean_column(source, 'observed_bar', True)
 171     full['observed_bar'] = declared_observed.reindex(full.index).fillna(False).astype(bool)
 172     full['synthetic_event_bar'] = ~full.index.isin(observed)
 173     full['raw_volume'] = full.volume
 174     for col in OHLC:
 175         full['raw_' + col] = full[col]
 176     output = {x: [] for x in OHLC + ('volume', 'adjustment_factor', 'volume_factor')}
 177     with localcontext() as context:
 178         context.prec, context.rounding = 40, ROUND_HALF_EVEN
 179         factor, share_units, previous = Decimal(1), Decimal(1), None
 180         for date, row in full.iterrows():
 181             event = active.get(date)
 182             cash = decimal(event.get('signal_cash_per_old_share', event['cash_per_old_share'])) if event else Decimal(0)
 183             split = decimal(event.get('signal_split_ratio', event['split_ratio'])) if event else Decimal(1)
 184             volume_split = decimal(event.get('volume_split_ratio',event['split_ratio'])) if event else Decimal(1)
 185             is_observed = date in observed
 186             prices = ({k: decimal(row[k]) if pd.notna(row[k]) and np.isfinite(float(row[k])) else None
 187                        for k in OHLC} if is_observed else None)
 188             if event:
 189                 if method == 'unadjusted_index':
 190                     raise ValueError('Index cannot receive stock distribution terms')
 191                 if method == 'theoretical_ex_price':
 192                     if previous is None or previous <= cash:
 193                         raise ValueError('Invalid prior raw price for theoretical ex-price')
 194                     ex_price = (previous - cash) / split
 195                     factor *= previous / ex_price
```

**变量：** raw_OHLC保留；factor/share_units从1开始；theoretical ex price=(previous−cash)/split。

**时钟：** 只在已到effective_date的action上改因子。

**前后状态：** previous为前raw close；本段结束后signal价格是raw×factor，不是下单raw价。

## 14 signal坐标：价格/量输出

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py:196](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py:196)；原文范围 196–221。

```python
 196                     if not is_observed:
 197                         prices = {k: ex_price for k in OHLC}
 198                 elif method == 'total_return':
 199                     if not is_observed:
 200                         raise ValueError('Total-return event requires observed close or reviewed prepared source')
 201                     if prices['close'] is None or prices['close'] <= 0:
 202                         raise ValueError('Total-return event needs a positive finite close')
 203                     if cash != 0 and split != 1:
 204                         raise ValueError('Combined cash/split outside frozen total-return preparation convention')
 205                     factor *= split + cash / prices['close']
 206                 share_units *= volume_split
 207             if prices is None:
 208                 raise ValueError('Synthetic price requires supported explicit event')
 209             for k in OHLC:
 210                 output[k].append(float(prices[k] * factor) if prices[k] is not None else np.nan)
 211             v = (decimal(row.volume) if is_observed and pd.notna(row.volume)
 212                  and np.isfinite(float(row.volume)) else None)
 213             output['volume'].append(float(v / share_units) if v is not None else np.nan)
 214             output['adjustment_factor'].append(float(factor))
 215             output['volume_factor'].append(float(1 / share_units))
 216             if prices['close'] is not None and prices['close'] > 0:
 217                 previous = prices['close']
 218     for key, values in output.items():
 219         full[key] = values
 220     # A synthetic action row is never a market observation or executable price.
 221     return full
```

**变量：** 价格输出prices[k]×factor；volume输出v/share_units；previous随后更新为本raw close。

**时钟：** CLOSE观察含当日已生效权息；synthetic action行不作市场观察。

**前后状态：** factor、volume_factor单独输出供后续raw转换，不改成账户收益。

## 15 numeric比较的原浮点规则

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:15](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:15)；原文范围 15–35。

```python
  15 UNIT_ROUNDOFF = np.finfo(np.float64).eps / 2
  16 # Two input encodings plus one unit multiplication on each side of a comparison.
  17 # A machine-precision comparison policy motivated by that four-rounding model.
  18 # The prior adjustment/serialization pipelines are not certified to obey it.
  19 ROUNDING_STEPS = 4
  20 GAMMA4 = ROUNDING_STEPS * UNIT_ROUNDOFF / (1 - ROUNDING_STEPS * UNIT_ROUNDOFF)
  21 
  22 
  23 def compare(a: float, b: float) -> int:
  24     """Order finite nonnegative magnitudes, treating the gamma4 band as a tie.
  25 
  26     Homogeneous in exact arithmetic. Independent rounded rescaling can move an
  27     input on the band's boundary across it; universal scale invariance is NOT
  28     promised. Comparisons outside this band remain strict.
  29     """
  30     a, b = float(a), float(b)
  31     if not (math.isfinite(a) and math.isfinite(b) and a >= 0 and b >= 0):
  32         raise ValueError("finite nonnegative magnitudes required")
  33     if abs(a - b) <= GAMMA4 * max(a, b):
  34         return 0
  35     return 1 if a > b else -1
```

**变量：** GAMMA4由binary64 unit-roundoff及4步误差模型得；compare返回−1/0/1。

**时钟：** 纯标量运算，无账户时钟。

**前后状态：** 落在机器误差tie band保原极值/原floor；不是金融百分比阈值。

## 16 numeric局部对数与ratchet

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:38](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:38)；原文范围 38–55。

```python
  38 def log_ratio(a: float, b: float) -> float:
  39     """Local log change without subtracting two origin-normalized logarithms."""
  40     a, b = float(a), float(b)
  41     if not (math.isfinite(a) and math.isfinite(b) and a > 0 and b > 0):
  42         raise ValueError("finite positive prices required")
  43     if compare(a, b) == 0:
  44         return 0.0
  45     # log1p preserves a small displacement. The far-down case avoids rounding
  46     # (a-b)/b to -1. At the branch boundary, rounded rescaling can select the
  47     # other algebraically equivalent expression; universal bit equality is not promised.
  48     if 0.5 <= a / b <= 2:
  49         return math.log1p((a - b) / b)
  50     return math.log(a) - math.log(b)
  51 
  52 
  53 def higher(old: float, new: float) -> float:
  54     """The existing ratchet retains its actual old point on a numerical tie."""
  55     return float(new) if compare(new, old) > 0 else float(old)
```

**变量：** log_ratio近比值用log1p，其余用log(a)−log(b)；higher只在strict greater时换值。

**时钟：** 纯数学被原事件/参与层调用。

**前后状态：** 相等/tie保留旧点。

## 17 原E0事件的样本钟与sigma

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:58](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:58)；原文范围 58–80。

```python
  58 def event_frame_numeric(close, volume, joint=True, event_exit=False):
  59     """Numerical repair of frozen event+structure equations, separately named.
  60 
  61     Same observation clock, warmup, 21/63/5 constants, activity clipping,
  62     confirmation >=1, floor <=, and same-day exit priority. Numerical changes:
  63     raw-price extrema/floors with an explicit tie policy; local log returns;
  64     local fsum instead of long cumulative-volume subtraction.
  65     Original output log fields are display only; raw pivot fields are canonical.
  66     """
  67     if not close.index.is_unique or not close.index.is_monotonic_increasing:
  68         raise ValueError("ordered unique index required")
  69     raw = pd.concat([close.rename("close"), volume.rename("volume")], axis=1)
  70     d = raw.loc[raw.gt(0).all(axis=1) & np.isfinite(raw).all(axis=1)]
  71     if d.empty:
  72         raise ValueError("no valid observations")
  73     prices, volumes = d.close.to_numpy(), d.volume.to_numpy()
  74     returns = [math.nan] + [log_ratio(prices[t], prices[t - 1])
  75                               for t in range(1, len(d))]
  76     sigma = np.full(len(d), np.nan)
  77     baseline = d.volume.shift().rolling(21).median().to_numpy()
  78     for t in range(64, len(d)):
  79         sigma[t] = max(math.sqrt(math.fsum(x * x for x in returns[t - 63:t]) / 63), 1e-8)
  80     direction, ext, active, floor = -1, None, False, math.nan
```

**变量：** event clock仅正finite C/V；sigma[t]=max(sqrt(fsum(r[t−63:t]^2)/63),1e−8)；baseline=过去21量median。

**时钟：** t>=64才有尺度；sigma及baseline不含本次量/收益。

**前后状态：** 初始direction=−1,ext=None,active=False；此numeric内部target不是当前cache最终e0_target。

## 18 原E0事件的极值与量修正确认

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:90](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:90)；原文范围 90–114。

```python
  90         if not math.isfinite(sigma[t] + baseline[t]):
  91             rows.append(row)
  92             continue
  93         if ext is None:
  94             ext = t
  95         if active and not event_exit and compare(prices[t], floor) <= 0:
  96             active, row["exited"] = False, 1.0
  97         extreme_order = compare(prices[t], prices[ext])
  98         if (direction == -1 and extreme_order < 0) or (direction == 1 and extreme_order > 0):
  99             ext = t
 100         if t > ext:
 101             activity = math.sqrt(
 102                 (math.fsum(float(x) for x in volumes[ext + 1:t + 1]) / (t - ext))
 103                 / baseline[ext]
 104             ) if joint else 1.0
 105             activity = min(max(activity, 0.5), 2.0)
 106             confirmation = (-direction) * log_ratio(prices[t], prices[ext]) * activity / (math.sqrt(5) * sigma[ext])
 107             row["confirmation"] = confirmation
 108             # A numerically indistinguishable exact threshold is inclusive.
 109             if compare(max(confirmation, 0.0), 1.0) >= 0:
 110                 event = -direction
 111                 pivot = float(prices[ext])
 112                 row.update(event=float(event), confirmed_pivot=math.log(pivot),
 113                            confirmed_pivot_price=pivot, pivot_age=float(t - ext),
 114                            confirmed_pivot_date=str(d.index[ext].date()))
```

**变量：** activity=sqrt(极值之后到t的平均量/baseline[ext])，clamp .5到2；confirmation=(−direction)×log_ratio(Ct,Cext)×activity/(sqrt5×sigma[ext])。

**时钟：** 当日CLOSE与当日volume已完成后判断；ext尺度冻结在极值观察。

**前后状态：** 先检测已有floor；再更新方向所属极值；confirmation>=1时event=−direction，确认pivot为旧ext价格/日期。

## 19 原numeric确认后的状态

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:115](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:115)；原文范围 115–136。

```python
 115                 if event == 1:
 116                     if active:
 117                         floor = higher(floor, pivot)
 118                     elif not row["exited"]:
 119                         active, floor, row["entered"] = True, pivot, 1.0
 120                 elif event_exit and active:
 121                     active, row["exited"] = False, 1.0
 122                 direction, ext = event, t
 123         row.update(leg_direction=float(direction),
 124                    developing_extreme=math.log(float(prices[ext])),
 125                    developing_extreme_price=float(prices[ext]),
 126                    developing_extreme_date=str(d.index[ext].date()), target=float(active))
 127         if active or row["exited"]:
 128             row.update(structure_floor=math.log(floor), structure_floor_price=floor)
 129         rows.append(row)
 130     result = pd.DataFrame(rows, index=d.index).reindex(close.index)
 131     for col in ("event", "entered", "exited"):
 132         result[col] = result[col].fillna(0.0)
 133     result["target"] = result.target.ffill().fillna(0.0)
 134     for col in ("confirmed_pivot_date", "developing_extreme_date"):
 135         result[col] = result[col].astype("string")
 136     return result
```

**变量：** 正event提高floor或在本日未退出时entered；direction/ext更新为event,t。

**时钟：** 同一个CLOSE结束状态。

**前后状态：** event_exit=False下负event本身不触发该numeric结构退出；result事件供后面当前E0 policy使用。

## 20 被cache选用的原state ready/量字段

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/participation.py:17](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/participation.py:17)；原文范围 17–37。

```python
  17     e = events.reindex(bars.index)
  18     v = bars.volume.where(np.isfinite(bars.volume) & bars.volume.gt(0))
  19     volume_base = v.shift().rolling(21, min_periods=21).median()
  20     ratios = v / volume_base
  21     active, floor, pending, previous_close = False, math.nan, None, math.nan
  22     ready = False
  23     next_id = 0
  24     rows, ledger = [], []
  25     for n, (date, bar) in enumerate(bars.iterrows()):
  26         ev = e.loc[date]
  27         price_event = int(ev.event) if pd.notna(ev.event) else 0
  28         ready = ready or bool(pd.notna(ev.leg_direction))
  29         c, low = float(bar.close), float(bar.low)
  30         q = float(ratios.loc[date])
  31         declined = bool(math.isfinite(previous_close) and compare(c, previous_close) < 0)
  32         high_effort = bool(math.isfinite(q) and compare(q, 2.0) >= 0)
  33         entered = exited = created = response = consumed = independent = 0
  34         ended_id = None
  35         entry_kind = ""
  36         if active and compare(c, floor) <= 0:
  37             active, exited = False, 1
```

**变量：** v为正finite volume；volume_base为过去21价格槽median；ready一旦见leg_direction即持续；q=v/base。

**时钟：** 每个price观察更新previous_close/declined/high_effort。

**前后状态：** 这些列会被cache引用；其pending/reclaim状态不直接作为当前cache的base.target。

## 21 当前base E0的真实state转移

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:86](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:86)；原文范围 86–114。

```python
  86         active, floor, pending = False, math.nan, None
  87         next_id = 0
  88         for n, (date, fact) in enumerate(bars.iterrows()):
  89             if fact.price_observation != n:
  90                 raise ValueError("Price observation clock must restart at zero and advance on valid rows")
  91             price_event = int(fact.event) if pd.notna(fact.event) else 0
  92             ready = bool(fact.ready)
  93             c = float(fact.close)
  94             q = float(fact.volume_ratio)
  95             declined, high_effort = bool(fact.declined), bool(fact.high_effort)
  96             entered = exited = created = response = consumed = independent = 0
  97             ended_id = None
  98             entry_kind = ""
  99             if active and compare(c, floor) <= 0:
 100                 active, exited = False, 1
 101             if pending:
 102                 if compare(c, pending["lower"]) < 0:
 103                     response = -1
 104                 elif compare(c, pending["reclaim"]) > 0:
 105                     response = 1
 106             if price_event == 1:
 107                 pivot = float(fact.confirmed_pivot_price)
 108                 if not math.isfinite(pivot):
 109                     raise ValueError("up event lacks canonical pivot")
 110                 if active:
 111                     floor = higher(floor, pivot)
 112                 elif not exited:
 113                     active, entered, floor = True, 1, pivot
 114                     entry_kind = "original_event"
```

**变量：** active/floor/pending每segment从False/NaN/None开始；c=当日adjusted close；price_event用保存事件。

**时钟：** 先旧floor失效，再处理本观察正event。

**前后状态：** c<=floor先exited；正event若active则higher floor，若本日未exited才entered。

## 22 当前base的pending创建入口为何不走

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:124](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:124)；原文范围 124–150。

```python
 124                     active, entered, independent, floor = True, 1, 1, pending["lower"]
 125                     entry_kind, outcome = "participation_reclaim", "reclaimed"
 126                 if outcome:
 127                     record = dict(pending)
 128                     record.update(resolved_date=str(date.date()), outcome=outcome,
 129                                   response=response, independent_entry=independent,
 130                                   original_entry_same_day=int(entry_kind == "original_event"),
 131                                   resolution_volume_ratio=q if math.isfinite(q) else None,
 132                                   waiting_observations=n-pending["created_observation"],
 133                                   segment_id=str(segment))
 134                     ledger.append(record)
 135                     ended_id, pending = pending["id"], None
 136             if not active and pending is None and bool(fact.decline_candidate):
 137                 next_id += 1
 138                 pending = {
 139                     "id": next_id, "created_date": str(date.date()),
 140                     "created_observation": n, "reclaim": float(fact.candidate_reclaim),
 141                     "lower": float(fact.candidate_lower),
 142                     "event_open": float(fact.open), "event_high": float(fact.high),
 143                     "event_close": c, "event_volume": float(fact.volume),
 144                     "volume_ratio": q if math.isfinite(q) else None,
 145                     "volume_baseline": float(fact.volume_baseline) if pd.notna(fact.volume_baseline) else None,
 146                     "created_on_exit": exited,
 147                 }
 148                 created = 1
 149             if active and pending is not None:
 150                 raise AssertionError("active structure retained pending memory")
```

**变量：** 唯一创建pending需要fact.decline_candidate=True。

**时钟：** cache.py:26在调用前将该字段所有行显式False。

**前后状态：** 初始pending=None，所以这里的reclaim路径在当前cache不建立；不是删掉旧源码或以另一旧策略替换。

## 23 当前base输出字段

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:149](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:149)；原文范围 149–163。

```python
 149             if active and pending is not None:
 150                 raise AssertionError("active structure retained pending memory")
 151             rows.append({
 152                 "date": date, "target": int(active), "entered": entered, "exited": exited,
 153                 "floor": floor if active or exited else math.nan,
 154                 "pending": int(pending is not None), "pending_id": pending["id"] if pending else None,
 155                 "pending_since": pending["created_date"] if pending else None,
 156                 "pending_reclaim": pending["reclaim"] if pending else math.nan,
 157                 "pending_lower": pending["lower"] if pending else math.nan,
 158                 "created": created, "response": response, "consumed_by_base": consumed,
 159                 "independent_entry": independent, "ended_id": ended_id,
 160                 "entry_kind": entry_kind, "volume_ratio": q, "high_effort": int(high_effort),
 161                 "declined": int(declined), "price_event": price_event, "ready": int(ready),
 162                 "segment_id": str(segment),
 163             })
```

**变量：** target=int(active)，floor仅active或exited时输出；ready/price_event/segment均保存。

**时钟：** 本CLOSE转移之后的结果。

**前后状态：** cache仅取base.target/floor/ready并传给G1_I，不把numeric内部target直接当结果。

## 24 现成G1 grade的实际生产入口

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/code/prepare_ix.py:9](/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/code/prepare_ix.py:9)；原文范围 9–32。

```python
   9 def worker(job):
  10  sid,rec=job
  11  sys.path.insert(0,str(B5/'code'))
  12  import api
  13  sys.path.insert(0,str(G1/'code'))
  14  from grade import classify
  15  from policies_g1 import project
  16  sys.path.insert(0,str(ROOT/'research_rounds/pv-participation-response-20261020/code'))
  17  from data_utils import eligible_prices
  18  a=rec['files']['signal'];p=OLD/'prepared-v2'/a['path'];assert sha(p)==a['sha256']
  19  signal=pd.read_parquet(p);f=eligible_prices(signal)[['open','high','low','close','volume','segment_id']].copy()
  20  f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
  21  t=time.time();r=api.run_b5(f,enhancements=False);e=r['evidence'];b=r['state'];g,j=classify(e);ix=project(e,b,g,'G1_IX');ee=events(g,ix)
  22  oldp=OLD/'prepared-v2'/rec['files']['states']['path'];assert sha(oldp)==rec['files']['states']['sha256'];old=pd.read_parquet(oldp)
  23  assert old.index.equals(b.index)
  24  for col in ['ready','target','entered','exited','floor','pending','pending_lower','pending_reclaim']:
  25   np.testing.assert_array_equal(b[col].to_numpy(dtype=float,na_value=np.nan),old[col].to_numpy(dtype=float,na_value=np.nan),err_msg=sid+':'+col)
  26  out=HERE/'signals'/f'{sid}.parquet'
  27  keep=pd.DataFrame(index=f.index)
  28  for c in ['segment_id','open','high','low','close','volume','valid_strength_observation']:keep[c]=f[c]
  29  for c in ['ready','target','entered','exited','floor','entry_kind']:keep['e0_'+c]=b[c]
  30  for c in ['grade','score','proposal','phase','z5','z21','fresh_up','up_reasons','promotion_blocked','acute_down','acute_up']:keep[c]=g[c]
  31  keep['strength_ready']=g.ready
  32  for c in ['target','entered','exited','floor','entry_kind','exit_reason']:keep['ix_'+c]=ix[c]
```

**变量：** api.run_b5(f,enhancements=False)产e/b；grade.classify(e)产g；keep保存grade/fresh_up/up_reasons等。

**时钟：** 原全历史一次生成IX signals，cache只读这些g列。

**前后状态：** G1_I不是这里的ix_target：cache另以当前base调用G1_I；这里只追grade的来源。

## 25 B5 orchestration的真实调用

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/api.py:8](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/api.py:8)；原文范围 8–19。

```python
   8 def run_b5(f, enhancements=False):
   9     """Return evidence, journal, state and ledger under those exact dict keys.
  10 
  11     journal contains `events` (pure E0 market receipts) and `strength` (the
  12     unchanged frozen B4 journal).  enhancements=True has no defined policy and
  13     is rejected; False consumes E0 facts without consulting strength fields.
  14     """
  15     if enhancements is True:
  16         raise NotImplementedError("B5 strength-enhanced participation is not specified or implemented")
  17     evidence, journal = build_evidence(f)
  18     state, ledger = e0_policy(evidence, enhancements=enhancements)
  19     return dict(evidence=evidence, journal=journal, state=state, ledger=ledger)
```

**变量：** build_evidence先产市场事实；e0_policy消费facts；enhancements=True明确未实现。

**时钟：** 历史指标生产，不是金融账户/OPEN执行。

**前后状态：** 原IX producer使用False。

## 26 B4强度的明确source绑定

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:20](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:20)；原文范围 20–51。

```python
  20 
  21 ROOT = Path(__file__).resolve().parents[3]
  22 B4_SOURCE = ROOT / "research_rounds/pv-strength-b4-20261025/code/model.py"
  23 B4_SHA256 = "0beb0b16f2f2cac4f1aff23258b7c45722dc12f16e495be27bf5635c03888cf1"
  24 INPUT_COLUMNS = [
  25     "open", "high", "low", "close", "volume", "segment_id",
  26     "valid_price_observation", "valid_strength_observation",
  27 ]
  28 EVENT_COLUMNS = [
  29     "confirmation", "leg_direction", "developing_extreme", "confirmed_pivot",
  30     "event", "pivot_age", "developing_extreme_price", "confirmed_pivot_price",
  31     "confirmed_pivot_date", "developing_extreme_date",
  32 ]
  33 EVENT_DATE_COLUMNS = ["confirmed_pivot_date", "developing_extreme_date"]
  34 FACT_COLUMNS = [
  35     "price_observation", "event_observation", "strength_observation", "ready",
  36     "previous_close", "volume_baseline", "volume_ratio", "declined",
  37     "high_effort", "decline_candidate", "candidate_lower", "candidate_reclaim",
  38 ]
  39 
  40 
  41 def _load_frozen_b4():
  42     """Verify the bytes before loading under an isolated, source-specific name."""
  43     if hashlib.sha256(B4_SOURCE.read_bytes()).hexdigest() != B4_SHA256:
  44         raise RuntimeError("Frozen B4 source SHA-256 mismatch")
  45     spec = importlib.util.spec_from_file_location(
  46         "_pvs_b5_frozen_b4_0beb0b16f2f2cac4", B4_SOURCE)
  47     if spec is None or spec.loader is None:
  48         raise RuntimeError("Cannot load frozen B4 source")
  49     module = importlib.util.module_from_spec(spec)
  50     spec.loader.exec_module(module)
  51     return module
```

**变量：** B4_SOURCE与常量B4_SHA256固定；加载前验证bytes。

**时钟：** build_evidence内的依赖绑定。

**前后状态：** 不是随便选一个旧strength实现；下段227–229实际调用这个frozen B4。

## 27 B5事件与price/strength观察字段

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:184](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:184)；原文范围 184–210。

```python
 184         bars = group.loc[group.valid_price_observation, ["open", "high", "low", "close", "volume"]].astype(float)
 185         if bars.empty:
 186             continue
 187         events, event_clock = _event_facts(bars)
 188         facts.loc[bars.index, EVENT_COLUMNS] = events
 189         facts.loc[bars.index, "event_observation"] = event_clock
 190         facts.loc[bars.index, "price_observation"] = np.arange(len(bars), dtype=float)
 191         strength_dates = group.index[group.valid_strength_observation]
 192         facts.loc[strength_dates, "strength_observation"] = np.arange(len(strength_dates), dtype=float)
 193         v = bars.volume.where(np.isfinite(bars.volume) & bars.volume.gt(0))
 194         volume_base = v.shift().rolling(21, min_periods=21).median()
 195         ratios = v / volume_base
 196         ready, previous_close = False, math.nan
 197         for n, (date, bar) in enumerate(bars.iterrows()):
 198             ev = events.loc[date]
 199             ready = ready or bool(pd.notna(ev.leg_direction))
 200             c, low = float(bar.close), float(bar.low)
 201             q = float(ratios.loc[date])
 202             declined = bool(math.isfinite(previous_close) and compare(c, previous_close) < 0)
 203             high_effort = bool(math.isfinite(q) and compare(q, 2.0) >= 0)
 204             candidate = bool(ready and declined and high_effort)
 205             facts.loc[date, ["ready", "previous_close", "volume_baseline", "volume_ratio",
 206                              "declined", "high_effort", "decline_candidate",
 207                              "candidate_lower", "candidate_reclaim"]] = [
 208                 int(ready), previous_close, float(volume_base.loc[date]), q,
 209                 int(declined), int(high_effort), int(candidate),
 210                 low if candidate else math.nan, previous_close if candidate else math.nan,
```

**变量：** price_observation对所有有效价bars编号；event clock另有正C/V索引；volume_base为过去21价观察量。

**时钟：** valid_price与valid_strength的钟不同。

**前后状态：** 这里产事件/ready字段，strength_date另按传入mask编号。

## 28 B5确实调用冻结B4

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:227](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:227)；原文范围 227–236。

```python
 227     b4 = _load_frozen_b4()
 228     strength, strength_journal = b4.strength_frame(f, joint=True)
 229     out = pd.concat([out, facts[FACT_COLUMNS + EVENT_COLUMNS], strength.add_prefix("strength_")], axis=1)
 230     out.attrs.update(
 231         model="PVS-B5", strength_source=str(B4_SOURCE.relative_to(ROOT)),
 232         strength_sha256=B4_SHA256, strength_attrs=strength.attrs.copy(),
 233         clocks="price: explicit mask; event: price plus positive finite C/V; strength: explicit subset mask",
 234         journal_contract="events: pure event/candidate receipts; strength: unchanged frozen B4 journal",
 235     )
 236     return out, {"events": event_journal, "strength": strength_journal}
```

**变量：** b4.strength_frame(f,joint=True)；各字段只加strength_前缀。

**时钟：** 每个已完成有效strength观察。

**前后状态：** grade.py读取的strength_mu/S21/S63等来自这里，不由账户或持仓决定。

## 29 B4有效钟与初值

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:96](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:96)；原文范围 96–117。

```python
  96 def run_valid(f, joint=True):
  97     """Compute one already validated, contiguous source segment.
  98 
  99     joint=False is the explicit price ablation: both structure-credit and
 100     acute-event volume multipliers are one. Valid positive volume is still
 101     required by strength_frame. Candidate columns are end-of-day states;
 102     structure_confirmed journal entries retain the consumed candidate receipt.
 103     """
 104     if not isinstance(joint, (bool, np.bool_)):
 105         raise ValueError('Scalar Boolean joint mode required')
 106     if len(f) == 0:
 107         out = pd.DataFrame(index=f.index, columns=FIELDS + DATE_FIELDS + ['phase'])
 108         out.attrs['terminal'] = None
 109         return out, []
 110     close = f.close.to_numpy(float)
 111     p = _log_prices(close)
 112     r = np.r_[np.nan, np.diff(p)]
 113     v = f.volume.to_numpy(float)
 114     dates = [str(date.date()) for date in f.index]
 115     rows, journal = [], []
 116     states = {}
 117     mu = {h: None for h in PACE_SPANS}
```

**变量：** close→p(log prices)→r；states空，mu5/mu21初值None。

**时钟：** run_valid仅处理一个连续source segment的有效strength观察。

**前后状态：** run_valid没有账户或仓位状态。

## 30 B4候选冻结与新frontier信用

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:122](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:122)；原文范围 122–152。

```python
 122     def fresh_candidate(t, anchor_t, h, direction, scale, vref, reason, prior=None):
 123         candidate = dict(
 124             direction=int(direction), anchor=float(p[anchor_t]),
 125             anchor_price=float(close[anchor_t]), anchor_observation=int(anchor_t),
 126             anchor_date=dates[anchor_t], created_observation=int(t),
 127             threshold=float(math.sqrt(h) * scale), scale_at_anchor=float(scale),
 128             volume_reference=float(vref), frontier=0., credit=0.,
 129             x=float(direction * (p[t] - p[anchor_t])), new_frontier=0.,
 130             frontier_increment=0., credit_increment=0., volume_weight=1.,
 131         )
 132         emit(t, 'candidate_reset', horizon=h, reason=reason,
 133              previous_candidate=copy.deepcopy(prior), candidate=copy.deepcopy(candidate))
 134         return candidate
 135 
 136     def advance_candidate(t, h, candidate):
 137         direction = candidate['direction']
 138         x = float(direction * (p[t] - candidate['anchor']))
 139         old_frontier, old_credit = candidate['frontier'], candidate['credit']
 140         extension = gt(x, old_frontier)
 141         weight = (float(np.clip(math.sqrt(float(v[t] / candidate['volume_reference'])), .5, 2.))
 142                   if joint else 1.)
 143         eligible = extension and direction * r[t] > 0.
 144         # F and Q describe the same accepted frontier. Updating F for tiny
 145         # sub-tolerance moves while leaving Q fixed would break .5F <= Q.
 146         frontier = x if eligible else old_frontier
 147         frontier_increment = float(frontier - old_frontier)
 148         credit_increment = float((x - old_frontier) * weight) if eligible else 0.
 149         candidate.update(
 150             x=x, frontier=float(frontier), credit=float(old_credit + credit_increment),
 151             new_frontier=float(eligible), frontier_increment=frontier_increment,
 152             credit_increment=credit_increment, volume_weight=weight,
```

**变量：** 候选threshold=sqrt(h)×scale_at_anchor，vref也冻结；只有extension且direction*r[t]>0才增加credit；weight=sqrt(v/vref)裁剪.5到2。

**时钟：** 本CLOSE推进旧候选。

**前后状态：** 新极值会另建候选；同一已用frontier不反复计credit。

## 31 B4确认与均值/波动公式

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:153](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:153)；原文范围 153–183。

```python
 153         )
 154         if extension:
 155             emit(t, 'frontier_extended', horizon=h, direction=direction,
 156                  prior_frontier=float(old_frontier), prior_credit=float(old_credit),
 157                  direction_return=float(direction * r[t]), eligible_for_credit=bool(eligible),
 158                  r=float(r[t]), volume=float(v[t]), candidate=copy.deepcopy(candidate))
 159         confirmed = (eligible and ge(x, candidate['threshold'])
 160                      and ge(candidate['credit'], candidate['threshold']))
 161         return bool(confirmed)
 162 
 163     for t in range(len(f)):
 164         if t >= 1:
 165             for h in PACE_SPANS:
 166                 alpha = 2. / (h + 1.)
 167                 mu[h] = float(r[t]) if mu[h] is None else float(alpha * r[t] + (1. - alpha) * mu[h])
 168         row = _blank_row()
 169         if t < 64:
 170             rows.append(row)
 171             continue
 172 
 173         # Exactly the preceding 63 returns and 21 volumes; never today's data.
 174         scale = max(1.4826 * float(np.median(np.abs(r[t - 63:t]))), 1e-8)
 175         vref = float(np.median(v[t - 21:t]))
 176         activity = float(v[t] / vref)
 177         q = float(r[t] / scale)
 178         qeff = float(q * math.sqrt(float(np.clip(activity, 1., 4.)) if joint else 1.))
 179         row.update(
 180             r=float(r[t]), r_bp=float(1e4 * r[t]), s=scale,
 181             volume_reference=vref, activity=activity, q=q, qeff=qeff,
 182             acute_down=float(le(qeff, -2.)), acute_up=float(ge(qeff, 2.)),
 183         )
```

**变量：** confirmed需eligible且x、credit同时>=threshold；mu_h按alpha=2/(h+1)平滑r；scale=1.4826×前63绝对r中位数；qeff=q×sqrt(clip(activity,1,4))。

**时钟：** t<64保unknown；scale/vref不含当前，mu包含本次r。

**前后状态：** acute_down/up为qeff≤−2/≥2；这是strength尺度，不是E0 numeric的RMS sigma。

## 32 B4 21/63状态与极值重置

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:195](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:195)；原文范围 195–221。

```python
 195         for h in SCALES:
 196             row[f'delta_{h}'] = float(math.sqrt(h) * scale)
 197             row[f'confirmed_{h}'] = 0.
 198             row[f'confirmed_direction_{h}'] = 0.
 199             if h not in states:
 200                 states[h] = dict(
 201                     direction=0, high=float(p[t - 1]), low=float(p[t - 1]),
 202                     high_observation=t - 1, low_observation=t - 1,
 203                     candidates={
 204                         1: fresh_candidate(t, t - 1, h, 1, scale, vref, 'initialization'),
 205                         -1: fresh_candidate(t, t - 1, h, -1, scale, vref, 'initialization'),
 206                     },
 207                 )
 208             state = states[h]
 209             before = state['direction']
 210             candidates = state['candidates']
 211 
 212             # Only extrema belonging to the active structure are maintained.
 213             # Before first confirmation both initial candidates are available.
 214             if before >= 0 and gt(float(p[t]), state['high']):
 215                 state['high'], state['high_observation'] = float(p[t]), t
 216                 candidates[-1] = fresh_candidate(
 217                     t, t, h, -1, scale, vref, 'new_high', candidates.get(-1))
 218             if before <= 0 and lt(float(p[t]), state['low']):
 219                 state['low'], state['low_observation'] = float(p[t]), t
 220                 candidates[1] = fresh_candidate(
 221                     t, t, h, 1, scale, vref, 'new_low', candidates.get(1))
```

**变量：** h遍历SCALES=(21,63)；state.direction=0起；up结构维护high、down结构维护low。

**时钟：** 本CLOSE先更新当前结构所属极值。

**前后状态：** 新high重置向下候选，新low重置向上候选，冻结当时尺度/量基准。

## 33 B4确认后的direction状态

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:223](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:223)；原文范围 223–252。

```python
 223             # A single return cannot provide same-day directional extension in
 224             # both directions. The assertion also prevents an accidental double
 225             # confirmation if the implementation changes later.
 226             confirmations = []
 227             for direction, candidate in candidates.items():
 228                 if advance_candidate(t, h, candidate):
 229                     confirmations.append(direction)
 230             if len(confirmations) > 1:
 231                 raise AssertionError('At most one structure confirmation per scale and observation')
 232             if confirmations:
 233                 direction = confirmations[0]
 234                 receipt = copy.deepcopy(candidates[direction])
 235                 emit(t, 'structure_confirmed', horizon=h, previous_direction=before,
 236                      direction=direction, r=float(r[t]), volume=float(v[t]),
 237                      s=scale, lag_volume_reference=vref,
 238                      close=float(close[t]), log_close=float(p[t]), joint=bool(joint),
 239                      receipt=receipt)
 240                 state['direction'] = direction
 241                 row[f'confirmed_{h}'] = 1.
 242                 row[f'confirmed_direction_{h}'] = float(direction)
 243                 state['candidates'] = {
 244                     -direction: fresh_candidate(
 245                         t, t, h, -direction, scale, vref, 'direction_confirmed',
 246                         candidates.get(-direction))
 247                 }
 248                 # On confirmation discard the old structure's extreme. The
 249                 # new direction starts its running high/low at today's close.
 250                 if direction == 1:
 251                     state.update(high=float(p[t]), high_observation=t,
 252                                  low=None, low_observation=None)
```

**变量：** 每尺度每观察最多一个confirmation；确认后state.direction改为该方向，只保留反向候选。

**时钟：** 当前CLOSE确认时。

**前后状态：** confirmed_direction_h为本次脉冲；不是持续S_h状态。

## 34 B4输出持续状态和running frontier

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:253](/Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b4-20261025/code/model.py:253)；原文范围 253–274。

```python
 253                 else:
 254                     state.update(low=float(p[t]), low_observation=t,
 255                                  high=None, high_observation=None)
 256             row[f'S{h}'] = float(state['direction'])
 257             for direction, side in ((1, 'up'), (-1, 'down')):
 258                 candidate = state['candidates'].get(direction)
 259                 row[f'{side}_active_{h}'] = float(candidate is not None)
 260                 if candidate is not None:
 261                     for field in CANDIDATE_FIELDS:
 262                         if field != 'active':
 263                             row[f'{side}_{field}_{h}'] = candidate[field]
 264                     row[f'{side}_anchor_date_{h}'] = candidate['anchor_date']
 265             if state['direction'] != 0:
 266                 extreme = 'high' if state['direction'] == 1 else 'low'
 267                 extreme_t = state[f'{extreme}_observation']
 268                 row[f'running_extreme_{h}'] = state[extreme]
 269                 row[f'running_extreme_price_{h}'] = float(close[extreme_t])
 270                 row[f'running_extreme_observation_{h}'] = float(extreme_t)
 271                 row[f'running_extreme_date_{h}'] = dates[extreme_t]
 272 
 273         local, background = int(row['S21']), int(row['S63'])
 274         phase, building_direction = phase_for(local, background)
```

**变量：** S_h为持续direction；running_extreme_price_h取真实close[extreme_t]。

**时钟：** 本CLOSE完成后的状态。

**前后状态：** grade的S21/S63与fresh frontier比较从这些字段读取。

## 35 G1 fresh/warm之前的真实分级

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py:13](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py:13)；原文范围 13–41。

```python
  13     rows=[];events=[];previous_segment=None;previous_grade=None;prior_extreme=math.nan;prior_s21=0
  14     for dt,r in e.iterrows():
  15         segment=str(r.segment_id)
  16         if segment!=previous_segment:
  17             previous_grade=None;prior_extreme=math.nan;prior_s21=0;previous_segment=segment
  18         out=dict(date=dt,segment_id=segment,ready=False,proposal=np.nan,grade=np.nan,score=np.nan,label='未知',phase='unknown',z5=np.nan,z21=np.nan,fresh_up=False,up_reasons='',transition='unknown',promotion_blocked=False,acute_down=False,acute_up=False,display='未知')
  19         if not bool(r.valid_strength_observation) or not np.isfinite(r.strength_mu21):rows.append(out);continue
  20         a,b=int(r.strength_S21),int(r.strength_S63);m5=float(r.strength_mu5);m21=float(r.strength_mu21);scale=float(r.strength_s)
  21         z5=math.sqrt(5)*m5/scale;z21=math.sqrt(21)*m21/scale
  22         down=bool(r.strength_acute_down);up=bool(r.strength_acute_up)
  23         reasons=[]
  24         if int(r.event)==1:reasons.append('new_E0_price_volume_up_event')
  25         for h in [21,63]:
  26             if float(r[f'strength_confirmed_direction_{h}'])==1:reasons.append(f'new_S{h}_up_confirmation')
  27         ext=float(r.strength_running_extreme_price_21)
  28         if a==1 and prior_s21==1 and np.isfinite(prior_extreme) and ext>prior_extreme+32*np.finfo(float).eps*max(abs(ext),abs(prior_extreme),1):reasons.append('new_price_frontier_in_confirmed_up_structure')
  29         fresh=bool(reasons)
  30         if a==0 and b==0:g=0;why='structure_unconfirmed'
  31         elif m21<0 and m5<=0:g=-3 if a==b==-1 else -2;why='both_paces_negative'
  32         elif m21<0 and m5>0:g=1 if a==1 else -1;why='local_repair' if a==1 else 'countertrend_rebound'
  33         elif m21>0:
  34             if a==b==1:g=3;why='up_structure_and_positive_medium_pace'
  35             elif a==1:g=2;why='local_up_with_positive_medium_pace'
  36             elif m5>0:g=1;why='pace_recovery_not_locally_confirmed'
  37             else:g=-1;why='local_support_missing'
  38         else:g=1 if m5>0 else -1 if m5<0 else 0;why='medium_pace_zero'
  39         if a==b==1 and z5>=1 and z21>=1:g=4;why='two_scale_pace_expansion'
  40         launch=up and int(r.event)==1 and m5>0
  41         if launch and g<2:g=2;why='acute_up_and_new_volume_price_up_event'
```

**变量：** 新E0 event、新S21/S63 up确认或已confirmed-up内strict新price frontier组成fresh；g按mu5/mu21与a=S21,b=S63决定。

**时钟：** 每个CLOSE；segment切换清previous_grade/prior_extreme。

**前后状态：** 暖grade可来自S21上行+正medium pace；不以持仓盈亏分级。

## 36 G1 grade锁与写出

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py:40](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py:40)；原文范围 40–63。

```python
  40         launch=up and int(r.event)==1 and m5>0
  41         if launch and g<2:g=2;why='acute_up_and_new_volume_price_up_event'
  42         if z5<=-1 and g>-2:g=-2;why='fast_adverse_displacement'
  43         if down:g=min(g,-3);why='acute_down_overrides_old_structure'
  44         proposal=g;old=previous_grade
  45         blocked=old is not None and proposal>old and not fresh
  46         if blocked:g=old
  47         transition='initialize' if old is None else 'upgrade' if g>old else 'downgrade' if g<old else 'blocked_upgrade' if blocked else 'unchanged'
  48         if down:phase='acute_down'
  49         elif launch:phase='fast_launch'
  50         elif up:phase='acute_up'
  51         elif a==b==1 and z5>=1 and z21>=1:phase='expansion'
  52         elif m21<0 and m5>0:phase='local_repair' if a==1 else 'downtrend_rebound'
  53         elif m21<0 and m5<=0:phase='decline'
  54         elif a==b==1 and (m5<0 or abs(z21)<1):phase='up_structure_consolidation'
  55         elif a==b==1:phase='up_continuation'
  56         elif a==1:phase='up_structure_building'
  57         elif a==b==0:phase='unconfirmed'
  58         else:phase='mixed_evidence'
  59         out.update(ready=True,proposal=proposal,grade=g,score=25*g,label=LABELS[g],phase=phase,z5=z5,z21=z21,fresh_up=fresh,up_reasons='|'.join(reasons),transition=transition,promotion_blocked=blocked,acute_down=down,acute_up=up,display=('freeze·' if down else '')+LABELS[g],reason=why)
  60         if transition!='unchanged':events.append(dict(date=str(dt.date()),segment=segment,previous=old,proposal=proposal,grade=g,score=25*g,kind=transition,basis=why,new_up_evidence=reasons))
  61         rows.append(out);previous_grade=g;prior_extreme=ext;prior_s21=a
  62     f=pd.DataFrame(rows).set_index('date')
  63     return f,events
```

**变量：** 升级若没有fresh则blocked并保previous_grade；down可压到−3；输出ready/grade/fresh_up/up_reasons。

**时钟：** 本观察结尾才写previous_grade/prior_extreme/prior_s21。

**前后状态：** fresh不是grade必须上升；grade不变也可有新frontier事件。

## 37 G1_I旧线优先、warm与i_buy原公式

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:6](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:6)；原文范围 6–34。

```python
   6 def project(e,base,g,kind):
   7     if kind not in ['G1_I','G1_X','G1_IX']:raise ValueError(kind)
   8     use_i=kind in ['G1_I','G1_IX'];use_x=kind in ['G1_X','G1_IX']
   9     active=False;floor=math.nan;segment=None;rows=[]
  10     for dt,r in e.iterrows():
  11         b=base.loc[dt];a=g.loc[dt]
  12         if r.segment_id!=segment:active=False;floor=math.nan;segment=r.segment_id
  13         valid=bool(r.valid_price_observation)
  14         if not valid:
  15             rows.append(dict(date=dt,target=np.nan,entered=0,exited=0,floor=np.nan,exit_line=np.nan,buy_event=False,entry_kind='',exit_reason='',grade=a.grade));continue
  16         shadow=bool(b.target);ready=bool(a.ready);entered=exited=0;reason='';entry_kind=''
  17         fresh=bool(a.fresh_up) if ready else False
  18         warm=ready and a.grade>=2
  19         cold=ready and (a.grade<=-2 or bool(a.acute_down))
  20         if active:
  21             if not shadow or float(r.close)<=floor:reason='E0_structure_boundary'
  22             elif use_x and cold:reason='G1_cold_or_acute'
  23             if reason:active=False;exited=1
  24             elif np.isfinite(b.floor):floor=max(floor,float(b.floor))
  25         # Entry-only is a new-evidence gate and restoration channel, while
  26         # exit-only preserves E0's new-cycle entry stream. An exit-only entry
  27         # is first checked by the extra exit rule on the next observation,
  28         # matching the original sensitive-policy ordering.
  29         opportunity=shadow and warm and (bool(b.entered) or fresh) if use_i else bool(b.entered)
  30         if not active and not exited and opportunity:
  31             active=True;entered=1;floor=float(b.floor)
  32             entry_kind='G1_fresh_warm_evidence' if use_i else str(b.entry_kind)
  33         buy=bool(active and opportunity) if use_i else bool(active)
  34         rows.append(dict(date=dt,target=int(active),entered=entered,exited=exited,floor=floor if active or exited else np.nan,exit_line=floor if active or exited else np.nan,buy_event=buy,entry_kind=entry_kind,exit_reason=reason,grade=a.grade))
```

**变量：** use_i=True,use_x=False；warm=ready&grade>=2；opportunity=shadow&warm&(base.entered|fresh)。

**时钟：** active旧floor先检查；未失效才max当前base.floor。

**前后状态：** not active且not exited才同观察入场；buy_event=active&opportunity；持续target不等于每日buy。

## 38 账户Facts把i_buy接到event资格

来源：[/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py:24](/Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py:24)；原文范围 24–47。

```python
  24  def row(self,sid,at):
  25   f=self.f[sid];day=pd.Timestamp(at.date());i=f.index.searchsorted(day,side='right')-1
  26   return None if i<0 else f.iloc[i]
  27  def factor(self,sid,at):return D(str(self.row(sid,at)['factor']))
  28  def floor(self,sid,at,mode):
  29   r=self.row(sid,at);v=np.nan if r is None else r[policy(mode).lower()+'_floor']
  30   return None if not np.isfinite(v) else D(str(v))
  31  def packet(self,at,mode):
  32   p=policy(mode)
  33   if self.day!=at:self.day=at;self.cache={}
  34   if p in self.cache:return self.cache[p]
  35   clock=admission.Clock(at,self.market.sessions['A'][bisect_right(self.market.sessions['A'],at)],at.date())
  36   inputs=self.b.at_decision(clock,market_buyable=self.market.market_buyable(at));stocks=[]
  37   for l,h in zip(inputs.lines,inputs.historical):
  38    assert l.security_id==h.security_id;sid=l.security_id;r=self.row(sid,at)
  39    if p!='E0':
  40     up=h.trend_up.read(clock)
  41     if up is not None:h=replace(h,trend_up=replace(h.trend_up,value=bool(r[p.lower()+'_target'])))
  42    s=pool.build_security(l,h,inputs.evidence)
  43    if p!='E0':
  44     allowed=s.buy_allowed.read(clock,for_execution=True);f=self.f[sid];today=pd.Timestamp(at.date());event=today in f.index and bool(f.loc[today,p.lower()+'_buy'])
  45     s=replace(s,buy_allowed=admission.Fact(None if allowed is None else bool(allowed and event),at,at,source_id='original_'+p+'_daily_event'))
  46    stocks.append(s)
  47   result=(clock,tuple(stocks),inputs.sectors);self.cache[p]=result;return result
```

**变量：** row取<=当日最后事实；floor按mode读i_floor；packet I把stock trend替为i_target，buy_allowed AND exact当日i_buy。

**时钟：** decision Clock的earliest_execution_at取下一session OPEN。

**前后状态：** Fact source_id=original_I_daily_event；OPEN没有在这里再计算E0/I。

## 39 No60 planning读取与I退出

来源：[/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)；原文范围 213–240。

```python
 213  def planning(self,at):
 214   clock,stocks,sectors=self.facts.packet(at,'I');sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};buyable=self.market.market_buyable(at);day=pd.Timestamp(at.date());event={};continuing={}
 215   for sid,s in sd.items():
 216    row=self.facts.row(sid,at);key=(bool(row.i_target),int(row.segment_id)) if row is not None else (False,-1)
 217    if self.last_epoch.get(sid)!=key:self.epoch[sid]+=1;self.global_watch.pop(sid,None);self.last_epoch[sid]=key
 218    ep=(key[1],self.epoch[sid]);event[sid]=BP.A.eligibility(s,ss,clock,'S0');continuing[sid]=BP.A.eligibility(replace(s,buy_allowed=buyable[sid]),ss,clock,'S0')
 219    if event[sid].q is True:self.global_watch[sid]=ep
 220   ordered=sorted(sd,key=lambda sid:(-(sd[sid].rank.read(clock) if sd[sid].rank and sd[sid].rank.read(clock) is not None else -1),sid))
 221   for a in self.accounts.values():
 222    C.activate(a);a.expire_day_buys(at);a.current_nav=a.balance(at,self.market.marks(at,a.positions))['nav'];M.E.risk_policy.step(a,at,'ACT20_BREAK');a.pending=[]
 223    for sid in tuple(a.positions):
 224     row=self.facts.row(sid,at);cp=self.cp[sid].loc[day] if day in self.cp[sid].index else None;quote=self.market.quote(sid,at);assert quote
 225     if not a.risk_state['on'] or not bool(row.i_target):
 226      if not bool(row.i_target):
 227       for x in a.live(sid):
 228        if x['kind']=='core':a.jmeta[x['id']]['pending_I_exit_reference']=True
 229      a.sell(sid,clock,quote,[x['id'] for x in a.live(sid)],'ACT_pause' if not a.risk_state['on'] else 'I_structure_exit');continue
 230     for x in a.live(sid):
 231      if x['kind']=='core':
 232       known_floor=self.facts.floor(sid,at,'I')
 233       if known_floor is not None:a.jmeta[x['id']]['last_core_line']=str(known_floor)
 234       continue
 235      if x['kind']!='add' or x['id'] in a.sell_layers.get(sid,set()):continue
 236      if D(str(row.close))<=x['floor']:a.sell(sid,clock,quote,[x['id']],'CP1_add_protection')
 237      else:
 238       floor=self.facts.floor(sid,at,'I')
 239       if floor is not None:x['floor']=max(x['floor'],floor)
 240       if cp is not None and bool(cp.receipt):x['floor']=max(x['floor'],D(str(cp.candidate)))
```

**变量：** 事实row.i_target与segment组成watch epoch；active账户先ACT/I退出，再处理各层。

**时钟：** planning在CLOSE执行。

**前后状态：** I_targetFalse全股I_structure_exit；CORE更新last_core_line不重复比较上游I线；mobile另按旧floor。

## 40 I事件资格与持仓/epoch的后置分开

来源：[/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:241](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:241)；原文范围 241–258。

```python
 241    a.sync(at);self.industry(a,at)
 242    for rank,sid in enumerate(ordered):
 243     cpr=self.receipts[sid].get(gidday(at));roles=[];why=[];held=bool(a.quantity(sid));epoch=self.global_watch.get(sid);sector=self.sector_by_sid[sid]
 244     if event[sid].q is True and not held and a.core_epoch.get(sid)!=epoch:roles.append('core')
 245     if cpr and continuing[sid].q is True:roles.append('mobile')
 246     if not a.risk_state['on']:why.append('ACT_paused')
 247     if sid in a.exits:why.append('exit_pending')
 248     if sid in a.buys:why.append('buy_pending')
 249     if event[sid].q is not True and not (cpr and continuing[sid].q is True):why.extend(event[sid].reasons or ['no_fresh_signal_or_Q'])
 250     self.opportunities.append(dict(account=a.label,day=gidday(at),sid=sid,sector=sector,rank=rank,core_Q=event[sid].q,mobile_Q=continuing[sid].q,CP1_id=cpr['receipt_id'] if cpr else None,roles=roles,held=held,barriers=why))
 251     if why or not roles:continue
 252     q=self.market.quote(sid,at);floor=self.facts.floor(sid,at,'I')
 253     if q is None or floor is None:continue
 254     for role in roles:
 255      fline=max(floor,D(str(self.cp[sid].loc[day,'candidate']))) if role=='mobile' else floor;budget=min(a.current_nav*D('.02'),max(Z,a.current_nav*D('.1')-a.quantity(sid)*q.raw_price));i=dict(sid=sid,clock=clock,quote=q,budget=budget,cap=q.quantity.buy_floor(int(budget/q.raw_price)),weight=1.,group=0,score=sd[sid].rank.read(clock),kind='add' if role=='mobile' else 'core',role=role,floor=fline,epoch=epoch,reason='fresh_CP1_mobile' if role=='mobile' else 'I_early_core',rank=rank,CP1_id=cpr['receipt_id'] if role=='mobile' else None,CP1_trace=cpr if role=='mobile' else None)
 256      if role=='core':LR.resize_core(i,a.current_nav,self.facts.factor(sid,at))
 257      if not i.get('size_reject') and i['cap']>0:a.pending.append(i)
 258      else:self.funding.append(dict(account=a.label,at=at,sid=sid,role=role,result=i.get('size_reject','no_nominal_gap')))
```

**变量：** event.Q是原I当日事件资格；continuing.Q换成市场buyable；core角色再检查flat/core_epoch。

**时钟：** CLOSE退出/ratchet并sync以后才生成pending。

**前后状态：** i_buy不含not-held/epoch；mobile由canonical CP+continuing.Q，不能把它等同新I event。

## 当前实际文件绑定实例

- `000620.SZ`：STOCK_MANIFEST.refs.facts=`/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/facts/000620.SZ.parquet`；prepared事件=`/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/prepared-v2/000072/events.parquet`；grade-containing IX=`/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/signals/000620.SZ.parquet`。
- `688146.SH`：STOCK_MANIFEST.refs.facts=`/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared/facts/688146.SH.parquet`；prepared事件=`/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/prepared-v2/001520/events.parquet`；grade-containing IX=`/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/signals/688146.SH.parquet`。
- `300085.SZ`：STOCK_MANIFEST.refs.facts=`/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared/facts/300085.SZ.parquet`；prepared事件=`/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/prepared-v2/000516/events.parquet`；grade-containing IX=`/Users/bytedance/Documents/ChatGPT/money/research_rounds/ix-a-share-entry-20261025/signals/300085.SZ.parquet`。

这里只核字节身份与源片段，未重算其中任何信号；不把源码绑定核查冒充新的回测结果。
