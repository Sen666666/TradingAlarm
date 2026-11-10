from prepare import *
if __name__=='__main__':
 checks=[]
 for name in ['R1','R2','R3','P1']:
  for sid in SYMS:
   f=eligible_prices(pd.read_parquet(ORIG/'signals'/f'{sid}.parquet'));full=pd.read_parquet(O/name/'traces'/f'{sid}.parquet')
   for end in ['2024-12-31','2025-12-31','2026-06-30','2026-08-31']:
    small=run(f.loc[:end],int(name[-1]),name.startswith('P'));pd.testing.assert_frame_equal(small,full.loc[:end],check_exact=True);checks.append(dict(version=name,symbol=sid,end=end,rows=len(small)))
  stats=dict(rows=0,shock=0,bad_shock=0,bad_price=0,bad_credit=0,bad_weight=0,negative_medium_warm=0)
  for path in (O/name/'traces').glob('*.parquet'):
   z=pd.read_parquet(path);events=z[z.event.ne(0)];stats['rows']+=len(z);stats['shock']+=int(z.shock.sum());stats['bad_shock']+=int(((z.shock==1)&((z.grade!=-2)|(z.c_target!=0)|(z.h_buy)|(z.c_buy))).sum());stats['bad_price']+=int((events.frontier<events.threshold).sum());stats['bad_credit']+=int((events.credit<events.threshold).sum());stats['bad_weight']+=int(((z.weight<0)|(z.weight>1)).sum());stats['negative_medium_warm']+=int(((z.mu21<=0)&(z.grade>=2)).sum())
  assert not any(stats[x] for x in ['bad_shock','bad_price','bad_credit','bad_weight']);assert name not in ['R2','R3'] or stats['negative_medium_warm']==0
  (O/name/'contracts.json').write_text(json.dumps(dict(passed=True,**stats),indent=2)+'\n')
 (O/'signal-prefix.json').write_text(json.dumps(dict(passed=True,checks=checks),indent=2)+'\n');print('physical prefixes',len(checks),'all contracts pass')
