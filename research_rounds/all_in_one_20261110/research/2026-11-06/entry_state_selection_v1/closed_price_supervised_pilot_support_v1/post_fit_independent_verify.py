"""Independent saved-artifact audit only. No fitting, optimization, source feature recomputation,
economic simulation, account run, or changes to inputs. Writes this audit's JSON/Markdown only."""
from pathlib import Path
from decimal import Decimal
import csv, json, hashlib, datetime
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent
R=O.parent
H=Path("/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz")
checks=[]; monthly=[]; raw_summary=[]; biases=[]; rebuilt_out=[]; rebuilt_cov=[]; rebuilt_tails=[]; rebuilt_quality=[]
def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple,np.ndarray)): return [clean(v) for v in x]
    if isinstance(x,(np.integer,)): return int(x)
    if isinstance(x,(np.bool_,)): return bool(x)
    if isinstance(x,(float,np.floating)): return float(x) if np.isfinite(x) else None
    if isinstance(x,pd.Timestamp): return x.isoformat()
    return x
def check(ok,name,detail=None):
    checks.append(dict(name=name,passed=bool(ok),detail=clean(detail)))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dec(v): return Decimal(v) if v not in ("",None) else Decimal(0)
def near(a,b,atol=1e-7):
    if a is None or (isinstance(a,(float,np.floating)) and np.isnan(a)):
        return b is None or pd.isna(b)
    if isinstance(a,(str,bool)): return a==b
    return bool(np.isclose(float(a),float(b),rtol=1e-11,atol=atol,equal_nan=True))
primary=["PROTOCOL.json","run_pilot.py","ALL_ORIGINAL_PRICE_ROWS.parquet","PREPARE_SEAL.json","PREPARE_QA.json","INPUT_HASHES.json","MONTHLY_MODELS.json","TRAINING_IDENTITIES.csv","PREDICTIONS.parquet","PREDICTION_SEAL.json","OUTCOMES.csv","COVERAGE.csv","PROBABILITY_QUALITY.csv","LOST_WINNERS_AND_TAILS.csv","FUTURE_LABEL_POISON_QA.json"]
hashes_before={n:sha(O/n) for n in primary}
seal=json.loads((O/"PREDICTION_SEAL.json").read_text()); prepseal=json.loads((O/"PREPARE_SEAL.json").read_text())
for key,name in [("predictions_sha256","PREDICTIONS.parquet"),("models_sha256","MONTHLY_MODELS.json"),("training_ids_sha256","TRAINING_IDENTITIES.csv"),("script_sha256","run_pilot.py"),("protocol_sha256","PROTOCOL.json")]:
    check(seal[key]==sha(O/name),"prediction_seal:"+name)
for key,name in [("table_sha256","ALL_ORIGINAL_PRICE_ROWS.parquet"),("script_sha256","run_pilot.py"),("protocol_sha256","PROTOCOL.json")]:
    check(prepseal[key]==sha(O/name),"prepare_seal:"+name)
