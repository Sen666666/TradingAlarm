只读准备已完成：97个原日记录、29个真实CP凭证、40条原保存intent旁注。未运行V4或其他状态机，未新建账户/订单，未导出候选数量、现金或收益。

盈新2022年1月19个原观察日有9个CP：1/7、1/10、1/11、1/12、1/13、1/20、1/21、1/24、1/25。海能达2024年1月无CP；9月至11/27有20个，完整日期/保护价/真实ID/冻结尺度/原角色及层ID见[CP_RECEIPT_TABLE.csv](CP_RECEIPT_TABLE.csv)。9/20凭证即使没有原保存intent也保留，不能只取原成交/申请母体。

关键同日时钟事实：

- 盈新1/6原up无CP，1/7才有CP；1/20新up与CP同时出现，1/21又有CP而V3仍START，1/24成熟且有CP。候选值依次为1/20的3.240185719931597、1/21的3.553880661418941、1/24的3.904117953737246，均为连续调整价域。
- 海9/19原up无CP，9/20有首CP21.907325111517334；9/30新up+CP33.482232147854816、10/11新up+CP41.508605578976066；11/20新up+CP102.637393202947，V3当日仍未成熟。
- 海原CORE1994是10/14信号，该日无CP，不能伪称消耗一个原CP。原MOBILE2017/2039分别对应10/18与10/21的CP59.14866295659032、63.67407589811411。
- 盈新原1/10同收盘有CORE和MOBILE intent，但只有CORE对应实际层68；原MOBILE旁注的无成交不能被改写成候选拒绝或已消耗probe。

原CP生成输入是保存的`CP1-input`：`close, segment_id, i_target, i_floor, amount, e0_down, e0_valid`；两股全源自2013-01-04开始。当前范围逐日已核`e0_valid == old_native.i_target`、`i_floor == old_native.i_floor`。原实现`continuous-protection-lines-20261028/code/common.py:23`把旧I target映射到e0_valid；`model.py:33–36`在无效/下行时重置，`:40–49`用新frontier/credit发receipt、先用旧冻结scale生成candidate，再消费并冻结next_scale。因此这些原CP不是V3-I重算后的新CP，后续若只接授权FSM，必须保留“冻结旧CP旁路”口径。

两层状态必须分开：V3 `active_generation/I_hold/P`是纯信号结构，不是实际账户position；原链保存的实际layer IDs、旧线和pending列表仅作**原路径条件**。假设某笔授权改变后，后续原snapshot不能当作新路径现状；没有原snapshot的日期写UNKNOWN，不当flat。原40条intent与原层号只是注释，不输入候选，也不能据此判最终grant、reserve消费、部分成交或撤单ACK。未定义的V4 probe消费/失败重试/pending锁与执行clock等待冻结，本准备稿不自行选择。

文件：

- [DAILY_ORIGINAL_CP_INPUTS.json](DAILY_ORIGINAL_CP_INPUTS.json)：全部97日，包括无receipt日、原生成输入、原请求、V3旁注和已存原position条件。
- [CP_RECEIPT_TABLE.json](CP_RECEIPT_TABLE.json)：29个完整真实凭证的关键字段；完整canonical来源保留于每日表。
- [ORIGINAL_REQUEST_ANNOTATIONS.json](ORIGINAL_REQUEST_ANNOTATIONS.json)：40条原intent/角色/CPID/实际层ID，保原索引。
- [CP_GENERATOR_SOURCE_AND_INPUT_CONTRACT.json](CP_GENERATOR_SOURCE_AND_INPUT_CONTRACT.json)与[PREPARATION_RECEIPT.json](PREPARATION_RECEIPT.json)：真实源路径、核对范围及SHA。

V3/V2和原CP/账户源均未修改。
