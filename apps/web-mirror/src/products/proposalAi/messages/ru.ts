// Russian ProposalAI messages.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";
import { ru as tone } from "../../shared/toneMessages/ru";

export const ru: Shape<typeof en> = {
  title: "ProposalAI",
  tone,
  quotaRemaining: "Осталось {remaining} из {limit, plural, one {# предложения} few {# предложений} many {# предложений} other {# предложения}}.",
  fields: {
    taskText: "Опишите задачу",
    freelancerPositioning: "Ваше позиционирование",
    tone: "Тон (необязательно)",
    tonePlaceholder: "По умолчанию",
    language: "Язык (необязательно)",
  },
  fieldNames: {
    taskText: "Описание задачи",
    freelancerPositioning: "Ваше позиционирование",
    language: "Язык",
  },
  validation: { languageFormat: 'Язык должен выглядеть как "en" или "en-US".' },
  generate: {
    submit: "Создать предложение",
    running: "Создаём ваше предложение…",
    runFailed: "При создании предложения что-то пошло не так. Пожалуйста, попробуйте ещё раз.",
  },
};