src_hashes=json.loads((O/"INPUT_HASHES.json").read_text())
check(sha(H)==src_hashes[str(H)],"calendar_hash")
r=pd.read_parquet(O/"ALL_ORIGINAL_PRICE_ROWS.parquet")
pred=pd.read_parquet(O/"PREDICTIONS.parquet")
check(not r.round_id.duplicated().any() and not pred.round_id.duplicated().any(),"unique_round_ids")
raw={}
for year in ("2022","2024"):
    E=R/"independent_channel_joint_economic_v1"/("economic_"+year); J=E/"joint"
    files=[E/"COMPARISON_REPORT_RECOVERED.json"]+[J/n for n in ["ROUNDS.csv","ACTIONS.csv","CLAIMS.json","CLAIM_LEDGER.csv","BRIDGES.json","REGISTRATIONS.csv","LEDGER_QA.json"]]
    for p in files: check(sha(p)==src_hashes[str(p)],"financial_source_hash:"+str(p.relative_to(R)))
    rows=[x for x in csv.DictReader((J/"ROUNDS.csv").open()) if x["owner_lane"]=="PRICE"]
    coverage={x["round_id"]:x for x in json.loads((E/"COMPARISON_REPORT_RECOVERED.json").read_text())["round_coverage"] if x["arm"]=="joint"}
    claims={x["owner_round_id"] for x in json.loads((J/"CLAIMS.json").read_text())}
    bridges={x["round_id"] for x in json.loads((J/"BRIDGES.json").read_text())}
    led={x["round_id"] for x in csv.DictReader((J/"CLAIM_LEDGER.csv").open())}
    reg={x["owner_round_id"] for x in csv.DictReader((J/"REGISTRATIONS.csv").open())}
    qa={x["round_id"]:x for x in json.loads((J/"LEDGER_QA.json").read_text())}
    actions={}
    for x in csv.DictReader((J/"ACTIONS.csv").open()): actions.setdefault(x["round_id"],[]).append(x)
    for x in rows:
        rid=x["round_id"]; aa=actions.get(rid,[]); cv=coverage[rid]; q=qa.get(rid,{})
        check(all(a["side"] in ("buy_core","buy_add","sell_all","sell_add") for a in aa),"known_action_sides:"+rid)
        buys=[a for a in aa if a["side"].startswith("buy")]; sells=[a for a in aa if a["side"].startswith("sell")]
        cash=sum((dec(a["q"])*dec(a["price"])-dec(a["fee"]) for a in sells),Decimal(0))-sum((dec(a["q"])*dec(a["price"])+dec(a["fee"]) for a in buys),Decimal(0))
        qty=sum((dec(a["q"]) for a in buys),Decimal(0))-sum((dec(a["q"]) for a in sells),Decimal(0))
        fees=sum((dec(a["fee"]) for a in aa),Decimal(0))
        entered=any(a["side"]=="buy_core" and dec(a["q"])>0 for a in aa)
        complete=x["status"]=="COMPLETE_CONDITIONAL_STOCK_ROUND"
        touched=rid in claims|bridges|led|reg
        ordinary=entered and complete and cv["financial_covered"] is True and cv["reason"]=="LOCAL_NO_ACTION_EVIDENCE" and not touched
        ordinary=ordinary and all(dec(x.get(k))==0 for k in ("core_qty","add_qty","dividend_at_termination","receivable_at_termination","receivable_after_payouts","dividend_net80_total","dividend_net80_paid"))
        ordinary=ordinary and qty==0 and q.get("qty")==0 and q.get("reconciled") is True and q.get("paid")==0 and q.get("receivable")==0
        ordinary=ordinary and bool(aa) and min(a["day"] for a in aa)==x["entry_day"] and max(a["day"] for a in aa)==x["exit_day"]
        ordinary=ordinary and all(abs(float(cash)-float(x[k]))<1e-7 for k in ("net_pnl","cashflow_to_date","cash_after_payouts"))
        ordinary=ordinary and abs(float(cash)-float(q["trade_cash"]))<1e-7 and abs(float(fees)-float(q["fees"]))<1e-7
        fin=complete and cv["financial_covered"] is True and q.get("reconciled") is True and dec(x["core_qty"])==0 and dec(x["add_qty"])==0 and x["net_pnl"]!=""
        raw[rid]=dict(window_label=year,entered=entered,complete=complete,ordinary=bool(ordinary),eval_financial_known=bool(fin),rights_touched=touched,has_claim=rid in claims,has_bridge=rid in bridges,
                      signal_day=x["signal_day"],entry_day=x["entry_day"],exit_day=x["exit_day"],PVR_score=float(x["PVR_score"]) if x["PVR_score"] else np.nan,net_pnl=float(x["net_pnl"]) if x["net_pnl"] else np.nan,
                      net_return_on_buy_cash=float(x["net_return_on_buy_cash"]) if x["net_return_on_buy_cash"] else np.nan,total_buy_cash=float(x["total_buy_cash"]) if x["total_buy_cash"] else np.nan,source=x)
    ss=[v for v in raw.values() if v["window_label"]==year]
    raw_summary.append(dict(window=year,registered=len(ss),entered=sum(x["entered"] for x in ss),closed=sum(x["complete"] for x in ss),ordinary=sum(x["ordinary"] for x in ss),financial_closed=sum(x["eval_financial_known"] for x in ss),rights_touched=sum(x["rights_touched"] for x in ss)))
