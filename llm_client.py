# llm_client.py
from dotenv import load_dotenv
load_dotenv()

import os
import time
import json
import traceback
from typing import Any, Dict, Optional

import google.generativeai as genai

# Ensure GEMINI_API_KEY is present
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment! Make sure .env is present and loaded.")
genai.configure(api_key=API_KEY)

# Default model (you can change to "gemini-1.5-flash" to reduce quotas/costs)
MODEL = "gemini-2.5-flash"


def _retry(fn, attempts: int = 3, backoff: float = 1.0):
    last_exc = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            time.sleep(backoff * (1 + i))
    raise last_exc


def _get_finish_reason_from_response(response) -> Optional[str]:
    """
    Try to find a finish_reason in common response shapes.
    """
    try:
        # new style: response.output[0].candidates[0].safety or finish_reason
        out = getattr(response, "output", None)
        if out and isinstance(out, (list, tuple)) and len(out) > 0:
            first = out[0]
            # candidate may be under first.get('candidates') or first.candidates
            cands = getattr(first, "candidates", None) or (first.get("candidates") if isinstance(first, dict) else None)
            if cands and len(cands) > 0:
                fr = getattr(cands[0], "finish_reason", None) or (cands[0].get("finish_reason") if isinstance(cands[0], dict) else None)
                if fr:
                    return fr
    except Exception:
        pass

    # older style: response.candidates[0].finish_reason
    try:
        cands = getattr(response, "candidates", None) or (response.get("candidates") if isinstance(response, dict) else None)
        if cands and len(cands) > 0:
            fr = getattr(cands[0], "finish_reason", None) or (cands[0].get("finish_reason") if isinstance(cands[0], dict) else None)
            if fr:
                return fr
    except Exception:
        pass

    # no finish reason found
    return None


def _extract_text_from_response(response) -> Optional[str]:
    """
    Robustly extract text from the SDK response object across many shapes.
    Returns a clean string if found, otherwise None.
    IMPORTANT: do NOT return a stringified SDK repr here; return None so callers can fallback safely.
    """
    # 1) quick accessor (may raise ValueError if no Part present) - handle safely
    try:
        text = getattr(response, "text", None)
        if text and isinstance(text, str) and text.strip():
            return text.strip()
    except Exception:
        # safe to swallow and continue searching other fields
        pass

    # 2) response.result / response.result.candidates (many SDKs use `.result`)
    try:
        res = getattr(response, "result", None)
        if res:
            cands = getattr(res, "candidates", None) or (res.get("candidates") if isinstance(res, dict) else None)
            if cands and len(cands) > 0:
                cand0 = cands[0]
                # candidate often has content list -> content[0].text
                content = getattr(cand0, "content", None) or (cand0.get("content") if isinstance(cand0, dict) else None)
                if isinstance(content, (list, tuple)) and len(content) > 0:
                    first = content[0]
                    txt = getattr(first, "text", None) or (first.get("text") if isinstance(first, dict) else None)
                    if txt and isinstance(txt, str) and txt.strip():
                        return txt.strip()
                # sometimes candidate has 'structured' or 'text' directly
                txt = getattr(cand0, "text", None) or (cand0.get("text") if isinstance(cand0, dict) else None)
                if txt and isinstance(txt, str) and txt.strip():
                    return txt.strip()
    except Exception:
        pass

    # 3) new-style 'output' field: list of parts
    try:
        out = getattr(response, "output", None)
        if out and isinstance(out, (list, tuple)) and len(out) > 0:
            for part in out:
                # part may have content list
                content = getattr(part, "content", None) or (part.get("content") if isinstance(part, dict) else None)
                if content:
                    if isinstance(content, (list, tuple)) and len(content) > 0:
                        for c in content:
                            txt = getattr(c, "text", None) or (c.get("text") if isinstance(c, dict) else None)
                            if txt and isinstance(txt, str) and txt.strip():
                                return txt.strip()
                    else:
                        txt = getattr(content, "text", None) or (content.get("text") if isinstance(content, dict) else None)
                        if txt and isinstance(txt, str) and txt.strip():
                            return txt.strip()
    except Exception:
        pass

    # 4) older SDK shapes: response.candidates
    try:
        candidates = getattr(response, "candidates", None) or (response.get("candidates") if isinstance(response, dict) else None)
        if candidates and len(candidates) > 0:
            cand0 = candidates[0]
            # check for content or text fields
            content = getattr(cand0, "content", None) or (cand0.get("content") if isinstance(cand0, dict) else None)
            if isinstance(content, (list, tuple)) and len(content) > 0:
                first = content[0]
                txt = getattr(first, "text", None) or (first.get("text") if isinstance(first, dict) else None)
                if txt and isinstance(txt, str) and txt.strip():
                    return txt.strip()
            txt = getattr(cand0, "text", None) or (cand0.get("text") if isinstance(cand0, dict) else None)
            if txt and isinstance(txt, str) and txt.strip():
                return txt.strip()
    except Exception:
        pass

    # nothing usable found; return None so caller can fallback (do NOT return a stringified SDK object)
    return None


