require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const multer = require('multer');
const Groq = require('groq-sdk');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

const app = express();
const PORT = process.env.PORT || 5000;

const AUDIO_CACHE_DIR = path.join(os.tmpdir(), 'cf_audio_cache');
if (!fs.existsSync(AUDIO_CACHE_DIR)) {
  fs.mkdirSync(AUDIO_CACHE_DIR, { recursive: true });
}

app.use(cors());
app.use(express.json({ limit: '50mb' }));

// Multer: in-memory storage for audio, 25MB limit
const upload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 25 * 1024 * 1024 }
});

// Multer: disk storage for video uploads (streams up to 100MB to os.tmpdir)
const uploadVideo = multer({
  storage: multer.diskStorage({
    destination: (req, file, cb) => cb(null, os.tmpdir()),
    filename: (req, file, cb) => {
      const ext = path.extname(file.originalname).toLowerCase() || '.mp4';
      cb(null, `cfvideo_${Date.now()}_${Math.random().toString(36).substring(2, 8)}${ext}`);
    }
  }),
  limits: { fileSize: 100 * 1024 * 1024 }, // 100 MB video limit
  fileFilter: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    const allowedExts = ['.mp4', '.mov', '.webm', '.mkv', '.avi', '.m4v'];
    if (file.mimetype.startsWith('video/') || allowedExts.includes(ext)) {
      cb(null, true);
    } else {
      const err = new Error(`Unsupported video format (${ext || 'unknown'}). Supported formats: MP4, MOV, WEBM, MKV, AVI.`);
      err.code = 'UNSUPPORTED_FORMAT';
      cb(err);
    }
  }
});

function getFFmpegPath() {
  return process.env.FFMPEG_PATH || 'ffmpeg';
}

function checkFFmpegAvailable() {
  return new Promise((resolve) => {
    const ffmpegCmd = getFFmpegPath();
    const proc = spawn(ffmpegCmd, ['-version']);
    proc.on('error', () => resolve(false));
    proc.on('close', (code) => resolve(code === 0));
  });
}

function extractAudioFromVideo(videoPath, audioPath) {
  return new Promise((resolve, reject) => {
    const ffmpegCmd = getFFmpegPath();
    // Extract mono 16kHz PCM WAV
    const args = [
      '-y',
      '-i', videoPath,
      '-vn',
      '-acodec', 'pcm_s16le',
      '-ar', '16000',
      '-ac', '1',
      audioPath
    ];

    let stderr = '';
    const proc = spawn(ffmpegCmd, args);

    proc.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    proc.on('error', (err) => {
      if (err.code === 'ENOENT') {
        const notFoundErr = new Error('FFmpeg is not installed or not found on PATH. To enable backend video audio extraction, please install FFmpeg (e.g. winget install Gyan.FFmpeg or https://ffmpeg.org) and ensure it is on PATH or set FFMPEG_PATH in backend/.env.');
        notFoundErr.code = 'FFMPEG_NOT_FOUND';
        return reject(notFoundErr);
      }
      reject(err);
    });

    proc.on('close', (code) => {
      if (code === 0) {
        try {
          const stats = fs.statSync(audioPath);
          if (stats.size === 0) {
            const emptyErr = new Error('Extracted audio file is empty (0 bytes). The video may not contain audible sound.');
            emptyErr.code = 'EMPTY_AUDIO';
            return reject(emptyErr);
          }
          resolve(audioPath);
        } catch (e) {
          reject(new Error(`Failed to locate extracted audio file: ${e.message}`));
        }
      } else {
        const lowerStderr = stderr.toLowerCase();
        if (
          lowerStderr.includes('does not contain any stream') ||
          lowerStderr.includes('output file does not contain any stream') ||
          lowerStderr.includes('matches no streams') ||
          lowerStderr.includes('audio: none') ||
          lowerStderr.includes('no audio')
        ) {
          const noAudioErr = new Error('The uploaded video does not contain an audio stream.');
          noAudioErr.code = 'NO_AUDIO_STREAM';
          return reject(noAudioErr);
        }
        if (lowerStderr.includes('invalid data found when processing input') || lowerStderr.includes('moov atom not found')) {
          const corruptErr = new Error('The uploaded video is corrupted or not a valid video file.');
          corruptErr.code = 'CORRUPTED_VIDEO';
          return reject(corruptErr);
        }
        const generalErr = new Error(`Audio extraction failed with exit code ${code}.`);
        generalErr.details = stderr.slice(-400);
        reject(generalErr);
      }
    });
  });
}

