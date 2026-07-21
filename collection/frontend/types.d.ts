/**
 * types.d.ts — Single frozen type surface for the FE Modernization spec.
 *
 * Declares all data shapes (FROZEN-1), state/action shapes (FROZEN-4),
 * and component prop types (FROZEN-5). Referenced by every component via
 * JSDoc: @param {import('../../types').XxxProps} props
 * (extension-less; tsc resolves to this .d.ts under moduleResolution:bundler)
 *
 * DO NOT edit without updating all components and Wave B tasks. These are
 * the frozen contracts that every parallel task codes against.
 */

// ---------------------------------------------------------------------------
// FROZEN-1 · Data object shapes (mirrored from results/data.js)
// ---------------------------------------------------------------------------

/** Display-ready crossing from GET /results */
export interface Result {
  time: Date;
  raceNumber: number;
  name: string | null;
  category: string;
  matched: boolean;
  crossingId: string;
  annotatedUrl: string;
  source: "auto" | "manual";
  edited: boolean;
  orderKey: number;
  orderOverridden: boolean;
  isCandidate: false;
  numberText: string;
}

/** Pseudo-Result built from GET /candidates */
export interface CandidateResult {
  isCandidate: true;
  candidateId: string;
  run: string;
  time: Date;
  lastSeen: Date;
  frameCount: number;
  hintNumber: string | null;
  hintConf: number;
  imageUrl: string;
  repBox: [number, number, number, number];
  orderKey: number;
  numberText: string;
  category: "Unknown";
}

/** Crossings within gapSeconds of each other; one separator per pack */
export interface Pack {
  startTime: Date;
  results: Array<Result | CandidateResult>;
}

/** One timeline lane (column) produced by computeLanes */
export interface Lane {
  category: string;
  index: number;
}

// ---------------------------------------------------------------------------
// FROZEN-4 · State & Action shapes — ResultsApp (design §8)
// ---------------------------------------------------------------------------

/** Full results-page state managed by useReducer in ResultsApp */
export interface State {
  runs: string[];
  selectedRun: string | null;

  /** Raw transform outputs from data.js — retained across poll cycles */
  crossings: Result[];
  candidates: CandidateResult[];
  /** String key over raw /results+/candidates JSON; identical hash → no new state object */
  lastPayloadHash: string;

  /** Derived view model — recomputed in-reducer on POLL_RESULTS and TOGGLE_CANDIDATES */
  packs: Pack[];
  lanes: Lane[];

  candidatesVisible: boolean;
  selectedId: string | null;

  sidebar: {
    open: boolean;
    item: object | null;
    /** Step index into surrounding frames */
    frameOffset: number;
  };

  browser: {
    open: boolean;
    /** ISO timestamp to centre frame browser on */
    anchorTs: string | null;
  };

  statusPayload: object | null;
  pollError: string | null;
}

/** Discriminated union of all 12 ResultsApp action shapes */
export type Action =
  | { type: "SET_RUNS"; runs: string[] }
  | { type: "SELECT_RUN"; runLabel: string }
  | { type: "POLL_RESULTS"; crossings: Result[]; candidates: CandidateResult[]; hash: string }
  | { type: "POLL_STATUS"; status: object }
  | { type: "TOGGLE_CANDIDATES" }
  | { type: "SELECT_ITEM"; item: object }
  | { type: "OPEN_SIDEBAR"; item: object; frameOffset?: number }
  | { type: "CLOSE_SIDEBAR" }
  | { type: "STEP_FRAME"; delta: number }
  | { type: "OPEN_BROWSER"; anchorTs: string }
  | { type: "CLOSE_BROWSER" }
  | { type: "POLL_ERROR"; error: string };

// ---------------------------------------------------------------------------
// FROZEN-5 · Component prop signatures (design §9)
// ---------------------------------------------------------------------------

// ── Results components ──

/** ResultsApp takes no props — self-contained via COLLECTION_CONFIG */
export interface ResultsAppProps {}

export interface RunSelectorProps {
  runs: string[];
  selected: string | null;
  onChange: (runLabel: string) => void;
}

export interface StatusBarProps {
  status: object | null;
}

export interface TimelineProps {
  packs: Pack[];
  /** From computeLanes; sets grid --lane-count */
  lanes: Lane[];
  candidatesVisible: boolean;
  selectedId: string | null;
  onSelect: (item: object) => void;
}

export interface PackProps {
  /** { startTime, results } — one gap group */
  pack: Pack;
  /** To resolve each result's grid column */
  lanes: Lane[];
  selectedId: string | null;
  onSelect: (item: object) => void;
}

export interface CardProps {
  crossing: object;
  /** 1-based grid column (resolved by Pack from lanes) */
  column: number;
  selected: boolean;
  onClick: () => void;
}

export interface CandidateCardProps {
  candidate: object;
  /** 1-based grid column (resolved by Pack from lanes) */
  column: number;
  selected: boolean;
  onClick: () => void;
}

export interface GapSeparatorProps {
  /** formatGapLabel(pack.startTime) — a timestamp label (hh:mm) */
  label: string;
}

export interface SidebarProps {
  item: object | null;
  frameOffset: number;
  runLabel: string;
  onClose: () => void;
  onStepFrame: (delta: number) => void;
  onEdit: (crossingId: string, fields: object) => Promise<void>;
  onDelete: (crossingId: string) => Promise<void>;
  onPromote: (candidateId: string, payload: object) => Promise<void>;
  onDismiss: (candidateId: string) => Promise<void>;
  onOpenBrowser: (anchorTs: string) => void;
}

export interface FrameBrowserProps {
  runLabel: string;
  anchorTs: string | null;
  onClose: () => void;
  onCreateCrossing: (payload: object) => Promise<void>;
}

// ── Capture components ──

/** CaptureApp takes no props — self-contained via COLLECTION_CONFIG */
export interface CaptureAppProps {}

export interface SourceSelectorProps {
  /** 'camera' | 'video' */
  value: string;
  onChange: (src: string) => void;
}

/** Manages its own stream ref internally */
export interface CameraPreviewProps {
  active: boolean;
}

export interface CaptureControlsProps {
  active: boolean;
  onStart: () => void;
  onStop: () => void;
  inflight: number;
  label: string;
  onLabel: (label: string) => void;
}

export interface RosterUploadProps {
  onUpload: (file: File) => Promise<void>;
  status: string | null;
}
