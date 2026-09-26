/**
 * Unified CutMap Engine (Phase 4)
 * Generates a single unified edit cut map [[start, end]] and applies it 
 * synchronously across Audio, Video, and Caption Timestamps.
 */
class UnifiedCutMapEngine {
  static FILLER_REGEX = /\b(um|uh|er|ahm|hmm|like|you know|so basically)\b/i;

  /**
   * Generates a CutMap array [[start1, end1], [start2, end2]] from silence gaps & filler words
   * @param {Array} blocks 
   * @param {Object} options { silenceThreshold: 0.5, removeFillers: true }
   * @returns {Object} { cutMap, totalTimeSaved }
   */
  static generateCutMap(blocks, options = {}) {
    const silenceThreshold = options.silenceThreshold || 0.5;
    const removeFillers = options.removeFillers !== false;

    const cuts = [];
    const allWords = [];
    blocks.forEach(b => (b.words || []).forEach(w => allWords.push(w)));

    // 1. Detect filler word cuts
    if (removeFillers) {
      allWords.forEach(w => {
        if (this.FILLER_REGEX.test(w.word.trim())) {
          cuts.push([w.start, w.end]);
        }
      });
    }

    // 2. Detect silence gap cuts
    for (let i = 0; i < allWords.length - 1; i++) {
      const curr = allWords[i];
      const next = allWords[i + 1];
      const gap = next.start - curr.end;
      if (gap >= silenceThreshold) {
        cuts.push([curr.end, next.start]);
      }
    }

    // Sort & merge overlapping cut intervals
    cuts.sort((a, b) => a[0] - b[0]);
    const mergedCuts = [];

    for (const cut of cuts) {
      if (mergedCuts.length === 0) {
        mergedCuts.push([...cut]);
      } else {
        const last = mergedCuts[mergedCuts.length - 1];
        if (cut[0] <= last[1]) {
          last[1] = Math.max(last[1], cut[1]);
        } else {
          mergedCuts.push([...cut]);
        }
      }
    }

    let totalTimeSaved = 0;
    mergedCuts.forEach(c => {
      totalTimeSaved += (c[1] - c[0]);
    });

    return {
      cutMap: mergedCuts,
      totalTimeSavedSeconds: parseFloat(totalTimeSaved.toFixed(2))
    };
  }

  /**
   * Applies CutMap to shift caption timestamps matching the cuts
   * @param {Array} blocks 
   * @param {Array} cutMap 
   * @returns {Array} Cleaned blocks with shifted timestamps
   */
  static applyCutMapToCaptions(blocks, cutMap) {
    if (!cutMap || cutMap.length === 0) return blocks;

    const shiftTime = (t) => {
      let shift = 0;
      for (const [cStart, cEnd] of cutMap) {
        if (t >= cEnd) {
          shift += (cEnd - cStart);
        } else if (t > cStart && t < cEnd) {
          shift += (t - cStart);
        }
      }
      return parseFloat(Math.max(0, t - shift).toFixed(2));
    };

    const cleanedBlocks = [];

    blocks.forEach(block => {
      const originalWords = block.words || [];
      const keptWords = [];

      originalWords.forEach(w => {
        // Check if word falls completely inside a cut
        const isCutOut = cutMap.some(([cS, cE]) => w.start >= cS && w.end <= cE);
        if (!isCutOut) {
          keptWords.push({
            ...w,
            start: shiftTime(w.start),
            end: shiftTime(w.end)
          });
        }
      });

      if (keptWords.length > 0) {
        cleanedBlocks.push({
          ...block,
          id: `block_${String(cleanedBlocks.length + 1).padStart(3, '0')}`,
          text: keptWords.map(w => w.word).join(' '),
          start: keptWords[0].start,
          end: keptWords[keptWords.length - 1].end,
          words: keptWords
        });
      }
    });

    return cleanedBlocks;
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = UnifiedCutMapEngine;
}
if (typeof window !== 'undefined') {
  window.UnifiedCutMapEngine = UnifiedCutMapEngine;
}
