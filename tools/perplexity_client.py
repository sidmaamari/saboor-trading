import os
import requests

API_URL = "https://api.perplexity.ai/chat/completions"
MODEL = "llama-3.1-sonar-large-128k-online"


def search(query: str, max_tokens: int = 1024) -> str:
    """Run a Perplexity online search and return the response text."""
    headers = {
        "Authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a financial research assistant. "
                    "Provide factual, data-driven analysis with specific numbers. "
                    "If you cannot find a specific number, say so — do not estimate."
                ),
            },
            {"role": "user", "content": query},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }
    resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]
