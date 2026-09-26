/**
 * Local Caption Director Engine (Phase 2 - 100% Offline Rule Engine)
 * Replaces LLM API calls with high-performance local keyword, currency, regex, 
 * emoji, SFX, and color classifier engines.
 */
class LocalCaptionDirector {
  static CURRENCY_REGEX = /[₹$€£]\d+|\b(rs|inr|usd|dollars|rupees)\b/i;

  static MONEY_TERMS = new Set([
    'money', 'cash', 'salary', 'profit', 'income', 'revenue', 'cost', 'price',
    'million', 'billion', 'lakh', 'lakhs', 'crore', 'crores', 'amount', 'pay', 'paid'
  ]);

  static WARNING_TERMS = new Set([
    'warning', 'danger', 'mistake', 'avoid', 'risk', 'problem', 'error', 'careful',
    "don't", 'dont', 'never', 'stop', 'scam', 'bad', 'trap', 'fail', 'failed'
  ]);

  static SUCCESS_TERMS = new Set([
    'win', 'won', 'success', 'achieved', 'growth', 'completed', 'result',
    'viral', 'secret', 'best', 'pro', 'great', 'profit', 'scale', 'easy'
  ]);

  static QUESTION_TERMS = new Set([
    'why', 'how', 'what', 'when', 'where', 'who', 'which'
  ]);

  static EMOJI_MAP = {
    money: '💰',
    currency: '💵',
    warning: '⚠️',
    success: '🏆',
    question: '❓',
    fire: '🔥',
    ai: '🤖',
    rocket: '🚀',
    time: '⏱️',
    video: '🎬'
  };

  /**
   * Annotates caption blocks with director tags (colorTag, emoji, sfx, emphasisWords)
   * @param {Array} blocks 
   * @returns {Array} Annotated blocks
   */
  static annotate(blocks) {
    if (!blocks || !Array.isArray(blocks)) return [];

    return blocks.map((block, idx) => {
      const text = block.text || '';
      const textLower = text.toLowerCase();
      const words = block.words || [];

      let colorTag = 'neutral';
      let emoji = null;
      let sfx = null;
      const emphasisWords = [];

      // 1. Currency & Money Engine
      const hasCurrency = this.CURRENCY_REGEX.test(text);
      const cleanTokens = textLower.split(/\s+/).map(t => t.replace(/[^a-z]/g, ''));
      const hasMoneyWord = cleanTokens.some(t => this.MONEY_TERMS.has(t));

      if (hasCurrency || hasMoneyWord) {
        colorTag = 'money';
        emoji = '💰';
        sfx = 'cash';
      }
      // 2. Warning Engine
      else if (cleanTokens.some(t => this.WARNING_TERMS.has(t))) {
        colorTag = 'warning';
        emoji = '⚠️';
        sfx = 'boom';
      }
      // 3. Question Engine
      else if (text.includes('?') || cleanTokens.some(t => this.QUESTION_TERMS.has(t))) {
        colorTag = 'question';
        emoji = '❓';
        sfx = 'ding';
      }
      // 4. Success / Highlight Engine
      else if (cleanTokens.some(t => this.SUCCESS_TERMS.has(t))) {
        colorTag = 'success';
        emoji = '🏆';
        sfx = 'pop';
      }

      // 5. Emphasis Word & Number Detector
      const annotatedWords = words.map(w => {
        const wordText = w.word || '';
        const cleanW = wordText.replace(/[^A-Za-z0-9₹$€£]/g, '');

        const isNumberOrCurrency = /[₹$€£]|\d+/.test(wordText);
        const isPowerWord = ['MISTAKE', 'STOP', 'NEVER', 'VIRAL', 'BEST', 'SECRET', 'WIN', 'PROFIT'].includes(cleanW.toUpperCase());
        const isEmph = isNumberOrCurrency || isPowerWord || cleanW.length >= 8;

        if (isEmph) {
          emphasisWords.push(wordText);
        }

        return {
          ...w,
          isEmphasis: isEmph
        };
      });

      // Distribute contextual emojis naturally (~15% of blocks)
      if (!emoji && (idx % 5 === 0)) {
        if (textLower.includes('ai') || textLower.includes('robot')) emoji = '🤖';
        else if (textLower.includes('fast') || textLower.includes('speed')) emoji = '⚡';
      }

      return {
        ...block,
        colorTag,
        emoji: emoji || null,
        sfx: sfx || null,
        emphasisWords,
        words: annotatedWords
      };
    });
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = LocalCaptionDirector;
}
if (typeof window !== 'undefined') {
  window.LocalCaptionDirector = LocalCaptionDirector;
}
