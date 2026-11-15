/**
 * gamingCoordinates.ts
 *
 * Authoritative Unified Geometry Engine and Coordinate Contracts for
 * ClipForge Dual-Region Gaming Layout (Milestone M1).
 *
 * Implements:
 * - Normalized coordinate unit space [0.0, 1.0]
 * - Container letterbox/pillarbox offset calculations
 * - Responsive pointer-to-normalized conversions
 * - Strict boundary clamping and opposite-corner anchor-preserving resize math
 * - Facecam placement presets (top-left, top-right, bottom-left, bottom-right)
 * - YUV420p even-pixel quantization for FFmpeg parity
 * - Scale-to-fill 9:16 vertical canvas framing mathematics
 */

/**
 * Normalized rectangle representing coordinates relative to source or canvas [0.0, 1.0].
 */
export interface NormalizedRect {
  x: number;      // [0.0, 1.0] left offset
  y: number;      // [0.0, 1.0] top offset
  width: number;  // [0.05, 1.0] width
  height: number; // [0.05, 1.0] height
}

/**
 * Pixel rectangle with integer boundaries aligned to even dimensions for video codecs.
 */
export interface PixelRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/**
 * DOM container bounding rectangle.
 */
export interface ContainerRect {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Video render offsets inside container due to letterbox/pillarbox bars.
 */
export interface RenderOffsets {
  renderLeft: number;
  renderTop: number;
  renderWidth: number;
  renderHeight: number;
}

/**
 * Standard 4-corner placement presets on 9:16 vertical canvas.
 */
export type FacecamPreset = 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';

/**
 * Corner and edge resize handles for interactive bounding boxes.
 */
export type ResizeHandle = 'nw' | 'ne' | 'se' | 'sw' | 'n' | 's' | 'e' | 'w';

/**
 * Display pixel coordinates for CSS positioning.
 */
export interface DisplayGeometry {
  left: number;
  top: number;
  width: number;
  height: number;
}

/**
 * Gaming Layout Configuration contract matching API and persist payload.
 */
export interface GamingLayoutConfig {
  mode: 'gaming';
  gameplay_roi: NormalizedRect;
  facecam_roi: NormalizedRect;
  facecam_placement: FacecamPreset | 'custom';
  facecam_output_rect?: NormalizedRect | null;
  canvas_width?: number;
  canvas_height?: number;
}

/**
 * Scale-to-fill framing calculation result for canvas drawing and preview.
 */
export interface FramingResult {
  scaleFactor: number;
  scaledW: number;
  scaledH: number;
  scaled_w?: number;
  scaled_h?: number;
  cropOffsetX: number;
  cropOffsetY: number;
  offset_x?: number;
  offset_y?: number;
  canvasWidth: number;
  canvasHeight: number;
  canvas_w?: number;
  canvas_h?: number;
  sourceCrop: PixelRect;
  sourceSubCrop?: PixelRect;
  ffmpegScaleFilter: string;
  ffmpeg_scale_filter?: string;
}

/**
 * Unified calculation result matching golden vector expectations and FFmpeg filter requirements.
 */
export interface GamingPlanResult {
  is_valid: boolean;
  facecam_resolved_output_rect: NormalizedRect;
  gameplay_crop: PixelRect;
  facecam_crop: PixelRect;
  facecam_dest: PixelRect;
  canvas_width: number;
  canvas_height: number;
  gameplay_scale_factor: number;
  gameplay_scaled_w: number;
  gameplay_scaled_h: number;
  ffmpeg_crop_gameplay: string;
  ffmpeg_crop_facecam: string;
  ffmpeg_filtergraph: string;
}

// Default presets geometry constants
export const DEFAULT_FACECAM_WIDTH = 0.30;
export const DEFAULT_FACECAM_HEIGHT = 0.22;
export const DEFAULT_FACECAM_MARGIN_X = 0.05;
export const DEFAULT_FACECAM_MARGIN_Y = 0.04;
export const MIN_ROI_SIZE = 0.05;
export const DEFAULT_CANVAS_WIDTH = 1080;
export const DEFAULT_CANVAS_HEIGHT = 1920;

/**
 * Calculates letterbox or pillarbox padding when video is fitted (object-fit: contain)
 * within a preview container.
 */
export function calculateRenderOffsets(
  containerWidth: number,
  containerHeight: number,
  videoWidth: number,
  videoHeight: number
): RenderOffsets {
  if (containerWidth <= 0 || containerHeight <= 0 || videoWidth <= 0 || videoHeight <= 0) {
    return {
      renderLeft: 0,
      renderTop: 0,
      renderWidth: Math.max(0, containerWidth),
      renderHeight: Math.max(0, containerHeight),
    };
  }

  const arVideo = videoWidth / videoHeight;
  const arContainer = containerWidth / containerHeight;

  let renderWidth = containerWidth;
  let renderHeight = containerHeight;
  let renderLeft = 0;
  let renderTop = 0;

  if (arVideo > arContainer) {
    // Letterbox: Video is wider than container; horizontal fit, top/bottom black bars
    renderWidth = containerWidth;
    renderHeight = Math.round(containerWidth / arVideo);
    renderTop = Math.floor((containerHeight - renderHeight) / 2);
  } else {
    // Pillarbox: Video is taller than or equal to container; vertical fit, left/right black bars
    renderHeight = containerHeight;
    renderWidth = Math.round(containerHeight * arVideo);
    renderLeft = Math.floor((containerWidth - renderWidth) / 2);
  }

  return {
    renderLeft,
    renderTop,
    renderWidth,
    renderHeight,
  };
}

/**
 * Converts DOM mouse/pointer coordinates to normalized [0.0, 1.0] coordinates relative
 * to the video frame, compensating for letterbox/pillarbox padding without drift.
 */
export function displayToNormalized(
  clientX: number,
  clientY: number,
  containerRect: ContainerRect,
  videoWidth?: number,
  videoHeight?: number
): { x: number; y: number } {
  if (!containerRect || containerRect.width <= 0 || containerRect.height <= 0) {
    return { x: 0, y: 0 };
  }

  let renderLeft = 0;
  let renderTop = 0;
  let renderWidth = containerRect.width;
  let renderHeight = containerRect.height;

  if (videoWidth && videoHeight && videoWidth > 0 && videoHeight > 0) {
    const offsets = calculateRenderOffsets(containerRect.width, containerRect.height, videoWidth, videoHeight);
    renderLeft = offsets.renderLeft;
    renderTop = offsets.renderTop;
    renderWidth = offsets.renderWidth;
    renderHeight = offsets.renderHeight;
  }

  const relX = clientX - (containerRect.left + renderLeft);
  const relY = clientY - (containerRect.top + renderTop);

  const x = Math.max(0.0, Math.min(1.0, relX / renderWidth));
  const y = Math.max(0.0, Math.min(1.0, relY / renderHeight));

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
  };
}

