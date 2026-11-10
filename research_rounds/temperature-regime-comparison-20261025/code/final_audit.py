"""Close evidence registry; no account execution."""
from common import *
from html.parser import HTMLParser
from urllib.parse import unquote,urlparse
import pandas as pd

def check_manifest(path,relative_root):
 d=read(path);bad=[]
 for raw,want in d['sha256'].items():
  p=Path(raw);p=p if p.is_absolute() else relative_root/p
  if not p.is_file() or sha(p)!=want:bad.append(str(p))
 assert not bad,(str(path),bad[:10])
 return dict(manifest=ref(path),files=len(d['sha256']),mismatches=0)

frozen=check_manifest(HERE/'freeze.json',ROOT)
old=check_manifest(OLD/'freeze.json',OLD)
registry=check_manifest(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json',ROOT)
assert read(HERE/'results/v0/audit.json')['passed']
assert read(HERE/'audit/account-prefixes.json')['passed']
assert read(HERE/'audit/preflight.json')['passed']
f=pd.read_csv(HERE/'results/v0/summary.csv');assert len(f)==972 and len(f[f.origin.eq('new')])==756
assert len(list((HERE/'results/v0/accounts').iterdir()))==756
assert (HERE/'results/attempt-00-control-csv-parser').is_dir()

class Links(HTMLParser):
 def __init__(self):super().__init__();self.targets=[]
 def handle_starttag(self,t,attrs):
  a=dict(attrs)
  for k in ['href','src']:
   if k in a:self.targets.append(a[k])
l=Links();l.feed((HERE/'report/index.html').read_text())
checked=[]
for x in l.targets:
 if x.startswith(('#','http:','https:','data:')):continue
 p=(HERE/'report'/unquote(urlparse(x).path)).resolve();assert p.is_file(),p;checked.append(str(p))
for x in ['data.json','conclusion.txt','key-curves.png','fixed-matrix.png','continuous-matrix.png']:
 assert (HERE/'report'/x).is_file()
qa=dict(recorded_at=now(),static_figures_visually_reviewed=['fixed-matrix.png','continuous-matrix.png','key-curves.png'],browser_rendered=True,dom_all_metrics_rows=972,dom_bull_C4_X6_trades=2,selected_trade_dates=['2025-02-11—2025-04-08','2025-05-09—2025-09-05'],screenshot=ref(HERE/'review/report-overview.png'),local_link_checks=len(checked),remote_publication=False)
write(HERE/'audit/report-qa.json',qa)

for file in [ROOT/'README.md',ROOT/'docs/HANDOFF.md',ROOT/'docs/NEXT_RESEARCH_TASKS.md']:
 s=file.read_text();lines=s.splitlines()
 hits=[i for i,x in enumerate(lines) if x.startswith('**2026-10-25最新用户补测授权：温度/拟合固定场景对照运行中。**')]
 assert len(hits)==1,file
 link='research_rounds/temperature-regime-comparison-20261025/README.md' if file.parent==ROOT else '../research_rounds/temperature-regime-comparison-20261025/README.md'
 lines[hits[0]]=f'**2026-10-25最新：温度/拟合固定场景补测已完成，不晋升。** [完整入口]({link})、[交互报告](http://127.0.0.1:8784/report/)。原11固定场景＋7连续检查（含原港股单资产代理），12温度入口/出口＋原温度T_ORIG/三层L3共756新账户，旧E0/R/F/HOLD的216只读复用。固定场景基础收益均值E0+14.72%、R+15.93%、原温度+6.59%、L3+8.72%，12温度最高+6.99%（均值非组合）；温度有黄金/恒科局部长处，但严格3→4漏跳级、降温退出后恢复不足。108旧控制、21输入前缀、14原型复现、432账户前缀及972账核验通过。原30登记/旧冻结不变；首个CSV解析技术失败保留，经济前修正，规则结果后修订0。本轮收口，不自动调参、换仓或全市场扩展。'
 file.write_text('\n'.join(lines)+'\n')

# Distinct post-result artifact manifest; never described as pre-economic freeze.
paths=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name not in ['complete.json','artifact-sha256.json']]
manifest={str(p.relative_to(HERE)):sha(p) for p in sorted(paths)}
write(HERE/'artifact-sha256.json',dict(recorded_at=now(),stage='post_result_delivery',sha256=manifest))
write(HERE/'complete.json',dict(recorded_at=now(),status='complete_no_promotion',economic_new_accounts=756,old_readonly_accounts=216,displayed=972,technical_E0_R_identity=108,technical_account_prefixes=432,physical_signal_prefix_sets=21,old_prototype_daily_replays=14,behavior_tests=10,accounting=read(HERE/'results/v0/audit.json'),new_frozen_sources=frozen,old_source_freeze=old,old_algorithm_registry=registry,artifact_manifest=ref(HERE/'artifact-sha256.json'),post_result_rules_changed=0,technical_failure_preserved=True,report_url='http://127.0.0.1:8784/report/',report_qa=ref(HERE/'audit/report-qa.json'),scope_closed=True))
print(json.dumps(dict(status='complete',new_frozen=frozen['files'],old_frozen=old['files'],registered=registry['files'],artifact_files=len(manifest),links=len(checked)),ensure_ascii=False))
