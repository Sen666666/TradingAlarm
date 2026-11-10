"""Freeze one design after raw review, before any temperature output."""
from pathlib import Path
import json,datetime,hashlib
from temperature import PARAMS,LABELS
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    prior={
      'raw_reviewed':['raw/raw-01.png','raw/raw-02.png','raw/raw-03.png','raw/raw-04.png','raw/raw-05.png'],
      'gold':'2024春季及2025年持续抬升，横盘多次仍处高区；2026年先急涨后转低区。替代解释是高区整理；收盘破坏此前结构下沿撤销。不能要求卖在最高点。',
      'semi':'2023至2024年9月前多为下降中的反弹；2024年9月急速启动没有完整回抽；2026年4月至7月长推进后明显转低。需要同时容纳快速切换与失败重试。',
      'bank':'江苏银行2024至2025年有较慢但持续的抬升；2024年多次整理，不应因缺当天爆量永远无法升温。',
      'range_stocks':'古越龙山和重庆燃气2024年前段反复震荡、9月共同急涨；2026后段古越仍有短促急涨后下落。快速启动和随后失败在初期可能共享证据，不能事后删去。',
      'hk':'腾讯2025年上涨跨过多次整理；京东2024年9月强启动后转较低区域。其余18旧固定窗均保留，包括弱市美团、恒隆和科技ETF，已见历史身份不变。',
      'scope':'主观判断是开发假说，不是正确标签或未来赢家名单。所有前述图已先于温度输出查看。'}
    (HERE/'raw-review.json').write_text(json.dumps(prior,ensure_ascii=False,indent=2)+'\n')
    protocol=dict(frozen_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),version='temperature-v0',candidate_count=1,post_run_mechanism_revisions=0,
      question='Can accepted structure be separated from currently effective progress, reducing repeated weak-rebound participation without structurally blocking fast starts or long trends?',
      input_freeze_sha256=sha(HERE/'input-freeze.json'),raw_review_sha256=sha(HERE/'raw-review.json'),
      code_sha256=sha(HERE/'temperature.py'),parameters=PARAMS,labels=LABELS,
      levels={
       'unknown':'前64观察预热或资料缺失；不填为冷。源连续性分段独立预热。',
       '0':'无接受的上行结构，且短期回暖条件未通过。不是未来必跌。',
       '1':'无接受结构；5观察净涨/背景波动/sqrt(5)>=1，或收盘超过前5收盘最高，只有回暖。',
       '2':'收盘突破前20观察收盘最高，已记录上沿与此前20低点，但尚未通过量价接受；候选最多5观察。',
       '3':'突破被量价接受：当日量比>=1.5且收盘位置>=2/3；或5观察内至少3次收盘守住旧上沿、当前收盘不低于突破日、推进日平均相对量不弱于下跌日。结构有效但未达到4级，或高参与下跌尚未收复。',
       '4':'结构有效且无未收复量价冲突；20观察Z>=1、带方向ER>=0.25、收盘>20均价；或快速通道：前63收盘新高、5观察Z>=2、量比>=1.5、收盘位置>=2/3。快速通道不要求回抽或长期均价先上行。',
       '5':'满足4级，且63观察Z>=1、带方向ER>=0.20、收盘>63均价；长短两尺度同向。',
       '6':'满足5级，当日再创前63收盘新高、量比>=2、日对数涨幅/背景波动>=1、收盘位置>=2/3。新增成交伴随新增推进，次日无扩张即可回5。'},
      formulas={'sigma':'过去63个已完成单日对数收益RMS，排除当日；下限1e-8。',
       'Z_h':'log(Ct/Ct-h)/(sigma_t*sqrt(h))；仅比较尺度，不解释为统计置信概率。',
       'ER_h':'log(Ct/Ct-h)/sum(abs(single-day log returns))；零路径定义0，保留方向，不重复累积旧位移。',
       'q':'当日成交量/前21个正成交观察的中位数。跨证券不比较原始量单位。',
       'clv':'(close-low)/(high-low)，无价差时为0.5；只能描述收盘位置。'},
      transitions='逐日取满足的最高等级，允许跳级；3以上须有接受结构。结构创建时下沿=突破前20日最低，之后仅在新的接受突破时按相应20日低点上移；收盘<=下沿撤销。高参与下跌(q>=1.5、收盘较前日下降且低于20均价)留下前收盘否决记忆，量比普通也能在收盘>记忆前收盘时解除；待解除时温度封顶3，已有参与不因此退出。',
      participation_projection='固定4级为解释性观察入口：每个结构第一次达到>=4才生成参与事件，并延续至收盘触及该结构下沿；仅降温不重新开仓，破坏日不重入。与结构直接参与、每日热度跨越同时列示，拆清状态记忆和温度筛选贡献。无订单、资金、成本、净值或策略盈利结论。',
      overextended='log(close/MA20)/sigma>=3单列，不自动降级、止盈、拦截或缩紧保护线。',
      parameters_rationale='5约一周、20约一月、63约一季、21量基线沿用旧观察尺度；Z=1/2区分正常尺度与强脉冲，ER阈值要求净推进占路径一定份额，q=1.5/2区分活跃与强活跃。这些是一次冻结的工程假设，不是文献最优值，不扫参。七级各增加不同证据而非等宽分箱，若某级罕见或无行为差异如实报告。',
      controls=['原numeric+participation同输入不改','新结构即参与：剥离结构解析变化','新温度入口：剥离温度门槛变化','同模型去量：突破及守位取消量门、移除高参与冲突，其余不变'],
      evaluation='先全18固定窗和8主展示图检；参与次数、10观察内结构失败（不是亏损）、信号覆盖、固定窗口启动日期、温度来回跨越与结构延续分列。原固定窗口类别仅诊断，不回填成信号。相同前缀、量价单位、同价异量、既有算法逐行一致核查。',
      limits='无参数搜索；一个候选、运行后机制修订0次。实现错误可修复但旧输出原样归档。未见身份不能恢复；黄金为518880 ETF代理，不是用户截图的未知黄金合约。A行业指数技术观察、当前分类偏差保留。HK无本次已核同源板块，单股图不冒充两级选股。',
      references=['https://images.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Demystifying-Managed-Futures.pdf','https://ta-lib.org/functions/er.html','https://www.wyckoffanalytics.com/wyckoff-method/'],
      account_runs=0,market_downloads=0,old_algorithm_changes=0)
    with (HERE/'protocol.json').open('x') as f:json.dump(protocol,f,ensure_ascii=False,indent=2)
    print(json.dumps({'frozen_at':protocol['frozen_at'],'code_sha256':protocol['code_sha256'],'levels':len(LABELS)},ensure_ascii=False))
if __name__=='__main__':main()
