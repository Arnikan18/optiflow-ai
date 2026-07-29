export type WalkthroughPace = 'focused' | 'standard' | 'deliberate';
export type MotionPreference = 'system' | 'reduced';
export type DetailPreference = 'guided' | 'compact';
export type DecisionEngineMode = 'rules_only' | 'ai_assisted';

export interface UiPreferences {
  walkthroughPace: WalkthroughPace;
  motion: MotionPreference;
  detail: DetailPreference;
  decisionEngine: DecisionEngineMode;
}

export const DEFAULT_UI_PREFERENCES: UiPreferences = {
  walkthroughPace: 'standard',
  motion: 'system',
  detail: 'guided',
  decisionEngine: 'rules_only',
};

export const WALKTHROUGH_DWELL_MS: Record<WalkthroughPace, number> = {
  focused: 1_600,
  standard: 2_600,
  deliberate: 4_000,
};

const STORAGE_KEY = 'optiflow_ui_preferences';
const EVENT_NAME = 'optiflow:preferences-change';

function isUiPreferences(value: unknown): value is UiPreferences {
  if (!value || typeof value !== 'object') return false;
  const candidate = value as Partial<UiPreferences>;
  return (
    ['focused', 'standard', 'deliberate'].includes(candidate.walkthroughPace ?? '')
    && ['system', 'reduced'].includes(candidate.motion ?? '')
    && ['guided', 'compact'].includes(candidate.detail ?? '')
    && ['rules_only', 'ai_assisted'].includes(candidate.decisionEngine ?? '')
  );
}

export function readUiPreferences(): UiPreferences {
  if (typeof window === 'undefined') return DEFAULT_UI_PREFERENCES;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? 'null');
    return isUiPreferences(parsed) ? parsed : DEFAULT_UI_PREFERENCES;
  } catch {
    return DEFAULT_UI_PREFERENCES;
  }
}

export function saveUiPreferences(preferences: UiPreferences): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(preferences));
  } catch {
    // Preferences still apply for the current page when storage is unavailable.
  }

  document.documentElement.dataset.userMotion = preferences.motion;
  document.documentElement.dataset.detailLevel = preferences.detail;
  window.dispatchEvent(new CustomEvent<UiPreferences>(EVENT_NAME, { detail: preferences }));
}

export function initializeUiPreferences(): void {
  const preferences = readUiPreferences();
  document.documentElement.dataset.userMotion = preferences.motion;
  document.documentElement.dataset.detailLevel = preferences.detail;
}

export function subscribeToUiPreferences(
  listener: (preferences: UiPreferences) => void,
): () => void {
  const handleChange = (event: Event) => {
    listener((event as CustomEvent<UiPreferences>).detail);
  };
  window.addEventListener(EVENT_NAME, handleChange);
  return () => window.removeEventListener(EVENT_NAME, handleChange);
}
