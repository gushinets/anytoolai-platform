# Freelancer Suite. Входы Atom Lab

Фиксированная выборка эксперимента ANY-936 от 25–26 ноября 2026 года.
Каждая запись содержит версии `inputs.ru` и `inputs.en` одного смыслового кейса.
Поле `sources` описывает происхождение и адаптацию примера.

| Набор | Файлы | Покрытие |
| --- | --- | --- |
| Пилот | `brief_decoder.json`, `proposal_ai.json`, `acceptance_builder.json` | 30 пар RU/EN на трёх промптах. По первой паре из каждого файла использовали для калибровки (`calibration: true`). |
| Финалисты | `*_holdout.json` | 45 пар RU/EN на 15 промптах пяти продуктов. Те же 90 входов использовали в повторном сравнении Luna. |
| Полные сценарии | `scenario-probes.json` | Восемь пар RU/EN. Вход подаётся на старт сценария, следующие шаги получают фактические промежуточные результаты. |

## Промпты и оценка

Все 15 продуктовых промптов использовали версию `.v1` из ревизии
`452b879c3f8a1d9b57a18c151af6a607e9eb4b57`. Исходники в той ревизии
находятся в каталоге `packages/backend/product-platforms/freelancer-suite/src/anytoolai_freelancer_suite/products/<product>/prompts/`.
Файл промпта определяется по `prompt_ref`, а для полного сценария список
промптов указан в `step_prompts`. Три промпта пилота — `brief_decoder.extract_brief.v1`,
`proposal_ai.compose_persuasive_text.v1` и `acceptance_builder.compare.v1`.

`rubric` хранит критерии для конкретного атомного или сквозного кейса.
В holdout поле `scenario_rubric` описывает критерии всего сценария.
Если сквозная рубрика ссылается на атомные шаги, ищите их в holdout по
`scenario_case_id` и `prompt_ref`.

Правила зачёта, стоимость и выводы приведены в
[решении по Luna и Sol](../../../docs/experiments/freelancer-model-selection-2026-11-26.md).
Замечания, выявленные после прогонов, собраны в
[поправках для следующей версии](NEXT_VERSION.md).
