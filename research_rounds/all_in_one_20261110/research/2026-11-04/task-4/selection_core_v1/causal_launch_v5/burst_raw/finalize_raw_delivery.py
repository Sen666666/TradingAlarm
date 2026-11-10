"""Documentation/source bindings for the fixed raw extraction, no strategy."""
from pathlib import Path
import hashlib,json
import pandas as pd
O=Path(__file__).resolve().parent;TASK=O.parents[2];SEL=O.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(n,v):(O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
 x=pd.read_parquet(O/'RAW_PATHS_COMPLETE.parquet');a=x.loc[x.relative_session.eq(0)]
 mapping={'main_semis_924':'924_SEMI','main_software_924':'924_SOFTWARE','main_comms_924':'924_COMMUNICATION','main_semis_2026jan5':'2026JAN5_SEMI','aux_semis_2026jan15':'2026JAN15_SEMI','counter_realestate_2022jan24':'2022JAN24_REALESTATE','counter_software_2024oct8':'2024OCT8_SOFTWARE','counter_multifinance_2024oct8':'2024OCT8_FINANCIAL'}
 pd.DataFrame([{'burst_raw_case_id':k,'feature_paths_case_id':v}for k,v in mapping.items()]).to_csv(O/'CASE_ID_MAPPING.csv',index=False)
 # The predeclared 924 cutoff case illustrates conditional breadth denominators.
 peer=SEL/'causal_launch_v5/feature_paths/CAUSAL_FEATURE_PATHS.parquet';f=pd.read_parquet(peer);cut=f.loc[f.date.eq('2024-09-24')&f.relative_session.eq(0),'T_cutoff_sector'].unique();assert len(cut)==1
 old=SEL/'industry_selection/channels_v2/INDUSTRY_OPPORTUNITIES_DAILY.parquet';g=pd.read_parquet(old);z=g.loc[g.sector_id_static.eq(cut[0])].sort_values('date').copy()
 z['B_own_lag5_raw']=z.B_now.shift(5);z['B_own_lag10_raw']=z.B_now.shift(10);z['a_own_raw']=z.B_now-2*z.B_own_lag5_raw+z.B_own_lag10_raw;z['a_pair_raw']=z.dB5_paired-z.dB5_paired.shift(5)
 col=['date','sector_id_static','industry_static','Nstatic','N_U_t','N_above20_t','N_above20_tminus5','B_now','dB5_paired','a_own_raw','a_pair_raw']
 comparison=pd.concat([x.loc[x.date.eq('2024-09-24')&x.case_role.eq('MAIN'),col],z.loc[z.date.eq('2024-09-24'),col]],ignore_index=True)
 comparison.to_csv(O/'PREDECLARED_924_CUTOFF_SAMPLE_SIZE_COMPARISON.csv',index=False)
 source=TASK/'native_algorithm_read_v1/cp_pvr/SOURCE_SHA256.json';declared=json.loads(source.read_text());model=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code/model.py');assert sha(model)==declared[str(model)]
 snippet=TASK/'native_algorithm_read_v1/cp_pvr/snippets/CP_constants_features_calculate.py.txt'
 dump('FORMULA_SOURCE_BINDINGS.json',{str(p.resolve()):sha(p)for p in [source,model,snippet,old,peer,Path(__file__)]})
 variables={
 'B_now':'Saved conditional U_t fraction C_T>SMA20_T; not full-market/industry membership breadth.',
 'Bmarket_subpool':'Sum saved N_above20 over all90 /sum N_U. Its shifts/acceleration use each dates own U.',
 'own_change5_raw':'B(T)-B(T-5), using each dates own eligible U.',
 'a_own_raw':'B(T)-2B(T-5)+B(T-10); changing cohorts retained.',
 'a_pair_raw':'saved dB5_paired(T)-saved dB5_paired(T-5); two separately paired intervals, not one cohort across both.',
 'share5/share20':'Original frozen same-T U: stock CNY sum recent5 /pool sum recent5, versus preceding nonoverlap20; no net flow interpretation.',
 'log_share5_over_share20_raw':'ln(share5/share20); unknown if nonpositive or absent.',
 'sector_amount_ratio21_sameTcohort':'At each T fix U_T members; sector aggregate CNY at T /median of its21 aggregate daily amounts T-21..T-1.',
 'pool_amount_ratio21_sameTcohort':'Same formula, all1709 static stocks qualifying into U_T across90 sectors; not all-A turnover.',
 'index_r1_log':'ln(raw industry index close_T/close_previous CSI session), complete same source segment.',
 'index_R5_log':'Original saved industry-minus-CSI rs_ind5 plus CSI same-common-session return5.',
 'prior20/60_high_close':'Maximum of previous20/60 close, excludes T; complete positive common sessions in one segment.',
 'newhigh20/60':'close_T strictly above the known preceding-close maximum; no new gate.',
 'crossup20/60':'newhigh(T) AND NOT newhigh(T-1), nullable/Kleene; not historical first.',
 'cp_original_r/s/z/scale':'Literal saved original CP fields; s=1.4826*median(previous63 abs daily logreturn), shift1,clip>=1e-8; z=max(s,log1p(.001)); scale is anchor/reset-frozen z.',
 'z1_new_r1_over_cp_prior63_s':'New descriptor r1/s using saved original s. Not original CP.z, not standard-normal significance, no threshold.',
 'cp_original_delta_frontier/receipt':'Original CP frontier increment and receipt are separate; no gate or state recomputed.',
 'next_common_session':'Earliest calendar opportunity after T-close information; not a fill or next-open execution guarantee.'}
 dump('VARIABLE_FORMULA_CLOCK.json',variables)
 lines=['v5固定原量诊断：168行完整交付（不实施新门、排名、账户）','',
 '主84+辅助21+预定反例63；76个唯一会话，5个真实行业指数。窗口锚是事先指定日历/旧研究日期，不是算法识别launch；窗口后15行属于随后才可见的观察，不是锚日已知输入。',
 '完整数值：RAW_PATHS_COMPLETE.parquet/csv；锚日8行：ANCHOR_RAW_COMPLETE.csv。与feature_paths的case_id映射见CASE_ID_MAPPING.csv。',
 '同T U掩码：U_T_MASK_ALL_FIXED_DATES.parquet，129884=76×1709；全部90行业×76日原NU/Nup/Nup5精确核平，share5/20重建误差0。金额薄提取最终耗时7.63秒；无账户、CP模型或新资格运行。',
 '',
 '锚日连续原量（r1、R5均为log return；s为原prior63稳健尺度；倍数为行业CNY金额/同cohort prior21聚合中位数）：']
 for r in a.itertuples():lines.append(f'{r.case_id} {r.date}: NU={r.N_U_t:g}/{r.Nstatic:g}static，Nup5→now={r.N_above20_tminus5:g}→{r.N_above20_t:g}；a_own={r.a_own_raw:.6f}, a_pair={r.a_pair_raw:.6f}；ln份额比={r.log_share5_over_share20_raw:.6f}；行业额倍数={r.sector_amount_ratio21_sameTcohort:.6f}, 子池额倍数={r.pool_amount_ratio21_sameTcohort:.6f}；r1/s={r.z1_new_r1_over_cp_prior63_s:.6f}；20/60above={r.newhigh20}/{r.newhigh60}、crossup={r.crossup20}/{r.crossup60}。')
 lines.extend(['','可复核含义及边界：',
 '1. 924三个行业广度加速度均正；2026Jan5/Jan15半导体均负。正加速度不能凭这些已知例子直接当必需启动门。',
 '2. 924半导体/通信相对份额下降，尽管行业CNY成交额较自身前21日放大。份额和绝对成交扩张是不同量，份额不是净流入。',
 '3. Oct8软件/多元金融的r1/s与成交倍数很大，且已在20/60高点之上，但crossup均False；价格冲击大不等于首次启动。反例是探索性已知风险窗口，不是未用测试集，也不能将窗口内每一天统称错误信号。',
 '4. PREDECLARED_924_CUTOFF_SAMPLE_SIZE_COMPARISON.csv另列原T第3厨卫电器。其当前静态子池仅1股，合格1股的Nup5→now=0→1与软件32股中13→31共同进入分位比较；不是说历史全行业只有1股。a_own/a_pair同样受人数与成员变化影响。本次不后验加入minimumN门。',
 '5. s、旧z、冻结scale已分列；oldCP.z是尺度而非r/s。共有会话r1与原CP.r最大差1.56e-15，仅浮点形式差异。r1/s与原CP价格冲击同源，不是独立新增信息。',
 '6. 原静态1709、当前市值筛选和2026行业桥非PIT，广度与金额是该条件子池；指数为原价格指数，未认证TR。日线CLOSE输入不能证明当日OPEN或次日涨停可成交。',
 '7. 同Tcohort金额分母是21个每日聚合值的中位数，不是个股中位数求和。行业指数amount单位未用于跨行业求和。',
 '8. 首次短calendar提取在守卫处停止，原始失败原因与修正见EXTRACTION_HISTORY.txt；最终严格复用原v2日历前缀，不改公式、阈值或母体。','',
 '本包仅提供固定正反例连续原量与因果时钟，不能证明至少2/3门、某系数、选中名单或账户收益。'])
 (O/'READOUT.txt').write_text('\n'.join(lines)+'\n')
 dump('FINAL_DELIVERY_STATUS.json',dict(status='COMPLETE_RAW_ONLY',rows=168,main=84,aux=21,counter=63,unique_dates=76,static_stocks=1709,mask_rows=129884,amount_date_sector_rows=6840,new_accounts=0,new_CP_models=0,new_gates=0,new_ranks=0,all_outputs_fixed_windows=True))
 files={str(p.relative_to(O)):sha(p)for p in sorted(O.iterdir())if p.is_file()and p.name not in ['OUTPUT_SHA256.json']};dump('OUTPUT_SHA256.json',files)
 print(json.dumps({'complete':True,'rows':len(x),'bound_files':len(files),'directory':str(O.resolve())},ensure_ascii=False))
if __name__=='__main__':main()