check(set(raw)==set(r.round_id),"all_registered_PRICE_preserved")
flags=["entered","complete","ordinary","eval_financial_known","rights_touched","has_claim","has_bridge"]
for flag in flags:
    bad=[row.round_id for row in r.itertuples() if bool(getattr(row,flag))!=raw[row.round_id][flag]]
    check(not bad,"raw_reconstructed_flag:"+flag,{"mismatches":bad[:10],"n":len(bad)})
for col in ("net_pnl","net_return_on_buy_cash","PVR_score"):
    a=np.array([raw[k][col] for k in r.round_id]); b=r[col].to_numpy(float)
    check(np.allclose(a,b,atol=1e-12,rtol=1e-12,equal_nan=True),"raw_numeric:"+col)
cal=pd.DatetimeIndex(np.load(H,allow_pickle=False)["dates"]); cal=cal[(cal>="2013-01-01")&(cal<="2026-05-15")]
re_t=cal.get_indexer(pd.to_datetime(r.signal_day))
check(np.array_equal(re_t,r.t.to_numpy()) and (re_t>=0).all(),"signal_calendar_indices")
fresh_features=np.isfinite(r[["P","D","C"]]).all(axis=1)&r.pvr_error.lt(1e-8)&r.price_root.notna()&~r.price_root.astype(str).str.contains("None|nan",regex=True)
check(np.array_equal(fresh_features.to_numpy(),r.feature_known.to_numpy()),"feature_known_flag_from_saved_features")
check(np.array_equal(r.P.to_numpy(),r.PVR_score.to_numpy(),equal_nan=True),"P_exact_original_PRIORITY")
check((r.loc[r.ordinary,"label_known_at_proxy"]==r.loc[r.ordinary,"exit_day"]+pd.Timedelta(hours=15)).all(),"ordinary_proxy_clock")
expected_test=r[((r.window_label=="2022")&(r.signal_day>="2022-07-01")&(r.signal_day<="2022-12-31"))|((r.window_label=="2024")&(r.signal_day>="2024-09-01")&(r.signal_day<="2024-12-31"))]
check(set(pred.round_id)==set(expected_test.round_id),"test_all_registered_no_future_ordinary_filter")
models=json.loads((O/"MONTHLY_MODELS.json").read_text()); ids=pd.read_csv(O/"TRAINING_IDENTITIES.csv",dtype=str)
poisons={x["month"]:x for x in json.loads((O/"FUTURE_LABEL_POISON_QA.json").read_text())}
check(len(models)==10 and len(poisons)==10,"ten_month_models_and_saved_poison_checks")
def get_design(frame,sc):
    x=frame[["P","D","C"]].to_numpy(float); med,s,im,isc=[np.asarray(a,float) for a in sc]
    z=np.maximum(-5,np.minimum(5,(x-med)/s)); prod=np.c_[z[:,0]*z[:,1],z[:,0]*z[:,2]]
    iz=np.maximum(-5,np.minimum(5,(prod-im)/isc))
    return np.c_[np.ones(len(frame)),z,iz]
