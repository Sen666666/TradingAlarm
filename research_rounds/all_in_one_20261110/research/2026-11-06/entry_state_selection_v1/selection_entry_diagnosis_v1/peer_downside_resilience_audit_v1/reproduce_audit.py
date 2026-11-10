
import numpy as np, pandas as pd, json, hashlib, math
from pathlib import Path
P=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared')
B=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1')
M=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/metadata.json')
d=pd.read_csv(B/'ALL_FIRST_ENTRIES.csv'); d['row_id']=np.arange(len(d))
meta=json.loads(M.read_text())
h=np.load(P/'h1.npz'); dates=pd.DatetimeIndex(h['dates']); symbols=list(h['symbols'])
ids=[s for s in symbols if not s.startswith('URFI')]
C=pd.DataFrame(h['close'],index=dates,columns=symbols).loc['2021-01-01':'2026-05-15',ids].copy()
G=pd.DataFrame(h['segment'],index=dates,columns=symbols).reindex(C.index)[ids]
C=C.where(np.isfinite(C)&C.gt(0)); R=np.log(C).diff().where(G.eq(G.shift()))
sects={}
for s in ids: sects.setdefault(meta[s]['sector_id'],[]).append(s)
features=[]
for sec, mem in sects.items():
    rr=R[mem]; su=rr.sum(axis=1,min_count=1); co=rr.notna().sum(axis=1)
    for sid in mem:
        if not (d.sid==sid).any(): continue
        peer=(su-rr[sid].fillna(0))/(co-rr[sid].notna().astype(int)).replace(0,np.nan)
        resid=(rr[sid]-peer).where(peer<0,0).where(rr[sid].notna()&peer.notna())
        A=resid.shift().rolling(20,min_periods=20).sum()
        ndown=peer.lt(0).astype(float).where(peer.notna()).shift().rolling(20,min_periods=20).sum()
        peer_n=(co-rr[sid].notna().astype(int)).shift().rolling(20,min_periods=20).min()
        for row in d[d.sid==sid].itertuples():
            t=pd.Timestamp(row.signal_day)
            if t not in C.index: continue
            risk=np.log(row.original_close/row.first_role_floor) if row.original_close>0 and row.first_role_floor>0 and row.original_close>row.first_role_floor else np.nan
            val=A.loc[t]
            features.append(dict(row_id=row.row_id,A=val,risk=risk,Q=val/risk if np.isfinite(risk) else np.nan,down_days=ndown.loc[t],min_peers=peer_n.loc[t],price_error=C.at[t,sid]-row.original_close))
f=pd.DataFrame(features); x=d.merge(f,on='row_id',validate='one_to_one')
x['outcome']=np.where(~x.closed,'OPEN',np.where(x.round_pnl>0,'WIN','LOSS'))
x['known']=np.isfinite(x.Q); x['nonpositive']=x.known & x.Q.le(0)
def sm(g):
    return pd.Series(dict(n=len(g),known=int(g.known.sum()),A_mean=g.A.mean(),Q_mean=g.Q.mean(),A_median=g.A.median(),Q_median=g.Q.median(),nonpositive=int(g.nonpositive.sum()),min_peer=g.min_peers.min(),min_down=g.down_days.min()))
print('AUDIT',json.dumps(dict(rows=len(x),known=int(x.known.sum()),A_unknown=int(x.A.isna().sum()),risk_unknown=int(x.risk.isna().sum()),max_price_error=float(x.price_error.abs().max()),source_sha256=hashlib.sha256((B/'ALL_FIRST_ENTRIES.csv').read_bytes()).hexdigest())))
print('YEAR_OUTCOME'); print(x.groupby(['account','year','outcome']).apply(sm,include_groups=False).round(6).to_string())
print('PVR_SIGN_BINS'); print(x[(x.account=='PVR')&x.closed&x.known].groupby(['year','nonpositive']).agg(n=('row_id','size'),wins=('round_pnl',lambda a:int((a>0).sum())),mean_original_round_return=('round_return_on_cumulative_cost','mean')).to_string())
print('BIG_COVERAGE'); print(x[(x.account=='PVR')&x.big60_posthoc].groupby('year').agg(n=('row_id','size'),known=('known','sum'),nonpositive=('nonpositive','sum')).to_string())
print('MAJOR_WINDOWS'); print(x[(x.account=='PVR')&(((x.signal_day>='2024-09-19')&(x.signal_day<='2024-10-08'))|((x.signal_day>='2025-12-15')&(x.signal_day<='2026-01-23')))].groupby(['year','sector']).agg(n=('row_id','size'),known=('known','sum'),nonpositive=('nonpositive','sum'),big=('big60_posthoc','sum')).to_string())
pairs=pd.read_csv('/Users/bytedance/Documents/Codex/2026-11-06/multiscale_entry_R_coverage_v1/MATCHED_PAIRS.csv')
print('PAIR_COLUMNS',pairs.columns.tolist())
ff=x.set_index('row_id')
pairs['delta_Q']=pairs.winner_row.map(ff.Q)-pairs.loser_row.map(ff.Q)
pairs['delta_A']=pairs.winner_row.map(ff.A)-pairs.loser_row.map(ff.A)
def ps(g):
    a=g.delta_Q.dropna(); b=g.delta_A.dropna()
    return pd.Series(dict(n=len(g),known=len(a),days=g.day.nunique(),win_Q_higher=int((a>0).sum()),lose_Q_higher=int((a<0).sum()),equal=int((a==0).sum()),delta_Q_mean=a.mean(),delta_Q_median=a.median(),win_A_higher=int((b>0).sum()),lose_A_higher=int((b<0).sum()),delta_A_mean=b.mean()))