// ─── Automated Praat + Parselmouth Acoustic Engine ──────────────────────────
function getPraatPythonPath() {
  return process.env.PRAAT_PYTHON_PATH || path.join(__dirname, '../audio_analysis/.venv/Scripts/python.exe');
}

function checkPraatAvailable() {
  return new Promise((resolve) => {
    const pythonExe = getPraatPythonPath();
    if (!fs.existsSync(pythonExe)) return resolve(false);
    const cliScript = path.join(__dirname, '../audio_analysis/cli.py');
    const proc = spawn(pythonExe, [cliScript, '--help']);
    proc.on('error', () => resolve(false));
    proc.on('close', (code) => resolve(code === 0));
  });
}

/**
 * Runs local acoustic analysis on the audio file using Praat / Parselmouth.
 * Measures F0 pitch (Hz), vocal intensity (dB), pause intervals, and word acoustic summaries.
 */
function runPraatAnalysis(audioPath, words = []) {
  return new Promise((resolve) => {
    const pythonExe = getPraatPythonPath();
    const cliScript = path.join(__dirname, '../audio_analysis/cli.py');

    if (!fs.existsSync(pythonExe) || !fs.existsSync(cliScript)) {
      console.warn('⚠️ Praat Python environment not found at', pythonExe);
      return resolve(null);
    }

    let tempIntervalsFile = null;
    const args = [cliScript, audioPath, '--compact'];

    if (Array.isArray(words) && words.length > 0) {
      try {
        const intervals = words.map(w => ({
          start: w.start,
          end: w.end,
          label: (w.word || '').trim()
        }));
        tempIntervalsFile = path.join(os.tmpdir(), `cfintervals_${Date.now()}_${Math.random().toString(36).substring(2, 7)}.json`);
        fs.writeFileSync(tempIntervalsFile, JSON.stringify(intervals));
        args.push('--intervals', tempIntervalsFile);
      } catch (err) {
        console.warn('⚠️ Failed to write intervals for Praat:', err.message);
      }
    }

    let stdout = '';
    let stderr = '';
    const proc = spawn(pythonExe, args);

    proc.stdout.on('data', chunk => stdout += chunk);
    proc.stderr.on('data', chunk => stderr += chunk);

    proc.on('close', (code) => {
      if (tempIntervalsFile) {
        try { fs.unlinkSync(tempIntervalsFile); } catch (_) {}
      }

      if (code === 0) {
        try {
          const parsed = JSON.parse(stdout);
          const voicedPct = ((parsed.pitch_analysis?.voiced_fraction || 0) * 100).toFixed(0);
          const pauseCount = parsed.pause_analysis?.pause_count || 0;
          console.log(`✅ Automated Praat Analysis complete in ${parsed.analysis_duration_seconds}s (voiced: ${voicedPct}%, pauses: ${pauseCount})`);
          resolve(parsed);
        } catch (e) {
          console.warn('⚠️ Praat output parse error:', e.message);
          resolve(null);
        }
      } else {
        console.warn('⚠️ Praat exited with code', code, stderr.slice(-300));
        resolve(null);
      }
    });

    proc.on('error', (err) => {
      if (tempIntervalsFile) {
        try { fs.unlinkSync(tempIntervalsFile); } catch (_) {}
      }
      console.warn('⚠️ Praat process error:', err.message);
      resolve(null);
    });
  });
}

/**
 * Augments caption blocks with Praat acoustic emphasis (pitch spikes + loudness peaks).
 */
