/**
 * BackendSettings.tsx — Collapsible back-end URL editor + reachability indicator.
 *
 * Self-contained via backend-url.ts and api.checkHealth. Props: {} (FROZEN-6).
 * Renders a summary row (always visible) with a health dot and disclosure toggle,
 * and an expanded panel with a URL input, Save, and Use default buttons.
 *
 * FROZEN-4 CSS classes used (task8 defines them in styles.css):
 *   .backend-settings
 *   .backend-settings__summary
 *   .backend-settings__dot  (+ --ok | --bad | --checking)
 *   .backend-settings__label
 *   .backend-settings__toggle
 *   .backend-settings__panel
 *   .backend-settings__input
 *   .backend-settings__save
 *   .backend-settings__default
 *
 * @module components/common/BackendSettings
 */

import { useState, useEffect, useCallback } from 'preact/hooks';
import {
  getBackendUrl,
  setBackendUrl,
  onBackendUrlChange,
  backendLabel,
} from '../../backend-url';
import * as api from '../../api';
import type { BackendSettingsProps } from '../../types';

/**
 * Health dot title text.
 */
function healthTitle(health: 'checking' | 'ok' | 'bad'): string {
  if (health === 'ok') return 'reachable';
  if (health === 'bad') return 'unreachable';
  return 'checking…';
}

/**
 * Shared collapsible back-end settings panel + reachability indicator.
 * Collapsed by default (OQ1). No reload on save (live re-apply, OQ2).
 */
export function BackendSettings(_props: BackendSettingsProps) {
  const [expanded, setExpanded] = useState(false);
  const [url, setUrl] = useState(() => getBackendUrl());
  const [draft, setDraft] = useState(() => getBackendUrl());
  const [health, setHealth] = useState<'checking' | 'ok' | 'bad'>('checking');

  // Subscribe to external URL changes (from other components calling setBackendUrl).
  // When the URL changes, reset both url and draft to the new value.
  useEffect(() => {
    const unsub = onBackendUrlChange((newUrl) => {
      setUrl(newUrl);
      setDraft(newUrl);
    });
    return unsub;
  }, []);

  // Re-probe health whenever the active URL changes.
  useEffect(() => {
    setHealth('checking');
    api.checkHealth()
      .then((ok) => setHealth(ok ? 'ok' : 'bad'))
      .catch(() => setHealth('bad'));
  }, [url]);

  const toggle = useCallback(() => setExpanded(!expanded), [expanded]);

  const handleSave = useCallback(() => {
    setBackendUrl(draft);
  }, [draft]);

  const handleDefault = useCallback(() => {
    setBackendUrl('');
  }, []);

  const dotClass = `backend-settings__dot backend-settings__dot--${health}`;
  const title = healthTitle(health);

  return (
    <div class="backend-settings">
      <div class="backend-settings__summary">
        <span class={dotClass} title={title} aria-label={title}></span>
        <span class="backend-settings__label">Back-end: {backendLabel(url)}</span>
        <button class="backend-settings__toggle" onClick={toggle}>
          {expanded ? '▾' : '▸'}
        </button>
      </div>
      {expanded &&
        <div class="backend-settings__panel">
          <input
            class="backend-settings__input"
            value={draft}
            placeholder="same-origin (default)"
            onInput={(e: Event) => setDraft((e.target as HTMLInputElement).value)}
          />
          <button class="backend-settings__save" onClick={handleSave}>Save</button>
          <button class="backend-settings__default" onClick={handleDefault}>Use default</button>
        </div>
      }
    </div>
  );
}
