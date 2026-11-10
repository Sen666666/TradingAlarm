"""Validation-only Parquet schema preservation; no market/model calculation.

Pandas 3 may infer string dtype when Parquet reads an object column containing
date strings.  This sidecar restores only that declared object representation
and its null sentinels.  All other dtype changes are rejected.  Float columns
are neither cast nor rounded.  Callers still assert all values/dtypes exactly.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def _schema_path(path):
    return Path(str(path) + ".schema.json")


def write_frame(frame, path):
    """Exclusively write Parquet and a column-schema sidecar; return sidecar path."""
    path = Path(path)
    sidecar = _schema_path(path)
    if path.exists() or sidecar.exists():
        raise FileExistsError(f"Refusing to replace serialized evidence: {path}")
    if not frame.columns.is_unique or not all(isinstance(c, str) for c in frame.columns):
        raise ValueError("Unique string columns required")
    schema = {"version": 1, "columns": list(frame.columns), "rows": len(frame),
              "dtypes": {c: str(frame[c].dtype) for c in frame}, "object_nulls": {},
              "restoration": "Declared object dtype and exact object-null kinds only; no float conversion"}
    for column in frame:
        if frame[column].dtype != object:
            continue
        nulls = {"none": [], "pandas_na": [], "pandas_nat": [], "nan": []}
        for n, value in enumerate(frame[column]):
            if value is None:
                nulls["none"].append(n)
            elif value is pd.NA:
                nulls["pandas_na"].append(n)
            elif value is pd.NaT:
                nulls["pandas_nat"].append(n)
            elif isinstance(value, (float, np.floating)) and math.isnan(value):
                nulls["nan"].append(n)
        schema["object_nulls"][column] = nulls
    with path.open("xb") as handle:
        frame.to_parquet(handle)
    with sidecar.open("x") as handle:
        json.dump(schema, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    return sidecar


def read_frame(path):
    """Reload using only Parquet+sidecar; no original frame or model is needed."""
    path = Path(path)
    schema = json.loads(_schema_path(path).read_text())
    if schema["version"] != 1:
        raise ValueError("Unsupported serialized schema")
    frame = pd.read_parquet(path)
    if list(frame.columns) != schema["columns"] or len(frame) != schema["rows"]:
        raise ValueError("Serialized frame shape/order does not match sidecar")
    for column, dtype in schema["dtypes"].items():
        if str(frame[column].dtype) == dtype:
            continue
        if dtype != "object" or column not in schema["object_nulls"]:
            raise TypeError(f"Unexpected dtype change in {column}: {frame[column].dtype} != {dtype}")
        # This operation touches declared object columns only.  It does not
        # recompute any number or cast any float/int evidence column.
        frame[column] = frame[column].astype(object)
    values = {"none": None, "pandas_na": pd.NA, "pandas_nat": pd.NaT, "nan": np.nan}
    for column, nulls in schema["object_nulls"].items():
        declared = {position for positions in nulls.values() for position in positions}
        if sum(len(positions) for positions in nulls.values()) != len(declared):
            raise ValueError(f"Duplicate object-null positions in sidecar: {column}")
        actual = set(np.flatnonzero(frame[column].isna().to_numpy()).tolist())
        if actual != declared:
            raise ValueError(f"Serialized object-null mask changed: {column}")
        for kind, positions in nulls.items():
            for position in positions:
                if not pd.isna(frame.iloc[position][column]):
                    raise ValueError(f"Serialized object null changed to a value: {column}[{position}]")
                frame.iat[position, frame.columns.get_loc(column)] = values[kind]
    return frame