/**
 * Specialized letterbox pointer conversion returning both container render_rect
 * and clamped normalized_pointer, matching cross-language golden vector contracts.
 */
export function displayToNormalizedLetterbox(
  clientX: number,
  clientY: number,
  container: ContainerRect,
  srcW: number,
  srcH: number
): {
  render_rect: { x: number; y: number; width: number; height: number };
  normalized_pointer: { x: number; y: number };
} {
  const offsets = calculateRenderOffsets(container.width, container.height, srcW, srcH);
  const relX = clientX - (container.left + offsets.renderLeft);
  const relY = clientY - (container.top + offsets.renderTop);

  const normX = Math.max(0.0, Math.min(1.0, relX / offsets.renderWidth));
  const normY = Math.max(0.0, Math.min(1.0, relY / offsets.renderHeight));

  return {
    render_rect: {
      x: offsets.renderLeft,
      y: offsets.renderTop,
      width: offsets.renderWidth,
      height: offsets.renderHeight,
    },
    normalized_pointer: {
      x: Math.round(normX * 10000) / 10000,
      y: Math.round(normY * 10000) / 10000,
    },
  };
}

/**
 * Converts a normalized rectangle back to container display pixels for CSS overlay positioning.
 */
export function normalizedToDisplay(
  normRect: NormalizedRect,
  containerWidth: number,
  containerHeight: number,
  renderOffsets?: RenderOffsets
): DisplayGeometry {
  const leftOffset = renderOffsets ? renderOffsets.renderLeft : 0;
  const topOffset = renderOffsets ? renderOffsets.renderTop : 0;
  const activeW = renderOffsets ? renderOffsets.renderWidth : containerWidth;
  const activeH = renderOffsets ? renderOffsets.renderHeight : containerHeight;

  return {
    left: Math.round(leftOffset + normRect.x * activeW),
    top: Math.round(topOffset + normRect.y * activeH),
    width: Math.round(normRect.width * activeW),
    height: Math.round(normRect.height * activeH),
  };
}

