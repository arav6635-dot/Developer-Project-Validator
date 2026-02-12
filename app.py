import json
import os
import re
import ast
from typing import Any, Dict, Tuple
import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
try:
    from json_repair import repair_json
except ImportError:  # Optional dependency fallback.
    repair_json = None

load_dotenv()

app = Flask(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
EXPECTED_KEYS = [
    "market_competition",
    "monetization_potential",
    "target_users",
    "feature_suggestions",
    "mvp_plan",
    "risk_score",
    "summary",
]
APP_BUILD = "2026-02-12-structured-v4"
RESPONSE_JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "market_competition": {"type": "string"},
        "monetization_potential": {"type": "string"},
        "target_users": {"type": "string"},
        "feature_suggestions": {"type": "array", "items": {"type": "string"}},
        "mvp_plan": {"type": "array", "items": {"type": "string"}},
        "risk_score": {"type": "string"},
        "summary": {"type": "string"},
    },
    "required": EXPECTED_KEYS,
    "additionalProperties": False,
}


def _extract_json(text: str) -> Dict[str, Any]:
    """Extract a JSON object from LLM output with tolerant fallbacks."""
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try automatic repair of malformed JSON output from the model.
    if repair_json is not None:
        try:
            repaired = repair_json(text)
            if isinstance(repaired, dict):
                return repaired
            if isinstance(repaired, str):
                return json.loads(repaired)
        except Exception:
            pass

    # Handle fenced code blocks: ```json { ... } ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    # Try extracting the first balanced object from noisy text.
    start = text.find("{")
    if start != -1:
        depth = 0
        end = -1
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end != -1:
            candidate = text[start : end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # Last resort for Python-style dict output with single quotes.
                try:
                    parsed = ast.literal_eval(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except (ValueError, SyntaxError):
                    pass

    raise ValueError(
        "No valid JSON object found in model response. "
        f"Raw model output starts with: {text[:220]!r}"
    )


def _parse_model_json(text: str) -> Dict[str, Any]:
    """
    Parse model output with multiple fallbacks, but never raise parsing errors.
    """
    try:
        return _extract_json(text)
    except ValueError:
        pass

    if repair_json is not None:
        try:
            repaired = repair_json(text)
            if isinstance(repaired, dict):
                return repaired
            if isinstance(repaired, str):
                return json.loads(repaired)
        except Exception:
            pass

    return _salvage_json_like(text)


def _salvage_json_like(text: str) -> Dict[str, Any]:
    """
    Best-effort extraction for malformed/truncated JSON-like model output.
    This prevents hard failures when the model returns near-JSON.
    """
    result: Dict[str, Any] = {}
    if not text:
        return result

    for idx, key in enumerate(EXPECTED_KEYS):
        current_key_pattern = rf'"{re.escape(key)}"\s*:'
        match = re.search(current_key_pattern, text)
        if not match:
            continue

        start = match.end()
        end = len(text)

        for next_key in EXPECTED_KEYS[idx + 1 :]:
            next_match = re.search(rf',?\s*"{re.escape(next_key)}"\s*:', text[start:])
            if next_match:
                end = start + next_match.start()
                break

        raw_value = text[start:end].strip().rstrip(",").strip()
        if not raw_value:
            continue

        if key in {"feature_suggestions", "mvp_plan"}:
            array_match = re.search(r"\[(.*?)]", raw_value, re.DOTALL)
            if array_match:
                inside = array_match.group(1)
            else:
                inside = raw_value

            items = re.findall(r'"([^"\n]+)"', inside)
            if not items:
                items = [s.strip(" -•\t\r\n") for s in re.split(r"[\n;]+", inside) if s.strip(" -•\t\r\n")]
            result[key] = items
        else:
            str_match = re.search(r'^"(.*)"$', raw_value, re.DOTALL)
            if str_match:
                val = str_match.group(1)
            else:
                val = raw_value
            result[key] = val.replace('\\"', '"').strip()

    return result


def _validate_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    required_keys = [
        "market_competition",
        "monetization_potential",
        "target_users",
        "feature_suggestions",
        "mvp_plan",
        "risk_score",
        "summary",
    ]
    list_fields = {"feature_suggestions", "mvp_plan"}
    for key in required_keys:
        if key not in payload:
            payload[key] = [] if key in list_fields else "Not provided"

    if not isinstance(payload.get("feature_suggestions"), list):
        payload["feature_suggestions"] = [str(payload["feature_suggestions"])]

    if not isinstance(payload.get("mvp_plan"), list):
        payload["mvp_plan"] = [str(payload["mvp_plan"])]

    payload["feature_suggestions"] = [str(x).strip() for x in payload["feature_suggestions"] if str(x).strip()]
    payload["mvp_plan"] = [str(x).strip() for x in payload["mvp_plan"] if str(x).strip()]

    return payload


def _call_gemini(prompt_text: str, max_tokens: int = 1400, temperature: float = 0.35) -> Tuple[str, str]:
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text}
                ]
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
            "responseMimeType": "application/json",
            "responseJsonSchema": RESPONSE_JSON_SCHEMA,
        },
    }


    url = GEMINI_URL.format(model=GEMINI_MODEL)
    params = {"key": GEMINI_API_KEY}
    resp = requests.post(url, params=params, json=body, timeout=45)
    resp.raise_for_status()

    data = resp.json()
    try:
        candidate = data["candidates"][0]
        text = candidate["content"]["parts"][0]["text"]
        finish_reason = candidate.get("finishReason", "")
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected Gemini response format: {data}") from exc

    return text, finish_reason


