/**
 * Text Normalizer Module (Phase 1 - Step 2 Upgrade)
 * Trims excess whitespace, fixes casing, normalizes contractions & cleans punctuation.
 */
class TextNormalizer {
  /**
   * Normalizes raw user or transcript text
   * @param {string} rawText 
   * @returns {string} Cleaned text
   */
  static normalize(rawText) {
    if (!rawText || typeof rawText !== 'string') return '';

    let text = rawText
      // Replace multiple horizontal spaces with a single space
      .replace(/[ \t]+/g, ' ')
      // Normalize consecutive line breaks (max 2)
      .replace(/\n\s*\n/g, '\n\n')
      // Remove spaces before punctuation (e.g. "word ," -> "word,")
      .replace(/\s+([,.!?:;])/g, '$1')
      // Remove isolated dangling punctuation marks (e.g. " word . " -> " word ")
      .replace(/(^|\s)[,.!?:;]+(?=\s|$)/g, ' ')
      // Normalize repeated punctuation (except ellipsis ...)
      .replace(/([,.!?:;])\1+/g, (match, p1) => match === '...' ? match : p1)
      .trim();

    // Casing and contraction lookup
    const wordReplacements = {
      'i': 'I',
      "i'm": "I'm",
      "i'll": "I'll",
      "i've": "I've",
      "i'd": "I'd",
      'im': "I'm",
      'ive': "I've",
      'dont': "don't",
      'cant': "can't",
      'wont': "won't",
      'doesnt': "doesn't",
      'didnt': "didn't",
      'isnt': "isn't",
      'arent': "aren't",
      'wasnt': "wasn't",
      'werent': "weren't",
      'hasnt': "hasn't",
      'havent': "haven't",
      'hadnt': "hadn't",
      'couldnt': "couldn't",
      'wouldnt': "wouldn't",
      'shouldnt': "shouldn't",
      'youre': "you're",
      'theyre': "they're",
      'weve': "we've",
      'whats': "what's",
      'thats': "that's",
      'theres': "there's",
      'heres': "here's"
    };

    text = text.replace(/\b[a-zA-Z']+\b/g, (w) => {
      const lower = w.toLowerCase();
      if (wordReplacements[lower]) {
        if (w[0] === w[0].toUpperCase() && w.length > 1 && lower !== 'i') {
          const rep = wordReplacements[lower];
          return rep.charAt(0).toUpperCase() + rep.slice(1);
        }
        return wordReplacements[lower];
      }
      return w;
    });

    return text.replace(/[ \t]+/g, ' ').trim();
  }
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = TextNormalizer;
}
if (typeof window !== 'undefined') {
  window.TextNormalizer = TextNormalizer;
}
