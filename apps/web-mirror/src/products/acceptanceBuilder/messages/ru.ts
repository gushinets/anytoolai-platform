import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const ru: Shape<typeof en> = {
  title: "Acceptance Builder",
  description: "Превратите бриф клиента в критерии приёмки или проверьте готовую работу по брифу.",
  quotaRemaining: "Осталось {remaining} из {limit, plural, one {# запуска} few {# запусков} many {# запусков} other {# запуска}}.",
  modes: {
    legend: "Режим",
    draft: "Составить критерии",
    check: "Проверить работу",
  },
  fields: {
    briefText: "Бриф клиента",
    briefTextPlaceholder: "Вставьте бриф, запрос или вакансию клиента.",
    briefTextHelp: "Вставьте бриф как есть.",
    deliverableText: "Готовая работа",
    deliverableTextPlaceholder: "Вставьте текст готовой работы.",
    deliverableTextHelp: "Вставьте текст, который вы собираетесь сдать.",
  },
  draft: {
    submit: "Составить критерии",
    running: "Составляем критерии приёмки…",
    runFailed: "Не удалось составить критерии. Попробуйте ещё раз.",
    resultTitle: "Критерии приёмки",
    placeholder: "Критерии приёмки появятся здесь после составления.",
    regenerate: "Составить заново",
  },
  check: {
    submit: "Проверить работу",
    running: "Проверяем работу…",
    runFailed: "Не удалось проверить работу. Попробуйте ещё раз.",
    resultTitle: "Проверка работы",
    placeholder: "Результат проверки появится здесь после запуска.",
    regenerate: "Проверить ещё раз",
  },
  result: {
    verdictScope: "Вердикт основан на четырёх общих критериях проверки, а не на каждом из перечисленных ниже критериев по отдельности.",
    recap: "Пересказ (только для просмотра, не копируется)",
  },
};
