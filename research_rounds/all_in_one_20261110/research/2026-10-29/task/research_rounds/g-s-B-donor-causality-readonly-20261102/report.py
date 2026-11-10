from pathlib import Path
from decimal import Decimal as D
import sys,json,hashlib,csv
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent/'g-s-B-joint-target-v2-20261102';sys.path.insert(0,str(ROOT));import selector as B
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def pct(x):return f'{D(x)*100:.2f}%'
def money(x):return f'{D(x):,.2f}'
def main():
 summary=read(HERE/'results/SUMMARY.json');totals={};tables=[]
 aliases={'account_risk6':'账户risk6','cash_reserve10':'现金10%底线','account_capital90':'账户资本90','industry_target':'行业资本','sector_risk5':'行业risk5'}
 for k,data in summary.items():
  x=read(ROOT/'inputs'/(k+'.json'));s=x['snapshot'];r=read(ROOT/'results'/k/'B.json');ds=x['B_demands'];comp={c['sid']:c for c in x['evidence']['full_union']}
  final=[]
  for sale in r['donors']['rows']:
   z=next(z for z in s['lots'] if z['id']==sale['layer']);m=D(z['mark']);f=D(z['floor'])
   final.append(dict(sid=z['sid'],name=comp[z['sid']]['name'],rank=comp[z['sid']]['competition_rank'],layer=z['id'],quantity=sale['q'],mark=m,floor=f,distance=m-f,line_fraction=(m-f)/m,
      capital=sale['capital'],nominal_risk_released=sale['risk_release'],net=sale['net'],role=z['role'],pool=z['pool'],purpose=z['purpose'],not_a_protection_failure=True))
  save(HERE/'results'/(k+'-FINAL_DONOR_LAYERS.json'),final)
  with (HERE/'results'/(k+'-FINAL_DONOR_LAYERS.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(final[0]));w.writeheader();w.writerows(final)
  soldmark=sum((D(z['capital']) for z in final),D(0));soldrisk=sum((D(z['nominal_risk_released']) for z in final),D(0));net=sum((D(o['net']) for o in r['donors']['orders']),D(0))
  buygross=D(0);buyrisk=D(0);buycash=D(0);markgross=D(0);markrisk=D(0)
  for d in ds:
   q=r['Q'].get(d['sid'],0);p=D(d['mark'])*(D(1)+B.SLIP);buygross+=D(q)*p;buyrisk+=D(q)*(p-D(d['floor']));buycash+=B.J.buy_cost(d,q);markgross+=D(q)*D(d['mark']);markrisk+=D(q)*(D(d['mark'])-D(d['floor']))
  totals[k]=dict(sold_mark=soldmark,sold_nominal_risk=soldrisk,sold_risk_per_capital=soldrisk/soldmark,buy_gross=buygross,buy_reserved_risk=buyrisk,buy_risk_per_capital=buyrisk/buygross,new_mark_capital=markgross,new_risk_at_mark=markrisk,new_mark_line_fraction=markrisk/markgross,
    net_sell=net,buy_cash=buycash,cash_increase=net-buycash,start_available=s['available'],end_available=r['validation']['terminal']['available'],
    start_risk=sum((D(z['risk']) for z in s['rows']),D(0)),end_risk=r['validation']['terminal']['risk'])
  table=[k,'新需求/增量股数 | 新线距(入价) | 本步正新增供资旧层平均线距(mark) | 最后一单位供资的实际紧约束']
  for p in data['per_new_demand']:
   edge=p['last_increment_donor_one_step'];binding=[aliases.get(z,z) for z in edge.get('violations',[]) if z!='insufficient_original_donors']
   table.append(f"{p['name']} {p['q']} | {pct(p['new_line_fraction'])} | {pct(p['positive_donor_weighted_line_fraction'])} | {' + '.join(binding)}")
  t=totals[k]
  table+= [f"合计：卖原价市值{money(soldmark)}/释放名义risk{money(soldrisk)}，平均{pct(t['sold_risk_per_capital'])}；新买同mark口径{money(markgross)}/risk{money(markrisk)}，平均{pct(t['new_mark_line_fraction'])}；另按+5bp预留毛额{money(buygross)}/risk{money(buyrisk)}，平均{pct(t['buy_risk_per_capital'])}。",
    f"净卖款{money(net)}−买含费{money(buycash)}={money(net-buycash)}现金增加；从{money(s['available'])}到{money(r['validation']['terminal']['available'])}。",'']
  tables+=table
 save(HERE/'results/TOTAL_RISK_CASH_BRIDGE.json',totals)
 text='''冻结B不利行为的最小只读解释（不改代码/窗口/订单）

结论：大额减持主要由“尽量给前排股票原资本上界 + 新层相对较宽的实际floor风险 + 账户6%名义风险 + 弱者先供资”共同造成，不只是现金不够。不是所有新线都比旧线宽；现金/资本也在部分步骤真正成为边际限制。无法据此宣布这个政策合理。

下表最后一列来自：保持该步全部新量，撤回最后新增供资者一个原合法卖出单位，再用冻结JF2逐阶段联立核验。与“如果完全没有本步新D会违反哪些限额”分别保存，后者可能多约束共存，不冒称唯一原因。新线距=(原收盘价×1.0005−新层实际floor)/入价；旧线距=(当时mark−旧层实际floor)/mark。均同原因子坐标，不拿近线替旧core。
“旧平均”只对应本步正新增拟减持；期间回填的减量另列，不能把各步正新增再累计成实际卖出量。最终完整47个供资层原mark/floor/距离/数量/role/pool/名义risk在FINAL_DONOR_LAYERS，逐新需求关联在PER_NEW_DEMAND。

'''+ '\n'.join(tables)+'''
为什么现金反而增加
独审与本报告的同mark新线距为9.51%/7.36%；+5bp预留口径为9.56%/7.40%，两者不混用。最终完整D的20/27只逐股回填一个合法单位，均由account_risk6拦住；下表的逐新需求前缀是另一个时点，因此Jan6京北方/中原的边际现金/资本约束与最终回填结果不矛盾。
Jul3新五层平均risk/金额比卖旧层更高，且前三新层线距约10%。前两步“没有本步新增D”也会违反现金10%和资本90%，但最后减少一单位供资时只有账户risk6失败；后三步连初始缺口测试也仅risk6。因此为释放足够risk卖出的资本超过买入需款，剩余现金并不等于还可承担这些新层风险。
Jan6第一笔京北方有原持仓，但追加需现金，边际由现金/资本决定。中原传媒也是现金/资本边际。其余几步账户risk6决定最后供资量；羚锐/昆仑新层线距约12.91%/10.87%，常明显高于供资旧层。以岭/中原/康恩贝新线并不都更宽，不能笼统说每笔都是“新股风险更高”。
两日所选增量的边际检验都没有行业资本或行业risk5成为最后紧约束；多数前排新量已到独立单股资本/合法单位上界。末尾华盛/昆仑未到原上界，是当前供资规则下的账户风险与合法单位限制；这不证明任何供资集合下都不能更多。
供资按冻结联合PVR_SLOT1由弱到强、只取更后排合法mobile，同股FIFO/聚合费用一次；不比较未来收益，也不按risk效率排序。因此可能先用大量低risk旧市值换少量更宽line的新风险。cash+风险名义支出核对通过，并不能证明这种替换具有收益价值。

同股冲突
冻结B所有最终目标均无同一股票delta>0且D>0；现有mobile追加的四只没有在B中被先卖再买。Jul3博敏是原OPEN已按独立CP1义务实际卖完、CLOSE fresh后形成计划再入，原退出责任已灭，不是B先减又加。
但真实账户仍有原A退出，不能把共同比较视图当账户：Jan6创维数字原A待卖100股仍在，B却有追加4600目标；实际接线必须先按原规则处理/确认，原guard也会拦这种冲突。Jul3新五个目标没有同股旧待卖冲突，但保留北方等旧股的B目标也不能自动撤掉原A卖单。本轮未发买单或撤单。

局部不可减不等于全局最小
固定最终Q不变，仅试“一只额外捐资旧股增加一卖出步 + 一只既有捐资股减少减持”的有界组合，找到两项全资源约束通过的更少毛卖金额见证：
'''
 for k,data in summary.items():
  a=data['local_alternative']
  if a['found']:
   text+=f"{k}：额外卖{a['add_name']}({a['add_sid']}){a['extra_sell']}股、保留{a['restore_name']}({a['restore_sid']}){a['restored']}股；原价毛卖额少{money(a['less_sold_mark'])}元，预计费用{money(a['original_fee'])}→{money(a['alternative_fee'])}。局部联合核验{a['checks']}次，首个成功即停。\n"
  else:text+=f"{k}：有界检验{a['checks']}次未发现，不推出全局最小。\n"
 text+='''这证明原“每D少一单位失败”不能推出全局最小换手。本两真实快照的有界见证仅省87/170元，不能据此量化几十万元冗余；它们改用更靠前/风险密度不同的旧股，违反当前冻结弱者优先的选择次序。共享资源的预留/费用/填前检查通过；没有证明它能由原B供资决策前缀产生，也没有测试另一套新策略。不能因少卖就认定经济上更好，更没有计算收益。
独立审计另有四股合成反例：同样买NEW900股，当前弱者前缀卖14万元，另一个财务可行集合只卖5万元；原集合逐股少一单位却全由risk6拦住。这是选择次序的政策代价反例，不是本两真实快照少卖9万元的证明；证据原文及SHA保存在independent-evidence。
是否存在显著少卖的其他合法集合未知；未全面优化、未动更前旧赢家去强求大幅节省。大额换手目前主要能归于明示目标/风险/排序政策，而不是已识别的实现无谓减仓。先前Decimal尾差和冗余100股已在冻结结果前收口，不能将旧故障重复归为现结果；也不能由此断言实现或政策已达到全局最优。

支持机制：名义risk密度和前排资本上界造成大额腾挪及高现金；行业不是本两点的最后瓶颈。否定过强解释：全因缺现金、每笔新线都更远、局部不可减就全局最少卖。未知：长期付出旧赢家肥尾/新假突破的双重代价是否值得，是否有大幅更省资本的合规供资组合。本任务只交解释，不用回测代答，不修改下一轮政策。
输入与冻结代码/原B全部文件SHA前后相同，0金融事件。所有金额仍是固定收盘价+原5bp条件目标，不是真实订单/成交/未来收益。完整源与证据见VERIFICATION和results。B保留为激进反例，当前不送长回测；本只读任务完成即停，不做更大优化搜索或新的B实现。
'''
 (HERE/'REPORT.txt').write_text(text)
 save(HERE/'ARTIFACT_SHA256.json',{str(p.relative_to(HERE)):sha(p) for p in sorted(HERE.rglob('*')) if p.is_file() and p.name!='ARTIFACT_SHA256.json'})
 print(json.dumps(dict(completed=True,financial_events=0,totals=totals),default=str),flush=True)
if __name__=='__main__':main()
