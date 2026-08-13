"""Reproducibility metadata emitted by the native harness."""

import hashlib
import importlib.metadata
import ipaddress
import json
import os
import platform
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .profile import execution_profile_metadata, profile_path

HARNESS_VERSION = "asyncodebench-harness-v2.0"
SENSITIVE_CONFIGURATION_KEYS = {
    "access_token",
    "api_key",
    "apikey",
    "authorization",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
}


def _git_revision(path):
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _sha256(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def _nvidia_hardware():
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=index,name,memory.total,driver_version",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    rows = []
    for line in output.splitlines():
        fields = [field.strip() for field in line.split(",")]
        if len(fields) == 4:
            rows.append(
                {
                    "index": fields[0],
                    "name": fields[1],
                    "memory_total_mib": fields[2],
                    "driver_version": fields[3],
                }
            )
    return rows


def _read_json_url(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return json.loads(response.read().decode("utf-8")), None
    except (
        OSError,
        urllib.error.URLError,
        json.JSONDecodeError,
    ) as exc:
        return None, str(exc)


def _redact_secrets(value):
    if isinstance(value, dict):
        redacted = {}
        for key, child in value.items():
            normalized_key = str(key).lower().replace("-", "_")
            redacted[key] = (
                "[REDACTED]"
                if normalized_key in SENSITIVE_CONFIGURATION_KEYS
                else _redact_secrets(child)
            )
        return redacted
    if isinstance(value, list):
        return [_redact_secrets(item) for item in value]
    return value


def _vllm_server_metadata():
    base_url = str(os.getenv("LLM_BASE_URL", "")).rstrip("/")
    if not base_url:
        return {"configured": False}
    parsed = urlsplit(base_url)
    hostname = parsed.hostname or ""
    try:
        local_address = ipaddress.ip_address(hostname).is_private
    except ValueError:
        local_address = hostname in {"localhost", "host.docker.internal"}
    explicit_vllm = os.getenv("ASYNCODEBENCH_MODEL_SERVER_KIND") == "vllm"
    safe_netloc = hostname
    if parsed.port:
        safe_netloc += f":{parsed.port}"
    safe_base_url = urlunsplit(
        (parsed.scheme, safe_netloc, parsed.path.rstrip("/"), "", "")
    )
    if not (local_address or explicit_vllm):
        return {
            "configured": True,
            "kind": os.getenv("ASYNCODEBENCH_MODEL_SERVER_KIND", "external_api"),
            "base_url": safe_base_url,
            "probed": False,
        }

    api_root = safe_base_url[:-3] if safe_base_url.endswith("/v1") else safe_base_url
    version, version_error = _read_json_url(f"{api_root}/version")
    models, models_error = _read_json_url(f"{safe_base_url}/models")
    model_records = (models or {}).get("data", []) if isinstance(models, dict) else []
    return {
        "configured": True,
        "kind": "vllm",
        "base_url": safe_base_url,
        "probed": True,
        "reachable": version is not None or models is not None,
        "version": version,
        "models": model_records,
        "input_context_limit": next(
            (
                record.get("max_model_len")
                for record in model_records
                if record.get("max_model_len") is not None
            ),
            None,
        ),
        "version_error": version_error,
        "models_error": models_error,
    }


def _generation_configuration():
    scalar_names = (
        "LLM_MAX_OUTPUT_TOKENS",
        "LLM_MAX_INPUT_TOKENS",
        "LLM_CONTEXT_WINDOW",
        "LLM_TEMPERATURE",
        "LLM_TOP_P",
        "LLM_TOP_K",
        "LLM_TIMEOUT",
        "LLM_NUM_RETRIES",
        "ASYNCODEBENCH_CONDENSER_MAX_TOKENS",
    )
    configuration = {
        "schema_version": "asyncodebench-generation-configuration-v1",
        "parameters": {
            name: {
                "value": os.getenv(name),
                "source": (
                    "environment"
                    if os.getenv(name) is not None
                    else "sdk_or_provider_default"
                ),
            }
            for name in scalar_names
        },
    }
    for name in scalar_names:
        if os.getenv(name) is not None:
            configuration[name] = os.getenv(name)
    for name in ("LLM_EXTRA_BODY_JSON", "ASYNCODEBENCH_VLLM_CONFIG_JSON"):
        raw_value = os.getenv(name)
        if raw_value is None:
            configuration["parameters"][name] = {
                "value": None,
                "source": "not_configured",
            }
            continue
        try:
            parsed_value = json.loads(raw_value)
        except json.JSONDecodeError:
            parsed_value = {"parse_error": "invalid JSON; value omitted"}
        parsed_value = _redact_secrets(parsed_value)
        configuration[name] = parsed_value
        configuration["parameters"][name] = {
            "value": parsed_value,
            "source": "environment",
        }

    template_path = os.getenv("ASYNCODEBENCH_CHAT_TEMPLATE_PATH")
    if template_path:
        configuration["chat_template"] = {
            "path": template_path,
            "sha256": _sha256(template_path),
        }
    else:
        configuration["chat_template"] = {
            "path": None,
            "sha256": None,
            "source": "model_server_default",
        }
    return configuration


def build_run_metadata(
    task,
    workflow_config,
    protocol,
    prompt_path,
    agent_adapter=None,
):
    repo_root = task._repo_root()
    runner_root = Path(__file__).resolve().parents[2]
    package_versions = {}
    for package in ("openhands-sdk", "openhands-workspace", "litellm", "fire"):
        try:
            package_versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            package_versions[package] = None

    safe_environment = {
        name: os.getenv(name)
        for name in (
            "LLM_MAX_OUTPUT_TOKENS",
            "LLM_TEMPERATURE",
            "LLM_TOP_P",
            "LLM_TOP_K",
            "ASYNCODEBENCH_WORKSPACE_DOCKER_NETWORK",
            "ASYNCODEBENCH_WORKSPACE_HOST_PORT",
            "ASYNCODEBENCH_PROBE_TIMEOUT_SECONDS",
            "ASYNCODEBENCH_FINAL_PYTEST_TIMEOUT_SECONDS",
        )
        if os.getenv(name) is not None
    }
    return {
        "schema_version": "0.1",
        "harness_version": HARNESS_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "task_id": task.task_id,
        "source_task_id": task.source_task_id,
        "release": task.asyncodebench_config.release,
        "protocol": protocol,
        "scenario_id": task.public_scenario_id(protocol),
        "source_scenario_id": task.scenario_for(protocol).get("scenario_id"),
        "model": workflow_config.model,
        # The runner falls back to the manager LLM when no separate subagent
        # model is configured. Record the effective model, not the nullable
        # user input, so campaign lineage remains unambiguous.
        "subagent_model": workflow_config.subagent_model or workflow_config.model,
        "agent_adapter": agent_adapter
        or {
            "name": "openhands",
            "class": "agents.openhands:OpenHandsAgentAdapter",
        },
        "budgets": {
            "manager_max_iterations": workflow_config.manager_max_iterations,
            "max_subagents": workflow_config.max_subagents,
            "subagent_max_iterations": workflow_config.subagent_max_iterations,
            "max_rounds_chat": workflow_config.max_rounds_chat,
        },
        "execution_profile": execution_profile_metadata(
            task, workflow_config, protocol
        ),
        "source": {
            "repository": task.curated_task.get("repository"),
            "base_ref": task.curated_task.get("base_ref"),
            "base_sha": task.curated_task.get("base_sha"),
            "overlays": task.curated_task.get("overlays", []),
        },
        "artifacts": {
            name: {"path": str(path), "sha256": _sha256(path)}
            for name, path in task.manifest_paths.items()
        },
        "prompt": {"path": str(prompt_path), "sha256": _sha256(prompt_path)},
        "code_revisions": {
            "asyncodebench": _git_revision(repo_root),
            "async_swe_agents": _git_revision(runner_root),
            "software_agent_sdk": _git_revision(
                repo_root / "reproductions" / "software-agent-sdk"
            ),
        },
        "software": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": package_versions,
        },
        "hardware": {"gpus": _nvidia_hardware()},
        "model_server": _vllm_server_metadata(),
        "generation_configuration": _generation_configuration(),
        "environment": safe_environment,
    }


def write_run_metadata(output_dir, metadata):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "run_metadata.json"
    path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def write_contract_snapshots(output_dir, task, protocol):
    output_dir = Path(output_dir)
    snapshot_sources = {
        "task_snapshot.json": task.manifest_paths["task"],
        "scenario_manifest_snapshot.json": task.manifest_paths["scenario"],
        "metrics_snapshot.json": task.manifest_paths["metrics"],
        "quality_snapshot.json": task.manifest_paths["quality"],
        "execution_profile_snapshot.json": profile_path(),
    }
    written = {}
    for filename, source_path in snapshot_sources.items():
        path = output_dir / filename
        path.write_bytes(Path(source_path).read_bytes())
        written[filename] = str(path)

    active_scenario_path = output_dir / "scenario_snapshot.json"
    active_scenario_path.write_text(
        json.dumps(task.scenario_for(protocol), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written["scenario_snapshot.json"] = str(active_scenario_path)

    scenario = task.scenario_for(protocol)
    protocol_path = output_dir / "protocol.json"
    protocol_payload = {
        "schema_version": "0.1",
        "harness": HARNESS_VERSION,
        "task_id": task.task_id,
        "source_task_id": task.source_task_id,
        "protocol": protocol,
        "scenario_id": task.public_scenario_id(protocol),
        "source_scenario_id": scenario.get("scenario_id"),
        "execution_mode": scenario.get("execution_mode"),
        "information_profile": scenario.get("information_profile"),
        "communication_condition": scenario.get("communication_condition"),
        "message_delivery_policy": scenario.get("message_delivery_policy"),
        "integration_policy": scenario.get("integration_policy"),
        "scope_policy": (
            "reject_artifact_before_merge"
            if protocol != "single"
            else "full_task_workspace"
        ),
    }
    protocol_path.write_text(
        json.dumps(protocol_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    written["protocol.json"] = str(protocol_path)
    return written