function applyAcousticEmphasis(blocks, praatResult) {
  if (!praatResult || !praatResult.interval_summaries || !Array.isArray(praatResult.interval_summaries)) {
    return blocks;
  }

  const summaries = praatResult.interval_summaries.filter(s => s.intensity && s.intensity.mean_db > 0);
  if (summaries.length === 0) return blocks;

  const avgDb = summaries.reduce((sum, s) => sum + s.intensity.mean_db, 0) / summaries.length;
  const voicedSummaries = summaries.filter(s => s.pitch && s.pitch.mean_hz > 0);
  const avgHz = voicedSummaries.length > 0 
    ? (voicedSummaries.reduce((sum, s) => sum + s.pitch.mean_hz, 0) / voicedSummaries.length) 
    : 0;

  const summaryMap = new Map();
  summaries.forEach(s => {
    summaryMap.set(parseFloat(s.start.toFixed(2)), s);
  });

  return blocks.map(block => {
    let hasAcousticEmphasis = false;
    const words = (block.words || []).map(w => {
      const match = summaryMap.get(parseFloat((w.start || 0).toFixed(2)));
      let isAcousticEmphasis = false;
      let pitchHz = null;
      let intensityDb = null;

      if (match) {
        intensityDb = match.intensity ? parseFloat(match.intensity.mean_db.toFixed(1)) : null;
        pitchHz = match.pitch ? parseFloat(match.pitch.mean_hz.toFixed(1)) : null;

        const isLoud = intensityDb && (intensityDb >= avgDb + 2.5);
        const isHighPitch = avgHz > 0 && pitchHz && (pitchHz >= avgHz * 1.15);

        if (isLoud || isHighPitch) {
          isAcousticEmphasis = true;
          hasAcousticEmphasis = true;
        }
      }

      return {
        ...w,
        pitchHz,
        intensityDb,
        isAcousticEmphasis,
        isEmphasis: w.isEmphasis || isAcousticEmphasis
      };
    });

    let colorTag = block.colorTag;
    if (hasAcousticEmphasis && (!colorTag || colorTag === 'neutral')) {
      colorTag = 'highlight';
    }

    return {
      ...block,
      colorTag,
      words
    };
  });
}

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
app.get('/api/health', async (req, res) => {
  const ffmpegOk = await checkFFmpegAvailable();
  const praatOk = await checkPraatAvailable();
  res.json({
    status: 'online',
    phase: 'Phase 3 — Video & Audio STT + Praat Acoustics',
    groqConfigured: !!(process.env.GROQ_API_KEY && process.env.GROQ_API_KEY !== 'your_groq_api_key_here'),
    ffmpegAvailable: ffmpegOk,
    praatAvailable: praatOk,
    timestamp: new Date().toISOString()
  });
});

app.get('/api/ffmpeg-status', async (req, res) => {
  const ffmpegOk = await checkFFmpegAvailable();
  res.json({
    available: ffmpegOk,
    ffmpegPath: getFFmpegPath(),
    recommendation: ffmpegOk
      ? 'FFmpeg is installed and ready for video audio extraction.'
      : 'FFmpeg is not detected on PATH. To enable backend video audio extraction, install FFmpeg (e.g. winget install Gyan.FFmpeg) and add it to PATH or set FFMPEG_PATH in backend/.env.'
  });
});

