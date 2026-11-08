import type { ImageFocusArea, KenBurnsConfig } from '@/lib/types';
import { resolveKenBurnsConfig } from '@/lib/kenBurns';

/**
 * Browser-side mirror of `backend/core_engine/ken_burns.py`.
 *
 * The editor preview must show the same camera move the renderer will use:
 * the same prepared frame, the same start/end crops, the same smoothstep
 * easing and the same per-frame clamping.  The functions below are a direct
 * port of the manual and automatic planners, expressed in the prepared
 * frame's pixel space so rounding and zoom headroom match the renderer too.
 */

/** Size of the cover-cropped / resized frame the renderer works on. */
export interface PreparedFrame {
  width: number;
  height: number;
}

/** A sampled crop window normalised to the prepared frame (0..1). */
export interface KenBurnsPreviewFrame {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** A motion plan consumed by `sampleKenBurnsPreview`. */
export interface KenBurnsPreviewPlan {
  sourceWidth: number;
  sourceHeight: number;
  duration: number;
  motion: string;
  source: 'manual' | 'automatic';
  subject: ImageFocusArea | null;
  startCrop: [number, number];
  endCrop: [number, number];
  startCentre: [number, number];
  endCentre: [number, number];
  startScale: number;
  endScale: number;
}

export interface KenBurnsPreviewOptions {
  config?: KenBurnsConfig | null;
  /** Block duration in seconds (the TTS audio length when known). */
  duration: number;
  segmentIndex: number;
  prepared: PreparedFrame;
  outputWidth: number;
  outputHeight: number;
  zoomIntensity: number;
  focusArea?: ImageFocusArea | null;
  focusAreas?: ImageFocusArea[] | null;
}

// ── Renderer constants (keep in sync with core_engine/ken_burns.py) ──

const DIRECTIONS: ReadonlyArray<readonly [string, string]> = [
  ['top_left', 'center'],
  ['bottom_right', 'top_left'],
  ['top_right', 'bottom_left'],
  ['bottom_left', 'top_right'],
  ['center', 'top_left'],
  ['center', 'bottom_right'],
  ['top_left', 'bottom_right'],
];

const POSITION_UNIT: Record<string, readonly [number, number]> = {
  top_left: [0, 0],
  top_right: [1, 0],
  bottom_left: [0, 1],
  bottom_right: [1, 1],
  center: [0.5, 0.5],
};

const MOTION_PRESETS = [
  'pan',
  'zoom_in',
  'pan',
  'zoom_out',
  'pan_zoom',
  'pan',
  'zoom_in',
] as const;

const MANUAL_ANIMATIONS: ReadonlyArray<KenBurnsConfig['animation']> = [
  'pan',
  'zoom_in',
  'zoom_out',
  'pan_zoom',
];

const PAN_SPEED_TARGET = 0.045;
const ZOOM_RATE_TARGET = 0.03;
const MIN_PAN_ROOM = 0.018;
const MIN_PAN_TRAVEL = 0.04;
const MIN_ZOOM_SPAN = 0.04;
const MIN_PAN_SPEED = 0.012;
const MIN_ZOOM_RATE = 0.012;
const MAX_REQUIRED_MOTION = 0.1;
const FOCUS_OVERFLOW_RATIO = 0.1;
const ZOOM_IN_RANGE = 0.12;
const ZOOM_OUT_RANGE = 0.15;
const PAN_ZOOM_FACTOR = 0.6;
const MANUAL_ZOOM_MIN = 1;
const MANUAL_ZOOM_MAX = 4;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function positive(value: number, fallback: number): number {
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

/**
 * Reproduce `load_and_prepare_image()` sizing: cover-crop the source to the
 * output aspect ratio, upscale to at least `output × zoomIntensity`, then
 * downscale oversized frames to that minimum.
 */
export function computePreparedFrame(
  naturalWidth: number,
  naturalHeight: number,
  outputWidth: number,
  outputHeight: number,
  zoomIntensity: number,
): PreparedFrame {
  const outW = Math.max(1, Math.round(positive(outputWidth, 1920)));
  const outH = Math.max(1, Math.round(positive(outputHeight, 1080)));
  const zoom = positive(zoomIntensity, 1.3);

  let sourceW = Math.max(1, Math.round(positive(naturalWidth, outW)));
  let sourceH = Math.max(1, Math.round(positive(naturalHeight, outH)));

  const targetAspect = outW / outH;
  const sourceAspect = sourceW / sourceH;
  let frameW: number;
  let frameH: number;
  if (sourceAspect > targetAspect) {
    frameH = sourceH;
    frameW = Math.max(1, Math.round(sourceH * targetAspect));
  } else {
    frameW = sourceW;
    frameH = Math.max(1, Math.round(sourceW / targetAspect));
  }

  const minW = Math.max(1, Math.trunc(outW * zoom));
  const minH = Math.max(1, Math.trunc(outH * zoom));

  if (frameW < minW || frameH < minH) {
    const scale = Math.max(minW / frameW, minH / frameH);
    frameW = Math.max(minW, Math.round(frameW * scale));
    frameH = Math.max(minH, Math.round(frameH * scale));
    sourceW = frameW;
    sourceH = frameH;
  }

  if (frameW > minW * 1.5 || frameH > minH * 1.5) {
    frameW = minW;
    frameH = minH;
  }

  return { width: frameW, height: frameH };
}

/** One valid subject rectangle (the first entry wins, like the renderer). */
export function normalisePreviewFocusAreas(
  input: ImageFocusArea | ImageFocusArea[] | null | undefined,
): ImageFocusArea[] {
  if (!input) return [];
  const items = Array.isArray(input) ? input : [input];
  const areas: ImageFocusArea[] = [];
  for (const item of items) {
    if (!item || typeof item !== 'object') continue;
    const x = Number(item.x);
    const y = Number(item.y);
    const w = Number(item.w);
    const h = Number(item.h);
    if (![x, y, w, h].every((value) => Number.isFinite(value))) continue;
    if (![x, y, w, h].every((value) => value >= 0 && value <= 1)) continue;
    const clippedW = Math.min(w, 1 - x);
    const clippedH = Math.min(h, 1 - y);
    if (clippedW <= 0 || clippedH <= 0) continue;
    areas.push({ x, y, w: clippedW, h: clippedH });
    break;
  }
  return areas;
}

/** Allowed crop top-left range that keeps the subject sufficiently visible. */
function focusAreaBounds(
  area: ImageFocusArea,
  sourceWidth: number,
  sourceHeight: number,
  cropWidth: number,
  cropHeight: number,
  overflowRatio = 0,
): [number, number, number, number] {
  let fx = Math.round(area.x * sourceWidth);
  let fy = Math.round(area.y * sourceHeight);
  let fw = Math.max(1, Math.round(area.w * sourceWidth));
  let fh = Math.max(1, Math.round(area.h * sourceHeight));

  fx = clamp(fx, 0, sourceWidth - 1);
  fy = clamp(fy, 0, sourceHeight - 1);
  fw = Math.max(1, Math.min(fw, sourceWidth - fx));
  fh = Math.max(1, Math.min(fh, sourceHeight - fy));

  const marginX = Math.round(fw * Math.max(0, overflowRatio));
  const marginY = Math.round(fh * Math.max(0, overflowRatio));

  let minX = Math.max(0, fx + fw - cropWidth - marginX);
  let maxX = Math.min(sourceWidth - cropWidth, fx + marginX);
  let minY = Math.max(0, fy + fh - cropHeight - marginY);
  let maxY = Math.min(sourceHeight - cropHeight, fy + marginY);

  if (minX > maxX) {
    const centre = fx + Math.floor(fw / 2) - Math.floor(cropWidth / 2);
    minX = maxX = Math.max(0, Math.min(centre, sourceWidth - cropWidth));
  }
  if (minY > maxY) {
    const centre = fy + Math.floor(fh / 2) - Math.floor(cropHeight / 2);
    minY = maxY = Math.max(0, Math.min(centre, sourceHeight - cropHeight));
  }

  return [minX, maxX, minY, maxY];
}

function focusBoundsForCrop(
  subject: ImageFocusArea | null,
  sourceWidth: number,
  sourceHeight: number,
  cropWidth: number,
  cropHeight: number,
  overflowRatio = 0,
): [number, number, number, number] {
  if (subject) {
    return focusAreaBounds(
      subject,
      sourceWidth,
      sourceHeight,
      cropWidth,
      cropHeight,
      overflowRatio,
    );
  }
  return [
    0,
    Math.max(0, sourceWidth - cropWidth),
    0,
    Math.max(0, sourceHeight - cropHeight),
  ];
}

function cropForScale(
  baseWidth: number,
  baseHeight: number,
  scale: number,
  sourceWidth: number,
  sourceHeight: number,
): [number, number] {
  return [
    Math.max(1, Math.min(sourceWidth, Math.round(baseWidth * scale))),
    Math.max(1, Math.min(sourceHeight, Math.round(baseHeight * scale))),
  ];
}

function baseCropDimensions(
  outputWidth: number,
  outputHeight: number,
  zoomIntensity: number,
): [number, number] {
  return [
    Math.max(1, Math.trunc(outputWidth / zoomIntensity)),
    Math.max(1, Math.trunc(outputHeight / zoomIntensity)),
  ];
}

function focusCropDimensions(
  outputWidth: number,
  outputHeight: number,
  zoomIntensity: number,
  subject: ImageFocusArea | null,
  sourceWidth: number,
  sourceHeight: number,
): [number, number] {
  const [baseW, baseH] = baseCropDimensions(
    outputWidth,
    outputHeight,
    zoomIntensity,
  );
  if (!subject) return [baseW, baseH];

  const padding = 1.1;
  const neededScale =
    Math.max(
      (subject.w * sourceWidth) / baseW,
      (subject.h * sourceHeight) / baseH,
      1,
    ) * padding;
  const maxScale = Math.min(sourceWidth / baseW, sourceHeight / baseH);
  const scale = Math.min(neededScale, maxScale);

  return [
    Math.max(1, Math.min(sourceWidth, Math.round(baseW * scale))),
    Math.max(1, Math.min(sourceHeight, Math.round(baseH * scale))),
  ];
}

function directionVector(segmentIndex: number): [number, number] {
  const pair = DIRECTIONS[
    ((segmentIndex % DIRECTIONS.length) + DIRECTIONS.length) %
      DIRECTIONS.length
  ];
  const start = POSITION_UNIT[pair[0]] ?? [0.5, 0.5];
  const end = POSITION_UNIT[pair[1]] ?? [0.5, 0.5];
  const sign = (value: number) => (value > 0.001 ? 1 : value < -0.001 ? -1 : 0);
  return [sign(end[0] - start[0]), sign(end[1] - start[1])];
}

type MotionFlags = {
  pan: boolean;
  panZoom: boolean;
  zoomIn: boolean;
  zoomOut: boolean;
};

function selectMotion(preferred: string, flags: MotionFlags): string {
  if (preferred === 'pan_zoom') {
    if (flags.panZoom && (flags.zoomIn || flags.zoomOut)) return 'pan_zoom';
    if (flags.pan) return 'pan';
    if (flags.zoomIn) return 'zoom_in';
    if (flags.zoomOut) return 'zoom_out';
    return 'pan';
  }
  if (preferred === 'zoom_in') {
    if (flags.zoomIn) return 'zoom_in';
    if (flags.pan) return 'pan';
    if (flags.zoomOut) return 'zoom_out';
    return 'pan';
  }
  if (preferred === 'zoom_out') {
    if (flags.zoomOut) return 'zoom_out';
    if (flags.pan) return 'pan';
    if (flags.zoomIn) return 'zoom_in';
    return 'pan';
  }
  if (flags.pan) return 'pan';
  if (flags.zoomIn) return 'zoom_in';
  if (flags.zoomOut) return 'zoom_out';
  return 'pan';
}

function centreRange(
  bounds: [number, number, number, number],
  cropWidth: number,
  cropHeight: number,
): [number, number, number, number] {
  return [
    bounds[0] + cropWidth / 2,
    bounds[1] + cropWidth / 2,
    bounds[2] + cropHeight / 2,
    bounds[3] + cropHeight / 2,
  ];
}

/** Port of `plan_ken_burns_motion()` for a block without manual override. */
function planAutomatic(options: KenBurnsPreviewOptions): KenBurnsPreviewPlan {
  const { prepared, outputWidth, outputHeight, duration, segmentIndex } =
    options;
  const zoomIntensity = positive(options.zoomIntensity, 1.3);
  const sourceWidth = prepared.width;
  const sourceHeight = prepared.height;
  const subject =
    normalisePreviewFocusAreas(options.focusAreas)[0] ??
    normalisePreviewFocusAreas(options.focusArea)[0] ??
    null;

  const [baseW, baseH] = baseCropDimensions(
    outputWidth,
    outputHeight,
    zoomIntensity,
  );
  const [focusW, focusH] = focusCropDimensions(
    outputWidth,
    outputHeight,
    zoomIntensity,
    subject,
    sourceWidth,
    sourceHeight,
  );

  const maxScale = Math.min(sourceWidth / baseW, sourceHeight / baseH);
  let minScale = Math.max(focusW / baseW, focusH / baseH, 1);
  minScale = Math.max(0.05, Math.min(minScale, maxScale));

  const effectiveDuration = Math.max(0, Number(duration) || 0);
  const requiredPan = Math.max(
    MIN_PAN_TRAVEL,
    Math.min(MAX_REQUIRED_MOTION, MIN_PAN_SPEED * effectiveDuration),
  );
  const requiredZoom = Math.max(
    MIN_ZOOM_SPAN,
    Math.min(MAX_REQUIRED_MOTION, MIN_ZOOM_RATE * effectiveDuration),
  );

  const [panCropW, panCropH] = cropForScale(
    baseW,
    baseH,
    minScale,
    sourceWidth,
    sourceHeight,
  );
  const panBounds = focusBoundsForCrop(
    subject,
    sourceWidth,
    sourceHeight,
    panCropW,
    panCropH,
    FOCUS_OVERFLOW_RATIO,
  );
  const roomXPx = Math.max(0, panBounds[1] - panBounds[0]);
  const roomYPx = Math.max(0, panBounds[3] - panBounds[2]);
  const panRoom = Math.max(
    panCropW ? roomXPx / panCropW : 0,
    panCropH ? roomYPx / panCropH : 0,
  );

  const zoomSpanTarget = Math.max(
    MIN_ZOOM_SPAN,
    ZOOM_RATE_TARGET * effectiveDuration,
  );
  const overflowMinScale = Math.max(
    0.05,
    minScale * (1 - FOCUS_OVERFLOW_RATIO),
  );
  const headroomUp = Math.max(0, maxScale - minScale);
  const headroomDown = Math.max(0, minScale - overflowMinScale);

  const zoomShape = (direction: string, span: number) => {
    const upPart = Math.min(span, headroomUp);
    const downPart = Math.min(Math.max(0, span - upPart), headroomDown);
    const effect = upPart + downPart;
    if (direction === 'zoom_in') {
      return {
        start: minScale + upPart,
        end: minScale - downPart,
        effect,
      };
    }
    return {
      start: minScale - downPart,
      end: minScale + upPart,
      effect,
    };
  };

  const zoomIn = zoomShape('zoom_in', Math.min(ZOOM_IN_RANGE, zoomSpanTarget));
  const zoomOut = zoomShape(
    'zoom_out',
    Math.min(ZOOM_OUT_RANGE, zoomSpanTarget),
  );

  const [directionX, directionY] = directionVector(segmentIndex);
  const panFractionTarget =
    Math.max(PAN_SPEED_TARGET, MIN_PAN_SPEED) * effectiveDuration;

  const panEffect = (factor: number) => {
    const targetX = Math.abs(directionX) * panFractionTarget * factor;
    const targetY = Math.abs(directionY) * panFractionTarget * factor;
    const travelX = Math.min(panCropW ? roomXPx / panCropW : 0, targetX);
    const travelY = Math.min(panCropH ? roomYPx / panCropH : 0, targetY);
    return Math.max(travelX, travelY);
  };

  const panOk = panRoom >= MIN_PAN_ROOM && panEffect(1) >= requiredPan;
  const panZoomOk =
    panOk && panEffect(PAN_ZOOM_FACTOR) >= requiredPan * PAN_ZOOM_FACTOR;
  const zoomInOk = zoomIn.effect >= requiredZoom;
  const zoomOutOk = zoomOut.effect >= requiredZoom;

  const preferred =
    MOTION_PRESETS[
      ((segmentIndex % MOTION_PRESETS.length) + MOTION_PRESETS.length) %
        MOTION_PRESETS.length
    ];
  let motion = selectMotion(preferred, {
    pan: panOk,
    panZoom: panZoomOk,
    zoomIn: zoomInOk,
    zoomOut: zoomOutOk,
  });

  if (motion === 'pan' && !panOk) {
    const candidates: Array<[number, string]> = [
      [requiredPan ? panEffect(1) / requiredPan : 0, 'pan'],
      [requiredZoom ? zoomIn.effect / requiredZoom : 0, 'zoom_in'],
      [requiredZoom ? zoomOut.effect / requiredZoom : 0, 'zoom_out'],
    ];
    candidates.sort((a, b) => b[0] - a[0]);
    motion = candidates[0][1];
  }

  let startScale = minScale;
  let endScale = minScale;
  let panFactor = 0;
  if (motion === 'zoom_in') {
    startScale = zoomIn.start;
    endScale = zoomIn.end;
  } else if (motion === 'zoom_out') {
    startScale = zoomOut.start;
    endScale = zoomOut.end;
  } else if (motion === 'pan_zoom') {
    panFactor = PAN_ZOOM_FACTOR;
    const preferIn = zoomInOk && (!zoomOutOk || segmentIndex % 2 === 0);
    if (preferIn) {
      startScale = zoomIn.start;
      endScale = zoomIn.end;
    } else if (zoomOutOk) {
      startScale = zoomOut.start;
      endScale = zoomOut.end;
    } else {
      motion = 'pan';
      panFactor = 0;
    }
  }
  if (motion === 'pan') panFactor = 1;

  const startCrop = cropForScale(
    baseW,
    baseH,
    startScale,
    sourceWidth,
    sourceHeight,
  );
  const endCrop = cropForScale(
    baseW,
    baseH,
    endScale,
    sourceWidth,
    sourceHeight,
  );

  const referenceCropW = (startCrop[0] + endCrop[0]) / 2;
  const referenceCropH = (startCrop[1] + endCrop[1]) / 2;
  const targetX =
    Math.abs(directionX) *
    Math.max(PAN_SPEED_TARGET, MIN_PAN_SPEED) *
    effectiveDuration *
    referenceCropW *
    panFactor;
  const targetY =
    Math.abs(directionY) *
    Math.max(PAN_SPEED_TARGET, MIN_PAN_SPEED) *
    effectiveDuration *
    referenceCropH *
    panFactor;
  const travelX = Math.min(roomXPx, targetX);
  const travelY = Math.min(roomYPx, targetY);

  const startBounds = focusBoundsForCrop(
    subject,
    sourceWidth,
    sourceHeight,
    startCrop[0],
    startCrop[1],
    FOCUS_OVERFLOW_RATIO,
  );
  const endBounds = focusBoundsForCrop(
    subject,
    sourceWidth,
    sourceHeight,
    endCrop[0],
    endCrop[1],
    FOCUS_OVERFLOW_RATIO,
  );
  const startRange = centreRange(startBounds, startCrop[0], startCrop[1]);
  const endRange = centreRange(endBounds, endCrop[0], endCrop[1]);

  let startCx: number;
  let endCx: number;
  if (directionX > 0) {
    startCx = (startRange[0] + startRange[1]) / 2 - travelX / 2;
    endCx = (endRange[0] + endRange[1]) / 2 + travelX / 2;
  } else if (directionX < 0) {
    startCx = (startRange[0] + startRange[1]) / 2 + travelX / 2;
    endCx = (endRange[0] + endRange[1]) / 2 - travelX / 2;
  } else {
    startCx = (startRange[0] + startRange[1]) / 2;
    endCx = (endRange[0] + endRange[1]) / 2;
  }

  let startCy: number;
  let endCy: number;
  if (directionY > 0) {
    startCy = (startRange[2] + startRange[3]) / 2 - travelY / 2;
    endCy = (endRange[2] + endRange[3]) / 2 + travelY / 2;
  } else if (directionY < 0) {
    startCy = (startRange[2] + startRange[3]) / 2 + travelY / 2;
    endCy = (endRange[2] + endRange[3]) / 2 - travelY / 2;
  } else {
    startCy = (startRange[2] + startRange[3]) / 2;
    endCy = (endRange[2] + endRange[3]) / 2;
  }

  startCx = clamp(startCx, startRange[0], startRange[1]);
  endCx = clamp(endCx, endRange[0], endRange[1]);
  startCy = clamp(startCy, startRange[2], startRange[3]);
  endCy = clamp(endCy, endRange[2], endRange[3]);

  return {
    sourceWidth,
    sourceHeight,
    duration: effectiveDuration,
    motion: `automatic_${motion}`,
    source: 'automatic',
    subject,
    startCrop,
    endCrop,
    startCentre: [startCx, startCy],
    endCentre: [endCx, endCy],
    startScale,
    endScale,
  };
}

function manualCropDims(
  zoom: number,
  sourceWidth: number,
  sourceHeight: number,
): [number, number] {
  const safeZoom = Math.max(MANUAL_ZOOM_MIN, zoom);
  return [
    Math.max(1, Math.min(sourceWidth, Math.round(sourceWidth / safeZoom))),
    Math.max(1, Math.min(sourceHeight, Math.round(sourceHeight / safeZoom))),
  ];
}

function centreForPoint(
  point: { x: number; y: number },
  sourceWidth: number,
  sourceHeight: number,
  cropWidth: number,
  cropHeight: number,
): [number, number] {
  const halfW = cropWidth / 2;
  const halfH = cropHeight / 2;
  return [
    clamp(point.x * sourceWidth, halfW, sourceWidth - halfW),
    clamp(point.y * sourceHeight, halfH, sourceHeight - halfH),
  ];
}

function manualPanPoints(config: KenBurnsConfig): [
  { x: number; y: number },
  { x: number; y: number },
] {
  const area = config.area;
  if (config.pan_mode === 'area' && area) {
    if (area.w >= area.h) {
      const start = { x: area.x, y: area.y + area.h / 2 };
      return [start, { x: area.x + area.w, y: start.y }];
    }
    const start = { x: area.x + area.w / 2, y: area.y };
    return [start, { x: start.x, y: area.y + area.h }];
  }
  return [config.start, config.end];
}

/** Port of `plan_manual_ken_burns_motion()` for an enabled manual config. */
function planManual(
  config: KenBurnsConfig,
  options: KenBurnsPreviewOptions,
): KenBurnsPreviewPlan {
  const { prepared, outputWidth, outputHeight } = options;
  const sourceWidth = prepared.width;
  const sourceHeight = prepared.height;
  const duration = Math.max(0, Number(options.duration) || 0);

  const headroom = Math.min(
    sourceWidth / Math.max(1, outputWidth),
    sourceHeight / Math.max(1, outputHeight),
  );
  const targetZoom = Math.max(
    MANUAL_ZOOM_MIN,
    Math.min(config.zoom, headroom, MANUAL_ZOOM_MAX),
  );

  let startZoom: number;
  let endZoom: number;
  if (config.animation === 'zoom_in') {
    startZoom = MANUAL_ZOOM_MIN;
    endZoom = targetZoom;
  } else if (config.animation === 'zoom_out') {
    startZoom = targetZoom;
    endZoom = MANUAL_ZOOM_MIN;
  } else if (config.animation === 'pan_zoom') {
    startZoom = 1 + (targetZoom - 1) * 0.25;
    endZoom = targetZoom;
  } else {
    startZoom = targetZoom;
    endZoom = targetZoom;
  }

  const startCrop = manualCropDims(startZoom, sourceWidth, sourceHeight);
  const endCrop = manualCropDims(endZoom, sourceWidth, sourceHeight);

  let startPoint: { x: number; y: number };
  let endPoint: { x: number; y: number };
  let startCentre: [number, number];
  let endCentre: [number, number];

  if (config.animation === 'zoom_in' || config.animation === 'zoom_out') {
    startPoint = config.focal_point;
    endPoint = config.focal_point;
    startCentre = centreForPoint(
      startPoint,
      sourceWidth,
      sourceHeight,
      startCrop[0],
      startCrop[1],
    );
    endCentre = centreForPoint(
      endPoint,
      sourceWidth,
      sourceHeight,
      endCrop[0],
      endCrop[1],
    );
  } else {
    [startPoint, endPoint] = manualPanPoints(config);
    startCentre = centreForPoint(
      startPoint,
      sourceWidth,
      sourceHeight,
      startCrop[0],
      startCrop[1],
    );
    endCentre = centreForPoint(
      endPoint,
      sourceWidth,
      sourceHeight,
      endCrop[0],
      endCrop[1],
    );
  }

  return {
    sourceWidth,
    sourceHeight,
    duration,
    motion: `manual_${config.animation}`,
    source: 'manual',
    subject: null,
    startCrop,
    endCrop,
    startCentre,
    endCentre,
    startScale: startZoom,
    endScale: endZoom,
  };
}

/** Build a preview plan for the block's current configuration. */
export function buildKenBurnsPreviewPlan(
  options: KenBurnsPreviewOptions,
): KenBurnsPreviewPlan {
  const raw = options.config;
  const usable =
    raw &&
    raw.enabled &&
    MANUAL_ANIMATIONS.includes(raw.animation);
  if (usable) {
    return planManual(resolveKenBurnsConfig(raw), options);
  }
  return planAutomatic(options);
}

/**
 * Sample the plan at `t` seconds and return the crop window normalised to the
 * prepared frame.  Mirrors `sample_ken_burns_motion()`, including smoothstep
 * easing, rounding and subject clamping.
 */
export function sampleKenBurnsPreview(
  plan: KenBurnsPreviewPlan,
  t: number,
): KenBurnsPreviewFrame {
  const span = plan.duration;
  const progress = span > 0 ? clamp(t / span, 0, 1) : 0;
  const eased = progress * progress * (3 - 2 * progress);

  const cropW = Math.round(
    plan.startCrop[0] + (plan.endCrop[0] - plan.startCrop[0]) * eased,
  );
  const cropH = Math.round(
    plan.startCrop[1] + (plan.endCrop[1] - plan.startCrop[1]) * eased,
  );
  const sourceW = Math.max(1, plan.sourceWidth);
  const sourceH = Math.max(1, plan.sourceHeight);

  const safeCropW = clamp(cropW, 1, sourceW);
  const safeCropH = clamp(cropH, 1, sourceH);

  const cx =
    plan.startCentre[0] + (plan.endCentre[0] - plan.startCentre[0]) * eased;
  const cy =
    plan.startCentre[1] + (plan.endCentre[1] - plan.startCentre[1]) * eased;

  let x = Math.round(cx - safeCropW / 2);
  let y = Math.round(cy - safeCropH / 2);
  x = clamp(x, 0, sourceW - safeCropW);
  y = clamp(y, 0, sourceH - safeCropH);

  if (plan.subject) {
    const bounds = focusAreaBounds(
      plan.subject,
      sourceW,
      sourceH,
      safeCropW,
      safeCropH,
      FOCUS_OVERFLOW_RATIO,
    );
    x = clamp(x, bounds[0], bounds[1]);
    y = clamp(y, bounds[2], bounds[3]);
  }

  return {
    x: x / sourceW,
    y: y / sourceH,
    w: safeCropW / sourceW,
    h: safeCropH / sourceH,
  };
}

/**
 * CSS transform that maps a sampled crop window onto the preview stage.
 * The stage already shows the prepared frame through `object-fit: cover`, so
 * scaling the image by `1 / cropSize` and shifting the crop centre onto the
 * stage centre reproduces the renderer's framing.
 */
export function previewTransform(frame: KenBurnsPreviewFrame): {
  transform: string;
  scaleX: number;
  scaleY: number;
} {
  const scaleX = 1 / Math.max(0.0001, frame.w);
  const scaleY = 1 / Math.max(0.0001, frame.h);
  const centreX = frame.x + frame.w / 2;
  const centreY = frame.y + frame.h / 2;
  const translateX = (0.5 - centreX) * scaleX * 100;
  const translateY = (0.5 - centreY) * scaleY * 100;
  return {
    transform: `translate(${translateX}%, ${translateY}%) scale(${scaleX}, ${scaleY})`,
    scaleX,
    scaleY,
  };
}
