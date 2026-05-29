from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
SUPPORTED_DEEPSEEK_MODELS = ("deepseek/deepseek-v4-pro", "deepseek/deepseek-v4-flash")
DEEPSEEK_MODEL_ALIASES = {
    "deepseek/deepseek-v4-pro": "deepseek-v4-pro",
    "deepseek/deepseek-v4-flash": "deepseek-v4-flash",
}


class EmptyDeepSeekAnalysis(RuntimeError):
    pass


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
        "models": list(SUPPORTED_DEEPSEEK_MODELS),
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
        "你是污水处理厂 AAO/A2O 工艺工程师，负责审阅 ASM 仿真结果。"
        "语言要像工程简报：直接、克制、可执行。避免营销话术、AI 自称、套话和 Markdown 标题。"
        "不要编造未给出的传感器、法规限值或现场结论；信息不足时写明需要补充的数据。"
        "不要输出思考过程、解释过程或对任务要求的复述。"
    )
    user = (
        "请只返回一个合法 JSON 对象，不要输出 Markdown，不要加代码块。结构如下：\n"
        "{\n"
        '  "headline": "一句话结论，30字以内",\n'
        '  "executiveSummary": ["2-4条结果概述，每条不超过45字"],\n'
        '  "riskItems": [{"level":"info|warning|critical","item":"风险名称","evidence":"数据依据","impact":"可能影响"}],\n'
        '  "recommendedActions": [{"priority":"high|medium|low","action":"调整动作","reason":"原因","expectedEffect":"预期效果"}],\n'
        '  "verificationPlan": ["2-4条复核或验证步骤"]\n'
        "}\n"
        "重点关注 NH4-N、TN、TSS、DO、MLSS、回流/排泥和模型告警。"
        "如果只能做参考判断，要写成“建议复核”而不是下定论。"
        "只输出 JSON，不要在 JSON 前后追加任何说明。\n\n"
        f"仿真摘要 JSON:\n{json.dumps(summary, ensure_ascii=False, indent=2)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_chat_messages(messages: list[dict[str, str]], context: dict[str, Any], summary: dict[str, Any] | None = None) -> list[dict[str, str]]:
    system = (
        "你是 AAO 工艺在线仿真平台的系统助手。"
        "你的任务是帮助用户理解系统功能、操作路径、实时仿真、模拟实验室、模型管理、数据清洗、校准和仿真结果。"
        "回答要直接、专业、简洁。不要编造系统不存在的功能；无法确定时说明需要补充信息。"
        "如果用户询问仿真结果，优先基于提供的 resultSummary 判断，并说明这是模型结果而不是现场结论。"
        "API Key、后端环境变量和本地敏感信息不可在回答中透露。"
    )
    platform_context = {
        "environment": context.get("environment"),
        "panel": context.get("panel"),
        "projectId": context.get("projectId"),
        "projectName": context.get("projectName"),
        "activeChart": context.get("activeChart"),
        "hasResult": bool(summary and summary.get("outputPoints")),
        "resultSummary": summary,
    }
    cleaned_messages: list[dict[str, str]] = []
    for message in messages[-12:]:
        role = message.get("role")
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        cleaned_messages.append({"role": role, "content": content[:3000]})
    return [
        {"role": "system", "content": system},
        {"role": "system", "content": f"当前系统上下文 JSON:\n{json.dumps(platform_context, ensure_ascii=False, indent=2)}"},
        *cleaned_messages,
    ]


def chat_with_deepseek(messages: list[dict[str, str]], params: dict[str, Any], result: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or {}
    config = deepseek_config()
    summary = result_summary(result, params, context) if result else None
    chat_messages = build_chat_messages(messages, context, summary)
    model_name = normalize_model_name("deepseek/deepseek-v4-pro", config)
    reply, model_used = call_deepseek(chat_messages, config, model_name)
    return {
        "provider": config["provider"],
        "model": model_used,
        "configured": config["configured"],
        "reply": reply,
        "summary": summary,
    }


def normalize_model_name(model: str | None, config: dict[str, Any]) -> str:
    requested = (model or "").strip()
    if not requested:
        configured = (config.get("model") or "").strip()
        if configured in DEEPSEEK_MODEL_ALIASES:
            return DEEPSEEK_MODEL_ALIASES[configured]
        if configured in DEEPSEEK_MODEL_ALIASES.values():
            return configured
        return DEEPSEEK_MODEL_ALIASES[SUPPORTED_DEEPSEEK_MODELS[1]]
    if requested not in SUPPORTED_DEEPSEEK_MODELS:
        raise RuntimeError(f"Unsupported DeepSeek model: {requested}")
    return DEEPSEEK_MODEL_ALIASES[requested]


def parse_analysis_report(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
        if text.startswith("json"):
            text = text[4:].strip()
    text = extract_first_json_object(text) or text
    try:
        report = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(report, dict):
        return None
    return {
        "headline": str(report.get("headline") or "仿真结果已生成"),
        "executiveSummary": report.get("executiveSummary") if isinstance(report.get("executiveSummary"), list) else [],
        "riskItems": report.get("riskItems") if isinstance(report.get("riskItems"), list) else [],
        "recommendedActions": report.get("recommendedActions") if isinstance(report.get("recommendedActions"), list) else [],
        "verificationPlan": report.get("verificationPlan") if isinstance(report.get("verificationPlan"), list) else [],
    }


def format_number(value: Any, digits: int = 2) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "--"
    if number != number or abs(number) == float("inf"):
        return "--"
    return f"{number:.{digits}f}".rstrip("0").rstrip(".")


def fallback_analysis_report(summary: dict[str, Any]) -> dict[str, Any]:
    effluent = summary.get("effluent") or {}
    process = summary.get("process") or {}
    controls = summary.get("controls") or {}
    warnings = summary.get("warnings") if isinstance(summary.get("warnings"), list) else []
    nh4 = effluent.get("NH4N_gN_m3")
    tn = effluent.get("TN_gN_m3")
    tss = effluent.get("TSS_g_m3")
    do_value = process.get("aerobicDO_gO2_m3")
    mlss = process.get("aerobicMLSS_g_m3")
    risk_items: list[dict[str, str]] = []
    if isinstance(nh4, (int, float)) and nh4 > 5:
        risk_items.append({"level": "warning", "item": "出水 NH4-N 偏高", "evidence": f"出水 NH4-N {format_number(nh4)} gN/m3", "impact": "硝化能力或曝气控制需要复核。"})
    if isinstance(tn, (int, float)) and tn > 15:
        risk_items.append({"level": "warning", "item": "出水 TN 偏高", "evidence": f"出水 TN {format_number(tn)} gN/m3", "impact": "反硝化能力、内回流或碳源条件需要复核。"})
    if isinstance(tss, (int, float)) and tss > 10:
        risk_items.append({"level": "warning", "item": "出水 TSS 接近或高于参考上限", "evidence": f"出水 TSS {format_number(tss)} g/m3", "impact": "二沉池固液分离或污泥沉降状态需要关注。"})
    if isinstance(mlss, (int, float)) and mlss < 2200:
        risk_items.append({"level": "info", "item": "好氧 MLSS 偏低", "evidence": f"好氧 MLSS {format_number(mlss)} g/m3", "impact": "硝化菌量和抗冲击能力可能不足。"})
    if warnings:
        risk_items.append({"level": "info", "item": "模型告警", "evidence": f"本次仿真包含 {len(warnings)} 条告警", "impact": "需先确认告警是否影响结果可信度。"})
    return {
        "headline": "关键出水指标已生成，建议复核风险项",
        "executiveSummary": [
            f"出水 NH4-N {format_number(nh4)} gN/m3，TN {format_number(tn)} gN/m3，TSS {format_number(tss)} g/m3。",
            f"好氧 DO {format_number(do_value)} gO2/m3，DO 设定 {format_number(controls.get('aerobicDOSet_gO2_m3'))} gO2/m3。",
            f"好氧 MLSS {format_number(mlss)} g/m3，RAS MLSS {format_number(process.get('rasMLSS_g_m3'))} g/m3。",
        ],
        "riskItems": risk_items,
        "recommendedActions": [
            {"priority": "high", "action": "复核出水 NH4-N、TN、TSS 与现场化验值", "reason": "先确认仿真结果与实测数据是否一致。", "expectedEffect": "避免基于模型偏差做运行调整。"},
            {"priority": "medium", "action": "检查 DO、回流比和排泥量设定", "reason": "这些参数直接影响硝化、反硝化和二沉池负荷。", "expectedEffect": "形成可追溯的调参方案。"},
        ],
        "verificationPlan": [
            "补充同一时段进水、出水和池内在线数据。",
            "复核模型告警和二沉池沉降相关参数。",
            "调整参数后重新运行方案，并对比关键指标变化。",
        ],
    }


def extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def text_from_part(part: Any) -> str:
    if isinstance(part, str):
        return part
    if isinstance(part, dict):
        value = part.get("text") or part.get("content")
        return value if isinstance(value, str) else ""
    return ""


def extract_deepseek_content(data: dict[str, Any]) -> str:
    primary_candidates: list[str] = []
    fallback_candidates: list[str] = []
    choices = data.get("choices") or []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") or {}
        if isinstance(message, dict):
            value = message.get("content")
            if isinstance(value, str):
                primary_candidates.append(value)
            elif isinstance(value, list):
                primary_candidates.append("\n".join(text_from_part(part) for part in value))
            reasoning = message.get("reasoning_content")
            if isinstance(reasoning, str):
                fallback_candidates.append(reasoning)
            elif isinstance(reasoning, list):
                fallback_candidates.append("\n".join(text_from_part(part) for part in reasoning))
        value = choice.get("text")
        if isinstance(value, str):
            primary_candidates.append(value)

    output_text = data.get("output_text")
    if isinstance(output_text, str):
        primary_candidates.append(output_text)

    for output in data.get("output") or []:
        if not isinstance(output, dict):
            continue
        content = output.get("content")
        if isinstance(content, str):
            primary_candidates.append(content)
        elif isinstance(content, list):
            primary_candidates.append("\n".join(text_from_part(part) for part in content))

    candidates = primary_candidates or fallback_candidates
    return "\n".join(item.strip() for item in candidates if item and item.strip()).strip()


def deepseek_response_diagnostic(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return "response did not include choices"
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") if isinstance(choice, dict) else {}
    message_keys = sorted(message.keys()) if isinstance(message, dict) else []
    finish_reason = choice.get("finish_reason") if isinstance(choice, dict) else None
    return f"finish_reason={finish_reason or 'unknown'}, message_keys={message_keys}"


def call_deepseek(messages: list[dict[str, str]], config: dict[str, Any], model: str | None = None) -> tuple[str, str]:
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not configured in the backend environment.")
    model_name = model or config["model"]
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1600,
        "stream": False,
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

    content = extract_deepseek_content(data)
    if not content:
        raise EmptyDeepSeekAnalysis(f"DeepSeek model {model_name} returned an empty analysis ({deepseek_response_diagnostic(data)}).")
    return content.strip(), model_name


def analyze_result(result: dict[str, Any], params: dict[str, Any], context: dict[str, Any] | None = None, model: str | None = None) -> dict[str, Any]:
    context = context or {}
    config = deepseek_config()
    summary = result_summary(result, params, context)
    messages = build_prompt(summary)
    requested_model = normalize_model_name(model, config)
    try:
        analysis, model_used = call_deepseek(messages, config, requested_model)
    except EmptyDeepSeekAnalysis:
        if requested_model == DEFAULT_DEEPSEEK_MODEL:
            raise
        analysis, model_used = call_deepseek(messages, config, DEFAULT_DEEPSEEK_MODEL)
    report = parse_analysis_report(analysis) or fallback_analysis_report(summary)
    return {
        "provider": config["provider"],
        "model": model_used,
        "configuredModel": config["model"],
        "configured": config["configured"],
        "summary": summary,
        "report": report,
        "analysis": analysis,
    }