def sig(v): return 1/(1+np.exp(-np.clip(v,-35,35)))
max_prob=0.; max_grad=0.; all_train_rows=0
for model in models:
    mo=model["month"]; first=cal[cal.to_period("M")==pd.Period(mo)][0]; ci=cal.get_loc(first)
    rawmask=np.array([raw[k]["ordinary"] for k in r.round_id])
    tr=r[rawmask&r.feature_known.to_numpy()&(re_t>=ci-504)&(re_t<ci)&r.exit_day.lt(first).to_numpy()]
    tid=ids.loc[ids.month==mo,"round_id"].tolist()
    check(tr.round_id.tolist()==tid,"training_identity:"+mo,{"n":len(tr)})
    y=(tr.net_pnl.to_numpy()>0).astype(float); all_train_rows+=len(tr)
    counts={"n":len(tr),"W":int(y.sum()),"L":int((1-y).sum()),"dates":tr.signal_day.nunique(),"stocks":tr.sid.nunique(),"roots":tr.price_root.nunique(),"p0":y.mean()}
    check(all(near(v,model[k],1e-12) for k,v in counts.items()),"training_counts_p0:"+mo,counts)
    check(model["cut"]==str(first.date()) and model["window_start"]==str(cal[max(0,ci-504)].date()),"month_cut_window:"+mo)
    check((tr.label_known_at_proxy < first+pd.Timedelta(hours=9,minutes=30)).all(),"label_proxy_before_model_open:"+mo)
    x=tr[["P","D","C"]].to_numpy(); med=np.median(x,axis=0); s=(np.quantile(x,.75,axis=0)-np.quantile(x,.25,axis=0))/1.349
    z=np.clip((x-med)/s,-5,5); v=np.c_[z[:,0]*z[:,1],z[:,0]*z[:,2]]; im=np.median(v,axis=0); isc=(np.quantile(v,.75,axis=0)-np.quantile(v,.25,axis=0))/1.349
    check(all(np.allclose(a,b,atol=1e-13,rtol=1e-13) for a,b in zip([med,s,im,isc],model["scaling"])),"training_only_scaling:"+mo)
    X=get_design(tr,model["scaling"]); rank=np.linalg.matrix_rank(X); cond=np.linalg.cond(X)
    check(rank==6 and cond<1e6 and near(cond,model["condition"],1e-10),"six_column_design:"+mo)
    for name,cols,pen in [("interaction",6,np.array([0,4,4,4,16,16.])),("pvr",2,np.array([0,4.]))]:
        b=np.array(model[name+"_beta"]); xx=X[:,:cols]; grad=xx.T@(sig(xx@b)-y)+pen*b; gg=float(np.max(abs(grad))); max_grad=max(max_grad,gg)
        obj=float(np.sum(np.logaddexp(0,xx@b)-y*(xx@b))+.5*np.sum(pen*b*b))
        check(gg<1e-6 and near(gg,model[name+"_QA"]["gradient_max"],1e-10) and near(obj,model[name+"_QA"]["objective"]),"saved_coefficient_gradient_objective:"+mo+":"+name,{"gradient_max":gg})
    g=pred[pred.signal_day.dt.to_period("M")==pd.Period(mo)]; known=g[g.feature_known]; T=get_design(known,model["scaling"])
    for name,xx in [("interaction",T),("pvr",T[:,:2])]:
        pp=sig(xx@np.array(model[name+"_beta"])); actual=known["p_"+name].to_numpy()
        err=float(np.max(abs(pp-actual))) if len(pp) else 0.;max_prob=max(max_prob,err)
        check(np.allclose(pp,actual,atol=1e-12,rtol=0),"saved_probability:"+mo+":"+name,{"max_abs_error":err})
        check(g.loc[~g.feature_known,"p_"+name].isna().all(),"missing_features_probability_unknown:"+mo+":"+name)
    check(g.p0.eq(y.mean()).all() and g.model_cut.eq(first).all(),"test_p0_cut:"+mo)
    check(g.model_reason.eq("KNOWN").all() and model["support_ok"] and len(known)==model["known_predictions"],"month_status_and_score_count:"+mo)
    check(poisons[mo]["coefficients_exact"] and poisons[mo]["unavailable_labels_poisoned"]==len(r)-len(tr),"saved_poison_scope:"+mo)
    monthly.append(dict(month=mo,cut=str(first.date()),**counts,condition=cond,known_scores=len(known),training_birth_years=tr.signal_day.dt.year.value_counts().sort_index().to_dict()))
