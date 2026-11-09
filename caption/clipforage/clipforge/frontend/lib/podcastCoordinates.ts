/**
 * podcastCoordinates.ts
 * 
 * Pure mathematical utilities for normalized coordinate transformations
 * between the interactive display preview and video source frame dimensions.
 * Normalized coordinates are in the unit interval [0.0, 1.0].
 */

export interface PodcastRegion {
  id: string;
  label: string;
  x: number;      // 0.0 to 1.0
  y: number;      // 0.0 to 1.0
  width: number;  // 0.0 to 1.0
  height: number; // 0.0 to 1.0
  color: string;
}

export const REGION_COLORS = [
  '#3b82f6', // Area 1: Blue
  '#a855f7', // Area 2: Purple
  '#10b981', // Area 3: Emerald
  '#f59e0b', // Area 4: Amber
  '#ec4899', // Area 5: Pink
  '#06b6d4', // Area 6: Cyan
];

/**
 * Creates default interview/podcast regions (Speaker 1 left, Speaker 2 right).
 */
export function createDefaultPodcastRegions(): PodcastRegion[] {
  return [
    {
      id: 'area-1',
      label: 'Area 1 (Speaker 1)',
      x: 0.06,
      y: 0.12,
      width: 0.40,
      height: 0.76,
      color: REGION_COLORS[0],
    },
    {
      id: 'area-2',
      label: 'Area 2 (Speaker 2)',
      x: 0.54,
      y: 0.12,
      width: 0.40,
      height: 0.76,
      color: REGION_COLORS[1],
    },
  ];
}

/**
 * Clamps normalized coordinates strictly within [0.0, 1.0] and enforces minimum dimensions.
 */
export function clampNormalizedRect(
  rect: { x: number; y: number; width: number; height: number },
  minSize: number = 0.05
): { x: number; y: number; width: number; height: number } {
  let x = Math.max(0.0, Math.min(1.0 - minSize, rect.x));
  let y = Math.max(0.0, Math.min(1.0 - minSize, rect.y));
  let width = Math.max(minSize, Math.min(1.0 - x, rect.width));
  let height = Math.max(minSize, Math.min(1.0 - y, rect.height));

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
    width: Math.round(width * 10000) / 10000,
    height: Math.round(height * 10000) / 10000,
  };
}

/**
 * Converts mouse/touch client coordinates to normalized [0.0, 1.0] coordinates relative to container.
 */
export function displayToNormalized(
  clientX: number,
  clientY: number,
  containerRect: { left: number; top: number; width: number; height: number }
): { x: number; y: number } {
  if (!containerRect || containerRect.width <= 0 || containerRect.height <= 0) {
    return { x: 0, y: 0 };
  }
  const relX = clientX - containerRect.left;
  const relY = clientY - containerRect.top;
  const x = Math.max(0.0, Math.min(1.0, relX / containerRect.width));
  const y = Math.max(0.0, Math.min(1.0, relY / containerRect.height));

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
  };
}

/**
 * Converts normalized [0.0, 1.0] coordinates back to display pixel coordinates for overlay styling.
 */
export function normalizedToDisplay(
  normRect: { x: number; y: number; width: number; height: number },
  containerRect: { width: number; height: number }
): { left: number; top: number; width: number; height: number } {
  if (!containerRect || containerRect.width <= 0 || containerRect.height <= 0) {
    return { left: 0, top: 0, width: 0, height: 0 };
  }
  return {
    left: Math.round(normRect.x * containerRect.width),
    top: Math.round(normRect.y * containerRect.height),
    width: Math.round(normRect.width * containerRect.width),
    height: Math.round(normRect.height * containerRect.height),
  };
}

export interface PanelFraming {
  scaledW: number;
  scaledH: number;
  padX: number;
  padY: number;
  scaleFactor: number;
  cropW: number;
  cropH: number;
  cropX: number;
  cropY: number;
  isTight: boolean;
  tightWarning: string | null;
  arCrop: number;
  arPanel: number;
}

export interface OutputPreviewPanel {
  panelId: string;
  speakerLabel: string;
  color: string;
  panelWidth: number;
  panelHeight: number;
  panelTop: number;
  panelLeft: number;
  region: PodcastRegion;
  framing: PanelFraming;
}

export interface OutputPreviewGeometry {
  canvasWidth: number;
  canvasHeight: number;
  aspectRatio: string;
  composition: 'stacked' | 'single_region' | 'side_by_side' | 'fixed_two_person';
  panels: OutputPreviewPanel[];
  overallWarning: string | null;
}

