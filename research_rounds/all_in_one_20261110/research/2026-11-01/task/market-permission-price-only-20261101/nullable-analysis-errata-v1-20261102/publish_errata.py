"""Publish replacement analysis reports and exact original-file migration map."""
from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent;B=O.parent;W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
S=B/'g-s-static-capital-competition-v1';C=W/'g-s-C-industry-first-projection-v1-20261102';A=W/'g-s-B-C-native-advance-attribution-readonly-20261102'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def save(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def text(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(x)
def main():
 summary=read(O/'CORRECTED_MARKET_SUMMARY.json');sources={};mapping=[]
 def original(p):sources[str(p)]=sha(p);return Path(p).read_text()
 root=original(S/'REPORT.txt').splitlines()
 for j,line in enumerate(root):
  if line.startswith('4/30原规范CP1'):
   root[j]='4/30原规范CP1共129张，纠正后G或成熟S扩张域14只：能源金属6、电子化学品4、元件2、电池2。严格半导体126固定身份中19只当日fresh且股票Q通过，行业ACTIVE/permit但尚无启动后推进，仍未成熟，未进入扩张域；不等于无信号或不能小试。化学品4只在纠正后B排名1、4、7、12；原B 1、4、5、7只是缺少能源金属6只的旧域排序。未改变S0→S1规则。'
  elif line.startswith('5/7原规范CP1'):
   root[j]='5/7原规范CP1共218张，纠正后扩张域62只。严格半导体仍21只，首只安路科技B6，前10有3只、前20改为5只；电子化学品9只，前20有3只。前5仍为共达电声、唯特偶、鼎龙股份、恒铭达、信维通信。新增力源信息（其他电子）PVR81.56411542802958，B19。原域61只及B前20半导体6只的完整性结论撤回。'
 notice='2026-11-02隔离分析勘误版。只修2026市场读取/列表，不改以下Jan6/Jul3静态事实、金融资源或后视镜结果。旧稿保留；相关2026原表由本包static/替代。根因是旧分析is None未识NaN，不是账户bug。\n\n'
 text('static/REPORT.txt',notice+'\n'.join(root)+'\n')
 ct=original(C/'REPORT.txt').splitlines()
 for j,line in enumerate(ct):
  if line.startswith('Apr30市场扩张列表'):
   ct[j]='Apr30完整市场扩张列表14股：能源金属6、电子化学品4、元件2、电池2。C前6依次天齐锂业、融捷股份、盛新锂能、腾远钴业、博迁新材、永兴材料；电子化学品为C7–10。严格半导体仍未成熟，19个原canonical_CP1_Q未进入S扩张，不叫无信号。旧8股与C前4化学品的完整性结论撤回。'
  elif line.startswith('May7市场扩张列表'):
   ct[j]='May7完整市场扩张列表62股：化学品9、元件14、通信设备6、电池1、其他电子1、严格半导体21、消费电子10。C前9仍全为化学品；力源信息B19/C31，严格半导体首只安路科技B6不变，C由31移至32。原B前20严格半导体由6只改为5只，前10仍3只。PVR真NA蘅东光仍B7/C24。行业优先不自动将严格半导体推80%。'
  elif line.startswith('能源金属May7行业H1第一'):
   ct[j]='能源金属May7行业H1第一但当日扩张列表仍0，只是当日无fresh机会；Apr30已有6只被旧分析NaN错误漏掉。其他电子May7实际有力源信息1只，不能再说无当日机会。全90行业与纠正后14/62股完整排序保留。'
 text('C-market-2026/REPORT.txt','2026-11-02隔离勘误版：仅2026市场列表段替换；Jan6/Jul3目标、C选择器和金融字段不变，未执行C/B求解器。\n\n'+'\n'.join(ct)+'\n')
 at=original(A/'REPORT.txt').splitlines()
 for j,line in enumerate(at):
  if line.startswith('其他电子：当天推进=True'):
   at[j]=line.replace('原扩张列表0股','纠正后扩张列表1股（力源信息B19/C31）')
  elif line.startswith('原61股中54股方向'):
   at[j]='纠正后的62股中55股方向伴随当天推进：电子化学品9、元件14、严格半导体21、消费电子10、其他电子1；另7股无当天推进：通信设备6、电池1。其他电子当天首次推进且有力源信息fresh机会。能源金属前一观察5/6推进、May7无推进且无fresh。推进与fresh分别核，不由排名或推进单独造订单。原61/54和其他电子无机会断言撤回。'
  elif line.startswith('May7市场context起点可核'):
   at[j]=line.replace('不预设54股都能买','不预设55股都能买')
 text('attribution/REPORT.txt','2026-11-02隔离勘误版：只替换May7市场方向段；Jan6/Jul3原28接收行/15行业政策组及原B/C目标均不变，不重跑金融。\n\n'+'\n'.join(at)+'\n')
 for key,root,sub in [('static',S,'static'),('C',C,'C-market-2026'),('attribution',A,'attribution')]:
  body=original(root/'AUDIT_ENTRY.txt')
  text(sub+'/AUDIT_ENTRY.txt','隔离勘误入口：本包REPORT.txt、ORIGINAL_FILE_REPLACEMENTS.json和VERIFICATION.json优先解释2026完整列表。旧正文/哈希仍作为旧稿保留；Jan6/Jul3金融/目标事实仍用原路径，不迁移或重算。2026市场替代视图在本包'+sub+'/。\n\n'+body)
 # Explicitly map every active generated view with a changed semantic value, plus their binding/completeness claims.
 def add(old,new,scope,corrected,status='REPLACE_ANALYSIS_VIEW'):
  sources[str(old)]=sha(old);mapping.append(dict(original=str(old),original_sha256=sha(old),replacement=str(O/new),scope=scope,corrected=corrected,status=status))
 for d in ['2026-04-30','2026-05-07']:
  desc='8→14，补能源金属6只' if d.endswith('04-30') else '61→62，补其他电子力源信息；Btop20半导体6→5'
  for name in ['ALL1709_DISPOSITIONS','ALL_SECTOR_FRESH_COMPETITION','SECTOR_OPPORTUNITY']:
   add(S/(d+'-'+name+'.json'),'static/'+d+'-'+name+'.json','2026市场部分',desc)
  for name in ['INDUSTRIES','STOCK_ORDER']:
   add(C/'market-2026'/(d+'-'+name+'.json'),'C-market-2026/'+d+'-'+name+'.json','原C市场排名定义不变',desc+'；C前6能源金属/化学品7–10' if d.endswith('04-30') else desc+'；力源B19/C31，首只半导体B6/C32，NA B7/C24')
 add(S/'SUMMARY.json','static/SUMMARY.json','仅extra_2026替代，account_cases/posthoc完全相等','Apr30 fresh14，May7 fresh62，top20与行业状态纠正')
 add(S/'analyze_static.py','rebuild_market_views.py','只替代sector_states→extra_cases分析流；不运行account_case','nullable_analysis.analysis_scope统一None/NaN；缺字段UNKNOWN；原脚本line242旧is None不再作为新分析入口','REPLACE_MARKET_ANALYSIS_ENTRY_ONLY')
 add(C/'prepare.py','rebuild_market_views.py','只替代market-2026输入与排序部分','原H1行业先序/B行业内顺序未变；输入使用完整14/62','REPLACE_MARKET_ANALYSIS_ENTRY_ONLY')
 add(A/'analyze.py','rebuild_market_views.py','只替代May7市场方向部分','May7全90行业，fresh62/advance55；Jan6/Jul3段不执行','REPLACE_MARKET_ANALYSIS_ENTRY_ONLY')
 add(C/'market-2026/COVERAGE.json','C-market-2026/COVERAGE.json','仅市场列表分母','8/61→14/62；容量/账户继续UNKNOWN')
 add(A/'MAY7_MARKET_DIRECTIONS.json','attribution/MAY7_MARKET_DIRECTIONS.json','May7既定可见行业视图','其他电子0→1；55/62；另有ALL90文件完整保留')
 for root,sub in [(S,'static'),(C,'C-market-2026'),(A,'attribution')]:
  for file in ['REPORT.txt','AUDIT_ENTRY.txt']:add(root/file,sub+'/'+file,'分析文字/入口','旧2026完整性断言被勘误段替代；其余段保留')
 for root,index in [(S,'PACKAGE_SHA256.json'),(C,'ARTIFACT_SHA256.json'),(A,'ARTIFACT_SHA256.json')]:
  add(root/index,'PACKAGE_SHA256.json','新市场视图绑定','旧字节哈希仍正确且原文件保留；新的14/62及归因绑定本包，不覆盖旧manifest','NEW_BINDING_NOT_OLD_HASH_INVALIDATION')
 add(C/'AUTHORIZATION_AND_FREEZE.json','C-market-2026/MARKET_BINDINGS.json','仅market_only_sources新视图','原C输入/目标/合同hash仍保留；新市场输入输出见本包manifest','MARKET_BINDING_SUPPLEMENT_ONLY')
 for root,file in [(S,'VERIFICATION.json'),(C,'COMPLETION.json'),(A,'COMPLETION.json')]:
  add(root/file,'VERIFICATION.json','原审计完整性范围勘误','旧8/61完整覆盖的断言撤回；原字节忠实复用、目标/金融审计不撤销；新14/62独立核验','COMPLETENESS_SCOPE_SUPPLEMENT_ONLY')
 # Old captured stdout is a historical log. It is retained, with corrected human-readable evidence here.
 for root,file in [(C,'PREPARE_STDOUT.txt'),(A,'STDOUT.txt')]:
  if (root/file).exists():add(root/file,'REPORT.txt','旧运行日志保留','旧8/61/54只是当时不完整分析日志，不重写；以本勘误完整数为准','ARCHIVE_LOG_WITH_ERRATA')
 save('ORIGINAL_FILE_REPLACEMENTS.json',mapping)
 bindings=dict(old_C_authorization_sha256=sha(C/'AUTHORIZATION_AND_FREEZE.json'),financial_C_artifact_manifest_unchanged=sha(C/'ARTIFACT_SHA256.json'),
  corrected_market_artifacts={str(p):sha(p) for p in sorted((O/'C-market-2026').glob('*.json'))},
  corrected_static_inputs={str(O/'static'/(d+'-ALL_SECTOR_FRESH_COMPETITION.json')):sha(O/'static'/(d+'-ALL_SECTOR_FRESH_COMPETITION.json')) for d in summary},
  financial_inputs_or_targets_recomputed=False,source_and_output_hashes='SOURCE_SHA256.json + PACKAGE_SHA256.json')
 save('C-market-2026/MARKET_BINDINGS.json',bindings);save('PUBLISH_SOURCE_SHA256.json',sources)
 save('SYNTHETIC_RESULTS.json',dict(passed=True,tests=16,command='python -B -m unittest -v test_nullable_analysis.py',exit_code=0,
  stdout_sha256=sha(O/'TEST_STDOUT.txt'),stderr_sha256=sha(O/'TEST_STDERR.txt'),no_strategy_or_financial_import=True))
 print('ERRATA_REPORTS_AND_MAPPING',len(mapping),'original-file entries')
if __name__=='__main__':main()