def call_gemini_text(prompt: str,
                     max_output_tokens: int = 512,
                     temperature: float = 0.0) -> str:
    """
    Robust text call to Gemini. Returns text (string) on success.
    Raises descriptive error when no usable text could be extracted.
    """
    def _call():
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content(
            prompt,
            generation_config={"temperature": temperature, "max_output_tokens": max_output_tokens}
        )

        # Try to extract best text first
        text = _extract_text_from_response(response)
        if text:
            return text

        # If no text, gather diagnostics to give a clearer error to caller
        diag = {"note": "no extractable text from SDK response"}
        try:
            # include finish_reason if present
            fr = _get_finish_reason_from_response(response)
            if fr:
                diag["finish_reason"] = fr
        except Exception:
            pass

        # include short repr for debugging but do not return it as normal text (raise instead)
        try:
            diag["repr"] = str(response)[:1000]
        except Exception:
            diag["repr"] = "<unserializable response>"

        raise ValueError(f"Model returned no extractable text. Diagnostics: {json.dumps(diag)[:1500]}")

    return _retry(_call)


def call_gemini_structured(prompt: str,
                           json_schema: Dict[str, Any],
                           max_output_tokens: int = 1024,
                           temperature: float = 0.0) -> Optional[Any]:
    """
    Ask Gemini to produce JSON conforming to json_schema. Returns parsed JSON or None if parsing fails.
    The wrapper asks the model to emit JSON only, then attempts to extract and parse it.
    """
    schema_text = json.dumps(json_schema, indent=2, ensure_ascii=False)
    wrapped_prompt = (
        "You are a helpful assistant. Output ONLY JSON that conforms to the given schema (no extra text).\n\n"
        f"Schema:\n{schema_text}\n\n"
        f"Content:\n{prompt}\n\n"
        "Respond with the JSON only. Do not add any commentary."
    )

    raw = call_gemini_text(wrapped_prompt, max_output_tokens=max_output_tokens, temperature=temperature)

    if not raw or not isinstance(raw, str):
        return None

    raw_str = raw.strip()
    # remove common triple-backtick fences if present
    for fence in ("```json", "```", "```json\n", "```json\r\n"):
        if raw_str.startswith(fence):
            raw_str = raw_str[len(fence):].strip()

    # Try to parse JSON reliably
    try:
        if raw_str.startswith("{") or raw_str.startswith("["):
            if raw_str.startswith("{"):
                start = raw_str.find("{")
                end = raw_str.rfind("}") + 1
            else:
                start = raw_str.find("[")
                end = raw_str.rfind("]") + 1
            candidate = raw_str[start:end]
            return json.loads(candidate)
        return json.loads(raw_str)
    except Exception:
        # parsing failed; return None so caller can fallback safely
        return None