/**
 * Shared geometry calculation contract mirroring backend LayoutEngine ScaleMode.CONTAIN logic.
 * Calculates exact crop bounds, aspect-ratio-preserving scale factor, and safe centering padding.
 */
export function calculatePanelFraming(
  region: { x: number; y: number; width: number; height: number },
  panelWidth: number = 1080,
  panelHeight: number = 960,
  srcW: number = 1920,
  srcH: number = 1080
): PanelFraming {
  // 1. Convert normalized region to source pixel coordinates (aligned to even pixels)
  let cropX = Math.round(region.x * srcW);
  let cropY = Math.round(region.y * srcH);
  let cropW = Math.round(region.width * srcW);
  let cropH = Math.round(region.height * srcH);

  cropX = Math.floor(cropX / 2) * 2;
  cropY = Math.floor(cropY / 2) * 2;
  cropW = Math.max(2, Math.floor(cropW / 2) * 2);
  cropH = Math.max(2, Math.floor(cropH / 2) * 2);

  if (cropX + cropW > srcW) {
    cropW = Math.max(2, Math.floor((srcW - cropX) / 2) * 2);
  }
  if (cropY + cropH > srcH) {
    cropH = Math.max(2, Math.floor((srcH - cropY) / 2) * 2);
  }

  // 2. Aspect ratios
  const arCrop = cropW / cropH;
  const arPanel = panelWidth / panelHeight;

  // 3. Aspect-ratio preserving ScaleMode.CONTAIN
  // scale = min(panelWidth / cropW, panelHeight / cropH)
  const scaleFactor = Math.min(panelWidth / cropW, panelHeight / cropH);
  const scaledW = Math.round(cropW * scaleFactor);
  const scaledH = Math.round(cropH * scaleFactor);

  const padX = Math.round((panelWidth - scaledW) / 2);
  const padY = Math.round((panelHeight - scaledH) / 2);

  // 4. Headroom and tight-crop risk analysis
  let isTight = false;
  let tightWarning: string | null = null;

  if (region.height < 0.22) {
    isTight = true;
    tightWarning = 'Area is very tight vertically; risk of cutting off chin/body';
  } else if (region.y < 0.04 && region.height < 0.35) {
    isTight = true;
    tightWarning = 'Minimal top headroom; risk of cutting off hair/head';
  } else if (region.width < 0.15) {
    isTight = true;
    tightWarning = 'Area is very narrow; shoulders may be clipped';
  }

  return {
    scaledW,
    scaledH,
    padX,
    padY,
    scaleFactor: Math.round(scaleFactor * 1000) / 1000,
    cropW,
    cropH,
    cropX,
    cropY,
    isTight,
    tightWarning,
    arCrop: Math.round(arCrop * 1000) / 1000,
    arPanel: Math.round(arPanel * 1000) / 1000,
  };
}

export interface SideBySideCropResult {
  x: number;
  y: number;
  w: number;
  h: number;
  norm_x: number;
  norm_y: number;
  norm_w: number;
  norm_h: number;
  region_left: number;
  region_right: number;
  user_region_width: number;
  aligned_crop_w: number;
  dest_panel_w: number;
  dest_panel_h: number;
  scale_factor: number;
  scaled_w: number;
  scaled_h: number;
  pad_x: number;
  pad_y: number;
  ffmpeg_crop: string;
  ffmpeg_filter: string;
  vertical_crop_used: boolean;
  vertical_crop_note: string;
}

/**
 * Calculates a destination-panel-optimized crop for a single participant in an A+B side-by-side layout.
 * Mirrors backend calculate_side_by_side_participant_crop with 100% bit-for-bit mathematical agreement.
 */
