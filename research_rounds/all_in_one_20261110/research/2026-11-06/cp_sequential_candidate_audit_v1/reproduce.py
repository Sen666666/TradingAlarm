# Read-only market calculation with isolated new research outputs; no account imports.
from pathlib import Path
import pandas as pd, numpy as np, json, math
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
sm={r['symbol']:r for r in json.loads((U/'STOCK_MANIFEST.json').read_text())}
D=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1')
CACHE=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
a=pd.read_csv(D/'ALL_FIRST_ENTRIES.csv')
SIDS=['000620.SZ','002385.SZ','300182.SZ','600606.SH','688582.SH','000987.SZ','300672.SZ','300666.SZ']

from collections import deque
CAL=pd.DatetimeIndex(np.load('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz',allow_pickle=False)['dates'])
CASES=[('000620.SZ','2022-01-11'),('002385.SZ','2022-01-04'),('002385.SZ','2022-03-04'),('300182.SZ','2022-01-04'),('600606.SH','2022-03-22'),('688582.SH','2024-07-29'),('000987.SZ','2024-09-24'),('300672.SZ','2026-01-16'),('300666.SZ','2026-01-15')]
def calculate(f):
 ix=CAL[(CAL>=f.index.min())&(CAL<=min(f.index.max(),pd.Timestamp('2026-05-15')))]
 x=f.reindex(ix); hist=deque(maxlen=63); prevC=None;prevseg=None;S=0.;origin=None;prevI=None;above_closed=0;rows=[]
 for pos,(dt,v) in enumerate(x.iterrows()):
  good=np.isfinite(v.close) and v.close>0 and pd.notna(v.segment_id) and pd.notna(v.i_target)
  reason='SOURCE_MISSING_OR_INVALID' if not good else 'SEGMENT_CHANGE' if prevseg is not None and v.segment_id!=prevseg else ''
  if reason:hist.clear();prevC=None;S=0.;origin=None;above_closed=0;prevI=None
  C=float(v.close) if good else np.nan;ri=math.log(C/prevC) if good and prevC is not None else np.nan
  n=len(hist);zz=max(1.4826*float(np.median(hist)),math.log(1.001)) if n==63 and np.isfinite(ri) else np.nan
  u=ri/zz if np.isfinite(zz) else np.nan;before=S
  delta=.5*u-.125 if np.isfinite(u) else np.nan
  su=max(0.,S+delta) if np.isfinite(delta) else np.nan
  if np.isfinite(su):
   if before==0 and su>0:origin=pos
   if su==0:origin=None
  ion=int(v.i_target) if good else None
  fire=bool(np.isfinite(su) and su>=1 and ion==1)
  wasabove=above_closed
  if np.isfinite(su) and su>=1 and ion==0:above_closed+=1
  else:above_closed=0
  after=0. if fire else su if np.isfinite(su) else 0.
  rows.append(dict(day=dt,raw_C=v.raw_close,C=C,native_segment=v.segment_id,factor=v.factor,I=ion,E0=v.e0_target,G=v.g_grade,I_buy=v.i_buy,source_status=reason or 'PRESENT',prior_count=n,r=ri,z=zz,u=u,delta=delta,S_before=before,S=su,S_after=after,signal=fire,I_opens=ion==1 and prevI==0,excursion_start=x.index[origin] if origin is not None else pd.NaT,excursion_age=pos-origin+1 if origin is not None else 0,prior_closed_above_days=wasabove,prior5_abs_scale=1.4826*float(np.median(list(hist)[-5:])) if len(hist)>=5 else np.nan))
  S=after
  if fire:origin=None;above_closed=0
  if good and np.isfinite(ri):hist.append(abs(ri))
  prevC=C if good else None;prevseg=v.segment_id if good else None;prevI=ion
 return pd.DataFrame(rows).set_index('day')
