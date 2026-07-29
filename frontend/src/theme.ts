export type ThemePreference = 'light' | 'dark' | 'system';
type ResolvedTheme = Exclude<ThemePreference, 'system'>;

const STORAGE_KEY = 'optiflow_theme';
const DARK_MODE_QUERY = '(prefers-color-scheme: dark)';

function isThemePreference(value: string | null): value is ThemePreference {
  return value === 'light' || value === 'dark' || value === 'system';
}

function readStoredPreference(): ThemePreference {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return isThemePreference(value) ? value : 'system';
  } catch {
    return 'system';
  }
}

function resolveTheme(preference: ThemePreference): ResolvedTheme {
  if (preference !== 'system') {
    return preference;
  }

  return window.matchMedia(DARK_MODE_QUERY).matches ? 'dark' : 'light';
}

function renderTheme(preference: ThemePreference) {
  const root = document.documentElement;
  root.dataset.themePreference = preference;
  root.dataset.theme = resolveTheme(preference);
}

export function getThemePreference(): ThemePreference {
  const current = document.documentElement.dataset.themePreference ?? null;
  return isThemePreference(current) ? current : readStoredPreference();
}

export function setThemePreference(preference: ThemePreference) {
  renderTheme(preference);

  try {
    window.localStorage.setItem(STORAGE_KEY, preference);
  } catch {
    // The active theme still works when storage is unavailable.
  }

  window.dispatchEvent(
    new CustomEvent<ThemePreference>('optiflow:theme-change', {
      detail: preference,
    }),
  );
}

export function initializeTheme() {
  renderTheme(readStoredPreference());

  window.matchMedia(DARK_MODE_QUERY).addEventListener('change', () => {
    if (getThemePreference() === 'system') {
      renderTheme('system');
    }
  });
}
