# Execution Plan: DDD-lite аудит границ и безопасный план исправлений

## Status

- State: active
- Owner: mixed
- Created: 2026-08-16
- Last updated: 2026-08-16
- Review date: 2026-08-16
- Next action: проверить и при необходимости исправить PR #73 по ANY-257 против актуального контракта A03, затем довести его до merge. Не копировать weighted-average логику A02. Не начинать DDD-рефакторинг.
- Blocker: none

## Снимок (main @ `c618e27`, 2026-08-16)

После merge ANY-256 (#72):

| Состояние | Факт |
|---|---|
| Kernel-demo `action_config` | 10 / 11. Нет только `text.score_multidimensional_axes` |
| Строгие JSON Schema | 10 атомов закрыты; A03 всё ещё `{ "additionalProperties": true }` |
| Python input validator | 3: extract, compare_and_classify, score_match_by_rubric |
| Python output cross-validator | 9. Нет у `score_multidimensional_axes` и `document.generate_from_template` |
| Это дыра? | Нет ключа в map — штатное `.get(...)`. JSON Schema достаточна, пока нет инварианта input↔output, который схема не выражает |
| Atom Runtime Proof | Не закрыт. Нет команды `atoms-proof`. 6 smoke-сценариев, не 11 standalone. Нет 3 composite на все 11 атомов |

## Goal

1. Зафиксировать read-only аудит границ (16 Aug 2026).
2. Доставить **минимальный безопасный путь** к MVP-A1 Atom Runtime Proof, не превращая аудит в DDD-программу.
3. Остальной долг держать как **trigger-based backlog**, не как обязательные фазы.

## Context

MVP-A1 отвечает на вопрос из [`docs/product-specs/mvp-a-platform-kernel.md`](../../product-specs/mvp-a-platform-kernel.md): backend читает config, создаёт `scenario_session_id`, гоняет все 11 атомов и composite-цепочки через worker/provider, пишет artifacts/events, отдаёт frontend-safe result — без web/CE.

Линейная карта proof уже есть в [`docs/exec-plans/active/mvp-a-mvp-b-linear-epics.md`](mvp-a-mvp-b-linear-epics.md):

```text
ANY-257 (последний строгий атом)
  -> ANY-218 11 standalone
  -> ANY-219 3 composite
  -> ANY-220 atoms-proof CLI / evidence
  -> ANY-221 live canary (не baseline CI)
```

Этот файл не подменяет A21. Он только: freeze горячего пути, правила ANY-257, явная вставка A21 в порядок работ, дешёвый замок `product-platforms → sdk`, backlog долга.

Runtime-контракт атома — **JSON Schema** (`docs/architecture/structured-output.md`, `ActionInputValidator` / `ActionOutputCrossValidator`). Python-валидаторы — опциональные плагины для семантики, которую статическая схема не выражает. Отсутствие ключа в `composition.py` — не баг.

## Scope

### In scope

- Правила и freeze для ANY-257.
- Явный milestone A21 между 11-м атомом и cleanup.
- Architecture check `product-platforms → platform-sdk only`.
- После зелёного proof: удаление реально неиспользуемых placeholder/definitions/schemas.
- Ранжированный backlog аудита с триггерами, не с обязательным исполнением.

### Out of scope

- Fail-closed «нет Python CV → runtime error».
- Обязательный CV для `document.generate_from_template`.
- Распил `loader.py` / `runner.py` / executor / съём `Session`.
- Унификация SDK Pydantic ↔ core dataclasses.
- Введение Pydantic-моделей всех 11 input/output.
- MVP-A2 client surfaces — канон: [`docs/product-specs/mvp-a2-client-surfaces.md`](../../product-specs/mvp-a2-client-surfaces.md).
- «DDD-lite completion» как цель перед MVP-B.

## Relevant docs

- `docs/architecture/package-layering.md`
- `docs/architecture/platform-boundaries.md`
- `docs/architecture/structured-output.md`
- `docs/architecture/action-model.md`
- `docs/product-specs/mvp-a-platform-kernel.md`
- `docs/product-specs/mvp-a2-client-surfaces.md`
- `docs/exec-plans/active/mvp-a-mvp-b-linear-epics.md`
- `docs/tech-debt-tracker.md` (TD-010)

## Contracts touched

Пока документ. Код — только в тикетах ниже, каждый своим PR:

- ANY-257: JSON Schema / YAML / prompt / fixture / tests этого атома. API/DB/events/frontend не трогать.
- Architecture lock: только `scripts/agent/validate_architecture.py` (+ тест).
- A21: scenarios/workflows/kernel_demo + runner command. Не рефакторинг ядра.
- Cleanup после proof: удаление неимпортируемых файлов.

---

## Контракт валидаторов (не путать с «всем нужен CV»)

| Слой | Когда обязателен |
|---|---|
| Закрытая JSON Schema (`additionalProperties: false`) | Всегда для complete-атома |
| `ActionInputValidator` | Только семантика, которую схема не выражает (например unique `id` в динамическом массиве). Бежит до provider call |
| `ActionOutputCrossValidator` | Только инвариант **output относительно этого input**, который нельзя зашить в статическую output-schema (coverage id, per-call `max_length`, формула score если она в контракте) |
| Нет ключа в `composition.py` | Штатно. `ActionRunner` / `StructuredLlmActionExecutor` делают `.get(...)` |

Не делать:

- allowlist-тест «каждый complete atom имеет cross-validator»;
- fail-closed по отсутствию валидатора;
- догонку CV для `document.generate_from_template`, пока нет конкретного инварианта `template_ref`/`data` ↔ `sections`.

---

## Карта 11 атомов

| Action type | Kernel-demo config | Python input CV | Python output CV | Статус |
|---|---|---|---|---|
| `text.extract_structured_fields` | да | да | да | Не регрессировать |
| `text.detect_issues_by_taxonomy` | да | нет | да | Complete. Input CV не обязателен задним числом |
| `text.compose_reply` | да | нет | да | Complete. Output CV есть из-за per-call constraints |
| `text.generate_clarifying_questions` | да | нет | да | Complete |
| `text.synthesize_angle` | да | нет | да | Complete |
| `text.compose_persuasive_text` | да | нет | да | Complete |
| `text.generate_gap_rewrites` | да | нет | да | Complete |
| `text.compare_and_classify` | да | да | да | ANY-255 #70 |
| `text.score_match_by_rubric` | да | да | да | ANY-256 #72. Unique rubric id + coverage + формула score — часть *его* контракта |
| `text.score_multidimensional_axes` | **нет** | нет | нет | **ANY-257.** Схема ещё permissive |
| `document.generate_from_template` | да | нет | нет | ANY-253. JSON Schema достаточна |

---

## Milestone order

| ID | Title | Depends on | Status |
|---|---|---|---|
| M0 | Freeze горячего пути | — | [x] |
| M1 | ANY-257: 11-й строгий атом | M0 | [ ] |
| M1b | Architecture lock `product-platforms → sdk` | M0 | [ ] |
| M2 | A21: 11 standalone + 3 composite + `atoms-proof` | M1 | [ ] |
| M3 | Опционально удалить реально мёртвые Python placeholders | M2 зелёный | optional, не gate MVP-A1 |

Долг из аудита **не** является M4/M5. См. backlog в конце файла.

---

### M0. Freeze `[x]`

Не распиливать, пока A21 не зелёный:

- `config/loader.py`
- `workflows/runner.py`
- `actions/runner.py`
- `structured_llm/executor.py`
- `handlers/run_workflow.py`
- съём `Session` с оркестраторов
- fail-fast event dimensions / provider `temperature` defaults
- переписывание recovery
- Pydantic-модели всех атомов в core/actions

Stop-and-fix: атомный или A21 PR, который двигает freeze-файлы без бага на этом атоме — вынести рефакторинг.

---

### M1. ANY-257 `text.score_multidimensional_axes` `[ ]`

11-й строгий контракт. **Не** Atom Runtime Proof.

#### Goal

Атом независимо исполняем через существующий `StructuredLlmActionExecutor` / `ActionRunner` / fake provider, со строгой JSON Schema, чтобы ANY-218 мог его посчитать в 11/11.

#### Что делать

- [ ] Зафиксировать контракт A03 в `docs/architecture/action-model.md`: `text`; caller-supplied `axes` с unique `id`, `description` и optional positive `weight`; ровно один `scores` item на ось с `number` 1–10 и required `commentary`; полные ordered `dominant_axes` / `weakest_axes` со всеми ties.
- [ ] Оставить `weight` в v1 без weighting formula и без weighted aggregate. Любая будущая формула — отдельное versioned contract change.
- [ ] Строгие закрытые JSON Schema вместо `{ "additionalProperties": true }`.
- [ ] Prompt, `kernel_demo` action_config, fake-provider fixture, schema/executor tests.
- [ ] Standalone execution на существующем kernel path (config + fixture + тест runner/executor). Отдельный scenario в `scenarios.yaml` можно отложить в ANY-218, если тикет ANY-257 его не требует; action_config обязателен.
- [ ] Добавить обязательные для контракта A03 Python validators:
  - input validator отклоняет duplicate `axes[*].id` до provider call;
  - output CV проверяет exact one-to-one coverage входных axis IDs, отсутствие unknown/duplicate IDs и полный состав `dominant_axes` / `weakest_axes` в порядке input для ties;
  - output CV вычисляет extrema по raw per-axis scores и не использует `weight` для несуществующего aggregate.
- [ ] Не добавлять `KERNEL_DEMO_*` в `platform-actions/definitions/` (эти модули нигде не импортируются).
- [ ] Не трогать loader/runner/executor «заодно».
- [ ] Не добавлять CV для `document.generate_from_template`.

#### Definition of Done

- A03 больше не permissive schema.
- Schema tests покрывают required `commentary`, duplicate input axis IDs, missing/unknown/duplicate output axis IDs, score range и tie ordering.
- Детерминированный ActionRunner execution создаёт validated output artifact и ожидаемую action/provider/artifact event lineage.
- Validation retry сохраняет детерминированный physical provider-call accounting.
- Config, architecture, docs, generated-doc и атомные тесты зелёные.
- 11 action types имеют строгий product-configured runtime path (config + schema + fixture). Proof 11/11 scenarios — ещё нет, это M2.

#### Validation

```bash
python scripts/agent/runner.py validate-configs
python scripts/agent/runner.py validate-architecture
python scripts/agent/runner.py validate-docs
python scripts/agent/runner.py generate-docs --check
python scripts/agent/runner.py quick-check
```

#### Known Risks

- Соблазн скопировать weighted-average A02, хотя `weight` в A03 v1 не имеет формулы и aggregate отсутствует.
- Соблазн «закрыть 11/11» в том же PR без A21.

#### Stop-and-Fix Rule

- Нет тестов unique IDs, exact coverage, required `commentary` и tie ordering — контракт A03 не закрыт.

---

### M1b. `product-platforms` → `platform-sdk` only `[ ]`

Дешёвый замок. Можно параллельно с M1, не внутри ANY-257.

- [ ] Расширить `scripts/agent/validate_architecture.py`: `product-platforms` не импортирует `platform-core`, `platform-actions`, `litellm`, `pydantic_ai`, provider SDKs.

```bash
python scripts/agent/runner.py validate-architecture
python scripts/agent/runner.py quick-check
```

---

### M2. A21 Atom Runtime Proof `[ ]`

Канонические тикеты: ANY-218, ANY-219, ANY-220 (parent ANY-24). Этот milestone — напоминание, что **между 11-м атомом и cleanup proof обязателен**. Детали реализации — в тикетах A21, не здесь.

#### Goal

```text
11 standalone scenarios
3 composite workflows covering all 11 atoms
python scripts/agent/runner.py atoms-proof   # команды сейчас нет — её надо добавить
```

Сейчас: `scenarios.yaml` — 6 smoke (extract/quota/handoff/detect-questions), не матрица атомов. `workflows.yaml` — нет трёх composite на 11 атомов. `runner.py` — нет `atoms-proof`.

#### Tasks (владельцы — A21 тикеты)

- [ ] ANY-218: 11 standalone.
- [ ] ANY-219: 3 composite, все 11 атомов покрыты.
- [ ] ANY-220: CLI/evidence. Пока команды нет — не ссылаться на неё как на существующую.

#### Definition of Done

- Команда proof существует и репортит 11/11 и 3/3 на fake provider.
- Не placeholder, не `expectedFailure`.

#### Validation

Реальные команды появятся в ANY-220. До них — тесты A21 + `quick-check`.

#### Stop-and-Fix Rule

- Не начинать M3 и не трогать backlog «потому что атомы готовы», пока proof не зелёный.

---

### M3. Опционально удалить мёртвое после proof

Не gate MVP-A1 и не обязательное продолжение этого плана. Если уборка всё ещё полезна после proof — один узкий Python-only PR. **Не** менять семантику валидаторов, **не** переносить SQL, **не** fail-closed.

Сначала проверить импорты. `packages/backend/platform-actions/src/anytoolai_platform_actions/definitions/` и `schemas/` на 2026-08-16 не импортируются из Python. Не «выносить» `KERNEL_DEMO_*` — удалить мёртвые модули.

- [ ] Удалить неимпортируемые `definitions/*.py` и `schemas/*.py`.
- [ ] Удалить skeleton: API `middleware/*.py`, `handlers/run_action.py`, core `actions/registry.py`, `products/{service,registry}.py`, `prompts/{registry,renderer,repository}.py`, `bootstrap/runtime.py`, `config/{sources,references}.py`, `errors.py`, `prompt_context.py`, если по-прежнему никто не импортирует.
- [ ] Не трогать `providers/adapters/openai.py` (явный stub на не-MVP путь).
- [ ] Frontend/CE/web-mirror placeholders — **не** этот milestone; это MVP-A2.

#### Validation

```bash
python scripts/agent/runner.py quick-check
python scripts/agent/runner.py validate-architecture
```

плюс proof-команда из M2, когда она появится.

#### Stop-and-Fix Rule

- Если файл всё-таки импортируется — исключить его из cleanup. Не переписывать импорты ради удаления и не изобретать новый «правильный» пакет констант.

---

## Implementation steps

- [x] Read-only аудит.
- [x] Freeze (M0).
- [x] Переписать план: CV опциональны; A21 явный; M3=удаление мёртвого; DDD-долг в backlog.
- [ ] M1 ANY-257.
- [ ] M1b architecture lock (можно параллельно).
- [ ] M2 A21 (ANY-218/219/220).
- [ ] M3 опциональное удаление мёртвых Python-модулей; не gate MVP-A1.

## Validation

Для M1 / M1b / опционального M3:

- [ ] `python scripts/agent/runner.py quick-check`
- [ ] `python scripts/agent/runner.py validate-configs` (M1)
- [ ] `python scripts/agent/runner.py validate-architecture`
- [ ] `python scripts/agent/runner.py validate-docs` (M1)
- [ ] `python scripts/agent/runner.py generate-docs --check` (M1)

Для M2 — команды тикетов A21; `atoms-proof` появится только там.

`frontend-check` этот план не требует.

---

## Decision log

| Date | Decision | Why |
|---|---|---|
| 2026-08-16 | JSON Schema — runtime-контракт атома; Python CV опционален | Протоколы `ActionInputValidator` / `ActionOutputCrossValidator` и `.get(...)` в runner/executor. |
| 2026-08-16 | Не вводить fail-closed missing validator и не требовать 11 ключей в composition | Ломает атомы, которым достаточно схемы (`document.generate_from_template`). |
| 2026-08-16 | Для A03 нужны input uniqueness и output coverage/extrema CV, но не weighted-average A02 | ANY-257 фиксирует unique axis IDs, exact coverage и ordered ties; `weight` остаётся без формулы и aggregate в v1. |
| 2026-08-16 | `commentary` обязателен в каждом `scores` item | Решение добавлено в Canonical Contract и Required Evidence ANY-257. |
| 2026-08-16 | ANY-257 ≠ proof; A21 — отдельный обязательный milestone | Нет `atoms-proof`, нет 11 standalone, нет 3 composite. |
| 2026-08-16 | Freeze loader/runner/executor до зелёного A21 | Горячий путь атомов и composite. |
| 2026-08-16 | Нет Pydantic в core — не Critical-дефект | Архитектурный выбор JSON Schema, не пробел валидации. |
| 2026-08-16 | M3 = удалить неимпортируемое, не relocating `KERNEL_DEMO_*` | `definitions/` не импортируется. |
| 2026-08-16 | Структурный DDD не является фазой этого плана | Trigger-based backlog. Не цель перед MVP-B. |
| 2026-08-16 | MVP-A2 убран из этого плана | Канон: `mvp-a2-client-surfaces.md`. |
| 2026-08-16 | ANY-256 принят; паттерн `KERNEL_DEMO_*` в definitions не откатывать | Мёртвые модули удалить в M3 оптом. |

## Progress log

| Date | Progress | Next |
|---|---|---|
| 2026-08-16 | Аудит записан | — |
| 2026-08-16 | ANY-256 #72 на `main` | ANY-257 |
| 2026-08-16 | План переписан по review: CV не обязателен, A21 явный, DDD → backlog | M1 ANY-257 |
| 2026-08-16 | ANY-257 уточнён: `weight` остаётся без формулы v1, `commentary` required; задача уже In Review с PR #73 | Проверить/fix PR #73 против обновлённого контракта |

## Open questions

- Нужен ли standalone **scenario** для A03 уже в ANY-257, или достаточно action_config + executor test, а scenario добавит ANY-218? Рекомендация: следовать DoD тикета ANY-257; не раздувать его до A21.

## Follow-up debt

- Canvas `ddd-lite-boundary-audit.canvas.tsx` — снимок первого аудита; канон — этот файл.
- Не смешивать с ANY-257. ANY-255 и ANY-256 уже на `main`.

---

## Что не является нарушением

- Composition roots (`bootstrap.py`, `composition.py`) имеют право собирать граф.
- `lease.py` / advisory lock — инфровая координация worker.
- JSON Schema как контракт атома.
- `.get(action_type)` для опциональных Python-валидаторов.
- Пустые `__init__.py`.
- Отсутствие Pydantic-моделей payload в `platform-core`.
- Двойная structured-output проверка PydanticAI retry + platform finalize — документированный split.

Жёсткие пакетные границы держатся: нет импорта `product-platforms` из core/actions; `pydantic_ai` только в `structured_llm`; `litellm` только в `providers`; роутеры без raw SQL; `scenario_session_id` на start; расширения без промптов.

---

## Backlog аудита (только по триггеру)

Находки 16 Aug 2026. **Не исполнять пакетом.** Не цель «DDD-lite completion».

| # | Наблюдение | Триггер, когда трогать | Не триггер |
|---|---|---|---|
| 1 | `config/loader.py` ~2030 строк | Второй независимый источник конфигов **или** регулярные merge-конфликты на loader в атомных/A21 PR | «Файл большой» |
| 2 | `workflows/runner.py` ~1689 строк + SQL `action_runs_table` | Конкретный тест/баг, которому мешает SQL в runner; или правки recovery, которые нельзя безопасно ревьюить в одном файле | Подготовка к MVP-B «на всякий случай» |
| 3 | SDK Pydantic ↔ core dataclasses | Обнаруженный contract drift (поле есть в одном мире, нет в другом) **или** первый product bundle, которому нужна общая модель | Унификация до первого drift |
| 4 | `dict[str, Any]` в core | Нужен новый инвариант runtime state, который JSON Schema на атоме не покрывает | «В core нет Pydantic» |
| 5 | Строковые error/event/action codes | Повторяющиеся опечатки в CI **или** второй клиент, которому нужен общий enum | Косметика |
| 6–7 | Роутеры собирают репозитории; дубль `ScenarioRuntimeService` | Третий копипаст графа **или** расхождение quota/start vs handoff accept | «Не тонкий адаптер» само по себе |
| 8 | Толстый `run_workflow.py` | Баг claim/fail/scenario, который нельзя покрыть тестом без выноса use-case | — |
| 9 | Worker/quota SQL в обход репозиториев | Нужен второй потребитель тех же запросов **или** смена предиката в двух местах | — |
| 10 | Толстый `StructuredLlmActionExecutor` | Нужно тестировать finalize без LLM **или** менять prompt/persistence независимо | — |
| 11 | Не у всех атомов есть Python CV | Появился конкретный input↔output инвариант, который схема не выражает | «Дырка в registry» |
| 12 | Event dimensions не enforced при emit | Ломается analytics/replay из-за пустых полей | Ужесточение «чтобы совпало с YAML» |
| 13 | `.get("temperature", 0.3)` | Явные поля уже стоят во всех policy YAML **и** есть баг из-за тихого default | Fail-fast до инвентаря YAML |
| 14, 20, 21, 27, 28 | Placeholders / мёртвые definitions/schemas | M3 после proof, после проверки импортов | Перенос констант в новое место |
| 15 | Runners держат `Session` | Нужен unit-тест оркестрации без БД, который сейчас невозможен | — |
| 16, 29 | Слабые HTTP схемы / `Any` session | Ломается OpenAPI-клиент **или** неверная ошибка на проде | A2 само по себе |
| 17 | Разные error maps в роутерах | Реальный mistmap одного `code` в двух роутерах | Общая таблица «для красоты» |
| 18–19 | Широкий `except` / `a or b` в recovery | Конкретный проглоченный сбой | Сужение во время атомных PR |
| 22 | Settings tenant/region defaults | Multi-tenant **или** неверный scope из-за забытого env | — |
| 23 | Нет check product-platforms → sdk | **M1b сейчас** | — |
| 24 | Handoff repo читает чужие таблицы | Баг инварианта target session/job | — |
| 25, 30 | CE-kit/web-mirror stubs, poll strings | MVP-A2 / `mvp-a2-client-surfaces.md` | Этот план |
| 26 | Двойная structured-output validation | Изменение retry/finalize ownership в `structured-output.md` | «Убрать дубль» |

OpenAI adapter stub (`NotImplementedError`) не трогать: MVP-A путь — LiteLLM.
