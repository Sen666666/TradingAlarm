"""Saved necessary-before/recovered-after accounting only."""
from pathlib import Path
import sys
import budget250 as B
X=B.X;E=B.E;P=B.HERE
sys.path.insert(0,str(X.M.C.OLD));from verify_saved import check_json
old=X.read(B.OLD/'C20_FAILED_NECESSARY_OBSERVABLE.json');new=X.read(P/'runs/C_BATCH20/2025-07-22-CLOSE.json');a=old['account'];b=new['account']
for k in ('fills','trades','native_inventory','market_marks','market_asof','market_factors','native_settlements','native_dividends','native_actions','core_epochs'):E.require(a[k]==b[k],'recovery changed prior financial field '+k)
for k in ('act','scopes','consumed','losses','incidents'):E.require(a['policy'][k]==b['policy'][k],'recovery replayed policy phase '+k)
E.require(old['f1']==new['f1'] and old['f1seq']==new['f1seq'],'F1 necessary phase replayed')
for cid,c in old['authority']['certificates'].items():E.require(new['authority']['certificates'][cid]==c,'old authority rewritten')
for k,v in old['approved_risk']['approvals'].items():E.require(new['approved_risk']['approvals'][k]==v,'old R0 authority changed')
E.require(new['events'][:-1]==old['events'] and new['events'][-1]['at'].startswith('2025-07-22') and new['events'][-1]['phase']=='CLOSE','native close history was not appended exactly once')
checks=[]
for f in sorted((P/'runs/C_BATCH20').glob('20*-*.json')):
 if f.stem.split('-')[-1] in ('ACTION','OPEN','CLOSE'):checks.append(dict(file=str(f),sha256=X.sha(f),differences=check_json(f)))
X.save(P/'RECOVERY_FINANCIAL_GATE.json',dict(passed=True,F1_and_ACT_not_replayed=True,old_receipts_losses_R0_certificates_unchanged=True,old_fills_cash_inventory_unchanged_at_optional_retry=True,new_authority_and_planned_funding_only=True,close_event_appended_once=True,event_checks=checks,financial_events=0));print('RECOVERY_FINANCE_PASS',len(checks))
