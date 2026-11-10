from pathlib import Path
from decimal import Decimal as D
import json,hashlib
import pandas as pd
O=Path(__file__).resolve().parent;R=O/'full_20241031_once';read=lambda p:json.loads(Path(p).read_text());o=pd.read_csv(R/'ORDERS.csv');a=pd.read_csv(R/'ATTEMPTS.csv');h=pd.read_csv(R/'HOLDINGS.csv');c=pd.read_csv(R/'CANDIDATES.csv');led=pd.read_csv(R/'DAY_LEDGER.csv');first=a[a.signal_day.lt('2024-09-18')];firstids=set(first.id);first.to_csv(O/'SEP06_ALL34_ATTEMPTS.csv',index=False);o[o.round_id.isin(firstids)].to_csv(O/'SEP06_ALL34_ORDERS.csv',index=False)
name=o.drop_duplicates('sid').set_index('sid').name.to_dict();hx=h[h.day.eq('2024-09-23')].groupby('sid').agg(shares=('qty','sum'),market_value=('market_value','sum')).reset_index();hx['name']=hx.sid.map(name);hx.to_csv(O/'SEP23_ALL30_HOLDINGS.csv',index=False)
byday=o[o.day.le('2024-09-24')].groupby(['day','side']).agg(orders=('qty','size'),shares=('qty','sum'),cash_delta=('cash_delta','sum'),fees=('fee','sum')).reset_index();byday.to_csv(O/'PRE924_CASH_MOVEMENTS.csv',index=False)
old=pd.read_csv(O.parent/'CORE_DAILY_EXISTING_ACCOUNTS_RELABELED.csv');old=old[(old.sector51=='证券保险')&old.day.isin(['2024-09-23','2024-09-30','2024-10-08','2024-10-31'])];compare=old[['arm','day','stocks','market_value','weight_pct_NAV','marked_fee_net_pnl','account_NAV']].copy();compare['scope']='Old 90-sector full portfolio, sector51 relabel only'
z=led[led.day.isin(old.day.unique())][['day','stocks','market_value','weight_pct','NAV']].copy();z['arm']='new_local_sector_only';z['marked_fee_net_pnl']=z.NAV-1200000;z['scope']='New 52-member local cash account; no other-sector competition';z=z.rename(columns={'weight_pct':'weight_pct_NAV','NAV':'account_NAV'});pd.concat([compare,z],ignore_index=True).to_csv(O/'OLD_SECTOR_PATH_CONTEXT.csv',index=False)
openrej=c[(c.phase=='OPEN')&c.decision.ne('PASS')];openrej.to_csv(O/'CAPITAL_REJECTIONS.csv',index=False)
counts=dict(days=len(led),orders=len(o),attempts=len(a),unique_traded_stocks=o.sid.nunique(),seed_fills=int(o.side.eq('BUY_SEED').sum()),add_fills=int(o.side.eq('BUY_ADD').sum()),capital_rejected_seed_tickets=int(openrej.event.eq('SEED').sum()),capital_rejected_ADD_open_attempts=int(openrej.event.eq('ADD').sum()),unique_rejected_CP_ids=int(openrej[openrej.event.eq('ADD')].cp_id.nunique()),first_episode_closed_stocks=len(first),first_episode_pnl=float(first.marked_net_pnl.sum()),first_episode_fees=float(first.fees.sum()),last_NAV=float(led.NAV.iloc[-1]),last_marked_pnl=float(led.NAV.iloc[-1]-1200000),max_close_to_close_drawdown_pct=float((led.NAV/led.NAV.cummax()-1).min()*100),known_net80_dividends=16.56)
(O/'SUMMARY.json').write_text(json.dumps(counts,ensure_ascii=False,indent=2)+'\n')
text='''# 证券保险51类：宽种子、CP后续增配的有限连续路径

## 读数与范围
这是2024-09-02至2024-10-31、初始现金120万元、仅新证券保险类别52个研究成员的局部账户。不是51类共同竞争的完整策略。冻结经济合同不限制两只、不使用PVR排序或共享试错风险池；先最低合法单位，后按既有CP与板块增强条件加仓。37个交易日、100次实际种子尝试、4次ADD、206笔实际代理交易。

板块“至少半数连续2收盘且三日净扩散为正”是在已看9/6与9/18轨迹后提出的研究候选；冻结只防看到本轮资金结果后再调，绝非样本外或未见数据预注册。不能凭这轮晋升为普遍有效策略。

## 9/24之前已经持有了什么
- 9/19：16只A种子，含费买款16,626.33元，收盘市值16,608元，仓位1.3845%。
- 9/20：再8只B种子，买款8,177.59元，持24只，市值24,776元，仓位2.0655%。
- 9/23：先3笔ADD合计71,065.06元，再6只B种子10,689.01元；持30只、10,800股，市值106,624元，仓位8.8881%。现金1,093,000.34元，NAV1,199,624.34元。

三笔真实ADD为国信证券2,600股、国投资本4,000股、中信建投1,200股，种子各100股。国信消费9/19收盘CP，另两只消费9/20收盘CP，均先实际持仓、后出现新CP，等到9/20板块增强成立，9/23开盘再核费后盈利。

截至9/23全部历史累计种子买款72,979.97元，包括已退出9月初回合37,487.04元。仅9/18后目前30个种子买款35,492.93元，加上3笔ADD71,065.06元，共106,557.99元。累计买款不可当作在场占用资金。

## 普通假启动真正花了多少钱
9/6的18只A种子9/9成交，9/9的16只新B种子9/10成交，共34只、买款37,487.04元。没有ADD，9/11板块FALSE后9/12全部退出，卖回37,045.37元，完整费后亏441.67元，占初始资金0.0368%；其中买卖费用363.40元。18只A的−207.19元只是这个回合的一部分，不能再冒充完整新路径损失。

所有34个尝试及68笔买卖逐笔列在 SEP06_ALL34_ATTEMPTS.csv、SEP06_ALL34_ORDERS.csv。10月下旬还有新的小试回合，完整路径保留这些损耗，没有在大行情结束时择时截断账户。

## 2%是买款上限，不是亏损上限
2%是每次ADD含费资金预算的上限，不是“最大亏损2%”，更不是“已经赚的钱覆盖新风险”。全attempt费后盈利只提供方向门槛。

9/23前三笔ADD之前，整个100股种子净浮盈只有5.55、1.04、12.77元；ADD后立即按同一OPEN反向清算整轮，分别变为−37.33、−42.71、−31.39元。新增层跌到当时CP/I保护点（再扣5bp和卖费，假设没有跳空）的新增损失分别为1,242.83、1,104.45、1,493.56元；整轮一起在该点清算为−1,278.24、−1,124.80、−1,596.18元。跳空、跌停或成交限制可以使损失更大。

第四笔是9/24新华保险300股，含费10,093.69元。加前净利79.58元，加后立即整轮净清算58.17元；新增层保护点损失535.87元，整轮同保护点损失621.11元。详细价格、CP/I信号坐标、当日原价转换、费用与逐层保护估算在 ADD_OPEN_PROTECTIONS_AND_DOWNSIDE.csv。

### 仅9/23当时的静态量纲对照
不改变完整账户：若每张CP新增股数不超过已有股数，这三笔各100股，共含费3,501.97元，其他种子与此前现金流固定，9/23收盘市值39,025元、仓位3.2532%、NAV1,199,588.43元。它没有后续连续路径，不能和冻结版的10月收益作策略比较。

若仅用α=1示意“新增保护点损失不超过已有净利润”，最低100股对应损失57.42、37.36、133.63元，都大于已有净利5.55、1.04、12.77元，因此三只都买不下一手。α=1仅是利润覆盖的定义示例，不是优化参数。这同时暴露最低单位和最低佣金对利润门槛的影响。

## 后续资金与退出
- 9/30：32只，市值160,626元，占12.9415%，NAV1,241,165.32元。
- 10/8：32只，市值176,563元，占14.0452%，NAV1,257,102.32元。
- 10/31：只余国信证券100股种子，市值1,156元，现金1,237,246.12元，NAV1,238,402.12元。累计标记损益38,402.12元，含已实现交易费与16.56元NET80现金权益，未假设终日卖出。
- 若10/31全部按收盘−5bp并计卖费清算，NAV为1,238,395.89元。短窗最大收盘净值回撤1.4880%，不是连续日内风险或一般回撤承诺。

9/18及以后新尝试的合计标记贡献：9/23为66.01元，9/30为41,607.00元，10/8为57,544.00元，10/31为38,843.79元；与9月初−441.67元相加得到整个局部账户损益。COHORT_DAILY.csv逐日可追溯。

国投资本ADD层10/10退出，国信和中信建投ADD层10/11退出，核心继续由I保护决定；不是行业降温一起卖掉成熟核心。中信建投核心10/15退出，国投资本核心和新华10/16退出，国信核心到窗口末仍持有。

## 剩下的资本瓶颈
9/23前所有合格计划都没有资本拒绝。9/24新华原计划上限700股，只剩板块空间支持300股；接着按代码顺序接广发证券和东方财富两个种子，空间余72.82元，另外8个当日种子被10%板块资本帽拒绝。随后另外3张新种子票也拒绝。160次ADD开盘尝试被同一板块资本帽拒绝，涉及136个不同CP；重复等待同一个未消费CP不是新增证据、不是实际ADD次数。

10%只管买入，涨价超过10%不强卖，所以9/30与10/8权重可以超过10%。冻结排序是CP时间/信号时间再代码，这是透明基线，不能称优秀股票优先。局部账户没有其他行业抢钱；移入全51行业账户后现金与持仓结果仍可能改变。

## 与旧路径的有限对照
旧90行业组合只重标证券保险的贡献，未重跑：原风险版9/23证券保险0仓；取消风险但留probe资金帽版9/23为2.1368%，10/8为7.2366%，该板块标记贡献25,612.87元，10/31为15,869.08元。新局部路径相应为8.8881%、14.0452%、57,102.32元和38,402.12元。

这些是不同账户、不同入口、不同资金竞争下的读数，不是控制变量实验，也不是完整新策略优于旧策略的证明。完整四日期三旧路径加新路径见 OLD_SECTOR_PATH_CONTEXT.csv。

## 验证和保留限制
- 合成检查实跑：A/B的UNKNOWN、半数两日门、合法数量、零净利不加、CP不能重复消费、逐lot T+1、退出覆盖ADD。
- 额外执行检查实跑：OPEN时删除当前H/L/CLOSE/volume及资格字段，9/23订单保持相同；故意制造持仓无效CLOSE，整日状态回滚、部分订单另列，认证前缀不混入未完成日。
- 独立精确重放37日、206笔：现金、股数、lot、费用、应收、原价NAV、清算NAV均零残差；100个attempt均仅一次seed，4笔ADD均两时点严格净盈利、CP身份不重复。
- 第一条9/23前缀与扩展到10/31的订单、持仓、账本、CP、候选记录逐条一致。独立审查者另完成638项因果检查并通过。
- 14个窗口现金权益事实全部已逐项审核登记/除息/发放、金额和因子桥。实持只收到601236的3.76元、002673的0.80元、601688的12元；平安在登记日前已退出，不生成虚假权益。NET80是固定保守研究税务情景，不是真实税结算。
- 价格是raw OPEN±5bp成本代理；有8笔代理价超出实际日H/L，不能当作交易所真实可成交价。未验证tick价位、涨跌停排队或逐笔撮合，不使用事后H/L反向过滤。
- 当前存续研究池、当前行业和市值筛选、后修订行情及非PIT现金权益公告源仍有历史选择/信息偏差。

## 文件导航
FROZEN_CONTRACT.md、FREEZE.json及FREEZE_V2.json：冻结合同与来源。初9月代码/结果保留，TECHNICAL_AMENDMENT.json记载只涉及权益补证和异常日前缀回滚的技术修订，没有更改经济规则。
full_20241031_once/：完整DAY_LEDGER、ORDERS、HOLDINGS、CANDIDATES、CP_EVENTS、EQUITY_EVENTS、ATTEMPTS，均有JSON与CSV。每个实际seed成本/费用和每笔ADD前利润均保留。
ACCOUNT_RECONCILIATION.csv、INDEPENDENT_ACCOUNTING_QA.json、SUPPLEMENTAL_SYNTHETIC_QA.json：本实现独立重放和异常测试。父目录independent_audit_v1/保存外部审查结果。
'''
(O/'READOUT.md').write_text(text)
(O/'DELIVERABLE_SEAL.json').write_text(json.dumps({str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in O.rglob('*') if p.is_file() and p.name!='DELIVERABLE_SEAL.json'},ensure_ascii=False,indent=2)+'\n')
print(json.dumps(counts,ensure_ascii=False));print('READOUT_READY',O/'READOUT.md')
