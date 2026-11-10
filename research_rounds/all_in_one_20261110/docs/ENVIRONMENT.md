# 最新环境静态取证

M12恢复日志使用的uv环境当前元数据：CPython3.11.13，macOS aarch64，uv0.8.13。只读取pyvenv.cfg和包METADATA，未执行解释器、pip或研究代码。

- ast_serialize==0.4.0
- librt==0.11.0
- mypy==2.1.0
- mypy_extensions==1.1.0
- numpy==2.4.5
- pandas==3.0.3
- pandas-stubs==3.0.0.260204
- pathspec==1.1.1
- pyarrow==24.0.0
- python-dateutil==2.9.0.post0
- six==1.17.0
- typing_extensions==4.15.0

这与旧project/requirements-research.txt明显不同，两份分别保留。这是整理时安装环境的取证，不是原运行完整锁文件，也未验证重装可用。详见manifest/ENVIRONMENT_OBSERVATION.json。

平台依赖还包括部分本地PDF取证脚本的osascript/PDFKit、绘图脚本的STHeiti字体，以及curl/xattr。旧恢复脚本还记录repos/TradingAlarm的venv。辅助交付脚本可能读取用户配置中的认证，本项目不带认证，也不把它们作为自动入口。
