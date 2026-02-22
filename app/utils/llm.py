"""LLM integration for natural language video editing."""

import json
import logging
import os
from typing import Any

import openai

logger = logging.getLogger(__name__)

EDIT_SYSTEM_PROMPT = """You are a video editing assistant. Given a natural language description of video edits, return a JSON object with an "operations" array. Each operation must have a "type" and its parameters.

Supported operations:
- {"type": "trim_start", "seconds": <number>} — Remove the first N seconds
- {"type": "trim_end", "seconds": <number>} — Remove the last N seconds
- {"type": "speed", "factor": <number>} — Change playback speed (e.g. 1.5 = 50% faster)
- {"type": "fade_out", "seconds": <number>} — Add a fade-out effect for the last N seconds

Return ONLY valid JSON, no markdown fences, no explanation. Example:
{"operations": [{"type": "trim_start", "seconds": 10}, {"type": "speed", "factor": 1.5}]}"""

VALID_OPERATION_TYPES = {"trim_start", "trim_end", "speed", "fade_out"}

REQUIRED_PARAMS: dict[str, list[str]] = {
    "trim_start": ["seconds"],
    "trim_end": ["seconds"],
    "speed": ["factor"],
    "fade_out": ["seconds"],
}


def _validate_operation(op: dict[str, Any]) -> bool:
    """Validate a single editing operation."""
    op_type = op.get("type")
    if op_type not in VALID_OPERATION_TYPES:
        return False
    for param in REQUIRED_PARAMS.get(op_type, []):
        if param not in op:
            return False
        if not isinstance(op[param], (int, float)):
            return False
        if op[param] <= 0:
            return False
    return True


async def parse_edit_instructions(edit_text: str) -> dict[str, Any]:
    """
    Send natural language edit instructions to an LLM and parse structured JSON operations.

    Args:
        edit_text: Natural language description of desired video edits.

    Returns:
        Dict with an "operations" list of validated editing operations.

    Raises:
        ValueError: If the LLM response cannot be parsed or contains no valid operations.
        openai.OpenAIError: If the API call fails.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    client = openai.AsyncOpenAI(api_key=api_key)

    logger.info("Sending edit instructions to LLM: %s", edit_text[:100])

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": EDIT_SYSTEM_PROMPT},
            {"role": "user", "content": edit_text},
        ],
        temperature=0.0,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    logger.debug("LLM raw response: %s", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}") from e

    operations = result.get("operations", [])
    validated: list[dict[str, Any]] = []
    for op in operations:
        if _validate_operation(op):
            validated.append(op)
        else:
            logger.warning("Skipping invalid operation: %s", op)

    if not validated:
        raise ValueError("LLM returned no valid editing operations")

    logger.info("Parsed %d valid operations from LLM response", len(validated))
    return {"operations": validated}
