// Russian ProposalAI messages.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const ru: Shape<typeof en> = {
  title: "ProposalAI",
  description: "Превратите бриф клиента и ваши сильные стороны в готовое к отправке предложение.",
  quotaRemaining: "Осталось {remaining} из {limit, plural, one {# предложения} few {# предложений} many {# предложений} other {# предложения}}.",
  fields: {
    taskText: "Опишите задачу",
    taskTextPlaceholder: "Вставьте задачу клиента, бриф или описание вакансии.",
    taskTextHelp: "Укажите цель, результаты, ограничения и сроки, если они известны.",
    freelancerPositioning: "Ваше позиционирование",
    freelancerPositioningPlaceholder: "Опишите опыт и сильные стороны, которые делают вас подходящим кандидатом.",
    freelancerPositioningHelp: "Указывайте только то, что можете подтвердить — предложение не будет придумывать опыт.",
    toneLegend: "Стиль предложения",
  },
  toneOptions: {
    warm: "Тёплый и располагающий",
    neutral: "Ясный и профессиональный",
    firm: "Уверенный и прямой",
  },
  fieldNames: {
    taskText: "Описание задачи",
    freelancerPositioning: "Ваше позиционирование",
  },
  generate: {
    submit: "Создать предложение",
    running: "Создаём ваше предложение…",
    runFailed: "При создании предложения что-то пошло не так. Пожалуйста, попробуйте ещё раз.",
    startAnother: "Создать ещё одно предложение",
  },
};
