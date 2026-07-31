"""Helpers for parsing JSON objects returned by text models."""

from __future__ import annotations

import json
import re
from typing import Any

import yaml


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()
    match = re.fullmatch(r"```(?:json|yaml|yml)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    cleaned = re.sub(r"^```(?:json|yaml|yml)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _object_slice(text: str) -> str | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    return text[start : end + 1]


def _looks_like_truncated_fence(candidate: str) -> bool:
    return candidate.count("```") % 2 == 1


def _parse_json_or_yaml_object(candidate: str) -> dict[str, Any]:
    if _looks_like_truncated_fence(candidate):
        raise ValueError("model response appears truncated inside a markdown code fence")
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        data = yaml.safe_load(candidate)
    if not isinstance(data, dict):
        raise ValueError("model response must be a JSON object")
    return data


def parse_model_json_object(text: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(str(text or ""))
    candidates = [cleaned]
    sliced = _object_slice(cleaned)
    if sliced and sliced != cleaned:
        candidates.append(sliced)

    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate.strip():
            continue
        try:
            return _parse_json_or_yaml_object(candidate)
        except (json.JSONDecodeError, yaml.YAMLError, ValueError) as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise ValueError("model response is empty")


def parse_model_json_array(text: str) -> list[Any]:
    cleaned = _strip_code_fence(str(text or ""))
    candidates = [cleaned]
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start >= 0 and end > start:
        sliced = cleaned[start : end + 1]
        if sliced != cleaned:
            candidates.append(sliced)

    last_error: Exception | None = None
    for candidate in candidates:
        if not candidate.strip():
            continue
        try:
            try:
                data = json.loads(candidate)
            except json.JSONDecodeError:
                data = yaml.safe_load(candidate)
            if not isinstance(data, list):
                raise ValueError("model response must be a JSON array")
            return data
        except (json.JSONDecodeError, yaml.YAMLError, ValueError) as exc:
            last_error = exc

    if last_error is not None:
        raise last_error
    raise ValueError("model response is empty")