for name in ("pvr","interaction"):
    expected=pred["p_"+name].isna()|(pred["p_"+name]>=pred.p0)
    check(np.array_equal(expected.to_numpy(),pred["select_"+name].to_numpy()),"exact_threshold_and_unknown_fallback:"+name)
    check(pred.loc[pred["p_"+name].isna(),"select_"+name].all(),"all_unknown_original_members_retained:"+name)
check(pred.select_original.all(),"original_all_selected")
check(np.array_equal(pred.p_interaction.notna(),pred.p_pvr.notna()),"control_same_score_known_domain")
def outcome(g):
    p=g.net_pnl.to_numpy(); ret=g.net_return_on_buy_cash.to_numpy(); pos=p[p>0]; neg=p[p<0]
    return dict(n=len(p),stocks=g.sid.nunique(),W=len(pos),L_nonpositive=int((p<=0).sum()),loss_negative=len(neg),Z=int((p==0).sum()),winrate=float((p>0).mean()) if len(p) else None,
                old_net_sum=float(p.sum()),mean_net=float(p.mean()) if len(p) else None,mean_win=float(pos.mean()) if len(pos) else None,mean_loss=float(neg.mean()) if len(neg) else None,
                payoff=float(pos.mean()/(-neg.mean())) if len(pos) and len(neg) else None,profit_factor=float(pos.sum()/(-neg.sum())) if len(neg) else None,mean_return=float(ret.mean()) if len(ret) else None,tail30=int((ret>=.3).sum()),tail30_old_net=float(p[ret>=.3].sum()))
def auc(y,p):
    pos=np.asarray(p)[np.asarray(y,dtype=bool)]; neg=np.sort(np.asarray(p)[~np.asarray(y,dtype=bool)])
    if not len(pos) or not len(neg): return None
    return float(np.mean((np.searchsorted(neg,pos,side="left")+np.searchsorted(neg,pos,side="right"))/(2*len(neg))))
for window,g in pred.groupby("window_label"):
    scopes={"ORDINARY_SETTLED":g.ordinary,"ALL_FINANCIAL_KNOWN_CLOSED":g.eval_financial_known}
    for name in ("original","pvr","interaction"):
        s=g[g["select_"+name]]
        rebuilt_cov.append(dict(window=window,model=name,registered=len(g),selected_registered=len(s),registered_select_rate=len(s)/len(g),filled=int(g.entered.sum()),selected_filled=int(s.entered.sum()),filled_select_rate=s.entered.sum()/g.entered.sum(),known_score=int(g.p_interaction.notna().sum()),unknown_score=int(g.p_interaction.isna().sum()),unknown_fallback_filled=int((s.entered&s.p_interaction.isna()).sum()),selected_closed=int((s.entered&s.complete).sum()),selected_financial_unknown_closed=int((s.entered&s.complete&~s.eval_financial_known).sum()),selected_path_unknown_or_unclosed=int((s.entered&~s.complete).sum()),selected_not_entered=int((~s.entered).sum())))
        for scope,mask in scopes.items():
            base=g[mask&g.entered]; kept=base[base["select_"+name]]; lost=base[~base["select_"+name]]
            rebuilt_out.append(dict(window=window,model=name,scope=scope,**outcome(kept)))
            rebuilt_tails.append(dict(window=window,model=name,scope=scope,baseline_W=int((base.net_pnl>0).sum()),lost_W=int((lost.net_pnl>0).sum()),lost_old_positive_cash=float(lost.loc[lost.net_pnl>0,"net_pnl"].sum()),lost_L=int((lost.net_pnl<0).sum()),lost_old_negative_cash=float(lost.loc[lost.net_pnl<0,"net_pnl"].sum()),baseline_tail30=int((base.net_return_on_buy_cash>=.3).sum()),lost_tail30=int((lost.net_return_on_buy_cash>=.3).sum())))
        rights=s[s.entered&s.eval_financial_known&~s.ordinary]
        biases.append(dict(window=window,model=name,financial_nonordinary_closed=outcome(rights),ordinary_closed=int((s.entered&s.ordinary).sum()),ordinary_unknown_score=int((s.entered&s.ordinary&s.p_interaction.isna()).sum()),nonordinary_registered=int((~g.ordinary).sum()),nonordinary_scored=int((~g.ordinary&g.p_interaction.notna()).sum())))
    for scope,mask in scopes.items():
        z=g[mask&g.entered&g.p_interaction.notna()&g.p_pvr.notna()&g.p0.notna()]
        y=(z.net_pnl.to_numpy()>0).astype(float)
        for name,col in [("constant","p0"),("pvr","p_pvr"),("interaction","p_interaction")]:
            p=np.clip(z[col].to_numpy(),1e-12,1-1e-12)
            same=[auc(x.net_pnl.to_numpy()>0,x[col].to_numpy()) for _,x in z.groupby("signal_day")]; same=[x for x in same if x is not None]
            rebuilt_quality.append(dict(window=window,scope=scope,model=name,n=len(z),auc=auc(y,p),same_date_auc_mean=np.mean(same) if same else None,same_date_eligible_dates=len(same),brier=float(np.mean((p-y)**2)),logloss=float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p))),mean_p=float(np.mean(p)),actual_winrate=float(np.mean(y))))
    eligible=g[g.entered&g.eval_financial_known]
    check(np.allclose(eligible.net_pnl/eligible.total_buy_cash,eligible.net_return_on_buy_cash,atol=1e-12,rtol=1e-12),"net_return_denominator:"+window)
