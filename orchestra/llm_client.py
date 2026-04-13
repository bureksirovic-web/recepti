"""Thin wrapper around the OpenAI-compatible chat completions API.

Uses only stdlib (urllib) — no external dependencies required.
Supports both streaming and non-streaming responses.
"""

import json
from typing import Generator, Optional
from urllib.request import Request, urlopen
from urllib.error import URLError


def chat_completion(
    base_url: str,
    model: str,
    messages: list[dict],
    api_key: str = "local",
    max_tokens: int = 8192,
    temperature: float = 0.0,
    stream: bool = False,
) -> str | Generator[str, None, None]:
    """Send a chat completion request.

    Args:
        base_url: API base URL (e.g., http://127.0.0.1:8002/v1)
        model: Model name (e.g., offline-brain)
        messages: Chat messages
        api_key: API key
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature (0.0 = deterministic)
        stream: If True, returns a generator yielding text chunks

    Returns:
        Complete response text (if stream=False) or generator of chunks
    """
    url = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream,
    }

    req = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    if not stream:
        return _non_streaming_request(req)
    return _streaming_request(req)


def _non_streaming_request(req: Request) -> str:
    """Send a non-streaming request and return the full response text."""
    try:
        with urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"] or ""
    except URLError as e:
        raise ConnectionError(f"LLM request failed: {e}") from e
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise ValueError(f"Invalid LLM response: {e}") from e


def _streaming_request(req: Request) -> Generator[str, None, None]:
    """Send a streaming request and yield text chunks."""
    try:
        resp = urlopen(req, timeout=600)
    except URLError as e:
        raise ConnectionError(f"LLM request failed: {e}") from e

    try:
        buffer = b""
        for raw_chunk in resp:
            buffer += raw_chunk
            # SSE lines end with \n\n
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line or line == b"data: [DONE]":
                    continue
                if line.startswith(b"data: "):
                    try:
                        data = json.loads(line[6:])
                        delta = data["choices"][0]["delta"]
                        content = delta.get("content")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
    finally:
        resp.close()


def is_endpoint_live(base_url: str) -> bool:
    """Check if a vLLM endpoint is responding."""
    try:
        req = Request(f"{base_url}/models", method="GET")
        with urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False
