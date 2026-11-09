/**
 * Text Segmenter Engine (Phase 1 Upgrade — Human Break Scoring Engine)
 * BreakScore = PauseScore + PunctuationScore + PhraseBoundaryScore + ReadabilityScore - AwkwardBreakPenalty
 */
class TextSegmenter {
  static CONJUNCTIONS = new Set(['and', 'but', 'so', 'because', 'or', 'when', 'if', 'while', 'although', 'since', 'then', 'where', 'as', 'than']);
  static PREPOSITIONS = new Set(['in', 'on', 'at', 'to', 'for', 'with', 'from', 'by', 'about', 'into', 'through', 'over', 'under', 'between', 'during', 'without']);
  static ARTICLES_PRONOUNS = new Set(['a', 'an', 'the', 'my', 'your', 'his', 'her', 'our', 'their', 'this', 'that', 'these', 'those', 'its']);
  static AUXILIARY_VERBS = new Set(['is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might', 'must']);

  /**
   * Calculates natural human break score for splitting after currentWord
   */
  static calculateBreakScore(currentWord, nextWord, currentBlockWordCount, currentBlockCharLen, pauseAfterSeconds = 0, maxWords = 4, maxChars = 24) {
    if (!currentWord) return 0;
    if (!nextWord) return 100;

    let score = 0;

    // 1. Pause score
    if (pauseAfterSeconds >= 0.35) score += 50;
    else if (pauseAfterSeconds >= 0.2) score += 25;

    // 2. Punctuation score
    if (/[.!?]$/.test(currentWord)) score += 60;
    else if (/[,:;\-]$/.test(currentWord)) score += 35;

    // 3. Phrase boundary score
    const cleanCurrent = currentWord.toLowerCase().replace(/[^a-z]/g, '');
    const cleanNext = nextWord.toLowerCase().replace(/[^a-z]/g, '');

    if (this.CONJUNCTIONS.has(cleanNext) && currentBlockWordCount >= 2) {
      score += 30;
    }
    if (this.PREPOSITIONS.has(cleanNext) && currentBlockWordCount >= 2 && currentBlockCharLen >= 10) {
      score += 25;
    }

    // 4. Readability score (char length & word count limits)
    const nextWordLen = nextWord.length;
    const projectCharLen = currentBlockCharLen + 1 + nextWordLen;

    if (projectCharLen > maxChars && currentBlockWordCount >= 1) {
      score += 45;
    }
    if (currentBlockWordCount >= maxWords) {
      score += 40;
    }

    // 5. Awkward break penalty
    if (this.ARTICLES_PRONOUNS.has(cleanCurrent)) {
      score -= 35;
    }
    if (this.AUXILIARY_VERBS.has(cleanCurrent) && currentBlockWordCount === 1) {
      score -= 20;
    }

    return score;
  }

  /**
   * Splits normalized text into structured caption blocks with calculated timestamps
   * @param {string} normalizedText 
   * @param {Object} options { maxWords: 4, maxChars: 24, wpm: 180, styleId: 'lightning-comic' }
   * @returns {Object} Unified Caption JSON
   */
  static segment(normalizedText, options = {}) {
    const maxWords = options.maxWords || 4;
    const maxChars = options.maxChars || 24;
    const wpm = options.wpm || 180;
    const styleId = options.styleId || 'lightning-comic';

    if (!normalizedText || normalizedText.trim().length === 0) {
      return { version: '2.0', styleId, blocks: [] };
    }

    const rawWords = normalizedText.split(/\s+/).filter(w => w.length > 0);
    const blocks = [];

    let currentBlockWords = [];
    let currentBlockCharLen = 0;
    let currentTimeCursor = 0.0;
    const secondsPerWord = 60 / wpm;

    for (let i = 0; i < rawWords.length; i++) {
      const wordStr = rawWords[i];
      const nextWordStr = i < rawWords.length - 1 ? rawWords[i + 1] : null;

      currentBlockWords.push(wordStr);
      currentBlockCharLen += (currentBlockCharLen > 0 ? 1 : 0) + wordStr.length;

      const isLastWord = i === rawWords.length - 1;
      const breakScore = this.calculateBreakScore(wordStr, nextWordStr, currentBlockWords.length, currentBlockCharLen, 0, maxWords, maxChars);

      const split = isLastWord || (breakScore >= 40);

      if (split) {
        const blockStart = parseFloat(currentTimeCursor.toFixed(2));
        const wordTimings = [];
        let wordTimeCursor = blockStart;

        for (const w of currentBlockWords) {
          const isPunct = /[.!?]$/.test(w);
          const isClause = /[,:;\-]$/.test(w);
          const duration = isPunct ? secondsPerWord * 1.35 : (isClause ? secondsPerWord * 1.15 : secondsPerWord);
          const wStart = parseFloat(wordTimeCursor.toFixed(2));
          const wEnd = parseFloat((wordTimeCursor + duration).toFixed(2));

          wordTimings.push({
            word: w.toUpperCase(),
            start: wStart,
            end: wEnd
          });

          wordTimeCursor = wEnd;
        }

        const blockEnd = parseFloat(wordTimeCursor.toFixed(2));
        const blockText = currentBlockWords.join(' ').toUpperCase();

        blocks.push({
          id: `block_${String(blocks.length + 1).padStart(3, '0')}`,
          text: blockText,
          start: blockStart,
          end: blockEnd,
          words: wordTimings
        });

        currentTimeCursor = blockEnd;
        currentBlockWords = [];
        currentBlockCharLen = 0;
      }
    }

    return {
      version: '2.0',
      styleId,
      blocks
    };
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = TextSegmenter;
}
if (typeof window !== 'undefined') {
  window.TextSegmenter = TextSegmenter;
}
