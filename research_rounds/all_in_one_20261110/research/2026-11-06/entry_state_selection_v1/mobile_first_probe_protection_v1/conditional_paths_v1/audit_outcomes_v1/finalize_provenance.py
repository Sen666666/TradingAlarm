from pathlib import Path
from decimal import Decimal as D
import json,hashlib,gzip
O=Path(__file__).resolve().parent;M=O.parent
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
a=read(M/'run/SOURCE_FREEZE.json');b=read(M/'FINAL_SOURCE_FREEZE_v3.json');out=read(M/'run/OUTPUT_HASHES.json')
assert set(a)<=set(b)
for p,h in b.items():assert sha(Path(p))==h
for p,h in out.items():assert sha(M/'run'/p)==h
core_fields=['case_id','arm','round','origin','opened','closed','buy_cost','sale_net','dividend','dividend_paid','fees','qty','net','status','return_on_buy_cost','cash_realized_net']
comparisons={}
for file in ['ROUNDS.json','FIRST_INTENTS.json','SEED.json']:
 r1=read(O/'result_01'/file);r2=read(O/'result_02'/file);assert len(r1)==len(r2)
 for x,y in zip(r1,r2):
  for key in core_fields:assert x.get(key)==y.get(key),(file,key,x.get(key),y.get(key))
 comparisons[file]=dict(rows=len(r1),economic_fields_unchanged=core_fields)
assert read(O/'result_01/SUMMARY.json')==read(O/'result_02/SUMMARY.json')
provenance=dict(passed=True,reviewed_sources=347,runtime_source_subset=342,review_only_extra_five={p:h for p,h in b.items()if p not in a},
 runtime_subset_hash_differences=0,run_output_hashes_reverified=36,all_original_economic_outputs_unchanged=True,
 result_01_to_02=dict(change='Audit-only: add actual fill endpoint adverse observations, layer-specific pending exit days, common-close wait intervals. No source/account rerun.',economic_comparisons=comparisons,summary_exact=True),
 execution_supplement=read(O/'execution_source_check.json'))
(O/'FINAL_PROVENANCE.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2)+'\n')
report=(O/'REPORT.md').read_text()
old='结论：本轮足以证明“空仓MOBILE首层按I持有”能在部分已知败例保住反弹，也证明它会扩大亏损、延长占资并吞掉部分右尾。它不是已经找到更好的入场公式。保留为机制研究假设有意义，但没有依据宣布成熟、进入35%目标验证，或直接推广为完整账户方案。'
new='主结论必须按种子完整0→0回合：只有新集能源由亏转赢。格力、烽火虽然首层转盈，加入实际ADD后仍亏；CP为5W/8L，I为5W/7L+1未闭，江丰两臂未入。没有证据说明完整种子交易胜率提高，更不能证明35%目标。首层I责任值得保留为机制研究假设，但它同时扩大亏损、延长占资并回吐部分右尾；当前不能直接推广为完整账户方案。'
assert old in report;report=report.replace(old,new)
report=report.replace('## 3. 计数而非外推胜率','## 3. 先看完整种子回合，再解释首层')
report=report.replace('- 固定14个种子：CP首层','- **主要评价单位，种子完整回合：CP 5W/8L/1未入；I 5W/7L/1未闭正/1未入。只新集由亏转赢。** 中国动力从控制已闭赢变成候选未闭正，不是新增一个已闭胜例。\n- 首层解释，固定14个种子：CP首层')
greeli='''### 格力电器：首层盈利不够覆盖反复追加损失
I首层+1742.39（买入含费13352.53），6次ADD合计亏2663.63，累计追加买入含费93302.59，完整种子回合亏921.23；控制完整种子回合亏462.72。I整轮累计买入含费106655.11，10→58个持仓收盘，成本日约20.15万→139.15万元×共同收盘日。
六笔新增在2024-01-17、2/27、3/04、3/08、3/28、4/02；ADD按CP分别在1/24、3/13、4/10退出，种子首层直到4/11按I退出。
每次新增前V>K都真实成立。1/17现库存V=13572.54、K=13352.53，只有220.02元纸面净盈仍允许买入含费13604.67元；3/28 V=15558.43、K=15392.18，缓冲166.25元仍允许买入含费15593.79元。这里是“盈利可追加”，没有“当前利润足以承保新增风险”的条件。新增本金不等于风险金额，本审计不据这些本金数字声称某笔新增名义风险超过缓冲；反例证明的是布尔门不保证整轮获利。

'''
report=report.replace('### 烽火通信：首层救回，整轮更亏',greeli+'### 烽火通信：首层救回，整轮更亏')
report=report.replace('13个首填的首层已闭退出均','两臂所有已闭种子首层退出均')
report=report.replace('- 输入冻结342项、run封存产物36项全部hash一致。','- 最终审前冻结347项、运行时实际导入冻结342项与run封存产物36项全部hash一致。运行时342是347的严格子集；多出的5项是CONTRACT.md、core_lifecycle_test.py、prefix_and_receipts.py、preflight.py、synthetic_callbacks.py，已在FINAL_PROVENANCE.json逐项复核。')
report=report.replace('### 烽火通信', '### 烽火通信',1)
report=report.replace('## 7. 文件与复现','## 7. 审计版本与文件')
report=report.replace('- FINAL_HASHES.json：本独审文件最终hash。','- REPORT_v2.md是主结论改为完整种子回合的最终文字版，补充格力追加明细。FINAL_PROVENANCE.json证明01→02仅审计极值/等待字段增加，228个完整/未闭回合、228个首原订单与28个种子记录的核心经济字段全部一致，SUMMARY完全相同；36个原经济产物重新核hash未变。\n- FINAL_HASHES_v2.json：本独审文件最终hash。')
(O/'REPORT_v2.md').write_text(report)
allfiles=[p for p in O.rglob('*')if p.is_file()and'__pycache__'not in str(p)and p.name!='FINAL_HASHES_v2.json']
(O/'FINAL_HASHES_v2.json').write_text(json.dumps({str(p.relative_to(O)):sha(p)for p in allfiles},ensure_ascii=False,indent=2)+'\n')
print('REPORT_v2',sha(O/'REPORT_v2.md'));print('PROVENANCE',sha(O/'FINAL_PROVENANCE.json'));print('FINAL_HASHES_v2',sha(O/'FINAL_HASHES_v2.json'));print('CASE_TABLE',sha(O/'THREE_LEVEL_CASES.csv'))