print('PAIR_YEAR');print(pairs[pairs.scope=='all_closed'].groupby(['account','year']).apply(ps,include_groups=False).round(6).to_string())
print('PAIR_ALL');print(pairs.groupby(['account','scope']).apply(ps,include_groups=False).round(6).to_string())
print('PVR_WEAK');print(pairs[(pairs.account=='PVR')&(pairs.scope=='all_closed')].groupby('weak').apply(ps,include_groups=False).round(6).to_string())
print('FIXED_CASES');print(x[(x.account=='PVR')&x.sid.isin(['600606.SH','002385.SZ','688582.SH','300182.SZ','600056.SH','601607.SH','300666.SZ','603061.SH','301611.SZ','002317.SZ'])][['sid','signal_day','entry_day','first_kind','A','risk','Q','down_days','min_peers','closed','round_pnl','big60_posthoc']].to_string(index=False))

O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/selection_entry_diagnosis_v1/peer_downside_resilience_audit_v1')
O.mkdir(parents=True,exist_ok=True)
x.to_csv(O/'ALL_FIRST_ENTRY_FEATURES.csv',index=False)
pairs.to_csv(O/'EXISTING_MATCHED_PAIRS_WITH_Q.csv',index=False)
x.groupby(['account','year','outcome']).apply(sm,include_groups=False).to_csv(O/'ANNUAL_OUTCOME_DIAGNOSTIC.csv')
pairs[pairs.scope=='all_closed'].groupby(['account','year']).apply(ps,include_groups=False).to_csv(O/'MATCHED_YEAR_DIAGNOSTIC.csv')
p=x[x.account=='PVR']
p[(p.signal_day>='2024-09-19')&(p.signal_day<='2024-10-08')].to_csv(O/'FIXED_924_ORIGINAL_ENTRIES.csv',index=False)
p[(p.signal_day>='2025-12-15')&(p.signal_day<='2026-01-23')&(p.sector=='URFI881121')].to_csv(O/'FIXED_SEMICONDUCTOR_ORIGINAL_ENTRIES.csv',index=False)
(O/'READOUT.md').write_text("# 行业下跌日相对抗跌 / 原保护风险：一次机制证伪\n\n## 结论\n停止此候选，不进入候选重排或账户，不反转方向、不改窗口或阈值补救。它没有显示稳定地优先原赢家，且会压低一批反转赢家。\n\n这是已被原账户选中首仓的历史描述，不是新策略反事实，也不是全部未入候选检验。未认证实际成交。已有历史反复研究，非样本外。公式在父任务消息中先声明后计算，此报告和文件在结果后保存，不能称预先保存的冻结文件。\n\n## 预先定义的单一假设\npeer 为同一原固定行业、排除本股的等权日对数收益。仅同源连续价格有效的成员进入当日peer平均；peer无有效成员则未知。原1709成员与行业来自未来静态名单，未PIT认证。\n\nA = 过去20个共同交易日（t-20至t-1，不含信号日t）中，peer<0的日子，个股日对数收益减peer日对数收益的总和。\nR = log(信号日原native close / 原first_role_floor)，仅原价格和保护线正有限且0<S<C时有效。\nQ=A/R；无epsilon、无截尾、无新阈值。A≤0仅用自然方向边界记录潜在降权覆盖，不据此删单。缺任一目标或peer日收益则整个20日A未知；未知保留，不当0或最差。\n逻辑是：若此前行业受压时个股已显示相对韧性，且当前到原保护线距离较小，则可能拥有较好的新入场质量。区别于原PVR的上涨记账、两轮成交额比较、次日突破、总20日相对涨幅、行业广度硬门。\n结果否定当前方向有可靠质量增益，不能因逻辑合理就采用。\n\n## 覆盖与源核验\n5373行两账户首仓，Q可算5311，未知62。主PVR2693行，2653可算、40未知。原price与H1矩阵逐条最大误差5.68e-14。\n全5373行另按明确20日切片、同行业直接排除本股平均重新计算A，最大误差1.11e-16，无超过1e-12的差异。8个跨源窗口均为UNKNOWN，没有带入旧source收益。\nPVR风险R最小0.0045803，1%分位0.0239485，中位0.0939728，99%分位0.5333073。未事后截尾或替换分母。PVR风险本身全部有效；Q未知来自历史/peer收益不足。\n原可用矩阵缺价不补、停牌不能造收益；同行业peer每日有效成员会变化，不是固定平衡面板。未认证历史资格、行业或公司行为发布时间。\n\n## 同日近原分配对\n复用既有MATCHED_PAIRS，不根据新Q重新配对：同账户、同signal_day、H1与PVR各差≤5，按原分欧氏距离贪心一对一。标签用于后验构建赢家/亏家配对，天然一赢一亏，不能称策略胜率。\nPVR162对，其中158对Q可算：赢家Q高81对，亏家Q高77对；Q赢减亏均值−0.107466，中位+0.017214。\n按入场年：2022为25/21，2023为13/13，2024为21/18，2025为15/22，2026部分为7/3（依次赢家Q更高/亏家Q更高）。均值差2022−0.04815、2023+0.10352、2024−0.20359、2025−0.32210、2026+0.24015。\nE31也仅83/79，均值差−0.060735。两账户共享股票与市场，不合并成独立证据。\n未标准化不同股票风险的极端Q不会解释全部失败：即使只看分子A，PVR仍81/77、均值差−0.006019，没有稳定方向。\n\n## 赢亏覆盖与大行情代价\nPVR675原已闭赢家、1951亏家。Q≤0涉及167赢家（24.74%）与417亏家（21.37%），赢家受影响比例反而更高。未知单列。\n原2022年末692闭局：已知Q>0的524局87赢（16.60%）；Q≤0的162局42赢（25.93%）；未知6局1赢。不是删单之后新系统胜率。\n按原big60后验路径标签，Q≤0涉及2022的21/73、2023的11/46、2024的31/113、2025的26/121、2026部分0/11。big60为下一开盘起完整60共同观察、最大收盘上行≥30%、期末≥20%，不是闭局赢家或可执行收益。\n\n## 重点行情与固定病例\n2024-09-19至10-08的原PVR实际首仓17条，14原净赢家；Q≤0的4条全是原赢家，其中含9个big60中的3个。这里是原已入场子集，不能据此声称完整924行情覆盖。\n2025-12-15至2026-01-23半导体原实际首仓6条。最高Q=3.557的002151原亏；唯一big60 300672的Q=0.1368。300666与301611于1/15的Q约0.2621/0.2414，原完整回合均亏；不能拿此前局部上涨替换实际入场结果。\n固定病例：\n- 002385 2022-03-04失败：Q−1.1550，方向有利于区分这一例。\n- 300182 2022-01-04失败：Q+0.4219。\n- 600606 2022-03-22赢家：Q−0.2173。\n- 688582 2024-07-29赢家：Q+0.0231。\n- 600056 2022-03-03大赢家：Q+0.4026；3/30末端失败：Q+5.5668。\n最后一对是核心反例：已形成强脉冲后在行业下跌日继续相对走强，会让末端失败获得很高韧性分。把全段相对抗跌除以当前原保护距离仍把过去强势误当下一笔机会。\n\n## 边界与下一步\n当前Q不晋升，不与CE、LDP或CP量额降权组合，不通过更换20日窗口、截尾或相反方向救活。原交易标签只诊断质量，不沿用为新排序的收益。\n现有价格/量额/固定行业信息里，未获得可直接支持30%完整净胜率的新增规则。下一次研究应先明确新的机制或新的可见信息，再预先注册；不以继续拼接失败公式作为默认推进。\n",encoding='utf-8')
(O/'PROTOCOL_RECORDED_AFTER_AUDIT.json').write_text(json.dumps(dict(status='STOP; formula declared in parent message before inspection; this file saved after results',formula='A=sum_{u=t-20..t-1,peer_u<0}(r_stock_u-r_peer_u); R=log(native_C_t/original_first_role_floor); Q=A/R',window=20,no_current_signal_return=True,no_epsilon=True,no_clipping=True,missing='unknown if any target or peer return missing in window',industry='fixed future-selected original1709 roster; non-PIT; exclude own stock',paired_source='existing frozen same-day matched pairs; not rematched using Q',account_runs=0,new_candidate_reorders=0,parameter_searches=0,scope='original selected first entries only; not counterfactual'),ensure_ascii=False,indent=2))
(O/'SOURCE_HASHES.json').write_text(json.dumps({str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in [P/'h1.npz',M,B/'ALL_FIRST_ENTRIES.csv',Path('/Users/bytedance/Documents/Codex/2026-11-06/multiscale_entry_R_coverage_v1/MATCHED_PAIRS.csv')]},indent=2))
print('SAVED',O)
