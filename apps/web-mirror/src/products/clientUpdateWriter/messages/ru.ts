// Russian Client Update Writer messages.
import type { Shape } from "../../../i18n/messageTypes";
import type { en } from "./en";

export const ru: Shape<typeof en> = {
  title: "Client Update Writer",
  quotaRemaining: "Осталось {remaining} из {limit, plural, one {# запуска Client Update Writer} few {# запусков Client Update Writer} many {# запусков Client Update Writer} other {# запуска Client Update Writer}}.",
  modes: {
    legend: "Режим",
    update: "Обновление",
    reply_draft: "Черновик ответа",
    prepaid_request: "Запрос предоплаты",
  },
  fields: {
    progressNotes: "Заметки о ходе работы",
    clientMessage: "Сообщение клиента",
    replyGoal: "Цель ответа",
    billingNotes: "Заметки по оплате",
    billingAmount: "Сумма",
    billingDueDate: "Срок оплаты (необязательно)",
    tone: "Тон",
    tonePlaceholder: "Выберите тон",
  },
  fieldNames: {
    progressNotes: "Заметки о ходе работы",
    clientMessage: "Сообщение клиента",
    replyGoal: "Цель ответа",
    billingNotes: "Заметки по оплате",
    billingAmount: "Сумма",
    billingDueDate: "Срок оплаты",
    tone: "Тон",
  },
  update: {
    submit: "Написать обновление",
    running: "Пишем ваше обновление…",
    runFailed: "При написании обновления что-то пошло не так. Пожалуйста, попробуйте ещё раз.",
  },
  reply_draft: {
    submit: "Написать ответ",
    running: "Пишем ваш ответ…",
    runFailed: "При написании ответа что-то пошло не так. Пожалуйста, попробуйте ещё раз.",
  },
  prepaid_request: {
    submit: "Написать запрос",
    running: "Пишем ваш запрос…",
    runFailed: "При написании запроса что-то пошло не так. Пожалуйста, попробуйте ещё раз.",
  },
};
