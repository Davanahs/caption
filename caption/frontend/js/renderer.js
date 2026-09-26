/**
 * Custom Canvas Renderer Engine (Phase 3 Upgrade - CapCut / Submagic / MrBeast Quality)
 * Ultra-Clean Submagic / CapCut Viral Aesthetic:
 *   - 100% Unobstructed Video Stream (Zero heavy dark background boxes).
 *   - Smart 1-2 Line Text Stacking & Word Wrapping.
 *   - Tight, vibrant active word sticker chips mapped to colorTag.
 *   - Universal high-contrast stroke outline & dark drop shadow.
 *   - Anchored floating emojis beside active keywords.
 *   - Decoupled SKINS & ANIMATIONS architecture.
 *   - Dynamic offscreen canvas preset thumbnail generator.
 */

const SKINS = {
  prettygirl: {
    id: 'prettygirl',
    name: 'Pretty Pretty Girl',
    font: "'Shrikhand', 'Abril Fatface', 'Bangers', cursive, serif",
    fontSize: 92,
    textColor: '#FFFFFF',
    contextAlpha: 0.90,
    activeTextColor: '#FFFFFF',
    chipBg: '#000000',
    chipPadding: { x: 26, y: 14 },
    chipRadius: 18,
    strokeColor: '#000000',
    strokeWidthPct: 0.04
  },
  fitcheck: {
    id: 'fitcheck',
    name: 'Fit Check Glitch',
    font: "'Montserrat', 'Outfit', sans-serif",
    fontStyle: 'italic',
    fontSize: 88,
    textColor: '#FF2A6D', // Vibrant Coral Pink
    contextAlpha: 0.85,
    activeTextColor: '#FF2A6D',
    glitchColor: '#00F0FF', // Cyan 3D Glitch Offset
    chipBg: '#FFFFFF', // White Sticker Outline Pill
    strokeColor: '#FFFFFF',
    strokeWidthPct: 0.12
  },
  ransomnote: {
    id: 'ransomnote',
    name: 'Newspaper Ransom Cutout',
    font: "'Abril Fatface', 'Montserrat', 'JetBrains Mono', serif",
    fontSize: 88,
    textColor: '#111111',
    contextAlpha: 0.95,
    activeTextColor: '#FFFFFF',
    chipBg: '#F3EFE0',
    strokeColor: '#000000',
    strokeWidthPct: 0.02
  },
  minimalscript: {
    id: 'minimalscript',
    name: 'Minimalist Script Overlay',
    font: "'Montserrat', 'Inter', sans-serif",
    scriptFont: "'Great Vibes', 'Dancing Script', 'Pacifico', cursive",
    fontSize: 84,
    textColor: '#FFFFFF',
    contextAlpha: 0.85,
    activeTextColor: '#FFFFFF',
    strokeColor: '#000000',
    strokeWidthPct: 0.04
  },
  script: {
    id: 'script',
    name: 'Script Elegance',
    font: "'Caveat', 'Pacifico', 'Dancing Script', cursive",
    fontSize: 98,
    textColor: '#FFFDF5',
    contextAlpha: 0.80,
    activeTextColor: '#2A1810',
    chipBg: '#FFF3E0', // Warm cream chip
    chipPadding: { x: 24, y: 12 },
    chipRadius: 12,
    strokeColor: '#3D2314', // Deep brown stroke
    strokeWidthPct: 0.07,
    flourish: true
  },
  retro: {
    id: 'retro',
    name: 'Neon Cyber',
    font: "'Orbitron', 'Audiowide', sans-serif",
    fontSize: 82,
    textColor: '#FFFFFF',
    contextAlpha: 0.80,
    activeTextColor: '#00F0FF', // Neon Cyan
    secondaryGlowColor: '#FF2E9A', // Dual Pink Glow
    strokeColor: '#06040C',
    strokeWidthPct: 0.08
  }
};

const PRESETS = {
  'pretty-pretty-girl': { skin: 'prettygirl', animation: 'prettyGirlRetro' },
  'fit-check': { skin: 'fitcheck', animation: 'fitCheckGlitch' },
  'ransom-note': { skin: 'ransomnote', animation: 'ransomNoteCutout' },
  'minimal-script': { skin: 'minimalscript', animation: 'minimalScriptHybrid' },
  'create-every-day': { skin: 'script', animation: 'scriptElegance' },
  'retro-triangle': { skin: 'retro', animation: 'neonGlow' }
};

class LightningComicRenderer {
  constructor(canvasElement, overlayContainer) {
    this.canvas = canvasElement;
    this.ctx = canvasElement.getContext('2d');
    this.overlay = overlayContainer;
    
    // Canvas Native Resolution (Vertical 1080x1920)
    this.width = 1080;
    this.height = 1920;
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    
    // Legacy theme compatibility object
    this.theme = {
      fontComic: "'Anton', 'Archivo Black', sans-serif",
      fontLeafy: "'Quicksand', 'Poppins', sans-serif",
      fontRetro: "'Orbitron', 'Audiowide', sans-serif",
      fontSize: 84,
      textColor: '#FFF5E1', 
      activeTextColor: '#FFFFFF',
      badgeBg: '#1B1233', 
      innerStrokeColor: '#FFFFFF', 
      outerStrokeColor: '#8B5CF6', 
      activeWordHighlight: '#FFE600', 
      skewAngle: -6 * (Math.PI / 180)
    };

    // Color Tag Palette Registry
    this.COLOR_PALETTES = {
      money: '#22C55E',     // Emerald Green
      warning: '#EF4444',   // Bright Red
      highlight: '#EAB308', // Radiant Yellow
      question: '#3B82F6',  // Vivid Blue
      neutral: '#FFE600'    // Default Neon Yellow
    };
  }

  getWordHighlightColor(w, blockColorTag) {
    if (w && w.colorOverride) return w.colorOverride;
    if (blockColorTag && this.COLOR_PALETTES[blockColorTag]) {
      return this.COLOR_PALETTES[blockColorTag];
    }
    if (w && w.isEmphasis) return '#FFE600';
    return '#FFE600';
  }

  /**
   * Helper: Draw rounded rectangular sticker chip behind active words with crisp black outline
   */
  drawWordChip(ctx, x, y, width, height, radius, fillColor, rotationDeg = 0) {
    ctx.save();
    ctx.translate(x, y);
    if (rotationDeg !== 0) ctx.rotate((rotationDeg * Math.PI) / 180);

    const halfW = width / 2;
    const halfH = height / 2;
    const r = Math.min(radius, halfW, halfH);

    ctx.beginPath();
    if (typeof ctx.roundRect === 'function') {
      ctx.roundRect(-halfW, -halfH, width, height, r);
    } else if (typeof ctx.arcTo === 'function') {
      ctx.moveTo(-halfW + r, -halfH);
      ctx.lineTo(halfW - r, -halfH);
      ctx.arcTo(halfW, -halfH, halfW, -halfH + r, r);
      ctx.lineTo(halfW, halfH - r);
      ctx.arcTo(halfW, halfH, halfW - r, halfH, r);
      ctx.lineTo(-halfW + r, halfH);
      ctx.arcTo(-halfW, halfH, -halfW, halfH - r, r);
      ctx.lineTo(-halfW, -halfH + r);
      ctx.arcTo(-halfW, -halfH, -halfW + r, -halfH, r);
    } else {
      ctx.rect(-halfW, -halfH, width, height);
    }
    ctx.closePath();

    // Fill Chip
    ctx.fillStyle = fillColor;
    ctx.fill();

    // Solid Black Stroke Contour around Chip
    ctx.lineWidth = 5;
    ctx.strokeStyle = '#000000';
    ctx.stroke();

    ctx.restore();
  }

