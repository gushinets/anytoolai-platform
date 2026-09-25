# Execution Plan: Atom Lab v1

## Status

- State: active
- Phase: AL09/ANY-467 automated acceptance implemented; credentialed acceptance blocked
- Owner: mixed
- Created: 2026-09-09
- Last updated: 2026-09-24
- Review date: 2026-09-16
- Next action: run the credentialed Atom Lab live-canary, then inspect and publish privacy-safe
  evidence.
- Blocker: the current ANY-467 environment has no live OpenAI, live-canary, or Atom Lab access
  credentials; AL09 and the release remain incomplete until real evidence exists.
- Linear project: [Atom Lab](https://linear.app/paveldik/project/atom-lab-e1efc95ce888)
- Milestone: Atom Lab v1

## Goal

Внутренний инструмент для ручного тестирования всех 11 существующих атомов: полный вход,
редактируемый промпт, OpenAI GPT/reasoning, результат, версионируемые пресеты и постоянная история.
Этот план декомпозирует согласованную спецификацию; он не является отчётом о реализации.

## Scope

### In scope

Развиваем текущий platform-api, PostgreSQL, worker, ActionRunner и ProviderGateway.
Размещаем статическую страницу /atom-lab на API origin; отдельный /v1/atom-lab/* защищён.
Все атомные контракты фиксированы; сохраняем production PromptedOutput и существующие retries.

### Out of scope

Цепочки, новый executor/deployment/database, новые providers, native JSON Schema migration,
изменение input/output contracts, автоматическая оптимизация, импорт/публикация пресетов в продукт,
аккаунты/SSO, автоматическое удаление истории. /demo не удаляем.

## Relevant docs

- [Approved specification](../../superpowers/specs/2026-09-09-atom-lab-design.md)
- [Controlling scope](../../product-specs/mvp-scope-source-of-truth.md)
- [Core beliefs](../../core-beliefs.md)
- [Platform boundaries](../../architecture/platform-boundaries.md)
- [Package layering](../../architecture/package-layering.md)
- [LLM runtime](../../architecture/llm-runtime.md)
- [Frontend boundaries](../../architecture/frontend-boundaries.md)
- [Runtime storage](../../architecture/runtime-storage.md)

## Existing implementation and reuse

- ANY-392 delivered /demo and its static assets inside platform-api; reuse hosting, safe rendering
  and runtime delegation patterns, not the fixed three-workflow input or public polling.
- ANY-218/ANY-221 delivered standalone matrix/live canary; reuse live action configurations,
  atom contracts, executor, fixtures and evidence tooling. Existing smoke workflows contain fixed
  literals and are NOT lab input bindings. AL02 adds internal one-step laboratory workflows using
  full-payload passthrough; existing smoke scenarios remain unchanged.
- Current demo uses a fresh guest per start and a process-local admission lock. Neither supplies
  durable idempotent Lab submissions. Reuse ScenarioRuntimeService idempotency with stable submission
  identity and PostgreSQL admission, not a fresh identity on each HTTP retry.
- Current executor resolves prompts/provider policies from registry. Run-local immutable overrides
  need explicit plumbing through queue/worker, not global registry edits.
- Current demo polls public session/result APIs without its access code. Lab must instead use
  protected history endpoints and deny lab resources through public sibling endpoints.
- OPENAI_API_KEY currently belongs to worker. Worker refreshes catalog through provider boundary;
  API reads persisted metadata. No provider key added to API.
- Client Surfaces shared web product runtime (ANY-453) is a separate product-facing initiative;
  Atom Lab does not depend on building that UI host.

## Contracts touched

- API: GET /atoms and /atoms/{id}; GET /models and POST /models/refresh; POST/GET /runs,
  GET /runs/{id}; GET/POST /presets, GET/POST version routes, version export, all under /v1/atom-lab.
  POST /runs uses Idempotency-Key. Shared-code header is internal-only and never persisted client-side.
- DB: minimal lab runs snapshot table, preset identity/version tables, last-good model catalog cache,
  using existing migration/repository conventions. Existing session/job/action/artifact/provider
  ledger remains authoritative. No second execution ledger.
- Config: base atom definitions remain YAML/Markdown; optional small provider capability corrections.
  Lab experimental presets are a documented narrow exception, not a production config registry.
- Events: existing required dimensions and runtime identifiers retained. No prompts/input/output,
  credentials or hidden reasoning in ordinary logs/events.
- Frontend: plain static assets on platform-api, one draft payload, schema-derived controls,
  protected data requests, no new framework or deployment.
- Security: server-established lab classification propagated to runtime resources; public reads,
  starts and downstream actions cannot expose or operate on these resources.

## Technical defaults

Technical starting defaults selected during planning, not immutable product requirements.
They are configurable on backend and documented in deployment:
input JSON 256 KiB, prompt UTF-8 64 KiB, total request body 384 KiB,
100 accepted starts per UTC day and one active lab run. Existing retry hard caps stay unchanged.
Counts and idempotency checks are atomic in PostgreSQL; failed pre-start validation does not count.
These are operational starting values, not model token/context guarantees.

Catalog refresh TTL: 24 hours; explicit refresh no more than once per 60 seconds; one refresh in flight.
Use a dedicated catalog state/cache row and a bounded refresh hook in the existing worker loop,
not workflow jobs or a new generic task queue/scheduler. AL03 owns initial, TTL and manual refresh.
Initial empty cache disables execution with
an actionable message; failed refresh retains last-good data marked stale. No paid probes.
Metadata is override > LiteLLM > unknown; unknown effort ranges cannot be fabricated.

History and presets are shared within the authorised team, paginated, no automatic deletion.
Fixed preset settings apply to entire top-level fields; full visible input is the executed payload.
Preset versions and accepted config snapshots are immutable. Status/result finalise on terminal state.
Historical schemas/context must remain readable after registry changes; rerun requires supported
current contract/model and explicit adaptation, not silent migration.

## Shared internal API and dependency contracts

All lab data routes use `X-Atom-Lab-Access-Code` and the server-owned lab tenant/region scope.
Public endpoints never accept lab access as a general override to normal platform authorization.
The static shell can load without the code but contains no protected data.

The common error envelope is `{error:{code,message,field_errors:[{path,message}]},request_id}`.
Paths are JSON field paths; messages are safe Russian copy, not echoed input/prompt/secret.
AL01 establishes this envelope; AL03/AL04/AL05 extend explicit error codes for their operations.
AL04 owns 202 run admission and run/history wire models; AL05 owns 201 preset version responses.
Business errors and malformed requests use the same envelope. Catalog refresh and generation are
different operations and never share a fake scenario/job identity.

Run status projects the existing lifecycle as `queued|running|succeeded|failed|expired|cancelled`;
no new workflow state machine. `result=null` until successful final validation.
IDs/timestamps/response model that do not yet exist are null, not invented.
Return `requested_model_id` separately from `response_model_id`; if the adapter's normalized model
falls back to the request, do not present that fallback as a provider-confirmed model ID.
Reasoning is requested and transmitted configuration, not an assertion about hidden model thinking.

Preset model settings use the same `model_id/reasoning_effort` names as run requests.
Save/new version is not generation or publication. A preset reference on an edited draft records
its provenance without merging or overwriting the visible run input.

Storage delivery order: AL02 creates run snapshots with nullable preset reference; AL05 creates
preset/version storage and referential checks; AL04 exposes validated run admission.
AL05 reads source runs directly from AL02 storage and does not depend on AL04 HTTP routes.
Thus AL02 -> AL05 -> AL04 is acyclic; AL03 and AL06 can proceed after AL01.
Catalog state storage is owned by AL03 and is separate from the run lifecycle.

Restart preserves accepted snapshots and history, not a promise of transparent provider-call resume.
An orphaned running job follows existing reconciliation and can fail with worker_lease_lost.
Explicit new experiments create new keys; validation/transport retries retain existing owners/caps.

## Implementation steps

Each issue owns its tests and documentation. First write a failing targeted regression/contract
test, implement the smallest slice, run the relevant canonical checks, and review the diff.
Do not postpone all testing to final QA.

### AL01 — [ANY-459](https://linear.app/paveldik/issue/ANY-459/atom-lab-zakrytaya-poverhnost-i-katalog-11-atomov): Atom Lab: закрытая поверхность и каталог 11 атомов

- [x] Implement and verify.
- Depends on: none.
- Files/areas: `apps/platform-api/src/anytoolai_platform_api/routers/demo.py (reference), routers/atom_lab.py (new), main.py, schemas.py`; `configs/kernel/products/kernel_demo`; `docs/core-beliefs.md`; `docs/product-specs/mvp-scope-source-of-truth.md`; `docs/architecture/frontend-boundaries.md`.

Разместить /atom-lab и защищённый /v1/atom-lab/* внутри platform-api. GET /atoms и /atoms/{id}: registry-owned live config, prompt, fixed input/output schemas+versions, русские объяснения и валидный пример для каждого из 11 атомов. Не копировать контракты в JS. Отдельный ANYTOOLAI_ATOM_LAB_ACCESS_CODE, fail closed, код только в памяти вкладки, не в логах/URL. Ввести внутреннюю классификацию лабораторных сессий/артефактов и запрет их чтения/действий через ВСЕ публичные session/result/artifact/handoff пути. Проверить реальные sibling endpoints, не только новый router. Публичные клиенты не получают model/prompt overrides. Синхронно оформить узкое исключение Atom Lab в controlling docs и architecture guards; опубликовать спецификацию/план. Старый /demo не удалять.

Acceptance: Без кода невозможно прочитать каталог/промпты или лабораторные данные; missing config закрывает доступ. Все 11 примеров проходят действующую входную валидацию. Поддельный публичный запрос не включает lab режим. Тесты доступа по известным lab IDs и regression обычных результатов; validate-docs, validate-architecture, quick-check.

### Уточнения после аудита

- [x] Первым изменением ANY-459 опубликовать спецификацию и этот план в репозитории до зависимой разработки. Одновременно описать узкое исключение внутреннего Lab в controlling docs и guards, не ослабляя публичные frontend boundaries.
- [x] Сервер создаёт доверенную маркировку lab scope; пользовательский input/metadata не может её включить. Определить проверку принадлежности session/job/action/artifact к lab через серверную связь с сессией, пригодную для хранилища ANY-460. До появления run API проверить guards на seeded fixtures. Отрицательные проверки охватывают чтение и действия публичных session/result/artifact/handoff маршрутов.
- [x] Добавить раннюю Compose/env-настройку отдельного lab access code на API, сохранить server live token и OpenAI key только у worker. Документировать закрытый локальный запуск и fail-closed режим; без production rollout и без секретов в git. Статический shell не содержит защищённых данных; запросы используют `X-Atom-Lab-Access-Code`.
- [x] Каталог атомов возвращает `atom_id, action_type, base_action_config_id, prompt, prompt_ref, input_schema, output_schema, schema_refs, description, example_input`. Схемы и промпт берутся из registry; описания подготовлены без LLM. `atom_id` — стабильный код A01–A11, а не произвольный scenario ID.
- [x] Приёмка: доступ к каталогу и seeded lab IDs закрыт без кода; обычные demo/results работают; все 11 примеров валидны. Добавить `apps/platform-api/tests/test_atom_lab_access.py` и `test_atom_lab_catalog.py`. Точная сериализация каталога и safe error envelope фиксируется API-моделями в этом PR.


### AL02 — [ANY-460](https://linear.app/paveldik/issue/ANY-460/atom-lab-neizmenyaemyj-snimok-nastroek-cherez-postgres-i-worker): Atom Lab: неизменяемый снимок настроек через Postgres и worker

- [x] Implement and verify.
- Depends on: ANY-459.
- Files/areas: `platform-core: scenarios/service.py, actions/executor.py, storage/db.py, storage/repositories.py`; `platform-actions: structured_llm/executor.py, pydanticai_runner.py`; `apps/platform-worker: handlers/run_workflow.py, composition.py`; `existing migration directory`.

Добавить atom_lab_runs с неизменяемым snapshot принятого запуска: action/config/schema refs+versions и достаточные сохранённые definitions, prompt, полный input, model/effort, capability provenance, preset version, runtime IDs. Типизированный validated override передавать из lab-only контекста через существующие session/job/ActionRunner к executor и ProviderGateway. Не мутировать shared registry/router configs. Prompt и provider policy разрешать локально для этого run и всех validation/transport retries. Существующие artifacts, action runs и provider-call ledger остаются единственными execution records. Не добавлять второй executor или native response_format. Обычные jobs работают без override. Snapshot фиксирует настройки и контекст; worker проверяет совместимость с registry при dequeue/retry и при несовместимости завершает запуск явной ошибкой, без silent migration.

Acceptance: Два lab запуска при повышенном test concurrency и обычный job не влияют друг на друга. Worker restart сохраняет snapshot; выполнение/завершение job следует существующим правилам reconciliation, без нового auto-resume. Snapshot принят до enqueue атомарно, нет orphan accepted runs. PostgreSQL tests; assertions фактического input/prompt/model/effort вплоть до вызова provider adapter; existing retry ownership и ledger tests, quick-check/postgresql-check.

### Уточнения после аудита

- [x] Сначала реализовать атомарный storage snapshot, затем laboratory workflow bindings, затем run-local provider settings. Каждый шаг — отдельный reviewable diff с собственным failing/passing тестом; тикет закрывается после интеграционной проверки всех трёх.
- [x] Добавить 11 allowlisted internal-only laboratory scenario/workflow definitions в существующий registry, используя те же live action configurations и атомные schema refs. Вход workflow — фиксированная входная схема атома; `input_mapping: {}` использует существующий `resolve_step_input` для передачи всего payload. Не переиспользовать smoke literals и не изменять существующие smoke workflows. Нового executor или изменения контрактов атомов нет.
- [x] Snapshot содержит полный атомный input, редактируемый prompt, base config/prompt provenance, schema refs/versions и сохранённое содержимое для чтения, workflow binding/version, выбранные model/reasoning, источник/версию capabilities, неизменные server policy limits и runtime IDs по мере появления. Сохранять минимальные execution definitions/hash, чтобы worker проверял совместимость, а не исполнял изменившийся registry молча. Новый framework для исполнения произвольных исторических definitions не нужен.
- [x] Сначала доступны `run_id, scenario_session_id, job_id`; `action_run_id` и `artifact_id` nullable до соответствующей стадии. Ошибка до создания action не требует выдуманного action ID.
- [x] Пресет на этом шаге необязателен: создать nullable `preset_id/preset_version` без зависимости от ещё не созданных preset tables. ANY-463 добавляет constraints/валидацию ссылки. Storage предоставляет создание snapshot в caller-owned transaction и чтение по run_id для ANY-463; публичный POST /runs появляется только в ANY-462.
- [x] Через typed run-local execution settings передать model/reasoning из доверенного snapshot в `ProviderRequest`, `ResolvedProviderRequest`, Gateway и LiteLLM adapter, включая validation/transport retries. Разрешение настроек не меняет глобальный Router или default policy. Выбранная реальная модель должна быть адресуемой адаптером, а не только известной строкой каталога; статический alias `anytoolai.default_text` не должен подменять выбор.
- [x] Владение фактическим применением model/effort — ANY-460; ANY-461 поставляет metadata, ANY-462 валидирует выбор при admission. Tests используют фиксированный capability fixture и не зависят от network catalog. Проверить аргументы непосредственно на вызове LiteLLM adapter, не ограничиваться mock Gateway; отсутствие effort не должно наследовать статический `medium`. Не вводить silent fallback/drop_params; при несовместимости server-owned дополнительных параметров — явная ошибка, без нового пользовательского редактора.
- [x] Изоляцию двух lab runs проверять с test concurrency >1 вместе с обычным job; default admission=1 не ослаблять. Проверить неизменность payload до ActionRunner для всех 11 атомов, включая значения, отличные от smoke literals.
- [x] Worker restart сохраняет snapshot/history. Ожидающий job выполняется по текущим правилам; прерванный running job получает существующий статус/error reconciliation (например worker_lease_lost). Автоматическое повторение платного вызова после crash не добавлять. Existing validation/transport retries сохраняются.
- [x] Дополнительные точки изменения: `configs/kernel/products/kernel_demo/workflows.yaml`, `scenarios.yaml`, `product.yaml`; `workflows/mappings.py` (reuse), `providers/models.py`, `providers/gateway/`, `providers/adapters/litellm.py`. Regression tests: `apps/platform-worker/tests/test_atom_lab_execution.py`, `apps/platform-api/tests/test_atom_lab_workflow_config.py`; PostgreSQL snapshot tests в existing storage suite.


### AL03 — [ANY-461](https://linear.app/paveldik/issue/ANY-461/atom-lab-obnovlyaemyj-katalog-openai-gpt-i-reasoning-capabilities): Atom Lab: обновляемый каталог OpenAI GPT и reasoning capabilities

- [x] Implement and verify.
- [x] Implementation branch: `feature/ANY-461`; ANY-459 and ANY-460 are integrated in `main`.
- [x] Preflight 2026-09-15: `python3 scripts/agent/runner.py doctor` found `uv`, Node and npm,
  but the Homebrew Python 3.14 interpreter lacks pytest, PyYAML and Pydantic. Use the
  repository-managed `.quick-check-venv`/runner commands for validation; do not install into the
  system interpreter.
- Depends on: ANY-459.
- Files/areas: `platform-core/src/anytoolai_platform_core/providers/ (catalog logic inside boundary), providers/adapters/litellm.py`; `apps/platform-worker`; `configs/kernel (small capability override YAML)`; `platform-api atom_lab router`; `storage/migrations`.

Получать доступные account model IDs OpenAI, совмещать с актуализируемым снимком LiteLLM metadata и небольшими YAML overrides с source/date. Priority override > metadata > unknown. Поддержка reasoning не доказывает список effort; неизвестное не равно unsupported. Допускать только подтверждённые text GPT для текущего prompted path, не фильтровать по native JSON Schema. API отдаёт модели, allowed efforts, compatibility reason, provenance, stale/last_success. GET /models; POST /models/refresh возвращает pending/running refresh status. Refresh обслуживается отдельным hook существующего worker loop через provider boundary и сохраняет last-good snapshot в PostgreSQL: OPENAI_API_KEY остаётся у worker, не добавлять его в API. Один refresh в работе, TTL 24h, rate limit refresh 60s, без платных probes. Проверить текущие provider/LiteLLM документы при реализации; не угадывать capabilities по имени.

Acceptance: Тесты new/removed model, unknown effort list, no reasoning, stale/failure, empty initial cache; native schema unsupported не исключает prompted-compatible модель. API и UI не содержат SDK/credentials. Каталог явно различает known/unknown/unsupported; отклонение при admission принадлежит AL04, отсутствие silent drop/fallback в adapter — AL02. Refresh не выполняет generation.

### Уточнения после аудита

- [x] Текущий worker не является очередью произвольных заданий: не помещать catalog refresh в workflow jobs и не создавать фиктивные scenario/action/provider-call rows.
- [x] Минимальный механизм: одна PostgreSQL cache/state запись на настроенный OpenAI account scope с last-good snapshot, due_at, refresh_requested_at, lease_until, last_success_at и safe last_error. POST /models/refresh только атомарно помечает запрос; worker обслуживает его на старте и между workflow jobs. Наступление TTL также делает refresh необходимым. Один bounded refresh с DB lease; после crash lease истекает, запрос подхватывается снова. Обычный длинный workflow может задержать refresh — API честно показывает pending/stale, не обещает мгновенность.
- [x] Refresh обновляет OpenAI IDs и валидируемый LiteLLM JSON snapshot; сохраняет только последний целостный корректный результат. Credentials, base URL, policy limits не берутся из внешних metadata. Никаких generation probes, новой очереди общего назначения или отдельного scheduler service.
- [x] GET /models возвращает `items, snapshot_id, last_success_at, stale, refresh_status, error`. У item: `model_id, compatibility, reason, reasoning_supported, allowed_reasoning_efforts, provenance`; unknown — явно unknown/null, а не false. Исчезнувшая модель не разрешается override. POST refresh возвращает 202 и pending/running состояние; GET models служит polling endpoint.
- [x] Empty cache: items пуст, execution disabled, refresh error видна; last-good stale cache остаётся доступен с предупреждением. TTL и cooldown — именованные backend settings. Подготовить worker Compose/env wiring в этом тикете; key остаётся только worker.
- [x] Каталог не реализует применение provider параметров повторно: это ANY-460. Проверки ANY-461: initial load, TTL без кликов пользователя, manual refresh, coalescing/cooldown, expired lease, restart, upstream failure/invalid JSON, model removal, unknown capabilities. API parsing и refresh tests плюс PostgreSQL lease tests; `apps/platform-worker/src/anytoolai_platform_worker/worker.py` и `composition.py` входят в scope.

### PR #126 review follow-up

- [x] Не брать новый workflow job, если shutdown был запрошен во время catalog refresh.
- [x] Не публиковать success/failure после истечения lease по времени PostgreSQL.
- [x] Строго валидировать source и ISO date в capability overrides.
- [x] Не срывать целый refresh на неизвестном LiteLLM reasoning effort; сохранять support и
  трактовать точный список как unknown.
- [x] Не возвращать refresh_status=current в retry window после failed refresh.
- [x] Не сохранять неиспользуемые полные upstream documents в polling-row каталога.
- [x] Типизировать закрытый wire-набор catalog reason codes.
- [x] Валидировать lease против фактического aggregate refresh deadline.
- [x] Добавить service-level regression для failed refresh с сохранением last-good snapshot.
- [x] Добавить read-only due fast path перед atomic lease claim, чтобы idle poll не писал и не
  блокировал catalog row.
- [x] Вычислять lease expiry по PostgreSQL clock и оставить достаточный publish budget.
- [x] Не создавать failing refresh hook в credential-free worker composition.
- [x] Закрепить HTTP-контракт stale last-good snapshot после refresh failure.
- [x] Сохранять manual refresh как pending во время cooldown и исполнять после его окончания.
- [x] Читать актуальную LiteLLM форму reasoning efforts: `reasoning_effort_levels` и per-level flags.
- [x] Использовать PostgreSQL clock для durable `due_at` eligibility и finalizer scheduling.

Не приняты предложения менять inclusion semantics для audio-capable/unsupported моделей и выносить
refresh из worker loop: они противоречат зафиксированным правилам AL03 и
`docs/architecture/provider-gateway.md`. Отдельный client-visible not-configured error не добавлен:
credential-free worker не запускает refresh hook и не создаёт ложный upstream failure; при реальной
ошибке настроенного источника generic client message остаётся безопасным, а detail пишется в log.
Строгий LiteLLM root parser оставлен fail-closed: проверенный 2026-09-15 live snapshot содержит
3958/3958 object-valued model entries и не содержит underscore-prefixed служебных ключей.


### AL04 — [ANY-462](https://linear.app/paveldik/issue/ANY-462/atom-lab-zapusk-atoma-i-zashishyonnaya-postoyannaya-istoriya-api): Atom Lab: запуск атома и защищённая постоянная история API

- [x] Implement and verify.
- Depends on: ANY-460, ANY-461, ANY-463.
- Files/areas: `platform-api routers/atom_lab.py, schemas.py`; `platform-core scenarios/service.py, storage repositories`; `worker terminal status/diagnostics integration`.

POST /runs принимает atom_id, input, prompt, model_id, reasoning_effort, optional preset_ref и Idempotency-Key; сервер валидирует фиксированный контракт, allowlist и capability snapshot. Использовать internal laboratory workflows из AL02 с полным payload и server live token; старые smoke bindings не использовать. Сохранить стабильную identity для одного idempotent submission; новый guest на retry недопустим. Same key+body возвращает тот же run, different body ->409. GET /runs cursor pagination, GET /runs/{id} — защищённые snapshot/status/result/diagnostics. Показывать все accepted runs, включая failed/running; не дублировать execution ledger. Лимиты defaults: input JSON 256KiB, prompt UTF-8 64KiB, общий request 384KiB, 100 accepted/day UTC, 1 active lab run; backend configurable. Сериализовать admission в PostgreSQL, чтобы quota/idempotency атомарны. Pre-start errors не расходуют лимит. Диагностика invalid output ограничена lab; не публиковать secret/hidden reasoning. Validation attempts, transport attempts и physical calls различать; actual response model != подтверждение effort.

Acceptance: Первый полный API vertical slice одного атома проходит existing worker; 11 mappings валидны. Concurrent duplicate starts дают один логический job; физические provider calls учитываются отдельно с разрешёнными runtime retries. Закрытие вкладки/restart не теряют историю. Pagination stable; terminal result immutable; unknown historical contract/model читается без silent migration. Tests oversized/unicode/auth/limits/races/failures; PostgreSQL checks.

### Уточнения после аудита

- [x] Зависимости: ANY-460 (snapshot и laboratory workflows), ANY-461 (catalog), ANY-463 (preset version validation). Порядок AL-номеров не означает порядок разработки.
- [x] POST /runs body: `{atom_id, input, prompt, model_id, reasoning_effort, preset_ref?}`; `preset_ref={preset_id,version}`, effort nullable. Extra fields запрещены. `input` — полный видимый payload, без скрытого merge со saved preset. Ссылка на пресет — provenance; допустим изменённый draft, который явно отличается от версии. Проверить существование и соответствие атома/контракта пресета; не выдавать draft за неизменённый preset.
- [x] Сервер сам разрешает laboratory scenario по atom_id; принимает только указанный atom contract. Прямые scenario IDs, arbitrary provider/base URL/credentials и schema overrides не принимаются.
- [x] Auth выполняется до idempotency lookup. Scope ключа — внутренняя lab область tenant/region. Hash охватывает atom, полный input, prompt, model/effort и preset reference; JSON порядок ключей не влияет. Повтор accepted key+hash возвращает существующий run даже если модель исчезла/лимит исчерпан позже; другой hash ->409. Новому ключу — новая серверная guest identity, retry того же ключа использует сохранённую. Snapshot+session+job и admission count атомарны; не держать admission lock во время provider call.
- [x] Успешный POST возвращает 202: `{run_id,scenario_session_id,job_id,status}`. GET /runs — `{items,next_cursor}`, стабильная сортировка created_at+run_id, limit default 20/max100. GET /runs/{id} — `{run_id,status,snapshot,runtime_ids,result,diagnostics,created_at,started_at,finished_at}`. result только при успешной финальной валидации; диагностика отдельно. nullable IDs/времена не заменять фиктивными значениями.
- [x] Safe error envelope: `{error:{code,message,field_errors:[{path,message}]},request_id}`. 401 access_denied; 404 lab resource not found; 409 idempotency_conflict/preset_mismatch/contract_unavailable; 413 payload_too_large; 422 input_invalid/model_not_allowed/reasoning_not_allowed; 429 lab_busy/daily_limit_exhausted; 503 lab_unavailable/catalog_unavailable. Framework parsing errors привести к этому формату. Не включать секреты или полный prompt/input в ошибки/логи.
- [x] Размеры считать в UTF-8 по документированному JSON encoding, отдельно лимитировать raw request body; проверить unicode и JSON escaping. Начальные лимиты — технические defaults из плана, не изменение атомных схем и не гарантия попадания в context window.
- [x] Worker/executor сохраняют bounded contract-failure diagnostics в lab storage по run_id без второго ledger; счётчики берутся из существующих semantic/transport/physical indices. Успех с первой попытки различим от успеха после валидационных исправлений. Невалидный текст — защищённая диагностика с признаком truncation при ограничении, не successful artifact. Terminal projection не теряет сведения при restart/reconciliation.
- [x] Один idempotent submission означает один логический job, не обещание одного physical provider call: разрешённые retries остаются. Проверить одинаковые key requests в гонке, replay после terminal/исчезновения модели, падение transaction и worker_lease_lost. Для каждого из 11 атомов submitted input == snapshot input == ActionRunner input; проверить optional omissions/null/false/0 и нестандартные поля из контракта. API tests: `apps/platform-api/tests/test_atom_lab_runs.py`, `test_atom_lab_history.py`.

#### Execution checklist (2026-09-18)

The approved specification and AL04 requirements above are the design source. Implementation stays
inside the existing Atom Lab snapshot/runtime path and proceeds with these independently verifiable
TDD slices.

- [x] **Slice 1 — durable serialized admission and idempotency.** Add failing repository/service
  tests in `packages/backend/platform-core/tests/unit/test_atom_lab_run_admission.py` for canonical
  JSON hashing, stable guest/run replay, conflict, UTC daily rollover, active-run exclusion and
  concurrent PostgreSQL starts. Extend `migrations/platform/versions/0015_atom_lab_run_admission.py`,
  `storage/db.py`, `atom_lab/models.py` and `atom_lab/repository.py` with a tenant/region admission
  lock row and scoped unique idempotency fields. Implement `atom_lab/service.py` so the locked
  transaction creates guest identity, scenario session, job and immutable snapshot together, then
  run the focused unit tests and PostgreSQL marker tests.
- [x] **Slice 2 — strict protected POST `/v1/atom-lab/runs`.** First add failing cases to
  `apps/platform-api/tests/test_atom_lab_runs.py` for auth-before-lookup, required idempotency key,
  forbidden extra fields, raw/input/prompt UTF-8 limits, all 11 exact input contracts, model/effort
  capability validation, preset provenance, replay and the documented safe error codes. Add the
  request/response models and configurable defaults in `schemas.py`/`settings.py`, then the smallest
  router orchestration in `routers/atom_lab.py`. Verify red then green with the exact test module.
- [x] **Slice 3 — persistent history projection.** Add failing list/detail tests in
  `apps/platform-api/tests/test_atom_lab_history.py` for `created_at + run_id` keyset ordering,
  running/failed/succeeded runs, nullable runtime IDs/timestamps, immutable normalized result,
  unknown historical model/contract readability and distinct validation/transport/physical counts.
  Add scoped projection queries to the Atom Lab repository/service and the exact list/detail wire
  models without copying the runtime ledger.
- [x] **Slice 4 — bounded terminal diagnostics and vertical integration.** Add failing worker tests
  for final invalid output, provider failure and `worker_lease_lost`, proving bounded/truncated raw
  contract diagnostics are Atom-Lab-only and survive reconciliation. Reuse the existing worker
  reconciliation and structured-output debug-artifact recovery boundary; add API/worker
  integration coverage proving one accepted submission creates one logical job while runtime retries
  retain separate provider-call rows. Run targeted suites, `quick-check`, real `postgresql-check`,
  `full-check`, generated OpenAPI drift checks and architecture/docs validation before completion.


### AL05 — [ANY-463](https://linear.app/paveldik/issue/ANY-463/atom-lab-biblioteka-neizmenyaemyh-versij-presetov-i-eksport-api): Atom Lab: библиотека неизменяемых версий пресетов и экспорт API

- [x] Implement and verify.
- Depends on: ANY-459, ANY-460.
- Files/areas: `platform-api atom_lab router/schemas`; `platform-core storage repositories/db`; `existing migration directory`.

Общая для команды библиотека: GET/POST /presets, GET /presets/{id}/versions/{version}, POST /presets/{id}/versions, GET /presets/{id}/versions/{version}/export. PostgreSQL preset identity + immutable versions, optimistic base_version check и атомарная нумерация. Сохранять имя/описание, atom/base config/schema refs+versions, prompt/provenance, model/effort, fixed top-level fields, пример входа, optional source run. Фиксация целого поля, без произвольных JSON paths; запуск использует видимый полный payload, нет скрытого overwrite. Export versioned JSON secret-free, достаточный для ручного переноса в YAML/prompt/provider policy через review. No production config DB registry, import, auto PR, delete UI. Недоступная модель/старый контракт не лишают чтения пресета; запуск требует явной адаптации.

Preset identity относится ровно к одному `atom_id`; новые версии могут обновлять contract/schema/prompt
версии, но не могут менять атом. Tenant/region пресета берутся из того же server-owned
`Settings.default_tenant_id/default_region`, который API использует при создании scenario sessions;
lab ownership определяется typed `RuntimeScope.atom_lab`, а repository дополнительно сохраняет и
сверяет scope для source-run и run-to-preset связей. Отдельных Atom Lab tenant/region literals нет.

Acceptance: Сохранение и reopen после restart, immutable old versions, concurrent save -> conflict без потери данных. Создание, чтение, версионирование и экспорт защищены; удаление не входит в v1. Сохранение не вызывает LLM и не меняет production. Невалидные refs/fields отвергаются; source run проверяется в lab scope. PostgreSQL tests и export fixture с точными полями/без secrets.

### Уточнения после аудита

- [x] Зависит от ANY-460, а не от будущего runs API: источник запуска читать из уже созданного lab storage. Добавить constraints для nullable run->preset/version references после создания preset tables. Это позволяет ANY-462 зависеть от ANY-463 без цикла.
- [x] Version payload: `{name,description,atom_id,base_action_config_id,schema_refs,prompt,prompt_ref,model_id,reasoning_effort,fixed_fields,example_input,source_run_id?}`. `fixed_fields` — уникальные имена целых верхнеуровневых полей; их значения находятся в example_input. Остальные поля контракта считаются runtime inputs. Схема атома не редактируется.
- [x] POST /presets создаёт identity и v1 атомарно. POST /presets/{id}/versions принимает version payload и `base_version`; успешный ответ 201 с `preset_id,version,created_at`, stale base ->409 `preset_version_conflict`. GET /presets — paginated identities; добавить GET /presets/{id}/versions для списка версий, detail/export — существующие version endpoints.
- [x] Проверить source_run_id в lab scope и соответствие atom/schema provenance. Ссылка означает происхождение, а не доказательство идентичности настроек или качества результата. Черновой пресет можно сохранить без successful run; не ставить статус «проверен» автоматически. Невалидный input не проходит contract validation, но плохой по смыслу prompt допустим.
- [x] Экспорт конкретной версии: `{format_version:1,preset_id,version,configuration}`, configuration содержит version payload без credentials, provider base URL и внутренних auth данных. Модель/effort — настройки для ручного переноса в provider policy, не raw поля production action config. Runtime не читает production configs из этой библиотеки.
- [x] Чтение старых версий не требует доступности модели. Сохранённые schema/provenance сведения остаются читаемыми; ANY-462 проверяет совместимость перед новым запуском. Contract tests покрывают exact export fields, conflicts, scope, разные версии и отсутствие LLM вызова при save. Добавить `apps/platform-api/tests/test_atom_lab_presets.py`; error envelope совпадает с разделом API плана.

AL05 API errors: `404 preset_not_found`; `409 preset_version_conflict`; `422
preset_contract_invalid`, `preset_source_run_invalid` или `invalid_cursor`; `503
atom_lab_catalog_unavailable`. Оба list endpoint возвращают `{items,next_cursor}` с opaque cursor и
стабильным keyset order. Export возвращает ровно
`{format_version:1,preset_id,version,configuration}`; `configuration` — secret-free version payload
для ручного переноса через review, а не runtime production registry.


### AL06 — [ANY-464](https://linear.app/paveldik/issue/ANY-464/atom-lab-vybor-atoma-pasport-formy-vseh-kontraktov-i-redaktor-prompta): Atom Lab: выбор атома, паспорт, формы всех контрактов и редактор промпта

- [x] Implement and verify.
- Depends on: ANY-459.
- Files/areas: `apps/platform-api/src/anytoolai_platform_api/static/atom_lab/ (new)`; `API page tests`; `existing browser test harness`.

Русскоязычная страница без нового frontend deployment/framework: sidebar 11 атомов; паспорт назначения/input/transformation/output; readonly schemas; form/JSON один payload; input/prompt tabs, восстановление base prompt и valid example. Поддержать ВСЕ поля текущих 11 схем: nested objects, arrays, enum, dynamic dictionaries; optional omission отдельно от null/empty/false/0. Не перекладывать неизвестные поля только в JSON на нетехнического пользователя. Невалидный JSON не теряется при переключении и блокирует запуск. Состояние результата не подменяется новым draft. Предупреждать о потере dirty draft при atom/preset/history/example/reset навигации. Доступ проверять сервером до отображения protected data.

Acceptance: Матрица schema features по 11 атомам покрыта runnable UI tests; form->JSON->form сохраняет payload точно. Читаемые path validation errors, readonly contracts, keyboard/focus/labels, narrow-screen layout. textContent/safe rendering, без secret storage. Browser check и page/assets tests.

### Уточнения после аудита

- [x] Контракт UI — каталог из ANY-459 и единый JSON-совместимый draft. Переключение Form/JSON не добавляет defaults, не удаляет пустые допустимые значения и не превращает omitted в null. Проверка exact payload round-trip параметризована по всем 11 атомам.
- [x] Этот тикет отвечает за точность browser payload; равенство submitted/snapshot/executor payload проверяется в ANY-462 и ANY-467, без скрытой зависимости формы от ещё не готового run API.
- [x] Упаковка static assets и локальная browser-test команда входят в этот PR, а не ждут ANY-468. Использовать установленный browser test harness; зафиксировать запускаемую команду и подключение tests к canonical checks. Проверка наличия строк в HTML не заменяет интерактивные тесты.
- [x] Ошибки по path из safe API envelope привязаны к контролам; невалидный JSON сохраняется дословно до исправления. Секрет только в памяти вкладки, после reload требуется новый вход, но server history не теряется.


### AL07 — [ANY-465](https://linear.app/paveldik/issue/ANY-465/atom-lab-gptreasoning-zapusk-i-chitaemyj-rezultat-v-ui): Atom Lab: GPT/reasoning, запуск и читаемый результат в UI

- [x] Implement and verify.
- Depends on: ANY-462, ANY-464.
- Files/areas: `static/atom_lab/`; `API/browser tests`.

Подключить модели из backend catalog, supported effort selector, unsupported hidden/disabled с пояснением, unknown отдельно, stale banner/refresh. Отправлять current draft с idempotency key; network retry того же submission не создаёт новый run, явный новый запуск — новый key. Poll только protected lab endpoint. Pending/reconnecting/failed/completed показывают реальное состояние, browser timeout не отменяет job. Результат читабельный со всеми значимыми полями и JSON; invalid response отделён от successful artifact. Показывать run snapshot отдельно от изменяемого draft, duration/requested model/response model/effort/validation and transport attempts, IDs в diagnostics. No chain progress fiction; no native schema toggle.

Acceptance: Browser scenarios success/validation correction/final invalid/provider error/network recovery/unsupported selection; double click и повтор transport request не удваивают run. Result не исполняет HTML. Редактирование draft во время/после запуска не меняет displayed run configuration. Один реальный атом end-to-end плюс детерминированные UI tests.

### Уточнения после аудита

- [x] Раздельные сущности UI: editable draft, immutable submitted snapshot, response-derived metadata. Для запуска использовать `model_id/reasoning_effort` и response shape ANY-462; catalog fields — ANY-461. Изменение формы не переписывает карточку уже принятого запуска.
- [x] Подписи: «Запрошенная модель», «Модель в ответе», «Запрошенный reasoning». Отсутствие provider-confirmed effort не трактовать как подтверждение; unknown response model отображать как неизвестную, не подставлять запрос.
- [x] Browser timeout/network loss оставляют возможность повторного чтения принятого run. Running job после crash может завершиться ошибкой текущего runtime; не показывать автоматическое возобновление или повторять POST с новым key.
- [x] В acceptance связать browser-selected настройки с adapter-call evidence ANY-460/467, а не только текстом dropdown. Проверить согласованные safe error codes, last-good stale catalog и сохранение draft после отказа admission.


### AL08 — [ANY-466](https://linear.app/paveldik/issue/ANY-466/atom-lab-presety-eksport-i-vosstanovlenie-istorii-v-ui): Atom Lab: пресеты, экспорт и восстановление истории в UI

- [x] Implement and verify.
- Depends on: ANY-463, ANY-465.
- Files/areas: `static/atom_lab/`; `browser/API integration tests`.

Библиотека: создать пресет/открыть/выбрать immutable version/сохранить новую, имя и описание, fixed top-level field controls, source run, export конкретной версии. Отображать draft vs saved version. Save conflict сохраняет local draft и предлагает актуальную версию либо новый пресет. История общая, paginated, включает running/failed; reopen detail после закрытия страницы. Restore snapshot заполняет форму, не запускает платный вызов. Save preset из history использует именно выбранный snapshot, не несвязанный current draft. Unavailable model/contract показывать явно, historical data readonly без silent migration; unsaved warning.

Acceptance: Browser test полного пути input+prompt -> run -> save v1 -> change -> save v2 -> reopen v1 -> export -> reload -> history restore. Обе версии неизменны; восстановление не увеличивает provider calls; concurrency conflict не теряет draft. Ошибка сохранения оставляет значения; все reads/writes защищены.

### Уточнения после аудита

- [x] Использовать `preset_id/version/base_version`, version-list endpoint и export format из ANY-463; history snapshot/runtime IDs/error envelope из ANY-462. Раскрытие старой версии не заменяет её автоматически latest.
- [x] Восстановление заполняет `model_id/reasoning_effort` и полный snapshot input; требует отдельного клика «Запустить». Сохранение из history получает source_run_id выбранного запуска, а изменения после восстановления остаются draft.
- [x] Проверить историю crash-failed job, nullable action/artifact IDs, success-after-validation-retry и конфликт сохранения с сохранением локального draft. При несовместимости текущего контракта исторический snapshot остаётся доступен для чтения; адаптация только явным действием.

Implementation slices:

- [x] **Slice 1 — strict browser contracts and workspace state.** Add exact parsers for paginated
  preset/version/history responses, immutable preset detail/export and historical run detail. Track
  selected saved version, source run, fixed top-level fields and draft-vs-saved state without
  weakening the existing run-admission parsers.
- [x] **Slice 2 — preset library and optimistic saves.** Add the protected paginated library,
  version picker, create/new-version forms, top-level fixed-field controls and concrete-version
  export. Preserve all local values on API failures; on `preset_version_conflict`, keep the draft
  and offer explicit latest-version reload or save-as-new-preset actions.
- [x] **Slice 3 — durable history and explicit restore.** Add protected paginated run summaries and
  detail reopening for queued/running/failed/succeeded states. Restore the exact snapshot input,
  prompt, model and reasoning only after an explicit user action, never submit automatically, and
  carry the selected `source_run_id` when saving that restored snapshot.
- [x] **Slice 4 — browser acceptance and repository validation.** Cover the complete
  run -> preset v1 -> v2 -> reopen v1 -> export -> reload -> history restore journey, immutable
  versions, nullable runtime IDs, validation-retry success, crash failure, no provider-call increase
  on restore, protected requests, conflict/error draft retention, dirty navigation and inaccessible
  historical model/contract states. Run focused Node/Chromium checks, lint, quick-check and the
  broader applicable repository gates.


### AL09 — [ANY-467](https://linear.app/paveldik/issue/ANY-467/atom-lab-v1-priyomka-vseh-11-atomov-i-regressiya-production-puti): Atom Lab v1: приёмка всех 11 атомов и регрессия production пути

- [ ] Implement and verify.
- Depends on: ANY-466.
- Files/areas: `apps/platform-api/tests`; `platform-worker/tests`; `existing atoms-proof/live-canary harness`; `docs (acceptance evidence)`.

Собрать итоговую проверку поверх тестов feature PRs, не переносить сюда их ответственность. Live evidence всех 11 атомов на доступной разрешённой GPT через Atom Lab API -> Postgres -> worker; отдельные smoke combos supported reasoning. Зафиксировать IDs/model/date/input validity/result validity, без secrets. Проверить неизменённый PromptedOutput/runtime retries/physical-call ledger и отсутствие влияния lab overrides на обычные jobs. Security обход через public result/session/artifact/handoff; restart и idempotency; preset conflict; form field coverage; history failures. Язык результатов проверять через фактический prompt/input, не вводить скрытое language rule. Использовать существующий harness, не создавать второй benchmark. Fake fixtures не evidence живого провайдера.

Acceptance: 12 критериев спецификации имеют ссылки на tests/manual/live evidence. quick-check, full-check, postgresql-check с реальным test DB, validate-docs/architecture зелёные; credentialed live check выполнен. При отсутствии credentials/evidence задача и release остаются blocked, а не принимаются по fake/skip green. Ни одной новой обязательной MVP-A1 gate зависимости. Обнаруженные defects оформлены/исправлены до v1 acceptance.

### Уточнения после аудита

- [ ] Для всех 11 лабораторных workflow проверить равенство form/submitted/snapshot/ActionRunner input, используя значения, отличные от smoke literals. Старые smoke config/proof tests должны остаться зелёными.
- [ ] Проверить model/effort непосредственно на вызове provider adapter: выбор не теряется в Router alias, не наследует medium при отсутствии effort, не меняет соседние jobs и не сбрасывается на retry. Fake instrumentation доказывает plumbing; отдельно credentialed live evidence доказывает реальные прогоны.
- [ ] Crash/restart matrix: pending job, прерванный running job с existing reconciliation, terminal job; история не теряется, restart сам не создаёт повторного платного запуска. Различать logical jobs, validation attempts и physical calls.
- [ ] Проверить catalog initial/TTL/manual update и восстановление lease без workflow jobs, а также preset/run dependency integration и публичные обходы lab доступа.
- [ ] Ранняя Compose/env/asset подготовка уже выполнена в ANY-459/461/464, поэтому QA не блокируется будущим ANY-468. Не закрывать приёмку при отсутствии live credentials/evidence: это blocker, а не альтернативное успешное условие.


### AL10 — [ANY-468](https://linear.app/paveldik/issue/ANY-468/atom-lab-v1-compose-razvyortyvanie-i-vnutrennij-runbook): Atom Lab v1: Compose-развёртывание и внутренний runbook

- [ ] Implement and verify.
- Depends on: ANY-467.
- Files/areas: `infra/compose/docker-compose.yml, infra/compose/.env.example, infra/deployment/README.md`; `API/worker packaging`; `docs/exec-plans/active/atom-lab-v1.md`.

Проверить упаковку static assets, миграции и env wiring в существующем Compose stack. Отдельный lab access secret только API; live token server-side; OpenAI key только worker. Документировать HTTPS/internal network gate, refresh/catalog stale troubleshooting, backend limits, shared history/presets data handling, backup существующего Postgres и recover/rollback без удаления history. /demo и обычный runtime остаются работоспособны. Никаких новых сервисов/SSO/базы/публичной раздачи кода. Оператор задаёт секреты и разрешённый внутренний адрес; если их нет, остановиться на проверенном deployment package и явно не заявлять rollout.

Acceptance: Compose smoke: migrations, API/worker ready, assets доступны, missing/wrong lab secret fail closed, valid access -> реальный run -> история после restart. Документирована ротация access code и ограничение совместного доступа. Для закрытия задачи в evidence есть фактический адрес и операторская проверка; при blocker задача остаётся незавершённой; код доступа не в Linear/git/logs. План отмечать completed только после приёмки.

### Уточнения после аудита

- [ ] Scope этого тикета — финальное внутреннее развёртывание, операторская проверка и runbook после ANY-467. Не откладывать сюда создание dev/test окружения: auth/env принадлежит ANY-459, catalog worker wiring — ANY-461, static assets/browser setup — ANY-464.
- [ ] Повторно проверить migration/backup и безопасный rollback существующего Postgres без удаления presets/history, обновление каталога и ротацию lab code. На restart не обещать автоматический resume прерванного provider call.
- [ ] При отсутствии согласованного внутреннего адреса, секретов или rollout authority оставить rollout blocked и явно указать что package проверен, но развёртывание не завершено. Ни эта задача, ни milestone не считаются выполненными по одному наличию blocker report.


## Validation

- [x] Planning environment: python scripts/agent/runner.py doctor passed 2026-09-09.
- [ ] Each feature: targeted unit/API/browser tests (fail before implementation, pass after).
- [ ] python scripts/agent/runner.py quick-check
- [ ] python scripts/agent/runner.py full-check
- [ ] python scripts/agent/runner.py postgresql-check with a real test database.
- [ ] python scripts/agent/runner.py validate-docs
- [ ] python scripts/agent/runner.py validate-architecture
- [ ] Credentialed lab end-to-end evidence for 11 atoms; fixtures do not prove live compatibility.
- [ ] Existing /demo and ordinary production runtime regressions.
- [ ] Actual internal deployment smoke after operator configuration.

## Specification coverage

| Spec acceptance | Delivery |
| --- | --- |
| 1. Registry catalog, descriptions, 11 atoms | AL01, AL06 |
| 2. Every schema input shape and exact executed payload | AL02, AL04, AL06, AL09 |
| 3. Prompt editing; immutable contracts | AL02, AL06 |
| 4. Run-local prompt/model/effort through worker and retries | AL02, AL03, AL04 |
| 5. Production prompted output and validation | AL02, AL09 |
| 6. Models/capabilities/staleness/errors | AL03, AL07 |
| 7. Preset versions and concurrent saves | AL05, AL08 |
| 8. Exact history and attempt diagnostics | AL02, AL04, AL08 |
| 9. Durable runs, reconnection and idempotency | AL04, AL07, AL08 |
| 10. Secret-free export and reviewed reuse | AL05, AL08 |
| 11. Internal access and public API isolation | AL01, AL04, AL05, AL09 |
| 12. Accessible usable UI and dirty draft protection | AL06, AL07, AL08 |

## Decision log

| Date | Decision | Why |
| --- | --- | --- |
| 2026-09-09 | Separate Linear project, one v1 milestone | Long-lived internal tool, future chains are not v1 backlog promises. |
| 2026-09-09 | Reuse platform-api/worker/PostgreSQL | User explicitly requires production runtime path. |
| 2026-09-09 | Worker-owned catalog refresh | Preserve existing provider credential boundary. |
| 2026-09-09 | Guard public sibling endpoints before accepting lab runs | A protected start endpoint alone does not protect results. |
| 2026-09-09 | Keep all new issues in Backlog, no assignees/dates | Staffing and release schedule not agreed. |

## Progress log

| Date | Progress | Next |
| --- | --- | --- |
| 2026-09-09 | Inspected demo/runtime flow and existing Linear work; created project, milestone and ten dependency-linked tickets. | Start AL01; no implementation has been performed. |
| 2026-09-09 | User approved audit corrections: full-payload lab bindings, adapter settings, worker refresh mechanism, preset dependencies, recovery semantics and early test environment. | Ten existing tickets synchronized and read back; implementation remains unstarted. |
| 2026-09-14 | ANY-460 started on `feature/ANY-460`; confirmed ANY-459 is the branch base, reviewed the approved Atom Lab spec/AL02 contracts, and selected immutable snapshot + registry compatibility hash + typed run-local execution settings. `doctor` under system `python3` reported missing pytest/yaml/pydantic, while the repository-managed `.quick-check-venv` is present for canonical checks. | Add failing storage, config, worker/provider isolation tests before implementation. |
| 2026-09-14 | Implemented AL02: migration/repository snapshot, 11 internal full-payload bindings, worker compatibility loading, typed prompt/model/effort/policy propagation, direct LiteLLM model addressing, fill-once runtime links, and ordinary-job isolation. TDD regressions, `quick-check` (1283 passed) and a real PostgreSQL `postgresql-check` completed successfully, including three-worker concurrency and restart coverage. | Review and commit ANY-460. |
| 2026-09-16 | Implemented AL05/ANY-463: immutable preset identities and versions, optimistic concurrent saves, source-run and contract validation, protected list/detail/version/export APIs, run-to-preset integrity constraints, and exact secret-free export. Added API, SQLite, and real PostgreSQL concurrency coverage; regenerated OpenAPI and frontend contracts; `quick-check`, `postgresql-check`, and `full-check` passed. | Review and commit ANY-463, then continue with ANY-462/AL04. |
| 2026-09-17 | Addressed PR #128 review: unified preset/run tenant-region scope through API settings, made `atom_id` an identity invariant, hardened cursor/model/validator boundaries, expanded deterministic pagination/error/source-run coverage, and documented AL05 error/list/export contracts. `quick-check` (1358 passed), real PostgreSQL `postgresql-check`, Ruff, docs checks, and `full-check` passed. | Commit and push review fixes; resolve review threads after GitHub readback. |
| 2026-09-18 | Addressed follow-up PR #128 review: bounded serialized preset `example_input` at a configurable 256 KiB default, rejected whitespace-only required text, enforced strict bounded cursors, and made migration 0014 repair partially created preset schemas object-by-object. Added API regressions and a real PostgreSQL partial-schema migration test. | Run repository-wide validation, commit and push the fixes, then resolve the `gushinets` review threads after GitHub readback. |
| 2026-09-20 | Started AL07/ANY-465 on `feature/ANY-465`; reviewed the approved Atom Lab spec, backend catalog/run contracts, existing editor and browser harness. The bounded design separates editable draft, immutable submitted snapshot and response metadata; `doctor` under system `python3` reported missing pytest/yaml/pydantic, so canonical validation will use the repository-managed environment. | Add failing model-selection, idempotent submission/polling and safe-result UI tests before implementation. |
| 2026-09-20 | Implemented AL07/ANY-465: capability-aware model/reasoning controls, stale catalog refresh, immutable idempotent submissions, protected polling with reconnect/timeout/manual reread, safe readable result/invalid-output views, strict response parsing and full diagnostics. Verified 26 deterministic Node tests, 22 Chromium journeys, 13 API-to-worker adapter tests, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed); independent review found no remaining Critical/Important issues. `frontend-check` was also attempted but the unrelated web-mirror suite fails under local Node 26 because its jsdom `window.localStorage` is unavailable. | Review and commit ANY-465, then continue with AL08/ANY-466. |
| 2026-09-20 | Addressed PR #138 review: catalog refresh preserves still-valid model/reasoning choices; catalog polling is single-chain, deadline-bounded and cleaned up; transport replay bypasses mutable draft/catalog validation and reuses the frozen request. Added red-green regressions for all three paths (27 Node tests and 22 Chromium journeys). | Run the full Node 22 gate, push the review commit and resolve the inline threads. |
| 2026-09-21 | Addressed the second PR #138 review: model-catalog and run-detail closed values now parse fail-closed; an unaccepted submission cannot replace or mix with the accepted-run card; and a terminal replay keeps Run blocked until its protected detail is loaded. Added red-green malformed-boundary and consecutive/recovered-run regressions (28 Node tests and 23 Chromium journeys). | Run the full Node 22 gate, push the review commit and resolve the inline threads. |
| 2026-09-21 | Addressed follow-up PR #138 teardown feedback: run polling now tracks its scheduled timer and active abort controller, rejects work after destroy, and cancels both on page teardown. Added a red-green active-read teardown regression (29 Node tests). | Re-run the full Node 22 gate, push the follow-up commit and reply to the inline thread. |
| 2026-09-21 | Addressed further PR #138 idempotency and availability feedback: unresolved submission outcomes keep the primary Run action blocked so only the frozen replay can proceed; retryable run reads use deadline-bounded exponential backoff and honor valid `Retry-After`. Added red-green coverage (30 Node tests and 23 Chromium journeys). | Run the full Node 22 gate, push the review commit and resolve the inline threads. |
| 2026-09-21 | Addressed the next PR #138 review round: transient catalog reads retain the last-good selectable snapshot and continue refresh polling; persisted execution snapshots no longer overwrite immutable submitted configuration; authoritative admission field errors remain actionable; reconnect copy no longer invents workflow state; and IDs from the accepted envelope render before detail recovery. Added red-green coverage with real execution-snapshot fixtures (31 Node tests and 25 Chromium journeys). | Run the full Node 22 gate, push the review commit and resolve the inline threads. |
| 2026-09-21 | Addressed follow-up PR #138 runtime-ID and submission-integrity feedback: nullable detail IDs no longer erase IDs known from admission, and retryable POST HTTP outcomes retain the frozen body/key for explicit safe replay while 429 remains a confirmed rejection. Added red-green Chromium coverage (31 Node tests and 26 Chromium journeys). | Re-run the full Node 22 gate, push the follow-up commit and resolve all current inline threads. |
| 2026-09-21 | Started the next PR #138 review round: verify stale admission-error cleanup after accepted correction, persist the model-refresh response across bfcache pause/resume, and keep manual reread hidden while automatic run polling is active. | Add focused regressions for all three findings, implement the smallest UI-state fixes, then run the Atom Lab Node/browser suites and canonical repository checks. |
| 2026-09-21 | Closed the remaining external review findings: persisted `pagehide` now pauses transport work and `pageshow` resumes the same accepted run without a new POST; the complete submission phase, including response-body parsing, has an abortable 30-second deadline that preserves the frozen replay. Added deterministic red-green coverage for bfcache restore plus stalled fetch and stalled JSON body (34 Node tests and 26 Chromium journeys). | Run the full Node 22 gate, publish the follow-up commit, and report the fixes on PR #138. |
| 2026-09-21 | Addressed the three latest PR #138 findings: accepted corrected submissions clear obsolete admission errors and ARIA state; the validated refresh response persists `pending`/`running` across bfcache pause/resume; and resumed or valid nonterminal automatic polling hides manual reread. Verified 36 Node tests, 26 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the four-file remediation, then reply to the three review threads. |
| 2026-09-21 | Addressed a follow-up PR #138 catalog-polling race: an in-flight pre-pause catalog read can no longer orphan the timer scheduled after bfcache resume because the tracked timer is cancelled before rescheduling. Added a deterministic in-flight pause/resume regression and verified 37 Node tests, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the two-file follow-up, then reply to the review thread. |
| 2026-09-22 | Addressed the PR #138 catalog-failure load finding: failed reads now use capped exponential backoff through 4 seconds and a successful pending read resets the delay. Added deterministic failure/cap/recovery coverage and verified 38 Node tests, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Commit and push the follow-up, then reply to the review thread. |
| 2026-09-22 | Addressed the next three PR #138 findings: accepted refresh state now survives bfcache without a last-good catalog; delayed admission errors are attached only when the current draft field still matches the captured frozen submission; and run detail parsing enforces `succeeded` with a non-null result and every other status with `result=null`. Verified 39 Node tests, 28 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the four-file remediation, then reply to the three review threads. |
| 2026-09-22 | Addressed the next two PR #138 catalog findings: polling now checks its deadline before I/O and caps every scheduled delay to the remaining budget; a `current` refresh response stops polling and immediately reloads/renders the latest catalog items. Added deterministic deadline-budget and immediate-current regressions and verified 41 Node tests, 28 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the three-file remediation, then reply to both review threads. |
| 2026-09-22 | Addressed the next two PR #138 findings: superseded catalog reads can no longer overwrite a newer refresh result, and protected run details whose requested model or reasoning effort conflicts with the frozen submission fail closed. Added deterministic regressions and verified 42 Node tests, 30 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the four-file remediation, then reply to both review threads. |
| 2026-09-22 | Addressed the next five PR #138 findings: protected accepted runtime identity, bounded and abortable in-flight catalog reads, restored validation-owned ARIA state before atom navigation, classified malformed confirmed admission rejections before safe body decoding, and required explicit reselection when refresh invalidates a model or effort. Verified 43 Node tests, 36 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the four-file remediation, then reply to the five review threads. |
| 2026-09-23 | Implemented AL08/ANY-466: protected paginated preset/history UI, immutable version selection, optimistic version saves with conflict-preserved drafts, exact version export, source-run provenance, fixed top-level controls, durable run detail reopening and explicit snapshot restore/adaptation without submission. Added strict browser parsers plus full v1/v2/export/reload/restore, conflict, exact save-from-history provenance, validation-retry, running/crash-failed, nullable-ID and unavailable model/contract Chromium coverage. Verified 51 Node tests, 47 Chromium journeys, ESLint, focused API/storage tests and canonical `quick-check` (1864 passed). `frontend-check` passed install/lint/typecheck and the Atom Lab package, then failed only in the unrelated web-mirror suite under local Node 26 because jsdom exposes no `window.localStorage`, matching the existing AL07 environment note. | Review and commit ANY-466, then continue with AL09/ANY-467. |
| 2026-09-23 | Addressed PR #142 CI race: preset fields and save actions stay disabled until the initial protected preset-list read completes, so late initialization cannot erase an in-progress draft. Added a delayed-response Chromium regression that exercises the loading state before the immutable-version journey. Verified 51 Node tests, 47 Chromium journeys, 10 parallel repetitions of the failing journey, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Commit and push the CI fix, then confirm the replacement PR checks. |
| 2026-09-23 | Addressed PR #142 review blockers: historical preset provenance is compatibility-checked and read-only until explicit adaptation; new and saved preset metadata share discard protection; atom changes clear preset association; history-to-preset preserves action, schema and prompt provenance; and preset/run boundaries reject atom IDs outside A01-A11. Added focused provenance, dirty-state, association and fail-closed regressions. Verified 51 Node tests, 49 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Commit and push the review fixes, then inspect replacement PR checks. |
| 2026-09-23 | Addressed the next PR #142 review round: incompatible history adaptation drops stale preset refs; restore clears the preset save target; preset selection commits atomically behind a generation guard; visible preset editors remain active across atom changes; version changes invalidate stale exports; and preset writes use a shared mutation lock. Added delayed/stale/failing read, double-submit, restore-association, post-navigation dirty-state and exact-version export regressions. Verified 51 Node tests, 50 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Commit and push the follow-up, then inspect replacement PR checks. |
| 2026-09-23 | Addressed the latest PR #142 review round: preset reads and writes now lock the complete mutable workspace; history adaptation uses the shared dirty-draft guard; history detail and all paginated reads reject stale or duplicate responses; incompatible history adaptation drops stale source-run provenance; and a successful preset write retains its server identity even when the readback fails. Added out-of-order detail/page, double-click, dirty-adaptation, source-run and post-write readback regressions. Verified 51 Node tests, 52 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Commit and push the follow-up, then inspect replacement PR checks. |
| 2026-09-23 | Addressed the next PR #142 review round: preset saves now reject invalid visible editor state; conflict recovery resolves the latest version directly by identity and disables stale recovery on refresh failure; preparing a history preset preserves the unrelated runtime preset reference; pagination and run-summary parsers enforce cursor/link invariants; and accepted runs immediately refresh preset draft state. Added invalid-save, later-page conflict, conflict-read failure, history provenance and run-state regressions. Verified 51 Node tests, 55 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Commit and push the follow-up, update the PR description, then inspect replacement PR checks. |
| 2026-09-23 | After merging current `main`, closed the remaining non-blocking PR #142 findings: fixed fields are available only when present in the saved input; conflict recovery re-resolves the newest version at click time and synchronizes the library summary; and every protected preset/history request has a browser deadline, with ambiguous writes blocking blind duplicate saves. Added newest-version, fixed-field, stalled-read and stalled-write regressions. Verified 51 Node tests, 58 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1884 passed). | Commit and push the follow-up, then inspect replacement PR checks. |
| 2026-09-23 | Addressed the final PR #142 reopen and recovery review: reopening Presets now restores the saved/draft status and revalidates fixed fields against edits made while the panel was closed; saving an existing identity updates the already-loaded library in place instead of resetting late-page pagination; and a failed conflict refresh retains its actionable error. Expanded the four affected Chromium journeys and verified 51 Node tests, all 58 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1884 passed). | Commit and push the follow-up, then inspect replacement PR checks. |
| 2026-09-24 | Addressed the remaining PR #142 write-recovery blocker: POST transport failures and malformed or contract-invalid successful envelopes now enter the ambiguous-outcome state and block blind duplicate saves, while known HTTP failures remain retryable; preset save errors also expose validated backend field paths/messages without discarding the draft. Added transport-loss, malformed-success, invalid-success and field-error Chromium regressions. Verified 51 Node tests, all 62 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1884 passed). | Commit and push the follow-up, then inspect replacement PR checks. |
| 2026-09-24 | Addressed the follow-up PR #142 blockers: every preset POST `5xx` is now treated as an ambiguous proxy-boundary outcome while proven `4xx` business failures remain retryable, and Fill Example uses the shared preset/history-aware dirty guard so unsaved fixed-field choices cannot disappear silently. Added committed-then-502 and preset-only fixed-field regressions. Verified 51 Node tests, all 64 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1884 passed). | Commit and push the follow-up, then inspect replacement PR checks. |
| 2026-09-24 | After merging current `main`, addressed the latest PR #142 review and CI feedback: history-to-preset preserves an explicit `null` reasoning effort instead of inheriting the unrelated editor value; identity clicks resolve the fresh latest version while dropdown selection remains exact; and ProposalAI's guest-persistence smoke waits for the asynchronous identity rather than the newly earlier-rendered shell title. Added null-provenance and stale-summary regressions. Verified 51 Node tests, all 65 Atom Lab Chromium journeys, the CI-parity ProposalAI smoke (8/8), both affected ESLint configurations, ProposalAI smoke typecheck, `git diff --check`, and canonical `quick-check` (1884 passed). | Commit and push the follow-up, reply to the inline review, then inspect replacement PR checks. |
| 2026-09-24 | Addressed the final PR #142 contract-hardening review: every version-list item must belong to the requested preset identity; successful create receipts must report v1; successful version receipts must report the requested identity and exactly `base_version + 1`; untrusted success mismatches enter ambiguous-outcome recovery. Also aligned the history fixture's diagnostic reasoning effort with its snapshot. Added fail-closed parser and write-receipt regressions. Verified 51 Node tests, all 68 Atom Lab Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1884 passed). | Commit and push the follow-up, reply to the inline review, then inspect replacement PR checks. |
| 2026-09-24 | Addressed the PR #142 run-provenance ownership blocker: each frozen run submission retains the draft session that created it across delayed admission and idempotent retries; an accepted `run_id` is attached only while that owner remains the current draft, so atom or preset navigation cannot contaminate unrelated preset provenance. Added delayed-accept and transport-retry navigation regressions that assert the subsequent preset POST keeps `source_run_id=null`. Verified 51 Node tests, all 70 Atom Lab Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1884 passed). | Commit and push the follow-up, reply to review, then inspect replacement PR checks. |
| 2026-09-24 | Addressed the remaining non-blocking PR #142 shared-library findings: ambiguous preset writes now also lock the New Preset transition so their duplicate protection cannot be reset without reconciliation, and every Presets reopen refreshes the shared first page while merging it ahead of already-loaded later pages without discarding their pagination position. Added unknown-outcome bypass and shared-identity refresh regressions. Verified 51 Node tests, all 71 Atom Lab Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1884 passed). | Commit and push the follow-up, then inspect replacement PR checks. |
| 2026-09-24 | Hardened the final shared-library reconciliation edges from PR #142 review: first-page refresh preserves loaded pagination only when the refreshed range overlaps it, otherwise it resets to the server's fresh cursor so newly inserted identities cannot fall into a gap; ambiguous create remains locked across reopen and unrelated identity reads, while a fresh read of the same identity safely reconciles an ambiguous update; the recovery instruction remains visible across secondary preset errors and export, and stale conflict recovery is cleared when write outcome becomes unknown. Added overlap, no-overlap, unknown-create/export and conflict-to-ambiguous update-recovery coverage. Verified 51 Node tests, all 74 Atom Lab Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1884 passed). | Commit and push the follow-up, then inspect replacement PR checks. |
| 2026-09-22 | Addressed the next three PR #138 findings: reasoning capability loss now keeps the invalid effort blocking while allowing an explicit no-effort recovery; malformed successful run-detail bodies fail closed without automatic reconnect; and every catalog read, including initial and immediate-current refresh loads, has an abortable deadline. Verified 45 Node tests, 39 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the four-file remediation, then reply to the three review threads. |
| 2026-09-22 | Addressed the next six PR #138 findings: refresh POST is deadline-bounded and cancelled on lifecycle teardown; bfcache resume completes an interrupted current-catalog reload; prompt admission errors are visible and bound to the prompt editor; action/artifact runtime IDs are fill-once; stale warnings include last-success time; and truncated invalid raw output is explicitly marked. Verified 47 Node tests, 42 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the five-file remediation, then reply to the six review threads. |
| 2026-09-22 | Addressed the next three PR #138 findings: refresh and polling failures now retain stale wording and last-success context; initial catalog loads interrupted by bfcache resume automatically; and authoritative admission field errors retire immediately when their owning prompt, input, model, or effort changes. Verified 48 Node tests, 43 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the four-file remediation, then reply to the three review threads. |
| 2026-09-22 | Addressed the next PR #138 lifecycle finding: persisted pagehide/pageshow pauses now preserve the original catalog and accepted-run polling deadlines, and resumed catalog scheduling is capped to the remaining cumulative budget. Verified 50 Node tests, 43 Chromium journeys, ESLint, `git diff --check`, and canonical `quick-check` (1864 passed). | Review and commit the three-file remediation, then reply to the review thread. |
| 2026-09-24 | Addressed the latest PR #142 review: known structured pre-write `503` failures remain retryable while unproven proxy `5xx` outcomes stay ambiguous; history preset saves no longer replace an unrelated editor draft; preset/history entry points remain inert until access is unlocked; Reset Prompt warns only for a genuinely dirty draft; unavailable model placeholders and warnings are reconciled on every saved selection; and the browser atom-ID closed set is checked against the backend enum without hiding the literal `prompt_ref` contract field. Added focused regressions and verified 51 Node tests, all 78 Atom Lab Chromium journeys, architecture tests, ESLint, `git diff --check`, and canonical `quick-check` (1885 passed). | Commit and push the review fixes, reply to all six inline threads, then inspect replacement PR checks. |
| 2026-09-25 | Merged current `main` after PR #142 landed and started its post-merge review follow-up: history model availability must track initial/refresh catalog changes, history summaries must identify both preset and version, and ambiguous existing-version writes need reconciliation that preserves the local draft for pre-commit loss, exact commit, and concurrent conflict outcomes. | Add red Chromium regressions for all three findings, implement the smallest state-machine changes, then run Atom Lab and canonical repository gates before opening a follow-up PR. |
| 2026-09-25 | Closed the three post-merge ANY-466 review findings and follow-up PR #149 comments: an open History detail recomputes model availability on every catalog load/refresh; history rows display `preset_id` with the version; ambiguous version writes retain the frozen payload/base so same-identity reconciliation can unlock a safe retry, confirm an exact committed version, or surface a concurrent conflict without discarding submitted or later local edits; recovery after replacing the owner session, including a history-derived editor-preserving update, clears stale guidance and falls back to a normal latest-version open; exact and conflict recovery materialize the selected immutable version outside the first page, keep it selected/deduplicated/newest-first across pagination, export the same base, and use it for the next `base_version`. Merged current `main` and preserved both ANY-466 recovery coverage and ANY-467 acceptance-harness plan history while resolving the plan conflict. Verified 52 Node tests, all 84 Atom Lab Chromium journeys, ESLint, architecture tests, `git diff --check`, canonical `quick-check` (1929 passed), and clean independent diff re-reviews. Canonical `frontend-check` passed install/lint/typecheck and the feature-owned journeys, then the unrelated web-mirror Vitest suite remained incompatible with local Node 26 `localStorage`; GitHub's supported Node gate is the authoritative rerun. | Commit and push the follow-up, reply to the new inline comment, and monitor replacement CI. |
| 2026-09-24 | Implemented ANY-467 automated acceptance: the existing live-canary now has an optional protected Atom Lab surface with non-smoke A01-A11 inputs, repository prompts, catalog-selected GPT/reasoning combinations, immutable snapshot and idempotent-replay checks, shared PostgreSQL ledger validation, cost fail-closed behavior, and privacy-safe model/date/validity evidence. Added adapter-level retry and explicit-null reasoning assertions and a repository-visible 12-criterion matrix. Final quick-check passed (1908 tests), as did the real PostgreSQL gate and all 78 Atom Lab Chromium journeys; independent review has no remaining Critical or Important findings. The aggregate full-check remains locally red only for the previously documented Node 26/web-mirror localStorage incompatibility. | Run the supported Node 22 CI gate and credentialed Atom Lab live-canary. Live credentials are absent, so AL09 remains blocked and unchecked. |
| 2026-09-25 | Addressed PR #145 acceptance review: one fixture now drives the same A01-A11 non-smoke inputs through browser Form submission, HTTP durability and ActionRunner; the canary consumes the real `/atoms` array; validates output schema plus semantic validators; keeps provider credentials server-side; treats crash reconciliation as unknown spend; and checks direct model/effort metadata on every physical call. Verified quick-check (1929 passed), 52 Node tests, ESLint and all 78 Chromium journeys. | Commit and push the remediation, reply to the six review threads, then run the credentialed live gate when a configured stack and access code are available. |
| 2026-09-25 | Closed the final PR #149 recovery-ownership blocker: ambiguous preset-version reconciliation now requires the original editor session, immutable preset identity/base version, and exact preset source context. Starting a new preset from History therefore cannot inherit recovery ownership merely because it reuses the editor session. Added a browser regression for `ambiguous update → Save preset from History → reopen original preset`, including the normal discard/open flow and proof that the History snapshot is not attached to the recovered version. Verified 52 Node tests, all 85 Atom Lab Chromium journeys, ESLint, documentation checks, `git diff --check`, and canonical `quick-check` (1929 passed). | Commit and push the remediation, update PR evidence, and inspect replacement checks. |

## Planning revision verification (2026-09-09)

- All ten Linear descriptions match their revised plan sections after normalizing Linear issue-link markup.
- All ten dependency sets match the plan; graph has no cycles. Valid order: ANY-459, ANY-460,
  ANY-461, ANY-463, ANY-462, ANY-464, ANY-465, ANY-466, ANY-467, ANY-468.
- Projects, statuses, labels, assignees, priorities and due dates were preserved; no issues created or deleted.
- Repo doctor, validate-docs and validate-architecture passed for this documentation-only revision.
- generate-docs --check reported DOCGEN001: docs/generated/openapi.json is stale.
  API source and generated OpenAPI were not changed in this revision; regeneration is not included.
- Runtime/full-check/live tests were not executed: this revision changes the plan and Linear tickets,
  not Atom Lab implementation. Implementation acceptance checkboxes above intentionally remain open.

## Open questions

No product decision blocks the first ticket. Implementation must verify current provider metadata
and exact migration naming; the plan intentionally does not freeze model IDs. Operator secrets,
internal hostname and rollout authority are required before actual deployment, not for local development.
Spec and plan are currently local workspace changes; publish them as the first AL01 change before distributed dependent work.
Any change to contract scope or production execution semantics requires a separate explicit decision.

## Follow-up debt

Chains and automatic adoption into product configs are deliberately deferred; no speculative framework.