/**
 * Clamps normalized coordinates strictly within [0.0, 1.0] and enforces minimum dimension.
 */
export function clampNormalizedRect(
  rect: { x: number; y: number; width: number; height: number },
  minSize: number = MIN_ROI_SIZE
): NormalizedRect {
  const safeX = Number.isFinite(rect.x) ? rect.x : 0;
  const safeY = Number.isFinite(rect.y) ? rect.y : 0;
  const safeW = Number.isFinite(rect.width) ? rect.width : minSize;
  const safeH = Number.isFinite(rect.height) ? rect.height : minSize;

  let x = Math.max(0.0, Math.min(1.0 - minSize, safeX));
  let y = Math.max(0.0, Math.min(1.0 - minSize, safeY));
  let width = Math.max(minSize, Math.min(1.0 - x, safeW));
  let height = Math.max(minSize, Math.min(1.0 - y, safeH));

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
    width: Math.round(width * 10000) / 10000,
    height: Math.round(height * 10000) / 10000,
  };
}

/**
 * Calculates resize deltas preserving the opposite corner as a fixed anchor point.
 * Prevents edge jumping when resizing bounding boxes near boundaries.
 */
export function calculateResize(
  initialRect: NormalizedRect,
  handle: ResizeHandle,
  deltaNormX: number,
  deltaNormY: number,
  minSize: number = MIN_ROI_SIZE
): NormalizedRect {
  const x0 = initialRect.x;
  const y0 = initialRect.y;
  const w0 = initialRect.width;
  const h0 = initialRect.height;

  let x = x0;
  let y = y0;
  let width = w0;
  let height = h0;

  switch (handle) {
    case 'se': {
      // Anchor: Top-Left (x0, y0)
      const r = Math.max(x0 + minSize, Math.min(1.0, x0 + w0 + deltaNormX));
      const b = Math.max(y0 + minSize, Math.min(1.0, y0 + h0 + deltaNormY));
      x = x0;
      y = y0;
      width = r - x0;
      height = b - y0;
      break;
    }
    case 'ne': {
      // Anchor: Bottom-Left (x0, y0 + h0)
      const r = Math.max(x0 + minSize, Math.min(1.0, x0 + w0 + deltaNormX));
      const newY = Math.max(0.0, Math.min(y0 + h0 - minSize, y0 + deltaNormY));
      x = x0;
      y = newY;
      width = r - x0;
      height = (y0 + h0) - newY;
      break;
    }
    case 'sw': {
      // Anchor: Top-Right (x0 + w0, y0)
      const newX = Math.max(0.0, Math.min(x0 + w0 - minSize, x0 + deltaNormX));
      const b = Math.max(y0 + minSize, Math.min(1.0, y0 + h0 + deltaNormY));
      x = newX;
      y = y0;
      width = (x0 + w0) - newX;
      height = b - y0;
      break;
    }
    case 'nw': {
      // Anchor: Bottom-Right (x0 + w0, y0 + h0)
      const newX = Math.max(0.0, Math.min(x0 + w0 - minSize, x0 + deltaNormX));
      const newY = Math.max(0.0, Math.min(y0 + h0 - minSize, y0 + deltaNormY));
      x = newX;
      y = newY;
      width = (x0 + w0) - newX;
      height = (y0 + h0) - newY;
      break;
    }
    case 'n': {
      // Anchor: Bottom edge (y0 + h0). x and width remain constant.
      const newY = Math.max(0.0, Math.min(y0 + h0 - minSize, y0 + deltaNormY));
      x = x0;
      y = newY;
      width = w0;
      height = (y0 + h0) - newY;
      break;
    }
    case 's': {
      // Anchor: Top edge (y0). x and width remain constant.
      const b = Math.max(y0 + minSize, Math.min(1.0, y0 + h0 + deltaNormY));
      x = x0;
      y = y0;
      width = w0;
      height = b - y0;
      break;
    }
    case 'w': {
      // Anchor: Right edge (x0 + w0). y and height remain constant.
      const newX = Math.max(0.0, Math.min(x0 + w0 - minSize, x0 + deltaNormX));
      x = newX;
      y = y0;
      width = (x0 + w0) - newX;
      height = h0;
      break;
    }
    case 'e': {
      // Anchor: Left edge (x0). y and height remain constant.
      const r = Math.max(x0 + minSize, Math.min(1.0, x0 + w0 + deltaNormX));
      x = x0;
      y = y0;
      width = r - x0;
      height = h0;
      break;
    }
  }

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
    width: Math.round(width * 10000) / 10000,
    height: Math.round(height * 10000) / 10000,
  };
}

