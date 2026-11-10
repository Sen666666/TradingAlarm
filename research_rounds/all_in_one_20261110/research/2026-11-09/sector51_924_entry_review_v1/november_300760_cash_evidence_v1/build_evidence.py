import json,hashlib,datetime
from pathlib import Path
from decimal import Decimal
import pandas as pd
out=Path(__file__).parent
root=out.parent
action=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions/300760.SZ.json')
manifest=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
m=next(a for a in json.loads(manifest.read_text()) if a['symbol']=='300760.SZ')
facts=Path(m['refs']['facts']);d=pd.read_parquet(facts)
prev=d.loc['2024-11-06'];ex=d.loc['2024-11-07']
P=Decimal(str(prev.raw_close));cash=Decimal('1.65');expected=P/(P-cash);observed=Decimal(str(ex.factor))/Decimal(str(prev.factor))
ev=next(e for e in json.loads(action.read_text())['events'] if e['effective_date']=='2024-11-07')
def save(name,x): (out/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
proposal={'status':'PROPOSED_EVIDENCE_ONLY_NOT_ENGINE_ADMITTED','sid':'300760.SZ','name':'迈瑞医疗','announcement_title':'2024年第二次中期权益分派实施公告','announcement_number':'2024-049','announcement_date':'2024-10-30','record_date':'2024-11-06','ex_date':'2024-11-07','pay_date':'2024-11-07','pay_date_scope':'CSDC Shenzhen distributed A shares; listed company-self-distributed holders excluded from this payment-date certification','currency':'CNY','gross_cash_per_share':'1.65','gross_cash_per_10_shares':'16.50','reference_decrement_per_share':'1.65','source_decrement_per_share':ev['cash_per_old_share'],'split_ratio':'1','action_classification':'ordinary_cash_only','structural_action':False,'structural_evidence':'Section II specifies only cash to all 1,212,441,394 shares. Section I.2 reports no change in share capital. No bonus, capitalization, split or rights component specified in this distribution.','total_shares':1212441394,'total_gross_cash':'2000528300.10','primary_source_url':'https://static.cninfo.com.cn/finalpage/2024-10-30/1221571865.PDF','source_pdf':'300760_2024-049_cninfo.pdf','source_extraction':'300760_2024-049_cninfo.txt','extraction_method':'macOS PDFKit via Swift, downloaded original PDF','facts_locations':{'gross':'Sections I.1 and II, pages 1-2','dates':'Section III, page 2','eligibility':'Section IV, page 2','payment':'Section V.1-2, page 2'},'scope_caveats':['Not a strategy parameter change, formal event adapter, engine admission, backtest or live trade.','Frozen simulation reports candidate UNHELD: no record-date shares means no dividend entitlement. A Nov7 or later new buyer must not be credited this dividend.','Cash/factor event still needs explicit reviewed admission for candidate signal continuity, even when no cash is owed.','Reference decrement is inferred from equal cash distribution to all shares and verified against local factor bridge, not separately quoted exchange reference-price data.','Official notice specifies differential withholding; do not replace frozen net80 modeling convention with official universal 80% withholding claim.','This evidence resolves only the named cash-event fact gap. ST, eligibility and other boundary blockers remain untouched.']}
save('EVENT_FACT_PROPOSAL.json',proposal)
bridge={'sid':'300760.SZ','ex_date':'2024-11-07','facts_path':str(facts),'previous_session':'2024-11-06','raw_previous_close':str(P),'cash_decrement':str(cash),'theoretical_ex_reference':str(P-cash),'factor_before':repr(prev.factor),'factor_after':repr(ex.factor),'formula':'factor_after / factor_before = raw_previous_close / (raw_previous_close - cash_decrement)','expected_ratio':str(expected),'observed_ratio':str(observed),'ratio_abs_error':str(abs(expected-observed)),'pass_abs_tolerance_1e_12':abs(expected-observed)<Decimal('1e-12'),'implied_decrement':str(P*(1-1/observed)),'observed_ex_raw_close':str(ex.raw_close),'note':'Reference is theoretical ex reference, not ex-day traded close. Factor sourced from existing immutable facts; no recomputation or replacement of strategy facts.'}
save('FACTOR_BRIDGE.json',bridge)
save('LOCAL_SOURCE_EVENT.json',{'path':str(action),'event':ev,'manifest_entry':m})
inputs=[action,manifest,facts,root/'november_cash_evidence_v1/MISSING_EVENT_INVENTORY.json']
allfiles=inputs+list(out.glob('*.pdf'))+list(out.glob('*.txt'))+list(out.glob('*.json'))+[Path(__file__)]
save('SOURCE_HASHES.json',{'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sha256':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in allfiles}})
assert bridge['pass_abs_tolerance_1e_12']
assert '2024年11月7日' in (out/'300760_2024-049_cninfo.txt').read_text()
print(json.dumps(bridge,indent=2))
print('pdf_sha256',hashlib.sha256((out/'300760_2024-049_cninfo.pdf').read_bytes()).hexdigest())
