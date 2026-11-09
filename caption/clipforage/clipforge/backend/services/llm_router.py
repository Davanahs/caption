"""
Unified Dynamic LLM Router — dynamically discovers, ranks, and queries
models across OpenRouter and Nvidia NIM with automatic failover.
"""
import time
import httpx
import asyncio
import re
import json
from typing import Optional, List, Dict, Any
from backend.core.config import settings

# In-memory registry cache
_cached_models: Optional[List[Dict[str, Any]]] = None
_last_fetch_time: float = 0.0
CACHE_TTL = 3600  # 1 hour


def is_ai_provider_configured() -> bool:
    """Check if at least one cloud AI provider is configured with non-empty credentials."""
    has_openrouter = bool(settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip())
    has_nvidia = bool(settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY.strip())
    return has_openrouter or has_nvidia


def get_configured_providers() -> List[str]:
    """Return list of configured AI provider names."""
    providers = []
    if settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip():
        providers.append("OpenRouter")
    if settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY.strip():
        providers.append("Nvidia NIM")
    return providers


async def fetch_openrouter_models() -> List[Dict[str, Any]]:
    """Fetch active models list from OpenRouter."""
    global _cached_models, _last_fetch_time
    now = time.time()

    if _cached_models and (now - _last_fetch_time < CACHE_TTL):
        return _cached_models

    url = "https://openrouter.ai/api/v1/models"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                models = data.get("data", [])
                if models:
                    _cached_models = models
                    _last_fetch_time = now
                    return _cached_models
    except Exception as e:
        print(f"[LLM Router] Failed to fetch OpenRouter models registry: {e}")

    # Return previous cache if network request failed, otherwise return empty list
    return _cached_models or []


def rank_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ranks the models according to viral moment application requirements.
    Rules:
    - Prefer completely FREE models (pricing prompt == 0.00 and pricing completion == 0.00).
    - Prefer reasoning / instruction-dense models (deepseek-r1, llama-3.3, qwen-2.5-72b, gemini-2.5-flash).
    - Exclude models with tiny context windows (< 4096 tokens).
    """
    ranked_list = []

    for m in models:
        model_id = m.get("id", "").lower()
        context_length = m.get("context_length", 2048)

        # 1. Filter out models with low context window
        if context_length < 4096:
            continue

        pricing = m.get("pricing", {})
        prompt_price = float(pricing.get("prompt", 0.0))
        completion_price = float(pricing.get("completion", 0.0))

        score = 0.0

        # Identify models with negative pricing (usually meta-routers like openrouter/auto)
        is_dynamic_pricing = (prompt_price < 0 or completion_price < 0)

        # 2. Prefer Free Models (massive boost)
        is_free = (prompt_price == 0.0 and completion_price == 0.0)
        if is_free:
            score += 1000.0
        elif is_dynamic_pricing:
            score -= 500.0
        else:
            score -= (prompt_price + completion_price) * 100000.0

        # 3. Boost reasoning & quality instruction models (user prefers accuracy over speed)
        if "deepseek-r1" in model_id or "reasoning" in model_id:
            score += 300.0
        elif "llama-3.3" in model_id or "llama-3-70b" in model_id:
            score += 150.0
        elif "qwen" in model_id and "72b" in model_id:
            score += 150.0
        elif "gemini-2.5" in model_id or "gemini-flash" in model_id:
            score += 120.0
        elif "llama-3" in model_id or "mistral-7b" in model_id or "gemma-2" in model_id:
            score += 50.0

        # Keep track of key metadata
        ranked_list.append({
            "id": m.get("id"),
            "name": m.get("name"),
            "score": score,
            "is_free": is_free,
            "context_window": context_length,
            "prompt_price": prompt_price,
            "completion_price": completion_price
        })

    # Sort in descending order of score
    ranked_list.sort(key=lambda x: x["score"], reverse=True)
    return ranked_list


async def get_ranked_openrouter_models() -> List[Dict[str, Any]]:
    """Retrieve and rank OpenRouter models."""
    models = await fetch_openrouter_models()
    if not models:
        # Hardcoded fallback list if OpenRouter models registry API is down
        return [
            {"id": "deepseek/deepseek-r1:free",              "name": "DeepSeek R1 (Free)",        "is_free": True,  "score": 1300},
            {"id": "meta-llama/llama-3.3-70b-instruct:free", "name": "Llama 3.3 70B (Free)",      "is_free": True,  "score": 1150},
            {"id": "google/gemini-2.5-flash",                "name": "Gemini 2.5 Flash",          "is_free": False, "score": 120},
            {"id": "meta-llama/llama-3.3-70b-instruct",      "name": "Llama 3.3 70B Instruct",   "is_free": False, "score": 150},
        ]
    return rank_models(models)


async def query_openrouter(prompt: str, model_id: str) -> str:
    """Send chat completion to OpenRouter API with detailed progress logging."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://clipforge.net",
        "X-Title": "ClipForge App"
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    start_time = time.time()
    print(f"[LLM Router] Sending request to OpenRouter ({model_id})...")
    print(f"[LLM Router] Waiting for response (Reasoning models like DeepSeek-R1 can take up to 90 seconds to think)...")

    # Increase timeout to 120s to allow full thinking time for reasoning models
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        elapsed = time.time() - start_time
        print(f"[LLM Router] Response received in {elapsed:.1f} seconds (Status code: {response.status_code})")
        response.raise_for_status()
        res_json = response.json()
        
        # Check for OpenRouter API error payloads returned with 200 OK status
        if "error" in res_json:
            err_msg = res_json["error"].get("message", str(res_json["error"]))
            raise RuntimeError(f"OpenRouter API Error: {err_msg}")
            
        choices = res_json.get("choices")
        if not choices:
            raise RuntimeError(f"OpenRouter returned no choices. Response: {res_json}")
            
        content = choices[0].get("message", {}).get("content")
        if content is None:
            raise RuntimeError(f"OpenRouter returned null content (likely refusal or limit). Response: {res_json}")
            
        return content


