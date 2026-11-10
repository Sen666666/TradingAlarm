from study import *
from model import evidence
_save=save
def save(p,x):
 if Path(p).exists():
  assert read(p)==x;return
 _save(p,x)

def initialize():
 save(O/'protocol.json',{'name':'COR-1 有缓冲的组合纠正；稳健性为主要目标','scope':'同407科技股11行业、已见2024至2026-10-27历史；当前存续/行业市值快照开发口径；每条账户独立100万元ACTIVE，不是实盘',
 'cohorts':STARTS,'initial_states':'每起点三种接纳顺序：0原RS；1首5个收盘内同10分RS区间按代码升序；2同区间按代码降序。仅个股排序，行业排序不变。第6收盘恢复原RS。不是预塞赢家/亏损仓，也不免初始成交费用。初始5日不同策略的同seed必须完全同账。若未形成不同持仓，如实报不可识别，不改日期或种子。',
 'variants':{'ACT':'原自然退出，不换仓','BUF':'每周第一个市场收盘、首次5收盘之后，有原I新买点且原行业资格，新RS>=50且比可行旧股高至少10分；旧股当前持有阶段至少10交易观察；按原行业/个股RS选择候选，旧股选可行最低RS，最多一对','COR':'与BUF完全相同，再要求新机会持续证据和旧股自身弱化同时成立'},
 'new_evidence':'最近5观察至少3观察E0有效且G1>=暖；当前收盘>EMA21，EMA21>5观察前EMA21，10观察收益>0，最近10观察收涨日真实成交金额/总金额>=60%。EMA21按同源连续有效段计算，至少21观察。',
 'old_weakness':'连续3观察收盘低于自身EMA21，10观察收益<=0，最近10观察上涨日金额/总金额<50%。绝对自身弱化，不因排名掉队自动弱化；无效源/金额缺失不提供证据。',
 'buffer':'新旧RS差>=10、旧股至少10观察、每周首收盘检查、每次最多一对。均事前研究约定，不调参；BUF也使用相同缓冲，只缺新持续/旧弱化约束。',
 'execution':'复用已修复PVR换仓v2双腿执行：正常买卖优先，T收盘冻结对手/预算/支持/股数；次可执行开盘先卖后买，预检双方、T+1、旧股全卖、现金/整手/新股保护。卖最多2市场日，买最多卖成日及次日，正常买先接纳则撤旧配对。不要求后续重复新买点。日线同开盘加1秒仅顺序代理，不声称分钟成交。',
 'unchanged':'原I/E0-NR1、RS、6股3行业2股、15%NAV/90%新增投入、ACT20_BREAK暂停恢复、原费用滑点权息及普通日有效均保持；不采用上一轮新入口、PVR评分、行业解限或新仓位。',
 'paths':'S0九模式×基础/双成本/延迟=27；S1和S2各九模式×基础/延迟=18；共63完整路径，其中原ACT三起点三seed共21对照，BUF/COR各21；额外旧原ACT技术身份在S0 ACT0三情景核对。',
 'primary_evaluation':{'poor_paths':'每个起点按ACT基础期末NAV选最低seed，平手seed较小者；预先固定这一选法，策略不见未来标签。3条较差路径配对收益差均值至少+5百分点，至少2/3改善，且其最大回撤均值不增加。不是与ACT最高298%比较。','dispersion':'同一起点三seed期末log(NAV/100万)总体标准差；3起点标准差等权均值至少下降20%，且至少2起点下降。ACT标准差零的起点不当改善证据。','economic_guards':'9基础路径配对期末NAV比值中位数>=0.90；尾部净贡献总和>=配对ACT的80%；平均资金暴露比>=80%，不得把低暴露当纠正能力。尾部是已闭合净收益>=30%周期，非止盈；各账户不可相加称组合收益，尾部总和仅等权情景汇总。','stress':'delay1相同9对的较差路径选择保持基础ACT确定，不重选；差路径平均收益改善须仍>=0，配对NAV比值中位数>=0.90；S0双成本报告全3seed，不能挑最好情景。','verdict':'上述核心标准全部满足只记为候选有研究支持，仍非样本外或自动采用；部分满足则展示取舍/证据不足。阈值为本轮研究判据，非用户永久收益承诺。'},
 'secondary':'不同初始组合的持仓Jaccard距离在第5/21/63/126/252观察的变化（空空不视为成功收敛，另报非空样本）；候选首次容量拒绝至首次持有的时间及未接纳比例；固定每笔换仓后21/63观察新旧净价格推进四象限（不作账户利润，未知/缺数据单列）；实际换仓周期赢家/普通/全部负收益损失；原ACT各路径尾部窗口持有股票日和新机制自身尾部贡献并列；共同2025年起区间归一收益与完整持有区间分开。',
 'stop':'先原图/机制检查/短段核账再冻结。一次63路径，无收益后寻参；只修实现违约并保留失败。没有达标也完成裁决，不启动第二轮、不修改交易台。'})
 snap=Path(read(PRIOR/'input.json')['snapshot']['path']);ids=pd.read_csv(P.C.DESIGN/'proposed-pool.csv').symbol.tolist();(O/'signals').mkdir(exist_ok=True);records=[];pre=0
 for sid in ids:
  f=pd.read_parquet(snap/'signals'/f'{sid}.parquet');g=pd.read_parquet(snap/'facts'/f'{sid}.parquet');assert set(f.loc['2024':].amount_unit.dropna())=={'CNY'};z=evidence(f,g);z.to_parquet(O/'signals'/f'{sid}.parquet')
  for cut in ['2024-12-31','2026-06-30']:
   pd.testing.assert_frame_equal(evidence(f.loc[:cut],g.loc[:cut]),z.loc[:cut],check_exact=True);pre+=1
  records.append(dict(symbol=sid,signal_sha=sha(snap/'signals'/f'{sid}.parquet'),facts_sha=sha(snap/'facts'/f'{sid}.parquet'),new_days=int(z.loc['2024':].new_ok.sum()),weak_days=int(z.loc['2024':].weak.sum())))
 save(O/'input.json',{'snapshot':str(snap),'prior_input_sha256':sha(PRIOR/'input.json'),'roster_sha256':sha(P.C.DESIGN/'proposed-pool.csv'),'records':records});save(O/'signal-validation.json',{'passed':True,'physical_prefixes':pre});pd.DataFrame(records).to_csv(O/'coverage.csv',index=False)
 graphs(snap)

