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
    freelancerPositioningHelp: "Текст строится только на том, что здесь написано. Указывайте проверяемые факты: инструменты, кейсы, результаты.",
    toneLegend: "Тон предложения",
    required: "обязательно",
    languageLabel: "Язык предложения",
    languageHelp: "Не язык интерфейса. По умолчанию предложение пишется на языке задачи.",
    languageAuto: "Как в задаче",
    counterNear: "Вы приближаетесь к лимиту в {max} символов.",
    counterOver: "Превышен лимит в {max} символов.",
  },
  toneOptions: {
    warm: "Дружелюбный",
    neutral: "Ясный и деловой",
    firm: "Уверенный и по делу",
  },
  fieldNames: {
    taskText: "Описание задачи",
    freelancerPositioning: "Ваш опыт и сильные стороны",
  },
  result: {
    gapsTitle: "Чего нет в вашем опыте",
    gapsHint: "Предложение этого не заявляет. Добавьте сами или не упоминайте.",
  },
  generate: {
    submit: "Составить предложение",
    running: "Составляем предложение…",
    runFailed: "Не удалось составить предложение. Попробуйте ещё раз.",
    resultTitle: "Предложение",
    placeholder: "После составления предложение появится здесь.",
    regenerate: "Пересоставить предложение",
  },
};
