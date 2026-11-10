# 2026-11-10 研究库精简回执

用户授权：保留后续研究必需的数据、算法、成功和失败结论，核对依赖后处理冗余，GitHub只上传精简代码与研究档案。

## 本地实施

- 只在独立归档内合并字节完全相同的历史数据副本；未删除任何唯一研究信息或文件访问路径。
- 1,766份冗余副本完整SHA256相同，重复负载15,278,200,802字节，原子替换为只读硬链接。
- 当前9,108项冻结输入及当前M12相关资料整组排除；源码和成功失败结论不参与此次硬链接合并。
- 原外置研究目录、活跃产品runtime、实际及模拟账户、旧Git历史未删改。
- 大量增长型pickle状态未证明可丢弃，保留；未因实验失败或文件大而盲删。

## 核验结果

- 当前输入9,108/9,108项SHA匹配，全部从归档内部读取。
- 原归档686,178条记录的路径/大小/既有SHA检查通过；其中17,036份既有SHA再次核对，内部255条链接无误。
- 全部被合并候选在操作前完整计算SHA；未将大小或分段指纹相同冒充完整内容相同。
- 独立化回退测试通过：复制后inode独立，改动副本不影响共享原件。
- 空闲磁盘变化不作为可归因节省量；APFS原本存在共享块。

## GitHub档案

活跃应用、原算法源码、合同、成功/失败/取舍结论保留为普通文件；较大的研究身份与结果元数据4,819份、原91,187,646字节，压缩为16,364,825字节，已实际逐成员解压并核SHA。原行情、大账簿、pickle、认证资料及账户不上传。

此次采用新的干净发布历史，不继承旧本地私有main。只申请公开仓库权限，不申请workflow、组织或私库权限；令牌仅在本次推送进程内使用。具体远端提交以GITHUB_PUSH_RESULT.json为准。

## 文件

- DEDUPLICATION.json、EXACT_DUPLICATE_PLAN.csv、DEDUPLICATION_LEDGER.jsonl：候选、合并及回退身份。
- CORE_AND_ARCHIVE_VERIFICATION.json、VERIFICATION_SUMMARY.json：完整核验与摘要。
- ROLLBACK_QA.json：独立化测试。
- GITHUB_OMITTED_BUT_RETAINED_LOCALLY.csv：未展开上传但本机保留的材料。
- METADATA_PACKAGE_QA.json：压缩元数据逐成员核验。
- GITHUB_PUSH_RESULT.json：实际推送结果；不存在时不能声称已上传。

归档内同步保留manifest/RETENTION_STATE.json及完整合并台账；只读查看与独立化工具为tools/retention.py。
