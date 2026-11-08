import {
  buildKenBurnsPreviewPlan,
  computePreparedFrame,
  normalisePreviewFocusAreas,
  previewTransform,
  sampleKenBurnsPreview,
} from '@/lib/kenBurnsPreview';
import type { KenBurnsConfig } from '@/lib/types';

const OUTPUT = { width: 1920, height: 1080 };
const PREPARED = { width: 2496, height: 1404 };
const ZOOM = 1.3;

function manualConfig(patch: Partial<KenBurnsConfig> = {}): KenBurnsConfig {
  return {
    enabled: true,
    animation: 'pan',
    pan_mode: 'points',
    start: { x: 0.4, y: 0.5 },
    end: { x: 0.6, y: 0.5 },
    focal_point: { x: 0.5, y: 0.5 },
    area: null,
    zoom: 1.3,
    ...patch,
  };
}

function build(config: KenBurnsConfig | null, duration = 5) {
  return buildKenBurnsPreviewPlan({
    config,
    duration,
    segmentIndex: 0,
    prepared: PREPARED,
    outputWidth: OUTPUT.width,
    outputHeight: OUTPUT.height,
    zoomIntensity: ZOOM,
  });
}

describe('kenBurnsPreview', () => {
  describe('computePreparedFrame', () => {
    it('upscales a small square source to the renderer minimum', () => {
      expect(computePreparedFrame(1024, 1024, 1920, 1080, 1.3)).toEqual({
        width: 2496,
        height: 1404,
      });
    });

    it('keeps a source that already matches the minimum size', () => {
      expect(computePreparedFrame(2400, 1350, 1920, 1080, 1.3)).toEqual({
        width: 2496,
        height: 1404,
      });
    });

    it('downscales an oversized 4K frame to the minimum', () => {
      expect(computePreparedFrame(3840, 2160, 1920, 1080, 1.3)).toEqual({
        width: 2496,
        height: 1404,
      });
    });
  });

  it('normalises a single focus area and ignores extra legacy entries', () => {
    expect(
      normalisePreviewFocusAreas([
        { x: 0.2, y: 0.2, w: 0.2, h: 0.2 },
        { x: 0.6, y: 0.6, w: 0.2, h: 0.2 },
      ]),
    ).toEqual([{ x: 0.2, y: 0.2, w: 0.2, h: 0.2 }]);
  });

  it('moves a manual pan from the start point to the end point', () => {
    const plan = build(manualConfig());
    const start = sampleKenBurnsPreview(plan, 0);
    const end = sampleKenBurnsPreview(plan, 5);

    expect(plan.motion).toBe('manual_pan');
    expect(plan.source).toBe('manual');
    expect(plan.startCrop).toEqual(plan.endCrop);
    expect(end.x).toBeGreaterThan(start.x);
    expect(start.y).toBeCloseTo(end.y, 5);
    expect(start.w).toBeCloseTo(end.w, 5);
  });

  it('holds the focal point while a manual zoom pushes in', () => {
    const plan = build(
      manualConfig({
        animation: 'zoom_in',
        focal_point: { x: 0.5, y: 0.5 },
        zoom: 1.3,
      }),
    );
    const start = sampleKenBurnsPreview(plan, 0);
    const end = sampleKenBurnsPreview(plan, 5);

    expect(plan.motion).toBe('manual_zoom_in');
    expect(end.w).toBeLessThan(start.w);
    expect(end.h).toBeLessThan(start.h);
    expect(start.x + start.w / 2).toBeCloseTo(0.5, 5);
    expect(end.x + end.w / 2).toBeCloseTo(0.5, 5);
    expect(start.y + start.h / 2).toBeCloseTo(0.5, 5);
    expect(end.y + end.h / 2).toBeCloseTo(0.5, 5);
  });

  it('sweeps across the longer axis of a drawn pan area', () => {
    const plan = build(
      manualConfig({
        pan_mode: 'area',
        area: { x: 0.1, y: 0.2, w: 0.8, h: 0.2 },
      }),
    );
    const start = sampleKenBurnsPreview(plan, 0);
    const end = sampleKenBurnsPreview(plan, 5);

    expect(end.x).toBeGreaterThan(start.x);
    expect(start.y).toBeCloseTo(end.y, 5);
  });

  it('caps the manual zoom at the prepared-frame headroom', () => {
    const plan = build(manualConfig({ animation: 'zoom_in', zoom: 2 }));
    // 2496 / 1920 = 1.3, so the requested 2× is capped exactly like the backend.
    expect(plan.endScale).toBeCloseTo(1.3, 5);
    expect(plan.endCrop).toEqual([1920, 1080]);
  });

  it('falls back to the automatic planner when manual mode is disabled', () => {
    const plan = build(manualConfig({ enabled: false }));
    expect(plan.source).toBe('automatic');
    expect(plan.motion.startsWith('automatic_')).toBe(true);
    expect(plan.startCrop.length).toBe(2);
    expect(plan.endCrop.length).toBe(2);
  });

  it('matches the backend automatic planner for segment 0 at 5 s', () => {
    // Values produced by plan_ken_burns_motion(0, 5, 2496, 1404, 1920, 1080, 1.3)
    // and sample_ken_burns_motion() on the Python side.
    const plan = build(null, 5);
    const start = sampleKenBurnsPreview(plan, 0);
    const end = sampleKenBurnsPreview(plan, 5);

    expect(plan.motion).toBe('automatic_pan');
    expect(plan.startCrop).toEqual([1476, 830]);
    expect(plan.endCrop).toEqual([1476, 830]);
    expect(start.x).toBeCloseTo(344 / 2496, 6);
    expect(start.y).toBeCloseTo(194 / 1404, 6);
    expect(start.w).toBeCloseTo(1476 / 2496, 6);
    expect(start.h).toBeCloseTo(830 / 1404, 6);
    expect(end.x).toBeCloseTo(676 / 2496, 6);
    expect(end.y).toBeCloseTo(380 / 1404, 6);
  });

  it('matches the backend subject-aware pan at segment 5 for 6 s', () => {
    const plan = buildKenBurnsPreviewPlan({
      config: null,
      duration: 6,
      segmentIndex: 5,
      prepared: PREPARED,
      outputWidth: OUTPUT.width,
      outputHeight: OUTPUT.height,
      zoomIntensity: ZOOM,
      focusArea: { x: 0.36, y: 0.34, w: 0.18, h: 0.22 },
    });
    const start = sampleKenBurnsPreview(plan, 0);
    const end = sampleKenBurnsPreview(plan, 6);

    expect(plan.motion).toBe('automatic_pan');
    expect(plan.startCrop).toEqual([1624, 913]);
    expect(start.x).toBeCloseTo(217 / 2496, 6);
    expect(start.y).toBeCloseTo(122 / 1404, 6);
    expect(end.x).toBeCloseTo(655 / 2496, 6);
    expect(end.y).toBeCloseTo(369 / 1404, 6);
  });

  it('uses smoothstep easing (half progress is halfway through the move)', () => {
    const plan = build(manualConfig());
    const start = sampleKenBurnsPreview(plan, 0);
    const middle = sampleKenBurnsPreview(plan, 2.5);
    const end = sampleKenBurnsPreview(plan, 5);
    expect(middle.x).toBeCloseTo((start.x + end.x) / 2, 3);
  });

  it('clamps samples outside the clip range', () => {
    const plan = build(manualConfig());
    expect(sampleKenBurnsPreview(plan, -2)).toEqual(
      sampleKenBurnsPreview(plan, 0),
    );
    expect(sampleKenBurnsPreview(plan, 99)).toEqual(
      sampleKenBurnsPreview(plan, 5),
    );
  });

  it('builds a CSS transform that maps the crop onto the stage', () => {
    expect(previewTransform({ x: 0.25, y: 0.25, w: 0.5, h: 0.5 })).toEqual({
      transform: 'translate(0%, 0%) scale(2, 2)',
      scaleX: 2,
      scaleY: 2,
    });
    const corner = previewTransform({ x: 0, y: 0, w: 0.5, h: 0.5 });
    expect(corner.transform).toBe('translate(50%, 50%) scale(2, 2)');
  });
});
