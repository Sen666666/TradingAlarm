from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np
from model import compute
O=Path(__file__).resolve().parents[1];ROOT=O.parents[1];PRIOR=ROOT/'research_rounds/pvr-act-comparison-20261027';SNAP=Path(json.loads((PRIOR/'input.json').read_text())['snapshot']['path'])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):
 if Path(p).exists():
  assert json.loads(Path(p).read_text())==x;return
 with Path(p).open('x') as f:json.dump(x,f,ensure_ascii=False,indent=2)
if __name__=='__main__':
 save(O/'raw-review.json',{'reviewed':True,'windows':9,'before_model_account':True,'observations':['源杰/新易盛上行途中平台后推进，成交额随价格阶段扩大；不宜要求每次2倍巨量。','华正/中际2026年中高位后走低，局部反弹不等于恢复主趋势；需要既有结构背景但E0滞后仍可能错认。','启明星辰/宝信2024下降中也有小平台反弹，单纯突破几根K线不能证明趋势。','德明利长整理后跳空突破，无法保证局部止损价格成交；日线只能次日开盘代理。'],'selection':'复用已研究赢家及下降反例，非盲测，不按结果替换窗口'})
 save(O/'protocol.json',{'name':'TRE-1 趋势内再入场','versions':['ACT','PB','BOX','BOTH'],'scenarios':['base','cost2','delay1'],'scope':'同407科技股11行业，2024-01-02至2026-10-27，100万元ACTIVE研究账户；现存池快照偏差保留',
 'unchanged':'原I买点与其持有不变；原RS个股/行业排序、行业准入、6股3行业每行业2股、15%NAV初仓90%新增投入、无换仓无加仓、ACT20_BREAK风险/恢复、费用/权益/整手/T+1/次日开盘日有效及延迟均不变。',
 'background':'新增入口当日E0有效、G1准备完成且grade>=2，最近10个价格观察及当日E0均有效；有效同源价格/真实CNY金额，至少22连续有效观察。',
 'scale':'ATR20=此前20真实波幅算术均值，TR=max(H-L,abs(H-Cprev),abs(L-Cprev))；金额参考=此前21观察金额中位数，均不包含当日。',
 'amount':'共同确认：当日收涨且金额>=此前21中位额；或最近3观察净上涨>=ATR20，且收涨日金额/最近3观察总金额>=60%。并非资金净流入。',
 'PB':'此前20观察最高收盘的最近位置p，距今3至15观察；p后至昨日最低价比p收盘低至少1ATR；今日收盘突破此前3观察最高价。局部保护=max(E0保护,p后至昨日最低价)。',
 'BOX':'此前10观察高低区间<=4ATR；最后与第一个收盘差绝对值<=1ATR；至少3个收盘下跌日；今日收盘突破此前10观察最高价。保护=max(E0保护,该10观察最低价)。',
 'risk_distance':'仅新增入口要求0<当日收盘-保护<=3ATR；次日原开盘保护检查，未额外限制向上跳空，仍原15%预算，风险不是固定R保证。',
 'dedup':'同版本下一次局部结构anchor必须晚于上一次新事件日；PB/BOX各自单流，BOTH共同去重且同日PB优先。未成交也消耗事件，不延长旧订单。',
 'original_priority':'若与原I事件同日，保留原入口和原保护；新增入口仅在原I无事件时接入；现有持仓不加仓、不因新事件改变原持仓保护。',
 'local_exit':'新增入口成交后冻结局部保护；仅收盘<=有效保护时次可执行开盘卖，不模拟日内触价成交；E0原结构退出与账户风险退出仍生效。',
 'handoff':'新增持仓成交后，E0保护相对信号日E0保护严格提高且>=局部保护、E0仍有效且收盘高于有效保护，才转趋势持有。交接前后有效保护均不得下调，取既有保护和有效E0保护最大值；无固定止盈/保本/时间卖出。',
 'stop':'3新增机制各3情景=9经济路径+3完整原ACT控制；先9原图/标注/技术短段再冻结；不扫参数、不按结果调参。分开统计新增入口与原入口的成本后周期贡献，同时比较完整账户变化；不能把新增交易利润视为可直接叠加。'})
 if not (O/'execution-rules-v2.json').exists():(O/'execution-rules-v2.json').symlink_to((PRIOR/'execution-rules-v2.json').resolve())
 ids=pd.read_csv(ROOT/'research_rounds/tech-finite-compound-20261026/../tech-pool-design-20261026/proposed-pool.csv').symbol.tolist() if False else [r['symbol'] for r in __import__('csv').DictReader((ROOT/'research_rounds/tech-finite-compound-20261026/code/common.py').open())] if False else None
 sys.path.insert(0,str(PRIOR/'code'));import experiment as P
 ids=pd.read_csv(P.C.DESIGN/'proposed-pool.csv').symbol.tolist();coverage=[];prefix=0;hashes={}
 for v in ['PB','BOX','BOTH']:(O/v/'signals').mkdir(parents=True,exist_ok=True)
 for num,sid in enumerate(ids):
  f=pd.read_parquet(SNAP/'signals'/f'{sid}.parquet');g=pd.read_parquet(SNAP/'facts'/f'{sid}.parquet');assert set(f.loc['2024':].amount_unit.dropna())=={'CNY'}
  hashes[sid]={'signal':sha(SNAP/'signals'/f'{sid}.parquet'),'fact':sha(SNAP/'facts'/f'{sid}.parquet')}
  for v in ['PB','BOX','BOTH']:
   z=compute(f,g,v);z.to_parquet(O/v/'signals'/f'{sid}.parquet')
   for cut in ['2025-12-31','2026-06-30']:
    small=compute(f.loc[:cut],g.loc[:cut],v);pd.testing.assert_frame_equal(small,z.loc[:cut],check_exact=True);prefix+=1
   q=z.loc['2024':];coverage.append(dict(version=v,symbol=sid,events=int(q.event.sum()),additional=int((q.event&~g.i_buy.reindex(q.index)).sum())))
  if (num+1)%50==0:print('prepared',num+1,flush=True)
 pd.DataFrame(coverage).to_csv(O/'coverage.csv',index=False);save(O/'input.json',{'snapshot':str(SNAP),'prior':str(PRIOR),'source_hashes':hashes,'roster_sha256':sha(P.C.DESIGN/'proposed-pool.csv')});save(O/'signal-checks.json',{'passed':True,'physical_prefixes':prefix})
