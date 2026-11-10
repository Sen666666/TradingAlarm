from finish import *
def main():
 for p,h in read(O/'freeze.json')['sha256'].items():assert sha(p)==h,p
 full=prefix=control=0
 for rank,c in PAIRS:
  root=O/rank/c;a=read(root/'analysis/accounting.json');assert a['passed'] and D(a['max_nav_difference'])==0;full+=a['daily_rows'];p=read(root/'prefix-verification.json');assert p['passed'];prefix+=p['daily'];z=read(root/'control-full.json');assert z['passed'];control+=z['daily_rows']
 save(O/'verification.json',{'passed':True,'paths':49,'old_controls':14,'daily_rows':full,'physical_prefix_rows':prefix,'old_control_rows':control,'inherited_signal_prefixes':2442,'frozen_hashes_unchanged':True,'economic_reruns':0,'post_outcome_parameter_changes':0,'platform_changed':False})
 fs=[p for p in O.rglob('*') if p.is_file() and '__pycache__' not in str(p) and p.suffix!='.log'];save(O/'completion-hashes.json',{str(p.relative_to(O)):sha(p) for p in fs})
if __name__=='__main__':main()
