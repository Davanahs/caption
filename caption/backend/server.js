require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const multer = require('multer');
const Groq = require('groq-sdk');
const fs = require('fs');
const os = require('os');

const app = express();
const PORT = process.env.PORT || 5000;

app.use(cors());
app.use(express.json({ limit: '50mb' }));

// Multer: in-memory storage, 25MB limit
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 25 * 1024 * 1024 }
});

// Initialize Groq Client
function getGroqClient() {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey || apiKey === 'your_groq_api_key_here') {
    throw new Error('GROQ_API_KEY is not configured in backend/.env');
  }
  return new Groq({ apiKey });
}

const CONJUNCTIONS = new Set(['and', 'but', 'so', 'because', 'or', 'when', 'if', 'while', 'although', 'since', 'then', 'where', 'as', 'than']);
const PREPOSITIONS = new Set(['in', 'on', 'at', 'to', 'for', 'with', 'from', 'by', 'about', 'into', 'through', 'over', 'under', 'between', 'during', 'without']);

/**
 * Deterministic Word Clustering (Phase 1 Upgrade — POS-Tagging-Lite)
 * Groups Whisper word timestamps into natural caption blocks using phrase boundary scoring.
 */
function segmentWhisperWordsToBlocks(words, maxWordsPerBlock = 4, maxCharsPerBlock = 24, pauseThreshold = 0.25) {
  if (!words || words.length === 0) return [];

  const blocks = [];
  let currentBlockWords = [];
  let currentBlockCharLen = 0;
  let blockStartTime = null;

  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    const wordStr = (w.word || '').trim();
    if (!wordStr) continue;

    if (currentBlockWords.length === 0) blockStartTime = w.start;

    const uppercaseWord = wordStr.toUpperCase();
    currentBlockWords.push({
      word: uppercaseWord,
      start: parseFloat((w.start || 0).toFixed(2)),
      end: parseFloat((w.end || 0).toFixed(2))
    });

    currentBlockCharLen += (currentBlockCharLen > 0 ? 1 : 0) + uppercaseWord.length;

    const isLast = i === words.length - 1;
    const next = !isLast ? words[i + 1] : null;
    const pauseAfter = next ? (next.start - w.end) : 0;
    const nextWordStr = next ? (next.word || '').trim() : '';
    const cleanNextWord = nextWordStr.toLowerCase().replace(/[^a-z]/g, '');

    const projectCharLen = next ? (currentBlockCharLen + 1 + nextWordStr.length) : currentBlockCharLen;

    const isFullWordCount = currentBlockWords.length >= maxWordsPerBlock;
    const isExceedingCharLimit = projectCharLen > maxCharsPerBlock && currentBlockWords.length >= 1;
    const isPauseSplit = pauseAfter >= pauseThreshold;
    const isTerminalPunct = /[.!?]$/.test(wordStr);
    const isClausePunct = /[,:;\-]$/.test(wordStr) && currentBlockWords.length >= 2;
    const isConjunctionSplit = CONJUNCTIONS.has(cleanNextWord) && currentBlockWords.length >= 2;
    const isPrepositionSplit = PREPOSITIONS.has(cleanNextWord) && currentBlockWords.length >= 2 && currentBlockCharLen >= 12;

    const shouldSplit =
      isLast ||
      isTerminalPunct ||
      isPauseSplit ||
      isExceedingCharLimit ||
      isFullWordCount ||
      isClausePunct ||
      isConjunctionSplit ||
      isPrepositionSplit;

    if (shouldSplit) {
      const blockEnd = currentBlockWords[currentBlockWords.length - 1].end;
      blocks.push({
        id: `block_${String(blocks.length + 1).padStart(3, '0')}`,
        text: currentBlockWords.map(bw => bw.word).join(' '),
        start: parseFloat((blockStartTime || 0).toFixed(2)),
        end: parseFloat(blockEnd.toFixed(2)),
        words: [...currentBlockWords]
      });
      currentBlockWords = [];
      currentBlockCharLen = 0;
      blockStartTime = null;
    }
  }

  return blocks;
}

