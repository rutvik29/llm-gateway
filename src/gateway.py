"""LLM Gateway — unified API with caching, failover, routing."""
import os, time, hashlib
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import openai
import anthropic
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

app = FastAPI(title="LLM Gateway", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Semantic cache
_chroma = chromadb.Client()
_ef = OpenAIEmbeddingFunction(api_key=os.getenv("OPENAI_API_KEY",""), model_name="text-embedding-3-small")
_cache = _chroma.get_or_create_collection("llm_cache", embedding_function=_ef)

PROVIDERS = {
    "gpt-4o": {"provider": "openai", "model": "gpt-4o", "cost_per_1k": 0.005},
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini", "cost_per_1k": 0.00015},
    "claude-3-5-sonnet": {"provider": "anthropic", "model": "claude-3-5-sonnet-20241022", "cost_per_1k": 0.003},
}

TIERS = {
    "cheap": ["gpt-4o-mini", "claude-3-haiku"],
    "balanced": ["gpt-4o", "claude-3-5-sonnet"],
    "best": ["gpt-4o", "claude-3-5-sonnet"],
    "auto": ["gpt-4o-mini", "gpt-4o", "claude-3-5-sonnet"],
}


class ChatRequest(BaseModel):
    model: str = "auto"
    messages: List[dict]
    max_tokens: Optional[int] = 1024
    temperature: float = 0.7
    use_cache: bool = True
    tier: str = "auto"


async def check_cache(query: str, threshold: float = 0.95):
    try:
        results = _cache.query(query_texts=[query], n_results=1)
        if results["distances"] and results["distances"][0] and results["distances"][0][0] < (1 - threshold):
            cached = results["documents"][0][0] if results["documents"] and results["documents"][0] else None
            if cached:
                return results["metadatas"][0][0].get("response")
    except Exception:
        pass
    return None


async def call_openai(model_config, messages, max_tokens, temperature):
    client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = await client.chat.completions.create(model=model_config["model"], messages=messages, max_tokens=max_tokens, temperature=temperature)
    return resp.choices[0].message.content


async def call_anthropic(model_config, messages, max_tokens, temperature):
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    system = next((m["content"] for m in messages if m["role"] == "system"), "")
    user_msgs = [m for m in messages if m["role"] != "system"]
    resp = await client.messages.create(model=model_config["model"], max_tokens=max_tokens, system=system, messages=user_msgs)
    return resp.content[0].text


@app.post("/v1/chat/completions")
async def chat(request: ChatRequest):
    query = " ".join(m.get("content","") for m in request.messages if m.get("role") == "user")
    if request.use_cache:
        cached = await check_cache(query)
        if cached:
            return {"choices": [{"message": {"role": "assistant", "content": cached}, "finish_reason": "stop"}], "cached": True}

    models_to_try = TIERS.get(request.tier, TIERS["auto"])
    for model_name in models_to_try:
        cfg = PROVIDERS.get(model_name)
        if not cfg:
            continue
        try:
            start = time.time()
            if cfg["provider"] == "openai":
                content = await call_openai(cfg, request.messages, request.max_tokens, request.temperature)
            elif cfg["provider"] == "anthropic":
                content = await call_anthropic(cfg, request.messages, request.max_tokens, request.temperature)
            else:
                continue
            latency = time.time() - start
            _cache.add(documents=[query], ids=[hashlib.md5(query.encode()).hexdigest()], metadatas=[{"response": content, "model": model_name, "latency": latency}])
            return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}], "model": model_name, "latency_ms": round(latency * 1000)}
        except Exception as e:
            continue
    raise HTTPException(status_code=503, detail="All providers failed")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