RAW_MANIFEST=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/input-manifest.json')
rm={r['series_id']:r for r in json.loads(RAW_MANIFEST.read_text())['series']}
DATA={};RAW={}
for sid in SIDS:
 f=pd.read_parquet(sm[sid]['refs']['facts']).loc[:'2026-05-15']
 cp=pd.read_parquet(sm[sid]['refs']['CP1']);t=calculate(f)
 for c in ['receipt','candidate','phase','reset_reason','scale','credit','displacement','delta_frontier']:t['cp_'+c]=cp[c].reindex(t.index)
 raw=pd.read_parquet(rm[sid]['raw']['path']);raw.index=pd.DatetimeIndex(pd.to_datetime(raw.trade_date)).normalize();RAW[sid]=raw
 assert np.allclose(f.raw_close,raw.close.reindex(f.index),equal_nan=True)
 assert np.allclose(f.close,f.raw_close*f.factor,equal_nan=True)
 for k in ['observed_bar','price_eligible']:
  if k in raw:raw.loc[~raw[k].eq(True),['open','close']]=np.nan
 t['raw_open']=raw.open.reindex(t.index);t['adjusted_open']=t.raw_open*f.factor.reindex(t.index)
 t['sid']=sid
 t['original_actual_entry']=False
 aa=a[(a.account=='PVR')&a.sid.eq(sid)]
 for _,ar in aa.iterrows():
  if pd.Timestamp(ar.entry_day) in t.index:t.loc[ar.entry_day,'original_actual_entry']=True
 DATA[sid]=t
rows=[]
for sid,day in CASES:
 t=DATA[sid];dt=pd.Timestamp(day);pos=t.index.get_loc(dt);ar=a[(a.account=='PVR')&a.sid.eq(sid)&a.signal_day.eq(day)].iloc[0]
 off=t.iloc[:pos+1][t.iloc[:pos+1].I.ne(1)].tail(1)
 start=t.index.get_loc(off.index[-1])+1 if len(off) else 0
 cycle=t.iloc[start:pos+1];first=cycle[cycle.signal].head(1)
 last=t.iloc[max(0,pos-20):pos+1];last=last[last.signal].tail(1)
 later=t.iloc[pos+1:min(len(t),pos+21)];later=later[later.signal].head(1)
 out=dict(sid=sid,original_signal=day,original_entry=ar.entry_day,original_pnl=ar.round_pnl,I_cycle_start=str(t.index[start].date()),first_cycle_candidate=str(first.index[0].date()) if len(first) else None,same_date=bool(t.loc[dt,'signal']),S=float(t.loc[dt,'S']),last20=str(last.index[0].date()) if len(last) else None,next20=str(later.index[0].date()) if len(later) else None)
 for typ,d in [('original',dt),('last_candidate',last.index[0] if len(last) else None),('next_candidate',later.index[0] if len(later) else None)]:
  if d is None:continue
  p=t.index.get_loc(d)+1
  if p>=len(t):continue
  en=t.iloc[p];out[typ+'_earliest_next_day']=str(t.index[p].date());out[typ+'_open']=float(en.raw_open)
  for n in [1,5,20,60]:
   v=t.iloc[p:p+n]
   ok=len(v)==n and v.C.notna().all() and math.isfinite(en.adjusted_open)
   out[typ+'_close'+str(n)]=float(v.iloc[-1].raw_C) if len(v)==n else None
   out[typ+'_proxy_pct'+str(n)]=100*(float(v.iloc[-1].C)/en.adjusted_open-1) if ok else None
  raw=RAW[sid]
  if t.index[p] in raw.index:
   rr=raw.loc[t.index[p]];out[typ+'_oneprice']=bool(rr.open==rr.high==rr.low==rr.close)
 rows.append(out)


