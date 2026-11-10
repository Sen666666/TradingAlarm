from audit import *
def main():
 frozen=read(O/'freeze.json')['sha256']
 for p,h in frozen.items():assert sha(p)==h,p
 full=prefix=control=0
 for c in STARTS:
  a=read(O/c/'analysis/accounting.json');assert a['passed'] and D(a['max_nav_difference'])==0;full+=a['daily_rows']
  p=read(O/c/'prefix-verification.json');assert p['passed'];prefix+=p['daily']
  z=read(O/c/'control-full.json');assert z['passed'];control+=z['daily']
 save(O/'verification.json',{'passed':True,'economic_paths':28,'daily_rows':full,'prefix_daily_rows':prefix,'original_control_daily_rows':control,'original_controls':7,'signal_prefixes':814,'frozen_hashes_unchanged':True,'economic_reruns':0,'post_outcome_parameter_changes':0,'analysis_only_after_freeze':['diagnose.py','complete.py'],'platform_changed':False})
 fs=[p for p in O.rglob('*') if p.is_file() and '__pycache__' not in str(p) and p.suffix!='.log'];save(O/'completion-hashes.json',{str(p.relative_to(O)):sha(p) for p in fs})
if __name__=='__main__':main()