export const applyResizeHandle = calculateResize;

/**
 * Applies drag translation preserving rectangle width and height clamped inside [0.0, 1.0].
 */
export function applyDrag(
  initialRect: NormalizedRect,
  deltaNormX: number,
  deltaNormY: number
): NormalizedRect {
  let x = initialRect.x + deltaNormX;
  let y = initialRect.y + deltaNormY;

  x = Math.max(0.0, Math.min(1.0 - initialRect.width, x));
  y = Math.max(0.0, Math.min(1.0 - initialRect.height, y));

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
    width: initialRect.width,
    height: initialRect.height,
  };
}

/**
 * Calculates normalized placement coordinates for standard facecam presets.
 */
export function getFacecamPreset(
  preset: FacecamPreset | string,
  customWidth: number = DEFAULT_FACECAM_WIDTH,
  customHeight: number = DEFAULT_FACECAM_HEIGHT,
  marginX: number = DEFAULT_FACECAM_MARGIN_X,
  marginY: number = DEFAULT_FACECAM_MARGIN_Y
): NormalizedRect {
  const p = String(preset).toLowerCase();
  let x: number;
  let y: number;

  switch (p) {
    case 'top-left':
      x = marginX;
      y = marginY;
      break;
    case 'top-right':
      x = 1.0 - customWidth - marginX;
      y = marginY;
      break;
    case 'bottom-left':
      x = marginX;
      y = 1.0 - customHeight - marginY;
      break;
    case 'bottom-right':
      x = 1.0 - customWidth - marginX;
      y = 1.0 - customHeight - marginY;
      break;
    default:
      throw new Error(`Unknown facecam preset '${preset}'. Expected: 'top-left', 'top-right', 'bottom-left', 'bottom-right'`);
  }

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
    width: Math.round(customWidth * 10000) / 10000,
    height: Math.round(customHeight * 10000) / 10000,
  };
}

export const getFacecamPresetRect = getFacecamPreset;

/**
 * Default normalized Gameplay ROI (full frame).
 */
export function getDefaultGameplayRoi(): NormalizedRect {
  return {
    x: 0.0,
    y: 0.0,
    width: 1.0,
    height: 1.0,
  };
}

/**
 * Calculates a centered 9:16 portrait crop in normalized coordinate space [0.0, 1.0]
 * for a source video of dimensions srcW x srcH.
 * For standard 16:9 landscape (1920x1080), normalized height is 1.0,
 * normalized width is (1080 * 9/16) / 1920 = 607.5 / 1920 ≈ 0.3164, centered at x ≈ 0.3418.
 */
export function getCenteredPortraitRoi(
  srcW: number = 1920,
  srcH: number = 1080,
  targetAspect: number = 9 / 16
): NormalizedRect {
  const w = srcW > 0 ? srcW : 1920;
  const h = srcH > 0 ? srcH : 1080;
  const srcAspect = w / h;

  let normW: number;
  let normH: number;
  let x: number;
  let y: number;

  if (srcAspect >= targetAspect) {
    // Landscape or wider than 9:16: Full height, crop width
    normH = 1.0;
    normW = Math.min(1.0, (h * targetAspect) / w);
    x = Math.max(0.0, (1.0 - normW) / 2);
    y = 0.0;
  } else {
    // Taller than 9:16: Full width, crop height
    normW = 1.0;
    normH = Math.min(1.0, (w / targetAspect) / h);
    x = 0.0;
    y = Math.max(0.0, (1.0 - normH) / 2);
  }

  return {
    x: Math.round(x * 10000) / 10000,
    y: Math.round(y * 10000) / 10000,
    width: Math.round(normW * 10000) / 10000,
    height: Math.round(normH * 10000) / 10000,
  };
}

