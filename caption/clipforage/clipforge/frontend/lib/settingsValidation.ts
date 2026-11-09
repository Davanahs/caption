/**
 * Settings numeric validation logic for Clips limit and Channel check interval.
 * Disallows falsy-zero coercion, silent clamping, and out-of-range/negative numbers.
 */

export interface NumericSettingsValidationResult {
  clipsError?: string;
  intervalError?: string;
  parsedClips?: number;
  parsedInterval?: number;
}

export function validateNumericSettings(clips: any, interval: any): NumericSettingsValidationResult {
  let clipsError: string | undefined;
  let intervalError: string | undefined;

  const clipsStr = String(clips ?? '').trim();
  if (clipsStr === '') {
    clipsError = 'Clips limit per video is required.';
  } else {
    const n = Number(clipsStr);
    if (isNaN(n) || !Number.isInteger(n)) {
      clipsError = 'Clips limit must be a whole integer between 1 and 20.';
    } else if (n < 1 || n > 20) {
      clipsError = `Clips limit must be between 1 and 20 (got ${n}).`;
    }
  }

  const intervalStr = String(interval ?? '').trim();
  if (intervalStr === '') {
    intervalError = 'Channel check interval is required.';
  } else {
    const n = Number(intervalStr);
    if (isNaN(n) || !Number.isInteger(n)) {
      intervalError = 'Channel check interval must be a whole integer between 5 and 1440.';
    } else if (n < 5 || n > 1440) {
      intervalError = `Channel check interval must be between 5 and 1440 minutes (got ${n}).`;
    }
  }

  return {
    clipsError,
    intervalError,
    parsedClips: !clipsError ? Number(clipsStr) : undefined,
    parsedInterval: !intervalError ? Number(intervalStr) : undefined,
  };
}
