import json,hashlib
from pathlib import Path
import pandas as pd
OUT=Path('results/strength-peer-gate-transfer485')
def main():
 p=json.loads((OUT/'protocol.json').read_text())
 for name,h in p['source_sha256'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
 new=pd.read_parquet(OUT/'episodes.parquet');old=pd.read_parquet(Path(p['control_reference'])/'episodes.parquet')
 a=new.loc[new.strategy.eq('pairwise_volume')].reset_index(drop=True);b=old.loc[old.strategy.eq('pairwise_volume')].reset_index(drop=True);pd.testing.assert_frame_equal(a,b,check_exact=True)
 v=json.loads((OUT/'validation.json').read_text());v.update(exact_control_rows=len(a),source_hashes=len(p['source_sha256']),gate_unit_tests=2);(OUT/'validation.json').write_text(json.dumps(v,indent=2));print(v)
if __name__=='__main__':main()