  /**
   * Helper: Faked cheap offset drop shadow for context words (GPU optimized)
   */
  drawWordTextWithCheapShadow(ctx, wordText, x, y, strokeWidth, strokeColor, fillColor, shadowOffsetX = 3, shadowOffsetY = 4, shadowColor = 'rgba(0,0,0,0.85)') {
    ctx.save();
    // Pass 1: Dark offset shadow
    ctx.lineWidth = strokeWidth;
    ctx.strokeStyle = shadowColor;
    ctx.fillStyle = shadowColor;
    ctx.strokeText(wordText, x + shadowOffsetX, y + shadowOffsetY);
    ctx.fillText(wordText, x + shadowOffsetX, y + shadowOffsetY);

    // Pass 2: Main crisp stroke & fill
    ctx.strokeStyle = strokeColor;
    ctx.fillStyle = fillColor;
    ctx.strokeText(wordText, x, y);
    ctx.fillText(wordText, x, y);
    ctx.restore();
  }

  /**
   * Auto-fit font size so lines fit safe canvas width
   */
  fitFontSize(ctx, fontTemplate, text, maxPx, startSize = 96, minSize = 32) {
    let size = startSize;
    while (size > minSize) {
      ctx.font = fontTemplate.replace('{SIZE}', size);
      if (ctx.measureText(text).width <= maxPx) break;
      size -= 2;
    }
    return size;
  }

  /**
   * Main render call
   */
  render(captionData, currentTimeSeconds = 0) {
    this.ctx.clearRect(0, 0, this.width, this.height);
    
    if (!captionData || !captionData.blocks || captionData.blocks.length === 0) {
      this.drawPlaceholder();
      return null;
    }

    const activeBlock = captionData.blocks.find(
      b => currentTimeSeconds >= b.start && currentTimeSeconds <= b.end
    ) || captionData.blocks[0];

    if (!activeBlock) return null;

    const styleId = captionData.styleId || 'pretty-pretty-girl';
    const layout = captionData.layout || { x: 0.5, y: 0.52, scale: 1.0, rotation: 0 };

    // Camera Zoom Cut Engine on emphasis blocks
    const isEmphasisBlock = activeBlock.colorTag && activeBlock.colorTag !== 'neutral';
    this.ctx.save();
    if (isEmphasisBlock) {
      this.ctx.translate(this.width / 2, this.height / 2);
      this.ctx.scale(1.08, 1.08);
      this.ctx.translate(-this.width / 2, -this.height / 2);
    }

    // 1. Draw Background Environment (100% transparent in live preview)
    this.drawBackgroundEnvironment(styleId);

    // 2. Resolve Preset & Skin
    const presetConfig = PRESETS[styleId] || PRESETS['pretty-pretty-girl'];
    const skin = SKINS[presetConfig.skin] || SKINS.prettygirl;
    const animType = presetConfig.animation || 'prettyGirlRetro';

    // 3. Render Block using animation & skin
    const boxMeta = this.renderFullBlock(activeBlock, currentTimeSeconds, layout, skin, animType, styleId);

    this.ctx.restore();

    // 4. Draw Custom Canva Elements (Stickers)
    if (captionData.elements && captionData.elements.length > 0) {
      captionData.elements.forEach(el => {
        this.drawStickerElement(this.ctx, el, currentTimeSeconds);
      });
    }

    // 5. Return bounding box for Canva handle
    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId && selectedId.startsWith('el_') && captionData.elements) {
      const selectedEl = captionData.elements.find(e => e.id === selectedId);
      if (selectedEl) {
        return {
          normX: selectedEl.x,
          normY: selectedEl.y,
          widthPx: 120 * selectedEl.scale,
          heightPx: 120 * selectedEl.scale,
          scale: selectedEl.scale,
          rotation: selectedEl.rotation || 0
        };
      }
    }

