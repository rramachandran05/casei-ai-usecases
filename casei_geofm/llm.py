"""LLM harness: schema-constrained Anthropic calls with disk caching.

Cache key: (stage, input_uuid, prompt_version) — bumping a prompt's version
invalidates its cache. A cache hit makes no API call. Every response is
validated against the stage's pydantic model; one retry with the validation
error appended, then hard failure.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv()

CACHE_DIR = Path("data/cache/llm")
PROMPTS_DIR = Path(__file__).parent / "prompts"
DEFAULT_MODEL = os.environ.get("CASEI_GEOFM_MODEL", "claude-sonnet-5")

GUARDRAIL_PREAMBLE = """\
Ground every statement in the metadata provided. If a fact is missing or the
input marks it UNKNOWN, keep it UNKNOWN — never infer or invent metadata values
(resolutions, dates, formats, geometry). Your semantic judgments (label types,
tasks, ratings, reasoning) are wanted; invented facts are not.
This assessment is a Level-1 metadata inference: describe usefulness as
potential ("appears", "could", "may provide") — never as confirmed or verified.
Respond with a single JSON object matching the requested schema, nothing else.
"""


def load_prompt(stage: str, version: str) -> str:
    return (PROMPTS_DIR / f"{stage}_{version}.md").read_text()


def _extract_json(text: str) -> dict:
    """Tolerate code fences around the JSON object."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.removeprefix("json").strip()
    return json.loads(text)


def _call_api(system: str, user: str, model: str) -> str:
    import anthropic  # deferred so mocked tests never need a key

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=model,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return msg.content[0].text


def call_stage(stage: str, input_uuid: str, input_payload: dict,
               response_model: type[BaseModel], prompt_version: str = "v1",
               model: str = DEFAULT_MODEL, cache_dir: Path | None = None,
               api=_call_api) -> BaseModel:
    cache_dir = Path(cache_dir or CACHE_DIR) / stage
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{input_uuid}-{prompt_version}.json"
    if cache_file.exists():
        return response_model.model_validate_json(cache_file.read_text())

    system = GUARDRAIL_PREAMBLE + "\n" + load_prompt(stage, prompt_version)
    user = json.dumps(input_payload, default=str)

    last_error: Exception | None = None
    for attempt in range(2):
        raw = api(system, user, model)
        try:
            parsed = response_model.model_validate(_extract_json(raw))
            cache_file.write_text(parsed.model_dump_json())
            return parsed
        except (ValidationError, json.JSONDecodeError) as e:
            last_error = e
            user = (json.dumps(input_payload, default=str)
                    + f"\n\nYour previous response failed validation:\n{e}\nReturn corrected JSON only.")
    raise RuntimeError(f"LLM stage '{stage}' failed validation twice for {input_uuid}") from last_error
