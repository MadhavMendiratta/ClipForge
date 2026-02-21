"""LLM integration for natural language video editing."""

import json
import logging
import os
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

EDIT_SYSTEM_PROMPT = """You are a video editing assistant. Given a natural language description of video edits, return a JSON object with an "operations" array. Each operation must have a "type" and its parameters.

Supported operations:
- {"type": "trim_start", "seconds": <number>}
- {"type": "trim_end", "seconds": <number>}
- {"type": "speed", "factor": <number>}
- {"type": "fade_out", "seconds": <number>}

Return ONLY valid JSON. No markdown. No explanation.

Example:
{"operations": [{"type": "trim_start", "seconds": 10}, {"type": "speed", "factor": 1.5}]}
"""

VALID_OPERATION_TYPES = {"trim_start", "trim_end", "speed", "fade_out"}

REQUIRED_PARAMS: dict[str, list[str]] = {
    "trim_start": ["seconds"],
    "trim_end": ["seconds"],
    "speed": ["factor"],
    "fade_out": ["seconds"],
}


def _validate_operation(op: dict[str, Any]) -> bool:
    op_type = op.get("type")

    if op_type not in VALID_OPERATION_TYPES:
        return False

    for param in REQUIRED_PARAMS[op_type]:
        if param not in op:
            return False
        if not isinstance(op[param], (int, float)):
            return False
        if op[param] <= 0:
            return False

    # Reject unknown extra parameters
    allowed_keys = {"type"} | set(REQUIRED_PARAMS[op_type])
    if set(op.keys()) - allowed_keys:
        return False

    return True


async def parse_edit_instructions(edit_text: str) -> dict[str, Any]:

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    client = AsyncOpenAI(api_key=api_key)

    logger.info("Sending edit instructions to LLM")

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EDIT_SYSTEM_PROMPT},
            {"role": "user", "content": edit_text},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )

    if not response.choices:
        raise ValueError("Empty response from LLM")

    message = response.choices[0].message
    if not message or not message.content:
        raise ValueError("LLM returned empty content")

    raw = message.content

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON from LLM: {e}") from e

    operations = result.get("operations")
    if not isinstance(operations, list):
        raise ValueError("LLM response missing 'operations' array")

    validated: list[dict[str, Any]] = []

    for op in operations:
        if isinstance(op, dict) and _validate_operation(op):
            validated.append(op)
        else:
            logger.warning("Invalid operation skipped: %s", op)

    if not validated:
        raise ValueError("No valid editing operations returned")

    logger.info("Validated %d operations", len(validated))

    return {"operations": validated}