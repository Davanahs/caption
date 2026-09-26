/**
 * LocalAccuracyEngine (Phase 5 - 100% Offline Correction Engine)
 * Level 1: Safe spelling corrections
 * Level 2: High-confidence contextual homophones
 * Level 3: Optional local offline model hook (SmolLM2-135M)
 */
class LocalAccuracyEngine {
  // Level 1: Deterministic Spelling Dictionary
  static SPELLING_DICT = {
    'teh': 'the',
    'recieve': 'receive',
    'definately': 'definitely',
    'seperate': 'separate',
    'truely': 'truly',
    'occured': 'occurred',
    'untill': 'until',
    'gonna': 'going to',
    'wanna': 'want to',
    'gotta': 'got to'
  };

  /**
   * Performs Level 1 & Level 2 local offline corrections
   * @param {string} text 
   * @returns {string} Corrected text
   */
  static correctText(text) {
    if (!text || typeof text !== 'string') return '';

    let tokens = text.trim().split(/\s+/);

    // Level 1: Spelling corrections
    tokens = tokens.map(t => {
      const clean = t.toLowerCase().replace(/[^a-z]/g, '');
      if (this.SPELLING_DICT[clean]) {
        const replacement = this.SPELLING_DICT[clean];
        if (t[0] === t[0].toUpperCase()) {
          return replacement.charAt(0).toUpperCase() + replacement.slice(1);
        }
        return replacement;
      }
      return t;
    });

    let correctedText = tokens.join(' ');

    // Level 2: Contextual Homophones Rules
    correctedText = correctedText
      .replace(/\btheir\s+(going|doing|coming|making|building|ready|working)\b/gi, "they're $1")
      .replace(/\bthere\s+(car|house|money|revenue|business|project)\b/gi, "their $1")
      .replace(/\byour\s+(right|welcome|going|doing|coming)\b/gi, "you're $1")
      .replace(/\bits\s+(time|going|ready|important)\b/gi, "it's $1")
      .replace(/\bmore\s+then\b/gi, "more than")
      .replace(/\bto\s+much\b/gi, "too much");

    return correctedText;
  }

  /**
   * Corrects caption blocks using Local Accuracy Engine + TokenAlignmentEngine
   * @param {Array} blocks 
   * @returns {Array} Corrected blocks with remapped timestamps
   */
  static processBlocks(blocks) {
    if (!blocks || !Array.isArray(blocks)) return [];

    const TokenAlignment = (typeof window !== 'undefined' ? window.TokenAlignmentEngine : null) || 
                           (typeof module !== 'undefined' ? require('./alignment.js') : null);

    return blocks.map(block => {
      const originalText = block.text || '';
      const correctedText = this.correctText(originalText);
      const correctedTokens = correctedText.split(/\s+/).filter(t => t.length > 0);

      const remappedWords = TokenAlignment 
        ? TokenAlignment.alignTimestamps(block.words || [], correctedTokens)
        : block.words;

      return {
        ...block,
        text: remappedWords.map(w => w.word).join(' '),
        words: remappedWords
      };
    });
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = LocalAccuracyEngine;
}
if (typeof window !== 'undefined') {
  window.LocalAccuracyEngine = LocalAccuracyEngine;
}
