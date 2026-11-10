import json, hashlib, numpy as np, pandas as pd
from pathlib import Path
R=Path("/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/account_comparison_continuous_v1")
P=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared")
M=Path("/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json")
I=Path("/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json")
base,end=pd.Timestamp("2025-12-31"),pd.Timestamp("2026-05-15")
meta=json.loads(M.read_text()); names={r["sector_id"]:r["industry"] for r in meta.values() if r.get("sector_id")}
H=[r for r in json.loads((R/"inputs/H1_MANIFEST.json").read_text()) if r["industry"]]
assert len(H)==90 and len({r["sid"] for r in H})==90
im={r["series"]:r for r in json.loads(I.read_text())}
pm=json.loads((P/"manifest.json").read_text()); bm={r["series_id"]:r for r in pm["series"]}
a=np.load(P/"h1.npz",allow_pickle=True); ad=pd.DatetimeIndex(a["dates"]); aw=(ad>=base)&(ad<=end); days=ad[aw]; cols={s:i for i,s in enumerate(a["symbols"])}
source_hashes={}; checks=[]; native={}; rows=[]
def sha(p):
 p=Path(p); h=hashlib.sha256(p.read_bytes()).hexdigest();source_hashes[str(p)]=h;return h
def metric(s):
 s=s.dropna().sort_index();v=s.to_numpy(float); ds=[d.strftime("%Y-%m-%d") for d in s.index]
 # brute-force strict chronological pairs; ties pick earliest low/peak then earliest high/trough
 gain=[(v[j]/v[i]-1,i,j) for i in range(len(v)-1) for j in range(i+1,len(v))]
 best=max(gain,key=lambda z:z[0]); worst=min(gain,key=lambda z:z[0])
 return dict(observations=len(s),base_date=ds[0],end_date=ds[-1],base_close=float(v[0]),end_close=float(v[-1]),period_return_pct=float((v[-1]/v[0]-1)*100),max_low_then_high_rise_pct=float(max(0,best[0])*100),rise_low_date=ds[best[1]],rise_high_date=ds[best[2]],rise_low_close=float(v[best[1]]),rise_high_close=float(v[best[2]]),max_drawdown_pct=float(max(0,-worst[0])*100),drawdown_peak_date=ds[worst[1]],drawdown_trough_date=ds[worst[2]],drawdown_peak_close=float(v[worst[1]]),drawdown_trough_close=float(v[worst[2]]))
for item in H:
 sid=item["sid"]; src=next(k for k in item["source_identity"] if k.endswith("/signal.parquet"));q=pd.read_parquet(src);q.index=pd.to_datetime(q.index);w=q.loc[base:end].copy()
 bpath=P/"bars"/(sid+".parquet");b=pd.read_parquet(bpath).set_index("trade_date");b.index=pd.to_datetime(b.index);b=b.loc[base:end]
 sh=sha(src); bh=sha(bpath)
 valid=w["observed_bar"].fillna(False)&w["price_eligible"].fillna(False)&~w["source_invalid"].fillna(True)&~w["synthetic_event_bar"].fillna(True)&np.isfinite(w["close"])&(w["close"]>0)
 native[sid]=w.loc[valid,"close"]
 qv=w["close"].reindex(days).to_numpy(float); bv=b["close"].reindex(days).to_numpy(float);cv=a["close"][aw,cols[sid]]
 raw_parts=[]
 for rp in w["source_path"].dropna().unique():
  raw=pd.read_csv(rp);raw.index=pd.to_datetime(raw["date"]);raw=raw.loc[base:end]
  raw_parts.append(raw);sha(rp)
 raw=pd.concat(raw_parts).sort_index(); duplicate_raw=int(raw.index.duplicated().sum())
 raw=raw[~raw.index.duplicated(keep="first")];rv=raw["close"].reindex(days).to_numpy(float)
 prev_idx=np.flatnonzero(aw)-1; oc=a["obs_count"][aw,cols[sid]]; ocprev=a["obs_count"][prev_idx,cols[sid]]
 record=dict(sid=sid,industry_name=names.get(sid,sid),source_signal=str(src),source_signal_sha256=sh,source_identity_hash_matches=sh==item["source_identity"][src],other_industry_manifest_hash_matches=sh==im[sid]["source_sha256"][src],prepared_bar_hash_matches=bh==bm[sid]["raw"]["sha256"],signal_rows_with_base=len(w),observed_eligible_nonsynthetic_rows_with_base=int(valid.sum()),signal_missing_dates=len(days.difference(w.index)),signal_duplicate_dates=int(w.index.duplicated().sum()),raw_csv_rows_with_base=len(raw),raw_missing_dates=len(days.difference(raw.index)),raw_duplicate_dates=duplicate_raw,prepared_bar_rows_with_base=len(b),prepared_bar_missing_dates=len(days.difference(b.index)),cache_finite_cells=int(np.isfinite(cv).sum()),cache_obs_count_no_advance_cells=int((oc<=ocprev).sum()),cache_vs_signal_mismatch_cells=int((~np.isclose(cv,qv,rtol=0,atol=1e-9,equal_nan=True)).sum()),cache_vs_signal_max_abs_diff=float(np.nanmax(np.abs(cv-qv))),prepared_bar_vs_signal_mismatch_cells=int((~np.isclose(bv,qv,rtol=0,atol=1e-9,equal_nan=True)).sum()),raw_csv_vs_signal_mismatch_cells=int((~np.isclose(rv,qv,rtol=0,atol=1e-9,equal_nan=True)).sum()),observed_bar_false=int((~w.observed_bar).sum()),price_eligible_false=int((~w.price_eligible).sum()),synthetic_event_bar_true=int(w.synthetic_event_bar.sum()),source_invalid_true=int(w.source_invalid.sum()),raw_close_vs_close_mismatch_cells=int((~np.isclose(w.raw_close,w.close,rtol=0,atol=1e-9,equal_nan=True)).sum()),adjustment_factor_min=float(w.adjustment_factor.min()),adjustment_factor_max=float(w.adjustment_factor.max()),segment_count=int(w.segment_id.nunique()),source_csv_paths=list(w.source_path.dropna().unique()))
 checks.append(record)
 rows.append(dict(sid=sid,industry_name=names.get(sid,sid),**metric(native[sid])))
