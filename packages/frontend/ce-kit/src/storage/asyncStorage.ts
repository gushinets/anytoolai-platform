/**
 * Injectable async storage contract, narrowed to a single string key/value per call (`get`
 * returns the value or `undefined` if absent; `set` takes one key and one string value). This is
 * not the same shape as `chrome.storage.local` (which is multi-key and untyped-value), so a
 * Chrome extension needs a thin per-key adapter over it -- but that adapter, not this contract
 * itself, is what depends on `chrome.storage.local`, keeping CE-kit free of `@types/chrome`.
 */
export type AsyncStorage = {
  get(key: string): Promise<string | undefined>;
  set(key: string, value: string): Promise<void>;
  remove(key: string): Promise<void>;
};