def compare_file(filename,records,keys):
    saved=pd.read_csv(O/filename,dtype={k:str for k in keys},float_precision="round_trip")
    lookup={tuple(str(row[k]) for k in keys):row for row in saved.to_dict("records")}
    check(len(lookup)==len(saved)==len(records),"result_row_count:"+filename)
    bad=[];largest=0.
    for row in records:
        key=tuple(str(row[k]) for k in keys); old=lookup.get(key)
        if old is None:bad.append({"key":key,"missing":True});continue
        for col,value in row.items():
            if col in keys:continue
            if not near(value,old.get(col)):bad.append({"key":key,"column":col,"recomputed":clean(value),"saved":clean(old.get(col))})
    check(not bad,"independent_results:"+filename,{"mismatches":bad[:20],"count":len(bad)})
for fn,rows,keys in [("OUTCOMES.csv",rebuilt_out,["window","model","scope"]),("COVERAGE.csv",rebuilt_cov,["window","model"]),("LOST_WINNERS_AND_TAILS.csv",rebuilt_tails,["window","model","scope"]),("PROBABILITY_QUALITY.csv",rebuilt_quality,["window","scope","model"])]:compare_file(fn,rows,keys)
prepared=json.loads((O/"PREPARE_QA.json").read_text())
check(len(prepared["prefix"])==12 and all(x["passed"] for x in prepared["prefix"]),"saved_twelve_prefix_checks")
hashes_after={n:sha(O/n) for n in primary}
check(hashes_before==hashes_after,"audit_did_not_change_inputs")
failures=[x for x in checks if not x["passed"]]
report=clean(dict(status="PASS_SAVED_ARTIFACT_ARITHMETIC_AND_CLOCK_ONLY" if not failures else "FAIL_REVIEW_REQUIRED",checks_count=len(checks),failed_checks=failures,model_refits=0,new_economic_runs=0,account_runs=0,source_feature_recomputations=0,source_hash_scope="All primary pilot artifacts plus calendar and 16 direct financial input files; not all 1489 native stock sources rehashed in this post-fit pass.",
                 max_probability_absolute_error=max_prob,max_saved_coefficient_gradient=max_grad,raw_financial_reconstruction=raw_summary,monthly=monthly,training_identity_rows=all_train_rows,coverage=rebuilt_cov,outcomes=rebuilt_out,tail_audit=rebuilt_tails,probability_quality=rebuilt_quality,rights_and_unknown_diagnostics=biases,input_hashes=hashes_before,checks=checks,
                 limitations=["No refit or parameter tuning; saved coefficients were evaluated only.","No independent source feature recomputation in this pass; saved 12 prefix checks were inspected.","Future poison records verify excluded net-label values only, not historical financial PIT.","All scores are selected-original-policy closure-conditioned diagnostics; no policy counterfactual or actual execution certification.","No-action and closure selection, NON-PIT static pool/industry/source versions, missing2023/early2024 births and weak2022-to-strong2024 calibration drift remain."]))
