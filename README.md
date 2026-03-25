# 🚦 LLM Gateway

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688?style=flat&logo=fastapi)](https://fastapi.tiangolo.com)
[![Redis](https://img.shields.io/badge/Redis-7.x-DC382D?style=flat&logo=redis)](https://redis.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **Production LLM API gateway** — semantic caching, multi-provider failover, rate limiting, cost-based routing, and a unified OpenAI-compatible API.

## ✨ Highlights

- 💰 **Cost routing** — automatically sends to cheapest model that meets quality requirements
- 🔄 **Failover** — if OpenAI fails, routes to Anthropic or Bedrock in <50ms
- 🧠 **Semantic cache** — ChromaDB-based cache for similar queries (saves ~40% API costs)
- ⏱️ **Rate limiting** — per-user, per-model token bucket rate limiter via Redis
- 📊 **Analytics** — per-model cost, latency, error rate dashboards
- 🔌 **OpenAI-compatible** — drop in your existing OpenAI client code unchanged

## Quick Start

```bash
git clone https://github.com/rutvik29/llm-gateway
cd llm-gateway
pip install -r requirements.txt
cp .env.example .env

python -m src.gateway  # :8080

# Use it like OpenAI
import openai
client = openai.OpenAI(base_url="http://localhost:8080/v1", api_key="any")
response = client.chat.completions.create(model="auto", messages=[...])
```

## Routing Logic

```
Request
  │
  ├──▶ Semantic Cache Check (ChromaDB)
  │       └── HIT: return cached response (0 cost)
  │
  └──▶ Route Selection
          ├── "cheap": gpt-4o-mini → claude-haiku → bedrock-nova
          ├── "balanced": gpt-4o → claude-sonnet → bedrock-sonnet
          └── "best": gpt-4o → claude-opus → bedrock-premium
```

## License
MIT © Rutvik Trivedi