    return boxMeta;
  }

  drawPlaceholder() {
    const ctx = this.ctx;
    ctx.save();
    ctx.fillStyle = '#0F091F';
    ctx.fillRect(0, 0, this.width, this.height);
    ctx.font = `600 36px 'Outfit', sans-serif`;
    ctx.fillStyle = 'rgba(255, 255, 255, 0.4)';
    ctx.textAlign = 'center';
    ctx.fillText('⚡ CAPTION FORGE PREVIEW', this.width / 2, this.height / 2);
    ctx.restore();
  }

  drawBackgroundEnvironment(styleId) {
    // 100% Clean video stream — zero dark background fills or paint splatters
  }

  /**
   * Split words into 1-2 balanced lines if word count > 3
   */
  splitWordsIntoLines(words, maxWordsPerLine = 3) {
    if (!words || words.length === 0) return [];
    if (words.length <= maxWordsPerLine) return [words];

    const lines = [];
    const mid = Math.ceil(words.length / 2);
    lines.push(words.slice(0, mid));
    lines.push(words.slice(mid));
    return lines;
  }

  /**
   * Unified Full-Block Renderer Method
   * Renders caption text in 1-2 clean lines with full context, active word sticker chips & floating emojis.
   */
  renderFullBlock(block, currentTime, layout, skin, animType, styleId) {
    const ctx = this.ctx;
    ctx.save();

    const normX = layout.x !== undefined ? layout.x : 0.5;
    const normY = layout.y !== undefined ? layout.y : 0.52;
    const scaleFactor = layout.scale !== undefined ? layout.scale : 1.0;
    const rotationDeg = layout.rotation !== undefined ? layout.rotation : (styleId === 'lightning-comic' ? -4 : 0);
    const skewRads = rotationDeg * (Math.PI / 180);

    const centerX = normX * this.width;
    const centerY = normY * this.height;

    ctx.translate(centerX, centerY);
    ctx.rotate(skewRads);
    ctx.scale(scaleFactor, scaleFactor);

    const words = block.words || [];
    const fontStyleStr = skin.fontStyle ? `${skin.fontStyle} ` : '';
    const fontTemplate = `${fontStyleStr}700 {SIZE}px ${skin.font}`;

    // Split words into 1-2 balanced lines
    const wordLines = this.splitWordsIntoLines(words, 3);
    const longestLineText = wordLines.reduce((max, line) => {
      const txt = line.map(w => w.word).join(' ');
      return txt.length > max.length ? txt : max;
    }, '');

    const safeW = (this.width / scaleFactor) - 160;
    const fontSize = this.fitFontSize(ctx, fontTemplate, longestLineText, safeW, skin.fontSize || 92, 32);
    ctx.font = `${fontStyleStr}700 ${fontSize}px ${skin.font}`;

    const lineHeight = fontSize * 1.25;
    const totalBlockHeight = wordLines.length * lineHeight;
    let lineStartY = -totalBlockHeight / 2 + lineHeight / 2;

    const strokeWidth = Math.max(6, fontSize * (skin.strokeWidthPct || 0.08));
    let activeWordAnchor = null;

    // ── Render Lines & Words ──
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    wordLines.forEach((lineWords, lineIdx) => {
      // Pre-calculate per-word widths with exact rendering fonts
      const wordMetricsList = lineWords.map((w, wIdx) => {
        const wordText = w.word;
        let wFont = `${fontStyleStr}700 ${fontSize}px ${skin.font}`;

        if (animType === 'minimalScriptHybrid') {
          const isScriptWord = lineIdx > 0 || (wordLines.length === 1 && wIdx >= Math.floor(lineWords.length / 2));
          wFont = isScriptWord 
            ? `700 ${fontSize * 1.20}px 'Great Vibes', 'Dancing Script', cursive`
            : `700 ${fontSize * 0.80}px 'Montserrat', 'Inter', sans-serif`;
        }

        ctx.font = wFont;
        let wordW = ctx.measureText(wordText).width;
        let spaceW = Math.max(10, ctx.measureText(' ').width * 0.65);

        if (animType === 'ransomNoteCutout') {
          wordW = this.measureRansomWordWidth(ctx, wordText, wIdx, fontSize);
          spaceW = 14;
        }

        return { wordText, wordW, spaceW, wFont };
      });

      const totalLineW = wordMetricsList.reduce((sum, item, idx) => {
        return sum + item.wordW + (idx < wordMetricsList.length - 1 ? item.spaceW : 0);
      }, 0);

      let wordX = -totalLineW / 2;

      lineWords.forEach((w, wIdx) => {
        const m = wordMetricsList[wIdx];
        const wordText = w.word;
        const wordCenterX = wordX + m.wordW / 2;
        const wordCenterY = lineStartY;

        const isActive = currentTime >= w.start && currentTime <= w.end;
        const isPast = currentTime > w.end;
        const isFuture = currentTime < w.start;

        if (isActive) {
          activeWordAnchor = { x: wordCenterX, y: wordCenterY, width: m.wordW };
        }

        // Typewriter reveal check
        if (animType === 'typewriter' && isFuture) {
          wordX += m.wordW + m.spaceW;
          return;
        }

        ctx.save();
        ctx.translate(wordCenterX, wordCenterY);
        ctx.font = m.wFont;

        if (isActive) {
          const activeProgress = (currentTime - w.start) / Math.max(w.end - w.start, 0.1);

          // 1. Karaoke Fill
          if (animType === 'karaokeFill') {
            this.drawWordTextWithCheapShadow(ctx, wordText, 0, 0, strokeWidth, skin.strokeColor, skin.textColor);

            ctx.save();
            const sweepW = m.wordW * Math.min(activeProgress, 1.0);
            ctx.beginPath();
            ctx.rect(-m.wordW / 2, -fontSize, sweepW, fontSize * 2);
            ctx.clip();

            const sweepColor = this.getWordHighlightColor(w, block.colorTag) || skin.sweepColor || '#22C55E';
            ctx.fillStyle = sweepColor;
            ctx.strokeStyle = skin.strokeColor;
            ctx.lineWidth = strokeWidth;
            ctx.strokeText(wordText, 0, 0);
            ctx.fillText(wordText, 0, 0);
            ctx.restore();

          } 
          // 2. Neon Dual Glow
          else if (animType === 'neonGlow') {
            const popScale = 1.0 + Math.sin(Math.min(activeProgress, 1.0) * Math.PI) * 0.16;
            ctx.scale(popScale, popScale);

            ctx.shadowColor = skin.activeTextColor || '#00F0FF';
            ctx.shadowBlur = 22;
            ctx.lineWidth = strokeWidth;
            ctx.strokeStyle = skin.strokeColor;
            ctx.strokeText(wordText, 0, 0);

            ctx.fillStyle = skin.activeTextColor || '#00F0FF';
            ctx.fillText(wordText, 0, 0);

          } 
          // 3. Pretty Pretty Girl Retro Swash (No Background Box)
          else if (animType === 'prettyGirlRetro') {
            const popScale = 1.0 + Math.sin(Math.min(activeProgress, 1.0) * Math.PI) * 0.16;
            ctx.scale(popScale, popScale);

            ctx.shadowColor = 'rgba(0,0,0,0.8)';
            ctx.shadowBlur = 12;
            ctx.fillStyle = '#FFFFFF';
            ctx.fillText(wordText, 0, 0);

          } 
          // 4. Fit Check 3D Cyan Glitch with True Sticker Text Outline Contour
          else if (animType === 'fitCheckGlitch') {
            const popScale = 1.0 + Math.sin(Math.min(activeProgress, 1.0) * Math.PI) * 0.16;
            ctx.scale(popScale, popScale);

            const outlineWidth = Math.max(16, fontSize * 0.22);
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';

            // Pass 1: Thick White Sticker Contour around letters and offset
            ctx.lineWidth = outlineWidth;
            ctx.strokeStyle = '#FFFFFF';
            ctx.strokeText(wordText, -5, 4);
            ctx.strokeText(wordText, 0, 0);

            // Pass 2: 3D Cyan Glitch Offset
            ctx.shadowColor = '#00F0FF';
            ctx.shadowBlur = 10;
            ctx.fillStyle = skin.glitchColor || '#00F0FF';
            ctx.fillText(wordText, -5, 4);

            // Pass 3: Main Coral Pink Fill
            ctx.shadowBlur = 0;
            ctx.fillStyle = skin.activeTextColor || '#FF2A6D';
            ctx.fillText(wordText, 0, 0);

          } 
          // 5. Newspaper Ransom Note Cutout (Per-letter background tiles)
          else if (animType === 'ransomNoteCutout') {
            const activeProgress = (currentTime - w.start) / Math.max(w.end - w.start, 0.1);
            this.drawRansomWord(ctx, wordText, wIdx, fontSize, true, activeProgress);
          }
          // 6. Minimalist Script Overlay (Hybrid Sans + Script)
          else if (animType === 'minimalScriptHybrid') {
            const activeProgress = (currentTime - w.start) / Math.max(w.end - w.start, 0.1);
            const popScale = 1.0 + Math.sin(Math.min(activeProgress, 1.0) * Math.PI) * 0.16;
            ctx.scale(popScale, popScale);

            const isScriptWord = lineIdx > 0 || (wordLines.length === 1 && wIdx >= Math.floor(lineWords.length / 2));
            ctx.shadowColor = 'rgba(0,0,0,0.8)';
            ctx.shadowBlur = 10;
            ctx.fillStyle = '#FFFFFF';
            if (isScriptWord) {
              ctx.fillText(wordText.toLowerCase(), 0, 0);
            } else {
              ctx.fillText(wordText.toUpperCase(), 0, 0);
            }
          }
          // 7. Sticker Chip Highlight Box (Submagic / CapCut / MrBeast)
          else {
            const popScale = 1.0 + Math.sin(Math.min(activeProgress, 1.0) * Math.PI) * 0.16;
            ctx.scale(popScale, popScale);

            const chipColor = this.getWordHighlightColor(w, block.colorTag) || skin.chipBg || '#FFE600';
            const chipW = m.wordW + (skin.chipPadding?.x || 20) * 2;
            const chipH = fontSize * 1.25;
            const chipR = skin.chipRadius !== undefined ? skin.chipRadius : 10;
            const chipRot = skin.chipRotation || 0;

            this.drawWordChip(ctx, 0, 0, chipW, chipH, chipR, chipColor, chipRot);

            // Active text
            ctx.lineWidth = strokeWidth;
            ctx.strokeStyle = skin.strokeColor;
            ctx.strokeText(wordText, 0, 0);

            ctx.fillStyle = skin.activeTextColor || '#000000';
            ctx.fillText(wordText, 0, 0);
          }

        } else {
          // Context Word
          ctx.globalAlpha = skin.contextAlpha || 0.85;

          if (animType === 'prettyGirlRetro') {
            ctx.shadowColor = 'rgba(0,0,0,0.8)';
            ctx.shadowBlur = 8;
            ctx.fillStyle = '#FFFFFF';
            ctx.fillText(wordText, 0, 0);
          } else if (animType === 'fitCheckGlitch') {
            const outlineWidth = Math.max(16, fontSize * 0.22);
            ctx.lineJoin = 'round';
            ctx.lineCap = 'round';

            // Pass 1: Thick White Sticker Contour
            ctx.lineWidth = outlineWidth;
            ctx.strokeStyle = '#FFFFFF';
            ctx.strokeText(wordText, -5, 4);
            ctx.strokeText(wordText, 0, 0);

            // Pass 2: 3D Cyan Glitch Offset
            ctx.fillStyle = skin.glitchColor || '#00F0FF';
            ctx.fillText(wordText, -5, 4);

            // Pass 3: Main Coral Pink Fill
            ctx.fillStyle = skin.textColor || '#FF2A6D';
            ctx.fillText(wordText, 0, 0);
          } else if (animType === 'ransomNoteCutout') {
            this.drawRansomWord(ctx, wordText, wIdx, fontSize, false, 0);
          } else if (animType === 'minimalScriptHybrid') {
            const isScriptWord = lineIdx > 0 || (wordLines.length === 1 && wIdx >= Math.floor(lineWords.length / 2));
            ctx.shadowColor = 'rgba(0,0,0,0.8)';
            ctx.shadowBlur = 8;
            ctx.fillStyle = '#FFFFFF';
            if (isScriptWord) {
              ctx.fillText(wordText.toLowerCase(), 0, 0);
            } else {
              ctx.fillText(wordText.toUpperCase(), 0, 0);
            }
          } else {
            const wordFillColor = isPast && animType === 'karaokeFill' ? (skin.sweepColor || '#22C55E') : skin.textColor;

            this.drawWordTextWithCheapShadow(
              ctx, wordText, 0, 0,
              strokeWidth, skin.strokeColor, wordFillColor,
              3, 4, 'rgba(0,0,0,0.85)'
            );
          }
        }

        ctx.restore();
        wordX += m.wordW + m.spaceW;
      });

      lineStartY += lineHeight;
    });

    // ── Floating Emoji Anchored Beside Active Word ──
    if (block.emoji) {
      const emojiX = activeWordAnchor ? activeWordAnchor.x + activeWordAnchor.width / 2 + 45 : 0;
      const emojiY = activeWordAnchor ? activeWordAnchor.y - 25 : -totalBlockHeight / 2 - 35;
      this.drawEmojiBadge(ctx, block.emoji, emojiX, emojiY);
    }

    // Calligraphy flourish below for Script
    if (skin.flourish) {
      const flourishY = totalBlockHeight / 2 + 30;
      const flourishHalf = Math.min(safeW * 0.4, 260);
      this.drawCalligraphyFlourish(ctx, 0, flourishY, flourishHalf, fontSize);
    }

    ctx.restore();

    return {
      normX,
      normY,
      widthPx: (longestLineText.length * fontSize * 0.6 + 100) * scaleFactor,
      heightPx: (totalBlockHeight + 60) * scaleFactor,
      scale: scaleFactor
    };
  }

  /**
   * Helper: Measure Ransom Note Word Width across character tiles
   */
  measureRansomWordWidth(ctx, wordText, wordIdx, fontSize) {
    const PALETTE = [
      { font: "'Abril Fatface', serif" },
      { font: "'Times New Roman', serif" },
      { font: "'Shrikhand', serif" },
      { font: "'Playfair Display', serif" },
      { font: "'Montserrat', sans-serif" },
      { font: "'Outfit', sans-serif" }
    ];

    const safeWIdx = (typeof wordIdx === 'number' && !isNaN(wordIdx)) ? wordIdx : 0;
    const chars = (wordText || '').split('');
    if (chars.length === 0) return 0;

    let totalW = 0;
    chars.forEach((char, i) => {
      const idx = (safeWIdx * 7 + i) % PALETTE.length;
      ctx.font = `700 ${fontSize}px ${PALETTE[idx].font}`;
      const charW = Math.max(ctx.measureText(char).width + 24, fontSize * 0.72);
      totalW += charW + 6;
    });

    return totalW - 6;
  }

  /**
   * Helper: Render Newspaper Ransom Cutout Word with individual letter tiles
   */
  drawRansomWord(ctx, wordText, wordIdx = 0, fontSize = 88, isActive = false, activeProgress = 0) {
    const PALETTE = [
      { bg: '#F5F2EB', text: '#111111', font: "'Abril Fatface', serif", rot: -3 },
      { bg: '#E4E0D8', text: '#222222', font: "'Times New Roman', serif", rot: 4 },
      { bg: '#D8D2C2', text: '#1A1A1A', font: "'Shrikhand', serif", rot: -2 },
      { bg: '#D83A6F', text: '#FFFFFF', font: "'Playfair Display', serif", rot: 5 },
      { bg: '#E63946', text: '#FFFFFF', font: "'Montserrat', sans-serif", rot: -4 },
      { bg: '#3D3635', text: '#FFFFFF', font: "'Outfit', sans-serif", rot: 3 }
    ];

    const safeWIdx = (typeof wordIdx === 'number' && !isNaN(wordIdx)) ? wordIdx : 0;
    const chars = (wordText || '').split('');
    if (chars.length === 0) return 0;

    const charWidths = chars.map((char, i) => {
      const idx = (safeWIdx * 7 + i) % PALETTE.length;
      ctx.font = `700 ${fontSize}px ${PALETTE[idx].font}`;
      return Math.max(ctx.measureText(char).width + 24, fontSize * 0.72);
    });

    const totalW = charWidths.reduce((a, b) => a + b + 6, 0) - 6;
    let currX = -totalW / 2;

    chars.forEach((char, i) => {
      const idx = (safeWIdx * 7 + i) % PALETTE.length;
      const styleItem = PALETTE[idx];
      const tileW = charWidths[i];
      const tileH = fontSize * 1.2;
      const charCenterX = currX + tileW / 2;

      ctx.save();
      ctx.translate(charCenterX, 0);

      if (isActive) {
        const popScale = 1.0 + Math.sin(Math.min(activeProgress, 1.0) * Math.PI) * 0.16;
        ctx.scale(popScale, popScale);
      }
      ctx.rotate((styleItem.rot * Math.PI) / 180);

      // Draw paper cut-out tile box for each letter
      ctx.beginPath();
      ctx.rect(-tileW / 2, -tileH / 2, tileW, tileH);
      ctx.fillStyle = styleItem.bg;
      ctx.fill();

      ctx.lineWidth = 2;
      ctx.strokeStyle = 'rgba(0,0,0,0.25)';
      ctx.stroke();

      // Letter inside tile
      ctx.font = `700 ${fontSize}px ${styleItem.font}`;
      ctx.fillStyle = styleItem.text;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(char, 0, 2);

      ctx.restore();

      currX += tileW + 6;
    });

    return totalW;
  }

  /**
   * Dynamic Offscreen Canvas Thumbnail Generator
   */
  generatePresetThumbnails() {
    const thumbnails = {};
    const sampleLayout = { x: 0.5, y: 0.5, scale: 0.9, rotation: 0 };

    Object.keys(PRESETS).forEach(presetKey => {
      const offCanvas = document.createElement('canvas');
      offCanvas.width = 160;
      offCanvas.height = 60;
      const offCtx = offCanvas.getContext('2d');

      const tempRenderer = new LightningComicRenderer(offCanvas, null);
      let sampleText = 'STYLE';
      if (presetKey === 'pretty-pretty-girl') sampleText = 'pretty';
      if (presetKey === 'fit-check') sampleText = 'fit check';
      if (presetKey === 'ransom-note') sampleText = 'the end';
      if (presetKey === 'minimal-script') sampleText = 'best of me';

      tempRenderer.render({
        styleId: presetKey,
        layout: sampleLayout,
        blocks: [{
          id: 'preview_01',
          text: sampleText,
          start: 0,
          end: 1,
          words: sampleText.split(' ').map(w => ({ word: w, start: 0, end: 1 }))
        }]
      }, 0.5);

      thumbnails[presetKey] = offCanvas.toDataURL('image/png');
    });

    return thumbnails;
  }

  drawEmojiBadge(ctx, emoji, x, y) {
    if (!emoji) return;
    ctx.save();
    ctx.font = '64px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.shadowColor = 'rgba(0,0,0,0.6)';
    ctx.shadowBlur = 10;
    ctx.fillText(emoji, x, y);
    ctx.restore();
  }

  drawCalligraphyFlourish(ctx, cx, cy, halfWidth, fontSize = 100) {
    const s = Math.max(fontSize / 110, 0.5);
    ctx.save();
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#FFFDF5';
    ctx.lineWidth = 4 * s;
    ctx.beginPath();
    ctx.moveTo(cx - halfWidth, cy);
    ctx.bezierCurveTo(cx - halfWidth * 0.65, cy - 30 * s, cx - halfWidth * 0.35, cy + 18 * s, cx, cy);
    ctx.bezierCurveTo(cx + halfWidth * 0.35, cy + 18 * s, cx + halfWidth * 0.65, cy - 30 * s, cx + halfWidth, cy);
    ctx.stroke();
    ctx.restore();
  }

  drawStickerElement(ctx, el, currentTime) {
    ctx.save();
    ctx.translate(el.x * this.width, el.y * this.height);
    ctx.rotate(((el.rotation || 0) * Math.PI) / 180);
    ctx.scale(el.scale || 1.0, el.scale || 1.0);

    const size = 110;
    const type = el.type || 'heart_neon';

    if (type === 'heart_neon' || type.includes('heart')) {
      this.drawAestheticHeart(ctx, size, currentTime);
    } else if (type === 'sparkle_gold' || type.includes('sparkle')) {
      this.drawAestheticSparkle(ctx, size, currentTime);
    } else if (type === 'blossom_cherry' || type.includes('blossom') || type.includes('flower')) {
      this.drawAestheticBlossom(ctx, size, currentTime);
    } else if (type === 'crown_gold' || type.includes('crown')) {
      this.drawAestheticCrown(ctx, size, currentTime);
    } else if (type === 'fire_flame' || type.includes('fire') || type.includes('flame')) {
      this.drawAestheticFlame(ctx, size, currentTime);
    } else if (type === 'butterfly_pastel' || type.includes('butterfly')) {
      this.drawAestheticButterfly(ctx, size, currentTime);
    } else if (type === 'daisy_vintage' || type.includes('daisy')) {
      this.drawAestheticDaisy(ctx, size, currentTime);
    } else if (type === 'apple_cute' || type.includes('apple')) {
      this.drawAestheticApple(ctx, size, currentTime);
    } else if (type === 'tape_retro' || type.includes('tape')) {
      this.drawAestheticTape(ctx, size, currentTime);
    } else if (type === 'star_cyber' || type.includes('star') || type.includes('speaker')) {
      this.drawAestheticCyberStar(ctx, size, currentTime);
    } else {
      this.drawAestheticHeart(ctx, size, currentTime);
    }

    ctx.restore();
  }

  /**
   * Ultra-High-Aesthetic Die-Cut Graphic Sticker Renderers
   */

  // 1. 💖 Neon Pink Heart
  drawAestheticHeart(ctx, size, t) {
    const pulse = 1.0 + Math.sin(t * 3.5) * 0.04;
    ctx.scale(pulse, pulse);
    const r = size * 0.44;

    // Pass 1: Die-Cut White Sticker Contour & Drop Shadow
    ctx.save();
    ctx.shadowColor = 'rgba(0, 0, 0, 0.4)';
    ctx.shadowBlur = 14;
    ctx.shadowOffsetY = 4;
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.moveTo(0, r * 0.85);
    ctx.bezierCurveTo(-r * 1.55, -r * 0.15, -r * 1.25, -r * 1.45, 0, -r * 0.55);
    ctx.bezierCurveTo(r * 1.25, -r * 1.45, r * 1.55, -r * 0.15, 0, r * 0.85);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Pass 2: Rich Dual Gradient Heart Fill
    const rInner = r * 0.86;
    const grad = ctx.createLinearGradient(-rInner, -rInner, rInner, rInner);
    grad.addColorStop(0, '#FF2A6D');
    grad.addColorStop(0.5, '#FF5E97');
    grad.addColorStop(1, '#EC4899');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.moveTo(0, rInner * 0.85);
    ctx.bezierCurveTo(-rInner * 1.55, -rInner * 0.15, -rInner * 1.25, -rInner * 1.45, 0, -rInner * 0.55);
    ctx.bezierCurveTo(rInner * 1.25, -rInner * 1.45, rInner * 1.55, -rInner * 0.15, 0, rInner * 0.85);
    ctx.closePath();
    ctx.fill();

    // Pass 3: Specular Glossy Arc
    ctx.fillStyle = 'rgba(255, 255, 255, 0.65)';
    ctx.beginPath();
    ctx.ellipse(-rInner * 0.4, -rInner * 0.45, rInner * 0.28, rInner * 0.16, -Math.PI / 4, 0, Math.PI * 2);
    ctx.fill();
  }

  // 2. ✨ Gold Sparkle Star
  drawAestheticSparkle(ctx, size, t) {
    const rot = Math.sin(t * 1.5) * 0.15;
    ctx.rotate(rot);

    const rOuter = size * 0.48;
    const rInner = size * 0.12;

    // Outer Glow & White Contour
    ctx.save();
    ctx.shadowColor = 'rgba(255, 230, 0, 0.6)';
    ctx.shadowBlur = 18;
    ctx.fillStyle = '#FFFFFF';
    this.drawStarPath(ctx, rOuter * 1.12, rInner * 1.12, 4);
    ctx.fill();
    ctx.restore();

    // Metallic Gold Core
    const grad = ctx.createRadialGradient(0, 0, 2, 0, 0, rOuter * 0.9);
    grad.addColorStop(0, '#FFFFFF');
    grad.addColorStop(0.3, '#FFF3A1');
    grad.addColorStop(0.7, '#FFC700');
    grad.addColorStop(1, '#E69900');

    ctx.fillStyle = grad;
    this.drawStarPath(ctx, rOuter * 0.9, rInner * 0.9, 4);
    ctx.fill();

    // Mini Secondary Companion Sparkle
    ctx.save();
    ctx.translate(rOuter * 0.6, -rOuter * 0.6);
    ctx.fillStyle = '#FFFFFF';
    this.drawStarPath(ctx, rOuter * 0.35, rInner * 0.35, 4);
    ctx.fill();
    ctx.restore();
  }

  // 3. 🌸 Cherry Blossom
  drawAestheticBlossom(ctx, size, t) {
    const r = size * 0.44;

    // White Die-Cut Contour
    ctx.save();
    ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
    ctx.shadowBlur = 12;
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(0, 0, r * 1.14, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // 5 Shaded Sakura Petals
    for (let i = 0; i < 5; i++) {
      ctx.save();
      ctx.rotate((i * Math.PI * 2) / 5 + t * 0.2);

      const pGrad = ctx.createLinearGradient(0, 0, 0, -r * 0.9);
      pGrad.addColorStop(0, '#FFF0F5');
      pGrad.addColorStop(0.6, '#FFB7C5');
      pGrad.addColorStop(1, '#FF80A0');

      ctx.fillStyle = pGrad;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.bezierCurveTo(-r * 0.45, -r * 0.4, -r * 0.35, -r * 0.95, 0, -r * 0.9);
      ctx.bezierCurveTo(r * 0.35, -r * 0.95, r * 0.45, -r * 0.4, 0, 0);
      ctx.closePath();
      ctx.fill();

      // Delicate petal crease line
      ctx.strokeStyle = 'rgba(236, 72, 153, 0.35)';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, -r * 0.2);
      ctx.lineTo(0, -r * 0.7);
      ctx.stroke();

      ctx.restore();
    }

    // Golden Stamen Center
    const cGrad = ctx.createRadialGradient(0, 0, 1, 0, 0, r * 0.35);
    cGrad.addColorStop(0, '#FFF59D');
    cGrad.addColorStop(1, '#FFB700');

    ctx.fillStyle = cGrad;
    ctx.beginPath();
    ctx.arc(0, 0, r * 0.32, 0, Math.PI * 2);
    ctx.fill();
  }

  // 4. 👑 Royal Golden Crown
  drawAestheticCrown(ctx, size, t) {
    const w = size * 0.88;
    const h = size * 0.65;
    const halfW = w / 2;
    const halfH = h / 2;

    // Pass 1: Die-Cut White Sticker Contour & Shadow
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.4)';
    ctx.shadowBlur = 14;
    ctx.shadowOffsetY = 4;
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.moveTo(-halfW * 1.1, halfH * 1.1);
    ctx.lineTo(-halfW * 1.1, -halfH * 0.2);
    ctx.bezierCurveTo(-halfW * 0.7, -halfH * 0.1, -halfW * 0.6, -halfH * 0.8, -halfW * 0.45, -halfH * 0.95);
    ctx.bezierCurveTo(-halfW * 0.2, -halfH * 0.3, 0, -halfH * 1.15, 0, -halfH * 1.15);
    ctx.bezierCurveTo(0, -halfH * 1.15, halfW * 0.2, -halfH * 0.3, halfW * 0.45, -halfH * 0.95);
    ctx.bezierCurveTo(halfW * 0.6, -halfH * 0.8, halfW * 0.7, -halfH * 0.1, halfW * 1.1, -halfH * 0.2);
    ctx.lineTo(halfW * 1.1, halfH * 1.1);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Pass 2: Metallic Gold Crown Body
    const gGrad = ctx.createLinearGradient(0, -halfH, 0, halfH);
    gGrad.addColorStop(0, '#FFF4B8');
    gGrad.addColorStop(0.4, '#FFD700');
    gGrad.addColorStop(0.8, '#E69900');
    gGrad.addColorStop(1, '#B37400');

    ctx.fillStyle = gGrad;
    ctx.beginPath();
    ctx.moveTo(-halfW, halfH);
    ctx.lineTo(-halfW, -halfH * 0.3);
    ctx.lineTo(-halfW * 0.5, -halfH * 0.1);
    ctx.lineTo(-halfW * 0.45, -halfH * 0.85);
    ctx.lineTo(0, -halfH * 0.2);
    ctx.lineTo(0, -halfH * 1.05);
    ctx.lineTo(0, -halfH * 0.2);
    ctx.lineTo(halfW * 0.45, -halfH * 0.85);
    ctx.lineTo(halfW * 0.5, -halfH * 0.1);
    ctx.lineTo(halfW, -halfH * 0.3);
    ctx.lineTo(halfW, halfH);
    ctx.closePath();
    ctx.fill();

    // Pass 3: Crown Base Band with Velvet Trim
    ctx.fillStyle = '#990033';
    ctx.fillRect(-halfW * 0.92, halfH * 0.55, w * 0.92, halfH * 0.38);

    ctx.fillStyle = '#FFD700';
    ctx.fillRect(-halfW * 0.95, halfH * 0.8, w * 0.95, halfH * 0.18);

    // Pass 4: Shimmering Jewels on Crown Tips
    const jewelColors = ['#FF2E63', '#00F0FF', '#FF2E63'];
    const jewelPositions = [
      { x: -halfW * 0.45, y: -halfH * 0.85 },
      { x: 0, y: -halfH * 1.05 },
      { x: halfW * 0.45, y: -halfH * 0.85 }
    ];

    jewelPositions.forEach((pos, idx) => {
      ctx.fillStyle = jewelColors[idx];
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 7, 0, Math.PI * 2);
      ctx.fill();

      // Specular dot
      ctx.fillStyle = '#FFFFFF';
      ctx.beginPath();
      ctx.arc(pos.x - 2, pos.y - 2, 2.5, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  // 5. 🔥 Dynamic Multi-Tier Flame
  drawAestheticFlame(ctx, size, t) {
    const flicker = 1.0 + Math.sin(t * 6) * 0.03;
    ctx.scale(flicker, flicker);

    const w = size * 0.72;
    const h = size * 0.92;
    const halfW = w / 2;
    const halfH = h / 2;

    // Pass 1: White Die-Cut Contour & Warm Glow
    ctx.save();
    ctx.shadowColor = 'rgba(255, 69, 0, 0.55)';
    ctx.shadowBlur = 18;
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.moveTo(0, -halfH * 1.1);
    ctx.bezierCurveTo(-halfW * 1.25, -halfH * 0.2, -halfW * 1.1, halfH * 0.9, 0, halfH * 1.1);
    ctx.bezierCurveTo(halfW * 1.1, halfH * 0.9, halfW * 1.25, -halfH * 0.2, 0, -halfH * 1.1);
    ctx.closePath();
    ctx.fill();
    ctx.restore();

    // Pass 2: Outer Red-Magenta Flame
    const f1Grad = ctx.createLinearGradient(0, halfH, 0, -halfH);
    f1Grad.addColorStop(0, '#D00000');
    f1Grad.addColorStop(0.5, '#FF2A6D');
    f1Grad.addColorStop(1, '#FF4500');

    ctx.fillStyle = f1Grad;
    ctx.beginPath();
    ctx.moveTo(0, -halfH);
    ctx.bezierCurveTo(-halfW * 1.1, -halfH * 0.1, -halfW * 0.95, halfH * 0.8, 0, halfH);
    ctx.bezierCurveTo(halfW * 0.95, halfH * 0.8, halfW * 1.1, -halfH * 0.1, 0, -halfH);
    ctx.closePath();
    ctx.fill();

    // Pass 3: Middle Bright Orange Flame
    const f2Grad = ctx.createLinearGradient(0, halfH * 0.8, 0, -halfH * 0.5);
    f2Grad.addColorStop(0, '#FF7700');
    f2Grad.addColorStop(1, '#FFAA00');

    ctx.fillStyle = f2Grad;
    ctx.beginPath();
    ctx.moveTo(halfW * 0.1, -halfH * 0.55);
    ctx.bezierCurveTo(-halfW * 0.7, -halfH * 0.0, -halfW * 0.6, halfH * 0.6, 0, halfH * 0.85);
    ctx.bezierCurveTo(halfW * 0.6, halfH * 0.6, halfW * 0.7, -halfH * 0.0, halfW * 0.1, -halfH * 0.55);
    ctx.closePath();
    ctx.fill();

    // Pass 4: Inner Yellow-White Core
    ctx.fillStyle = '#FFF59D';
    ctx.beginPath();
    ctx.ellipse(0, halfH * 0.35, halfW * 0.28, halfH * 0.38, 0, 0, Math.PI * 2);
    ctx.fill();
  }

  // 6. 🦋 Y2K Aesthetic Fairy Butterfly
  drawAestheticButterfly(ctx, size, t) {
    const wingFlutter = 1.0 + Math.sin(t * 4) * 0.06;
    ctx.scale(wingFlutter, 1.0);

    const r = size * 0.46;

    // Pass 1: Die-Cut White Sticker Contour & Soft Drop Shadow
    ctx.save();
    ctx.shadowColor = 'rgba(0, 0, 0, 0.35)';
    ctx.shadowBlur = 14;
    ctx.shadowOffsetY = 3;
    ctx.fillStyle = '#FFFFFF';
    
    // Outer butterfly contour
    ctx.beginPath();
    ctx.arc(-r * 0.5, -r * 0.35, r * 0.58, 0, Math.PI * 2);
    ctx.arc(r * 0.5, -r * 0.35, r * 0.58, 0, Math.PI * 2);
    ctx.arc(-r * 0.38, r * 0.38, r * 0.42, 0, Math.PI * 2);
    ctx.arc(r * 0.38, r * 0.38, r * 0.42, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Pass 2: Pastel Cyan-Pink-Lavender Gradient Wings
    const wingGrad = ctx.createLinearGradient(-r, -r, r, r);
    wingGrad.addColorStop(0, '#EC4899'); // Pink
    wingGrad.addColorStop(0.5, '#A855F7'); // Purple
    wingGrad.addColorStop(1, '#06B6D4'); // Cyan

    ctx.fillStyle = wingGrad;

    // Top Left Wing
    ctx.beginPath();
    ctx.ellipse(-r * 0.48, -r * 0.35, r * 0.52, r * 0.38, -0.35, 0, Math.PI * 2);
    ctx.fill();

    // Top Right Wing
    ctx.beginPath();
    ctx.ellipse(r * 0.48, -r * 0.35, r * 0.52, r * 0.38, 0.35, 0, Math.PI * 2);
    ctx.fill();

    // Bottom Left Wing
    ctx.beginPath();
    ctx.ellipse(-r * 0.36, r * 0.38, r * 0.36, r * 0.30, 0.35, 0, Math.PI * 2);
    ctx.fill();

    // Bottom Right Wing
    ctx.beginPath();
    ctx.ellipse(r * 0.36, r * 0.38, r * 0.36, r * 0.30, -0.35, 0, Math.PI * 2);
    ctx.fill();

    // Pass 3: Delicate White Inner Wing Filigree Veins
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
    ctx.lineWidth = 2.5;

    // Left Wing Vein
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.quadraticCurveTo(-r * 0.4, -r * 0.3, -r * 0.75, -r * 0.45);
    ctx.moveTo(0, 0);
    ctx.quadraticCurveTo(-r * 0.3, -r * 0.5, -r * 0.5, -r * 0.7);
    ctx.stroke();

    // Right Wing Vein
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.quadraticCurveTo(r * 0.4, -r * 0.3, r * 0.75, -r * 0.45);
    ctx.moveTo(0, 0);
    ctx.quadraticCurveTo(r * 0.3, -r * 0.5, r * 0.5, -r * 0.7);
    ctx.stroke();

    // Pass 4: Butterfly Body & Antennae
    ctx.fillStyle = '#1E1B4B';
    ctx.beginPath();
    ctx.ellipse(0, 0, 4.5, r * 0.55, 0, 0, Math.PI * 2);
    ctx.fill();

    // Swirled Antennae with Golden Bead Tips
    ctx.strokeStyle = '#1E1B4B';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    ctx.moveTo(0, -r * 0.4);
    ctx.bezierCurveTo(-r * 0.15, -r * 0.7, -r * 0.35, -r * 0.75, -r * 0.3, -r * 0.85);
    ctx.moveTo(0, -r * 0.4);
    ctx.bezierCurveTo(r * 0.15, -r * 0.7, r * 0.35, -r * 0.75, r * 0.3, -r * 0.85);
    ctx.stroke();

    ctx.fillStyle = '#FFD700';
    ctx.beginPath();
    ctx.arc(-r * 0.3, -r * 0.85, 3.5, 0, Math.PI * 2);
    ctx.arc(r * 0.3, -r * 0.85, 3.5, 0, Math.PI * 2);
    ctx.fill();
  }

  // 7. 🌼 Retro 70s Cute Daisy
  drawAestheticDaisy(ctx, size, t) {
    const rot = Math.sin(t * 1.2) * 0.08;
    ctx.rotate(rot);

    const r = size * 0.45;

    // Pass 1: Die-Cut White Sticker Contour & Shadow
    ctx.save();
    ctx.shadowColor = 'rgba(0, 0, 0, 0.35)';
    ctx.shadowBlur = 12;
    ctx.shadowOffsetY = 3;
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(0, 0, r * 1.18, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Pass 2: 12 Overlapping 3D Shaded Petals
    const numPetals = 12;
    for (let i = 0; i < numPetals; i++) {
      ctx.save();
      ctx.rotate((i * Math.PI * 2) / numPetals);

      const petalGrad = ctx.createLinearGradient(0, 0, 0, -r * 0.95);
      petalGrad.addColorStop(0, '#FFFDF5');
      petalGrad.addColorStop(0.7, '#FFFFFF');
      petalGrad.addColorStop(1, '#F3EFE0');

      ctx.fillStyle = petalGrad;
      ctx.beginPath();
      ctx.ellipse(0, -r * 0.58, r * 0.19, r * 0.44, 0, 0, Math.PI * 2);
      ctx.fill();

      ctx.strokeStyle = 'rgba(0, 0, 0, 0.12)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      ctx.restore();
    }

    // Pass 3: Sunburst Golden Yellow Center
    const cGrad = ctx.createRadialGradient(0, 0, 2, 0, 0, r * 0.38);
    cGrad.addColorStop(0, '#FFE066');
    cGrad.addColorStop(0.7, '#FFB700');
    cGrad.addColorStop(1, '#E69900');

    ctx.fillStyle = cGrad;
    ctx.beginPath();
    ctx.arc(0, 0, r * 0.36, 0, Math.PI * 2);
    ctx.fill();

    // Pass 4: Cute Aesthetic Smile Face
    ctx.strokeStyle = '#3D2314';
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';

    // Left Eye
    ctx.beginPath();
    ctx.arc(-r * 0.14, -r * 0.06, 3, 0, Math.PI * 2);
    ctx.fillStyle = '#3D2314';
    ctx.fill();

    // Right Eye
    ctx.beginPath();
    ctx.arc(r * 0.14, -r * 0.06, 3, 0, Math.PI * 2);
    ctx.fill();

    // Happy Smile Curve
    ctx.beginPath();
    ctx.arc(0, 0, r * 0.15, 0.2 * Math.PI, 0.8 * Math.PI);
    ctx.stroke();
  }

  // 8. 🍎 Cute Glossy Red Apple
  drawAestheticApple(ctx, size, t) {
    const bounce = 1.0 + Math.sin(t * 3) * 0.03;
    ctx.scale(bounce, bounce);

    const r = size * 0.44;

    // Pass 1: Die-Cut White Sticker Contour & Shadow
    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.35)';
    ctx.shadowBlur = 12;
    ctx.shadowOffsetY = 4;
    ctx.fillStyle = '#FFFFFF';
    ctx.beginPath();
    ctx.arc(0, r * 0.05, r * 0.95, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Pass 2: Juicy Red Gradient Apple Body
    const appleGrad = ctx.createRadialGradient(-r * 0.3, -r * 0.3, 5, 0, 0, r * 0.9);
    appleGrad.addColorStop(0, '#FF5E7E');
    appleGrad.addColorStop(0.5, '#FF2D55');
    appleGrad.addColorStop(1, '#D7003A');

    ctx.fillStyle = appleGrad;
    ctx.beginPath();
    ctx.moveTo(0, -r * 0.55);
    ctx.bezierCurveTo(-r * 0.95, -r * 0.65, -r * 1.05, r * 0.4, -r * 0.45, r * 0.85);
    ctx.bezierCurveTo(-r * 0.15, r * 0.95, 0, r * 0.75, 0, r * 0.75);
    ctx.bezierCurveTo(0, r * 0.75, r * 0.15, r * 0.95, r * 0.45, r * 0.85);
    ctx.bezierCurveTo(r * 1.05, r * 0.4, r * 0.95, -r * 0.65, 0, -r * 0.55);
    ctx.closePath();
    ctx.fill();

    // Pass 3: Leaf & Stem
    // Brown Stem
    ctx.strokeStyle = '#5D4037';
    ctx.lineWidth = 4;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(0, -r * 0.5);
    ctx.quadraticCurveTo(r * 0.1, -r * 0.75, r * 0.05, -r * 0.88);
    ctx.stroke();

    // Green Leaf
    ctx.fillStyle = '#34C759';
    ctx.beginPath();
    ctx.moveTo(0, -r * 0.65);
    ctx.quadraticCurveTo(-r * 0.4, -r * 0.85, -r * 0.45, -r * 0.55);
    ctx.quadraticCurveTo(-r * 0.15, -r * 0.45, 0, -r * 0.65);
    ctx.closePath();
    ctx.fill();

    // Pass 4: Glossy Specular Highlight
    ctx.fillStyle = 'rgba(255, 255, 255, 0.65)';
    ctx.beginPath();
    ctx.ellipse(-r * 0.4, -r * 0.25, r * 0.22, r * 0.12, -Math.PI / 4, 0, Math.PI * 2);
    ctx.fill();
  }

  // 9. 📼 Retro Scrapbook Washi Tape
  drawAestheticTape(ctx, size, t) {
    const w = size * 0.94;
    const h = size * 0.38;
    const halfW = w / 2;
    const halfH = h / 2;

    ctx.save();
    ctx.shadowColor = 'rgba(0,0,0,0.3)';
    ctx.shadowBlur = 10;
    ctx.shadowOffsetY = 3;

    // Translucent Cream Washi Paper with Torn Edges
    ctx.fillStyle = 'rgba(255, 253, 245, 0.92)';
    ctx.beginPath();
    ctx.moveTo(-halfW, -halfH);

    // Jagged Left Torn Edge
    for (let y = -halfH; y <= halfH; y += 6) {
      ctx.lineTo(-halfW + (y % 12 === 0 ? -4 : 4), y);
    }

    ctx.lineTo(halfW, halfH);

    // Jagged Right Torn Edge
    for (let y = halfH; y >= -halfH; y -= 6) {
      ctx.lineTo(halfW + (y % 12 === 0 ? 4 : -4), y);
    }

    ctx.closePath();
    ctx.fill();

    // Gold Foil Grid Pattern on Tape
    ctx.strokeStyle = 'rgba(255, 183, 0, 0.35)';
    ctx.lineWidth = 1.5;
    for (let x = -halfW + 15; x < halfW - 15; x += 16) {
      ctx.beginPath();
      ctx.moveTo(x, -halfH);
      ctx.lineTo(x, halfH);
      ctx.stroke();
    }

    ctx.restore();
  }

  // 10. ⭐ Y2K Chrome Neon Star
  drawAestheticCyberStar(ctx, size, t) {
    const rot = t * 0.6;
    ctx.rotate(rot);

    const rOuter = size * 0.48;
    const rInner = size * 0.14;

    // Pass 1: Cyber Cyan Glow & White Contour
    ctx.save();
    ctx.shadowColor = '#00F0FF';
    ctx.shadowBlur = 22;
    ctx.fillStyle = '#FFFFFF';
    this.drawStarPath(ctx, rOuter * 1.12, rInner * 1.12, 4);
    ctx.fill();
    ctx.restore();

    // Pass 2: Chrome Cyan Gradient Star Body
    const sGrad = ctx.createLinearGradient(-rOuter, -rOuter, rOuter, rOuter);
    sGrad.addColorStop(0, '#FFFFFF');
    sGrad.addColorStop(0.3, '#70F3FF');
    sGrad.addColorStop(0.7, '#00F0FF');
    sGrad.addColorStop(1, '#0088FF');

    ctx.fillStyle = sGrad;
    this.drawStarPath(ctx, rOuter, rInner, 4);
    ctx.fill();

    // Pass 3: Center Diamond Crosshair Lens Flare
    ctx.fillStyle = '#FFFFFF';
    this.drawStarPath(ctx, rOuter * 0.3, rInner * 0.3, 4);
    ctx.fill();
  }

  drawStarPath(ctx, rOuter, rInner, points) {
    let angle = Math.PI / 2;
    const step = Math.PI / points;
    ctx.beginPath();
    ctx.moveTo(0, -rOuter);
    for (let i = 0; i < points; i++) {
      angle += step;
      ctx.lineTo(rInner * Math.cos(angle - Math.PI / 2), rInner * Math.sin(angle - Math.PI / 2));
      angle += step;
      ctx.lineTo(rOuter * Math.cos(angle - Math.PI / 2), rOuter * Math.sin(angle - Math.PI / 2));
    }
    ctx.closePath();
  }
}

// Global exports
if (typeof window !== 'undefined') {
  window.LightningComicRenderer = LightningComicRenderer;
  window.SKINS = SKINS;
  window.PRESETS = PRESETS;
}
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { LightningComicRenderer, SKINS, PRESETS };
}
