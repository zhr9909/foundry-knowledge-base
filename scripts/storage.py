#!/usr/bin/env python3
"""Storage abstraction for uploaded engineering documents.

The first implementation writes objects to local disk while keeping a
bucket/object_key contract so a MinIO/S3 backend can replace it later.
"""
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUCKET = os.environ.get("STORAGE_BUCKET", "foundry-kb")
LOCAL_STORAGE_ROOT = Path(os.environ.get("LOCAL_STORAGE_ROOT", PROJECT_ROOT / "storage" / "objects")).resolve()


def safe_name(value, fallback="file"):
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "_", str(value or fallback)).strip(" ._")
    return (name or fallback)[:120]


def object_hash(data):
    return hashlib.sha256(data).hexdigest()


def build_object_key(project_id, filename, content_hash, prefix="engineering_cases/original"):
    today = datetime.now().strftime("%Y/%m/%d")
    digest = content_hash[:16]
    return f"projects/{int(project_id)}/{prefix}/{today}/{digest}-{safe_name(filename)}"


class LocalObjectStore:
    def __init__(self, root=LOCAL_STORAGE_ROOT, bucket=DEFAULT_BUCKET):
        self.root = Path(root).resolve()
        self.bucket = bucket

    def _path_for(self, object_key):
        target = (self.root / object_key).resolve()
        if not str(target).startswith(str(self.root)):
            raise ValueError("invalid object key")
        return target

    def put_bytes(self, object_key, data):
        target = self._path_for(object_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return {
            "storage_backend": "local",
            "bucket": self.bucket,
            "object_key": object_key,
            "local_path": str(target),
            "size": len(data),
        }

    def read_bytes(self, object_key):
        return self._path_for(object_key).read_bytes()


def get_object_store():
    return LocalObjectStore()
