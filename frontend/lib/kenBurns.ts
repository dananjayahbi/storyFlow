import type {
  KenBurnsAnimation,
  KenBurnsConfig,
  KenBurnsPanMode,
  KenBurnsPoint,
} from '@/lib/types';

/**
 * Default settings used when a segment first switches to manual Ken Burns.
 * Values mirror the backend defaults so an untouched config still renders a
 * pleasant move (`pan` from 30% to 70% across the frame).
 */
export const DEFAULT_KEN_BURNS_CONFIG: KenBurnsConfig = {
  enabled: false,
  animation: 'pan',
  pan_mode: 'points',
  start: { x: 0.3, y: 0.5 },
  end: { x: 0.7, y: 0.5 },
  focal_point: { x: 0.5, y: 0.5 },
  area: null,
  zoom: 1.25,
};

export const KEN_BURNS_ANIMATION_OPTIONS: Array<{
  value: KenBurnsAnimation;
  label: string;
  description: string;
}> = [
  {
    value: 'pan',
    label: 'Pan',
    description: 'Travel from a start point to an end point (or across a drawn area).',
  },
  {
    value: 'zoom_in',
    label: 'Zoom in',
    description: 'Push in towards a focal point.',
  },
  {
    value: 'zoom_out',
    label: 'Zoom out',
    description: 'Start close on a focal point and pull back.',
  },
  {
    value: 'pan_zoom',
    label: 'Pan + zoom',
    description: 'Travel along the path while pushing in.',
  },
];

export const KEN_BURNS_PAN_MODE_OPTIONS: Array<{
  value: KenBurnsPanMode;
  label: string;
}> = [
  { value: 'points', label: 'Start / end points' },
  { value: 'area', label: 'Draw area' },
];

const ANIMATIONS = new Set<KenBurnsAnimation>(
  KEN_BURNS_ANIMATION_OPTIONS.map((option) => option.value),
);

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function point(value: unknown, fallback: KenBurnsPoint): KenBurnsPoint {
  if (!value || typeof value !== 'object') return fallback;
  const candidate = value as { x?: unknown; y?: unknown };
  const x = Number(candidate.x);
  const y = Number(candidate.y);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return fallback;
  return { x: clamp01(x), y: clamp01(y) };
}

/**
 * Merge a stored (possibly partial/legacy) config with the defaults.
 * Invalid animation names and out-of-range points fall back safely so the
 * editor never crashes on data written by an older client.
 */
export function resolveKenBurnsConfig(
  config?: Partial<KenBurnsConfig> | null,
): KenBurnsConfig {
  if (!config || typeof config !== 'object') {
    return { ...DEFAULT_KEN_BURNS_CONFIG };
  }
  const animation = ANIMATIONS.has(config.animation as KenBurnsAnimation)
    ? (config.animation as KenBurnsAnimation)
    : DEFAULT_KEN_BURNS_CONFIG.animation;
  const panMode =
    config.pan_mode === 'area' ? 'area' : DEFAULT_KEN_BURNS_CONFIG.pan_mode;
  const zoomValue = Number(config.zoom);
  const zoom = Number.isFinite(zoomValue)
    ? Math.max(1, Math.min(4, zoomValue))
    : DEFAULT_KEN_BURNS_CONFIG.zoom;
  const area = config.area;
  return {
    enabled: Boolean(config.enabled),
    animation,
    pan_mode: panMode,
    start: point(config.start, DEFAULT_KEN_BURNS_CONFIG.start),
    end: point(config.end, DEFAULT_KEN_BURNS_CONFIG.end),
    focal_point: point(
      config.focal_point,
      DEFAULT_KEN_BURNS_CONFIG.focal_point,
    ),
    area:
      area &&
      Number.isFinite(Number(area.x)) &&
      Number.isFinite(Number(area.y)) &&
      Number(area.w) > 0 &&
      Number(area.h) > 0
        ? {
            x: clamp01(Number(area.x)),
            y: clamp01(Number(area.y)),
            w: clamp01(Number(area.w)),
            h: clamp01(Number(area.h)),
          }
        : null,
    zoom,
  };
}

export function animationUsesPan(animation: KenBurnsAnimation): boolean {
  return animation === 'pan' || animation === 'pan_zoom';
}

export function animationUsesZoom(animation: KenBurnsAnimation): boolean {
  return animation !== 'pan';
}

export function animationLabel(animation: KenBurnsAnimation): string {
  return (
    KEN_BURNS_ANIMATION_OPTIONS.find((option) => option.value === animation)
      ?.label ?? 'Pan'
  );
}

/** Short summary shown under the image so the block explains its motion. */
export function describeKenBurnsConfig(config: KenBurnsConfig): string {
  if (!config.enabled) {
    return 'Automatic Ken Burns — the planner picks a random pan or zoom.';
  }
  if (config.animation === 'pan') {
    return config.pan_mode === 'area'
      ? 'Manual pan — sweeps across the drawn area.'
      : 'Manual pan — travels from the start point to the end point.';
  }
  if (config.animation === 'zoom_in') {
    return 'Manual zoom in — holds the focal point while pushing in.';
  }
  if (config.animation === 'zoom_out') {
    return 'Manual zoom out — starts close and pulls back from the focal point.';
  }
  return 'Manual pan + zoom — travels along the path while pushing in.';
}
