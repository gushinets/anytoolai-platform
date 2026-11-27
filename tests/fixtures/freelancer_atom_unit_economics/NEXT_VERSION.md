# Поправки для следующей версии датасета Freelancer Suite

Исходные JSON и опубликованные результаты относятся к прогонам 25–26 ноября 2026 года.
Эти поправки применяются в следующей версии набора. Результаты на ней следует
публиковать с указанием новой версии и оценивать всех сравниваемых кандидатов по одним правилам.

## Acceptance Builder

Все три замечания относятся к пилотному файлу [acceptance_builder.json](acceptance_builder.json).

- **Совместимость вердикта со статусами** (`ab-06-missing-json`, `ab-07-delivery-text-directions`).
  В проверке учитывайте сочетание полей. `partially_meets` допустим, когда недовыполненные
  общие критерии имеют статус `partial`. При `mismatch` у такого критерия нужен
  `does_not_meet`. В `ab-10-product-photography` отдельно зафиксируйте допустимые сочетания
  для частичного покрытия кадров и нарушения обязательного порога качества.
  [Замечание к вердикту](https://github.com/gushinets/anytoolai-platform/pull/293#discussion_r4715276382)
- **Вход в личный кабинет** (`ab-09-store-checkout`). Засчитывайте просмотр заказа после
  регистрации. Проверку последующего входа отмечайте как неподтверждённую до появления
  явного подтверждения в отчёте о сдаче.
  [Замечание ко входу](https://github.com/gushinets/anytoolai-platform/pull/293#discussion_r4715276385)
- **Передача протокола** (`ab-09-store-checkout`). В `completeness` засчитывайте передачу
  ссылки и инструкции. Протокол указан как существующий. Его передачу учитывайте по явному
  подтверждению, а функциональную готовность магазина оценивайте по её собственным критериям.
  [Замечание к протоколу](https://github.com/gushinets/anytoolai-platform/pull/293#discussion_r4715276395)

## Brief Decoder

- **Сохранение данных Excel** (`bd-04-sheets`). В `rubric.required` добавьте требование
  сохранить остальные данные исходных таблиц. Засчитывайте его в `deliverables` или
  `constraints` вместе с действующими требованиями к сортировке, удалению дубликатов
  и подсветке различий. [Кейс](brief_decoder.json) ·
  [Замечание](https://github.com/gushinets/anytoolai-platform/pull/293#discussion_r4715276399)

## Client Update Writer

- **Просьба к клиенту.** В `cuw-h02-illustration-preview` и `cuw-h05-call-time` ожидается
  текст без просьб к клиенту. В `cuw-h04-testimonials-rounds` просьба необязательна,
  а при наличии должна появиться один раз. Примените это правило и в копии сценарной
  рубрики `cuw-h04-testimonials-rounds`. Для кейсов, которым нужна просьба, сохраните
  требование об одном упоминании. [Атомные кейсы](client_update_writer_holdout.json) ·
  [Сценарный кейс](scenario-probes.json) ·
  [Замечание](https://github.com/gushinets/anytoolai-platform/pull/293#discussion_r4715276405)

## ProposalAI

- **Опыт работы с HubSpot** (`pa-04-hubspot-pilot`). В `claims_to_avoid` для RU и EN
  явно укажите, что исполнитель не соответствует требованию о десяти годах опыта
  для полной интеграции. Для отдельного пилота с одной формой это требование не действует.
  [Кейс](proposal_ai.json) ·
  [Замечание](https://github.com/gushinets/anytoolai-platform/pull/293#discussion_r4715276410)
