import type { Shape } from "../../i18n/messageTypes";
import type { en } from "./en";

export const ru: Shape<typeof en> = {
  title: "Проверьте передачу",
  loading: "Загрузка передачи…",
  notFound: "Эта ссылка на передачу недействительна.",
  loadFailed: "Не удалось загрузить эту передачу. Попробуйте ещё раз.",
  retry: "Повторить",
  actionFailed: "Не удалось выполнить действие. Попробуйте ещё раз.",
  fields: {
    from: "От",
    to: "Кому",
    expires: "Действует до",
    status: "Статус",
  },
  accept: "Принять",
  decline: "Отклонить",
  accepting: "Принимаем…",
  declining: "Отклоняем…",
  status: {
    waiting: "Ждёт вашего решения",
    accepted: "Принята",
    declined: "Отклонена",
    expired: "Истекла",
    failed: "Не удалась",
  },
};
