/**
 * App Main Controller — Phase 1 + Phase 2
 * Text segmentation, Groq Whisper STT, Canva drag, audio sync playback.
 *
 * Libraries used:
 *   • Native Fetch API    — audio POST to backend (no Axios needed)
 *   • FormData API        — multipart audio file upload (built-in)
 *   • Web Audio / <audio> — HTML5 audio sync to caption timeline
 *   • requestAnimationFrame — smooth 60fps canvas playback loop
 *   • All segmentation & rendering: custom rule-based (no external NLP lib needed)
 *
 * Why no extra libraries?
 *   Phase 1 chunking is deterministic (word count + pause rules) — no NLP needed.
 *   Phase 2 STT is done server-side via Groq Whisper. Frontend only handles upload + playback.
 */
document.addEventListener('DOMContentLoaded', () => {

  // ─── DOM References ───────────────────────────────────────────────────────
  const tabTextMode       = document.getElementById('tabTextMode');
  const tabAudioMode      = document.getElementById('tabAudioMode');
  const textModeContainer = document.getElementById('textModeContainer');
  const audioModeContainer= document.getElementById('audioModeContainer');
  const panelModeTitle    = document.getElementById('panelModeTitle');
  const panelModeTag      = document.getElementById('panelModeTag');
  const statusText        = document.getElementById('statusText');

  // Text mode
  const scriptInput    = document.getElementById('scriptInput');
  const maxWordsSlider = document.getElementById('maxWordsSlider');
  const maxWordsVal    = document.getElementById('maxWordsVal');
  const playbackSpeed  = document.getElementById('playbackSpeed');
  const speedVal       = document.getElementById('speedVal');
  const generateBtn    = document.getElementById('generateBtn');

  // Audio mode
  const audioDropzone       = document.getElementById('audioDropzone');
  const audioFileInput      = document.getElementById('audioFileInput');
  const audioFileInfo       = document.getElementById('audioFileInfo');
  const fileNameDisplay     = document.getElementById('fileNameDisplay');
  const fileSizeDisplay     = document.getElementById('fileSizeDisplay');
  const audioMaxWordsSlider = document.getElementById('audioMaxWordsSlider');
  const audioMaxWordsVal    = document.getElementById('audioMaxWordsVal');
  const transcribeAudioBtn  = document.getElementById('transcribeAudioBtn');
  const transcribeBtnText   = document.getElementById('transcribeBtnText');
  const syncAudioPlayer     = document.getElementById('syncAudioPlayer');

  // Video mode
  const tabVideoMode          = document.getElementById('tabVideoMode');
  const videoModeContainer    = document.getElementById('videoModeContainer');
  const videoDropzone         = document.getElementById('videoDropzone');
  const videoFileInput        = document.getElementById('videoFileInput');
  const videoDropContent      = document.getElementById('videoDropContent');
  const videoFileInfo         = document.getElementById('videoFileInfo');
  const videoFileNameDisplay  = document.getElementById('videoFileNameDisplay');
  const videoFileSizeDisplay  = document.getElementById('videoFileSizeDisplay');
  const clearVideoFileBtn     = document.getElementById('clearVideoFileBtn');
  const videoMaxWordsSlider   = document.getElementById('videoMaxWordsSlider');
  const videoMaxWordsVal      = document.getElementById('videoMaxWordsVal');
  const transcribeVideoBtn    = document.getElementById('transcribeVideoBtn');
  const transcribeVideoBtnText= document.getElementById('transcribeVideoBtnText');
  const videoProcessingStatus = document.getElementById('videoProcessingStatus');
  const videoStatusSpinner    = document.getElementById('videoStatusSpinner');
  const videoStatusTitle      = document.getElementById('videoStatusTitle');
  const videoStatusDetail     = document.getElementById('videoStatusDetail');
  const retryVideoBtn         = document.getElementById('retryVideoBtn');
  const stepUpload            = document.getElementById('stepUpload');
  const stepExtract           = document.getElementById('stepExtract');
  const stepTranscribe        = document.getElementById('stepTranscribe');
  const stepSegment           = document.getElementById('stepSegment');
  const previewVideoPlayer    = document.getElementById('previewVideoPlayer');
  const acousticSummaryPill   = document.getElementById('acousticSummaryPill');
  const acousticSummaryText   = document.getElementById('acousticSummaryText');

  // Layout & Stage
  const scaleSlider          = document.getElementById('scaleSlider');
  const scaleVal             = document.getElementById('scaleVal');
  const centerBtn            = document.getElementById('centerBtn');
  const toggleSafeZoneBtn    = document.getElementById('toggleSafeZoneBtn');
  const depthInFrontBtn      = document.getElementById('depthInFrontBtn');
  const depthBehindPersonBtn = document.getElementById('depthBehindPersonBtn');
  const depthPositionRow     = document.getElementById('depthPositionRow');
  const posAboveHeadBtn      = document.getElementById('posAboveHeadBtn');
  const posShouldersBtn      = document.getElementById('posShouldersBtn');
  const toggleBehindPersonBtn= document.getElementById('toggleBehindPersonBtn');
  const safeZoneOverlay      = document.getElementById('safeZoneOverlay');
  const canvaBoundingBox     = document.getElementById('canvaBoundingBox');
  const stageBox             = document.getElementById('stageBox');
  const previewImagePlayer   = document.getElementById('previewImagePlayer');
  const personCutoutCanvas   = document.getElementById('personCutoutCanvas');

  // Playback
  const canvas       = document.getElementById('captionCanvas');
  const domOverlay   = document.getElementById('domOverlayContainer');
  const playPauseBtn = document.getElementById('playPauseBtn');
  const playIcon     = document.getElementById('playIcon');
  const resetBtn     = document.getElementById('resetBtn');
  const timeScrubber = document.getElementById('timeScrubber');
  const currentTimeEl= document.getElementById('currentTime');
  const totalTimeEl  = document.getElementById('totalTime');
  const exportJsonBtn= document.getElementById('exportJsonBtn');
  const exportFrameBtn=document.getElementById('exportFrameBtn');

  // Volume & Aspect Ratio Controls
  const volumeToggleBtn    = document.getElementById('volumeToggleBtn');
  const volumeIcon         = document.getElementById('volumeIcon');
  const volumeSlider       = document.getElementById('volumeSlider');
  const aspectBtnsContainer= document.getElementById('aspectBtnsContainer');

  // ─── Renderer ─────────────────────────────────────────────────────────────
  const renderer = new LightningComicRenderer(canvas, domOverlay);

  // ─── App State ────────────────────────────────────────────────────────────
  let captionData = {
    version: '1.0',
    styleId: 'pretty-pretty-girl',
    layout: { x: 0.5, y: 0.52, scale: 1.0, rotation: 0 },
    blocks: [],
    elements: [],
    selectedItemId: 'caption' // 'caption' or 'el_<id>'
  };

  // Stickers / Canva Elements UI elements
  const elRotationSlider = document.getElementById('elRotationSlider');
  const elRotationVal    = document.getElementById('elRotationVal');
  const deleteElementBtn = document.getElementById('deleteElementBtn');
  const elementControls  = document.getElementById('elementControls');
  const elementSearch    = document.getElementById('elementSearch');
  const elementsGrid     = document.getElementById('elementsGrid');
  const canvaDeleteBadge = document.getElementById('canvaDeleteBadge');

  let currentMode          = 'text'; // 'text' | 'audio' | 'video'
  let audioBlob            = null;   // stored audio file for sync playback
  let videoBlob            = null;   // stored video file for preview & transcription
  let imageBlob            = null;   // stored image file for photo preview
  let behindPersonEnabled  = false;  // 3D text behind subject cutout active
  let userExplicitlyEnabledDepth = false; // true if user manually clicked Behind Person button
  let selfieSegmentation   = null;   // MediaPipe instance
  let isSegmenting         = false;  // lock for active frame segmentation
  let latestMaskCanvas     = null;   // offscreen canvas storing latest segmentation alpha mask
  let hasValidMask         = false;  // true when latestMaskCanvas contains valid mask
  let lastSegmentationTime = 0;      // throttle timestamp
  const SEGMENTATION_INTERVAL_MS = 120; // ~8 FPS inference throttle to prevent WebGL/video stutter
  let currentTime          = 0.0;
  let totalDuration        = 0.0;
  let isPlaying            = false;
  let animFrameId          = null;
  let lastTimestamp        = 0;
  let audioSynced          = false;  // true when audio mode is active & playing

  // Volume state
  let currentVolume = 1.0;
  let isMuted       = false;

  // Aspect ratio state
  let currentRatio       = 'auto'; // 'auto' | '9:16' | '16:9' | '1:1' | '4:5'
  let videoNaturalWidth  = 0;
  let videoNaturalHeight = 0;

  // ─── Volume Management ─────────────────────────────────────────────────────
  function updateVolume(vol, muted) {
    currentVolume = Math.max(0, Math.min(1, vol));
    isMuted = muted;

    previewVideoPlayer.muted = isMuted;
    previewVideoPlayer.volume = isMuted ? 0 : currentVolume;

    syncAudioPlayer.muted = isMuted;
    syncAudioPlayer.volume = isMuted ? 0 : currentVolume;

    if (volumeSlider) volumeSlider.value = isMuted ? 0 : currentVolume;
    if (volumeIcon) {
      volumeIcon.textContent = isMuted || currentVolume === 0 ? '🔇' : (currentVolume < 0.5 ? '🔉' : '🔊');
    }
  }

  if (volumeSlider) {
    volumeSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      updateVolume(val, val === 0);
    });
  }

  if (volumeToggleBtn) {
    volumeToggleBtn.addEventListener('click', () => {
      updateVolume(currentVolume > 0 ? currentVolume : 1.0, !isMuted);
    });
  }

  // ─── Aspect Ratio Management (Preserve Original Video Ratio) ───────────────
  function setStageAspectRatio(ratioStr, naturalW, naturalH) {
    currentRatio = ratioStr;

    // Highlight active ratio button
    if (aspectBtnsContainer) {
      aspectBtnsContainer.querySelectorAll('.aspect-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.ratio === ratioStr);
      });
    }

    const nw = naturalW || videoNaturalWidth || 0;
    const nh = naturalH || videoNaturalHeight || 0;

    let targetRatio;
    if (ratioStr === 'auto') {
      if (nw > 0 && nh > 0) {
        targetRatio = nw / nh;
      } else {
        targetRatio = 9 / 16; // Default to vertical reels if no video
      }
    } else if (ratioStr === '16:9') {
      targetRatio = 16 / 9;
    } else if (ratioStr === '9:16') {
      targetRatio = 9 / 16;
    } else if (ratioStr === '1:1') {
      targetRatio = 1.0;
    } else if (ratioStr === '4:5') {
      targetRatio = 4 / 5;
    } else {
      targetRatio = 9 / 16;
    }

    // Determine stage display box dimensions
    const maxW = 540;
    const maxH = 533;
    let boxW, boxH;

    if (targetRatio >= 1.0) {
      // Landscape or square
      boxW = Math.min(maxW, 520);
      boxH = Math.round(boxW / targetRatio);
      if (boxH > maxH) {
        boxH = maxH;
        boxW = Math.round(boxH * targetRatio);
      }
    } else {
      // Portrait / vertical
      boxH = Math.min(maxH, 533);
      boxW = Math.round(boxH * targetRatio);
      if (boxW > maxW) {
        boxW = maxW;
        boxH = Math.round(boxW / targetRatio);
      }
    }

    stageBox.style.width = `${boxW}px`;
    stageBox.style.height = `${boxH}px`;
    if (nw > 0 && nh > 0) {
      stageBox.style.aspectRatio = `${nw} / ${nh}`;
    }

    // Match canvas native render resolution 1:1 to video without distortion
    let canvasW, canvasH;
    if (ratioStr === 'auto' && nw > 0 && nh > 0) {
      canvasW = nw;
      canvasH = nh;
    } else if (targetRatio >= 1.0) {
      canvasW = 1920;
      canvasH = Math.round(1920 / targetRatio);
    } else {
      canvasH = 1920;
      canvasW = Math.round(1920 * targetRatio);
    }

    renderer.setSize(canvasW, canvasH);
    if (personCutoutCanvas) {
      personCutoutCanvas.width = canvasW;
      personCutoutCanvas.height = canvasH;
    }
    renderCurrentFrame();
  }

  if (aspectBtnsContainer) {
    aspectBtnsContainer.addEventListener('click', (e) => {
      const btn = e.target.closest('.aspect-btn');
      if (btn && btn.dataset.ratio) {
        setStageAspectRatio(btn.dataset.ratio, videoNaturalWidth, videoNaturalHeight);
      }
    });
  }

  // ─── Mode Switching ────────────────────────────────────────────────────────
  tabTextMode.addEventListener('click', () => switchMode('text'));
  tabAudioMode.addEventListener('click', () => switchMode('audio'));
  tabVideoMode.addEventListener('click', () => switchMode('video'));

  function switchMode(mode) {
    currentMode = mode;
    pausePlayback();
    currentTime = 0.0;
    timeScrubber.value = 0;
    syncAudioPlayer.pause();
    syncAudioPlayer.currentTime = 0;

    tabTextMode.classList.toggle('active', mode === 'text');
    tabAudioMode.classList.toggle('active', mode === 'audio');
    tabVideoMode.classList.toggle('active', mode === 'video');

    textModeContainer.classList.toggle('hidden', mode !== 'text');
    audioModeContainer.classList.toggle('hidden', mode !== 'audio');
    videoModeContainer.classList.toggle('hidden', mode !== 'video');

    if (mode === 'text') {
      panelModeTitle.textContent = '1. Script & Caption Blocks';
      panelModeTag.textContent = 'Text Engine';
      statusText.textContent = 'Phase 1: Text-to-Captions';
      if (!imageBlob) {
        previewVideoPlayer.pause();
        previewVideoPlayer.classList.add('hidden');
      }
      setStageAspectRatio(currentRatio, videoNaturalWidth, videoNaturalHeight);
    } else if (mode === 'audio') {
      panelModeTitle.textContent = '1. Audio Transcription';
      panelModeTag.textContent = 'Groq Whisper STT';
      statusText.textContent = 'Phase 2: Audio STT';
      previewVideoPlayer.pause();
      previewVideoPlayer.classList.add('hidden');
      previewImagePlayer.classList.add('hidden');
      setStageAspectRatio(currentRatio, videoNaturalWidth, videoNaturalHeight);
    } else if (mode === 'video') {
      panelModeTitle.textContent = '1. Video Upload & Transcription';
      panelModeTag.textContent = 'Video STT Engine';
      statusText.textContent = 'Phase 3: Video Upload & Canvas Overlay';
      if (videoBlob && previewVideoPlayer.src) {
        previewVideoPlayer.classList.remove('hidden');
        previewImagePlayer.classList.add('hidden');
      } else if (imageBlob && previewImagePlayer.src) {
        previewImagePlayer.classList.remove('hidden');
        previewVideoPlayer.classList.add('hidden');
      }
      setStageAspectRatio(currentRatio, videoNaturalWidth, videoNaturalHeight);
    }

    renderCurrentFrame();
  }

  // ─── Text Mode ─────────────────────────────────────────────────────────────
  scriptInput.value = "We are building a standalone caption engine MVP first, so we can create high-quality captions with extreme visual polish.";

  maxWordsSlider.addEventListener('input', (e) => {
    maxWordsVal.textContent = e.target.value;
  });
  playbackSpeed.addEventListener('input', (e) => {
    speedVal.textContent = e.target.value;
  });

  generateBtn.addEventListener('click', processTextAndGenerate);

  function processTextAndGenerate() {
    const normalized = TextNormalizer.normalize(scriptInput.value);
    if (!normalized) { alert('Please paste a valid text script.'); return; }

    // Phase 1: Smart Caption Segmentation (Break Scoring Engine)
    const generated = TextSegmenter.segment(normalized, {
      maxWords: parseInt(maxWordsSlider.value, 10),
      maxChars: 24,
      wpm: parseInt(playbackSpeed.value, 10),
      styleId: captionData.styleId || 'pretty-pretty-girl'
    });

    // Phase 5 & 5.5: Local Accuracy Engine & Token Alignment
    const correctedBlocks = LocalAccuracyEngine.processBlocks(generated.blocks);

    // Phase 2: Local Caption Director (100% Offline Rule Engine)
    const annotatedBlocks = LocalCaptionDirector.annotate(correctedBlocks);

    // Load annotated blocks into preview player
    loadCaptionData(annotatedBlocks);
    statusText.textContent = '⚡ Phase 1–5.5: Local Offline Caption Engine Ready!';
  }

  // ─── Audio Mode ─────────────────────────────────────────────────────────────
  audioMaxWordsSlider.addEventListener('input', (e) => {
    audioMaxWordsVal.textContent = e.target.value;
  });

  // File selection via click or drag-drop
  audioFileInput.addEventListener('change', (e) => {
    if (e.target.files[0]) handleAudioFile(e.target.files[0]);
  });

  audioDropzone.addEventListener('click', (e) => {
    if (e.target !== audioFileInput) {
      audioFileInput.click();
    }
  });

  audioDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    audioDropzone.classList.add('drag-over');
  });
  audioDropzone.addEventListener('dragleave', () => {
    audioDropzone.classList.remove('drag-over');
  });
  audioDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    audioDropzone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('audio/')) {
      handleAudioFile(file);
    }
  });

  function handleAudioFile(file) {
    const SUPPORTED = ['audio/mpeg','audio/mp3','audio/wav','audio/x-wav','audio/mp4','audio/m4a','audio/ogg','audio/webm','audio/flac'];
    if (!SUPPORTED.includes(file.type) && !file.name.match(/\.(mp3|wav|m4a|ogg|flac|webm)$/i)) {
      showTranscriptStatus('error', `Unsupported format: ${file.type}. Use MP3, WAV, M4A, OGG.`);
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      showTranscriptStatus('error', 'File exceeds 25MB limit.');
      return;
    }

    audioBlob = file;
    fileNameDisplay.textContent = file.name;
    fileSizeDisplay.textContent = formatFileSize(file.size);
    audioFileInfo.classList.remove('hidden');

    // Load into HTML5 audio element for sync playback
    const blobUrl = URL.createObjectURL(file);
    syncAudioPlayer.src = blobUrl;
    syncAudioPlayer.load();
  }

  transcribeAudioBtn.addEventListener('click', async () => {
    if (!audioBlob) {
      showTranscriptStatus('error', 'Please select an audio file first.');
      return;
    }

    // Loading state
    transcribeAudioBtn.classList.add('btn-loading');
    transcribeAudioBtn.disabled = true;
    transcribeBtnText.textContent = 'Transcribing...';
    showTranscriptStatus('loading', '⚡ Sending to Groq Whisper API — this takes a few seconds...');

    try {
      const formData = new FormData();
      formData.append('audio', audioBlob, audioBlob.name);
      formData.append('maxWords', audioMaxWordsSlider.value);

      const response = await fetch('/api/caption/transcribe-audio', {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        throw new Error(result.details || result.error || 'Transcription failed');
      }

      showTranscriptStatus('success', `✅ Transcribed ${result.captionData.blocks.length} caption blocks from speech.`);
      loadCaptionData(result.captionData.blocks, true);
      audioSynced = true;

    } catch (err) {
      console.error('Transcription error:', err);
      showTranscriptStatus('error', `❌ ${err.message}`);
    } finally {
      transcribeAudioBtn.classList.remove('btn-loading');
      transcribeAudioBtn.disabled = false;
      transcribeBtnText.textContent = '🎙️ Transcribe Speech with Groq Whisper';
    }
  });

  function showTranscriptStatus(type, message) {
    // Create or update status element
    let statusEl = document.getElementById('transcriptStatusEl');
    if (!statusEl) {
      statusEl = document.createElement('div');
      statusEl.id = 'transcriptStatusEl';
      statusEl.className = 'transcript-status';
      transcribeAudioBtn.parentNode.insertBefore(statusEl, transcribeAudioBtn.nextSibling);
    }
    statusEl.className = `transcript-status ${type}`;
    statusEl.textContent = message;
    statusEl.classList.remove('hidden');
  }

  // ─── Video Mode (Phase 3) ───────────────────────────────────────────────────
  videoMaxWordsSlider.addEventListener('input', (e) => {
    videoMaxWordsVal.textContent = e.target.value;
  });

  videoFileInput.addEventListener('change', (e) => {
    if (e.target.files[0]) handleVideoFile(e.target.files[0]);
  });

  videoDropzone.addEventListener('click', (e) => {
    if (e.target !== clearVideoFileBtn && !clearVideoFileBtn.contains(e.target) && e.target !== videoFileInput) {
      videoFileInput.click();
    }
  });

  videoDropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    videoDropzone.classList.add('drag-over');
  });

  videoDropzone.addEventListener('dragleave', () => {
    videoDropzone.classList.remove('drag-over');
  });

  videoDropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    videoDropzone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && (file.type.startsWith('video/') || file.type.startsWith('image/') || file.name.match(/\.(mp4|webm|mov|mkv|avi|m4v|jpg|jpeg|png|webp)$/i))) {
      handleVideoFile(file);
    }
  });

  clearVideoFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    clearVideoFile();
  });

  retryVideoBtn.addEventListener('click', () => {
    if (videoBlob) startVideoTranscription();
  });

  function clearVideoFile() {
    videoBlob = null;
    imageBlob = null;
    videoNaturalWidth = 0;
    videoNaturalHeight = 0;
    videoFileInput.value = '';
    videoDropContent.classList.remove('hidden');
    videoFileInfo.classList.add('hidden');
    transcribeVideoBtn.disabled = true;
    transcribeVideoBtnText.textContent = '⚡ Extract Audio & Generate Captions';
    videoProcessingStatus.classList.add('hidden');
    if (acousticSummaryPill) acousticSummaryPill.classList.add('hidden');
    previewVideoPlayer.pause();
    previewVideoPlayer.removeAttribute('src');
    previewVideoPlayer.load();
    previewVideoPlayer.classList.add('hidden');
    previewImagePlayer.removeAttribute('src');
    previewImagePlayer.classList.add('hidden');
    if (personCutoutCanvas) {
      const pCtx = personCutoutCanvas.getContext('2d');
      pCtx.clearRect(0, 0, personCutoutCanvas.width, personCutoutCanvas.height);
      personCutoutCanvas.classList.add('hidden');
    }
    setStageAspectRatio('auto', 1080, 1920);
    renderCurrentFrame();
  }

  function handleVideoFile(file) {
    const ext = (file.name.split('.').pop() || '').toLowerCase();
    const isImage = file.type.startsWith('image/') || ['jpg', 'jpeg', 'png', 'webp', 'bmp'].includes(ext);
    const allowedVideoExts = ['mp4', 'mov', 'webm', 'mkv', 'avi', 'm4v'];

    if (!isImage && !file.type.startsWith('video/') && !allowedVideoExts.includes(ext)) {
      alert(`Unsupported file format (.${ext}). Supported formats: Video (MP4, MOV, WEBM, MKV) or Image (JPG, PNG, WEBP).`);
      return;
    }

    if (file.size > 100 * 1024 * 1024) {
      alert('File exceeds the 100MB limit. Please upload a smaller file.');
      return;
    }

    if (isImage) {
      // ── Handle Image File ──
      imageBlob = file;
      videoBlob = null;
      videoFileNameDisplay.textContent = file.name;
      videoFileSizeDisplay.textContent = formatFileSize(file.size);
      videoDropContent.classList.add('hidden');
      videoFileInfo.classList.remove('hidden');
      transcribeVideoBtn.disabled = false;
      transcribeVideoBtnText.textContent = '👤 Person Cutout Active';
      videoProcessingStatus.classList.remove('hidden');

      previewVideoPlayer.pause();
      previewVideoPlayer.classList.add('hidden');

      const imgUrl = URL.createObjectURL(file);
      previewImagePlayer.src = imgUrl;

      previewImagePlayer.onload = () => {
        previewImagePlayer.classList.remove('hidden');
        videoNaturalWidth = previewImagePlayer.naturalWidth || 1080;
        videoNaturalHeight = previewImagePlayer.naturalHeight || 1920;

        setStageAspectRatio(currentRatio, videoNaturalWidth, videoNaturalHeight);

        // Auto-activate "Behind Person" style preset
        const behindBtn = document.getElementById('presetBehindPerson');
        if (behindBtn) {
          behindBtn.click();
        } else {
          setBehindPersonMode(true);
        }

        setVideoStep('upload', 'completed', `Loaded image: ${file.name}`);
        setVideoStep('extract', 'completed', 'Image mode (No audio track needed)');
        setVideoStep('transcribe', 'completed', 'Text Behind Person active');
        setVideoStep('segment', 'completed', 'Captions positioned behind subject! Use Text Mode or block editor to customize words.');
        videoStatusSpinner.textContent = '👤';
        videoStatusTitle.textContent = 'Text Behind Person Active';

        runSegmentationOnCurrentMedia(true);
        renderCurrentFrame();
      };
      return;
    }

    // ── Handle Video File ──
    imageBlob = null;
    videoBlob = file;
    hasAutoPositionedPerson = false;
    videoFileNameDisplay.textContent = file.name;
    videoFileSizeDisplay.textContent = formatFileSize(file.size);
    videoDropContent.classList.add('hidden');
    videoFileInfo.classList.remove('hidden');
    transcribeVideoBtn.disabled = false;
    transcribeVideoBtnText.textContent = '⚡ Extract Audio & Generate Captions';
    videoProcessingStatus.classList.remove('hidden');

    previewImagePlayer.classList.add('hidden');

    const videoUrl = URL.createObjectURL(file);
    previewVideoPlayer.src = videoUrl;
    previewVideoPlayer.classList.remove('hidden');

    previewVideoPlayer.onloadedmetadata = () => {
      videoNaturalWidth = previewVideoPlayer.videoWidth || 1080;
      videoNaturalHeight = previewVideoPlayer.videoHeight || 1920;
      totalDuration = previewVideoPlayer.duration || totalDuration;
      timeScrubber.max = totalDuration;
      totalTimeEl.textContent = `${totalDuration.toFixed(2)}s`;

      // 1. Adapt stage box & canvas resolution to video's exact aspect ratio
      setStageAspectRatio(currentRatio, videoNaturalWidth, videoNaturalHeight);

      // 2. Ensure audio volume is unmuted and audible
      updateVolume(currentVolume > 0 ? currentVolume : 1.0, false);

      renderCurrentFrame();

      if (behindPersonEnabled) {
        runSegmentationOnCurrentMedia(true);
      }
    };

    previewVideoPlayer.onerror = (e) => {
      console.warn('Browser video element had issue decoding container preview, backend FFmpeg extraction continues:', e);
    };

    // Auto-start video audio extraction and caption generation IMMEDIATELY
    startVideoTranscription();
  }

  function setVideoStep(step, state, detailText) {
    const steps = {
      upload: stepUpload,
      extract: stepExtract,
      transcribe: stepTranscribe,
      segment: stepSegment
    };
    const stepKeys = ['upload', 'extract', 'transcribe', 'segment'];
    const curIdx = stepKeys.indexOf(step);

    stepKeys.forEach((key, idx) => {
      const el = steps[key];
      if (!el) return;
      el.classList.remove('active', 'completed', 'error');
      if (idx < curIdx) {
        el.classList.add('completed');
      } else if (idx === curIdx) {
        el.classList.add(state);
      }
    });

    if (state === 'error') {
      videoStatusSpinner.textContent = '❌';
      videoStatusTitle.textContent = 'Generation Failed';
      videoStatusDetail.textContent = detailText;
      retryVideoBtn.classList.remove('hidden');
    } else if (state === 'completed' && step === 'segment') {
      videoStatusSpinner.textContent = '✅';
      videoStatusTitle.textContent = 'Captions Ready!';
      videoStatusDetail.textContent = detailText || 'Captions generated successfully. Press Play to preview.';
      retryVideoBtn.classList.add('hidden');
    } else {
      videoStatusSpinner.textContent = '⏳';
      videoStatusTitle.textContent = 'Generating Captions...';
      videoStatusDetail.textContent = detailText;
      retryVideoBtn.classList.add('hidden');
    }
  }

  transcribeVideoBtn.addEventListener('click', () => {
    if (imageBlob && !videoBlob) {
      setVideoStep('upload', 'completed', `Image "${imageBlob.name}" loaded.`);
      setVideoStep('segment', 'completed', 'Captions active! Type in Text Mode or click any block on the left to edit text.');
      videoStatusSpinner.textContent = '👤';
      videoStatusTitle.textContent = 'Text Behind Person Active';
      videoStatusDetail.textContent = 'Images do not contain audio tracks. You can type words in Text Mode or edit existing blocks to position words behind the person!';
      return;
    }
    if (!videoBlob) return;
    startVideoTranscription();
  });

  async function startVideoTranscription() {
    videoProcessingStatus.classList.remove('hidden');
    transcribeVideoBtn.disabled = true;
    transcribeVideoBtn.classList.add('btn-loading');
    transcribeVideoBtnText.textContent = 'Processing Video...';

    try {
      setVideoStep('upload', 'active', `Uploading ${videoBlob.name} (${formatFileSize(videoBlob.size)}) to backend...`);

      const formData = new FormData();
      formData.append('video', videoBlob, videoBlob.name);
      formData.append('maxWords', videoMaxWordsSlider.value);

      setVideoStep('extract', 'active', 'Extracting 16kHz mono audio track via FFmpeg...');

      const response = await fetch('/api/caption/transcribe-video', {
        method: 'POST',
        body: formData
      });

      const result = await response.json();

      if (response.ok && result.success) {
        if (result.acousticData && acousticSummaryText && acousticSummaryPill) {
          const ac = result.acousticData;
          acousticSummaryText.textContent = `Praat Acoustics: Pitch avg ${ac.pitch?.meanHz || 0}Hz (peak ${ac.pitch?.maxHz || 0}Hz) • Loudness ${ac.intensity?.meanDb || 0}dB • ${ac.pauses?.count || 0} pauses (${ac.pauses?.totalDurationSeconds || 0}s)`;
          acousticSummaryPill.classList.remove('hidden');
        }

        // Connect extracted clean audio track to syncAudioPlayer so user reliably hears the audio
        if (result.audioUrl) {
          syncAudioPlayer.src = result.audioUrl;
          syncAudioPlayer.load();
          audioSynced = true;
          updateVolume(currentVolume > 0 ? currentVolume : 1.0, false);
        }

        if (!result.captionData || !result.captionData.blocks || result.captionData.blocks.length === 0) {
          setVideoStep('segment', 'completed', `⚠️ Audio track extracted (${result.wordCount} words recognized). No distinct spoken caption blocks detected. If the audio is quiet, check microphone levels.`);
          statusText.textContent = `⚠️ Video audio extracted, but no spoken caption words detected.`;
        } else {
          setVideoStep('transcribe', 'completed', `Transcribed ${result.wordCount} words with Praat acoustic emphasis (${result.language || 'auto'}).`);
          setVideoStep('segment', 'completed', `✅ Generated ${result.captionData.blocks.length} caption blocks! Press Play to preview with video.`);
          loadCaptionData(result.captionData.blocks, false);
          statusText.textContent = `✅ Transcribed video: ${result.captionData.blocks.length} blocks ready!`;
        }

        const effectiveDuration = Math.max(
          previewVideoPlayer.duration || 0,
          result.audioDuration || 0,
          totalDuration || 0
        );
        if (effectiveDuration > 0) {
          totalDuration = effectiveDuration;
          timeScrubber.max = totalDuration;
          totalTimeEl.textContent = `${totalDuration.toFixed(2)}s`;
        }
        return;
      }

      // If backend failed due to FFmpeg not being found on the system, run browser Web Audio API extraction fallback
      if (result.code === 'FFMPEG_NOT_FOUND' || response.status === 503) {
        console.warn('Backend FFmpeg not available — initiating native browser audio extraction fallback...');
        setVideoStep('extract', 'active', 'Host FFmpeg not found on PATH. Extracting audio in browser via Web Audio API...');

        const wavBlob = await extractAudioFromVideoFile(videoBlob);
        
        setVideoStep('transcribe', 'active', 'Sending browser-extracted 16kHz audio to Groq Whisper...');
        const audioFormData = new FormData();
        audioFormData.append('audio', wavBlob, 'extracted_audio.wav');
        audioFormData.append('maxWords', videoMaxWordsSlider.value);

        const audioRes = await fetch('/api/caption/transcribe-audio', {
          method: 'POST',
          body: audioFormData
        });

        const audioResult = await audioRes.json();
        if (!audioRes.ok || !audioResult.success) {
          throw new Error(audioResult.details || audioResult.error || 'Audio transcription failed');
        }

        setVideoStep('segment', 'completed', `✅ Generated ${audioResult.captionData.blocks.length} caption blocks via browser audio extraction!`);
        loadCaptionData(audioResult.captionData.blocks, false);
        if (previewVideoPlayer.duration > 0) {
          totalDuration = previewVideoPlayer.duration;
          timeScrubber.max = totalDuration;
          totalTimeEl.textContent = `${totalDuration.toFixed(2)}s`;
        }
        statusText.textContent = `✅ Transcribed video: ${audioResult.captionData.blocks.length} blocks ready!`;
        return;
      }

      // Handle specific backend errors
      if (result.code === 'NO_AUDIO_STREAM') {
        throw new Error('The uploaded video does not contain an audio stream. Please upload a video with spoken audio.');
      } else if (result.code === 'CORRUPTED_VIDEO') {
        throw new Error('The uploaded video appears corrupted or is an invalid video file.');
      } else if (result.code === 'EMPTY_AUDIO') {
        throw new Error('Extracted audio contains no audible sound.');
      } else {
        throw new Error(result.error || result.details || 'Video processing failed');
      }

    } catch (err) {
      console.error('Video transcription error:', err);
      setVideoStep('extract', 'error', `Error: ${err.message}`);
    } finally {
      transcribeVideoBtn.disabled = false;
      transcribeVideoBtn.classList.remove('btn-loading');
      transcribeVideoBtnText.textContent = '⚡ Extract Audio & Generate Captions';
    }
  }

  // Helper: Client-side Web Audio 16kHz mono WAV extraction fallback
  async function extractAudioFromVideoFile(file) {
    const arrayBuffer = await file.arrayBuffer();
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new AudioContextClass();
    try {
      const decodedBuffer = await audioCtx.decodeAudioData(arrayBuffer);
      return audioBufferToWav(decodedBuffer, 16000);
    } finally {
      audioCtx.close().catch(() => {});
    }
  }

  function audioBufferToWav(buffer, optSampleRate = 16000) {
    const originalData = buffer.getChannelData(0);
    const sampleRate = optSampleRate;
    let samples;
    if (buffer.sampleRate === sampleRate) {
      samples = originalData;
    } else {
      const ratio = buffer.sampleRate / sampleRate;
      const newLength = Math.round(originalData.length / ratio);
      samples = new Float32Array(newLength);
      for (let i = 0; i < newLength; i++) {
        const origIdx = Math.floor(i * ratio);
        samples[i] = originalData[origIdx] || 0;
      }
    }

    const numChannels = 1;
    const bytesPerSample = 2;
    const blockAlign = numChannels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;
    const dataSize = samples.length * bytesPerSample;
    const wavBuffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(wavBuffer);

    function writeString(v, off, str) {
      for (let i = 0; i < str.length; i++) v.setUint8(off + i, str.charCodeAt(i));
    }

    writeString(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeString(view, 8, 'WAVE');
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, 'data');
    view.setUint32(40, dataSize, true);

    let offset = 44;
    for (let i = 0; i < samples.length; i++, offset += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
    }

    return new Blob([wavBuffer], { type: 'audio/wav' });
  }

  // ─── Shared Caption Loader ─────────────────────────────────────────────────
  function loadCaptionData(blocks, fromAudio = false) {
    captionData.blocks = blocks;
    totalDuration = blocks.length > 0 ? blocks[blocks.length - 1].end : 0;
    timeScrubber.max = totalDuration;
    totalTimeEl.textContent = `${totalDuration.toFixed(2)}s`;
    currentTime = 0.0;
    timeScrubber.value = 0;
    audioSynced = fromAudio;
    renderBlocksSidebar();
    renderCurrentFrame();
  }

  // ─── Block Sidebar ─────────────────────────────────────────────────────────
  function renderBlocksSidebar() {
    const blocksList = document.getElementById('blocksList');
    const blockCount = document.getElementById('blockCount');
    blocksList.innerHTML = '';
    blockCount.textContent = captionData.blocks.length;

    if (captionData.blocks.length === 0) {
      blocksList.innerHTML = `<div class="empty-state"><p>No caption blocks yet.<br>Generate text or transcribe audio above.</p></div>`;
      return;
    }

    captionData.blocks.forEach((block, index) => {
      const card = document.createElement('div');
      card.className = 'block-card';
      card.dataset.id = block.id;

      card.innerHTML = `
        <span class="block-index">#${index + 1}</span>
        <input type="text" class="block-input" value="${block.text.replace(/"/g, '&quot;')}" />
        ${block.start !== undefined ? `<span class="block-timing">${block.start.toFixed(1)}s</span>` : ''}
        <div class="block-actions">
          <button class="btn-icon split-btn" title="Split Block">✂️</button>
          <button class="btn-icon delete-btn" title="Delete Block">🗑️</button>
        </div>
      `;

      const inputEl = card.querySelector('.block-input');
      inputEl.addEventListener('input', (e) => {
        const newText = e.target.value;
        block.text = newText.toUpperCase();
        const words = newText.trim().split(/\s+/);
        const dur = (block.end - block.start) / Math.max(words.length, 1);
        block.words = words.map((w, i) => ({
          word: w.toUpperCase(),
          start: parseFloat((block.start + i * dur).toFixed(2)),
          end: parseFloat((block.start + (i + 1) * dur).toFixed(2))
        }));
        renderCurrentFrame();
      });

      card.querySelector('.split-btn').addEventListener('click', () => splitBlock(index));
      card.querySelector('.delete-btn').addEventListener('click', () => {
        captionData.blocks.splice(index, 1);
        renderBlocksSidebar();
        renderCurrentFrame();
      });

      blocksList.appendChild(card);
    });
  }

  function splitBlock(index) {
    const b = captionData.blocks[index];
    if (!b.words || b.words.length <= 1) { alert('Need at least 2 words to split.'); return; }
    const mid = Math.floor(b.words.length / 2);
    const p1 = b.words.slice(0, mid);
    const p2 = b.words.slice(mid);
    captionData.blocks.splice(index, 1,
      { id: b.id, text: p1.map(w => w.word).join(' '), start: p1[0].start, end: p1[p1.length - 1].end, words: p1 },
      { id: `block_${Date.now()}`, text: p2.map(w => w.word).join(' '), start: p2[0].start, end: p2[p2.length - 1].end, words: p2 }
    );
    renderBlocksSidebar();
    renderCurrentFrame();
  }

  // ─── 3D Text Behind Subject / Person (MediaPipe Selfie Segmentation) ────────
  let isLoadingSegmentationScript = false;
  async function initSelfieSegmentation() {
    if (selfieSegmentation) return;
    if (typeof window.SelfieSegmentation === 'undefined') {
      if (isLoadingSegmentationScript) return;
      isLoadingSegmentationScript = true;
      try {
        await new Promise((resolve) => {
          const s = document.createElement('script');
          s.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/selfie_segmentation/selfie_segmentation.js';
          s.crossOrigin = 'anonymous';
          s.onload = () => resolve();
          s.onerror = () => {
            console.warn('Failed to load MediaPipe SelfieSegmentation CDN script.');
            resolve();
          };
          document.head.appendChild(s);
        });
      } finally {
        isLoadingSegmentationScript = false;
      }
    }

    if (typeof window.SelfieSegmentation === 'undefined') return;

    try {
      selfieSegmentation = new window.SelfieSegmentation({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/selfie_segmentation/${file}`
      });
      selfieSegmentation.setOptions({
        modelSelection: 0, // 0: General model (256x256), ideal for portrait/vertical reels & standing people
        selfieMode: false
      });
      selfieSegmentation.onResults(onSegmentationResults);
      console.log('✅ MediaPipe SelfieSegmentation initialized.');
    } catch (err) {
      console.warn('MediaPipe SelfieSegmentation init failed:', err);
    }
  }

  let hasAutoPositionedPerson = false;
  let lastDetectedHeadTop = null;
  function detectPersonAnchor(maskSource) {
    try {
      const offCanvas = document.createElement('canvas');
      const w = 64, h = 64;
      offCanvas.width = w; offCanvas.height = h;
      const oCtx = offCanvas.getContext('2d');
      oCtx.drawImage(maskSource, 0, 0, w, h);
      const data = oCtx.getImageData(0, 0, w, h).data;

      let minX = w, maxX = 0, minY = h, maxY = 0;
      let totalX = 0, count = 0;

      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const idx = (y * w + x) * 4;
          if (data[idx] > 70 || data[idx + 3] > 70) {
            count++;
            totalX += x;
            if (x < minX) minX = x;
            if (x > maxX) maxX = x;
            if (y < minY) minY = y;
            if (y > maxY) maxY = y;
          }
        }
      }

      if (count < 10) return null;

      const normHeadTop = minY / h;
      lastDetectedHeadTop = normHeadTop;
      const normPersonHeight = (maxY - minY) / h;

      let targetX = 0.50;
      let targetY = 0.18;
      let targetScale = 1.0;

      // Smart readable positioning:
      // If there is open background space above the person's head (normHeadTop >= 0.15):
      // Place the text directly in the clear space above the head so NO words are blocked!
      if (normHeadTop >= 0.15) {
        targetY = Math.max(0.10, normHeadTop - 0.10);
        targetX = 0.50;
        targetScale = 1.0;
      } else {
        // Head is close to top -> place behind shoulders and scale so words extend into left/right margins
        targetY = Math.min(0.68, normHeadTop + normPersonHeight * 0.45);
        targetScale = 1.15;
      }

      return {
        normX: parseFloat(targetX.toFixed(2)),
        normY: parseFloat(targetY.toFixed(2)),
        scale: targetScale
      };
    } catch (_) {
      return null;
    }
  }

  function onSegmentationResults(results) {
    isSegmenting = false;
    if (!personCutoutCanvas || !behindPersonEnabled) {
      return;
    }

    const renW = renderer.width || 1080;
    const renH = renderer.height || 1920;

    if (!latestMaskCanvas) {
      latestMaskCanvas = document.createElement('canvas');
    }
    if (latestMaskCanvas.width !== renW || latestMaskCanvas.height !== renH) {
      latestMaskCanvas.width = renW;
      latestMaskCanvas.height = renH;
    }

    const mCtx = latestMaskCanvas.getContext('2d');
    mCtx.clearRect(0, 0, renW, renH);
    mCtx.drawImage(results.segmentationMask, 0, 0, renW, renH);
    hasValidMask = true;

    // Auto-detect person position so captions sit in open space and are NOT blocked
    if (!hasAutoPositionedPerson && behindPersonEnabled) {
      const anchor = detectPersonAnchor(latestMaskCanvas);
      if (anchor) {
        captionData.layout.x = parseFloat(anchor.normX.toFixed(2));
        captionData.layout.y = parseFloat(anchor.normY.toFixed(2));
        if (anchor.scale) captionData.layout.scale = anchor.scale;
        hasAutoPositionedPerson = true;
        renderCurrentFrame();
      }
    }

    drawPersonCutout();
  }

  function drawPersonCutout() {
    if (!behindPersonEnabled || !hasValidMask || !personCutoutCanvas || !latestMaskCanvas) {
      return;
    }

    const renW = renderer.width || 1080;
    const renH = renderer.height || 1920;

    if (personCutoutCanvas.width !== renW || personCutoutCanvas.height !== renH) {
      personCutoutCanvas.width = renW;
      personCutoutCanvas.height = renH;
    }

    let mediaSource = null;
    if (previewVideoPlayer && !previewVideoPlayer.classList.contains('hidden') && previewVideoPlayer.videoWidth > 0) {
      mediaSource = previewVideoPlayer;
    } else if (previewImagePlayer && !previewImagePlayer.classList.contains('hidden') && previewImagePlayer.naturalWidth > 0) {
      mediaSource = previewImagePlayer;
    }

    if (!mediaSource) return;

    const pCtx = personCutoutCanvas.getContext('2d');
    pCtx.save();
    pCtx.clearRect(0, 0, renW, renH);

    // 1. Draw segmentation alpha mask
    pCtx.drawImage(latestMaskCanvas, 0, 0, renW, renH);

    // 2. Composite source-in: retain only foreground pixels overlapping the person mask
    pCtx.globalCompositeOperation = 'source-in';

    // 3. Draw LIVE current media source (previewVideoPlayer or previewImagePlayer)
    // CRITICAL FIX: Drawing directly from the live media element at the EXACT current moment
    // ensures the foreground cutout aligns 1:1 with the underlying video with 0ms temporal lag.
    // This completely eliminates ghosting, jitter, and the double-person shaking artifact!
    pCtx.drawImage(mediaSource, 0, 0, renW, renH);

    pCtx.restore();
  }

  async function runSegmentationOnCurrentMedia(force = false) {
    if (!behindPersonEnabled) return;
    initSelfieSegmentation();
    if (!selfieSegmentation || isSegmenting) return;

    const now = performance.now();
    // Throttle inference during playback to ~8 FPS to prevent GPU overload and video buffering
    if (!force && isPlaying && (now - lastSegmentationTime < SEGMENTATION_INTERVAL_MS)) {
      return;
    }

    let mediaSource = null;
    if (previewVideoPlayer && !previewVideoPlayer.classList.contains('hidden') && previewVideoPlayer.videoWidth > 0) {
      mediaSource = previewVideoPlayer;
    } else if (previewImagePlayer && !previewImagePlayer.classList.contains('hidden') && previewImagePlayer.naturalWidth > 0) {
      mediaSource = previewImagePlayer;
    }

    if (!mediaSource) return;

    isSegmenting = true;
    lastSegmentationTime = now;
    try {
      await selfieSegmentation.send({ image: mediaSource });
    } catch (e) {
      isSegmenting = false;
    }
  }

  function setBehindPersonMode(enable, isUserAction = false) {
    behindPersonEnabled = enable;
    if (isUserAction) {
      userExplicitlyEnabledDepth = enable;
    }

    if (depthInFrontBtn) {
      depthInFrontBtn.classList.toggle('active', !enable);
    }
    if (depthBehindPersonBtn) {
      depthBehindPersonBtn.classList.toggle('active', enable);
    }
    if (toggleBehindPersonBtn) {
      toggleBehindPersonBtn.classList.toggle('active', enable);
    }
    if (depthPositionRow) {
      depthPositionRow.classList.toggle('hidden', !enable);
    }

    if (personCutoutCanvas) {
      personCutoutCanvas.classList.toggle('hidden', !enable);
      if (!enable) {
        const pCtx = personCutoutCanvas.getContext('2d');
        pCtx.clearRect(0, 0, personCutoutCanvas.width, personCutoutCanvas.height);
        hasValidMask = false;
        latestMaskCanvas = null;
      }
    }

    if (enable) {
      // If caption is currently right behind face (between 0.35 and 0.60), adjust to readable open space (above head)
      if (captionData.layout.y >= 0.35 && captionData.layout.y <= 0.60) {
        captionData.layout.y = (lastDetectedHeadTop !== null && lastDetectedHeadTop >= 0.15) 
          ? Math.max(0.10, parseFloat((lastDetectedHeadTop - 0.10).toFixed(2)))
          : 0.18;
      }
      initSelfieSegmentation();
      runSegmentationOnCurrentMedia(true);
    }
    renderCurrentFrame();
  }

  if (posAboveHeadBtn) {
    posAboveHeadBtn.addEventListener('click', () => {
      posAboveHeadBtn.classList.add('active');
      if (posShouldersBtn) posShouldersBtn.classList.remove('active');
      captionData.layout.y = (lastDetectedHeadTop !== null && lastDetectedHeadTop >= 0.15)
        ? Math.max(0.10, parseFloat((lastDetectedHeadTop - 0.10).toFixed(2)))
        : 0.18;
      captionData.layout.x = 0.50;
      captionData.layout.scale = 1.0;
      renderCurrentFrame();
    });
  }

  if (posShouldersBtn) {
    posShouldersBtn.addEventListener('click', () => {
      posShouldersBtn.classList.add('active');
      if (posAboveHeadBtn) posAboveHeadBtn.classList.remove('active');
      captionData.layout.y = 0.52;
      captionData.layout.x = 0.50;
      captionData.layout.scale = 1.15;
      renderCurrentFrame();
    });
  }

  if (depthInFrontBtn) {
    depthInFrontBtn.addEventListener('click', () => {
      setBehindPersonMode(false, true);
    });
  }
  if (depthBehindPersonBtn) {
    depthBehindPersonBtn.addEventListener('click', () => {
      setBehindPersonMode(true, true);
    });
  }
  if (toggleBehindPersonBtn) {
    toggleBehindPersonBtn.addEventListener('click', () => {
      setBehindPersonMode(!behindPersonEnabled, true);
    });
  }

  // ─── Style Preset Selection & Offscreen Canvas Thumbnails ───────────────────────
  const presetBtns = document.querySelectorAll('.preset-btn');
  
  function applyPresetThumbnails() {
    try {
      const thumbs = renderer.generatePresetThumbnails();
      presetBtns.forEach(btn => {
        const styleId = btn.getAttribute('data-style');
        if (thumbs[styleId]) {
          btn.style.backgroundImage = `url("${thumbs[styleId]}")`;
        }
      });
    } catch (e) {
      console.warn('Could not generate preset thumbnails:', e);
    }
  }

  // Generate thumbnails after fonts load
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(applyPresetThumbnails);
  } else {
    setTimeout(applyPresetThumbnails, 500);
  }

  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      presetBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      
      const chosenStyle = btn.getAttribute('data-style');
      const prevStyle = captionData.styleId;
      captionData.styleId = chosenStyle;

      if (chosenStyle === 'behind-person') {
        captionData.layout.rotation = 0;
        captionData.layout.y = (lastDetectedHeadTop !== null && lastDetectedHeadTop >= 0.15)
          ? Math.max(0.10, parseFloat((lastDetectedHeadTop - 0.10).toFixed(2)))
          : 0.18;
        captionData.layout.scale = 1.0;
        setBehindPersonMode(true, false);
      } else {
        // If transitioning away from behind-person preset, return to In Front unless user explicitly turned on Behind Person
        if (prevStyle === 'behind-person' && !userExplicitlyEnabledDepth) {
          setBehindPersonMode(false, false);
        }
        // Transparent presets and capsule looks best at 0 deg rotation
        if (chosenStyle === 'leafy-circle' || chosenStyle === 'botanical-capsule' || chosenStyle === 'create-every-day' || chosenStyle === 'word-pop-green' || chosenStyle === 'pretty-pretty-girl' || chosenStyle === 'fit-check' || chosenStyle === 'ransom-note' || chosenStyle === 'minimal-script') {
          captionData.layout.rotation = 0;
        } else {
          captionData.layout.rotation = -6;
        }
      }

      // Toggle checkerboard stage background for transparent presets
      const isTransparent = chosenStyle === 'create-every-day' || chosenStyle === 'word-pop-green' || chosenStyle === 'pretty-pretty-girl' || chosenStyle === 'fit-check' || chosenStyle === 'ransom-note' || chosenStyle === 'minimal-script' || chosenStyle === 'behind-person';
      stageBox.classList.toggle('transparent-preset', isTransparent);
      
      renderCurrentFrame();
    });
  });

  // ─── Layout & Sticker Controls ────────────────────────────────────────────────────────
  scaleSlider.addEventListener('input', (e) => {
    const scale = parseFloat(e.target.value);
    scaleVal.textContent = `${scale.toFixed(2)}x`;
    
    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId === 'caption') {
      captionData.layout.scale = scale;
    } else {
      const el = captionData.elements.find(item => item.id === selectedId);
      if (el) {
        el.scale = scale;
      }
    }
    renderCurrentFrame();
  });

  centerBtn.addEventListener('click', () => {
    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId === 'caption') {
      captionData.layout.x = 0.5;
      captionData.layout.y = 0.52;
    } else {
      const el = captionData.elements.find(item => item.id === selectedId);
      if (el) {
        el.x = 0.5;
        el.y = 0.35;
      }
    }
    renderCurrentFrame();
  });

  // Selection manager
  function selectItem(itemId) {
    captionData.selectedItemId = itemId;
    const isSticker = itemId && itemId.startsWith('el_');

    if (!isSticker) {
      // Caption selected — show caption scale, hide sticker controls
      scaleSlider.value = captionData.layout.scale;
      scaleVal.textContent = `${captionData.layout.scale.toFixed(2)}x`;
      elementControls.classList.add('hidden');
      canvaDeleteBadge.classList.add('hidden');
    } else {
      const el = captionData.elements.find(item => item.id === itemId);
      if (el) {
        scaleSlider.value = el.scale || 1.0;
        scaleVal.textContent = `${(el.scale || 1.0).toFixed(2)}x`;
        elRotationSlider.value = el.rotation || 0;
        elRotationVal.textContent = `${el.rotation || 0}°`;
        elementControls.classList.remove('hidden');
        canvaDeleteBadge.classList.remove('hidden');
      }
    }
    renderCurrentFrame();
  }

  // Canvas delete badge — direct delete on the stage
  canvaDeleteBadge.addEventListener('click', (e) => {
    e.stopPropagation();
    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId && selectedId.startsWith('el_')) {
      captionData.elements = captionData.elements.filter(el => el.id !== selectedId);
      selectItem('caption');
    }
  });

  // Search bar filtering
  elementSearch.addEventListener('input', (e) => {
    const query = e.target.value.trim().toLowerCase();
    const allBtns = elementsGrid.querySelectorAll('.element-btn');
    allBtns.forEach(btn => {
      const label = (btn.textContent || '').toLowerCase();
      const type  = (btn.getAttribute('data-type') || '').toLowerCase();
      const visible = !query || label.includes(query) || type.includes(query);
      btn.style.display = visible ? '' : 'none';
    });
  });

  elementSearch.addEventListener('focus', () => {
    elementSearch.style.borderColor = 'rgba(139, 92, 246, 0.6)';
  });
  elementSearch.addEventListener('blur', () => {
    elementSearch.style.borderColor = 'rgba(255, 255, 255, 0.15)';
  });

  // Click on stage selection handler
  stageBox.addEventListener('mousedown', (e) => {
    if (e.target.classList.contains('canva-handle')) return;
    
    const rect = stageBox.getBoundingClientRect();
    const clickX = (e.clientX - rect.left) / rect.width;
    const clickY = (e.clientY - rect.top) / rect.height;

    // 1. Check stickers
    let foundElement = null;
    if (captionData.elements && captionData.elements.length > 0) {
      for (let el of captionData.elements) {
        const dist = Math.hypot(el.x - clickX, el.y - clickY);
        if (dist < 0.08) {
          foundElement = el;
          break;
        }
      }
    }

    if (foundElement) {
      selectItem(foundElement.id);
    } else {
      // 2. Check caption center
      const capDist = Math.hypot(captionData.layout.x - clickX, captionData.layout.y - clickY);
      if (capDist < 0.15) {
        selectItem('caption');
      }
    }
  });

  // Adding stickers handler
  const elementBtns = document.querySelectorAll('.element-btn');
  elementBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.getAttribute('data-type');
      const newId = `el_${Date.now()}_${Math.random().toString(36).substr(2, 4)}`;
      
      const newSticker = {
        id: newId,
        type: type,
        x: 0.5,
        y: 0.35,
        scale: 1.0,
        rotation: 0
      };
      
      if (!captionData.elements) {
        captionData.elements = [];
      }
      captionData.elements.push(newSticker);
      selectItem(newId);
    });
  });

  // Deleting sticker handler
  deleteElementBtn.addEventListener('click', () => {
    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId && selectedId.startsWith('el_')) {
      captionData.elements = captionData.elements.filter(el => el.id !== selectedId);
      selectItem('caption');
    }
  });

  // Rotating sticker handler
  elRotationSlider.addEventListener('input', (e) => {
    const deg = parseInt(e.target.value, 10);
    elRotationVal.textContent = `${deg}°`;
    
    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId && selectedId.startsWith('el_')) {
      const el = captionData.elements.find(item => item.id === selectedId);
      if (el) {
        el.rotation = deg;
      }
    }
    renderCurrentFrame();
  });

  toggleSafeZoneBtn.addEventListener('click', () => {
    toggleSafeZoneBtn.classList.toggle('active');
    safeZoneOverlay.classList.toggle('hidden');
  });

  // ─── Playback ───────────────────────────────────────────────────────────────
  playPauseBtn.addEventListener('click', () => {
    isPlaying ? pausePlayback() : startPlayback();
  });

  resetBtn.addEventListener('click', () => {
    pausePlayback();
    currentTime = 0.0;
    timeScrubber.value = 0;
    if (currentMode === 'video' && previewVideoPlayer.src) {
      previewVideoPlayer.currentTime = 0;
    }
    syncAudioPlayer.currentTime = 0;
    renderCurrentFrame();
    if (behindPersonEnabled) {
      runSegmentationOnCurrentMedia();
    }
  });

  timeScrubber.addEventListener('input', (e) => {
    currentTime = parseFloat(e.target.value);
    if (currentMode === 'video' && previewVideoPlayer.src) {
      previewVideoPlayer.currentTime = currentTime;
    } else if (audioSynced) {
      syncAudioPlayer.currentTime = currentTime;
    }
    renderCurrentFrame();
    if (behindPersonEnabled) {
      runSegmentationOnCurrentMedia();
    }
  });

  function startPlayback() {
    const videoDur = (currentMode === 'video' && previewVideoPlayer.duration && !isNaN(previewVideoPlayer.duration)) ? previewVideoPlayer.duration : 0;
    const audioDur = (syncAudioPlayer.duration && !isNaN(syncAudioPlayer.duration)) ? syncAudioPlayer.duration : 0;
    const effectiveTotal = Math.max(totalDuration, videoDur, audioDur);

    if (effectiveTotal <= 0 && (!previewVideoPlayer.src || currentMode !== 'video') && !syncAudioPlayer.src) return;
    if (totalDuration <= 0 && effectiveTotal > 0) {
      totalDuration = effectiveTotal;
      timeScrubber.max = totalDuration;
      totalTimeEl.textContent = `${totalDuration.toFixed(2)}s`;
    }

    if (currentTime >= totalDuration) currentTime = 0.0;
    isPlaying = true;
    playIcon.textContent = '⏸';

    if (currentMode === 'video' && previewVideoPlayer.src) {
      previewVideoPlayer.currentTime = currentTime;
      previewVideoPlayer.muted = isMuted;
      previewVideoPlayer.volume = isMuted ? 0 : currentVolume;
      previewVideoPlayer.play().catch(e => console.warn('Video play interrupted:', e));

      // Also sync and play audio track via syncAudioPlayer if available
      if (syncAudioPlayer.src && audioSynced) {
        syncAudioPlayer.currentTime = currentTime;
        syncAudioPlayer.muted = isMuted;
        syncAudioPlayer.volume = isMuted ? 0 : currentVolume;
        syncAudioPlayer.play().catch(e => console.warn('Sync audio play interrupted:', e));
      }
    } else if (audioSynced || syncAudioPlayer.src) {
      syncAudioPlayer.currentTime = currentTime;
      syncAudioPlayer.muted = isMuted;
      syncAudioPlayer.volume = isMuted ? 0 : currentVolume;
      syncAudioPlayer.play().catch(e => console.warn('Audio play interrupted:', e));
    }

    lastTimestamp = performance.now();
    animFrameId = requestAnimationFrame(playbackLoop);
  }

  function pausePlayback() {
    isPlaying = false;
    playIcon.textContent = '▶';
    if (animFrameId) cancelAnimationFrame(animFrameId);
    if (currentMode === 'video') {
      previewVideoPlayer.pause();
    }
    syncAudioPlayer.pause();
  }

  function playbackLoop(timestamp) {
    if (!isPlaying) return;
    const delta = (timestamp - lastTimestamp) / 1000;
    lastTimestamp = timestamp;

    // Sync time to video or audio element if available (drift-free)
    if (currentMode === 'video' && !previewVideoPlayer.paused) {
      currentTime = previewVideoPlayer.currentTime;
      if (syncAudioPlayer.src && Math.abs(syncAudioPlayer.currentTime - currentTime) > 0.15) {
        syncAudioPlayer.currentTime = currentTime;
      }
    } else if ((audioSynced || syncAudioPlayer.src) && !syncAudioPlayer.paused) {
      currentTime = syncAudioPlayer.currentTime;
    } else {
      currentTime += delta;
    }

    if (currentTime >= totalDuration) {
      currentTime = totalDuration;
      pausePlayback();
    }

    timeScrubber.value = currentTime;
    renderCurrentFrame();

    // Run depth segmentation on new video frame throttled to ~8 FPS
    if (behindPersonEnabled && currentMode === 'video' && !previewVideoPlayer.paused) {
      runSegmentationOnCurrentMedia(false);
    }

    if (isPlaying) animFrameId = requestAnimationFrame(playbackLoop);
  }

  // ─── Frame Render + Canva Handle Sync ──────────────────────────────────────
  function renderCurrentFrame() {
    currentTimeEl.textContent = `${currentTime.toFixed(2)}s`;
    const boxMeta = renderer.render(captionData, currentTime);

    if (boxMeta) {
      const stageRect = stageBox.getBoundingClientRect();
      const sw = stageRect.width;
      const sh = stageRect.height;
      const renW = renderer.width || 1080;
      const renH = renderer.height || 1920;
      const handleW = boxMeta.widthPx  * (sw / renW);
      const handleH = boxMeta.heightPx * (sh / renH);
      const handleX = boxMeta.normX * sw - handleW / 2;
      const handleY = boxMeta.normY * sh - handleH / 2;
      const rotation = boxMeta.rotation !== undefined ? boxMeta.rotation : captionData.layout.rotation;

      canvaBoundingBox.style.cssText = `
        width:${handleW}px; height:${handleH}px;
        left:${handleX}px; top:${handleY}px;
        transform:rotate(${rotation}deg);
        display:flex;
      `;
    } else {
      canvaBoundingBox.style.display = 'none';
    }

    // If depth Behind-Person mode is enabled and mask is available, draw live person cutout
    if (behindPersonEnabled && hasValidMask && personCutoutCanvas && !personCutoutCanvas.classList.contains('hidden')) {
      drawPersonCutout();
    }

    const activeBlock = captionData.blocks.find(b => currentTime >= b.start && currentTime <= b.end);
    document.querySelectorAll('.block-card').forEach(card => {
      card.classList.toggle('active-playing', !!(activeBlock && card.dataset.id === activeBlock.id));
    });
  }

  // Update depth cutout on video seek
  previewVideoPlayer.addEventListener('seeked', () => {
    renderCurrentFrame();
    if (behindPersonEnabled) {
      runSegmentationOnCurrentMedia(true);
    }
  });

  // ─── Canva Drag & Resize Engine ─────────────────────────────────────────────
  let isDragging = false, isResizing = false;
  let dragStartX = 0, dragStartY = 0, initNX = 0.5, initNY = 0.52, initScale = 1.0;
  let boxCenterX = 0, boxCenterY = 0, initDist = 1;

  canvaBoundingBox.addEventListener('mousedown', (e) => {
    // 1. Resize Handle dragging
    if (e.target.classList.contains('canva-handle')) {
      isResizing = true;
      const selectedId = captionData.selectedItemId || 'caption';
      if (selectedId === 'caption') {
        initScale = captionData.layout.scale;
      } else {
        const el = captionData.elements.find(item => item.id === selectedId);
        if (el) initScale = el.scale || 1.0;
      }

      const rect = canvaBoundingBox.getBoundingClientRect();
      boxCenterX = rect.left + rect.width / 2;
      boxCenterY = rect.top + rect.height / 2;
      initDist = Math.hypot(e.clientX - boxCenterX, e.clientY - boxCenterY) || 1;

      e.preventDefault();
      e.stopPropagation();
      return;
    }

    // 2. Element Position dragging
    isDragging = true;
    canvaBoundingBox.classList.add('dragging');
    dragStartX = e.clientX; dragStartY = e.clientY;

    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId === 'caption') {
      initNX = captionData.layout.x; initNY = captionData.layout.y;
    } else {
      const el = captionData.elements.find(item => item.id === selectedId);
      if (el) {
        initNX = el.x; initNY = el.y;
      }
    }
    e.preventDefault();
  });

  window.addEventListener('mousemove', (e) => {
    // Handle resizing - distance ratio scaling
    if (isResizing) {
      const currentDist = Math.hypot(e.clientX - boxCenterX, e.clientY - boxCenterY);
      const scaleRatio = currentDist / initDist;
      const newScale = parseFloat(Math.max(0.3, Math.min(3.5, initScale * scaleRatio)).toFixed(2));
      
      const selectedId = captionData.selectedItemId || 'caption';
      if (selectedId === 'caption') {
        captionData.layout.scale = newScale;
      } else {
        const el = captionData.elements.find(item => item.id === selectedId);
        if (el) el.scale = newScale;
      }
      scaleSlider.value = newScale;
      scaleVal.textContent = `${newScale.toFixed(2)}x`;
      renderCurrentFrame();
      return;
    }

    // Handle position dragging
    if (!isDragging) return;
    const r = stageBox.getBoundingClientRect();
    const newNX = parseFloat(Math.max(0.05, Math.min(0.95, initNX + (e.clientX - dragStartX) / r.width)).toFixed(3));
    const newNY = parseFloat(Math.max(0.05, Math.min(0.95, initNY + (e.clientY - dragStartY) / r.height)).toFixed(3));

    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId === 'caption') {
      captionData.layout.x = newNX;
      captionData.layout.y = newNY;
    } else {
      const el = captionData.elements.find(item => item.id === selectedId);
      if (el) {
        el.x = newNX;
        el.y = newNY;
      }
    }
    renderCurrentFrame();
  });

  window.addEventListener('mouseup', () => {
    if (isDragging) { isDragging = false; canvaBoundingBox.classList.remove('dragging'); }
    if (isResizing) { isResizing = false; }
  });

  canvaBoundingBox.addEventListener('touchstart', (e) => {
    if (e.touches.length !== 1) return;
    
    // Resize Handle touch
    if (e.target.classList.contains('canva-handle')) {
      isResizing = true;
      const selectedId = captionData.selectedItemId || 'caption';
      if (selectedId === 'caption') {
        initScale = captionData.layout.scale;
      } else {
        const el = captionData.elements.find(item => item.id === selectedId);
        if (el) initScale = el.scale || 1.0;
      }
      const rect = canvaBoundingBox.getBoundingClientRect();
      boxCenterX = rect.left + rect.width / 2;
      boxCenterY = rect.top + rect.height / 2;
      initDist = Math.hypot(e.touches[0].clientX - boxCenterX, e.touches[0].clientY - boxCenterY) || 1;
      e.stopPropagation();
      return;
    }

    // Position drag touch
    isDragging = true;
    canvaBoundingBox.classList.add('dragging');
    dragStartX = e.touches[0].clientX; dragStartY = e.touches[0].clientY;

    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId === 'caption') {
      initNX = captionData.layout.x; initNY = captionData.layout.y;
    } else {
      const el = captionData.elements.find(item => item.id === selectedId);
      if (el) {
        initNX = el.x; initNY = el.y;
      }
    }
  });

  window.addEventListener('touchmove', (e) => {
    if (e.touches.length !== 1) return;

    if (isResizing) {
      const currentDist = Math.hypot(e.touches[0].clientX - boxCenterX, e.touches[0].clientY - boxCenterY);
      const scaleRatio = currentDist / initDist;
      const newScale = parseFloat(Math.max(0.3, Math.min(3.5, initScale * scaleRatio)).toFixed(2));
      
      const selectedId = captionData.selectedItemId || 'caption';
      if (selectedId === 'caption') {
        captionData.layout.scale = newScale;
      } else {
        const el = captionData.elements.find(item => item.id === selectedId);
        if (el) el.scale = newScale;
      }
      scaleSlider.value = newScale;
      scaleVal.textContent = `${newScale.toFixed(2)}x`;
      renderCurrentFrame();
      return;
    }

    if (!isDragging) return;
    const r = stageBox.getBoundingClientRect();
    const newNX = parseFloat(Math.max(0.05, Math.min(0.95, initNX + (e.touches[0].clientX - dragStartX) / r.width)).toFixed(3));
    const newNY = parseFloat(Math.max(0.05, Math.min(0.95, initNY + (e.touches[0].clientY - dragStartY) / r.height)).toFixed(3));

    const selectedId = captionData.selectedItemId || 'caption';
    if (selectedId === 'caption') {
      captionData.layout.x = newNX;
      captionData.layout.y = newNY;
    } else {
      const el = captionData.elements.find(item => item.id === selectedId);
      if (el) {
        el.x = newNX;
        el.y = newNY;
      }
    }
    renderCurrentFrame();
  });

  window.addEventListener('touchend', () => {
    isDragging = false;
    isResizing = false;
    canvaBoundingBox.classList.remove('dragging');
  });

  // ─── Export & Import ────────────────────────────────────────────────────────
  const importJsonBtn = document.getElementById('importJsonBtn');
  const importJsonInput = document.getElementById('importJsonInput');
  const exportVideoBtn = document.getElementById('exportVideoBtn');

  importJsonBtn.addEventListener('click', () => importJsonInput.click());

  importJsonInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      try {
        const imported = JSON.parse(evt.target.result);
        if (imported.blocks) {
          captionData = {
            ...captionData,
            ...imported
          };
          loadCaptionData(captionData.blocks, false);
          if (captionData.styleId) {
            const btn = document.querySelector(`.preset-btn[data-style="${captionData.styleId}"]`);
            if (btn) btn.click();
          }
          statusText.textContent = `✅ Imported ${captionData.blocks.length} blocks successfully!`;
        } else {
          alert('Invalid caption JSON file structure.');
        }
      } catch (err) {
        alert('Failed to parse JSON file: ' + err.message);
      }
    };
    reader.readAsText(file);
  });

  exportJsonBtn.addEventListener('click', () => {
    const a = document.createElement('a');
    a.href = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(captionData, null, 2));
    a.download = `captions_${currentMode}_${Date.now()}.json`;
    a.click();
  });

  exportFrameBtn.addEventListener('click', () => {
    // Composite full 3D depth frame (background + captions + person cutout)
    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = renderer.width || 1080;
    exportCanvas.height = renderer.height || 1920;
    const eCtx = exportCanvas.getContext('2d');

    // 1. Draw media background if present
    if (previewVideoPlayer && !previewVideoPlayer.classList.contains('hidden') && previewVideoPlayer.videoWidth > 0) {
      eCtx.drawImage(previewVideoPlayer, 0, 0, exportCanvas.width, exportCanvas.height);
    } else if (previewImagePlayer && !previewImagePlayer.classList.contains('hidden') && previewImagePlayer.naturalWidth > 0) {
      eCtx.drawImage(previewImagePlayer, 0, 0, exportCanvas.width, exportCanvas.height);
    }

    // 2. Draw middle caption canvas
    eCtx.drawImage(canvas, 0, 0);

    // 3. Draw foreground person cutout if behind-person mode is active
    if (behindPersonEnabled && personCutoutCanvas && !personCutoutCanvas.classList.contains('hidden')) {
      eCtx.drawImage(personCutoutCanvas, 0, 0);
    }

    const a = document.createElement('a');
    a.href = exportCanvas.toDataURL('image/png');
    a.download = `caption_depth_frame_${currentTime.toFixed(2)}s.png`;
    a.click();
  });

  exportVideoBtn.addEventListener('click', async () => {
    if (!captionData.blocks || captionData.blocks.length === 0) {
      alert('Please generate or transcribe caption blocks first.');
      return;
    }

    if (!window.MediaRecorder) {
      alert('MediaRecorder is not supported in this browser.');
      return;
    }

    exportVideoBtn.disabled = true;
    const btnSpan = exportVideoBtn.querySelector('span');
    if (btnSpan) btnSpan.textContent = '🎬 Rendering Video...';

    pausePlayback();
    currentTime = 0.0;
    renderCurrentFrame();

    try {
      const stream = canvas.captureStream(60);
      const mimeType = MediaRecorder.isTypeSupported('video/webm;codecs=vp9')
        ? 'video/webm;codecs=vp9'
        : 'video/webm';

      const recorder = new MediaRecorder(stream, { mimeType });
      const chunks = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunks.push(e.data);
      };

      recorder.onstop = () => {
        const blob = new Blob(chunks, { type: mimeType });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `caption_video_${Date.now()}.webm`;
        a.click();
        exportVideoBtn.disabled = false;
        if (btnSpan) btnSpan.textContent = '🎥 Export Video';
        statusText.textContent = '✅ Animated caption video exported successfully!';
      };

      recorder.start();
      startPlayback();

      const checkInterval = setInterval(() => {
        if (!isPlaying || currentTime >= totalDuration) {
          clearInterval(checkInterval);
          recorder.stop();
        }
      }, 200);

    } catch (err) {
      console.error('Video export error:', err);
      alert('Video export failed: ' + err.message);
      exportVideoBtn.disabled = false;
      if (btnSpan) btnSpan.textContent = '🎥 Export Video';
    }
  });

  // ─── Utilities ─────────────────────────────────────────────────────────────
  function formatFileSize(bytes) {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  // ─── Init ──────────────────────────────────────────────────────────────────
  processTextAndGenerate();
});
