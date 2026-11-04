"""Offline CLI integration tests: every invocation runs a temporary fake codex."""
import asyncio
import json
import os
from pathlib import Path
import sys

import pytest

from app.services.llm.codex_cli_provider import CodexCLIProvider


@pytest.fixture(autouse=True)
async def subprocess_wakeup():
    # The network-restricted sandbox can lose the child watcher's socketpair
    # wakeup. A timer keeps the test loop responsive to completed child futures.
    async def tick():
        while True:
            await asyncio.sleep(0.01)

    timer = asyncio.create_task(tick())
    yield
    timer.cancel()
    try:
        await timer
    except asyncio.CancelledError:
        pass


@pytest.fixture
def fake_codex(tmp_path, monkeypatch):
    record = tmp_path / "calls.jsonl"
    executable = tmp_path / "codex"
    executable.write_text(f"""#!{sys.executable}
import json, os, pathlib, sys, time
args = sys.argv[1:]
schema = pathlib.Path(args[args.index('--output-schema') + 1]).read_text() if '--output-schema' in args else None
with open(os.environ['FAKE_RECORD'], 'a') as f:
    f.write(json.dumps(dict(argv=args, stdin=sys.stdin.read(), cwd=os.getcwd(), schema=schema, started=time.monotonic())) + '\\n')
print('fake stderr diagnostic', file=sys.stderr, flush=True)
time.sleep(float(os.environ.get('FAKE_DELAY', '0')))
if os.environ.get('FAKE_EXIT'):
    sys.exit(int(os.environ['FAKE_EXIT']))
pathlib.Path(args[args.index('-o') + 1]).write_text(os.environ.get('FAKE_OUTPUT', 'hello'))
""")
    executable.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("FAKE_RECORD", str(record))
    return lambda: [json.loads(line) for line in record.read_text().splitlines()]


@pytest.mark.asyncio
async def test_complete_chat_and_interface(fake_codex):
    provider = CodexCLIProvider()
    prompt = "document " * 40000
    assert await provider.complete(prompt) == "hello"
    call = fake_codex()[0]
    assert call["stdin"] == prompt
    assert prompt not in call["argv"]
    assert call["argv"] == [
        "exec", "--skip-git-repo-check", "--ephemeral", "-s", "read-only",
        "-m", "gpt-6.1-sol", "-c", "model_reasoning_effort=medium",
        "-o", str(Path(call["cwd"]) / "out.txt"), "-",
    ]
    assert not Path(call["cwd"]).exists()
    assert await provider.chat([{"role": "system", "content": "rules"},
                                {"role": "user", "content": "question"}]) == "hello"
    assert fake_codex()[1]["stdin"] == "system: rules\n\nuser: question"
    assert await provider.test_connection() is True
    assert [m.id for m in await provider.list_models()] == ["gpt-6.1-sol"]


@pytest.mark.asyncio
@pytest.mark.parametrize("strict", [True, False])
async def test_structured_schema_selection(fake_codex, monkeypatch, strict):
    schema = {"type": "object", "properties": {
        "items": {"type": "array", "items": {"type": "object",
            "properties": {"name": {"type": "string"}}, "required": ["name"],
            "additionalProperties": False}}},
        "required": ["items"], "additionalProperties": False}
    if not strict:
        del schema["properties"]["items"]["items"]["additionalProperties"]
    monkeypatch.setenv("FAKE_OUTPUT", 'Here is JSON: {"items": []} trailing')
    provider = CodexCLIProvider(model="custom-model", effort="high")
    assert await provider.structured("extract", schema) == {"items": []}
    call = fake_codex()[0]
    assert ("--output-schema" in call["argv"]) is strict
    assert "custom-model" in call["argv"]
    assert "model_reasoning_effort=high" in call["argv"]
    if strict:
        assert json.loads(call["schema"]) == schema
    else:
        assert json.dumps(schema) in call["stdin"]
        assert "only JSON" in call["stdin"]
    assert not Path(call["cwd"]).exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["exit", "empty", "timeout"])
async def test_errors_and_cleanup(fake_codex, monkeypatch, mode):
    if mode == "exit":
        monkeypatch.setenv("FAKE_EXIT", "7")
    elif mode == "empty":
        monkeypatch.setenv("FAKE_OUTPUT", " ")
    else:
        monkeypatch.setenv("FAKE_DELAY", "5")
    provider = CodexCLIProvider(timeout=0.2 if mode == "timeout" else 5)
    with pytest.raises(RuntimeError, match="gpt-6.1-sol") as err:
        await provider.complete("test")
    assert "fake stderr diagnostic" in str(err.value)
    assert {"exit": "7", "empty": "empty", "timeout": "timed out"}[mode] in str(err.value)
    assert not Path(fake_codex()[0]["cwd"]).exists()
    if mode != "timeout":
        assert await provider.test_connection() is False