import hashlib, sys, platform
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/cp_sequential_candidate_audit_v1')
checks=[]
for sid in SIDS:
 f=pd.read_parquet(sm[sid]['refs']['facts']).loc[:'2026-05-15'];t=DATA[sid]
 for cut in [pd.Timestamp('2022-01-04'),pd.Timestamp('2024-09-24'),pd.Timestamp('2026-01-15')]:
  if cut not in f.index:continue
  cols=['r','z','S_before','S','S_after','signal','I']
  p=calculate(f.loc[:cut]);pd.testing.assert_frame_equal(p[cols],t.loc[:cut,cols],check_dtype=False)
  poison=f.copy();poison.loc[poison.index>cut,'close']*=2.;poison.loc[poison.index>cut,'i_target']=0
  v=calculate(poison);pd.testing.assert_frame_equal(v.loc[:cut,cols],t.loc[:cut,cols],check_dtype=False)
  checks.append(dict(sid=sid,cut=str(cut.date()),prefix_exact=True,future_poison_exact=True))
 assert not t[t.signal].I.ne(1).any()
 assert t.loc[t.signal,'S_after'].eq(0).all()
 assert not t[t.source_status!='PRESENT'].signal.any()
 assert t.loc[t.signal,'S'].ge(1).all()
for row in rows:
 aa=a[(a.account=='PVR')&a.sid.eq(row['sid'])&a.signal_day.eq(row['original_signal'])].iloc[0]
 assert abs(row['original_open']-aa.first_raw_open)<1e-10
 def ff(val): return float(val) if pd.notna(val) else None
 f=pd.read_parquet(sm[row['sid']]['refs']['facts'])
 for col,newcol in [('original_i_target','i_target'),('original_e0_target','e0_target'),('original_g_grade','g_grade')]:
  assert ff(aa[col])==ff(f.loc[row['original_signal'],newcol])
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.integer,)):return int(x)
 if isinstance(x,(np.bool_,)):return bool(x)
 if isinstance(x,(np.floating,float)):return float(x) if np.isfinite(x) else None
 if isinstance(x,(pd.Timestamp,)):return str(x)
 return x
def dump(name,x):(O/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False))
sourcepaths=[U/'STOCK_MANIFEST.json',RAW_MANIFEST,D/'ALL_FIRST_ENTRIES.csv']
for sid in SIDS:
 sourcepaths.extend([Path(sm[sid]['refs']['facts']),Path(sm[sid]['refs']['CP1']),Path(rm[sid]['raw']['path'])])
sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sourcepaths}
freeze=dict(formula='r=ln(C/Cprev); z=max(1.4826*median(abs(previous63returns)),ln(1.001)); A=max(0,Sprev+0.5*r/z-0.125); receipt iff I=1 and A>=1; Safter=0 on receipt else A',
 missing_rule='At any common-calendar absent/invalid price/unknown I or native segment boundary, clear S and history and emit no signal; require63 prior returns to restart. Normal holidays not inserted.',
 sources=sources,calendar_source='native H1 dates from update-20261030-153010-c551af/prepared/h1.npz',calendar_value_sha256=hashlib.sha256(CAL.asi8.tobytes()).hexdigest(),
 selected_sids=SIDS,selected_case_pairs=CASES,endpoint='2026-05-15',no_parameter_grid=True,no_account_run=True,no_orders=True,no_random_control=True,receipt_consumed_independent_of_selection_or_fill=True,formula_prior_to_case_calculation=True,
 python=sys.executable,python_version=platform.python_version(),pandas=pd.__version__,numpy=np.__version__)
O.mkdir(exist_ok=False)
dump('FREEZE_AND_SOURCE_HASHES.json',freeze)
full=pd.concat(DATA.values()).reset_index()
full['earliest_next_market_day']=full.groupby('sid').day.shift(-1)
full.loc[~full.signal,'earliest_next_market_day']=pd.NaT
full['candidate_order_executed']=pd.NA
full['receipt_consumed_at_close']=full.signal
full['execution_status']='NOT_SIMULATED'
full.to_parquet(O/'FULL_PREFIX_DAILY.parquet',index=False)
full[(full.day>='2022-01-01')&full.signal].to_parquet(O/'ALL_CANDIDATE_RECEIPTS_2022_20260515.parquet',index=False)
windows=[]
for sid,day in CASES:
 t=DATA[sid];p=t.index.get_loc(pd.Timestamp(day));v=t.iloc[max(0,p-20):min(len(t),p+61)].copy();v['case_original_signal']=day;windows.append(v)