/**
 * Default normalized Facecam source ROI (top-right quadrant).
 */
export function getDefaultFacecamRoi(): NormalizedRect {
  return {
    x: 0.70,
    y: 0.05,
    width: 0.25,
    height: 0.25,
  };
}

/**
 * Default Facecam canvas output overlay rect (top-right preset on 9:16).
 */
export function getDefaultFacecamOutputRect(preset: FacecamPreset = 'top-right'): NormalizedRect {
  return getFacecamPreset(preset);
}

/**
 * Converts a normalized coordinate to an even integer pixel value matching YUV420p codec requirements.
 * Formula: floor((coord * dim) / 2) * 2
 */
export function toEvenPixel(val: number, dim: number): number {
  if (!Number.isFinite(val)) {
    throw new Error(`Coordinate must be finite, got ${val}`);
  }
  if (!Number.isFinite(dim)) {
    throw new Error(`Dimension must be finite, got ${dim}`);
  }
  if (val < -1e-4) {
    throw new Error(`negative coordinate: ${val} is less than 0`);
  }
  return Math.floor((Math.max(0, val) * dim) / 2) * 2;
}

/**
 * Converts a normalized dimension span to an even integer pixel value.
 * Guarantees at least 2 pixels.
 */
export function toEvenSpan(val: number, dim: number): number {
  if (!Number.isFinite(val)) {
    throw new Error(`Dimension must be finite, got ${val}`);
  }
  if (!Number.isFinite(dim)) {
    throw new Error(`Dimension must be finite, got ${dim}`);
  }
  return Math.max(2, Math.floor((Math.max(0, val) * dim) / 2) * 2);
}

/**
 * Converts normalized rect to even-pixel source dimensions.
 */
export function toEvenPixels(normRect: NormalizedRect, width: number, height: number): PixelRect {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    throw new Error(`Source dimensions must be positive, got ${width}x${height}`);
  }
  const norm = validateNormalizedRect(normRect, 'source_crop');
  const maxW = Math.floor(width / 2) * 2;
  const maxH = Math.floor(height / 2) * 2;

  let x = toEvenPixel(norm.x, width);
  let y = toEvenPixel(norm.y, height);
  let w = toEvenSpan(norm.width, width);
  let h = toEvenSpan(norm.height, height);

  if (maxW < 2) {
    x = 0;
    w = 0;
  } else {
    w = Math.min(w, maxW);
    if (x + w > maxW) {
      x = Math.max(0, maxW - w);
    }
  }

  if (maxH < 2) {
    y = 0;
    h = 0;
  } else {
    h = Math.min(h, maxH);
    if (y + h > maxH) {
      y = Math.max(0, maxH - h);
    }
  }

  return { x, y, w, h };
}

export const toSourceCrop = toEvenPixels;

/**
 * Converts normalized facecam output rect to canvas overlay pixels.
 */
export function toCanvasOverlay(
  rect: NormalizedRect,
  canvasW: number = DEFAULT_CANVAS_WIDTH,
  canvasH: number = DEFAULT_CANVAS_HEIGHT
): PixelRect {
  if (!Number.isFinite(canvasW) || !Number.isFinite(canvasH) || canvasW <= 0 || canvasH <= 0) {
    throw new Error(`Canvas dimensions must be positive, got ${canvasW}x${canvasH}`);
  }
  const norm = validateNormalizedRect(rect, 'canvas_overlay');
  const maxW = Math.floor(canvasW / 2) * 2;
  const maxH = Math.floor(canvasH / 2) * 2;

  let destX = toEvenPixel(norm.x, canvasW);
  let destY = toEvenPixel(norm.y, canvasH);
  let destW = toEvenSpan(norm.width, canvasW);
  let destH = toEvenSpan(norm.height, canvasH);

  if (maxW < 2) {
    destX = 0;
    destW = 0;
  } else {
    destW = Math.min(destW, maxW);
    if (destX + destW > maxW) {
      destX = Math.max(0, maxW - destW);
    }
  }

  if (maxH < 2) {
    destY = 0;
    destH = 0;
  } else {
    destH = Math.min(destH, maxH);
    if (destY + destH > maxH) {
      destY = Math.max(0, maxH - destH);
    }
  }

  return { x: destX, y: destY, w: destW, h: destH };
}

