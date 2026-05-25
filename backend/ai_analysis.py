from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"


def load_local_env() -> None:
    for path in (Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"):
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def deepseek_config() -> dict[str, Any]:
    load_local_env()
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    return {
        "provider": "deepseek",
        "configured": bool(api_key),
        "model": os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL).strip() or DEFAULT_DEEPSEEK_MODEL,
        "url": os.getenv("DEEPSEEK_API_URL", DEFAULT_DEEPSEEK_URL).strip() or DEFAULT_DEEPSEEK_URL,
    }


def finite_last(values: Any) -> float | None:
    if not isinstance(values, list) or not values:
        return None
    for value in reversed(values):
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number == number and abs(number) != float("inf"):
            return number
    return None


def result_summary(result: dict[str, Any], params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    time = result.get("time") if isinstance(result.get("time"), list) else []
    warnings = result.get("warnings") or result.get("validation", {}).get("warnings") or []
    return {
        "projectId": context.get("projectId") or "default",
        "mode": result.get("mode"),
        "sourceName": result.get("sourceName"),
        "solverMethod": result.get("solverMethod") or params.get("solverMethod"),
        "engineVersion": result.get("engineVersion") or params.get("engineVersion"),
        "simulationDays": params.get("simulationDays"),
        "outputPoints": len(time),
        "startTimeDay": time[0] if time else None,
        "endTimeDay": time[-1] if time else None,
        "effluent": {
            "COD_gCOD_m3": finite_last(result.get("effCod")),
            "NH4N_gN_m3": finite_last(result.get("effNh4")),
            "NO3N_gN_m3": finite_last(result.get("effNo3")),
            "TN_gN_m3": finite_last(result.get("effTn")),
            "TSS_g_m3": finite_last(result.get("effTss")),
        },
        "process": {
            "anaerobicNO3_gN_m3": finite_last(result.get("anaerobicNo3")),
            "anoxicNO3_gN_m3": finite_last(result.get("anoxicNo3")),
            "aerobicNO3_gN_m3": finite_last(result.get("aerobicNo3")),
            "aerobicDO_gO2_m3": finite_last(result.get("aerobicDo")),
            "aerobicMLSS_g_m3": finite_last(result.get("aerobicMlss")),
            "rasMLSS_g_m3": finite_last(result.get("rasMlss")),
        },
        "controls": {
            "influentQ_m3_d": params.get("influentQ"),
            "influentCOD_gCOD_m3": params.get("influentCod"),
            "influentNH4_gN_m3": params.get("influentNh4"),
            "influentTSS_g_m3": params.get("influentTss"),
            "aerobicDOSet_gO2_m3": params.get("aerobicDo"),
            "rasRatio_percent": params.get("rasRatio"),
            "internalRecycleRatio_percent": params.get("internalRecycleRatio"),
            "wasQ_m3_d": params.get("wasQ"),
        },
        "warnings": warnings[:8] if isinstance(warnings, list) else [],
    }


def build_prompt(summary: dict[str, Any]) -> list[dict[str, str]]:
    system = (
        "你是污水处理 AAO/A2O 工艺仿真结果分析助手。"
        "请基于给定 JSON 输出工程化、谨慎的中文分析。"
        "不要编造未给出的传感器或法规限值；如果信息不足，要明确说明。"
    )
    user = (
        "请分析以下 ASM/AAO 仿真结果，输出四段：\n"
        "1. 结果概览；2. 主要风险或异常；3. 推荐调整；4. 后续验证建议。\n"
        "要求每段简洁，优先关注 NH4-N、TN、TSS、DO、MLSS、回流/排泥和模型告警。\n\n"
        f"仿真摘要 JSON:\n{json.dumps(summary, ensure_ascii=False, indent=2)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def call_deepseek(messages: list[dict[str, str]], config: dict[str, Any]) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured in the backend environment.")
    payload = {
        "model": config["model"],
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 900,
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        config["url"],
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API HTTP {exc.code}: {detail[:300]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"DeepSeek API connection failed: {exc.reason}") from exc

    choices = data.get("choices") or []
    content = choices[0].get("message", {}).get("content") if choices else ""
    if not content:
        raise RuntimeError("DeepSeek API returned an empty analysis.")
    return content.strip()


def analyze_result(result: dict[str, Any], params: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    config = deepseek_config()
    summary = result_summary(result, params, context)
    analysis = call_deepseek(build_prompt(summary), config)
    return {
        "provider": config["provider"],
        "model": config["model"],
        "configured": config["configured"],
        "summary": summary,
        "analysis": analysis,
    }
