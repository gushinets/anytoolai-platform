# AnytoolAI Architecture

## Layers

```text
apps/*
  deployable composition roots

apps/web-mirror
  shared multi-product web host, product routes, results, consent, onboarding, and paywall

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
  optional product-specific Chrome Extensions

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
apps/web-mirror -> ce-kit -> platform API
apps/web-mirror -> web-result-kit
```

## Runtime principle

```text
Product Definition -> Scenario Session -> Workflow Definition -> Action Configurations -> Atomic Actions -> Provider Gateway -> Structured Output -> Artifact -> Event Log -> Frontend-safe Result API
```

## MVP-A scope

MVP-A is delivered in two sequential milestones:

- MVP-A1 Atom Runtime Proof proves all 11 typed atoms individually and in composite workflows
  through API, PostgreSQL, worker, Provider Gateway, artifacts, and events. It does not depend on a
  web page or Chrome Extension.
- MVP-A2 Client Surfaces delivers shared client contracts, the multi-product web host, handoff
  consent, paywall/onboarding, the kernel-demo reference Chrome Extension, and browser evidence over
  frontend-safe Platform Core APIs.

MVP-A has no real Freelancer product semantics. `kernel_demo` is an internal smoke-test surface only.

## MVP-B scope

MVP-B is the web-first Freelancer Validation Bundle v0. The validation set is ProposalAI, Client
Update Writer, Brief Decoder, Acceptance Builder, Task Finder, and Send-Ready. Each product has a
product-owned bundle/workflow, web definition/page, renderer, events, and runtime E2E slice hosted
through `apps/web-mirror`. Dedicated Chrome Extensions are optional and remain product-owned when a
product requires them. Product delivery must not add Freelancer semantics to Platform Core or change
atoms, action/workflow runners, Provider Gateway, scenario/quota/handoff runtime, or mapping DSL.

The 21 atom-ready concepts are a capability inventory, not a release commitment.