async def query_nvidia_nim(prompt: str) -> str:
    """Send chat completion to Nvidia NIM API."""
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.NVIDIA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        res_json = response.json()
        return res_json["choices"][0]["message"]["content"]


import redis

# Redis client for shared state
_redis_client = None
try:
    _redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception as e:
    print(f"[LLM Router] Failed to initialize Redis client: {e}")

def set_openrouter_cooldown():
    """Set a 1-hour cooldown for paid OpenRouter models."""
    if _redis_client:
        try:
            _redis_client.setex("openrouter:credits_exhausted", 3600, "1")
            print("[LLM Router] Set global OpenRouter cooldown (402 Payment Required).")
        except Exception as e:
            print(f"[LLM Router] Failed to set OpenRouter cooldown: {e}")

def is_openrouter_cooldown_active() -> bool:
    """Check if the paid OpenRouter models are currently on cooldown."""
    if _redis_client:
        try:
            return bool(_redis_client.get("openrouter:credits_exhausted"))
        except Exception as e:
            print(f"[LLM Router] Failed to check OpenRouter cooldown: {e}")
    return False

async def route_and_generate(prompt: str, max_tokens: int = 1000) -> str:
    """
    Main orchestration entry point:
    1. Try user-configured model first (if not skipped due to global cooldown).
    2. Try remaining ranked OpenRouter models (free first, then paid).
    3. Try Nvidia NIM (if key set).
    4. Raise RuntimeError with full per-provider diagnostics if all fail.
    """
    errors = []
    
    # ── 1. OpenRouter ─────────────────────────────────────────────────────────
    if settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip():
        # Pre-fetch ranked models to determine free/paid status
        ranked = await get_ranked_openrouter_models()
        free_models = [m for m in ranked if m.get("is_free")]
        paid_models = [m for m in ranked if not m.get("is_free")]
        
        # Build map of models to quickly check if they are free
        is_free_map = {m["id"]: m.get("is_free", False) for m in ranked}

        # Determine if we have a global cooldown on PAID OpenRouter models
        openrouter_out_of_credits = is_openrouter_cooldown_active()

        user_model = getattr(settings, "OPENROUTER_MODEL", None)
        if user_model and user_model.strip():
            # Treat unknown user models as paid by default unless we know they are free
            user_model_is_free = is_free_map.get(user_model, "free" in user_model.lower())
            
            if openrouter_out_of_credits and not user_model_is_free:
                print(f"[LLM Router] Skipping user-configured paid model {user_model} due to global 402 cooldown.")
            else:
                try:
                    print(f"[LLM Router] Trying user-configured model: {user_model}")
                    return await query_openrouter(prompt, user_model)
                except httpx.HTTPStatusError as e:
                    errors.append(f"User model ({user_model}): {e}")
                    if e.response.status_code == 402:
                        print(f"[LLM Router] Detected 402 Payment Required for {user_model}.")
                        set_openrouter_cooldown()
                        openrouter_out_of_credits = True
                    else:
                        print(f"[LLM Router] User model {user_model} failed: {e}. Trying fallback models...")
                except Exception as e:
                    print(f"[LLM Router] User model {user_model} failed: {e}. Trying fallback models...")
                    errors.append(f"User model ({user_model}): {e}")

        candidates = list(free_models[:3])
        if not openrouter_out_of_credits:
            candidates += paid_models[:2]

        for model_info in candidates:
            model_id = model_info["id"]
            if user_model and model_id == user_model:
                continue
                
            if openrouter_out_of_credits and not model_info.get("is_free"):
                print(f"[LLM Router] Skipping paid model {model_id} due to global 402 cooldown.")
                continue

            label = "FREE" if model_info.get("is_free") else "PAID"
            
            max_retries = 1
            for attempt in range(max_retries + 1):
                try:
                    print(f"[LLM Router] -> Trying OpenRouter [{label}]: {model_id} (Attempt {attempt+1})")
                    result = await query_openrouter(prompt, model_id)
                    if not result or not result.strip():
                        raise ValueError("Model returned empty or null content.")
                    print(f"[LLM Router] [OK] OpenRouter '{model_id}' OK.")
                    return result
                except httpx.HTTPStatusError as e:
                    print(f"[LLM Router] [ERR] OpenRouter '{model_id}' error: {e}")
                    errors.append(f"OpenRouter/{model_id}: {e}")
                    if e.response.status_code == 401:
                        print(f"[LLM Router] Detected 401 Unauthorized for OpenRouter key. Halting OpenRouter attempts.")
                        break  # Will break model attempts and move to next provider
                    elif e.response.status_code == 402:
                        print(f"[LLM Router] Detected 402 Payment Required for {model_id}.")
                        set_openrouter_cooldown()
                        openrouter_out_of_credits = True
                        break # Break retry loop, move to next model (which will skip paid models)
                    elif e.response.status_code == 429:
                        if attempt < max_retries:
                            print(f"[LLM Router] Detected 429 Too Many Requests. Retrying in 2 seconds...")
                            await asyncio.sleep(2)
                            continue
                        else:
                            break
                    else:
                        break
                except Exception as e:
                    print(f"[LLM Router] [ERR] OpenRouter '{model_id}' error: {e}")
                    errors.append(f"OpenRouter/{model_id}: {e}")
                    break
            if errors and "401 Unauthorized" in str(errors[-1]):
                break # Stop iterating remaining OpenRouter models, jump to Nvidia NIM

    # ── 2. Nvidia NIM ─────────────────────────────────────────────────────────
    if settings.NVIDIA_API_KEY and settings.NVIDIA_API_KEY.strip():
        try:
            print(f"[LLM Router] -> Trying Nvidia NIM: {settings.NVIDIA_MODEL}")
            result = await query_nvidia_nim(prompt)
            if not result or not result.strip():
                raise ValueError("Model returned empty or null content.")
            print(f"[LLM Router] ✅ Nvidia NIM OK.")
            return result
        except Exception as e:
            print(f"[LLM Router] ❌ Nvidia NIM error: {e}")
            errors.append(f"Nvidia NIM: {e}")

    raise RuntimeError(
        "All cloud AI providers failed. Errors: " + (" | ".join(errors) if errors else "API keys not set")
    )