def graphs(snap):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams['font.sans-serif']=['Arial Unicode MS'];plt.rcParams['axes.unicode_minus']=False
 cases=[('603186.SH','2026-03-01','2026-06-01'),('300570.SZ','2025-06-01','2025-08-31'),('688498.SH','2025-06-01','2025-11-28'),('688041.SH','2026-06-01','2026-10-27'),('002439.SZ','2024-01-01','2024-06-30'),('300502.SZ','2025-04-01','2025-10-31')]
 for page in range(2):
  fig,ax=plt.subplots(3,3,figsize=(17,10),sharex='col',gridspec_kw={'height_ratios':[3,1,1]})
  for j,(sid,start,end) in enumerate(cases[page*3:page*3+3]):
   f=pd.read_parquet(snap/'signals'/f'{sid}.parquet').loc[start:end];z=pd.read_parquet(O/'signals'/f'{sid}.parquet').reindex(f.index)
   ax[0,j].plot(f.index,f.close,color='#333',lw=1,label='收盘');ax[0,j].fill_between(f.index,f.low,f.high,color='#999',alpha=.2);ax[0,j].plot(z.index,z.ema21,color='#b88b35',lw=1,label='EMA21');ax[0,j].scatter(z.index[z.weak],f.close[z.weak],s=12,c='#b93333',label='自身弱化');ax[0,j].set_title(sid);ax[0,j].legend(fontsize=8);ax[1,j].bar(f.index,f.amount/1e8,color='#8096aa');ax[1,j].set_ylabel('金额/亿元');ax[2,j].plot(z.index,z.up_amount10,label='10日上涨日金额比例');ax[2,j].scatter(z.index[z.new_ok],z.loc[z.new_ok,'up_amount10'],s=8,c='#2468a1');ax[2,j].axhline(.6,color='#777',ls='--',lw=.5);ax[2,j].axhline(.5,color='#777',ls=':',lw=.5);ax[2,j].tick_params(axis='x',rotation=20)
  fig.suptitle('组合纠正图检：量价自身弱化与新机会持续证据；非实际换仓');fig.tight_layout();fig.savefig(O/f'graph-{page+1}.png',dpi=115);plt.close(fig)
if __name__=='__main__':initialize()
