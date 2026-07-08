"""LLM client for answer generation."""

import os
from typing import Optional

import requests

from app.config import DEEPSEEK_API_URL, DEEPSEEK_MAX_TOKENS, DEEPSEEK_MODEL

# 调用DeepSeek API
def call_deepseek_api(
    prompt: str,
    system_prompt: str,
    temperature: float = 0.1,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
) -> str:
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return "DEEPSEEK_API_KEY is not set in the environment variables."

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    data = {
        "model": model or DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens or DEEPSEEK_MAX_TOKENS,
        "temperature": temperature,
        "stream": False,
    }

    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result["choices"][0]["message"]["content"]
    except requests.RequestException as exc:
        return f"Request error: {exc}"
    except (KeyError, IndexError) as exc:
        return f"Response parsing error: {exc}"
