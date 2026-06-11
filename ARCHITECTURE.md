# AnytoolAI Architecture

## Layers

```text
apps/*
  deployable composition roots

packages/backend/platform-core
  product-neutral runtime: config, identity, products, scenarios, workflows, jobs, actions, prompts, providers, artifacts, events, quotas, handoffs, storage, errors

packages/backend/platform-actions
  generic action definitions and generic Structured LLM executor bindings

packages/backend/platform-sdk
  public contracts used by product bundles

packages/backend/product-platforms
  product-specific bundles; never imported by platform-core

packages/frontend/ce-kit
  shared Chrome Extension client kit

packages/frontend/web-result-kit
  shared artifact/result rendering components

extensions/*
  product-specific Chrome Extensions

configs/*
  declarative definitions for MVP

migrations/*
  durable runtime schema
```

## Dependency direction

```text
apps/platform-api -> platform-core
apps/platform-api -> platform-actions
apps/platform-api -> product-platforms/*  (MVP-B only)

product-platforms/* -> platform-sdk
platform-actions -> platform-sdk / platform-core public contracts
platform-core -> no product-platforms

extensions/* -> ce-kit -> platform API
```

## Runtime principle

```text
Product Definition -> Scenario Session -> Workflow Definition -> Action Configurations -> Atomic Actions -> Provider Gateway -> Structured Output -> Artifact -> Event Log -> Guest Quota -> Email Capture / Waitlist Intent -> Handoff -> Web Mirror / CE Kit
```

## MVP-A scope

MVP-A is the Platform Kernel. It proves that a declarative product/scenario/workflow/action configuration can create a scenario session, run a typed workflow, call a provider through the gateway, validate structured output, store artifacts, write events, apply guest quota, capture email, and create a user-confirmed handoff.

MVP-A has no real Freelancer product semantics. `kernel_demo` is an internal smoke-test surface only.

## MVP-B scope

MVP-B is the Freelancer Validation Bundle v0. It adds thin product configs, prompts, schemas, workflows, result renderers, handoff maps, product events, and separate Chrome Extensions for the Freelancer products. ProposalAI is the first real product after the kernel because it is the fastest end-to-end proof. MVP-B must not change platform-core.
