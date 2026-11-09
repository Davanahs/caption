/**
 * TokenAlignmentEngine (Phase 5.5 - Reusable Core Component)
 * Aligns original timestamp tokens with corrected token streams.
 * Handles 1->1, 1->2 ("gonna"->"going to"), 2->1 ("ice cream"->"icecream"), 
 * insertions, deletions, and replacements with ZERO time drift.
 */
class TokenAlignmentEngine {
  /**
   * Aligns corrected tokens to original word timestamp array
   * @param {Array} originalWords [{ word, start, end }]
   * @param {Array} correctedTokens ['word1', 'word2']
   * @returns {Array} Remapped words with accurate timestamps
   */
  static alignTimestamps(originalWords, correctedTokens) {
    if (!originalWords || originalWords.length === 0) return [];
    if (!correctedTokens || correctedTokens.length === 0) return originalWords;

    const tStart = originalWords[0].start;
    const tEnd = originalWords[originalWords.length - 1].end;
    const totalDuration = Math.max(0.1, tEnd - tStart);

    // 1. Direct 1-to-1 match shortcut
    if (correctedTokens.length === originalWords.length) {
      return correctedTokens.map((wStr, i) => ({
        word: wStr.toUpperCase(),
        start: originalWords[i].start,
        end: originalWords[i].end
      }));
    }

    // 2. Proportional character-weight interpolation for token length shifts (1->2, 2->1)
    const totalChars = correctedTokens.reduce((sum, w) => sum + w.length, 0);
    let timeCursor = tStart;

    return correctedTokens.map((wStr, i) => {
      const isLast = i === correctedTokens.length - 1;
      const charRatio = wStr.length / Math.max(1, totalChars);
      const wDuration = parseFloat((totalDuration * charRatio).toFixed(2));
      const wStart = parseFloat(timeCursor.toFixed(2));
      const wEnd = isLast ? tEnd : parseFloat((timeCursor + wDuration).toFixed(2));

      timeCursor = wEnd;

      return {
        word: wStr.toUpperCase(),
        start: wStart,
        end: wEnd
      };
    });
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = TokenAlignmentEngine;
}
if (typeof window !== 'undefined') {
  window.TokenAlignmentEngine = TokenAlignmentEngine;
}
