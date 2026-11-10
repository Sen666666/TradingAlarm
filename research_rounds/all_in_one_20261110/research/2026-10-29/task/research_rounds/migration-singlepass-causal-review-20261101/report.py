"""Condensed causal matrix from saved records/projections. No account execution."""
from pathlib import Path
from decimal import Decimal as D
import json,gzip,collections,hashlib
O=Path(__file__).resolve().parent;W=O.parent
def read(p):return json.loads(Path(p).read_text())
def rows(p):
    with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def obj(p):
    with gzip.open(p,'rt') as f:return json.load(f)
def save(p,x):(O/p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def v(x):return D(str(x))
def fmt(x):return f'{v(x):.2f}'

def main():
    chains=read(O/'CHAINS.json');matrix=[]
    rules=read(Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json'))
    roots={'SC':W/'q2-normal-continuation-20261031/runs/B_diag/pair','SD':W/'migration-admission-singlepass-economics-20261101/runs/2025_26/pair'}
    data={k:dict(book=obj(p/'B.json.gz'),daily={r['at'][:10]:r for r in rows(p/'daily.jsonl.gz')}) for k,p in roots.items()}
    for sid in ['601869.SH','301511.SZ']:
        for ref in ['SC','SD']:
            es=[r for e in chains[sid][ref]['episodes'] for r in e['rows'] if r['canonical_CP1'] and r['mobile_Q'] is True]
            seen=set();outcomes=[]
            for r in es:
                assert r['canonical_CP1'] not in seen;seen.add(r['canonical_CP1'])
                ff=[x for x in r['funding'] if x.get('role')=='mobile'];result=ff[0]['result'] if ff else None
                extra={}
                if r['actual_fill']:reason='actual_filled'
                elif r['barriers']:reason='signal_barrier:'+','.join(r['barriers'])
                elif any(x.get('role')=='core' and x['result']=='reserved' for x in r['funding']):reason='core_reservation_suppressed_mobile'
                elif result=='reserved':reason='reserved_without_fill'
                elif result=='no_nominal_gap':
                    d=r['signal_day'];snap=data[ref]['daily'][d];price=v(r['current_price_state']['raw_close']);nav=v(snap['nav']);held=snap['positions'].get(sid,0)
                    unit=next(x['rule']['buy_minimum'] for x in rules['quantity_versions'][sid] if x['from']<=d and (not x.get('to') or d<x['to']))
                    budget=min(nav*D('.02'),max(D(0),nav*D('.10')-D(held)*price))
                    if budget>0 and budget<D(unit)*price:reason='positive_nominal_target_below_initial_minimum'
                    elif budget<=0:reason='stock_nominal_capacity_zero'
                    else:reason='unresolved_original_no_nominal_gap'
                    extra=dict(close_budget=str(budget),close_price=str(price),legal_initial_minimum=unit,minimum_gross=str(D(unit)*price),held_quantity=held)
                elif result:reason=result
                elif r['next_open_day'] is None:reason='right_boundary'
                else:reason='unknown_no_mobile_funding_record'
                outcomes.append(dict(day=r['signal_day'],next_open=r['next_open_day'],receipt=r['canonical_CP1'],reason=reason,
                    industry=r['industry'],price=r['current_price_state'],held=r['held_previous_close'],rank=r['rank'],**extra))
            save(Path(sid+'_'+ref+'_RECEIPT_OUTCOMES.json'),outcomes)
            cutoff='2025-10-09' if sid=='601869.SH' else '2025-09-03'
            for label,lo,hi in [('whole_window','2025-07-01','2026-06-30'),('after_first_true_exit',cutoff,'2026-06-30')]:
                rr=[x for x in outcomes if lo<=x['day']<=hi]
                matrix.append(dict(sid=sid,name=chains[sid]['name'],reference=ref,phase=label,range=[lo,hi],
                    fresh_Qtrue_receipts=len(rr),outcome_counts=dict(collections.Counter(x['reason'] for x in rr)),
                    first_price=rr[0]['price'] if rr else None,last_price=rr[-1]['price'] if rr else None))
    save(Path('OPPORTUNITY_EPISODE_MATRIX.json'),matrix)
    point_rows=[]
    for d,sid in [('2025-09-01','601869.SH'),('2025-12-19','601869.SH'),('2026-04-22','301511.SZ')]:
        for ref in ['SC','SD']:
            r=read(O/'points'/f'{d}_{sid}_{ref}.json');ls=r['lots'];probe=[x for x in ls if x['pool']=='probe'];conf=[x for x in ls if x['pool']=='confirmed']
            stale=[x for x in probe if not x['own_attempt_still_current']]
            def summary(xs):return dict(layers=len(xs),capital=sum(x['capital'] for x in xs),risk=sum(x['nominal_risk'] for x in xs),
                Ivalid_layers=sum(x['I_valid_previous_close'] for x in xs),profitable_previous_close=sum(v(x['economic_net_previous_close'])>0 for x in xs))
            point_rows.append(dict(day=d,sid=sid,reference=ref,live_NAV=r['opening_live_NAV'],decision_NAV=r['decision_NAV'],
                cash=r['cash_available'],probe=summary(probe),stale_probe=summary(stale),confirmed_held=summary(conf),
                confirmed_with_reservations=r['confirmed'],industry=r['industry'],target_checks=r['full_or_minimum_checks'],
                top10_confirmed=sorted(conf,key=lambda x:-x['capital'])[:10],top10_probe=sorted(probe,key=lambda x:-x['nominal_risk'])[:10]))
    save(Path('POINT_OWNER_MATRIX.json'),point_rows)
    # Preserve the exact owner's role-channel records; no request to rerun 8/1.
    role=[]
    for ref,p in roots.items():
        b=data[ref]['book'];fund=rows(p/'funding.jsonl.gz')
        role.append(dict(reference=ref,stock='600113.SH',name='浙江东日',
            actual_reservations=[x for x in b['journal'] if x['kind']=='real_reserve' and x['sid']=='600113.SH' and x['at'][:10]<='2025-09-01'],
            August1_funding=[x for x in fund if x['sid']=='600113.SH' and x['at'][:10]=='2025-08-01'],
            same_signal_opportunity=[x for x in rows(p/'opportunities.jsonl.gz') if x['sid']=='600113.SH' and x['day']=='2025-07-31']))
    save(Path('OWNER_CORE_MOBILE_CHANNEL.json'),role)
    local=read(O/'THIRTY_THREE_CLASSIFICATION.json')
    lc=read(O/'points/2025-12-19_601869.SH_SD.json')['full_or_minimum_checks'][0]
    dc=read(O/'points/2026-04-22_301511.SZ_SD.json')['full_or_minimum_checks'][0]
    lines=['长飞/德福源头诊断｜仅原账与三个固定开盘的资源投影，无账户/策略回放','',
        '外部信号/Q/CP1/H1顺序逐日核同；长飞32张、德福26张Q=true fresh CP1均相同。',
        'SD长飞32张：成交2、原资源拒20、行业attempt失效2、正2%名义目标不足一手8；真全清后仍有17张，其中资源拒7/行业失效2/目标不足8。',
        'SD德福26张：成交1、原资源拒19、行业attempt失效6；真全清后仍有16张，其中资源拒10/行业失效6。',
        '目标股票没有ACT暂停、core成功抢占mobile或一手规则变化导致的第一次差异；目标core失败后mobile都实际进入路由。','',
        '1. 长飞：先减量，后来新凭据重入被行业risk拒。',
        '9/1同价92.54625、同原目标200股：SC200、SD100（均confirmed mobile）。',
        'SC通信行业既有名义risk9792.08，SD11814.83；SD一手新risk1233.86可容纳、两手2467.72过原1%行业risk。',
        '差额来自既有太辰光2032风险及仕佳等数量差，均I有效、前收盘盈利；不是同日新单抢走、不是可称垃圾的旧仓。',
        '9/4各追加100；10/9分别卖300/200股，CP1 mobile保护退出相同，第一轮闭合净+2011.83/+1186.84。',
        f"12/19同原目标200：SC重入100、SD0。SD行业已有11430.06风险，一手需{fmt(lc['new_nominal_risk'])}而含费余量仅{fmt(lc['remaining_industry_risk'])}。",
        '两者共同有先于它预留的长芯博创risk1772.16；主要存量差为SD永鼎risk3621.84 vs SC信科risk316.20。',
        '永鼎12/12在SD获mobile900，SC当时原资源拒绝；该SD凭据不在“局部解锁33”内，属于早先状态分叉后的普通分配。',
        'SC后来100股入价110.055，6/30原收盘545.90仍未平，净+43578.79；SD没有再次实际入场。后续并非无信号：详情见receipt outcomes。','',
        '2. 德福：第一轮完全相同，后来同时遇到旧占额和同开盘优先竞争。',
        '7/2两臂900股；9/3同CP1保护卖900，第一轮均闭合净+10377.45。',
        '4/22 SC原目标400且实际400；SD受此前NAV影响原目标300，但一手100本可通过原目标/股/行业检查。',
        'SD confirmed实际承诺719837.70，含先到的金安国纪300股毛12501.25预留（rank15优先于德福rank40；该单不是局部33之一，后来也确实fill300）。',
        f"有效confirmed含费余量{fmt(dc['remaining_confirmed_capital'])}元，一手毛{fmt(dc['gross'])}，故confirmed池容量拒；现金39.37万不是限制。",
        '原probe亦无路：已有6层88135.80资本/risk12202.64，高于约6015.43风险上限；6层全部旧attempt，但I仍有效且前收盘经济净贡献正。',
        '其中蓝特光学core risk6535.40、九州一轨mobile2218.44等，不可仅凭attempt编号称垃圾或假释放。',
        'SC该400股入价62.020995，6/30原收盘143.93仍未平，净+32757.01。两个缺席未平层合计76335.81元，占两股贡献差77160.80元的98.93%；不是新增SD层的已实现亏损。','',
        '3. 角色/保护层的路径依赖是比“多留几元现金”更具体的风险。',
        '7/31浙江东日同一日core+mobile证据均合法；8/1 SC两角色均probe_risk拒，SD先reserve core700即跳mobile。',
        '9/1 SD浙江仍core/probe，市值41671、远core线26.41，名义risk23184；此前经济净+21368.71，I与原attempt仍有效。',
        '该23184名义risk可分剩余本金下行1529.003、浮盈回吐21654.997（按gross unit cost28.59429）；回吐仍是真实财富风险，不豁免。',
        'SC稍后8/6、8/12、8/15以fresh mobile近线参与，至9/1该股500股已在confirmed，保护51.8029、总risk3863.54。',
        '这是原core-first及两种保护职责的合法路径反馈，不是漏更新。浙江解释probe备路受压，不是通信行业risk差的直接来源。',
        '两遍仍保留core-first；更多minimum core可抑制同股mobile。不能把更多试仓自动解释为更好的确认扩张。','',
        '局部33凭据语义：5张在SC为probe、9张在SC也为confirmed，3张SC先reserve core而跳mobile，16张SC同开盘无预留。',
        '它们是在SD自身状态下确实依赖去门的新confirmed权限；14张与SC实际mobile成交重合。只有全局首次分歧7/2松发（SC probe200→SD confirmed400）有共同前状态识别。',
        '后续33的cohort盈利24918.93不是边际政策利润，也不能称33个净新增参与者。','',
        '正对照：思泉新材SD8/1先买200、8/7再100，SC仅8/7买100；同10/20退出，贡献25593.15 vs6507.23。',
        '上纬新材SC7/22起四批、SD7/23起三批；SD首入更晚但第一轮1038股同8/7退出，未参加SC8/15再入的后续亏损，贡献35491.72 vs20143.27。',
        '上纬SD有8次预留（7 mobile+1 core），仅3张mobile真实fill；core211及4张mobile均未fill，不能把预留说成交；原执行代理限制保留。',
        '这与两只失去的赢家共同说明路径竞争可获益也可损失，不构成用未来赢家重排当日资金的理由。','',
        'SD三个点的当前confirmed总承诺 / probe持股 / 其中旧attempt probe（元）：',
        '9/1: 749006.74 / 50370.00 / 2874.00；12/19: 649021.17(含当日新单14337.17) / 51886.00 / 41867.00；',
        '4/22: 719837.70(含当日新单12501.25) / 88135.80 / 88135.80。完整SC/SD前10持仓与待单、原角色/保护/有效性在POINT_OWNER_MATRIX及points中。','',
        '三点结论：确认后新准入与旧迁池解耦在逻辑上成立；这次差额主要经持仓行业风险/容量和角色保护路径传导。',
        '两遍只压缩当日新probe预留，不能直接压缩上述既有风险。在4/22固定S0所有probe均旧attempt且风险已超限，原两遍对这一开盘没有可缩新probe，按冻结规则应不变。',
        '尤其金安和德福都是confirmed mobile，新股/重入的“小参与”不等于pool=probe；只probe小额化不会均分这两笔confirmed竞争。若研究对象要扩大须另审经济合同，不能借接线偷偷改变。',
        '早期两遍是否改变这些路径仍未知，不能因此否定小试方向，也不直接启动整窗。Native固定提交与异常协议缺口见TWO_PASS_NATIVE_DESIGN_GAPS.txt。','',
        '证据边界：仅三个固定开盘，按原实际sell/reserve与原迁池表示转换重建资源，不是完整Account恢复。',
        'SD三开盘分别475/84/263处保存资源标量核同；SC无同类逐笔标量，依原账/规则重建且目标实际量与原约束检查相符。',
        '局部数量可行性不是可执行反事实PnL。全部源/旧账未改；没有Account/Contract构造、指标重算、替代分配preview或新经济路径。']
    (O/'CAUSAL_READOUT.txt').write_text('\n'.join(lines)+'\n')
    save(Path('READINESS.json'),dict(ready_for_readonly_review=True,new_financial_paths=0,new_allocator_runs=0,
        original_economic_sources_changed=False,resource_projection_points=6,SD_scalar_anchors=[475,84,263],
        scope='two named stocks, two deterministic positive-delta controls, one global first intervention and owner role example',
        full_account_state_restored=False,unknowns=['full policy marginal PnL of the 33 conditional permissions','two-pass full-history effect'],
        financial_wait_correction='migration-admission-singlepass-economics-20261101/analysis-errata-20261101/CORRECTION_VERIFICATION.json'))
    files=[p for p in O.rglob('*') if p.is_file() and p.name!='ARTIFACT_SHA256.json' and '__pycache__' not in p.parts]
    save(Path('ARTIFACT_SHA256.json'),{str(p.relative_to(O)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)})
    print('CAUSAL_REPORT_READY',len(files),'files')

if __name__=='__main__':main()
