// Russian host messages.
import type { Shape } from "../messageTypes";
import type { en } from "./en";

export const ru: Shape<typeof en> = {
  language: { label: "Язык" },
  loading: "Загрузка {product}…",
  unavailable: "{product} сейчас недоступен. Обновите страницу.",
  quotaExhausted: "Лимит использования {product} исчерпан.",
  resultFetchFailed: "Результат готов, но загрузить его не удалось. Попробуйте ещё раз.",
  starting: "Запускаем…",
  generating: "Готовим результат…",
  identityUnavailable: "Не удалось проверить ваш сеанс. Обновите страницу и попробуйте ещё раз.",
  retry: "Попробовать ещё раз",
  formLabel: "Форма {product}",
  errors: {
    startFailed: "Не удалось начать работу с {product}. Попробуйте ещё раз.",
    timeout: "Ожидание затянулось. Попробуйте ещё раз.",
    connectionLost: "Соединение прервалось, пока мы ждали результат. Попробуйте ещё раз.",
    tryAgain: "Попробуйте ещё раз.",
  },
  result: {
    copy: "Скопировать",
    copying: "Копируем…",
    copied: "Скопировано",
    copyFailed: "Не удалось скопировать текст. Выделите его выше и скопируйте вручную.",
  },
  // These label-colon fragments do not require agreement with `{field}`'s grammatical number.
  validation: {
    required: "{field}: обязательное поле.",
    outerWhitespace: "{field}: уберите пробелы в начале или конце.",
    maxLength: "{field}: не более {maxLength, plural, one {# символ} few {# символа} many {# символов} other {# символа}}.",
  },
};
