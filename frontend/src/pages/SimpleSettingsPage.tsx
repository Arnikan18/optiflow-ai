import { useEffect, useState } from 'react';
import { api } from '../api/client';
import {
  DEFAULT_UI_PREFERENCES,
  readUiPreferences,
  saveUiPreferences,
  type UiPreferences,
} from '../preferences';
import {
  getThemePreference,
  setThemePreference,
  type ThemePreference,
} from '../theme';
import type {
  LLMProviderName,
  LLMSettingsPayload,
  LLMSettingsStatus,
} from '../types/api';

const THEMES: Array<{ id: ThemePreference; label: string }> = [
  { id: 'system', label: 'Use device' },
  { id: 'light', label: 'Light' },
  { id: 'dark', label: 'Dark' },
];

export function SimpleSettingsPage() {
  const [theme, setTheme] = useState<ThemePreference>(getThemePreference);
  const [preferences, setPreferences] = useState<UiPreferences>(readUiPreferences);
  const [status, setStatus] = useState<LLMSettingsStatus | null>(null);
  const [models, setModels] = useState<Record<LLMProviderName, string[]>>({
    gemini: ['gemini-2.0-flash'],
    groq: ['llama-3.1-8b-instant'],
  });
  const [provider, setProvider] = useState<LLMProviderName>('gemini');
  const [model, setModel] = useState('gemini-2.0-flash');
  const [apiKey, setApiKey] = useState('');
  const [busy, setBusy] = useState<'test' | 'save' | 'disconnect' | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [catalog, nextStatus] = await Promise.all([
          api.getLLMModels(),
          api.getLLMSettings(),
        ]);
        if (cancelled) return;
        const nextModels = Object.fromEntries(
          catalog.providers.map((item) => [item.id, item.models]),
        ) as Record<LLMProviderName, string[]>;
        const nextProvider = nextStatus.active_llm_provider ?? catalog.providers[0]?.id ?? 'gemini';
        setModels(nextModels);
        setStatus(nextStatus);
        setProvider(nextProvider);
        setModel(
          nextStatus.providers[nextProvider]?.model_name
          ?? catalog.providers.find((item) => item.id === nextProvider)?.default_model
          ?? nextModels[nextProvider][0],
        );
      } catch {
        if (!cancelled) setError('Core settings are unavailable. Personal display settings still work.');
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const updatePreference = <Key extends keyof UiPreferences>(
    key: Key,
    value: UiPreferences[Key],
  ) => {
    const next = { ...preferences, [key]: value };
    setPreferences(next);
    saveUiPreferences(next);
  };

  const chooseTheme = (next: ThemePreference) => {
    setTheme(next);
    setThemePreference(next);
  };

  const connect = async (action: 'test' | 'save') => {
    if (!apiKey.trim()) {
      setError('Enter a provider API key.');
      return;
    }
    setBusy(action);
    setMessage(null);
    setError(null);
    const payload: LLMSettingsPayload = {
      version: 1,
      mode: 'ai_assisted',
      active_llm_provider: provider,
      providers: {
        [provider]: {
          model_name: model,
          credentials: [{ label: 'Primary', api_key: apiKey.trim(), priority: 0 }],
        },
      },
    };
    try {
      const result = action === 'test'
        ? await api.testLLMSettings(payload)
        : await api.saveLLMSettings(payload);
      if (!result.connected) throw new Error(result.credentials[0]?.message ?? 'Provider connection failed.');
      setMessage(action === 'test' ? 'Connection works. Nothing was saved.' : 'AI-assisted mode is connected.');
      if (action === 'save') {
        setApiKey('');
        setStatus(await api.getLLMSettings());
        updatePreference('decisionEngine', 'ai_assisted');
      }
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Provider connection failed.');
    } finally {
      setBusy(null);
    }
  };

  const disconnect = async () => {
    setBusy('disconnect');
    setMessage(null);
    setError(null);
    try {
      setStatus(await api.disconnectLLM(null));
      updatePreference('decisionEngine', 'rules_only');
      setMessage('Rules-only mode is active. Saved provider credentials were removed.');
    } catch (caught: unknown) {
      setError(caught instanceof Error ? caught.message : 'Core could not switch modes.');
    } finally {
      setBusy(null);
    }
  };

  const restore = () => {
    chooseTheme('system');
    setPreferences(DEFAULT_UI_PREFERENCES);
    saveUiPreferences(DEFAULT_UI_PREFERENCES);
  };

  return (
    <div className="min-h-full paper-noise">
      <header className="border-b border-border-dim bg-abyss">
        <div className="mx-auto max-w-5xl px-5 py-9 sm:px-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-sm font-bold text-ops-amber">Settings</p>
              <h1 className="mt-1 text-3xl font-extrabold tracking-[-0.045em] sm:text-4xl">
                Make OptiFlow comfortable
              </h1>
            </div>
            <button
              type="button"
              onClick={restore}
              className="min-h-11 rounded-xl border border-border-base bg-deep px-4 py-2 text-sm font-bold text-ink-secondary focus-ring"
            >
              Restore defaults
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-4 px-5 py-7 sm:px-8">
        {error && <p className="rounded-xl border border-ops-rose/30 bg-ops-rose/[0.06] p-4 text-sm font-bold text-ops-rose" role="alert">{error}</p>}
        {message && <p className="rounded-xl border border-ops-emerald/30 bg-ops-emerald/[0.06] p-4 text-sm font-bold text-ops-emerald" role="status">{message}</p>}

        <section className="rounded-2xl border border-border-dim bg-abyss p-5 shadow-card">
          <h2 className="text-xl font-extrabold">Appearance</h2>
          <div className="mt-4 grid grid-cols-3 gap-2">
            {THEMES.map((option) => (
              <button
                key={option.id}
                type="button"
                aria-pressed={theme === option.id}
                onClick={() => chooseTheme(option.id)}
                className={`min-h-12 rounded-xl border px-4 py-3 text-sm font-bold focus-ring ${
                  theme === option.id
                    ? 'border-ops-cyan bg-ops-cyan/[0.07] text-ops-cyan'
                    : 'border-border-dim bg-deep text-ink-secondary'
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </section>

        <details className="group rounded-2xl border border-border-dim bg-abyss shadow-card">
          <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between rounded-2xl px-5 py-4 text-lg font-extrabold focus-ring">
            <span>Experience</span>
            <span className="text-xl text-ops-violet transition-transform group-open:rotate-45">+</span>
          </summary>
          <div className="border-t border-border-dim p-5">
            <p className="text-sm font-bold text-ink-secondary">Walkthrough pace</p>
            <div className="mt-2 grid grid-cols-3 gap-2">
              {(['focused', 'standard', 'deliberate'] as const).map((pace) => (
                <button
                  key={pace}
                  type="button"
                  onClick={() => updatePreference('walkthroughPace', pace)}
                  className={`min-h-11 rounded-xl border px-3 text-sm font-bold capitalize focus-ring ${
                    preferences.walkthroughPace === pace
                      ? 'border-ops-violet bg-ops-violet/[0.07] text-ops-violet'
                      : 'border-border-dim bg-deep text-ink-secondary'
                  }`}
                >
                  {pace}
                </button>
              ))}
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <label className="flex min-h-12 items-center gap-3 rounded-xl border border-border-dim bg-deep px-4">
                <input
                  type="checkbox"
                  checked={preferences.motion === 'reduced'}
                  onChange={(event) => updatePreference('motion', event.target.checked ? 'reduced' : 'system')}
                  className="h-5 w-5 accent-current"
                />
                <span className="text-sm font-bold">Reduce motion</span>
              </label>
              <label className="flex min-h-12 items-center gap-3 rounded-xl border border-border-dim bg-deep px-4">
                <input
                  type="checkbox"
                  checked={preferences.detail === 'compact'}
                  onChange={(event) => updatePreference('detail', event.target.checked ? 'compact' : 'guided')}
                  className="h-5 w-5 accent-current"
                />
                <span className="text-sm font-bold">Compact explanations</span>
              </label>
            </div>
          </div>
        </details>

        <section className="rounded-2xl border border-border-dim bg-abyss shadow-card">
          <div className="flex flex-wrap items-center justify-between gap-3 p-5">
            <div>
              <h2 className="text-xl font-extrabold">Decision engine</h2>
              <p className="mt-1 text-sm text-ink-muted">
                {status?.mode === 'ai_assisted' ? 'AI-assisted explanations' : 'Deterministic rules-only mode'}
              </p>
            </div>
            {status?.mode === 'ai_assisted' && (
              <button
                type="button"
                disabled={busy !== null}
                onClick={() => void disconnect()}
                className="min-h-11 rounded-xl border border-ops-rose/30 px-4 text-sm font-bold text-ops-rose disabled:opacity-40 focus-ring"
              >
                {busy === 'disconnect' ? 'Switching…' : 'Use rules only'}
              </button>
            )}
          </div>

          <details className="group border-t border-border-dim">
            <summary className="flex min-h-14 cursor-pointer list-none items-center justify-between rounded-b-2xl px-5 py-4 text-base font-bold text-ops-amber focus-ring">
              <span>Configure AI provider</span>
              <span className="text-xl transition-transform group-open:rotate-45">+</span>
            </summary>
            <div className="border-t border-border-dim p-5">
              <div className="grid gap-3 sm:grid-cols-2">
                <label>
                  <span className="text-sm font-bold text-ink-secondary">Provider</span>
                  <select
                    value={provider}
                    onChange={(event) => {
                      const next = event.target.value as LLMProviderName;
                      setProvider(next);
                      setModel(models[next][0]);
                    }}
                    className="mt-2 min-h-11 w-full rounded-xl border border-border-base bg-deep px-4 text-base font-bold focus-ring"
                  >
                    <option value="gemini">Google Gemini</option>
                    <option value="groq">GroqCloud</option>
                  </select>
                </label>
                <label>
                  <span className="text-sm font-bold text-ink-secondary">Model</span>
                  <select
                    value={model}
                    onChange={(event) => setModel(event.target.value)}
                    className="mt-2 min-h-11 w-full rounded-xl border border-border-base bg-deep px-4 text-base font-bold focus-ring"
                  >
                    {models[provider].map((item) => <option key={item} value={item}>{item}</option>)}
                  </select>
                </label>
              </div>
              <label className="mt-4 block">
                <span className="text-sm font-bold text-ink-secondary">Provider API key</span>
                <input
                  type="password"
                  autoComplete="off"
                  value={apiKey}
                  onChange={(event) => setApiKey(event.target.value)}
                  placeholder="Sent directly to encrypted Core storage"
                  className="mt-2 min-h-11 w-full rounded-xl border border-border-base bg-deep px-4 text-base focus-ring"
                />
              </label>
              <div className="mt-4 flex justify-end gap-2">
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void connect('test')}
                  className="min-h-11 rounded-xl border border-border-base px-4 text-sm font-bold text-ink-secondary disabled:opacity-40 focus-ring"
                >
                  {busy === 'test' ? 'Testing…' : 'Test'}
                </button>
                <button
                  type="button"
                  disabled={busy !== null}
                  onClick={() => void connect('save')}
                  className="min-h-11 rounded-xl bg-ops-amber px-5 text-sm font-bold text-white disabled:opacity-40 focus-ring"
                >
                  {busy === 'save' ? 'Saving…' : 'Save & use AI'}
                </button>
              </div>
            </div>
          </details>
        </section>
      </main>
    </div>
  );
}
