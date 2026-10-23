import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

import strot
from strot.exceptions import CompilationError, RouterConfigurationError
from test_compiler import REGISTRY, SAMPLE, VALID_PATHS


@pytest.fixture
def sdk(monkeypatch):
    class CodexError(Exception):
        pass

    result = SimpleNamespace(status=SimpleNamespace(value="completed"), final_response=VALID_PATHS)
    client = MagicMock()
    client.__enter__.return_value = client
    client.thread_start.return_value.run.return_value = result
    factory = Mock(return_value=client)
    monkeypatch.setitem(sys.modules, "openai_codex", SimpleNamespace(
        Codex=factory, CodexConfig=SimpleNamespace, CodexError=CodexError,
        Sandbox=SimpleNamespace(read_only="read-only"), ApprovalMode=SimpleNamespace(deny_all="deny-all"),
    ))
    return client, factory, result, CodexError


@pytest.mark.parametrize("model", [None, "gpt-6-luna"])
def test_sdk_repairs_and_reuses_cached_code(sdk, monkeypatch, tmp_path, model):
    client, factory, result, _ = sdk
    client.thread_start.return_value.run.side_effect = [
        SimpleNamespace(status=result.status, final_response="not valid code"), result,
    ]
    spec = "codex-sdk" + ("/" + model if model else "")
    first = strot.run(SAMPLE, "triage", REGISTRY, llm=spec, state=tmp_path, execute=False)
    assert first.attempts == 2 and not first.cache_hit
    assert factory.call_count == client.__exit__.call_count == 2
    for call in factory.call_args_list:
        config = call.args[0]
        assert config.codex_bin is None
        assert config.experimental_api is False
        assert config.config_overrides == ("project_doc_max_bytes=0", "features.shell_tool=false",
                                           'web_search="disabled"')
        assert not Path(config.cwd).exists() and Path(config.cwd) != Path.cwd()
    for call in client.thread_start.call_args_list:
        assert call.kwargs == dict(model=model, model_provider="openai", cwd=call.kwargs["cwd"],
                                   ephemeral=True, developer_instructions="",
                                   sandbox="read-only", approval_mode="deny-all")
    assert "PREVIOUS ATTEMPT" in client.thread_start.return_value.run.call_args.args[0]
    monkeypatch.setitem(sys.modules, "openai_codex", None)
    assert strot.run(SAMPLE, "triage", REGISTRY, llm=spec, state=tmp_path, execute=False).cache_hit


def test_missing_sdk_names_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai_codex", None)
    with pytest.raises(RouterConfigurationError, match=r"strot-ai\[codex-sdk\]"):
        strot.codex_sdk_llm_client()


@pytest.mark.parametrize("installed", [False, True])
def test_runtime_accepts_sdk_configuration(monkeypatch, tmp_path, installed):
    sdk = pytest.importorskip("openai_codex")
    from codex_cli_bin import bundled_codex_path

    codex_bin = str(bundled_codex_path()) if installed else None
    config_type = sdk.CodexConfig

    def isolated_config(**kwargs):
        return config_type(**kwargs, env={
            "CODEX_HOME": str(tmp_path), "OPENAI_API_KEY": "offline-sdk-key",
            "CODEX_API_KEY": "", "CODEX_ACCESS_TOKEN": "",
            "OPENAI_BASE_URL": "http://127.0.0.1:9/v1",
        })

    monkeypatch.setattr(sdk, "CodexConfig", isolated_config)
    monkeypatch.setattr("openai_codex.client.CodexClient._start_turn",
                        lambda *args, **kwargs: pytest.fail("Model calls are forbidden"))
    # Start the real runtime and thread, but replace generation before any model call.
    monkeypatch.setattr(sdk.Thread, "run", lambda _, prompt: SimpleNamespace(
        status=SimpleNamespace(value="completed"), final_response=prompt))
    assert strot.codex_sdk_llm_client("gpt-6-luna", cli=codex_bin)("compiled code") == "compiled code"


def test_sdk_passes_explicit_cli_to_runtime(sdk):
    _, factory, _, _ = sdk
    strot.codex_sdk_llm_client(cli="/custom/codex")("compile this")
    assert factory.call_args.args[0].codex_bin == "/custom/codex"


@pytest.mark.parametrize("failure", ["startup", "thread", "run", "encoding", "interrupted", "none", "empty"])
def test_sdk_failures_close_resources(sdk, failure):
    client, factory, result, error = sdk
    if failure == "startup":
        factory.side_effect = OSError("runtime missing")
    elif failure == "thread":
        client.thread_start.side_effect = error("login required")
    elif failure == "run":
        client.thread_start.return_value.run.side_effect = RuntimeError("turn failed")
    elif failure == "encoding":
        client.thread_start.return_value.run.side_effect = UnicodeDecodeError(
            "utf-8", b"\xff", 0, 1, "invalid byte")
    elif failure == "interrupted":
        result.status.value = "interrupted"
    else:
        result.final_response = None if failure == "none" else " \n"
    with pytest.raises(error if failure == "thread" else CompilationError):
        strot.codex_sdk_llm_client()("compile this")
    if failure != "startup":
        client.__exit__.assert_called_once()
    for call in factory.call_args_list:
        assert not Path(call.args[0].cwd).exists()


@pytest.mark.parametrize("entry", ["run", "decide"])
@pytest.mark.parametrize("stage", ["startup", "thread", "run"])
@pytest.mark.parametrize("error_type,args", [
    ("ServerBusyError", (-32001, "server busy", {"retry_after": 1})),
    ("TransportClosedError", ("connection closed",)),
])
def test_sdk_typed_errors_reach_callers_unchanged(monkeypatch, tmp_path, entry, stage, error_type, args):
    sdk = pytest.importorskip("openai_codex")
    error = getattr(sdk, error_type)(*args)
    client = MagicMock()
    client.__enter__.return_value = client
    factory = Mock(return_value=client)
    target = {"startup": factory, "thread": client.thread_start,
              "run": client.thread_start.return_value.run}[stage]
    target.side_effect = error
    monkeypatch.setattr(sdk, "Codex", factory)
    llm = strot.codex_sdk_llm_client(cli=sys.executable)
    args = (SAMPLE, "triage", REGISTRY) if entry == "run" else (
        SAMPLE, {"is_bug": {"type": "boolean", "instructions": "Does this mention crashes?"}})
    with pytest.raises(type(error)) as caught:
        getattr(strot, entry)(*args, llm=llm, state=tmp_path, execute=False)
    assert caught.value is error
    factory.assert_called_once()
    assert not Path(factory.call_args.args[0].cwd).exists()
    if stage != "startup":
        client.__exit__.assert_called_once()


@pytest.mark.parametrize("base", [OSError, RuntimeError, UnicodeError])
def test_sdk_error_subclasses_are_never_wrapped(sdk, base):
    class Error(sdk[3], base):
        pass
    error = Error("SDK failure")
    sdk[1].side_effect = error
    with pytest.raises(Error) as caught:
        strot.codex_sdk_llm_client()("compile")
    assert caught.value is error
