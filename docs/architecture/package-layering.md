# Package Layering

```text
apps/platform-api
  -> platform-core
  -> platform-actions
  -> product-platforms/*  (MVP-B)

platform-core
  -> no product-platforms
  -> provider boundary may import litellm/provider SDKs only under providers/*

platform-actions
  -> platform-core public contracts
  -> no product-platforms
  -> structured_llm_executor may import pydantic_ai only under that executor boundary

product-platforms/*
  -> platform-sdk only
  -> no pydantic_ai, litellm, or provider SDK imports

extensions/*
  -> ce-kit
  -> platform API
  -> no prompts, provider policies, pydantic_ai, litellm, or provider SDK imports

web-result-kit
  -> shared UI/components only

shared/contracts
  -> cross-language public contracts
```

Architecture tests enforce these edges.

## LLM runtime boundaries

Allowed imports:

```text
packages/backend/platform-core/**/providers/**
  litellm
  openai
  anthropic
  google.genai
  cohere
  mistralai

packages/backend/platform-actions/**/structured_llm_executor/**
  pydantic_ai
```

Every other package must use AnytoolAI platform contracts. This keeps Provider Gateway as the single path to external models and keeps product bundles from bypassing provider policy, retry accounting, provider-call logging, and structured-output artifact rules.
