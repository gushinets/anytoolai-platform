import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const ru: Shape<typeof en> = {
  title: "Brief Decoder",
  description: "Превратите бриф клиента в структурированные данные, риски, вопросы для уточнения и сводку, которую можно скопировать.",
  quotaRemaining: "Осталось {remaining} из {limit, plural, one {# разбора} few {# разборов} many {# разборов} other {# разбора}}.",
  fields: {
    briefText: "Бриф клиента",
    briefTextPlaceholder: "Вставьте бриф, запрос или описание вакансии от клиента.",
    briefTextHelp: "Вставьте бриф как есть. Чем подробнее бриф, тем точнее вопросы.",
  },
  decode: {
    submit: "Разобрать бриф",
    running: "Разбираем ваш бриф…",
    runFailed: "При разборе брифа что-то пошло не так. Пожалуйста, попробуйте ещё раз.",
    startAnother: "Разобрать другой бриф",
  },
  result: {
    brief: "Бриф",
    notProvided: "Не указано",
    issues: "Проблемы",
    noIssues: "Проблем не найдено.",
    evidence: "Основание: {text}",
    questions: "{count, plural, one {# уточняющий вопрос} few {# уточняющих вопроса} many {# уточняющих вопросов} other {# уточняющего вопроса}}",
    noQuestions: "Уточняющие вопросы не сформированы.",
    rationale: "Зачем спрашивать: {text}",
    document: "Итоговый документ",
  },
  briefFields: {
    project_goal: "Цель проекта",
    deliverables: "Результаты",
    deadline: "Срок",
    budget: "Бюджет",
    target_audience: "Целевая аудитория",
    constraints: "Ограничения",
  },
  severity: {
    low: "Низкая серьёзность",
    medium: "Средняя серьёзность",
    high: "Высокая серьёзность",
  },
  priority: {
    low: "Низкий приоритет",
    medium: "Средний приоритет",
    high: "Высокий приоритет",
  },
  categories: {
    missing_information: "Недостающая информация",
    ambiguity: "Неоднозначность",
    scope_risk: "Риск по объёму работ",
    timeline_risk: "Риск по срокам",
    budget_risk: "Риск по бюджету",
    contradiction: "Противоречие",
  },
};
