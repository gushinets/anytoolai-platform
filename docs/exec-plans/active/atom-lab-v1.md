# Execution Plan: Atom Lab v1

## Status

- State: active
- Phase: AL01 implemented and verified; dependent delivery remains active
- Owner: mixed
- Created: 2026-09-09
- Last updated: 2026-09-10
- Review date: 2026-09-16
- Next action: Begin ANY-460 snapshot and worker execution plumbing on top of the AL01 boundary.
- Blocker: none for development; operator configuration required before rollout.
- Linear project: [Atom Lab](https://linear.app/paveldik/project/atom-lab-e1efc95ce888)
- Milestone: Atom Lab v1

Publication update: these documents are submitted for review under ANY-399. Once that PR is merged,
the document-publication prerequisite mentioned under AL01 is satisfied; its implementation,
controlling-doc/guard changes and all runtime acceptance criteria remain outstanding.

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

- [ ] Implement and verify.
- Depends on: ANY-459.
- Files/areas: `platform-core: scenarios/service.py, actions/executor.py, storage/db.py, storage/repositories.py`; `platform-actions: structured_llm/executor.py, pydanticai_runner.py`; `apps/platform-worker: handlers/run_workflow.py, composition.py`; `existing migration directory`.

Добавить atom_lab_runs с неизменяемым snapshot принятого запуска: action/config/schema refs+versions и достаточные сохранённые definitions, prompt, полный input, model/effort, capability provenance, preset version, runtime IDs. Типизированный validated override передавать из lab-only контекста через существующие session/job/ActionRunner к executor и ProviderGateway. Не мутировать shared registry/router configs. Prompt и provider policy разрешать локально для этого run и всех validation/transport retries. Существующие artifacts, action runs и provider-call ledger остаются единственными execution records. Не добавлять второй executor или native response_format. Обычные jobs работают без override. Snapshot фиксирует настройки и контекст; worker проверяет совместимость с registry при dequeue/retry и при несовместимости завершает запуск явной ошибкой, без silent migration.

Acceptance: Два lab запуска при повышенном test concurrency и обычный job не влияют друг на друга. Worker restart сохраняет snapshot; выполнение/завершение job следует существующим правилам reconciliation, без нового auto-resume. Snapshot принят до enqueue атомарно, нет orphan accepted runs. PostgreSQL tests; assertions фактического input/prompt/model/effort вплоть до вызова provider adapter; existing retry ownership и ledger tests, quick-check/postgresql-check.

### Уточнения после аудита

- [ ] Сначала реализовать атомарный storage snapshot, затем laboratory workflow bindings, затем run-local provider settings. Каждый шаг — отдельный reviewable diff с собственным failing/passing тестом; тикет закрывается после интеграционной проверки всех трёх.
- [ ] Добавить 11 allowlisted internal-only laboratory scenario/workflow definitions в существующий registry, используя те же live action configurations и атомные schema refs. Вход workflow — фиксированная входная схема атома; `input_mapping: {}` использует существующий `resolve_step_input` для передачи всего payload. Не переиспользовать smoke literals и не изменять существующие smoke workflows. Нового executor или изменения контрактов атомов нет.
- [ ] Snapshot содержит полный атомный input, редактируемый prompt, base config/prompt provenance, schema refs/versions и сохранённое содержимое для чтения, workflow binding/version, выбранные model/reasoning, источник/версию capabilities, неизменные server policy limits и runtime IDs по мере появления. Сохранять минимальные execution definitions/hash, чтобы worker проверял совместимость, а не исполнял изменившийся registry молча. Новый framework для исполнения произвольных исторических definitions не нужен.
- [ ] Сначала доступны `run_id, scenario_session_id, job_id`; `action_run_id` и `artifact_id` nullable до соответствующей стадии. Ошибка до создания action не требует выдуманного action ID.
- [ ] Пресет на этом шаге необязателен: создать nullable `preset_id/preset_version` без зависимости от ещё не созданных preset tables. ANY-463 добавляет constraints/валидацию ссылки. Storage предоставляет создание snapshot в caller-owned transaction и чтение по run_id для ANY-463; публичный POST /runs появляется только в ANY-462.
- [ ] Через typed run-local execution settings передать model/reasoning из доверенного snapshot в `ProviderRequest`, `ResolvedProviderRequest`, Gateway и LiteLLM adapter, включая validation/transport retries. Разрешение настроек не меняет глобальный Router или default policy. Выбранная реальная модель должна быть адресуемой адаптером, а не только известной строкой каталога; статический alias `anytoolai.default_text` не должен подменять выбор.
- [ ] Владение фактическим применением model/effort — ANY-460; ANY-461 поставляет metadata, ANY-462 валидирует выбор при admission. Tests используют фиксированный capability fixture и не зависят от network catalog. Проверить аргументы непосредственно на вызове LiteLLM adapter, не ограничиваться mock Gateway; отсутствие effort не должно наследовать статический `medium`. Не вводить silent fallback/drop_params; при несовместимости server-owned дополнительных параметров — явная ошибка, без нового пользовательского редактора.
- [ ] Изоляцию двух lab runs проверять с test concurrency >1 вместе с обычным job; default admission=1 не ослаблять. Проверить неизменность payload до ActionRunner для всех 11 атомов, включая значения, отличные от smoke literals.
- [ ] Worker restart сохраняет snapshot/history. Ожидающий job выполняется по текущим правилам; прерванный running job получает существующий статус/error reconciliation (например worker_lease_lost). Автоматическое повторение платного вызова после crash не добавлять. Existing validation/transport retries сохраняются.
- [ ] Дополнительные точки изменения: `configs/kernel/products/kernel_demo/workflows.yaml`, `scenarios.yaml`, `product.yaml`; `workflows/mappings.py` (reuse), `providers/models.py`, `providers/gateway/`, `providers/adapters/litellm.py`. Regression tests: `apps/platform-worker/tests/test_atom_lab_execution.py`, `apps/platform-api/tests/test_atom_lab_workflow_config.py`; PostgreSQL snapshot tests в existing storage suite.


### AL03 — [ANY-461](https://linear.app/paveldik/issue/ANY-461/atom-lab-obnovlyaemyj-katalog-openai-gpt-i-reasoning-capabilities): Atom Lab: обновляемый каталог OpenAI GPT и reasoning capabilities

- [ ] Implement and verify.
- Depends on: ANY-459.
- Files/areas: `platform-core/src/anytoolai_platform_core/providers/ (catalog logic inside boundary), providers/adapters/litellm.py`; `apps/platform-worker`; `configs/kernel (small capability override YAML)`; `platform-api atom_lab router`; `storage/migrations`.

Получать доступные account model IDs OpenAI, совмещать с актуализируемым снимком LiteLLM metadata и небольшими YAML overrides с source/date. Priority override > metadata > unknown. Поддержка reasoning не доказывает список effort; неизвестное не равно unsupported. Допускать только подтверждённые text GPT для текущего prompted path, не фильтровать по native JSON Schema. API отдаёт модели, allowed efforts, compatibility reason, provenance, stale/last_success. GET /models; POST /models/refresh возвращает queued/current refresh status. Refresh обслуживается отдельным hook существующего worker loop через provider boundary и сохраняет last-good snapshot в PostgreSQL: OPENAI_API_KEY остаётся у worker, не добавлять его в API. Один refresh в работе, TTL 24h, rate limit refresh 60s, без платных probes. Проверить текущие provider/LiteLLM документы при реализации; не угадывать capabilities по имени.

Acceptance: Тесты new/removed model, unknown effort list, no reasoning, stale/failure, empty initial cache; native schema unsupported не исключает prompted-compatible модель. API и UI не содержат SDK/credentials. Каталог явно различает known/unknown/unsupported; отклонение при admission принадлежит AL04, отсутствие silent drop/fallback в adapter — AL02. Refresh не выполняет generation.

### Уточнения после аудита

- [ ] Текущий worker не является очередью произвольных заданий: не помещать catalog refresh в workflow jobs и не создавать фиктивные scenario/action/provider-call rows.
- [ ] Минимальный механизм: одна PostgreSQL cache/state запись на настроенный OpenAI account scope с last-good snapshot, due_at, refresh_requested_at, lease_until, last_success_at и safe last_error. POST /models/refresh только атомарно помечает запрос; worker обслуживает его на старте и между workflow jobs. Наступление TTL также делает refresh необходимым. Один bounded refresh с DB lease; после crash lease истекает, запрос подхватывается снова. Обычный длинный workflow может задержать refresh — API честно показывает pending/stale, не обещает мгновенность.
- [ ] Refresh обновляет OpenAI IDs и валидируемый LiteLLM JSON snapshot; сохраняет только последний целостный корректный результат. Credentials, base URL, policy limits не берутся из внешних metadata. Никаких generation probes, новой очереди общего назначения или отдельного scheduler service.
- [ ] GET /models возвращает `items, snapshot_id, last_success_at, stale, refresh_status, error`. У item: `model_id, compatibility, reason, reasoning_supported, allowed_reasoning_efforts, provenance`; unknown — явно unknown/null, а не false. Исчезнувшая модель не разрешается override. POST refresh возвращает 202 и pending/running состояние; GET models служит polling endpoint.
- [ ] Empty cache: items пуст, execution disabled, refresh error видна; last-good stale cache остаётся доступен с предупреждением. TTL и cooldown — именованные backend settings. Подготовить worker Compose/env wiring в этом тикете; key остаётся только worker.
- [ ] Каталог не реализует применение provider параметров повторно: это ANY-460. Проверки ANY-461: initial load, TTL без кликов пользователя, manual refresh, coalescing/cooldown, expired lease, restart, upstream failure/invalid JSON, model removal, unknown capabilities. API parsing и refresh tests плюс PostgreSQL lease tests; `apps/platform-worker/src/anytoolai_platform_worker/worker.py` и `composition.py` входят в scope.


### AL04 — [ANY-462](https://linear.app/paveldik/issue/ANY-462/atom-lab-zapusk-atoma-i-zashishyonnaya-postoyannaya-istoriya-api): Atom Lab: запуск атома и защищённая постоянная история API

- [ ] Implement and verify.
- Depends on: ANY-460, ANY-461, ANY-463.
- Files/areas: `platform-api routers/atom_lab.py, schemas.py`; `platform-core scenarios/service.py, storage repositories`; `worker terminal status/diagnostics integration`.

POST /runs принимает atom_id, input, prompt, model_id, reasoning_effort, optional preset_ref и Idempotency-Key; сервер валидирует фиксированный контракт, allowlist и capability snapshot. Использовать internal laboratory workflows из AL02 с полным payload и server live token; старые smoke bindings не использовать. Сохранить стабильную identity для одного idempotent submission; новый guest на retry недопустим. Same key+body возвращает тот же run, different body ->409. GET /runs cursor pagination, GET /runs/{id} — защищённые snapshot/status/result/diagnostics. Показывать все accepted runs, включая failed/running; не дублировать execution ledger. Лимиты defaults: input JSON 256KiB, prompt UTF-8 64KiB, общий request 384KiB, 100 accepted/day UTC, 1 active lab run; backend configurable. Сериализовать admission в PostgreSQL, чтобы quota/idempotency атомарны. Pre-start errors не расходуют лимит. Диагностика invalid output ограничена lab; не публиковать secret/hidden reasoning. Validation attempts, transport attempts и physical calls различать; actual response model != подтверждение effort.

Acceptance: Первый полный API vertical slice одного атома проходит existing worker; 11 mappings валидны. Concurrent duplicate starts дают один логический job; физические provider calls учитываются отдельно с разрешёнными runtime retries. Закрытие вкладки/restart не теряют историю. Pagination stable; terminal result immutable; unknown historical contract/model читается без silent migration. Tests oversized/unicode/auth/limits/races/failures; PostgreSQL checks.

### Уточнения после аудита

- [ ] Зависимости: ANY-460 (snapshot и laboratory workflows), ANY-461 (catalog), ANY-463 (preset version validation). Порядок AL-номеров не означает порядок разработки.
- [ ] POST /runs body: `{atom_id, input, prompt, model_id, reasoning_effort, preset_ref?}`; `preset_ref={preset_id,version}`, effort nullable. Extra fields запрещены. `input` — полный видимый payload, без скрытого merge со saved preset. Ссылка на пресет — provenance; допустим изменённый draft, который явно отличается от версии. Проверить существование и соответствие атома/контракта пресета; не выдавать draft за неизменённый preset.
- [ ] Сервер сам разрешает laboratory scenario по atom_id; принимает только указанный atom contract. Прямые scenario IDs, arbitrary provider/base URL/credentials и schema overrides не принимаются.
- [ ] Auth выполняется до idempotency lookup. Scope ключа — внутренняя lab область tenant/region. Hash охватывает atom, полный input, prompt, model/effort и preset reference; JSON порядок ключей не влияет. Повтор accepted key+hash возвращает существующий run даже если модель исчезла/лимит исчерпан позже; другой hash ->409. Новому ключу — новая серверная guest identity, retry того же ключа использует сохранённую. Snapshot+session+job и admission count атомарны; не держать admission lock во время provider call.
- [ ] Успешный POST возвращает 202: `{run_id,scenario_session_id,job_id,status}`. GET /runs — `{items,next_cursor}`, стабильная сортировка created_at+run_id, limit default 20/max100. GET /runs/{id} — `{run_id,status,snapshot,runtime_ids,result,diagnostics,created_at,started_at,finished_at}`. result только при успешной финальной валидации; диагностика отдельно. nullable IDs/времена не заменять фиктивными значениями.
- [ ] Safe error envelope: `{error:{code,message,field_errors:[{path,message}]},request_id}`. 401 access_denied; 404 lab resource not found; 409 idempotency_conflict/preset_mismatch/contract_unavailable; 413 payload_too_large; 422 input_invalid/model_not_allowed/reasoning_not_allowed; 429 lab_busy/daily_limit_exhausted; 503 lab_unavailable/catalog_unavailable. Framework parsing errors привести к этому формату. Не включать секреты или полный prompt/input в ошибки/логи.
- [ ] Размеры считать в UTF-8 по документированному JSON encoding, отдельно лимитировать raw request body; проверить unicode и JSON escaping. Начальные лимиты — технические defaults из плана, не изменение атомных схем и не гарантия попадания в context window.
- [ ] Worker/executor сохраняют bounded contract-failure diagnostics в lab storage по run_id без второго ledger; счётчики берутся из существующих semantic/transport/physical indices. Успех с первой попытки различим от успеха после валидационных исправлений. Невалидный текст — защищённая диагностика с признаком truncation при ограничении, не successful artifact. Terminal projection не теряет сведения при restart/reconciliation.
- [ ] Один idempotent submission означает один логический job, не обещание одного physical provider call: разрешённые retries остаются. Проверить одинаковые key requests в гонке, replay после terminal/исчезновения модели, падение transaction и worker_lease_lost. Для каждого из 11 атомов submitted input == snapshot input == ActionRunner input; проверить optional omissions/null/false/0 и нестандартные поля из контракта. API tests: `apps/platform-api/tests/test_atom_lab_runs.py`, `test_atom_lab_history.py`.


### AL05 — [ANY-463](https://linear.app/paveldik/issue/ANY-463/atom-lab-biblioteka-neizmenyaemyh-versij-presetov-i-eksport-api): Atom Lab: библиотека неизменяемых версий пресетов и экспорт API

- [ ] Implement and verify.
- Depends on: ANY-459, ANY-460.
- Files/areas: `platform-api atom_lab router/schemas`; `platform-core storage repositories/db`; `existing migration directory`.

Общая для команды библиотека: GET/POST /presets, GET /presets/{id}/versions/{version}, POST /presets/{id}/versions, GET /presets/{id}/versions/{version}/export. PostgreSQL preset identity + immutable versions, optimistic base_version check и атомарная нумерация. Сохранять имя/описание, atom/base config/schema refs+versions, prompt/provenance, model/effort, fixed top-level fields, пример входа, optional source run. Фиксация целого поля, без произвольных JSON paths; запуск использует видимый полный payload, нет скрытого overwrite. Export versioned JSON secret-free, достаточный для ручного переноса в YAML/prompt/provider policy через review. No production config DB registry, import, auto PR, delete UI. Недоступная модель/старый контракт не лишают чтения пресета; запуск требует явной адаптации.

Acceptance: Сохранение и reopen после restart, immutable old versions, concurrent save -> conflict без потери данных. Создание, чтение, версионирование и экспорт защищены; удаление не входит в v1. Сохранение не вызывает LLM и не меняет production. Невалидные refs/fields отвергаются; source run проверяется в lab scope. PostgreSQL tests и export fixture с точными полями/без secrets.

### Уточнения после аудита

- [ ] Зависит от ANY-460, а не от будущего runs API: источник запуска читать из уже созданного lab storage. Добавить constraints для nullable run->preset/version references после создания preset tables. Это позволяет ANY-462 зависеть от ANY-463 без цикла.
- [ ] Version payload: `{name,description,atom_id,base_action_config_id,schema_refs,prompt,prompt_ref,model_id,reasoning_effort,fixed_fields,example_input,source_run_id?}`. `fixed_fields` — уникальные имена целых верхнеуровневых полей; их значения находятся в example_input. Остальные поля контракта считаются runtime inputs. Схема атома не редактируется.
- [ ] POST /presets создаёт identity и v1 атомарно. POST /presets/{id}/versions принимает version payload и `base_version`; успешный ответ 201 с `preset_id,version,created_at`, stale base ->409 `preset_version_conflict`. GET /presets — paginated identities; добавить GET /presets/{id}/versions для списка версий, detail/export — существующие version endpoints.
- [ ] Проверить source_run_id в lab scope и соответствие atom/schema provenance. Ссылка означает происхождение, а не доказательство идентичности настроек или качества результата. Черновой пресет можно сохранить без successful run; не ставить статус «проверен» автоматически. Невалидный input не проходит contract validation, но плохой по смыслу prompt допустим.
- [ ] Экспорт конкретной версии: `{format_version:1,preset_id,version,configuration}`, configuration содержит version payload без credentials, provider base URL и внутренних auth данных. Модель/effort — настройки для ручного переноса в provider policy, не raw поля production action config. Runtime не читает production configs из этой библиотеки.
- [ ] Чтение старых версий не требует доступности модели. Сохранённые schema/provenance сведения остаются читаемыми; ANY-462 проверяет совместимость перед новым запуском. Contract tests покрывают exact export fields, conflicts, scope, разные версии и отсутствие LLM вызова при save. Добавить `apps/platform-api/tests/test_atom_lab_presets.py`; error envelope совпадает с разделом API плана.


### AL06 — [ANY-464](https://linear.app/paveldik/issue/ANY-464/atom-lab-vybor-atoma-pasport-formy-vseh-kontraktov-i-redaktor-prompta): Atom Lab: выбор атома, паспорт, формы всех контрактов и редактор промпта

- [ ] Implement and verify.
- Depends on: ANY-459.
- Files/areas: `apps/platform-api/src/anytoolai_platform_api/static/atom_lab/ (new)`; `API page tests`; `existing browser test harness`.

Русскоязычная страница без нового frontend deployment/framework: sidebar 11 атомов; паспорт назначения/input/transformation/output; readonly schemas; form/JSON один payload; input/prompt tabs, восстановление base prompt и valid example. Поддержать ВСЕ поля текущих 11 схем: nested objects, arrays, enum, dynamic dictionaries; optional omission отдельно от null/empty/false/0. Не перекладывать неизвестные поля только в JSON на нетехнического пользователя. Невалидный JSON не теряется при переключении и блокирует запуск. Состояние результата не подменяется новым draft. Предупреждать о потере dirty draft при atom/preset/history/example/reset навигации. Доступ проверять сервером до отображения protected data.

Acceptance: Матрица schema features по 11 атомам покрыта runnable UI tests; form->JSON->form сохраняет payload точно. Читаемые path validation errors, readonly contracts, keyboard/focus/labels, narrow-screen layout. textContent/safe rendering, без secret storage. Browser check и page/assets tests.

### Уточнения после аудита

- [ ] Контракт UI — каталог из ANY-459 и единый JSON-совместимый draft. Переключение Form/JSON не добавляет defaults, не удаляет пустые допустимые значения и не превращает omitted в null. Проверка exact payload round-trip параметризована по всем 11 атомам.
- [ ] Этот тикет отвечает за точность browser payload; равенство submitted/snapshot/executor payload проверяется в ANY-462 и ANY-467, без скрытой зависимости формы от ещё не готового run API.
- [ ] Упаковка static assets и локальная browser-test команда входят в этот PR, а не ждут ANY-468. Использовать установленный browser test harness; зафиксировать запускаемую команду и подключение tests к canonical checks. Проверка наличия строк в HTML не заменяет интерактивные тесты.
- [ ] Ошибки по path из safe API envelope привязаны к контролам; невалидный JSON сохраняется дословно до исправления. Секрет только в памяти вкладки, после reload требуется новый вход, но server history не теряется.


### AL07 — [ANY-465](https://linear.app/paveldik/issue/ANY-465/atom-lab-gptreasoning-zapusk-i-chitaemyj-rezultat-v-ui): Atom Lab: GPT/reasoning, запуск и читаемый результат в UI

- [ ] Implement and verify.
- Depends on: ANY-462, ANY-464.
- Files/areas: `static/atom_lab/`; `API/browser tests`.

Подключить модели из backend catalog, supported effort selector, unsupported hidden/disabled с пояснением, unknown отдельно, stale banner/refresh. Отправлять current draft с idempotency key; network retry того же submission не создаёт новый run, явный новый запуск — новый key. Poll только protected lab endpoint. Pending/reconnecting/failed/completed показывают реальное состояние, browser timeout не отменяет job. Результат читабельный со всеми значимыми полями и JSON; invalid response отделён от successful artifact. Показывать run snapshot отдельно от изменяемого draft, duration/requested model/response model/effort/validation and transport attempts, IDs в diagnostics. No chain progress fiction; no native schema toggle.

Acceptance: Browser scenarios success/validation correction/final invalid/provider error/network recovery/unsupported selection; double click и повтор transport request не удваивают run. Result не исполняет HTML. Редактирование draft во время/после запуска не меняет displayed run configuration. Один реальный атом end-to-end плюс детерминированные UI tests.

### Уточнения после аудита

- [ ] Раздельные сущности UI: editable draft, immutable submitted snapshot, response-derived metadata. Для запуска использовать `model_id/reasoning_effort` и response shape ANY-462; catalog fields — ANY-461. Изменение формы не переписывает карточку уже принятого запуска.
- [ ] Подписи: «Запрошенная модель», «Модель в ответе», «Запрошенный reasoning». Отсутствие provider-confirmed effort не трактовать как подтверждение; unknown response model отображать как неизвестную, не подставлять запрос.
- [ ] Browser timeout/network loss оставляют возможность повторного чтения принятого run. Running job после crash может завершиться ошибкой текущего runtime; не показывать автоматическое возобновление или повторять POST с новым key.
- [ ] В acceptance связать browser-selected настройки с adapter-call evidence ANY-460/467, а не только текстом dropdown. Проверить согласованные safe error codes, last-good stale catalog и сохранение draft после отказа admission.


### AL08 — [ANY-466](https://linear.app/paveldik/issue/ANY-466/atom-lab-presety-eksport-i-vosstanovlenie-istorii-v-ui): Atom Lab: пресеты, экспорт и восстановление истории в UI

- [ ] Implement and verify.
- Depends on: ANY-463, ANY-465.
- Files/areas: `static/atom_lab/`; `browser/API integration tests`.

Библиотека: создать пресет/открыть/выбрать immutable version/сохранить новую, имя и описание, fixed top-level field controls, source run, export конкретной версии. Отображать draft vs saved version. Save conflict сохраняет local draft и предлагает актуальную версию либо новый пресет. История общая, paginated, включает running/failed; reopen detail после закрытия страницы. Restore snapshot заполняет форму, не запускает платный вызов. Save preset из history использует именно выбранный snapshot, не несвязанный current draft. Unavailable model/contract показывать явно, historical data readonly без silent migration; unsaved warning.

Acceptance: Browser test полного пути input+prompt -> run -> save v1 -> change -> save v2 -> reopen v1 -> export -> reload -> history restore. Обе версии неизменны; восстановление не увеличивает provider calls; concurrency conflict не теряет draft. Ошибка сохранения оставляет значения; все reads/writes защищены.

### Уточнения после аудита

- [ ] Использовать `preset_id/version/base_version`, version-list endpoint и export format из ANY-463; history snapshot/runtime IDs/error envelope из ANY-462. Раскрытие старой версии не заменяет её автоматически latest.
- [ ] Восстановление заполняет `model_id/reasoning_effort` и полный snapshot input; требует отдельного клика «Запустить». Сохранение из history получает source_run_id выбранного запуска, а изменения после восстановления остаются draft.
- [ ] Проверить историю crash-failed job, nullable action/artifact IDs, success-after-validation-retry и конфликт сохранения с сохранением локального draft. При несовместимости текущего контракта исторический snapshot остаётся доступен для чтения; адаптация только явным действием.


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