(O/"POST_FIT_INDEPENDENT_REVIEW.json").write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
md=["# PRICE 监督试点：独立结果核验","", "状态："+report["status"],"", "本次未重拟合、未重新计算源特征、未执行新经济生命周期或账户；独立重建了原始财务分类、逐月训练身份、保存系数的概率与固定选择，以及全部结果表。", "",
    "## 核验结果",f"- 检查 {len(checks)} 项，失败 {len(failures)} 项。",f"- 逐月训练身份合计 {all_train_rows} 行，10个月全部核对。",f"- 保存系数重算概率最大绝对误差 {max_prob:.17g}。",f"- 保存系数在对应训练设计上的最大梯度 {max_grad:.17g}。","- p>=p0、两模型共同评分域、UNKNOWN原全选、全量登记分母与四张结果表逐项核对。","- 全部主交付文件在核验前后哈希未变。","",
    "## 普通已闭回合主结果"]
for row in rebuilt_out:
    if row["scope"]=="ORDINARY_SETTLED":
        md.append(f"- {row['window']} {row['model']}: n={row['n']}, W={row['W']}, winrate={row['winrate']:.6%}, payoff={row['payoff']:.6f}, old_net_sum={row['old_net_sum']:.6f}, tail30={row['tail30']}。")
md+=["","## 权益与缺失边界"]
for row in biases:
    if row["model"] in ("original","interaction"):
        d=row["financial_nonordinary_closed"]
        md.append(f"- {row['window']} {row['model']}: 财务可用但非普通闭合 {d['n']} 条，W={d['W']}，原净额={d['old_net_sum']:.6f}；普通闭合中UNKNOWN回退 {row['ordinary_unknown_score']} 条。")
md+=["","## 结论与解释限制","- 核验通过只说明保存产物的时间掩码、数学和报表一致，不说明模型有效，也不构成真实成交或财务PIT认证。","- 2022的胜率局部增加不抵消2024胜率、赔率及尾部保留退化，不能晋升为已证明改善的准入器。","- 财务可用非普通回合仅作另外的已知场景评价，不回填普通训练域；不能按这些未来结果决定测试评分。","- 固定未来股票池、行业/源版本、无权益路径与闭合快慢选择、缺失出生队列、同股/同市场依赖仍在。所有净额均为旧路径子集，不能当新策略或共享账户损益。","- 原始12个prefix与10个poison记录存在且一致，本次未重做它们；poison的结论限于已排除净额值，不扩大为PIT保证。","- 详细检查、月度身份、财务分类、结果和输入哈希见同名JSON。"]
if failures: md+=["","## 失败项",json.dumps(clean(failures),ensure_ascii=False,indent=2)]
(O/"POST_FIT_INDEPENDENT_REVIEW.md").write_text("\n".join(md)+"\n",encoding="utf-8")
print(json.dumps(clean(dict(status=report["status"],checks=len(checks),failures=failures,max_probability_absolute_error=max_prob,max_gradient=max_grad,training_rows=all_train_rows,raw_financial=raw_summary,monthly=monthly,ordinary_results=[x for x in rebuilt_out if x["scope"]=="ORDINARY_SETTLED"],rights_diagnostics=biases,quality=rebuilt_quality,outputs=[str(O/"POST_FIT_INDEPENDENT_REVIEW.md"),str(O/"POST_FIT_INDEPENDENT_REVIEW.json")])),ensure_ascii=False))
