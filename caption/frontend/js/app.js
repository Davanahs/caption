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

  // Layout & Stage
  const scaleSlider       = document.getElementById('scaleSlider');
  const scaleVal          = document.getElementById('scaleVal');
  const centerBtn         = document.getElementById('centerBtn');
  const toggleSafeZoneBtn = document.getElementById('toggleSafeZoneBtn');
  const safeZoneOverlay   = document.getElementById('safeZoneOverlay');
  const canvaBoundingBox  = document.getElementById('canvaBoundingBox');
  const stageBox          = document.getElementById('stageBox');

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

  let currentMode   = 'text'; // 'text' | 'audio'
  let audioBlob     = null;   // stored audio file for sync playback
  let currentTime   = 0.0;
  let totalDuration = 0.0;
  let isPlaying     = false;
  let animFrameId   = null;
  let lastTimestamp = 0;
  let audioSynced   = false;  // true when audio mode is active & playing

  // ─── Mode Switching ────────────────────────────────────────────────────────
  tabTextMode.addEventListener('click', () => switchMode('text'));
  tabAudioMode.addEventListener('click', () => switchMode('audio'));

  function switchMode(mode) {
    currentMode = mode;
    pausePlayback();
    currentTime = 0.0;
    timeScrubber.value = 0;
    syncAudioPlayer.pause();
    syncAudioPlayer.currentTime = 0;

    if (mode === 'text') {
      tabTextMode.classList.add('active');
      tabAudioMode.classList.remove('active');
      textModeContainer.classList.remove('hidden');
      audioModeContainer.classList.add('hidden');
      panelModeTitle.textContent = '1. Script & Caption Blocks';
      panelModeTag.textContent = 'Text Engine';
      statusText.textContent = 'Phase 1: Text-to-Captions';
    } else {
      tabAudioMode.classList.add('active');
      tabTextMode.classList.remove('active');
      audioModeContainer.classList.remove('hidden');
      textModeContainer.classList.add('hidden');
      panelModeTitle.textContent = '1. Audio Transcription';
      panelModeTag.textContent = 'Groq Whisper STT';
      statusText.textContent = 'Phase 2: Audio STT';
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
      captionData.styleId = chosenStyle;

      // Transparent presets and capsule looks best at 0 deg rotation
      if (chosenStyle === 'leafy-circle' || chosenStyle === 'botanical-capsule' || chosenStyle === 'create-every-day' || chosenStyle === 'word-pop-green' || chosenStyle === 'pretty-pretty-girl' || chosenStyle === 'fit-check' || chosenStyle === 'ransom-note' || chosenStyle === 'minimal-script') {
        captionData.layout.rotation = 0;
      } else {
        captionData.layout.rotation = -6;
      }

      // Toggle checkerboard stage background for transparent presets
      const isTransparent = chosenStyle === 'create-every-day' || chosenStyle === 'word-pop-green' || chosenStyle === 'pretty-pretty-girl' || chosenStyle === 'fit-check' || chosenStyle === 'ransom-note' || chosenStyle === 'minimal-script';
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
    syncAudioPlayer.currentTime = 0;
    renderCurrentFrame();
  });

  timeScrubber.addEventListener('input', (e) => {
    currentTime = parseFloat(e.target.value);
    if (audioSynced) syncAudioPlayer.currentTime = currentTime;
    renderCurrentFrame();
  });

  function startPlayback() {
    if (totalDuration === 0) return;
    if (currentTime >= totalDuration) currentTime = 0.0;
    isPlaying = true;
    playIcon.textContent = '⏸';
    if (audioSynced) {
      syncAudioPlayer.currentTime = currentTime;
      syncAudioPlayer.play();
    }
    lastTimestamp = performance.now();
    animFrameId = requestAnimationFrame(playbackLoop);
  }

  function pausePlayback() {
    isPlaying = false;
    playIcon.textContent = '▶';
    if (animFrameId) cancelAnimationFrame(animFrameId);
    if (audioSynced) syncAudioPlayer.pause();
  }

  function playbackLoop(timestamp) {
    if (!isPlaying) return;
    const delta = (timestamp - lastTimestamp) / 1000;
    lastTimestamp = timestamp;

    // Sync time to audio element if available (drift-free)
    if (audioSynced && !syncAudioPlayer.paused) {
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
      const handleW = boxMeta.widthPx  * (sw / 1080);
      const handleH = boxMeta.heightPx * (sh / 1920);
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

    const activeBlock = captionData.blocks.find(b => currentTime >= b.start && currentTime <= b.end);
    document.querySelectorAll('.block-card').forEach(card => {
      card.classList.toggle('active-playing', !!(activeBlock && card.dataset.id === activeBlock.id));
    });
  }

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
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = `caption_frame_${currentTime.toFixed(2)}s.png`;
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
