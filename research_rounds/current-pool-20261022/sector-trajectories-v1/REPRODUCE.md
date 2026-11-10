# 最小复现与证据入口

这是行业技术诊断，不是股票生产入口。账户 0，算法修改 0。原输出不可覆盖；若只阅读结果，无需重算。

关键入口：`PROTOCOL.json` 固定范围、来源和冻结算法哈希；`input-manifest.json` 固定 101 条原料及段落；`prepared/manifest.json` 列出全部 404 个信号、事件、状态、记忆文件的哈希；`prefix-validation.json` 为 23 个精确前缀检查；`charts/manifest.json` 列出六图及事前选择理由。`negative-evidence.json` 保存有界在线补证的实际范围，复现阶段不联网。

`delivery-manifest.json` 提供顶层证据、六图、代码及上游的 SHA-256。`code-at-run/` 是本次脚本和依赖的证据快照，不应直接以其目录层级导入运行。桥和上游入口有固定相对路径，以下命令先核验原位置源码哈希，再运行原位置代码，输出写入全新目录。若源码已变化，断言失败后应恢复独立环境，不得删掉校验继续。

在 `/Users/bytedance/Documents/ChatGPT/money` 中执行以下命令才会重新生成技术轨迹；本交付未重复运行。需现有研究虚拟环境（NumPy、Pandas、PyArrow、Matplotlib），没有账户、下载、全股票状态生产步骤。

```sh
/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/.venv/bin/python - <<'PY'
from pathlib import Path
import hashlib, json, sys
root = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/current-pool-20261022')
old = root / 'sector-trajectories-v1'
delivery = json.loads((old / 'delivery-manifest.json').read_text())
for ref in delivery['code_sources']:
    path = Path(ref['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], path
sys.path.insert(0, str(root / 'code'))
import prepare_sector_trajectories as prepare
import review_sector_trajectories as review
out = root / 'sector-trajectories-reproduction-01'
out.mkdir(exist_ok=False)
prepare.OUT = out
prepare.main()
review.OUT = out
review.main()
PY
```

复现目录路径会进入 manifest，故顶层 JSON 的字节哈希不要求与原目录相等。应比较 101 条状态表的列值、汇总及 23 个前缀检查。原始数据各自哈希由桥验证。图形字节可能随字体/绘图库版本变化；原图字节哈希保存的是本次实际看过的图。仅字体缓存目录警告已保留在日志，未影响六张输出的实际渲染。