@pytest.mark.parametrize("name", ["codex-cli", "codex_cli"])
def test_web_registry_rejects_cli(name):
    from app.services.llm.registry import get_provider
    from app.models.llm_models import LLMProviderType
    with pytest.raises(ValueError):
        get_provider(name)
    with pytest.raises(ValueError):
        LLMProviderType(name)


def test_bake_factory_bypasses_app_settings(monkeypatch):
    from scripts.generate_demos import build_generation_llm
    from app.config import settings
    monkeypatch.setattr(settings, "llm_model", "gemini-model")
    provider = build_generation_llm("codex-cli", None, None, effort="low")
    assert isinstance(provider, CodexCLIProvider)
    assert provider.model == "gpt-6.1-sol"
    assert provider.effort == "low"


@pytest.mark.asyncio
async def test_bake_main_uses_cli_for_every_task(tmp_path, monkeypatch):
    from dataclasses import fields
    from unittest.mock import AsyncMock
    from scripts import generate_demos
    from app.pipeline.orchestrator import TaskLLMs
    from app.config import settings

    monkeypatch.setattr(sys, "argv", ["generate_demos.py", "--provider", "codex-cli",
                                     "--model", "custom-model", "--effort", "high"])
    monkeypatch.setattr(settings, "llm_concept_provider", "google")
    monkeypatch.setattr(generate_demos, "DEMOS_DIR", tmp_path)
    monkeypatch.setattr(generate_demos, "init_services", AsyncMock())
    monkeypatch.setattr(generate_demos, "_write_sidecars", lambda _: None)
    from scripts import demo_documents
    monkeypatch.setattr(demo_documents, "load_demo_documents",
                        lambda _: {"sample": {"text": "doc"}})
    generate = AsyncMock()
    monkeypatch.setattr(generate_demos, "generate_demo", generate)
    await generate_demos.main()
    args = generate.call_args.args
    provider, tasks = args[3:5]
    assert isinstance(provider, CodexCLIProvider)
    assert provider.model == "custom-model"
    assert provider.effort == "high"
    assert all(getattr(tasks, f.name) is provider for f in fields(TaskLLMs))
    assert generate.call_args.kwargs["provider_name"] == "codex-cli"


@pytest.mark.asyncio
async def test_demo_metadata_only(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from scripts import generate_demos, slim_demos
    from app.models.job import JobStatus
    from app.pipeline.orchestrator import TaskLLMs

    result = SimpleNamespace(annotations=[], individuals=[], properties=[], triples=[])
    job = SimpleNamespace(status=JobStatus.COMPLETED, result=result)
    monkeypatch.setattr(generate_demos, "PipelineOrchestrator",
                        lambda **_: SimpleNamespace(run=AsyncMock(return_value=job)))
    monkeypatch.setattr(generate_demos, "DEMOS_DIR", tmp_path / "demos")
    monkeypatch.setattr(generate_demos, "build_cache_payload", lambda *_: {"original": True})
    monkeypatch.setattr(slim_demos, "slim_demo_cache", lambda _: None)
    await generate_demos.generate_demo(
        "sample", {"text": "doc", "title": "Title", "description": "Description"},
        tmp_path / "jobs", CodexCLIProvider(), TaskLLMs(), provider_name="codex-cli",
    )
    payload = json.loads((tmp_path / "demos/sample.json").read_text())
    assert payload["demo"]["provider"] == "codex-cli"
    assert payload["demo"]["model"] == "gpt-6.1-sol"
    assert payload["cache"] == {"original": True}


@pytest.mark.asyncio
async def test_semaphore_shared_across_instances(fake_codex, monkeypatch):
    monkeypatch.setenv("FAKE_DELAY", "0.15")
    # Four separate instances still share the three-call process limit.
    results = await asyncio.gather(*(CodexCLIProvider().complete(str(i)) for i in range(4)))
    assert results == ["hello"] * 4
    calls = fake_codex()
    assert len({call["cwd"] for call in calls}) == 4
    assert all(not Path(call["cwd"]).exists() for call in calls)
    starts = sorted(call["started"] for call in calls)
    assert starts[3] - starts[0] >= 0.15
