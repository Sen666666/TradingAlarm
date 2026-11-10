# 双时间尺度PVR：定义与最小评价口径

本件为纸面/源码独审，不是执行试探或成熟加仓合同。原候选依赖旧账户路径，跨行业同日比较也不是同业条件控制；股票/行业固定池非PIT。

原e仍为`u*(1+.5*abs(u)*b)`，u=tanh(r/s)，s为排当前的63个abs logreturn中位×1.4826，amount背景亦排当前21观察。首个有限e最早在同block第65个价格观察；fast5最早第69个，原PVR21e第85个，slow滞后5…62最早第127个。全部为原有效观察，非自然日或新CP后日数；invalid/source切block，不跨重启拼窗口，且须保pre-window历史。

fast是当前至前4个e、最新权重1再按0.8逐步衰减并归一化；slow是t−62至t−5共58个e等权，两窗口不重叠。它们仍共享相同价格、sigma/amount背景及趋势自相关，不代表独立证据。慢项长预热可能排除新上市或刚恢复有效来源的机会；慢项延迟也可能压低快速V形/启动股，不宜先称消除噪声。

已发现首版feature把fast也绑在63有限e上。该pass中断且无最终数据，修正版把fast独立5e计算放在63slot guard之前；不能再用dual_memory_status筛fast-only。完整fast队列必须保留fast-ready但slow/PVR未ready者。原PVR在该池的参照用保存native槽顺序，原PVR未知的H1固定槽不悄悄删除。

COMMON只按当时原PVR、fast、slow全部known及N>=10形成共同池；FAST_ONLY用独立fast已知池。两family各自比较，不跨池混分母。每个同日family、每臂都独立选K=ceil(N/10)，不采用percentile>=.9代替数量、不补未来缺失、不要求fast/slow正号、不求FAST与CONT交集。FAST只是队列名，不等同真实新E0、实际probe或假阳性。

平均秩分位p=A/[2(N−1)]时，CONT的精确比较键为3A+7B，分母20(N−1)同组固定；同分再原H1/sid。原PVR槽、分位ordinal和原native数字rank键不可混。FAST/CONT union可有2K成员，不得与K票baseline比总捕获量当作免费改善；保交集/union数及同日所选行业构成。

所有pool/rank/topK先落SHA再加载future labels。主标签沿既有t+1…t+20全部共享会话完整路径，以t+1OPEN为参考，Ct三指标固定副口径；max/min保符号且不是可成交价。30% peak/terminal仅为固定20会话价格尾部proxy，未成熟/缺失为UNKNOWN，不代表生命周期盈利/亏损。

先保每臂source picks K、known L、missing K−L。a个已知selected尾、u个selected未知的precision界为[a/K,(a+u)/K]。池已知尾T、池未知U时，若T>0，sharp capture界是[a/(T+U−u),(a+u)/(T+u)]；T=0需单列无已知尾/潜在尾，不填0或除0。主union-complete日期可有u=0而未选池仍有U>0，a/T只能叫已知池capture，不能冒完整池。

公平均值仅在该family所有既定selected union都完整的日期同时评所有臂，再等day权；不按臂各用不同日期，也不将缺日期填0。另全source selected诊断保缺失数和上下界。均值、分位、负终值率、MFE/min、尾部gained/lost均应保共同日期/数量；记录失去多少原候选/日期。开发2022—23仅描述，不选0.3/0.7、窗口或topfraction；后期已被消费历史不能叫真实OOS。

fast/slow的同日秩相关与top overlap、source观察跨度、selected中slow/fast非正比例和行业集中应并列解释。不同臂上/下尾都变宽、丢失大赢家或跨期方向不稳时，不可仅凭某个MFE或尾数晋升。没有账户资金/持仓路径，任何排名位移都不是收益反事实。
