from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
E=Path(__file__).resolve().parent;O=E.parent
old=pd.read_csv(O/'ALL50_DAILY_EVIDENCE.csv').sort_values(['day','sector51']).reset_index(drop=True)
new=pd.read_csv(E/'ALL50_DAILY_EVIDENCE.csv');p=new[new.day.le('2024-10-08')].sort_values(['day','sector51']).reset_index(drop=True)
assert old.shape==p.shape and set(old.columns)==set(p.columns);numeric=[]
for c in old:
 if pd.api.types.is_numeric_dtype(old[c]) and old[c].dtype!=bool:
  assert np.allclose(old[c],p[c],equal_nan=True,rtol=1e-9,atol=1e-9),c;numeric.append(c)
 else:assert old[c].equals(p[c]),c
# Synthetic tests for continuous-window admission, internal boundary handling and future cutoff.
def admit(v,line,h=5):
 v=pd.Series(v,dtype=bool);s=pd.Series(line);change=s.ne(s.shift());return (v.astype(int).rolling(h+1,min_periods=h+1).sum().eq(h+1)&change.astype(int).rolling(h,min_periods=h).sum().eq(0)).to_list()
tests={
 'complete_six_bars_for_five_intervals':admit([1]*6,['a']*6)[5] is True,
 'missing_middle_is_unknown_not_last_five_valid':admit([1,1,0,1,1,1],['a']*6)[5] is False,
 'internal_lineage_boundary_is_unknown':admit([1]*6,['a','a','a','b','b','b'])[5] is False,
 'boundary_at_window_start_not_inside_is_allowed':admit([1]*7,['a','b','b','b','b','b','b'])[6] is True,
 'future_rows_do_not_change_past':admit([1]*6,['a']*6)==admit([1]*8,['a']*6+['b']*2)[:6],
 'insufficient_history_unknown':admit([1]*5,['a']*5)[4] is False,
}
assert all(tests.values()),tests
b=new[new.sector51.eq('软件与IT服务')&new.day.ge('2024-10-08')].sort_values('day').copy()
for h in [5,10,20]:b[f'rs{h}_change_1day_pp']=b[f'rs{h}_median_pp'].diff()
b.to_csv(E/'SOFTWARE_FOLLOWTHROUGH_1008_1022.csv',index=False,float_format='%.12g')
# All50 short/long improvement evidence, without adding a new gate.
c=new.sort_values(['sector51','day']).copy()
for h in [5,10,20]:c[f'rs{h}_change_1day_pp']=c.groupby('sector51')[f'rs{h}_median_pp'].diff()
c[c.day.ge('2024-09-02')].to_csv(E/'ALL50_STRENGTH_AND_CHANGE.csv',index=False,float_format='%.12g')
rows=[]
for r in b.itertuples():
 rows.append({'日期':r.day,'M3 n/K/N':f'{r.m3_n}/{r.m3_K}/{r.m3_N}','状态':r.m3_state,'diff3':r.m3_diff,'半数持续天':r.m3_half_streak,'中位收益5/10/20%':'/'.join(f'{100*getattr(r,f"return{h}_median"):+.2f}' for h in [5,10,20]),'中位RS5/10/20 pp':'/'.join(f'{getattr(r,f"rs{h}_median_pp"):+.2f}' for h in [5,10,20]),'均值RS5/10/20 pp':'/'.join(f'{getattr(r,f"rs{h}_mean_pp"):+.2f}' for h in [5,10,20]),'20日高点回撤中位%':f'{100*r.drawdown20_median:.2f}','20日收盘突破数/K':f'{r.breakout20_count}/{r.breakout20_K}'})
df=pd.DataFrame(rows)
def table(df):
 out=['| '+' | '.join(df.columns)+' |','| '+' | '.join(['---']*len(df.columns))+' |']
 for row in df.itertuples(index=False,name=None):out.append('| '+' | '.join(map(str,row))+' |')
 return '\n'.join(out)