/**
 * Calculates scale-to-fill framing metrics for the gameplay layer without stretching or distortion.
 */
export function calculateGameplayFraming(
  sourceCrop: PixelRect | { x: number; y: number; width?: number; height?: number; w?: number; h?: number },
  canvasWidth: number = DEFAULT_CANVAS_WIDTH,
  canvasHeight: number = DEFAULT_CANVAS_HEIGHT
): FramingResult {
  if (!Number.isFinite(canvasWidth) || !Number.isFinite(canvasHeight) || canvasWidth <= 0 || canvasHeight <= 0) {
    throw new Error(`Canvas dimensions must be positive, got ${canvasWidth}x${canvasHeight}`);
  }
  const cropW = (sourceCrop as any).w ?? (sourceCrop as any).width ?? canvasWidth;
  const cropH = (sourceCrop as any).h ?? (sourceCrop as any).height ?? canvasHeight;
  const cropX = sourceCrop.x ?? 0;
  const cropY = sourceCrop.y ?? 0;

  if (cropW <= 0 || cropH <= 0) {
    throw new Error(`Crop dimensions must be positive, got ${cropW}x${cropH}`);
  }

  const scaleFactor = Math.max(canvasWidth / cropW, canvasHeight / cropH);
  const scaledW = Math.round(cropW * scaleFactor);
  const scaledH = Math.round(cropH * scaleFactor);

  const cropOffsetX = Math.floor((scaledW - canvasWidth) / 2);
  const cropOffsetY = Math.floor((scaledH - canvasHeight) / 2);

  const subCropW = Math.round(canvasWidth / scaleFactor);
  const subCropH = Math.round(canvasHeight / scaleFactor);
  const subCropX = cropX + Math.floor((cropW - subCropW) / 2);
  const subCropY = cropY + Math.floor((cropH - subCropH) / 2);

  return {
    scaleFactor: Math.round(scaleFactor * 1000000) / 1000000,
    scaledW,
    scaledH,
    scaled_w: scaledW,
    scaled_h: scaledH,
    cropOffsetX,
    cropOffsetY,
    offset_x: cropOffsetX,
    offset_y: cropOffsetY,
    canvasWidth,
    canvasHeight,
    canvas_w: canvasWidth,
    canvas_h: canvasHeight,
    sourceCrop: { x: cropX, y: cropY, w: cropW, h: cropH },
    sourceSubCrop: { x: subCropX, y: subCropY, w: subCropW, h: subCropH },
    ffmpegScaleFilter: `scale=${canvasWidth}:${canvasHeight}:force_original_aspect_ratio=increase,crop=${canvasWidth}:${canvasHeight}`,
    ffmpeg_scale_filter: `scale=${canvasWidth}:${canvasHeight}:force_original_aspect_ratio=increase,crop=${canvasWidth}:${canvasHeight}`,
  };
}

export function calculateGameplayFillFraming(
  gameplayRoi: NormalizedRect,
  srcW: number,
  srcH: number,
  canvasW: number = DEFAULT_CANVAS_WIDTH,
  canvasH: number = DEFAULT_CANVAS_HEIGHT
): FramingResult {
  const crop = toEvenPixels(gameplayRoi, srcW, srcH);
  return calculateGameplayFraming(crop, canvasW, canvasH);
}

/**
 * Validates a normalized rect, raising an Error with descriptive text matching golden vectors
 * if coordinates are non-finite, negative, out-of-bounds, or sub-minimum.
 */
