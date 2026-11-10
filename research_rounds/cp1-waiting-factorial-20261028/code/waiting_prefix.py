"""Additional literal waiting-log prefix check, without account execution."""
from fw_common import *
KINDS={'intent_create','intent_end','intent_entry_class','waiting_support_raise','waiting_support_inherited','entry_contract'}
def main():
 result=[]
 for sector in ['TECH','DRUG']:
  count=0
  for mode in run_modes(sector,'prefix'):
   for stress in SCENARIOS:
    aid=f'{mode}__S0_{stress}';a=read(O/sector/'technical/prefix'/f'{aid}.json');b=read(O/sector/'accounts-v2'/f'{aid}.json')
    small=[r for r in a['audit_log'] if r['kind'] in KINDS];large=[r for r in b['audit_log'] if r['kind'] in KINDS and r['at'][:10]<='2026-06-30']
    assert json.dumps(small,sort_keys=True)==json.dumps(large,sort_keys=True),(sector,aid,'waiting prefix');count+=len(small)
  result.append(dict(sector=sector,accounts=len(run_modes(sector,'prefix'))*3,waiting_and_entry_log_rows=count))
 save(O/'waiting-prefix-verification.json',dict(passed=True,cutoff='2026-06-30',source_sha256={str(Path(__file__)):sha(__file__)},receipts=result))
 print(result,flush=True)
if __name__=='__main__':main()
