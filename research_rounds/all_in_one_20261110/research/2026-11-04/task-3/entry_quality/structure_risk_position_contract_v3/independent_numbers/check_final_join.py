"""Final metadata/data join only; does not rerun local arithmetic or OPEN bridges."""
from pathlib import Path
import json,hashlib
OUT=Path(__file__).resolve().parent;V3=OUT.parent;SOURCE={};CHECKS=[]
def read(p):
 p=Path(p);b=p.read_bytes();SOURCE[str(p)]=hashlib.sha256(b).hexdigest();return json.loads(b)
def ck(n,x):CHECKS.append({'name':n,'pass':bool(x)});assert x,n
local=read(V3/'cases/SEVEN_FIXED_PREFIX_LOCAL_ARITHMETIC.json');final=read(V3/'cases/FINAL_SEVEN_PAPER_DECISIONS.json')
binding=read(V3/'cases/FINAL_BINDING.json');recon=read(V3/'cases/OWN_DERIVED_INPUT_HASH_RECONCILIATION.json');cardrecon=read(V3/'cases/CONTRACT_VERSION_RECONCILIATION.json')
la=read(OUT/'FINAL_SEVEN_LOCAL_AUDIT.json');oa=read(OUT/'SEVEN_ACTUAL_OPEN_BRIDGE_AUDIT.json');bridge=read(V3/'open_prefix/SEVEN_ORIGINAL_OPEN_PREFIX_BRIDGES.json')
localpath=str((V3/'cases/SEVEN_FIXED_PREFIX_LOCAL_ARITHMETIC.json').resolve());bridgepath=str((V3/'open_prefix/SEVEN_ORIGINAL_OPEN_PREFIX_BRIDGES.json').resolve());card=V3/'designer/MINIMUM_MATH_CONTRACT.md';cardsha=hashlib.sha256(card.read_bytes()).hexdigest();SOURCE[str(card)]=cardsha
ck('current final binding local/bridge SHA exact',binding['local_sha256']==SOURCE[localpath] and binding['OPEN_bridge_sha256']==SOURCE[bridgepath])
ck('local audit input exact current bytes or explicit before-to-after annotation bridge',SOURCE[localpath]==recon['after_cash_annotation'] and la['source_sha256'][localpath]in [SOURCE[localpath],recon['before_cash_annotation']])
ck('final card independently used by both audits, final binding and reconciliation',binding['current_contract_sha256']==cardsha==cardrecon['current_contract_sha256']==la['source_sha256'][str(card)]==oa['source_sha256'][str(card)])
ck('audited OPEN bridge bytes still exact',oa['source_sha256'][bridgepath]==SOURCE[bridgepath])
bi={(r['window'],r['next_OPEN'][:10]):r for r in bridge['results']};oi={(r['window'],r['actual_OPEN'][:10]):r for r in oa['rows']}
for l,f in zip(local,final):
 key=(l['window'],l['nextOPEN']);b=bi[key];aud=oi[key]
 ck(l['decision']+': final copies local fields with explicit local-status namespace',all(f['local_disposition' if k=='final_disposition' else k]==v for k,v in l.items()if k!='OPEN_full_portfolio_pressure') and 'final_disposition'not in f)
 x=f['original_OPEN_pressure_necessary_condition']
 pairs={'cash_after_actual_exits_and_settles':'cash_after_original_settles','ACTpeak':'ACT_peak','native_mark_NAV':'native_known_mark_NAV_prefix','native_mark_inventory':'native_known_mark_inventory_after_sells','A_native':'A_native_domain','G2_lower_native':'G2_lower_native_mark_domain','exact_raw_OPEN_NAV':'raw_OPEN_valued_NAV_prefix','exact_raw_OPEN_inventory':'exact_raw_OPEN_inventory_after_sells','A_OPEN':'A_OPEN_valuation_domain','G2_lower_OPEN':'G2_lower_OPEN_valuation_domain'}
 ck(l['decision']+': final exact original OPEN bridge amounts',all(x[k]==b[v]for k,v in pairs.items()))
 ck(l['decision']+': final source and independent audit agree',x['source_sha256']==SOURCE[bridgepath] and x['next_OPEN']==b['next_OPEN'] and x['both_necessary_inequalities_fail'] and x['not_signal_CLOSE_substitution'] and aud['grant_quantity_at_original_prefix']==f['q_final_grant']==0)
 ck(l['decision']+': no replacement account outcome claim',f['counterfactual_account_gain']=='NOT_COMPUTED_NOT_IDENTIFIED' and f['single_prefix_only'])
res={'status':'PASS_FINAL_SEVEN_JOIN_WITH_EXPLICIT_VERSION_RECONCILIATION','checks':CHECKS,'final_grants':[f['q_final_grant']for f in final],'local_caps':[f['q_local_after_source_and_frozen_caps']for f in final],'source_sha256':SOURCE,'consumed_local_version_note':{'owner_appended_cash_annotation_before_sha256':recon['before_cash_annotation'],'owner_appended_cash_annotation_after_sha256':recon['after_cash_annotation'],'independent_audit_consumed_sha256':la['source_sha256'][localpath],'audit_consumed_current_bytes':la['source_sha256'][localpath]==SOURCE[localpath],'scope':'Origin/fees/kappa/local-q fields retained and final copy checked; different owner versions not called unchanged.'},'current_contract_sha256':cardsha,'new_arithmetic_or_global_reruns':0,'new_accounts':0}
res['script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();(OUT/'FINAL_JOIN_AND_SOURCE_RECONCILIATION.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':res['status'],'checks':len(CHECKS),'q':res['final_grants']}))