export function validateNormalizedRect(
  rect: any,
  fieldName: string = 'rect',
  minSize: number = MIN_ROI_SIZE,
  eps: number = 1e-4
): NormalizedRect {
  if (!rect || typeof rect !== 'object') {
    throw new Error(`${fieldName} must be an object`);
  }

  const rawX = rect.x;
  const rawY = rect.y;
  const rawW = rect.width !== undefined ? rect.width : rect.w;
  const rawH = rect.height !== undefined ? rect.height : rect.h;

  for (const [val, prop] of [[rawX, 'x'], [rawY, 'y'], [rawW, 'width'], [rawH, 'height']] as const) {
    if (typeof val === 'string' && (val === 'NaN' || val === 'Infinity' || val === '-Infinity')) {
      throw new Error(`non-finite coordinate in ${fieldName}.${prop}: ${val}`);
    }
    if (typeof val !== 'number' || !Number.isFinite(val)) {
      throw new Error(`non-finite coordinate in ${fieldName}.${prop}: ${val}`);
    }
  }

  const x = Number(rawX);
  const y = Number(rawY);
  const width = Number(rawW);
  const height = Number(rawH);

  if (x < -eps || y < -eps) {
    throw new Error(`negative coordinate in ${fieldName}: x=${x}, y=${y}`);
  }

  if (width < minSize - eps) {
    throw new Error(`${fieldName}.width must be >= ${minSize}, got ${width}`);
  }
  if (height < minSize - eps) {
    throw new Error(`${fieldName}.height must be >= ${minSize}, got ${height}`);
  }

  if (x > 1.0 + eps || y > 1.0 + eps) {
    throw new Error(`coordinate out of bounds in ${fieldName}: x=${x}, y=${y} exceeds 1.0`);
  }

  if (x + width > 1.0 + eps || y + height > 1.0 + eps) {
    throw new Error(`${fieldName} out of bounds: x+width=${x + width}, y+height=${y + height} exceeds 1.0`);
  }

  const cleanX = Math.max(0.0, Math.min(1.0 - minSize, x));
  const cleanY = Math.max(0.0, Math.min(1.0 - minSize, y));
  const cleanW = Math.max(minSize, Math.min(1.0 - cleanX, width));
  const cleanH = Math.max(minSize, Math.min(1.0 - cleanY, height));

  const roundedX = Math.max(0, Math.round(cleanX * 1000000) / 1000000);
  const roundedY = Math.max(0, Math.round(cleanY * 1000000) / 1000000);
  const roundedW = Math.max(minSize, Math.round(Math.min(1.0 - roundedX, cleanW) * 1000000) / 1000000);
  const roundedH = Math.max(minSize, Math.round(Math.min(1.0 - roundedY, cleanH) * 1000000) / 1000000);

  return {
    x: roundedX,
    y: roundedY,
    width: roundedW,
    height: roundedH,
  };
}

/**
 * Validates complete gaming layout input configuration. Throws Error if invalid.
 */
export function validateGamingLayout(input: any): { is_valid: boolean; errors?: string[] } {
  if (!input || typeof input !== 'object') {
    throw new Error('Gaming layout input must be an object');
  }

  validateNormalizedRect(input.gameplay_roi, 'gameplay_roi');
  validateNormalizedRect(input.facecam_roi, 'facecam_roi');

  if (input.facecam_output_rect !== null && input.facecam_output_rect !== undefined) {
    validateNormalizedRect(input.facecam_output_rect, 'facecam_output_rect');
  }

  if (input.facecam_placement && input.facecam_placement !== 'custom') {
    getFacecamPreset(input.facecam_placement);
  }

  return { is_valid: true };
}

export function validateGamingCoordinates(input: any): { valid: boolean; errors: string[] } {
  try {
    validateGamingLayout(input);
    return { valid: true, errors: [] };
  } catch (err: any) {
    return { valid: false, errors: [err.message] };
  }
}

/**
 * Authoritative unified calculation function verifying exact parity against golden vectors.
 */
