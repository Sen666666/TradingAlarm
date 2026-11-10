"""Original typed digest retained solely for independent streaming-equivalence QA."""
from pathlib import Path
from decimal import Decimal as D
import hashlib,json
def structural_digest_reference(value):
    """Typed, order-preserving dictionaries. Handles runtime Timestamp/tuple keys and caches."""
    import dataclasses,datetime,math
    import pandas as pd
    import numpy as np
    def tree(x):
        if isinstance(x,pd.DataFrame):
            return ["DataFrame",list(map(str,x.dtypes)),tree(x.to_dict(orient="split"))]
        if isinstance(x,pd.Series):return ["Series",str(x.dtype),tree(x.to_dict())]
        if isinstance(x,pd.Index):return ["Index",str(x.dtype),tree(x.tolist())]
        if isinstance(x,dict):return ["dict",[[tree(k),tree(v)] for k,v in x.items()]]
        if isinstance(x,list):return ["list",[tree(v) for v in x]]
        if isinstance(x,tuple):return ["tuple",[tree(v) for v in x]]
        if isinstance(x,(set,frozenset)):
            return ["set",sorted((tree(v) for v in x),key=lambda z:json.dumps(z,sort_keys=True))]
        if dataclasses.is_dataclass(x):return [type(x).__module__+"."+type(x).__name__,tree(dataclasses.asdict(x))]
        if x is pd.NA:return ["pd.NA"]
        if isinstance(x,D):return ["Decimal",str(x)]
        if isinstance(x,(datetime.datetime,datetime.date)):return [type(x).__name__,x.isoformat()]
        if isinstance(x,np.generic):return [str(x.dtype),tree(x.item())]
        if isinstance(x,np.ndarray):return ["ndarray",str(x.dtype),tree(x.tolist())]
        if isinstance(x,float) and not math.isfinite(x):return ["float",str(x)]
        if isinstance(x,(str,int,float,bool)) or x is None:return x
        if isinstance(x,Path):return ["Path",str(x)]
        raise TypeError("Unsupported structural value "+str(type(x)))
    return hashlib.sha256(json.dumps(tree(value),ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

