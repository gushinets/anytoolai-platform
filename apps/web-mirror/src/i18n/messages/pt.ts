// Portuguese (generic) host messages.
import type { Shape } from "../messageTypes";
import type { en } from "./en";

export const pt: Shape<typeof en> = {
  language: { label: "Idioma" },
  nav: {
    label: "Ferramentas",
    allTools: "Todas as ferramentas",
    runInProgress: "Uma execução está em andamento. Se você sair agora, não verá o resultado e a cota não será restituída.",
  },
  loading: "Carregando {product}…",
  unavailable: "{product} está indisponível no momento. Recarregue a página.",
  quotaExhausted: "Você usou todas as execuções de {product} por enquanto.",
  resultFetchFailed: "Seu resultado está pronto, mas não conseguimos carregá-lo. Tente novamente.",
  starting: "Iniciando…",
  generating: "Gerando…",
  identityUnavailable: "Não foi possível verificar sua identidade. Recarregue a página e tente novamente.",
  retry: "Tentar novamente",
  formLabel: "Formulário {product}",
  errors: {
    startFailed: "Não foi possível iniciar {product}. Tente novamente.",
    timeout: "Está demorando mais do que o esperado. Tente novamente.",
    connectionLost: "A conexão foi perdida enquanto aguardávamos seu resultado. Tente novamente.",
    tryAgain: "Tente novamente.",
  },
  result: {
    copy: "Copiar",
    copying: "Copiando…",
    copied: "Copiado",
    copyFailed: "Não foi possível copiar para a área de transferência. Copie o texto acima manualmente.",
  },
  // Code review finding: outerWhitespace/maxLength made `{field}` the subject of "pode"/"deve"
  // (which agree in number: pode/podem, deve/devem) -- every message is now a label-colon-fragment
  // instead, matching `required`'s already-safe shape.
  validation: {
    required: "{field}: campo obrigatório.",
    outerWhitespace: "{field}: sem espaços no início ou no fim.",
    maxLength: "{field}: máximo {maxLength, plural, one {# caractere} many {# de caracteres} other {# caracteres}}.",
  },
};