def analyze_project_idea(idea: str) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        raise RuntimeError("Missing GEMINI_API_KEY in environment.")

    prompt_1 = (
        "You are a practical startup advisor for solo developers. "
        "Analyze the project idea and keep answers concise and concrete. "
        f"Project idea:\n{idea}"
    )

    text_1, finish_1 = _call_gemini(prompt_1, max_tokens=1400, temperature=0.35)
    parsed_1 = _parse_model_json(text_1)
    if parsed_1:
        return _validate_response(parsed_1)

    # Retry once if output is empty/invalid even with schema constraints.
    prompt_2 = (
        "Retry the same analysis. "
        "Keep each paragraph under 40 words and arrays short."
        f"\n\nProject idea:\n{idea}"
    )
    text_2, finish_2 = _call_gemini(prompt_2, max_tokens=1800, temperature=0.2)
    parsed_2 = _parse_model_json(text_2)
    if parsed_2:
        return _validate_response(parsed_2)

    fallback = _validate_response(
        {
            "market_competition": "Not provided",
            "monetization_potential": "Not provided",
            "target_users": "Not provided",
            "feature_suggestions": [],
            "mvp_plan": [],
            "risk_score": "Not provided",
            "summary": (
                "The model response was unusable. "
                f"finishReason(s): {finish_1 or 'unknown'}, {finish_2 or 'unknown'}."
            ),
        }
    )
    return fallback


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/health")
def health() -> Any:
    return jsonify({"ok": True, "build": APP_BUILD})


@app.post("/analyze")
def analyze() -> Any:
    payload = request.get_json(silent=True) or {}
    idea = (payload.get("idea") or "").strip()

    if not idea:
        return jsonify({"error": "Please enter a project idea."}), 400

    try:
        result = analyze_project_idea(idea)
        return jsonify(result)
    except requests.HTTPError as exc:
        details = exc.response.text if exc.response is not None else str(exc)
        return jsonify({"error": f"Gemini API error: {details}"}), 502
    except ValueError:
        return jsonify({"error": "Model response was malformed. Please try again."}), 502
    except Exception:  # pragma: no cover
        return jsonify({"error": "Unexpected server error. Check terminal logs."}), 500


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    app.run(host=host, port=port, debug=debug, use_reloader=False)