export function calculateGamingCoordinates(input: {
  src_w: number;
  src_h: number;
  canvas_w?: number;
  canvas_h?: number;
  gameplay_roi: any;
  facecam_roi: any;
  facecam_placement?: FacecamPreset | string | null;
  facecam_output_rect?: any | null;
}): GamingPlanResult {
  if (!input || typeof input !== 'object') {
    throw new Error('Gaming layout input must be an object');
  }

  const srcW = Number(input.src_w);
  const srcH = Number(input.src_h);
  if (!Number.isFinite(srcW) || !Number.isFinite(srcH) || srcW <= 0 || srcH <= 0) {
    throw new Error(`Source dimensions must be positive, got ${input.src_w}x${input.src_h}`);
  }

  const canvasW = input.canvas_w !== undefined ? Number(input.canvas_w) : DEFAULT_CANVAS_WIDTH;
  const canvasH = input.canvas_h !== undefined ? Number(input.canvas_h) : DEFAULT_CANVAS_HEIGHT;
  if (!Number.isFinite(canvasW) || !Number.isFinite(canvasH) || canvasW <= 0 || canvasH <= 0) {
    throw new Error(`Canvas dimensions must be positive, got ${canvasW}x${canvasH}`);
  }

  validateGamingLayout(input);

  const gameplayRoi = validateNormalizedRect(input.gameplay_roi, 'gameplay_roi');
  const facecamRoi = validateNormalizedRect(input.facecam_roi, 'facecam_roi');

  let resolvedFacecamOutputRect: NormalizedRect;
  if (input.facecam_output_rect !== null && input.facecam_output_rect !== undefined) {
    resolvedFacecamOutputRect = validateNormalizedRect(input.facecam_output_rect, 'facecam_output_rect');
  } else if (input.facecam_placement && input.facecam_placement !== 'custom') {
    resolvedFacecamOutputRect = getFacecamPreset(input.facecam_placement);
  } else {
    resolvedFacecamOutputRect = getFacecamPreset('top-right');
  }

  // 1. Gameplay Source Crop
  const gameplayCrop = toSourceCrop(gameplayRoi, srcW, srcH);
  const gcx = gameplayCrop.x;
  const gcy = gameplayCrop.y;
  const gcw = gameplayCrop.w;
  const gch = gameplayCrop.h;

  // 2. Facecam Source Crop
  const facecamCrop = toSourceCrop(facecamRoi, srcW, srcH);
  const fcx = facecamCrop.x;
  const fcy = facecamCrop.y;
  const fcw = facecamCrop.w;
  const fch = facecamCrop.h;

  // 3. Facecam Canvas Destination
  const facecamDest = toCanvasOverlay(resolvedFacecamOutputRect, canvasW, canvasH);
  const destX = facecamDest.x;
  const destY = facecamDest.y;
  const destW = facecamDest.w;
  const destH = facecamDest.h;

  // 4. Gameplay scale-to-fill metrics
  const scaleFactor = Math.max(canvasW / gcw, canvasH / gch);
  const scaledW = Math.round(gcw * scaleFactor);
  const scaledH = Math.round(gch * scaleFactor);

  // 5. FFmpeg strings
  const ffmpegCropGameplay = `crop=${gcw}:${gch}:${gcx}:${gcy}`;
  const ffmpegCropFacecam = `crop=${fcw}:${fch}:${fcx}:${fcy}`;
  const ffmpegFiltergraph =
    `[0:v]crop=${gcw}:${gch}:${gcx}:${gcy},scale=${canvasW}:${canvasH}:force_original_aspect_ratio=increase,crop=${canvasW}:${canvasH}[v0];` +
    `[1:v]crop=${fcw}:${fch}:${fcx}:${fcy},scale=${destW}:${destH}:force_original_aspect_ratio=increase,crop=${destW}:${destH}[v1];` +
    `[v0][v1]overlay=x=${destX}:y=${destY}:eof_action=pass:repeatlast=0,setsar=1[outv]`;

  return {
    is_valid: true,
    facecam_resolved_output_rect: resolvedFacecamOutputRect,
    gameplay_crop: gameplayCrop,
    facecam_crop: facecamCrop,
    facecam_dest: facecamDest,
    canvas_width: canvasW,
    canvas_height: canvasH,
    gameplay_scale_factor: Math.round(scaleFactor * 1000000) / 1000000,
    gameplay_scaled_w: scaledW,
    gameplay_scaled_h: scaledH,
    ffmpeg_crop_gameplay: ffmpegCropGameplay,
    ffmpeg_crop_facecam: ffmpegCropFacecam,
    ffmpeg_filtergraph: ffmpegFiltergraph,
  };
}
