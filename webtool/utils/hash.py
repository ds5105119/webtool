import hashlib
from typing import Union


def sha256(key: Union[bytes, str, memoryview]) -> bytes:
    if isinstance(key, str):
        key = key.encode("utf-8")
    elif isinstance(key, memoryview):
        key = key.tobytes()

    return hashlib.sha256(key).digest()