pd.concat(windows).reset_index().to_parquet(O/'CASE_DAILY_WINDOWS.parquet',index=False)
dump('NINE_CASE_COMPARISON.json',rows)
dump('VALIDATION.json',dict(checks=checks,n_prefix_checks=len(checks),consume_assertions=True,I_gate_assertions=True,missing_no_signal=True,raw_coordinate_identity=True,nine_original_entry_open_and_native_fields_match=True,all_possible_prefixes_checked=False,
 total_prefix_rows=len(full),candidate_receipts_2022_20260515=int(((full.day>='2022-01-01')&full.signal).sum()),delayed_threshold_receipts=int(((full.day>='2022-01-01')&full.signal&full.prior_closed_above_days.gt(0)).sum())))
(O/'REPORT.txt').write_text("CP 顺序累计候选审查，2026-11-06\n结论：不能采用为已验证的首仓改进。只在固定 8 只、9 个既有案例核逐日机制，没有账户回测、随机对照或参数网格，没有胜率或收益改善结论。\n\n固定公式与时钟\n使用原 facts 的同源、同段调整收盘 C。r_t=ln(C_t/C_{t-1})；z_t=max(1.4826×median(此前63个完整收益绝对值),ln(1.001))；u_t=r_t/z_t；A_t=max(0,S_{t-1}+.5u_t-.125)。I_t=1且A_t≥1，当日收盘发一张候选，随即S_t=0；否则S_t=A_t。I=0仍更新但不消费，不复用历史最高S。无论有无持仓、排序是否选到、是否成交，市场候选都消费；这不是实际首仓订单。候选仅当次有效，最早下一个交易日执行，不携带为永久准入。\n发证是点事件，不是持续条件；当日收盘后才知道r、I与A，不能以当日开盘成交。后续候选必须用上次消费之后的新收益积累；但I关着时已积累的证据可在I开启时延迟消费，这是本规则仍允许的旧证据。\n1.4826×median(|r|)不是去中位数MAD，亦未把u视为正态、独立或方差1。0.5、0.125、1是本次固定设计，不宣称最优或概率置信度。\n缺源、无效价格、未知I或源段变化时，该候选状态和收益窗清空且不发证；恢复后重新等63个已完成收益，首个可算信号需65个连续有效收盘。已知交易日无源不能当零收益、不能跨越推断；正常休市不插行。此为明确的保守数据约定，不是择时优势。本次未修改原E0/G/I/CP/持仓规则。\n市场收盘计算用原 facts 全前缀，从2013年/上市日开始，截至2026-05-15。样本只是反例检验，不是代表性抽样。原成交日期和回合损益来自既有PVR模拟账，不能归于新候选。\n\n主要反例\n1. 002385.SZ，2022-01-04：原CP与候选同日。新S=1.0243068，来自12/30、12/31与1/4的三日新推进，非旧最高点复用。原1/5开盘10.88，后第5/20观察收盘9.71/9.45（相对此开盘−10.75%/−13.14%）。候选没有挡住这个原亏损回合。同股3/4的原CP被挡（S=.6426625），但同一I周期2/21早已有新候选；若在2/22开盘8.79试探，第20观察收盘8.00，仍−8.99%。不能把挡掉3/4等同规避整个失败行情。\n2. 300182.SZ，2022-01-04：S=.9562612，不发证。1/14单日上涨20.03%后S=2.778294，I重开即发证；最早1/17，开盘7.50，后第20/60观察收盘6.49/5.08（−13.47%/−32.27%）。这是一条先挡较小反弹、后追更大反弹的反例，不能称过滤了该股失败。\n3. 000620.SZ，2022-01-11：S=1.8242025，仍与原实际首买前一日发证。本I周期1/6已发第一张；1/7、1/10、1/11、1/12、1/13可连续发新证，消费归零并不阻止持续急涨每天独立过线。1/11的63日z=.024108，而此前5日|r|尺度=.141848，显示尺度反应慢；但这只能证明机械原因，不能断言早期信号可成交或单纯提高尺度就改进。此股原账户最终亏1.49万元，但同一次原开盘至第20/60观察价格为+2.92%/+27.60%，证明回合胜负不能全归因于首日方向。\n4. 600606.SH，2022-03-22：候选S=1.6753222，与原信号同日；3/17已先发第一张。原3/23开盘4.28，第20观察4.70（+9.81%）。没有从这个样本看出必须牺牲该赢家。\n5. 688582.SH，2024-07-29：S=.7924236，不发证；7/31 S=1.557220才有新证，最早8/1开盘30.60，比原7/30开盘29.36高4.22%。但7/10已有更早候选，不能直接称漏掉整个赢家。如果此前未成交，原7/29时点确实没有可用新证。原7/30到第20观察32.43（+10.46%）；新7/31证的8/1开盘到其第20观察32.28（+5.49%），终点不同，不能当同持有期交易胜负。\n6. 000987.SZ，2024-09-24：S=3.1997158，与原CP同日；9/18已有首张。次日原开盘5.70，第20观察7.17（+25.79%）。同样的慢尺度对9·24大涨给很大u，也允许新证密集出现；不能只在败例上指责慢尺度，在赢家上却把它当优势。\n7. 300672.SZ，2026-01-16：原赢家当天S=.4347682无新证，因为1/15已发证并归零；1/19才再发，最早1/20。若1/15时已进入候选并能成交，可比原1/19早到1/16；若1/15没有被选中/未成交，就不能重复用旧证。这反映消费规则本身的时点代价，不等于漏掉整段行情。\n8. 300666.SZ，2026-01-15：S=1.5683298，仍同日发证；1/14也有独立新证。原1/16开盘127.34，1/29收盘113.48（−10.88%），原回合亏损。1/30—2/5源缺失，不填完整20/60观察统计。本股是2026半导体同阶段反例，不称该回合赢家。\n\n旧证据仍存在\n000987.SZ在2025-04-09已S≥1，但I=0；其后持续8个观察高于1。4/21 I开启时当日仅涨0.1584%，该日delta=−.067591，S仍从1.615066降至1.547475并发证。不是复用旧峰值，但确是消费过去积累、不是当日新增正证据。\n2022—2026-05-15的这8只合计507张候选，23张在I关着时已有S≥1、后来才消费；并非全市场发生率。未发现发证当日r≤0，但有当日delta≤0的发证，不能把“上涨当天”误当“证据新增加”。\n\n机制判断\n它能把回撤作为负项扣掉，且发证后消费，解决原CP只累加高点推进的一部分表示问题；然而S降到0后也清除了负债，随后一次大涨仍可独立过线。它检测的是相对旧尺度的新局部上涨，不直接识别上涨后还能否延续。\n从S=0一日发证，只需r/z≥2.25。63观察中位数对波动突增反应慢，急涨可能连续满足；缩短尺度可能反过来漏掉9·24，这次没有运行替代窗口或调参。因此可确认机制风险，不能证明其因果损益或最优修复。\n“开仓亏损不加仓”属于账户/持仓约束，本候选从不读取持仓盈亏，不能声称落实了它。此审查只研究首仓候选，不修改加仓或退出。\n\n数据、复核与限制\nclose与raw_close×factor在8只原来源上逐行相符；候选次日开盘读取原rs-h1-execution input-manifest的raw源，不混用全池日缓存的另一调整坐标。与既有模拟账9个案例的首买开盘核对。后续价格只是事后描述，不是候选账户收益，不含费用、跌涨停、T+1、现金、排序、持仓、撤单或成交推演。\n8只在2022-01-04、2024-09-24、2026-01-15可用切点做前缀重算与未来价格/I污染，已核切点前r/z/S/候选一致，共23个切点。仅这些切点，非所有前缀穷举。逐日归零/准入/缺源不发证断言通过。没有概率校准、样本外、账户胜率、收益、回撤结果。历史股票池/PIT、停牌、复权及真实成交限制未解决。30%胜率目标没有新增证据。\n")
(O/'reproduce.py').write_text(Path(__file__).read_text())
dump('OUTPUT_SHA256.json',{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'})
print(json.dumps(dict(output=str(O),prefix_rows=len(full),cases=len(rows),prefix_checks=len(checks),files=[p.name for p in O.iterdir()]),ensure_ascii=False))