export function calculateSideBySideParticipantCrop(
  region: { x: number; y?: number; width?: number; w?: number; height?: number; h?: number },
  srcW: number = 1920,
  srcH: number = 1080,
  faceBox?: { x: number; y?: number; width?: number; w?: number } | null,
  destPanelW: number = 540,
  destPanelH: number = 1920
): SideBySideCropResult {
  const maxSrcW = Math.floor(srcW / 2) * 2;
  const maxSrcH = Math.floor(srcH / 2) * 2;

  const rx = Number(region.x ?? 0.0);
  const rw = Number(region.width ?? region.w ?? 0.35);

  // 1. Outward integer conversion bounded by even source dimensions
  let regionLeft = Math.max(0, Math.min(maxSrcW, Math.floor(rx * maxSrcW)));
  let regionRight = Math.max(0, Math.min(maxSrcW, Math.ceil((rx + rw) * maxSrcW)));
  if (regionRight <= regionLeft) {
    regionRight = Math.min(maxSrcW, regionLeft + 2);
  }
  const userRegionWidth = Math.max(1, regionRight - regionLeft);

  // 2. Even-aligned bounds expansion to ensure even crop_x can contain both edges
  const alignedLeft = Math.floor(regionLeft / 2) * 2;
  const alignedRight = Math.floor((regionRight + 1) / 2) * 2;
  const requiredEvenSpan = Math.max(2, alignedRight - alignedLeft);

  // 3. Minimum crop width based on destination panel aspect ratio and actual source height
  let minFillW = Math.ceil(maxSrcH * (destPanelW / destPanelH));
  if (minFillW % 2 !== 0) {
    minFillW += 1;
  }
  minFillW = Math.max(2, minFillW); // e.g. 304 for 1080p

  let alignedCropW = Math.min(maxSrcW, Math.max(minFillW, requiredEvenSpan));
  if (alignedCropW % 2 !== 0) {
    alignedCropW += 1;
  }
  alignedCropW = Math.min(maxSrcW, alignedCropW);

  // 4. Feasible interval for crop origin
  const cropXMin = Math.max(0, regionRight - alignedCropW);
  const cropXMax = Math.min(regionLeft, maxSrcW - alignedCropW);

  let evenCropXMin = Math.floor((cropXMin + 1) / 2) * 2;
  let evenCropXMax = Math.floor(cropXMax / 2) * 2;

  if (evenCropXMin > evenCropXMax) {
    evenCropXMin = Math.max(0, Math.min(maxSrcW - alignedCropW, alignedLeft));
    evenCropXMax = evenCropXMin;
  }

  // 5. Target center: check face box consistency
  let useFace = false;
  let targetCenterX = (regionLeft + regionRight) / 2.0;

  if (faceBox) {
    const fbX = Number(faceBox.x ?? 0.0);
    const fbW = Number(faceBox.width ?? faceBox.w ?? 0.0);
    if (fbW > 0) {
      const faceCenterPx = (fbX + fbW / 2.0) * maxSrcW;
      if (faceCenterPx >= regionLeft && faceCenterPx <= regionRight) {
        targetCenterX = faceCenterPx;
        useFace = true;
      }
    }
  }

  // 6. Clamping to feasible even interval
  const preferredCropX = targetCenterX - (alignedCropW / 2.0);
  const unalignedClamped = Math.max(evenCropXMin, Math.min(evenCropXMax, preferredCropX));
  let cropX = Math.round(unalignedClamped);
  cropX = Math.floor(cropX / 2) * 2;
  cropX = Math.max(evenCropXMin, Math.min(evenCropXMax, cropX));

  // 7. Post-calculation validation assertions
  const cropY = 0;
  const cropH = maxSrcH;

  // Ensure horizontal containment of selected region
  if (cropX > regionLeft || (cropX + alignedCropW) < regionRight) {
    alignedCropW = Math.min(maxSrcW, Math.max(requiredEvenSpan, alignedCropW));
    cropX = Math.max(0, Math.min(maxSrcW - alignedCropW, alignedLeft));
    cropX = Math.floor(cropX / 2) * 2;
  }

  const scaleFactor = Math.min(destPanelW / alignedCropW, destPanelH / cropH);
  const scaledW = Math.round(alignedCropW * scaleFactor);
  const scaledH = Math.round(cropH * scaleFactor);
  const padX = Math.round((destPanelW - scaledW) / 2.0);
  const padY = Math.round((destPanelH - scaledH) / 2.0);

  const ffmpegCrop = `crop=${alignedCropW}:${cropH}:${cropX}:${cropY}:exact=1`;
  const ffmpegFilter = `${ffmpegCrop},scale=${destPanelW}:${destPanelH}:force_original_aspect_ratio=decrease,pad=${destPanelW}:${destPanelH}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1`;

  return {
    x: cropX,
    y: cropY,
    w: alignedCropW,
    h: cropH,
    norm_x: Math.round((cropX / srcW) * 10000) / 10000,
    norm_y: Math.round((cropY / srcH) * 10000) / 10000,
    norm_w: Math.round((alignedCropW / srcW) * 10000) / 10000,
    norm_h: Math.round((cropH / srcH) * 10000) / 10000,
    region_left: regionLeft,
    region_right: regionRight,
    user_region_width: userRegionWidth,
    aligned_crop_w: alignedCropW,
    dest_panel_w: destPanelW,
    dest_panel_h: destPanelH,
    scale_factor: Math.round(scaleFactor * 1000000) / 1000000,
    scaled_w: scaledW,
    scaled_h: scaledH,
    pad_x: padX,
    pad_y: padY,
    ffmpeg_crop: ffmpegCrop,
    ffmpeg_filter: ffmpegFilter,
    vertical_crop_used: false,
    vertical_crop_note: 'Vertical crop fields are 0 and full source height (crop_y=0, crop_h=max_src_h) as full height is preserved and scaled proportionally with black padding.',
  };
}

