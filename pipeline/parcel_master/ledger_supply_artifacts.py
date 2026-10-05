"""Publish an artifact only after its complete contents have been written."""
import gzip
import json
import os
import tempfile
from pathlib import Path


def _write_atomic(path,writer):
    path=Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent,prefix=path.name+'.',suffix='.pending',delete=False) as file:
        pending=Path(file.name)
    try:
        writer(pending)
        os.replace(pending,path)
    finally:
        pending.unlink(missing_ok=True)


def write_gzip_atomic(path,payload):
    def write(pending):
        with gzip.open(pending,'wt',encoding='utf-8') as file:
            json.dump(payload,file,ensure_ascii=False,allow_nan=False)
    _write_atomic(path,write)


def write_json_atomic(path,payload):
    def write(pending):
        with pending.open('w',encoding='utf-8') as file:
            json.dump(payload,file,ensure_ascii=False,indent=2,allow_nan=False)
            file.write('\n')
    _write_atomic(path,write)
