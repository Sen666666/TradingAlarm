"""Freeze independently reviewable preparation; never create release or run economy."""
from pathlib import Path
import json,hashlib,time,sys,platform,importlib.metadata
import annual_bridge_v1 as E
import run_annual_v1 as RUN
HERE=Path(__file__).resolve().parent;B=HERE.parent
def read(p):return json.loads(Path(p).read_text())
def save(name,v):RUN.save(HERE,name,v)
def main():
    qa=HERE/sys.argv[1]
    result=read(qa/'RESULT.json');assert result['status']=='AUTHOR_PASS_PENDING_INDEPENDENT_REVIEW'
    old=read(B/'known_evidence_union_diagnostic_v1/RUN_CONTRACT.json')
    protected=read(HERE/'PROTECTED_OLD_INPUTS.json')
    deps=E.merge_hashes(old['dependencies'],read(qa/'SOURCE_HASHES.json'),protected)
    for root in ['known_evidence_union_diagnostic_v1','known_halt_contract_v1','known_halt_dividend_candidate_v1','indexed_execution_v1','source_bridge_v1','shared_feasibility_v1','execution_bridge_v1']:
        deps=E.merge_hashes(deps,{str(p):E.sha(p) for p in (B/root).glob('*.py')})
    for p,h in deps.items():assert E.sha(p)==h,('dependency drift',p)
    fee_path=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/inputs-v2/market-rules.json')
    fee_rows={venue:[r for r in rows if r['from']<='2022-12-31' and (not r.get('to') or r['to']>'2022-01-01')] for venue,rows in read(fee_path)['fee_versions'].items()}
    save('FROZEN_2022_FEE_SCHEDULES.json',dict(source=str(fee_path),source_sha256=E.sha(fee_path),scope='exact original dated research schedules, no changes',fee_versions=fee_rows))
    contract={k:v for k,v in old.items() if k!='dependencies'}
    contract.update(version='ANNUAL_2022_MARKED_NAV_V1',scope=RUN.SCOPE,end='2022-12-30',birth_end='2022-12-31',observation_end_only=True,post_2022_account_phases=False,
        original_birth_source_sha256=old['dependencies'][str(B.parent/'m3_stock_birth_during_sector_v1/SEALED_ALL_BIRTH_EVENTS.csv')],
        source_engine_unchanged=True,
        entry='Original M3 A_SECTOR_BIRTH or B_STOCK_BIRTH_DURING_SECTOR events; original I/PVR eligibility; original industry top-two selection and PVR-descending/sid global order. Not a native E0/attempt entry gate.',
        preserved_parameters=dict(round_INIT='.02*frozen_Nd',round_ADD='.02*frozen_Nd',round_SLOT='.04*frozen_Nd',round_fee_risk='.0025*frozen_Nd',
            effective_NAV_probe_capital='.10',effective_NAV_probe_nominal_risk='.005',industry_ALL_probe_capital='.02',industry_ALL_confirmed_capital='.10',
            industry_ALL_nominal_risk='.01',cash_reserve='.10*daily_planning_NAV',stock_capital='.10*daily_planning_NAV',
            confirmed_industry_10pct='existing research parameter, not optimality assertion',one_successful_ADD=True),
        additional_halt='600595.SH 2022-05-19 FULL_DAY only; official historical full-day row + matching official announcement index + original-venue news pre-OPEN facts + complete mirror; original publisher PDF unavailable',
        halt_evidence_clock='2022-05-18T21:19:59+08:00 conservative news minute end; not fulltext publication time',
        entitlement_rule='Original 436+1 catalog/permissions unchanged; halt does not waive native local or admitted corporate-action conflict check or factor/source continuity',
        risk_rule='Native stale price global risk lock and resume OPEN recovery lock remain; reporting marks never feed back to decisions or quantities',
        reporting_NAV='cash + gross raw CLOSE inventory + recognized receivables; on evidence-supported full-day halts use last valid CLOSE; no hypothetical sell fee',
        reporting_allowed_substitutions=['KNOWN_HALT_STALE_MARK','RESUME_OPEN_RECOVERY_LOCK'],
        reporting_unknown='No substitution if any unknown, missing mark or unsupported gap. Annual return only year end reached; marked close DD only complete supported close path.',
        win_rates='Only execution-and-settlement-closed as of observation end; show total/closed/open-or-unsettled counts. No future terminal outcome labels.',
        fees='Exact frozen original dated per-order net-brokerage 0.0002 minimum CNY5, sell stamp 0.001 in 2022; exchange components separately charged. See FROZEN_2022_FEE_SCHEDULES. No changes.',
        slippage='buy raw OPEN*(1+.0005), sell raw OPEN*(1-.0005), conditional historical proxy not executability proof',
        dividends='NET80 research convention .8*registered-own-quantity*verified cash dividend; not actual personal tax withholding',
        hypothetical_liquidation='Original layer/round reports separately use terminal raw CLOSE*(1-.0005) minus hypothetical whole sell fee; never wallet marked NAV or realized winner classification.',
        observation_end_behavior='Preserve all actual quantities/costs/claims/orders; no forced liquidation. Last legal Dec30 signals may remain pending, not executed in 2023.',
        source_loading_limit='Original source module may load frozen full source history, but account phases and terminal reports never exceed 2022 observation end.',
        dependencies=deps)
    save('RUN_CONTRACT.json',contract)
    attempts=[]
    for p in sorted(HERE.glob('qa_attempt_*')):
        f=p/'RESULT.json';bad=p/'FAILURE.json'
        attempts.append(dict(name=p.name,status='PASS' if f.exists() else 'FAILED',result=read(f if f.exists() else bad)))
    save('ATTEMPT_HISTORY.json',dict(attempts=attempts,changes=['Attempt01 retained: star import overwrote adapter HERE, evidence lookup failed before prefix/new economy. Changed to explicit exports in annual adapter. All original code and outputs unchanged.','After qa02 freeze, direct official SSE historical raw-page provenance was added as an artifact. Prior metadata bytes archived before reseal; no economic logic changed.'],new_annual_economic_runs=0))
    save('AUTHOR_PRE_RUN_READOUT.json',dict(status='AUTHOR_PASS_PENDING_INDEPENDENT_REVIEW',qa=result,prefix=read(qa/'PREFIX_COMPARISON.json'),
        actual_overlap_test=read(qa/'ACTUAL_HASH_MERGE_TEST.json'),dependencies=len(deps),protected_old_files=len(protected),
        independent_review_needed=['May19 evidence subtype and exact clock/session scope','No mutation of financial engine/risk contract','Only reporting carries known halt/recovery marks; UNKNOWN unfilled',
            'Annual end only and no post-2022 actions/labels','Actual duplicate-key source intersection, conflicts and full final resource gate','Closed-only stats denominators and gross-NAV vs hypothetical-liquidation distinction'],
        frozen_at=time.time(),new_annual_economic_runs=0))
    files=[p for p in HERE.rglob('*') if p.is_file() and p.name not in ('PRE_RUN_STAGE_SEAL.json','INDEPENDENT_REVIEW_RELEASE.json')]
    save('PRE_RUN_STAGE_SEAL.json',{str(p.relative_to(HERE)):E.sha(p) for p in sorted(files)})
    print(json.dumps(dict(stage_sha256=E.sha(HERE/'PRE_RUN_STAGE_SEAL.json'),stage_files=len(files),dependencies=len(deps),prefix=read(qa/'PREFIX_COMPARISON.json')),indent=2))
if __name__=='__main__':main()