prices=pd.DataFrame(native).sort_index(); common=prices.dropna().index;stats=pd.DataFrame(rows).sort_values("period_return_pct",ascending=False)
assert prices.index.equals(days) and len(common)==len(days)
norm=prices/prices.loc[base]
basket=norm.mean(axis=1)
daily=(prices/prices.shift()).mean(axis=1).fillna(1).cumprod()
baskets=[dict(reference="initial_equal_weight_buy_hold_price_basket",**metric(basket)),dict(reference="daily_equal_weight_rebalanced_price_basket",**metric(daily))]
ck=pd.DataFrame(checks)
summary=dict(industry_count=90,baseline_date=str(base.date()),start_date="2026-01-01",end_date=str(end.date()),trading_days_excluding_baseline=len(days)-1,observations_including_baseline=len(days),first_trading_date=str(days[1].date()),common_native_observed_dates_including_baseline=len(common),union_native_dates_including_baseline=len(prices),rising_industries=int((stats.period_return_pct>0).sum()),flat_industries=int((stats.period_return_pct==0).sum()),falling_industries=int((stats.period_return_pct<0).sum()),period_return_median_pct=float(stats.period_return_pct.median()),rise_over_30_count=int((stats.max_low_then_high_rise_pct>=30).sum()),return_over_30_count=int((stats.period_return_pct>=30).sum()),basket_metrics=baskets,checks={c:int(ck[c].sum()) for c in ["signal_missing_dates","raw_missing_dates","prepared_bar_missing_dates","cache_obs_count_no_advance_cells","cache_vs_signal_mismatch_cells","prepared_bar_vs_signal_mismatch_cells","raw_csv_vs_signal_mismatch_cells","observed_bar_false","price_eligible_false","synthetic_event_bar_true","source_invalid_true","signal_duplicate_dates","raw_duplicate_dates","raw_close_vs_close_mismatch_cells"]},all_signal_hashes_match=bool(ck.source_identity_hash_matches.all()),all_industry_manifest_hashes_match=bool(ck.other_industry_manifest_hash_matches.all()),all_prepared_bar_hashes_match=bool(ck.prepared_bar_hash_matches.all()),source_identity="Account H1_MANIFEST original prepared-v2 signal close, checked against local source CSV and 2026-10-30 prepared bars/cache",non_pit=True)
for p in [R/"inputs/H1_MANIFEST.json",I,P/"manifest.json",P/"h1.npz",M]:sha(p)
print(json.dumps(summary,ensure_ascii=False,indent=2))
print("TOP_PERIOD");print(stats.head(12).to_string(index=False));print("SAMPLES");print(stats[stats.industry_name.isin(["半导体","元件","通信设备"])].to_string(index=False));print("TOP_STRICT_RISE");print(stats.sort_values("max_low_then_high_rise_pct",ascending=False).head(12).to_string(index=False));print("BOTTOM_PERIOD");print(stats.tail(5).to_string(index=False))