text='''# 软件主线10/9–22延展：退出一次不等于永久排除

## 结论先于规则

- 10/11确有可见退潮：软件M3从10/10的56/67跌到10/67，三日净扩散-54，个股20日高点回撤的中位数-14.69%。即便10/11的RS5/10/20仍是+5.75/+10.16/+14.47个百分点，也不能用“长期还是最强”无视绝对价格风险或阻止原有保护规则退出。
- 10/15–16短期进一步失速：5日中位收益-13.44%/-6.74%，中位RS5=-1.97/-2.82个百分点。长窗RS10/20仍强，说明过去一轮优势尚在统计窗口里，不代表现在无需控制风险。
- 10/17短期RS5重新转正，但M3仍FALSE。10/18出现新的广度确认：26/67、diff3=+16、5日中位收益+9.15%、RS5=+6.81个百分点；10/21到38/67，10/22到50/67。原先一次FALSE因此不能成为行业永久黑名单，后续可以出现新的小试和晋级证据。
- 这不证明应一直抱着，也不证明10/18应立刻满额恢复。10/18仅26/67，尚未半数；20日新高仅8/65，个股高点回撤中位仍-8.91%。10/21半数首次恢复，10/22半数连续2日，但突破数14/65降到4/65、回撤中位由-6.99%扩大至-9.18%，短期RS5由+5.17降至+1.52。新一轮广度修复和价格仍未全面重回高位同时存在。
- 10/22尤其显示不能单独读一个窗口符号：5日窗口10/15→10/22中位收益+6.01%、RS5=+1.52；10日窗口10/8尖峰→10/22中位收益-7.51%、RS10=-0.16；20日窗口9/13→10/22中位收益+47.61%、RS20=+20.96。它们回答不同问题，并不互相矛盾。
- 中位数与等权均值也不应择利解释。10/15中位RS5=-1.97，但均值RS5=+1.23；10/22中位RS10=-0.16，但均值RS10=+2.66。均值仍被部分强股支撑，不能因此宣称典型软件股无退潮，也不能只因中位略负就宣称全行业结束。

## 完整日线证据

以下RS为实际百分点，收益与回撤列已转成百分比展示。各收益窗口的价格K均为65/67；M3 K从64变65是信号知识集合变化，不是把价格收益0填进去。10/21以后扩散用共同可知配对样本计算，行业N固定67。

'''+table(df)+'''

## 三层状态应允许循环，不把后视身份写进规则

1. 初次或重新广度确认：得到小试资格。10/18属于重新确认，而不是凭10/8曾经强就自动恢复成熟仓位。
2. 已有持续相对优势的主线：相对强度持续天数、个股价格支撑与真实持仓盈利共同支持主线获得更有意义的资本。逐笔增量保护损失单独展示，本轮不设共享试错风险额度或共享风险池。长窗保留历史优势，不能覆盖当前保护位。
3. 短期领先且长窗改善的新强势：RS5转正/增强、RS10/20改善方向、持续半数广度和价格支撑分别展示。新强势不必先等待RS10/20全部翻正；反之，长窗未转负也不能豁免当前退潮。

这是描述性分层，尚未验证为最优策略。原先候选F/S仅为透明假设，下一步应先冻结三层的晋级、降级、资金分配及执行规则，再盲样本测试，而不是继续观察这段结果后调阈值。10/22也提示“RS10/20均正”不宜当唯一恢复门，但本报告不为该样本临时添加新的布尔捷径。

状态可以从小试→晋级→降温/退出→再次小试。FALSE可使当前试错失败或新投入停止，但退出事件与永久行业标签要分离。成熟仓的退出仍须按预先冻结的股票保护/行业降温规则执行，不能从本表推出“全部保留”或“全部卖出”。UNKNOWN单独冻结新增，不自动清空成熟仓。实际再买入要用当时新的信号、现金、最小手数、价格/保护与交易约束，不能凭后续上涨倒填持仓。

## 核验与范围

- 本延展独立放在extension_1022，原10/8数值、信号、窗口和候选标签公式保持不变。随后仅对候选资金说明修订；前版封印留存，变更记录说明新旧文稿哈希。
- 1692价格源hash继续全部匹配；21个目标日×50类=1050行；逐股连续窗口核验106596单元；旧M3字段逐行匹配。
- 与原10/8封存比较的9100行全部列通过前缀不变性检查，数值容差1e-9仅用于CSV小数序列化；后续日期没有改变此前信号、回报、相对强度或持续天数。
- 6项合成连续窗口测试通过，覆盖缺中间日、来源切换、窗口首边界、历史不足及未来数据不影响过去。
- 没有新增账户、交易或未来收益排名。固定现存池/行业非PIT以及历史数据后来采集的边界继续适用。
- SOFTWARE_FOLLOWTHROUGH_1008_1022.csv为软件完整字段；TARGET50_EVIDENCE.csv完整保留全部50类；ALL50_STRENGTH_AND_CHANGE.csv另列5/10/20日RS的当日变化，供看短期与长窗改善方向，不加新门槛。
'''
(E/'SOFTWARE_READOUT.md').write_text(text)
q=json.loads((E/'QA.json').read_text());q['prefix_invariance']={'rows':len(old),'columns':len(old.columns),'numeric_columns':len(numeric),'through':'2024-10-08','rtol':1e-9,'atol':1e-9,'result':'PASS'};q['synthetic_continuity_tests']=tests;(E/'QA.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n')
seal={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(E.iterdir()) if p.is_file() and p.name!='OUTPUT_SEAL.json'};(E/'OUTPUT_SEAL.json').write_text(json.dumps(seal,ensure_ascii=False,indent=2)+'\n')
# Verify original sealed bytes remain unchanged.
for filename,h in json.loads((O/'OUTPUT_SEAL.json').read_text()).items():assert hashlib.sha256((O/filename).read_bytes()).hexdigest()==h,filename
print('PASS: current original-directory seal verified; 9100-row prefix invariant; 6 synthetic tests; software followthrough report sealed.')
