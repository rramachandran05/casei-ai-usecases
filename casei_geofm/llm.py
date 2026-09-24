"""LLM harness: schema-constrained Anthropic calls with disk caching.

Cache key: (stage, input_uuid, prompt_version) — bumping a prompt's version
invalidates its cache. A cache hit makes no API call. Every response is
validated against the stage's pydantic model; one retry with the validation
error appended, then hard failure.

Backends (CASEI_GEOFM_BACKEND env var):
  api        — Anthropic SDK; needs ANTHROPIC_API_KEY.
  claude_cli — headless `claude -p` (Claude Code CLI); uses the user's
               existing Claude login, no API key or separate billing.
  auto       — (default) api when ANTHROPIC_API_KEY is set, else claude_cli.
"""

import json
import os
import shutil
import subprocess
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
    """Tolerate code fences and prose around the JSON object."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        text = text.removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # fall back to decoding from the first '{' (prose before/after JSON)
        start = text.find("{")
        if start == -1:
            raise
        obj, _ = json.JSONDecoder().raw_decode(text[start:])
        return obj


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


CLAUDE_BIN = os.environ.get("CASEI_GEOFM_CLAUDE_BIN", "claude")


def _call_claude_cli(system: str, user: str, model: str) -> str:
    """Headless Claude Code CLI call (`claude -p`). Prompt goes via stdin to
    avoid argv length limits; text generation only, no tools."""
    cmd = [CLAUDE_BIN, "-p", "--output-format", "text", "--system-prompt", system]
    if model:
        cmd += ["--model", model]
    result = subprocess.run(cmd, input=user, capture_output=True, text=True, timeout=600)
    out = result.stdout.strip()
    if result.returncode != 0 or not out or "Not logged in" in out:
        raise RuntimeError(
            f"claude CLI call failed (rc={result.returncode}): "
            f"{(out or result.stderr.strip())[:300]}")
    return out


def pick_backend():
    """Resolve the callable for the configured backend."""
    choice = os.environ.get("CASEI_GEOFM_BACKEND", "auto")
    if choice == "api":
        return _call_api
    if choice == "claude_cli":
        return _call_claude_cli
    if choice == "auto":
        if os.environ.get("ANTHROPIC_API_KEY"):
            return _call_api
        if shutil.which(CLAUDE_BIN):
            return _call_claude_cli
        raise RuntimeError(
            "no LLM backend available: set ANTHROPIC_API_KEY (api) or install "
            "and log in the Claude Code CLI (claude_cli)")
    raise ValueError(f"unknown CASEI_GEOFM_BACKEND={choice!r}")


def call_stage(stage: str, input_uuid: str, input_payload: dict,
               response_model: type[BaseModel], prompt_version: str = "v1",
               model: str = DEFAULT_MODEL, cache_dir: Path | None = None,
               api=None) -> BaseModel:
    if api is None:
        api = pick_backend()
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
                    + f"\n\nYour previous response failed validation:\n{e}\n"
                    "Return corrected, strictly valid JSON only — escape any "
                    "double quotes inside string values.")
    raise RuntimeError(f"LLM stage '{stage}' failed validation twice for {input_uuid}") from last_error
