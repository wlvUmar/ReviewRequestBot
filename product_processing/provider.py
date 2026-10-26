"""One call helper for both OpenAI-style APIs.

URL ending in /responses -> Responses API (OpenCode Go muse-spark, GPT, ...)
anything else            -> Chat Completions (OpenRouter, OpenCode Go glm/kimi/deepseek, ...)
"""
import aiohttp


def _is_responses(url: str) -> bool:
    return url.rstrip("/").endswith("/responses")


async def complete(
    session: aiohttp.ClientSession,
    *,
    url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    images_b64: list[str] | None = None,
    web_search: bool = False,
    max_tokens: int = 600,
    timeout: float = 30,
) -> str:
    """Return the model's text. Raises RuntimeError with a short reason on any failure."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    images_b64 = images_b64 or []

    if _is_responses(url):
        content = [{"type": "input_text", "text": user}]
        for b64 in images_b64:
            content.append({"type": "input_image", "image_url": f"data:image/jpeg;base64,{b64}"})
        payload = {
            "model": model,
            "instructions": system,
            "input": [{"role": "user", "content": content}],
            # reasoning tokens count against this limit, so leave headroom
            "max_output_tokens": max(max_tokens * 4, 2000),
        }
        if web_search:
            payload["tools"] = [{"type": "web_search"}]
    else:
        if images_b64:
            content = [{"type": "text", "text": user}] + [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}}
                for b64 in images_b64
            ]
        else:
            content = user
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
        }

    try:
        async with session.post(
            url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=timeout)
        ) as resp:
            data = await resp.json(content_type=None)
    except Exception as e:
        raise RuntimeError(f"LLM call failed: {e}")

    if not isinstance(data, dict):
        raise RuntimeError(f"LLM error: {str(data)[:200]}")

    if _is_responses(url):
        text = data.get("output_text") or "".join(
            part.get("text", "")
            for item in data.get("output") or []
            if item.get("type") == "message"
            for part in item.get("content") or []
            if part.get("type") == "output_text"
        )
        if not text.strip():
            raise RuntimeError(f"LLM error: {str(data.get('error') or data)[:200]}")
        return text.strip()

    if "choices" not in data:
        raise RuntimeError(f"LLM error: {str(data.get('error') or data)[:200]}")
    return (data["choices"][0]["message"].get("content") or "").strip()
