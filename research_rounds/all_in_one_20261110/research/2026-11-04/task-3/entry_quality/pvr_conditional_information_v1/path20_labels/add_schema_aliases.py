"""Post-export naming aliases only, without recomputing any label or mask."""
from pathlib import Path
import hashlib
import json
import shutil
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
PATH=HERE/'PATH20_LABELS.parquet'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
receipt=json.loads((HERE/'RUN_RECEIPT.json').read_text())
assert sha(PATH)==receipt['output_sha256']
assert not(HERE/'PATH20_LABELS_pre_alias.parquet').exists()
shutil.copyfile(PATH,HERE/'PATH20_LABELS_pre_alias.parquet')
frame=pd.read_parquet(PATH)
mapping={'ret20_open':'path20_return_next_OPEN','mfe20_open':'path20_MFE_next_OPEN','mae20_open':'path20_MAE_next_OPEN',
         'ret20_close':'path20_return_decision_CLOSE','mfe20_close':'path20_MFE_decision_CLOSE','mae20_close':'path20_MAE_decision_CLOSE'}
for new,old in mapping.items():
    frame[new]=frame[old]
    assert np.array_equal(frame[new].to_numpy(float),frame[old].to_numpy(float),equal_nan=True)
temp=HERE/'PATH20_LABELS_FINAL.tmp.parquet'
frame.to_parquet(temp,index=False,compression='zstd');temp.replace(PATH)
(HERE/'RUN_RECEIPT_pre_alias.json').write_text(json.dumps(receipt,indent=2)+'\n')
receipt['pre_schema_alias_output_sha256']=receipt['output_sha256']
receipt['output_sha256']=sha(PATH)
receipt['schema_aliases']=mapping
receipt['post_export_alias_only']=True
receipt['source_sha256'][str(Path(__file__).resolve())]=sha(__file__)
(HERE/'RUN_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(dict(rows=len(frame),complete=int(frame.path20_complete.sum()),output_sha256=receipt['output_sha256'],schema_aliases=mapping),indent=2))
