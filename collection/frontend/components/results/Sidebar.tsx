/**
 * Sidebar.tsx — Crossing / candidate detail overlay.
 *
 * Renders the sidebar for both a confirmed crossing (edit, delete, reorder, view
 * frames) and a candidate (rep frame + box overlay, promote, dismiss, view frames).
 * All mutations are delegated to the passed-in async callbacks — this component
 * never calls api directly and never dispatches events (FR13/SC5).
 *
 * @module components/results/Sidebar
 */

import { useState, useEffect, useRef, useCallback } from 'preact/hooks';
import type { SidebarProps, Result, CandidateResult } from '../../types';
import { setRosterOptions } from './roster';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Amber colour used for candidate repBox overlay */
const CANDIDATE_BOX_COLOR = '#f59e0b';

// ---------------------------------------------------------------------------
// Sub-components / helpers
// ---------------------------------------------------------------------------

interface RepBoxCanvasProps {
  imgRef: { current: HTMLImageElement | null };
  repBox: [number, number, number, number] | null;
}

function RepBoxCanvas({ imgRef, repBox }: RepBoxCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || !repBox || repBox.length !== 4) return;
    const [x1, y1, x2, y2] = repBox;
    const scaleX = img.clientWidth  / (img.naturalWidth  || img.clientWidth);
    const scaleY = img.clientHeight / (img.naturalHeight || img.clientHeight);
    canvas.width  = img.clientWidth;
    canvas.height = img.clientHeight;
    canvas.style.width  = `${img.clientWidth}px`;
    canvas.style.height = `${img.clientHeight}px`;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = CANDIDATE_BOX_COLOR;
    ctx.lineWidth   = 2;
    ctx.strokeRect(
      x1 * scaleX,
      y1 * scaleY,
      (x2 - x1) * scaleX,
      (y2 - y1) * scaleY
    );
  }, [imgRef, repBox]);

  useEffect(() => {
    const img = imgRef.current;
    if (!img) return;
    // Draw once loaded.
    if (img.complete && img.naturalWidth > 0) {
      draw();
    } else {
      img.addEventListener('load', draw);
    }
    // Redraw on resize.
    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== 'undefined') {
      ro = new ResizeObserver(draw);
      ro.observe(img);
    }
    return () => {
      img.removeEventListener('load', draw);
      if (ro) ro.disconnect();
    };
  }, [imgRef, draw]);

  return <canvas ref={canvasRef} class="frame-canvas-overlay" />;
}

// ---------------------------------------------------------------------------
// Crossing-mode sidebar
// ---------------------------------------------------------------------------

interface CrossingSidebarProps {
  item: object;
  runLabel: string;
  orderedCrossingIds: string[];
  onClose: () => void;
  onEdit: (crossingId: string, fields: object) => Promise<void>;
  onDelete: (crossingId: string) => Promise<void>;
  onReorder: (crossingId: string, neighbours: { earlierId: string | null; laterId: string | null }) => Promise<void>;
  onOpenBrowser: (anchorTs: string) => void;
}

