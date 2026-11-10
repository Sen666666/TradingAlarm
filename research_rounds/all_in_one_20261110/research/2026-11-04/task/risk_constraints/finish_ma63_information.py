"""Readout for frozen inclusive63 information results; no new features/accounts."""
from pathlib import Path
from decimal import Decimal as D
import json,hashlib,collections
HERE=Path(__file__).resolve().parent;O=HERE/'ma63_information_diagnostic_v1'
def read(p):return json.loads(p.read_text())
def n(x):return D(str(x))
def fmt(x):return f'{n(x):,.2f}'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
    r=read(O/'RESULTS.json');entries={ref:read(O/(ref+'_ENTRIES.json')) for ref in r};post=[x for x in entries['2022_2024'] if '2024-10-09'<=x['opened'][:10]<='2024-12-31'];assert len(post)==303
    postgroups=[]
    for key in sorted({x['MA63_class'] for x in post}):
        ee=[x for x in post if x['MA63_class']==key];postgroups.append(dict(MA63_class=key,fills=len(ee),actual_buy_cash=sum((n(x['cost']) for x in ee),D(0)),actual_full_life_contribution=sum((n(x['net']) for x in ee),D(0)),
            strict_realized=sum((n(x['strict_realized']) for x in ee),D(0)),unrealized=sum((n(x['open_unrealized']) for x in ee),D(0)),recognized_AR=sum((n(x['recognized_dividend_AR']) for x in ee),D(0))))
    save(O/'POST_OCT8_303_ACTUAL_FILLS.json',dict(fills=post,summary=postgroups,industry_MA_not_above_fills=sum(x['industry_state']['above'] is False for x in post),
        scope='all actual new fills openedOct9–Dec31; labels at actual decisionCLOSE; equity-flat by existing end, includes their recognizedAR; not deletion/counterfactual'))
    tails={}
    for ref in r:
        tt=read(O/(ref+'_ORIGINAL_FIXED_TAIL_COVERAGE.json'));groups=[]
        for key in sorted({t['original_MA63_class'] for t in tt}):
            gg=[t for t in tt if t['original_MA63_class']==key];ids={lid for t in gg for lid in t['matched_No60_layers']};own=[x for x in entries[ref] if x['layer'] in ids]
            groups.append(dict(original_MA63_class=key,original_tail_members=len(gg),original_actual_buy_cash=sum((n(t['original']['cost']) for t in gg),D(0)),original_actual_net=sum((n(t['original']['net']) for t in gg),D(0)),
                original_matched_members=sum(not t['unmatched'] for t in gg),unique_matched_No60_fills=len(ids),actual_matched_No60_buycash=sum((n(x['cost']) for x in own),D(0)),actual_matched_No60_net=sum((n(x['net']) for x in own),D(0)),
                original_active_members=sum(bool(t['original']['qty']) for t in gg)))
        tails[ref]=groups
    save(O/'FIXED_ORIGINAL_TAIL_SUMMARY.json',tails)
    p=r['2022_2024'];s=r['strong'];dual=next(x for x in p['groups']['by_MA'] if x['labels']['MA63_class']=='S+I+')
    text='''# 固定 inclusive MA63 信息诊断：不足以解释主损耗

本轮负结论是：价格相对63日均线与旧63观察收益正负存在数值非冗余，但主要亏损已经发生在股价和行业均高于均线的实际入场中。不能据当前结果把慢背景均线门晋升为核心修正，更不能把删除某组的事后净损益叫可避免损失。

本协议在计算前冻结，SHA `58fd99a563ace65caee4dc2bfd7d82d0318caad00d3de088f4061e86fff8cdbc`。范围为No60完整2022→2024全部2,265笔实际买入，以及正常strong全部1,171笔；覆盖所有角色、初试/加仓/重入，未知不删除。零新账户。

重要语义：本轮MA是**包含决策当日及前62观察**的inclusive简单平均，比较C_t>inclusiveSMA63，代数上等价C_t>previous62mean。它不是pool另冻草案的industry C_t>previous63mean，不能用这里的命中数声称exact B门效果。那一版本由独立分工按另定协议检查，本轮不改窗、不改定义、不择盈亏组。

价格用既有因果信号复权close，股票逐点核raw_close×factor；行业用原CP1_input.close。完整warm只按原价格可比/连续源segment_id，不按E0/I趋势、attempt或持仓重新rolling。每个样本只用actual budget_order decisionCLOSE之前及当日精确报价；两个时钟signal_at与decision_at均保留，本样本差异为0，未借成交OPEN后的收盘。6185个精确窗口快照，stock/industry未知0、ETF宏观未知0、MA相等0；这只描述实际成交母体，不代表所有未成交机会都有完整资格。

| 母体 / 决策MA组 | 实际买入笔数 | 实际含费累计买款 | 全生命周期净贡献 | 严格已实现 | 未实现 | 股息AR |
|---|---:|---:|---:|---:|---:|---:|
'''
    for ref,z in r.items():
        for g in z['groups']['by_MA']:text+=f"| {ref} / {g['labels']['MA63_class']} | {g['fills']} | "+' | '.join(fmt(g[k]) for k in ['actual_buy_cash','net_lifetime','strict_realized','open_unrealized','recognized_dividend_AR'])+' |\n'
    text+=f'''
三年S+I+为1,841/2,265笔，买款18,116,168.90元，占全实际买款的{fmt(n(dual['actual_buy_cash'])/n(p['overall']['actual_buy_cash'])*100)}%；该组净亏281,466.86元，主损耗不能概括为“在均线下仍扩张”。strong同组净贡献1,287,679.23元，含815,606.46元未实现和8,669.80元未收AR，不能叫全部已实现利润。全账分别闭合−362,010.39及+1,263,281.23元。

累计买款包含循环使用资本，不是独立本金。`fully_crossed`还保留各MA×macro×action×role组平均实际仍持仓成本、市值暴露、买卖费用、已平负层自身买款分母。已平正负、严格real+open+AR和层生命周期口径分列，没有重复扣费。net/buycash仅描述；没有用线性缩仓或按费用机械相除得到alpha。

旧63正号是同源close/shift63−1（需64观察），与本MA63不同。三年有516笔（买款4,502,069.44元）至少一轴标签不同，strong有159笔（2,144,447.30元）；这些差异组生命周期净贡献分别+18,375.01/+54,265.53元。存在不同不等于有用的修正；完整`by_MA_vs_return63`交叉保留，未只比较最赚钱格。

旧净推进是当前行业价格相对原probe close，以probe close−原冻结初始保护线为R；不是均线。本轮逐原行业state完整warm重建同一probe、初始线和R，unknown0，`by_MA_vs_original_probe_R`保留全交叉。三年原>=2R的617笔买款6,403,139.94元、净−204,595.69元；strong同档470笔净+387,320.65元。已有I/E0方向、RS/Q/CP1推进和较大净推进并不保证经济成功，不能把旧策略称为没有方向条件。

固定失败与恢复阶段按实际**期内财富**归因；入场时MA标签之后不变化，继承旧层和之后新层都在，未将层终生损耗误贴到该期：

| 既有固定阶段 | S+I+财富变化 | S+I− | S−I+ | S−I− |
|---|---:|---:|---:|---:|
'''
    phase=read(O/'2022_2024_ACTUAL_PHASE_WEALTH.json')
    for label in ['retrospective_L02','retrospective_L03','retrospective_L04','retrospective_L05','pre924','924_to_Oct8','postOct8']:
        gg={x['MA63_class']:x for x in phase if x['phase']==label};text+='| '+label+' | '+' | '.join(fmt(gg[k]['actual_phase_wealth']) for k in ['S+I+','S+I-','S-I+','S-I-'])+' |\n'
    text+='''
L02–L05沿既有HS30010%事后分段，仅用于诊断；L04是2022Nov1→2023Jan30，市场上行而No60失败，S+I+仍承担25,690.01元净损失。L03同组−89,608.38元。L05虽然市场下降，既有该组仍恢复55,912.67元，不能按市场阶段事后排除。每个阶段保留含费实际投入、持仓成本、市值暴露、real/unreal/AR；入口cohort终生贡献另存`ENTRY_PHASE_LIFECYCLE_COHORTS`，不可与此表互换。重叠year/quarter/leg标签不可累加。

Oct8后全303笔实际新买入另作完整子母体：

| MA组 | 实际笔数 | 含费买款 | 这些新层至现有终态的贡献 |
|---|---:|---:|---:|
'''
    for g in postgroups:text+=f"| {g['MA63_class']} | {g['fills']} | {fmt(g['actual_buy_cash'])} | {fmt(g['actual_full_life_contribution'])} |\n"
    text+='''
303笔行业inclusiveMA以下为0；301笔双MA以上净−113,650.06元，2笔stock不高于均线/industry高于净+1,192.46元，总计−112,457.60元。它们是真实新成交贡献，不能全部归为Oct8已有赢家回吐。整个postOct8财富−167,054.32元中，固定在S+I+入场类的期内变化−157,701.71元；慢MA背景不是这处主要新试错损耗的充分解释。以上只针对inclusive，未冒充exact prior63B。

ETF宏观标签来自benchmark已冻同一USHJ510300因果再投资close，固定63平均扩展到相同源2018→2026，先与已冻2022–23 history1327行（ready1265行）核同signal/MA/on。该标签是入场当时ETF close相对均线，非持有期间始终状态、非原ACT行业等权synthetic market。三年S+I+且ETF也above的911笔仍净−204,969.45元；宏观同向标签不能自动修复个股信号/退出反馈。无法从实际成交母体评估ACT恢复A产生的未见新机会，不能把这份表当A反事实。

原固定tail反例名单在任何MA标签前完整冻结：原PVR三年83层、strong94层，定义沿原whole-life net/含费buycash>=30%，含原股息/期末mark；这是本轮MA前冻结的最新2024名单，不谎称2024运行前已冻，也不是cash-closed campaign。跨arm只用sid/actual budget决策/role/CP1receipt、core原watch epoch核对，不用本地layer或内生attempt强配。全部名单及未匹配都保留：

| 原固定tail母体 / MA组 | 原成员 | 原实际买款 | 原贡献 | 有No60实际对应的原成员 |
|---|---:|---:|---:|---:|
'''
    for ref,gg in tails.items():
        for g in gg:text+=f"| {ref} / {g['original_MA63_class']} | {g['original_tail_members']} | {fmt(g['original_actual_buy_cash'])} | {fmt(g['original_actual_net'])} | {g['original_matched_members']} |\n"
    text+='''
strong原固定尾层6个处于industry inclusiveMA以下，原贡献合计27,159.06元；只有2个在No60有精确实际对应，另外4个未成交，不能叫No60一定会损失的6个赢家。全三年该类13个原尾层贡献17,259.22元，亦保留所有实际对应和未对应。原窗口具代表的正控包括凯格精机、科瑞技术、新疆众和、远东股份等；全名单不是挑两张成功图。任何未来不准入后的再入、腾资及新机会均未模拟，金额只是资格反例，不是可实现政策损失。

结论边界：本MA提供与旧63正号不同的标签，但既有主要失败处仍有大量同向且成熟的真实资本，当前不足以支持它成为主解。根因研究应继续审信号有效性、初试资金和保护/纠错反馈；不能因一个被删格净亏就新增门、加长窗口或延伸均线研究。强窗盈利和尾部反例同时保留，不预设“更慢确认”一定改善。

证据：`RESULTS.json`全母体/资本/real+open+AR；`*_ENTRIES.json`逐笔决策/价域/MA/oldreturn/R/macro/实际资金；`*_ACTUAL_PHASE_WEALTH.json`真实阶段财富；`POST_OCT8_303_ACTUAL_FILLS.json`全303；`ORIGINAL_FIXED_TAIL_COHORT_PRE_FEATURE.json`及`*_ORIGINAL_FIXED_TAIL_COVERAGE.json`完整旧尾和exact匹配；`MACRO_OVERLAP_GATE.json`宏观重叠核；`SOURCE_MANIFEST.json`1406源指纹。当前1709幸存者/当前行业开发样本、原日线执行和历史已消费限制仍在；无HK/OOS/120万实盘验证。
'''
    auditp=HERE.parent/'independent_review/PVR_MA63_INFORMATION_AUDIT.json';audit=read(auditp)
    text+='\n独立最小全量审查通过：`../independent_review/PVR_MA63_INFORMATION_AUDIT.json` 核1406SHA、6185直接63/坐标快照、全部2265/1171决策时钟与原decision成员、968日固定entry组现金/AR/rawvalue财富桥、116阶段行和原83/94尾名单/key。ProbeR、ETFmacro和strictreal细分为源码审范围，不冒称其数值另经独立全重算。\n'
    (O/'READOUT.md').write_text(text)
    save(O/'READOUT_BINDING.json',dict(account_events=0,protocol_sha256=read(O/'PROTOCOL_FREEZE.json')['protocol_sha256'],independent_audit_path=str(auditp),independent_audit_sha256=sha(auditp),
        scope='inclusive63 fixed diagnostic; not pool exactprior63B or ACT recoveryA; no deletedgroupcounterfactual',readout_sha256=sha(O/'READOUT.md'),finisher_sha256=sha(Path(__file__)),
        result_sha256=sha(O/'RESULTS.json'),source_manifest_sha256=sha(O/'SOURCE_MANIFEST.json')))
    print('MA63_READOUT_READY',len(post),'postOct8 fills',sum(len(x) for x in tails.values()),'fixedtail group rows')
if __name__=='__main__':main()
