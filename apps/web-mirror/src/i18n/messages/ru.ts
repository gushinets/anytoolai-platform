// Russian host messages.
import type { Shape } from "../messageTypes";
import type { en } from "./en";

export const ru: Shape<typeof en> = {
  language: { label: "Язык" },
  loading: "Загружаем {product}…",
  unavailable: "{product} сейчас недоступен. Пожалуйста, перезагрузите страницу.",
  quotaExhausted: "Вы использовали все запуски {product} на данный момент.",
  resultFetchFailed: "Ваш результат готов, но нам не удалось его загрузить. Пожалуйста, попробуйте ещё раз.",
  starting: "Запускаем…",
  generating: "Генерируем…",
  identityUnavailable: "Не удалось подтвердить вашу личность. Пожалуйста, перезагрузите страницу и попробуйте ещё раз.",
  retry: "Повторить",
  formLabel: "Форма {product}",
  errors: {
    startFailed: "Не удалось запустить {product}. Пожалуйста, попробуйте ещё раз.",
    timeout: "Это занимает больше времени, чем ожидалось. Пожалуйста, попробуйте ещё раз.",
    connectionLost: "Соединение потеряно во время ожидания результата. Пожалуйста, попробуйте ещё раз.",
    tryAgain: "Пожалуйста, попробуйте ещё раз.",
  },
  result: {
    copy: "Копировать",
    copying: "Копируем…",
    copied: "Скопировано",
    copyFailed: "Не удалось скопировать в буфер обмена. Пожалуйста, скопируйте текст выше вручную.",
  },
  // Unlike en/fr/it/de/pt (code review finding, fixed there), these are already label-colon-noun
  // fragments -- no verb agrees with `{field}`'s own grammatical number. Already safe; left as-is.
  validation: {
    required: "{field}: обязательное поле.",
    outerWhitespace: "{field}: не должно быть пробелов в начале и в конце.",
    maxLength: "{field}: не более {maxLength, plural, one {# символ} few {# символа} many {# символов} other {# символа}}.",
  },
};