function CrossingSidebar({ item, runLabel, orderedCrossingIds, onClose, onEdit, onDelete, onReorder, onOpenBrowser }: CrossingSidebarProps) {
  const result = item as Result;

  // Prefill number input — numberText carries "—" for unidentified.
  const initialNumber = (result.numberText && result.numberText !== '—')
    ? result.numberText
    : (result.raceNumber != null ? String(result.raceNumber) : '');

  const [numberValue, setNumberValue] = useState(initialNumber);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError(null);
    try {
      await onEdit(result.crossingId, { number: numberValue.trim() });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  }, [onEdit, result.crossingId, numberValue]);

  const handleDelete = useCallback(async () => {
    if (!confirm('Delete this crossing? This action can be undone by the next edit.')) return;
    setDeleting(true);
    setError(null);
    try {
      await onDelete(result.crossingId);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed');
      setDeleting(false);
    }
  }, [onDelete, result.crossingId, onClose]);

  const handleViewFrames = useCallback(() => {
    const anchorTs = result.time instanceof Date
      ? result.time.toISOString()
      : String(result.time);
    onOpenBrowser(anchorTs);
  }, [onOpenBrowser, result.time]);

  // ── Neighbour-based reorder (parity with legacy sidebar.js _buildMoveButtons) ──
  // Timeline displays newest-first (DESC by orderKey); order-of-record is ASC.
  // "Move earlier" ⇒ the card *below* (idx+1) becomes our laterId, and the one
  // below that (idx+2) our earlierId. "Move later" is the mirror (idx-1 / idx-2).
  const [reordering, setReordering] = useState(false);
  const ids = orderedCrossingIds || [];
  const idx = ids.indexOf(result.crossingId);
  const canMoveEarlier = idx >= 0 && idx < ids.length - 1; // a card exists below
  const canMoveLater   = idx > 0;                          // a card exists above

  const handleMove = useCallback(async (direction: 'earlier' | 'later') => {
    const i = ids.indexOf(result.crossingId);
    if (i < 0) return;
    let neighbours: { earlierId: string | null; laterId: string | null };
    if (direction === 'earlier') {
      if (i >= ids.length - 1) return;
      neighbours = { earlierId: ids[i + 2] ?? null, laterId: ids[i + 1] };
    } else {
      if (i <= 0) return;
      neighbours = { earlierId: ids[i - 1], laterId: ids[i - 2] ?? null };
    }
    setReordering(true);
    setError(null);
    try {
      await onReorder(result.crossingId, neighbours);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reorder failed');
    } finally {
      setReordering(false);
    }
  }, [onReorder, ids, result.crossingId]);

  // Display helpers
  const displayName = (result.matched && result.name) ? result.name : 'Unknown rider';
  // result.time is Date per the frozen Result type; the instanceof guard is defensive.
  const displayTime = _formatTimeOfDay(result.time instanceof Date ? result.time : new Date(String(result.time)));

  return (
    <>
      <img
        src={result.annotatedUrl}
        alt={'Annotated frame for crossing ' + result.crossingId}
        class="sidebar__image"
      />

      <div class="sidebar__details">
        <p class="sidebar__number">{result.numberText ? '#' + result.numberText : '#' + result.raceNumber}</p>
        <p class="sidebar__name">{displayName}</p>
        {(result.matched && result.category && result.category !== 'Unknown')
          ? <p class="sidebar__category">{result.category}</p>
          : null}
        <p class="sidebar__time">{displayTime}</p>
      </div>

      <div class="sidebar__actions">
        <div class="sidebar__action-row">
          <input
            type="text"
            class="sidebar__number-input"
            list="roster-numbers"
            placeholder="Race number"
            value={numberValue}
            onInput={(e: Event) => setNumberValue((e.target as HTMLInputElement).value)}
          />
          <button
            type="button"
            class="sidebar__btn sidebar__btn--primary"
            disabled={saving}
            onClick={handleSave}
          >Save number</button>
        </div>

        <div class="sidebar__action-row">
          <button
            type="button"
            class="sidebar__btn"
            disabled={reordering || !canMoveEarlier}
            onClick={() => handleMove('earlier')}
          >Move earlier</button>
          <button
            type="button"
            class="sidebar__btn"
            disabled={reordering || !canMoveLater}
            onClick={() => handleMove('later')}
          >Move later</button>
        </div>

        <div class="sidebar__action-row">
          <button
            type="button"
            class="sidebar__btn sidebar__btn--danger"
            disabled={deleting}
            onClick={handleDelete}
          >Delete</button>
          <button
            type="button"
            class="sidebar__btn"
            onClick={handleViewFrames}
          >View frames</button>
        </div>

        {error ? <p class="sidebar__error" style="color:#dc2626;font-size:0.8rem;margin:0.25rem 0 0;">{error}</p> : null}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Candidate-mode sidebar
// ---------------------------------------------------------------------------

interface CandidateSidebarProps {
  item: object;
  runLabel: string;
  onClose: () => void;
  onPromote: (candidateId: string, payload: object) => Promise<void>;
  onDismiss: (candidateId: string) => Promise<void>;
  onOpenBrowser: (anchorTs: string) => void;
}

function CandidateSidebar({ item, runLabel, onClose, onPromote, onDismiss, onOpenBrowser }: CandidateSidebarProps) {
  const result = item as CandidateResult;

  const [numberValue, setNumberValue] = useState(result.hintNumber ? String(result.hintNumber) : '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const imgRef = useRef<HTMLImageElement | null>(null);

  const handlePromote = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await onPromote(result.candidateId, { action: 'promote', number: numberValue.trim() });
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Promote failed');
      setBusy(false);
    }
  }, [onPromote, result.candidateId, numberValue, onClose]);

  const handleDismiss = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await onDismiss(result.candidateId);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Dismiss failed');
      setBusy(false);
    }
  }, [onDismiss, result.candidateId, onClose]);

  const handleViewFrames = useCallback(() => {
    let anchorTs: string | null = null;
    if (result.time instanceof Date) {
      anchorTs = result.time.toISOString();
    } else if (result.time) {
      anchorTs = String(result.time);
    }
    if (anchorTs) onOpenBrowser(anchorTs);
  }, [onOpenBrowser, result.time]);

  // Time display
  const timeText = (() => {
    if (result.time instanceof Date) {
      return `First seen: ${_formatTimeOfDay(result.time)}`;
    } else if (result.time) {
      // result.time is Date per CandidateResult type; String() coercion is a safe fallback.
      const d = new Date(String(result.time));
      return `First seen: ${isNaN(d.getTime()) ? String(result.time) : _formatTimeOfDay(d)}`;
    }
    return '';
  })();

  const confPct = result.hintConf != null
    ? ` (${Math.round(result.hintConf * 100)}% conf.)`
    : '';

  return (
    <>
      <div class="frame-canvas-wrapper">
        <img
          ref={imgRef}
          src={result.imageUrl ?? ''}
          alt={'Representative frame for candidate ' + result.candidateId}
          class="sidebar__image"
        />
        <RepBoxCanvas imgRef={imgRef} repBox={result.repBox ?? null} />
      </div>

      <div class="sidebar__details">
        <p class="sidebar__number">? Candidate crossing</p>
        {timeText ? <p class="sidebar__time">{timeText}</p> : null}
        {result.frameCount != null
          ? <p class="sidebar__meta">{result.frameCount} frame{result.frameCount !== 1 ? 's' : ''}</p>
          : null}
        {result.hintNumber
          ? <p class="sidebar__meta">Pipeline saw: #{result.hintNumber}{confPct}</p>
          : null}
      </div>

      <div class="sidebar__actions">
        <div class="sidebar__action-row">
          <input
            type="text"
            class="sidebar__number-input"
            list="roster-numbers"
            placeholder="Race number (blank = unidentified)"
            value={numberValue}
            onInput={(e: Event) => setNumberValue((e.target as HTMLInputElement).value)}
          />
        </div>

        <div class="sidebar__action-row">
          <button
            type="button"
            class="sidebar__btn sidebar__btn--primary"
            disabled={busy}
            onClick={handlePromote}
          >Promote</button>
          <button
            type="button"
            class="sidebar__btn sidebar__btn--danger"
            disabled={busy}
            onClick={handleDismiss}
          >Dismiss</button>
          <button
            type="button"
            class="sidebar__btn"
            onClick={handleViewFrames}
          >View frames</button>
        </div>

        {error ? <p class="sidebar__error" style="color:#dc2626;font-size:0.8rem;margin:0.25rem 0 0;">{error}</p> : null}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Sidebar (public export)
// ---------------------------------------------------------------------------

/**
 * Crossing / candidate detail overlay.
 *
 * When open (item != null), renders the appropriate mode. On mount / item
 * change, populates the shared #roster-numbers datalist via setRosterOptions.
 */
export function Sidebar(props: SidebarProps) {
  const { item, runLabel, orderedCrossingIds, onClose, onEdit, onDelete, onReorder, onPromote, onDismiss, onOpenBrowser } = props;

  // Populate the shared datalist whenever the overlay opens or runLabel changes.
  useEffect(() => {
    if (item && runLabel) {
      setRosterOptions(runLabel);
    }
  }, [item, runLabel]);

  if (!item) return null;

  const isCandidate = (item as Result | CandidateResult).isCandidate === true;

  return (
    <div class="sidebar__overlay" role="dialog" aria-modal="true">
      <div class="sidebar__header">
        <button
          type="button"
          class="sidebar__close"
          aria-label="Close sidebar"
          onClick={onClose}
        >×</button>
      </div>
      <div class="sidebar__content">
        {isCandidate
          ? <CandidateSidebar
              item={item}
              runLabel={runLabel}
              onClose={onClose}
              onPromote={onPromote}
              onDismiss={onDismiss}
              onOpenBrowser={onOpenBrowser}
            />
          : <CrossingSidebar
              item={item}
              runLabel={runLabel}
              orderedCrossingIds={orderedCrossingIds}
              onClose={onClose}
              onEdit={onEdit}
              onDelete={onDelete}
              onReorder={onReorder}
              onOpenBrowser={onOpenBrowser}
            />
        }
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Utilities (local — not exported)
// ---------------------------------------------------------------------------

/**
 * Format a Date as HH:MM:SS (local time).
 */
function _formatTimeOfDay(d: Date): string {
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return `${hh}:${mm}:${ss}`;
}
