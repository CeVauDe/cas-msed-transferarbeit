from __future__ import annotations

import json
import time
from uuid import uuid4


def _normalize_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _normalize_value(item)
            for key, item in value.items()
        }
    return str(value)


def log_event(event: str, request_id: str | None = None, **fields: object) -> str:
    resolved_request_id = request_id or str(uuid4())
    record = {
        "timestamp": int(time.time() * 1000),
        "event": event,
        "request_id": resolved_request_id,
        "trace_id": fields.pop("trace_id", None),
        "span_id": fields.pop("span_id", None),
    }
    for key, value in fields.items():
        record[key] = _normalize_value(value)
    print(json.dumps(record, ensure_ascii=False))
    return resolved_request_id
