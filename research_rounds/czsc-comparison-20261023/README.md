# CZSC 本地对照查看

CZSC 1.0.2 已在独立环境实际运行，最终展示为 outputs/v2。复用了江苏银行、古越龙山、重庆燃气、腾讯的既有行情；现有冻结算法未改，未下载新行情、未运行账户。

- [本机报告](http://127.0.0.1:8767/) / [离线页面](index.html)：股票切换、同轴对照、原生图及逐日状态。
- [具体结论](REPORT.md)、[事前范围](PROTOCOL.md)、[原始量价先看](RAW_REVIEW.md)、[展示补充](DISPLAY_AMENDMENT.md)。
- [数值与前缀核查](outputs/v2/verification.json)、[输入冻结](outputs/v2/input-freeze.json)、[运行冻结](outputs/v2/run-freeze.json)。
- 逐日 CSV、笔增删日志和几何结构均在 outputs/v2/data；旧尝试保留于 outputs/v1。

## 再次打开

已启动仅监听本机 127.0.0.1 的静态服务。服务退出后，可在仓库根运行：

    python3 research_rounds/czsc-comparison-20261023/serve.py --port 8767

再打开 http://127.0.0.1:8767/ 。也可直接用浏览器打开本目录 index.html，页面与子图无需在线库或行情。服务目录仅限本次对照报告。

## 环境与复现

环境为仓库根 .tools/czsc/.venv，Python 3.13.7；依赖见 requirements.lock.txt。脚本使用 PYTHONDONTWRITEBYTECODE=1，CZSC_HOME 和 Matplotlib 缓存位于项目工具目录。

prepare.py 校验输入及原算法哈希并先保存原始量价图；build.py 导入冻结 numeric/participation/data_utils，不调用账户或旧 runner。模型运行代码副本在 outputs/v2/code-at-run/build.py。之后仅增加双图同 y 范围和防覆盖检查；render_outputs.py 从保存输出重新绘图，未重算模型，另存收据。

不要覆盖旧结果。prepare.py 拒绝已有目录；build.py 拒绝已验证目录，复现须使用独立副本或新的输出目录与相应输入冻结。render_outputs.py 也拒绝重复创建修正前归档。

快照截止 2026-10-16，未冒充 22 日全池数据结项；信号与笔的语义见 REPORT.md。