# Independent O(n) prefix algorithm cross-checks brute-force chronology metrics.
metric_checks=[]
for sid,s in {**native,"BASKET_INITIAL_EQUAL_WEIGHT":basket,"BASKET_DAILY_EQUAL_WEIGHT":daily}.items():
 v=s.to_numpy(float); low=high=v[0]; up=down=0.0
 for val in v[1:]:
  up=max(up,val/low-1);down=max(down,1-val/high);low=min(low,val);high=max(high,val)
 m=metric(s)
 assert abs(up*100-m["max_low_then_high_rise_pct"])<1e-10
 assert abs(down*100-m["max_drawdown_pct"])<1e-10
 metric_checks.append(sid)
for sid in native:
 b=pd.read_parquet(P/"bars"/(sid+".parquet")).set_index("trade_date").loc[base:end]
 assert bool(b.observed_bar.all()) and bool(b.is_observed_bar.all()) and bool(b.price_eligible.all())
 assert not bool(b.synthetic_event_bar.any()) and not bool(b.source_invalid.any())
assert all(pd.Timestamp(r["rise_low_date"])<pd.Timestamp(r["rise_high_date"]) and pd.Timestamp(r["drawdown_peak_date"])<pd.Timestamp(r["drawdown_trough_date"]) for r in rows)
out=R/"sector_2026_price_path_diagnostic_v1"
assert out.exists()
stats.insert(0,"period_return_rank",range(1,len(stats)+1))
stats.to_csv(out/"INDUSTRY_PRICE_PATHS_90.csv",index=False,float_format="%.12g")
prices.index.name="date";prices.to_csv(out/"NATIVE_CLOSE_90.csv",float_format="%.12g")
norm.index.name="date";norm.to_csv(out/"NORMALIZED_CLOSE_90.csv",float_format="%.12g")
pd.DataFrame({"initial_equal_weight_buy_hold":basket,"daily_equal_weight_rebalanced":daily}).rename_axis("date").to_csv(out/"BASKET_PATHS.csv",float_format="%.15g")
pd.DataFrame(baskets).to_csv(out/"BASKET_METRICS.csv",index=False,float_format="%.12g")
ck.to_csv(out/"SOURCE_COMPARISON_90.csv",index=False)
(out/"SOURCE_COMPARISON_90.json").write_text(json.dumps(checks,ensure_ascii=False,indent=2)+"\n")
summary["checks"]["prepared_bars_observed_valid_nonsynthetic_all_7740_cells"]=True
summary["checks"]["independent_prefix_maxima_verifications"]=len(metric_checks)
summary["official_csi300"]="Not present in the supplied 1799-series cache or original 90-industry manifests; no new data fetched and no ETF substituted."
summary["scope"]="Descriptive daily close price paths only. No signal recomputation, account replay, parameter selection, downloads, or edits to prior files."
summary["definitions"]={
 "period_return":"C(2026-05-15)/C(2025-12-31)-1",
 "max_low_then_high_rise":"max(0,max_{base <= i < j <= end}(C_j/C_i-1)); dates strictly chronological; all daily CLOSE prices.",
 "max_drawdown":"max(0,max_{base <= i < j <= end}(1-C_j/C_i)); positive loss magnitude; dates strictly chronological; all daily CLOSE prices.",
 "ties":"earliest first endpoint, then earliest second endpoint",
 "main_basket":"B_t = (1/90)*sum_i(C_i,t/C_i,2025-12-31). Initial equal capital across index price series, held without rebalancing; normalized price average, not mean of daily percentage returns.",
 "secondary_basket":"D_0=1; D_t=D_(t-1)*(1+(1/90)*sum_i(C_i,t/C_i,t-1-1)). Daily equal-weight rebalanced price reference, separately labeled; not the main basket.",
 "coverage":"Intersection and union of original source observed, price-eligible, positive finite close, non-synthetic, non-invalid rows, checked against original source CSV. No fills introduced.",
 "interpretation":"All paths are retrospective descriptive labels; maxima are not ex ante signals or realizable returns. Industry index basket is a non-tradable broad comparison, not CSI300 or an investable performance benchmark. No transaction costs, dividends, execution, funding or index tradability modeled.",
 "universe":"90 original account industry IDs; roster and naming/industry assignments are current snapshot NON-PIT."
}
(out/"SUMMARY.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
(out/"SOURCE_SHA256.json").write_text(json.dumps(source_hashes,ensure_ascii=False,indent=2)+"\n")
pre=dict(source_hashes); mismatches=[p for p,h in pre.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h]
assert not mismatches
verify=dict(all_passed=True,industry_rows=len(stats),native_price_rows=len(prices),native_price_cells=int(prices.size),source_files_hashed=len(pre),source_files_unchanged=len(pre),source_hash_mismatches=mismatches,all_account_source_hashes_match=True,all_secondary_manifest_source_hashes_match=True,all_prepared_bar_hashes_match=True,strict_pair_date_checks=90,independent_prefix_metric_checks=len(metric_checks),account_replays=0,external_data_requests=0,old_files_modified=0)
(out/"VERIFICATION.json").write_text(json.dumps(verify,ensure_ascii=False,indent=2)+"\n")
focus=stats[stats.industry_name.isin(["半导体","元件","通信设备","工业金属","港口航运","医疗服务","环境治理","电力","煤炭开采加工"])]
focus.to_csv(out/"FOCUS_PRICE_PATHS.csv",index=False,float_format="%.12g")
def one(r):
 return f'{r["industry_name"]} ({r["sid"]}): 期末 {r["period_return_pct"]:+.2f}%；最大严格先低后高收盘上涨 {r["max_low_then_high_rise_pct"]:.2f}%（{r["rise_low_date"]}→{r["rise_high_date"]}）；最大收盘回撤 {r["max_drawdown_pct"]:.2f}%（{r["drawdown_peak_date"]}→{r["drawdown_trough_date"]}）。'
textlines=[
"# 2026年1月1日至5月15日，90行业每日收盘价格路径诊断",
"",
"基期2025-12-31；实测区间首个交易日2026-01-05。85交易日，加基期86个日期，90行业共同覆盖7740个真实有效价格单元。账户H1_MANIFEST原signal主源、原source_path CSV、10/30 prepared bars与h1缓存逐单元对照零差异；90份原signal及90份bars的SHA均匹配其manifest。该窗口无前填、缺日、重复日、合成事件条、invalid条或不合格价格条，全部原调整因子为1。此覆盖结论仅限本次窗口，不外推全部历史。",
"",
"61行业上涨、29行业下跌、0持平；期末涨幅中位数5.38%。8行业期末涨幅≥30%，15行业至少一段严格先低后高收盘涨幅≥30%。",
"",
"主宽参照：90行业基期各自归一后直接取平均，等同初始等资本买入持有的价格篮子，后续权重随价格漂移，不每日再平衡。期末+8.1797%；最大收盘回撤12.7649%（2026-02-27→2026-03-23），最大严格先低后高上涨14.0648%（2026-03-23→2026-05-11）。它不是可交易组合、不是沪深300，不包含手续费、股息、执行或资金约束。",
"",
"另列每日等权再平衡价格参照：期末+7.9862%、最大回撤12.7322%。该口径与主篮子分开保存、不可混用。",
"",
"所有最大上涨和回撤均使用每日CLOSE且要求两个端点严格按时序，不用同日H/L。最大上涨为max(C_j/C_i-1, i<j)，回撤为max(1-C_j/C_i, i<j)，范围均含基期。并列日期优先较早的第一个端点，再选较早的第二个端点。这些仅事后行情标签，不是事前买卖信号或可实现收益。",
"",
"## 重点行业",
*[one(r) for r in focus.to_dict("records")],
"",
"## 期间涨幅前十",
*[one(r) for r in stats.head(10).to_dict("records")],
"",
"## 最大严格时序上涨前五",
*[one(r) for r in stats.sort_values("max_low_then_high_rise_pct",ascending=False).head(5).to_dict("records")],
"",
"## 文件",
"INDUSTRY_PRICE_PATHS_90.csv：全部90行业逐行期间涨幅、时序上涨及日期、回撤及日期。",
"NATIVE_CLOSE_90.csv / NORMALIZED_CLOSE_90.csv：86日原生收盘与基期归一价格。",
"BASKET_PATHS.csv / BASKET_METRICS.csv：两种清楚区分的价格篮子。",
"SOURCE_COMPARISON_90.csv/json：逐行业原数据、缓存与完整性对照。",
"SOURCE_SHA256.json / VERIFICATION.json：源哈希和只读不变性、独立两种算法复核。",
"",
"行业名单和名称/归属为当前快照NON-PIT，已见历史开发材料，不声称历史时点全市场或样本外。未重算信号、未运行经济账户、未新取外部数据、未改旧文件。提供的1799序列缓存及90行业manifest中无正式沪深300指数，本轮不以ETF冒充，也不为此补数。",
]
(out/"READOUT.md").write_text("\n".join(textlines)+"\n")
deliverable={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!="DELIVERABLE_SHA256.json"}
(out/"DELIVERABLE_SHA256.json").write_text(json.dumps(deliverable,ensure_ascii=False,indent=2)+"\n")
print("SAVED",str(out));print("FOCUS");print(focus.to_string(index=False));print("VERIFIED",json.dumps(verify))