app.get('/api/praat-status', async (req, res) => {
  const praatOk = await checkPraatAvailable();
  res.json({
    available: praatOk,
    pythonPath: getPraatPythonPath(),
    description: 'Local Praat + Parselmouth Acoustic Engine for pitch, intensity, and pause detection'
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
 * Groq LLM Caption Director Pass with Praat Acoustic Emphasis Integration
 */
async function runDirectorPass(blocks, praatResult = null) {
  let annotatedBlocks;
  try {
    const apiKey = process.env.GROQ_API_KEY;
    if (!apiKey || apiKey === 'your_groq_api_key_here') {
      console.log('⚠️ GROQ_API_KEY not configured — using deterministic rule-based Director Pass');
      annotatedBlocks = ruleBasedDirectorPass(blocks);
    } else {
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

      annotatedBlocks = blocks.map(block => {
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
    }
  } catch (err) {
    console.warn('⚠️ Groq Director Pass failed, falling back to rule-based director:', err.message);
    annotatedBlocks = ruleBasedDirectorPass(blocks);
  }

  // ── Apply Praat Acoustic Emphasis (Pitch & Loudness Peaks) ────────────────
  if (praatResult) {
    annotatedBlocks = applyAcousticEmphasis(annotatedBlocks, praatResult);
  }

  return annotatedBlocks;
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

      const whisperParams = {
        file: fs.createReadStream(tempPath),
        model: 'whisper-large-v3',
        response_format: 'verbose_json',
        timestamp_granularities: ['word']
      };
      if (req.body.language && req.body.language !== 'auto') {
        whisperParams.language = req.body.language;
      }

      const transcription = await groq.audio.transcriptions.create(whisperParams);

      const rawWords = transcription.words || [];
      const maxWords = parseInt(req.body.maxWords || '4', 10);
      const rawBlocks = segmentWhisperWordsToBlocks(rawWords, maxWords, 24, 0.25);
      console.log(`✅ Transcribed ${rawWords.length} words → ${rawBlocks.length} caption blocks`);

      // ── Automated Praat Acoustic Analysis ──────────────────────────
      console.log('📊 Running automated Praat acoustic analysis on audio...');
      const praatResult = await runPraatAnalysis(tempPath, rawWords);

      // Cleanup temp file
      try { fs.unlinkSync(tempPath); } catch (_) {}

      console.log('🎬 Running Caption Director Pass on transcribed speech...');
      const annotatedBlocks = await runDirectorPass(rawBlocks, praatResult);

      res.json({
        success: true,
        text: transcription.text,
        wordCount: rawWords.length,
        acousticData: praatResult ? {
          pitch: {
            meanHz: praatResult.pitch_analysis?.statistics_hz?.mean ? parseFloat(praatResult.pitch_analysis.statistics_hz.mean.toFixed(1)) : 0,
            maxHz: praatResult.pitch_analysis?.statistics_hz?.max ? parseFloat(praatResult.pitch_analysis.statistics_hz.max.toFixed(1)) : 0,
            voicedRatio: parseFloat(((praatResult.pitch_analysis?.voiced_fraction || 0) * 100).toFixed(0))
          },
          intensity: {
            meanDb: praatResult.intensity_analysis?.statistics_db?.mean ? parseFloat(praatResult.intensity_analysis.statistics_db.mean.toFixed(1)) : 0,
            maxDb: praatResult.intensity_analysis?.statistics_db?.max ? parseFloat(praatResult.intensity_analysis.statistics_db.max.toFixed(1)) : 0
          },
          pauses: {
            count: praatResult.pause_analysis?.pause_count || 0,
            totalDurationSeconds: praatResult.pause_analysis?.total_pause_duration_seconds ? parseFloat(praatResult.pause_analysis.total_pause_duration_seconds.toFixed(2)) : 0
          },
          analysisDurationSeconds: praatResult.analysis_duration_seconds || 0
        } : null,
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

// ─── Serve Extracted Audio Stream (16kHz PCM WAV) ──────────────────────────
app.get('/api/caption/extracted-audio/:filename', (req, res) => {
  const safeFilename = path.basename(req.params.filename);
  const filePath = path.join(AUDIO_CACHE_DIR, safeFilename);
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'Extracted audio not found or expired.' });
  }
  const stat = fs.statSync(filePath);
  res.writeHead(200, {
    'Content-Type': 'audio/wav',
    'Content-Length': stat.size,
    'Accept-Ranges': 'bytes'
  });
  fs.createReadStream(filePath).pipe(res);
});

// ─── Phase 3: Video Upload & Automatic Caption Generation Endpoint ──────────
app.post('/api/caption/transcribe-video', (req, res) => {
  uploadVideo.single('video')(req, res, async (multerErr) => {
    if (multerErr) {
      console.error('❌ Multer video upload error:', multerErr.message);
      if (multerErr.code === 'LIMIT_FILE_SIZE') {
        return res.status(413).json({ error: 'Video file exceeds the 100MB limit.' });
      }
      return res.status(400).json({ error: multerErr.message || 'Video file upload failed' });
    }

    if (!req.file) {
      return res.status(400).json({ error: 'No video file received. Make sure the field name is "video".' });
    }

    const videoTempPath = req.file.path;
    const audioId = `cfaudio_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;
    const audioTempPath = path.join(AUDIO_CACHE_DIR, `${audioId}.wav`);

    console.log(`🎬 Received video: ${req.file.originalname} (${(req.file.size / (1024 * 1024)).toFixed(2)} MB, ${req.file.mimetype})`);

    try {
      console.log('🔊 Extracting audio track with FFmpeg (16kHz mono WAV)...');
      await extractAudioFromVideo(videoTempPath, audioTempPath);

      console.log('🎙️ Sending extracted audio to Groq Whisper API (Auto Language Detection)...');
      const groq = getGroqClient();

      const whisperParams = {
        file: fs.createReadStream(audioTempPath),
        model: 'whisper-large-v3',
        response_format: 'verbose_json',
        timestamp_granularities: ['word']
      };
      if (req.body.language && req.body.language !== 'auto') {
        whisperParams.language = req.body.language;
      }

      const transcription = await groq.audio.transcriptions.create(whisperParams);

      const rawWords = transcription.words || [];
      const maxWords = parseInt(req.body.maxWords || '4', 10);
      const rawBlocks = segmentWhisperWordsToBlocks(rawWords, maxWords, 24, 0.25);
      console.log(`✅ Transcribed ${rawWords.length} words from video → ${rawBlocks.length} caption blocks (detected lang: ${transcription.language || 'auto'})`);

      // ── Automated Praat Acoustic Analysis ──────────────────────────
      console.log('📊 Running automated Praat acoustic analysis on extracted video audio...');
      const praatResult = await runPraatAnalysis(audioTempPath, rawWords);

      console.log('🎬 Running Caption Director Pass on video transcription...');
      const annotatedBlocks = await runDirectorPass(rawBlocks, praatResult);

      res.json({
        success: true,
        text: transcription.text,
        wordCount: rawWords.length,
        language: transcription.language || 'auto',
        audioUrl: `/api/caption/extracted-audio/${audioId}.wav`,
        audioDuration: transcription.duration || (rawBlocks.length > 0 ? rawBlocks[rawBlocks.length - 1].end : 0),
        acousticData: praatResult ? {
          pitch: {
            meanHz: praatResult.pitch_analysis?.statistics_hz?.mean ? parseFloat(praatResult.pitch_analysis.statistics_hz.mean.toFixed(1)) : 0,
            maxHz: praatResult.pitch_analysis?.statistics_hz?.max ? parseFloat(praatResult.pitch_analysis.statistics_hz.max.toFixed(1)) : 0,
            voicedRatio: parseFloat(((praatResult.pitch_analysis?.voiced_fraction || 0) * 100).toFixed(0))
          },
          intensity: {
            meanDb: praatResult.intensity_analysis?.statistics_db?.mean ? parseFloat(praatResult.intensity_analysis.statistics_db.mean.toFixed(1)) : 0,
            maxDb: praatResult.intensity_analysis?.statistics_db?.max ? parseFloat(praatResult.intensity_analysis.statistics_db.max.toFixed(1)) : 0
          },
          pauses: {
            count: praatResult.pause_analysis?.pause_count || 0,
            totalDurationSeconds: praatResult.pause_analysis?.total_pause_duration_seconds ? parseFloat(praatResult.pause_analysis.total_pause_duration_seconds.toFixed(2)) : 0
          },
          analysisDurationSeconds: praatResult.analysis_duration_seconds || 0
        } : null,
        captionData: {
          version: '2.0',
          styleId: 'lightning-comic',
          layout: { x: 0.5, y: 0.52, scale: 1.0, rotation: 0 },
          blocks: annotatedBlocks
        }
      });

    } catch (err) {
      console.error('❌ Video Processing Error:', err.message || err);
      const status = err.code === 'FFMPEG_NOT_FOUND' ? 503 : (err.code === 'NO_AUDIO_STREAM' || err.code === 'CORRUPTED_VIDEO' || err.code === 'EMPTY_AUDIO') ? 400 : 500;
      res.status(status).json({
        error: err.message || 'Video processing failed',
        code: err.code || 'VIDEO_PROCESS_ERROR',
        details: err.details || null
      });
    } finally {
      // Clean up uploaded video temp file immediately; keep extracted WAV in cache for frontend audio sync playback
      if (videoTempPath) {
        try { fs.unlinkSync(videoTempPath); } catch (_) {}
      }
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