// ─── Health Check ──────────────────────────────────────────────────────────
app.get('/api/health', (req, res) => {
  res.json({
    status: 'online',
    phase: 'Phase 2 — Audio STT Caption Engine',
    groqConfigured: !!(process.env.GROQ_API_KEY && process.env.GROQ_API_KEY !== 'your_groq_api_key_here'),
    timestamp: new Date().toISOString()
  });
});

/**
 * Rule-Based Fallback Director Pass
 */
function ruleBasedDirectorPass(blocks) {
  return blocks.map((block, idx) => {
    const textLower = block.text.toLowerCase();
    const words = block.words || [];

    let colorTag = 'neutral';
    let emoji = null;
    let sfx = null;
    const emphasisWords = [];

    if (/\$|\bdollar\b|\bcash\b|\bmoney\b|\bprofit\b|\brevenue\b|\bcost\b|\bprice\b|\b\d+[kKmMbB]?\b/.test(textLower)) {
      colorTag = 'money';
      sfx = 'cash';
      emoji = '💰';
    } else if (/\bstop\b|\bwarning\b|\bnever\b|\bdont\b|\bdon't\b|\bdanger\b|\bavoid\b|\bwrong\b|\bbad\b/.test(textLower)) {
      colorTag = 'warning';
      sfx = 'whoosh';
      emoji = '🛑';
    } else if (/\?|\bwhy\b|\bhow\b|\bwhat\b|\bwhere\b|\bwhen\b|\bwho\b/.test(textLower)) {
      colorTag = 'question';
      sfx = 'ding';
      emoji = '❓';
    } else if (/\bviral\b|\bsecret\b|\bwin\b|\bbest\b|\bfast\b|\bpro\b|\bgreat\b/.test(textLower)) {
      colorTag = 'highlight';
      sfx = 'pop';
      emoji = '🔥';
    }

    words.forEach(w => {
      const cleanW = w.word.replace(/[^A-Z0-9$]/gi, '');
      if (/\$|\d+/.test(cleanW) || cleanW.length >= 7 || ['VIRAL', 'BEST', 'SECRET', 'STOP', 'NEVER', 'WIN'].includes(cleanW)) {
        emphasisWords.push(w.word);
        w.isEmphasis = true;
      } else {
        w.isEmphasis = false;
      }
    });


    return {
      ...block,
      colorTag,
      emoji: emoji || null,
      sfx: sfx || null,
      emphasisWords,
      words: words.map(w => ({
        ...w,
        isEmphasis: emphasisWords.includes(w.word)
      }))
    };
  });
}

/**
 * Groq LLM Caption Director Pass
 */
async function runDirectorPass(blocks) {
  try {
    const apiKey = process.env.GROQ_API_KEY;
    if (!apiKey || apiKey === 'your_groq_api_key_here') {
      console.log('⚠️ GROQ_API_KEY not configured — using deterministic rule-based Director Pass');
      return ruleBasedDirectorPass(blocks);
    }

    const groq = getGroqClient();
    const promptPayload = blocks.map(b => ({ id: b.id, text: b.text }));

    const response = await groq.chat.completions.create({
      messages: [
        {
          role: 'system',
          content: `You are an expert Short-Form Video Caption Director (like Submagic/CapCut).
Analyze caption text blocks and return visual director annotations to maximize viewer engagement.

For each block, return:
- id: match block id
- emphasisWords: array of 1-2 high-impact words from block text to emphasize visually (e.g. ["$10,000"], ["VIRAL"])
- emoji: single relevant contextual emoji (or null). Capped at ~15% of blocks.
- sfx: sound effect sting tag ("cash", "whoosh", "ding", "pop", "boom", or null)
- colorTag: semantic color category ("neutral", "highlight", "warning", "money", "question")

Respond ONLY with valid JSON:
{
  "annotations": [
    { "id": "block_001", "colorTag": "money", "emoji": "💰", "sfx": "cash", "emphasisWords": ["$10,000"] }
  ]
}`
        },
        {
          role: 'user',
          content: JSON.stringify({ blocks: promptPayload })
        }
      ],
      model: 'openai/gpt-oss-20b',
      temperature: 0.2,
      response_format: { type: 'json_object' }
    });

    const parsed = JSON.parse(response.choices[0].message.content);
    const annotations = parsed.annotations || parsed.blocks || [];
    const annotationMap = new Map(annotations.map(a => [a.id, a]));

    return blocks.map(block => {
      const ann = annotationMap.get(block.id) || {};
      const emphasisWords = ann.emphasisWords || [];
      const colorTag = ann.colorTag || 'neutral';
      const emoji = ann.emoji || null;
      const sfx = ann.sfx || null;

      const words = (block.words || []).map(w => {
        const isEmph = emphasisWords.some(ew => ew.toUpperCase() === w.word.toUpperCase());
        return {
          ...w,
          isEmphasis: isEmph
        };
      });

      return {
        ...block,
        colorTag,
        emoji,
        sfx,
        emphasisWords,
        words
      };
    });

  } catch (err) {
    console.warn('⚠️ Groq Director Pass failed, falling back to rule-based director:', err.message);
    return ruleBasedDirectorPass(blocks);
  }
}

