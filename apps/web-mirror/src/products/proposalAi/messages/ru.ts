// Russian ProposalAI messages.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const ru: Shape<typeof en> = {
  title: "ProposalAI",
  description: "Опишите задачу клиента и свои сильные стороны — мы подготовим предложение, которое можно сразу отправить.",
  quotaRemaining: "Осталось {remaining, plural, one {# предложение} few {# предложения} many {# предложений} other {# предложения}} из {limit}.",
  fields: {
    taskText: "Опишите задачу",
    taskTextPlaceholder: "Вставьте описание задачи, бриф или объявление о проекте.",
    taskTextHelp: "Если известны, укажите цель, ожидаемые результаты, ограничения и сроки.",
    freelancerPositioning: "Ваш опыт и сильные стороны",
    freelancerPositioningPlaceholder: "Опишите опыт и навыки, которые пригодятся в этом проекте.",
    freelancerPositioningHelp: "Указывайте только то, что можете подтвердить: сервис не будет придумывать за вас опыт и достижения.",
    toneLegend: "Тон предложения",
  },
  toneOptions: {
    warm: "Дружелюбный",
    neutral: "Ясный и деловой",
    firm: "Уверенный и по делу",
  },
  fieldNames: {
    taskText: "Описание задачи",
    freelancerPositioning: "Опыт и сильные стороны",
  },
  generate: {
    submit: "Составить предложение",
    running: "Составляем предложение…",
    runFailed: "Не удалось составить предложение. Попробуйте ещё раз.",
    startAnother: "Составить ещё одно предложение",
  },
};