/**
 * Builds the canonical 9:16 vertical output preview layout geometry.
 * Supports:
 * - Stacked Split (1080x960 top, 1080x960 bottom)
 * - Single Speaker Focus (1080x1920 full frame using deterministic Area 1)
 * - Side-by-Side (540x1920 left, 540x1920 right)
 * - Fixed Two-Person (1080x1920 single continuous canvas framing both participants)
 * - Shot-specific compositions (A_ONLY, B_ONLY, UNKNOWN_REVIEW)
 */
export function getOutputPreviewGeometry(
  composition: string = 'stacked',
  regions: PodcastRegion[] = [],
  canvasWidth: number = 1080,
  canvasHeight: number = 1920,
  srcW: number = 1920,
  srcH: number = 1080,
  outerBoundary?: { x: number; y: number; width: number; height: number },
  activeShot?: any
): OutputPreviewGeometry {
  const compLower = (composition || 'stacked').toLowerCase();

  const reg1 = regions[0] || {
    id: 'area-1',
    label: 'Area 1 (Speaker 1)',
    x: 0.06,
    y: 0.12,
    width: 0.40,
    height: 0.76,
    color: '#3b82f6',
  };
  const reg2 = regions.length > 1 ? regions[1] : {
    id: 'area-2',
    label: 'Area 2 (Speaker 2)',
    x: 0.54,
    y: 0.12,
    width: 0.40,
    height: 0.76,
    color: '#a855f7',
  };

  // Case 1: Side-by-Side (540x1920 left, 540x1920 right)
  if (compLower === 'side_by_side' || compLower === 'sidebyside') {
    const halfW = Math.floor(canvasWidth / 2); // 540
    const crop1 = calculateSideBySideParticipantCrop(reg1, srcW, srcH, null, halfW, canvasHeight);
    const crop2 = calculateSideBySideParticipantCrop(reg2, srcW, srcH, null, halfW, canvasHeight);

    const framing1: PanelFraming = {
      scaledW: crop1.scaled_w,
      scaledH: crop1.scaled_h,
      padX: crop1.pad_x,
      padY: crop1.pad_y,
      scaleFactor: Math.round(crop1.scale_factor * 1000) / 1000,
      cropW: crop1.w,
      cropH: crop1.h,
      cropX: crop1.x,
      cropY: crop1.y,
      isTight: reg1.width < 0.15,
      tightWarning: reg1.width < 0.15 ? 'Area is very narrow; shoulders may be clipped' : null,
      arCrop: Math.round((crop1.w / crop1.h) * 1000) / 1000,
      arPanel: Math.round((halfW / canvasHeight) * 1000) / 1000,
    };
    const framing2: PanelFraming = {
      scaledW: crop2.scaled_w,
      scaledH: crop2.scaled_h,
      padX: crop2.pad_x,
      padY: crop2.pad_y,
      scaleFactor: Math.round(crop2.scale_factor * 1000) / 1000,
      cropW: crop2.w,
      cropH: crop2.h,
      cropX: crop2.x,
      cropY: crop2.y,
      isTight: reg2.width < 0.15,
      tightWarning: reg2.width < 0.15 ? 'Area is very narrow; shoulders may be clipped' : null,
      arCrop: Math.round((crop2.w / crop2.h) * 1000) / 1000,
      arPanel: Math.round((halfW / canvasHeight) * 1000) / 1000,
    };

    const warnings = [framing1.tightWarning, framing2.tightWarning].filter(Boolean) as string[];

    return {
      canvasWidth,
      canvasHeight,
      aspectRatio: '9/16',
      composition: 'side_by_side',
      panels: [
        {
          panelId: 'left-panel-speaker-a',
          speakerLabel: reg1.label || 'Speaker A (Left Panel)',
          color: reg1.color || '#3b82f6',
          panelWidth: halfW,
          panelHeight: canvasHeight,
          panelTop: 0,
          panelLeft: 0,
          region: reg1,
          framing: framing1,
        },
        {
          panelId: 'right-panel-speaker-b',
          speakerLabel: reg2.label || 'Speaker B (Right Panel)',
          color: reg2.color || '#a855f7',
          panelWidth: halfW,
          panelHeight: canvasHeight,
          panelTop: 0,
          panelLeft: halfW,
          region: reg2,
          framing: framing2,
        },
      ],
      overallWarning: warnings.length > 0 ? warnings.join('; ') : null,
    };
  }

  // Case 2: Fixed Two-Person Area (Continuous 9:16 portrait canvas framing both participants)
  if (compLower === 'fixed_two_person' || compLower === 'fixed_two_person_follow') {
    let enclosingBox: { x: number; y: number; width: number; height: number };
    if (outerBoundary && outerBoundary.width > 0 && outerBoundary.height > 0) {
      enclosingBox = outerBoundary;
    } else if (regions.length >= 2) {
      const minX = Math.min(reg1.x, reg2.x);
      const minY = Math.min(reg1.y, reg2.y);
      const maxX = Math.max(reg1.x + reg1.width, reg2.x + reg2.width);
      const maxY = Math.max(reg1.y + reg1.height, reg2.y + reg2.height);
      enclosingBox = {
        x: Math.max(0, minX),
        y: Math.max(0, minY),
        width: Math.min(1.0 - minX, maxX - minX),
        height: Math.min(1.0 - minY, maxY - minY),
      };
    } else {
      enclosingBox = reg1;
    }

    const framing = calculatePanelFraming(enclosingBox, canvasWidth, canvasHeight, srcW, srcH);
    return {
      canvasWidth,
      canvasHeight,
      aspectRatio: '9/16',
      composition: 'fixed_two_person',
      panels: [
        {
          panelId: 'two-person-boundary-panel',
          speakerLabel: 'Both Participants (Fixed Outer Boundary)',
          color: '#6366f1',
          panelWidth: canvasWidth,
          panelHeight: canvasHeight,
          panelTop: 0,
          panelLeft: 0,
          region: {
            id: 'outer-boundary',
            label: 'Two-Person Boundary',
            ...enclosingBox,
            color: '#6366f1',
          },
          framing,
        },
      ],
      overallWarning: framing.tightWarning,
    };
  }

  // Case 3: B-Only Solo Focus (1080x1920 full frame using Speaker B)
  if (compLower === 'b_only' || compLower === 'speaker_b') {
    const shotCrop = activeShot?.crop_b || activeShot?.face_crop || activeShot?.crop_rect;
    const effectiveRegion = shotCrop ? {
      id: reg2.id,
      label: reg2.label || 'Area 2 (Speaker 2)',
      x: Number(shotCrop.norm_x ?? (shotCrop.x / srcW)),
      y: Number(shotCrop.norm_y ?? (shotCrop.y / srcH)),
      width: Number(shotCrop.norm_w ?? (shotCrop.w / srcW)),
      height: Number(shotCrop.norm_h ?? (shotCrop.h / srcH)),
      color: reg2.color || '#8b5cf6',
    } : reg2;
    const framing = calculatePanelFraming(effectiveRegion, canvasWidth, canvasHeight, srcW, srcH);
    return {
      canvasWidth,
      canvasHeight,
      aspectRatio: '9/16',
      composition: 'single_region',
      panels: [
        {
          panelId: 'single-focus-speaker-b',
          speakerLabel: reg2.label || 'Area 2 (Speaker 2)',
          color: reg2.color || '#8b5cf6',
          panelWidth: canvasWidth,
          panelHeight: canvasHeight,
          panelTop: 0,
          panelLeft: 0,
          region: effectiveRegion,
          framing,
        },
      ],
      overallWarning: framing.tightWarning,
    };
  }

  // Case 4: UNKNOWN_REVIEW Fallback (Safe full-frame fallback with review notice)
  if (compLower === 'unknown_review' || compLower === 'unknown') {
    const shotCrop = activeShot?.face_crop || activeShot?.crop_rect;
    const centerFallback = shotCrop ? {
      id: 'unknown-review-fallback',
      label: 'Safe Fallback (Review Recommended)',
      x: Number(shotCrop.norm_x ?? (shotCrop.x / srcW)),
      y: Number(shotCrop.norm_y ?? (shotCrop.y / srcH)),
      width: Number(shotCrop.norm_w ?? (shotCrop.w / srcW)),
      height: Number(shotCrop.norm_h ?? (shotCrop.h / srcH)),
      color: '#f59e0b',
    } : {
      id: 'unknown-review-fallback',
      label: 'Safe Fallback (Review Recommended)',
      x: 0.25,
      y: 0.0,
      width: 0.50,
      height: 1.0,
      color: '#f59e0b',
    };
    const framing = calculatePanelFraming(centerFallback, canvasWidth, canvasHeight, srcW, srcH);
    return {
      canvasWidth,
      canvasHeight,
      aspectRatio: '9/16',
      composition: 'single_region',
      panels: [
        {
          panelId: 'unknown-review-panel',
          speakerLabel: 'Unknown Visibility (Safe Fallback)',
          color: '#f59e0b',
          panelWidth: canvasWidth,
          panelHeight: canvasHeight,
          panelTop: 0,
          panelLeft: 0,
          region: centerFallback,
          framing,
        },
      ],
      overallWarning: 'Review warning: shot visibility could not be assigned to a known speaker; safe fallback applied.',
    };
  }

  // Case 5: Single Region / Single Speaker Focus / A_ONLY (Deterministic Area 1 / index 0)
  const isSingle = regions.length === 1 || compLower === 'single' || compLower === 'single_region' || compLower === 'single_focus' || compLower === 'a_only' || compLower === 'speaker_a';

  if (isSingle) {
    const shotCrop = activeShot?.crop_a || activeShot?.face_crop || activeShot?.crop_rect;
    const primaryRegion = (shotCrop && (compLower === 'a_only' || compLower === 'speaker_a')) ? {
      id: reg1.id,
      label: reg1.label || 'Area 1 (Speaker 1)',
      x: Number(shotCrop.norm_x ?? (shotCrop.x / srcW)),
      y: Number(shotCrop.norm_y ?? (shotCrop.y / srcH)),
      width: Number(shotCrop.norm_w ?? (shotCrop.w / srcW)),
      height: Number(shotCrop.norm_h ?? (shotCrop.h / srcH)),
      color: reg1.color || '#3b82f6',
    } : reg1;
    const framing = calculatePanelFraming(primaryRegion, canvasWidth, canvasHeight, srcW, srcH);
    return {
      canvasWidth,
      canvasHeight,
      aspectRatio: '9/16',
      composition: 'single_region',
      panels: [
        {
          panelId: 'single-focus-panel',
          speakerLabel: primaryRegion.label || 'Area 1 (Speaker 1)',
          color: primaryRegion.color || '#3b82f6',
          panelWidth: canvasWidth,
          panelHeight: canvasHeight,
          panelTop: 0,
          panelLeft: 0,
          region: primaryRegion,
          framing,
        },
      ],
      overallWarning: framing.tightWarning,
    };
  }

  // Case 6: Stacked Split (Top: Speaker 1, Bottom: Speaker 2)
  const halfH = Math.floor(canvasHeight / 2); // 960
  const framing1 = calculatePanelFraming(reg1, canvasWidth, halfH, srcW, srcH);
  const framing2 = calculatePanelFraming(reg2, canvasWidth, halfH, srcW, srcH);

  const warnings = [framing1.tightWarning, framing2.tightWarning].filter(Boolean) as string[];

  return {
    canvasWidth,
    canvasHeight,
    aspectRatio: '9/16',
    composition: 'stacked',
    panels: [
      {
        panelId: 'top-panel-speaker-1',
        speakerLabel: reg1.label || 'Speaker 1 (Top Panel)',
        color: reg1.color || '#3b82f6',
        panelWidth: canvasWidth,
        panelHeight: halfH,
        panelTop: 0,
        panelLeft: 0,
        region: reg1,
        framing: framing1,
      },
      {
        panelId: 'bottom-panel-speaker-2',
        speakerLabel: reg2.label || 'Speaker 2 (Bottom Panel)',
        color: reg2.color || '#a855f7',
        panelWidth: canvasWidth,
        panelHeight: halfH,
        panelTop: halfH,
        panelLeft: 0,
        region: reg2,
        framing: framing2,
      },
    ],
    overallWarning: warnings.length > 0 ? warnings.join('; ') : null,
  };
}