// ─── Phase 4: Audio Cleanup & Silence Trimming ─────────────────────────────
const DEFAULT_FILLER_REGEX = /\b(um|uh|er|ahm|hmm|like|you know|so basically)\b/i;

function detectSilenceGaps(blocks, threshold = 0.5) {
  const silenceCuts = [];
  const allWords = [];
  blocks.forEach(b => (b.words || []).forEach(w => allWords.push(w)));

  for (let i = 0; i < allWords.length - 1; i++) {
    const curr = allWords[i];
    const next = allWords[i + 1];
    const gap = next.start - curr.end;
    if (gap >= threshold) {
      silenceCuts.push({
        start: parseFloat(curr.end.toFixed(2)),
        end: parseFloat(next.start.toFixed(2)),
        duration: parseFloat(gap.toFixed(2))
      });
    }
  }

  return silenceCuts;
}

function processAudioCleanup(blocks, options = {}) {
  const threshold = options.silenceThreshold || 0.5;
  const removeFillers = options.removeFillers !== false;
  const silenceCuts = detectSilenceGaps(blocks, threshold);

  let totalTimeSaved = 0;
  let fillersRemovedCount = 0;

  if (!removeFillers) {
    return {
      silenceCuts,
      fillersRemovedCount: 0,
      totalTimeSavedSeconds: 0,
      blocks
    };
  }

  const cleanedBlocks = [];

  blocks.forEach(block => {
    const originalWords = block.words || [];
    const keptWords = [];

    originalWords.forEach(w => {
      const cleanW = w.word.trim();
      const isFiller = DEFAULT_FILLER_REGEX.test(cleanW);

      if (isFiller) {
        fillersRemovedCount++;
        const wordDur = w.end - w.start;
        totalTimeSaved += wordDur;
      } else {
        keptWords.push({
          ...w,
          start: parseFloat(Math.max(0, w.start - totalTimeSaved).toFixed(2)),
          end: parseFloat(Math.max(0, w.end - totalTimeSaved).toFixed(2))
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

  return {
    silenceCuts,
    fillersRemovedCount,
    totalTimeSavedSeconds: parseFloat(totalTimeSaved.toFixed(2)),
    blocks: cleanedBlocks
  };
}

app.post('/api/caption/cleanup-audio', (req, res) => {
  try {
    const { blocks, silenceThreshold, removeFillers } = req.body;
    if (!blocks || !Array.isArray(blocks)) {
      return res.status(400).json({ error: 'blocks array is required' });
    }

    console.log(`🧹 Processing Audio Cleanup for ${blocks.length} blocks...`);
    const cleanupResult = processAudioCleanup(blocks, { silenceThreshold, removeFillers });
    console.log(`✅ Cleanup done: Removed ${cleanupResult.fillersRemovedCount} fillers, saved ${cleanupResult.totalTimeSavedSeconds}s, detected ${cleanupResult.silenceCuts.length} silence gaps.`);

    res.json({
      success: true,
      ...cleanupResult
    });
  } catch (err) {
    console.error('❌ Audio cleanup error:', err.message);
    res.status(500).json({ error: 'Audio cleanup failed', details: err.message });
  }
});

// ─── Phase 5: Accuracy & Proofreading Pass ─────────────────────────────────
function reMapWordTimestamps(originalWords, correctedWordTokens) {
  if (!originalWords || originalWords.length === 0) return [];
  if (!correctedWordTokens || correctedWordTokens.length === 0) return originalWords;

  const tStart = originalWords[0].start;
  const tEnd = originalWords[originalWords.length - 1].end;
  const totalDuration = Math.max(0.1, tEnd - tStart);

  if (correctedWordTokens.length === originalWords.length) {
    return correctedWordTokens.map((wStr, i) => ({
      word: wStr.toUpperCase(),
      start: originalWords[i].start,
      end: originalWords[i].end
    }));
  }

  const totalChars = correctedWordTokens.reduce((sum, w) => sum + w.length, 0);
  let timeCursor = tStart;

  return correctedWordTokens.map((wStr, i) => {
    const isLast = i === correctedWordTokens.length - 1;
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

async function runProofreadingPass(blocks) {
  try {
    const apiKey = process.env.GROQ_API_KEY;
    if (!apiKey || apiKey === 'your_groq_api_key_here') {
      console.log('⚠️ GROQ_API_KEY not configured — skipping LLM proofreader');
      return blocks;
    }

    const groq = getGroqClient();

    const response = await groq.chat.completions.create({
      messages: [
        {
          role: 'system',
          content: `You are an expert transcript proofreader. Correct spelling, grammar, casing, and homophone errors in the transcript. Do NOT alter meaning.
Return JSON with the corrected text array matching input block count:
{
  "correctedBlocks": ["corrected text 1", "corrected text 2"]
}`
        },
        {
          role: 'user',
          content: JSON.stringify({ blocks: blocks.map(b => b.text) })
        }
      ],
      model: 'openai/gpt-oss-20b',
      temperature: 0.1,
      response_format: { type: 'json_object' }
    });

    const parsed = JSON.parse(response.choices[0].message.content);
    const correctedTexts = parsed.correctedBlocks || [];

    return blocks.map((block, i) => {
      const newText = correctedTexts[i] || block.text;
      const newTokens = newText.trim().split(/\s+/).filter(t => t.length > 0);
      const remappedWords = reMapWordTimestamps(block.words || [], newTokens);

      return {
        ...block,
        text: remappedWords.map(w => w.word).join(' '),
        words: remappedWords
      };
    });

  } catch (err) {
    console.warn('⚠️ Proofreading pass fallback:', err.message);
    return blocks;
  }
}

app.post('/api/caption/proofread', async (req, res) => {
  try {
    const { blocks } = req.body;
    if (!blocks || !Array.isArray(blocks)) {
      return res.status(400).json({ error: 'blocks array is required' });
    }

    console.log(`📝 Running Proofreading Pass on ${blocks.length} blocks...`);
    const startTime = Date.now();
    const correctedBlocks = await runProofreadingPass(blocks);
    const duration = Date.now() - startTime;
    console.log(`✅ Proofreading finished in ${duration}ms`);

    res.json({
      success: true,
      durationMs: duration,
      blocks: correctedBlocks
    });
  } catch (err) {
    console.error('❌ Proofreading error:', err.message);
    res.status(500).json({ error: 'Proofreading failed', details: err.message });
  }
});

// ─── Phase 1: Text Segment Endpoint ────────────────────────────────────────
app.post('/api/caption/text-segment', (req, res) => {
  const { text } = req.body;
  if (!text) return res.status(400).json({ error: 'text field is required' });
  res.json({ success: true, message: 'Text received — segmentation runs client-side in Phase 1.' });
});

// ─── Phase 2: LLM Caption Director Pass Endpoint ───────────────────────────
app.post('/api/caption/director-pass', async (req, res) => {
  try {
    const { blocks } = req.body;
    if (!blocks || !Array.isArray(blocks)) {
      return res.status(400).json({ error: 'blocks array is required' });
    }

    console.log(`🎬 Running Caption Director Pass on ${blocks.length} blocks...`);
    const startTime = Date.now();
    const annotatedBlocks = await runDirectorPass(blocks);
    const duration = Date.now() - startTime;
    console.log(`✅ Caption Director Pass finished in ${duration}ms`);

    res.json({
      success: true,
      durationMs: duration,
      blocks: annotatedBlocks
    });
  } catch (err) {
    console.error('❌ Director pass error:', err.message);
    res.status(500).json({ error: 'Director pass failed', details: err.message });
  }
});

// ─── Phase 2: Audio Transcription Endpoint ─────────────────────────────────
app.post('/api/caption/transcribe-audio', (req, res) => {
  // Wrap multer as a callback to catch multer-level errors properly
  upload.single('audio')(req, res, async (multerErr) => {
    if (multerErr) {
      console.error('❌ Multer error:', multerErr.message);
      return res.status(400).json({ error: 'File upload failed', details: multerErr.message });
    }

    try {
      if (!req.file) {
        return res.status(400).json({ error: 'No audio file received. Make sure the field name is "audio".' });
      }

      console.log(`🎙️ Received: ${req.file.originalname} (${req.file.size} bytes, ${req.file.mimetype})`);

      // Write buffer to a named temp file so Groq SDK can stream it
      const ext = path.extname(req.file.originalname) || '.mp3';
      const tempPath = path.join(os.tmpdir(), `cfaudio_${Date.now()}${ext}`);
      fs.writeFileSync(tempPath, req.file.buffer);

      const groq = getGroqClient();

      const transcription = await groq.audio.transcriptions.create({
        file: fs.createReadStream(tempPath),
        model: 'whisper-large-v3',
        response_format: 'verbose_json',
        timestamp_granularities: ['word'],
        language: 'en'
      });

      // Cleanup temp file
      try { fs.unlinkSync(tempPath); } catch (_) {}

      const rawWords = transcription.words || [];
      const maxWords = parseInt(req.body.maxWords || '4', 10);
      const rawBlocks = segmentWhisperWordsToBlocks(rawWords, maxWords, 24, 0.25);
      console.log(`✅ Transcribed ${rawWords.length} words → ${rawBlocks.length} caption blocks`);

      console.log('🎬 Running Caption Director Pass on transcribed speech...');
      const annotatedBlocks = await runDirectorPass(rawBlocks);

      res.json({
        success: true,
        text: transcription.text,
        wordCount: rawWords.length,
        captionData: {
          version: '2.0',
          styleId: 'lightning-comic',
          layout: { x: 0.5, y: 0.52, scale: 1.0, rotation: -6 },
          blocks: annotatedBlocks
        }
      });

    } catch (err) {
      console.error('❌ Transcription Error:', err.message || err);
      // Always return JSON — never let Express fall through to static HTML
      res.status(500).json({
        error: 'Transcription failed',
        details: err.message || String(err)
      });
    }
  });
});

// ─── Serve Frontend Static ──────────────────────────────────────────────────
app.use(express.static(path.join(__dirname, '../frontend')));

// ─── Global JSON Error Fallback (catches any unhandled route/middleware crash) ──
app.use((err, req, res, _next) => {
  console.error('❌ Unhandled error:', err.message);
  res.status(500).json({ error: 'Internal server error', details: err.message });
});

// ─── Start Server with port fallback ───────────────────────────────────────
function startServer(port) {
  const srv = app.listen(port, () => {
    console.log(`⚡ Caption Engine Backend running on http://localhost:${port}`);
  });
  srv.on('error', (err) => {
    if (err.code === 'EADDRINUSE') {
      console.log(`⚠️  Port ${port} busy — trying ${port + 1}...`);
      startServer(port + 1);
    } else {
      throw err;
    }
  });
}

startServer(PORT);
