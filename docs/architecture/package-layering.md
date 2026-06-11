# Package Layering

```text
apps/platform-api
  -> platform-core
  -> platform-actions
  -> product-platforms/*  (MVP-B)

platform-core
  -> no product-platforms

platform-actions
  -> platform-core public contracts
  -> no product-platforms

product-platforms/*
  -> platform-sdk only

extensions/*
  -> ce-kit
  -> platform API

web-result-kit
  -> shared UI/components only

shared/contracts
  -> cross-language public contracts
```

Architecture tests enforce these edges.
