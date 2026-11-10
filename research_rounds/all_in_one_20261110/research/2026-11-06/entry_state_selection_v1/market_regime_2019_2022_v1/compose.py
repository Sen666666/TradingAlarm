from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
O=Path(__file__).parent
T=pd.read_csv(O/'INDUSTRY_WITH_MEMBER_BREADTH.csv');ST=pd.read_csv(O/'STATIC_1709_STOCK_PHASES.csv');C=pd.read_csv(O/'INDUSTRY_DAILY_CLOSE.csv',index_col=0,parse_dates=True);N=pd.read_csv(O/'INDUSTRY_SOURCE_QUALITY.csv').set_index('symbol')
major=['半导体','消费电子','元件','软件开发','通信设备','文化传媒','白酒','化学制药','中药','生物制品','医疗器械','医疗服务','光伏设备','风电设备','电池','汽车整车','能源金属','煤炭开采加工','钢铁','银行','证券','房地产','养殖业','旅游及酒店']
core={
'P01':['养殖业','白酒','证券','光伏设备','软件开发','半导体','消费电子','汽车整车'],
'P02':[],
'P03':['半导体','消费电子','元件','能源金属'],
'P04':[],
'P05':['白酒','医疗器械','生物制品','医疗服务','能源金属','光伏设备','电池'],
'P06':['白酒','能源金属','光伏设备','风电设备','电池','汽车整车','医疗服务'],
'P07':[],
'P08':['能源金属','光伏设备','电池','煤炭开采加工','钢铁','半导体'],
'P09':[],
'P10':[],
'P11':['光伏设备','风电设备','电池','汽车整车','能源金属','消费电子','半导体','通信设备'],
'P12':[],
'P13':[],
'C01':['半导体','消费电子','元件','软件开发','能源金属'],
'C02':['白酒','医疗服务','能源金属','光伏设备','风电设备','电池','汽车整车']}
secondary={
'P01':[x for x in major if x not in core['P01']],
'P02':[],
'P03':['软件开发','通信设备','医疗器械','医疗服务','光伏设备','电池','证券','文化传媒'],
'P04':['医疗器械','生物制品','半导体','软件开发','通信设备','元件'],
'P05':[x for x in major if x not in core['P05']],
'P06':[],
'P07':['钢铁','煤炭开采加工'],
'P08':['风电设备','汽车整车','医疗服务','白酒','中药','通信设备'],
'P09':['风电设备','中药','文化传媒'],
'P10':['煤炭开采加工'],
'P11':[x for x in major if x not in core['P11'] and x not in ['银行','房地产']],
'P12':['中药','软件开发','医疗器械'],
'P13':['旅游及酒店','白酒','房地产','文化传媒'],
'C01':['医疗器械','医疗服务','化学制药','生物制品','光伏设备','电池','通信设备'],
'C02':['医疗器械','生物制品','半导体']}
notes={'P02':'大部分春季涨幅回吐，个股反例仍可能存在','P04':'整段下跌掩盖2/3至2/25科技急涨，必须另看C03，不能一刀切','P07':'消费抱团下跌同时多数行业上涨，不是全市场统一方向','P09':'轮动与前段趋势结束时钟不同；不要求吃满每次反弹','P10':'煤炭相对强，但不能把行业抗跌视为可实现盈利','P12':'后半段医药信创启动，请另看C05，整段端点会掩盖','P13':'消费短波段有实质涨幅，优先级需与用户对齐，不自动强制覆盖'}
V=T[T.industry.isin(major)].copy()
V['subjective_priority']=[('优先覆盖的主线肥尾候选' if r.industry in core[r.period] else '次级或短波段，可讨论容忍错过' if r.industry in secondary[r.period] else '本段非主要肥尾目标') for r in V.itertuples()]
V['interpretation']=V.period.map(notes).fillna('事后主观标签，不是当时入场资格，不由涨幅阈值机械生成')
V.to_csv(O/'MAJOR_24_INDUSTRY_ALIGNMENT.csv',index=False)
V.pivot(index='industry',columns='period',values='subjective_priority').to_csv(O/'MAJOR_24_QUALITATIVE_MATRIX.csv')
# Extra known historical theme windows, explicit hindsight illustrations, not optimized tests.
extra=[('C03','疫情内科技急涨','2020-02-03','2020-02-25'),('C04','2022煤炭跨弱市阶段','2021-12-31','2022-09-13'),('C05','2022秋季医药信创','2022-09-30','2022-11-21')]
E=[]
for pid,label,b,e in extra:
 w=C.loc[b:e]
 for sid in C:
  s=w[sid];dd=s/s.cummax()-1;E.append(dict(period=pid,label=label,start=b,end=e,sector=sid,industry=N.loc[sid,'name'],ret=s.iloc[-1]/s.iloc[0]-1,MDD=dd.min(),max_from_start=s.max()/s.iloc[0]-1,peak_day=s.idxmax(),sessions=len(s),known_closes=s.notna().sum()))
pd.DataFrame(E).to_csv(O/'OVERLAPPING_THEME_WINDOWS.csv',index=False)
pairs=[('P01','002714.SZ'),('P01','300059.SZ'),('P01','601012.SH'),('C01','603986.SH'),('C01','300661.SZ'),('C01','603501.SH'),('C01','002475.SZ'),('C01','002463.SZ'),('C02','300274.SZ'),('C02','601012.SH'),('C02','300750.SZ'),('C02','002594.SZ'),('C02','600519.SH'),('C02','300015.SZ'),('P08','002466.SZ'),('P08','002460.SZ'),('P08','601012.SH'),('P08','300750.SZ'),('P08','600188.SH'),('P08','000422.SZ'),('P11','600732.SH'),('P11','300274.SZ'),('P11','002594.SZ'),('P11','300750.SZ'),('P13','600519.SH'),('P13','600754.SH')]
mask=pd.Series(False,index=ST.index)
for p,s in pairs:mask|=ST.period.eq(p)&ST.sid.eq(s)
examples=ST[mask].copy();examples['warning']='Ex-post named illustration from current survivor pool and current name/industry; not a predicted winner, portfolio return, or verified executable fill. MDD uses observed closes.';examples.to_csv(O/'NAMED_26_STOCK_ILLUSTRATIONS.csv',index=False)
print('composition complete',len(V),len(E),len(examples))
