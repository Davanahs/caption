'use client';
import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { 
  listChannels, 
  addChannel, 
  updateChannel, 
  deleteChannel, 
  checkChannelNow, 
  getDestinations, 
  getChannelVideos, 
  processChannelVideo,
  processChannelVideosBatch,
  getPendingDecisions,
  applyDefaultsDecision,
  customizeDecision,
  saveAndProcessDecision,
  cancelDecision,
  getDecisionHistory,
  ChannelProcessingProfile,
  VideoDecision,
  DecisionHistoryItem,
  PaginatedVideosResponse,
  getHistoricalPreview,
  processHistoricalBatch,
  HistoricalSelectionMode,
  HistoricalCandidateItem,
  HistoricalPreviewResponse,
} from '@/lib/api';
import LayoutPreviewSelector, { resolveLayoutOptionId, LAYOUT_OPTIONS } from '@/components/LayoutThumbnailSelector';
import { YouTubeVideoThumbnail } from '@/components/automation/YouTubeVideoThumbnail';

function formatLayoutLabel(layoutId?: string): string {
  const opt = LAYOUT_OPTIONS.find(o => o.id === resolveLayoutOptionId(layoutId));
  return opt ? opt.name : (layoutId || 'Blur');
}

function formatUserFacingError(rawError?: string | null, currentStep?: string | null): string {
  if (!rawError && !currentStep) return 'Processing failed.';
  const err = (rawError || '').trim();
  const step = (currentStep || '').trim();
  
  // Guard against any technical driver/internal exception traces leaking through
  const isTechnical = /psycopg2|ProgrammingError|OperationalError|DataError|IntegrityError|sqlalchemy|\[SQL:|can't adapt type|Traceback/i.test(err);
  
  const displayMsg = isTechnical 
    ? 'Processing failed. See server logs for diagnostic details.' 
    : err || 'Processing failed.';
    
  return step ? `[${step}] ${displayMsg}` : displayMsg;
}

const DEFAULT_PROFILE: ChannelProcessingProfile = {
  duration_mode: 'adaptive',
  min_clip_duration: 15.0,
  max_clip_duration: 30.0,
  clips_count: 3,
  video_layout: 'fill_blur',
  segmentation_strategy: 'hook_peak_fall',
  scoring_mode: 'ai',
};

export default function AutomationPage() {
  const router = useRouter();

  // ── Channels & Destinations ──────────────────────────────────────────
  const [channels, setChannels] = useState<any[]>([]);
  const [destinations, setDestinations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedChannelId, setSelectedChannelId] = useState<string>('');
  const [selectedVideo, setSelectedVideo] = useState<{ id: string; url: string; title: string; channelId: string } | null>(null);
  // Multi-video selection: Map of videoId -> video object
  const [selectedVideos, setSelectedVideos] = useState<Record<string, { id: string; url: string; title: string; duration?: number; channelId: string }>>({});
  const [isBatchProcessing, setIsBatchProcessing] = useState(false);

  // ── Add Channel Form ─────────────────────────────────────────────────
  const [form, setForm] = useState<{
    channel_url: string;
    auto_clip: boolean;
    auto_publish: boolean;
    publish_destination_id: string;
    profile: ChannelProcessingProfile;
  }>({ 
    channel_url: '', 
    auto_clip: true, 
    auto_publish: false, 
    publish_destination_id: '',
    profile: { ...DEFAULT_PROFILE }
  });
  const [showAdvancedAdd, setShowAdvancedAdd] = useState(false);
  const [adding, setAdding] = useState(false);
  const [checking, setChecking] = useState<string | null>(null);

  // ── Channel Profile Editor Modal ─────────────────────────────────────
  const [editingChannel, setEditingChannel] = useState<any | null>(null);
  const [editProfile, setEditProfile] = useState<ChannelProcessingProfile>({ ...DEFAULT_PROFILE });
  const [savingProfile, setSavingProfile] = useState(false);

  // ── Paginated Videos State ───────────────────────────────────────────
  const [expandedChannels, setExpandedChannels] = useState<Record<string, boolean>>({});
  const [videoData, setVideoData] = useState<Record<string, PaginatedVideosResponse>>({});
  const [videoPages, setVideoPages] = useState<Record<string, number>>({});
  const [videoSortModes, setVideoSortModes] = useState<Record<string, 'latest' | 'most_viewed'>>({});
  const [loadingVideos, setLoadingVideos] = useState<Record<string, boolean>>({});
  const [processingVideo, setProcessingVideo] = useState<string | null>(null);

  // ── Pending Decisions & Countdown Toast ──────────────────────────────
  const [pendingDecisions, setPendingDecisions] = useState<VideoDecision[]>([]);
  const [activeDecision, setActiveDecision] = useState<VideoDecision | null>(null);
  const [countdownRemaining, setCountdownRemaining] = useState<number>(0);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);

  // ── Per-Video Customization Modal (120s Lease) ────────────────────────
  const [customizingDecision, setCustomizingDecision] = useState<VideoDecision | null>(null);
  const [customOverrides, setCustomOverrides] = useState<ChannelProcessingProfile>({ ...DEFAULT_PROFILE });
  const [savingCustomOverrides, setSavingCustomOverrides] = useState(false);

  // ── Decision History ─────────────────────────────────────────────────
  const [decisionHistory, setDecisionHistory] = useState<DecisionHistoryItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // ── Historical Video Processing State (Two-Action Model) ───────────────
  const [historicalChannelId, setHistoricalChannelId] = useState<string | null>(null);
  const [historicalPrimaryAction, setHistoricalPrimaryAction] = useState<'recent' | 'old'>('recent');
  const [historicalOldRanking, setHistoricalOldRanking] = useState<'most_viewed' | 'latest'>('most_viewed');
  const [historicalMode, setHistoricalMode] = useState<HistoricalSelectionMode>('latest');
  const [historicalCount, setHistoricalCount] = useState<number>(3);
  const [historicalSinceDate, setHistoricalSinceDate] = useState<string>('');
  const [historicalSearchDepth, setHistoricalSearchDepth] = useState<number>(50);
  const [showAdvancedHistorical, setShowAdvancedHistorical] = useState<boolean>(false);
  const [isLoadingPreview, setIsLoadingPreview] = useState<boolean>(false);
  const [historicalPreview, setHistoricalPreview] = useState<HistoricalPreviewResponse | null>(null);
  const [showHistoricalModal, setShowHistoricalModal] = useState<boolean>(false);
  const [isSubmittingHistorical, setIsSubmittingHistorical] = useState<boolean>(false);

  const openHistoricalProcessor = (channelId: string, initialAction: 'recent' | 'old' = 'recent') => {
    setHistoricalChannelId(channelId);
    setHistoricalPrimaryAction(initialAction);
    if (initialAction === 'recent') {
      setHistoricalMode('latest');
      setHistoricalCount(3);
    } else {
      setHistoricalMode(historicalOldRanking);
      setHistoricalCount(5);
    }
    setHistoricalPreview(null);
    setShowHistoricalModal(true);
  };

  const loadHistoricalPreview = async () => {
    if (!historicalChannelId) return;
    setIsLoadingPreview(true);
    setError('');
    try {
      const res = await getHistoricalPreview(historicalChannelId, {
        mode: historicalMode,
        count: Math.max(1, Math.min(Number(historicalCount) || 3, 20)),
        since_date: historicalSinceDate ? historicalSinceDate : null,
        max_search_depth: Math.max(10, Math.min(Number(historicalSearchDepth) || 50, 250)),
      });
      setHistoricalPreview(res);
    } catch (e: any) {
      setError(`Failed to generate historical preview: ${e.message || 'Server error'}`);
    } finally {
      setIsLoadingPreview(false);
    }
  };

  const executeHistoricalBatch = async () => {
    if (!historicalChannelId || !historicalPreview) return;
    setIsSubmittingHistorical(true);
    setError('');
    setMsg('');
    try {
      const targetIds = historicalPreview.items
        .filter(item => item.selected_for_queue)
        .map(item => item.id);

      const res = await processHistoricalBatch(historicalChannelId, {
        mode: historicalMode,
        video_ids: targetIds,
      });

      if (historicalMode === 'new_only') {
        setMsg(`✅ ${res.message || 'Auto Monitor active for future uploads.'}`);
      } else {
        let successText = `🚀 Historical batch queued! ${res.queued_count} video(s) queued for processing.`;
        if (res.already_processing_count > 0) {
          successText += ` (${res.already_processing_count} already processing)`;
        }
        setMsg(successText);
      }
      setShowHistoricalModal(false);
      setHistoricalPreview(null);
      fetchChannelVideos(historicalChannelId, videoPages[historicalChannelId] || 1);
      loadHistory();
      load();
    } catch (e: any) {
      setError(`Failed to execute historical batch: ${e.message || 'Server error'}`);
    } finally {
      setIsSubmittingHistorical(false);
    }
  };

  // ── Feedback Messages ────────────────────────────────────────────────
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');

  // ── Load Baseline Data ───────────────────────────────────────────────
  const load = () => {
    setLoading(true);
    Promise.all([
      listChannels().catch(() => []),
      getDestinations().catch(() => [])
    ]).then(([channelData, destData]) => {
      setChannels(channelData || []);
      setDestinations(destData || []);
      setLoading(false);
    }).catch(() => setLoading(false));
  };

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const hist = await getDecisionHistory(50);
      setDecisionHistory(hist || []);
    } catch (e: any) {
      console.error('Failed to load decision history:', e);
    }
    setLoadingHistory(false);
  };

  useEffect(() => { 
    load(); 
    loadHistory();

    if (typeof window !== 'undefined') {
      const sp = new URLSearchParams(window.location.search);
      const urlCh = sp.get('channel') || localStorage.getItem('last_automation_channel_id');
      if (urlCh) {
        setSelectedChannelId(urlCh);
        fetchChannelVideos(urlCh, 1);
      }
    }
  }, []);

  // ── 20-Second Decision Polling & Realtime Ticking ─────────────────────
  useEffect(() => {
    const pollPending = async () => {
      try {
        const decs = await getPendingDecisions();
        setPendingDecisions(decs || []);
        
        // Target decision awaiting settings or in customization
        const awaiting = decs.find(d => d.status === 'awaiting_settings' || d.status === 'customizing');
        if (awaiting) {
          setActiveDecision(awaiting);
          setCountdownRemaining(awaiting.remaining_seconds);
        } else {
          setActiveDecision(null);
        }
      } catch (err) {
        // Silent poll error
      }
    };

    pollPending();
    const interval = setInterval(pollPending, 3000);
    return () => clearInterval(interval);
  }, []);

  // Countdown timer tick down every 1 second
  useEffect(() => {
    if (!activeDecision || countdownRemaining <= 0) return;
    const timer = setInterval(() => {
      setCountdownRemaining(prev => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [activeDecision, countdownRemaining]);

  // ── Add Channel ──────────────────────────────────────────────────────
  const handleAdd = async () => {
    if (!form.channel_url.trim()) return;
    if (form.auto_publish && !form.publish_destination_id) {
      setError('Cannot enable auto-publish without selecting a valid publish destination.');
      return;
    }
    setAdding(true); 
    setError(''); 
    setMsg('');
    try {
      const res = await addChannel({
        channel_url: form.channel_url.trim(),
        auto_clip: form.auto_clip,
        auto_publish: form.auto_publish,
        publish_destination_id: form.publish_destination_id || undefined,
        processing_profile: form.profile
      });
      setMsg(`✅ Successfully monitored: ${res.channel_name}`);
      setForm({ 
        channel_url: '', 
        auto_clip: true, 
        auto_publish: false, 
        publish_destination_id: '',
        profile: { ...DEFAULT_PROFILE }
      });
      setShowAdvancedAdd(false);
      load();
    } catch (e: any) { 
      setError(e.message || 'Failed to add channel'); 
    }
    setAdding(false);
  };

  const handleToggle = async (id: string, field: string, val: any) => {
    const targetCh = channels.find(c => c.id === id);
    if (field === 'auto_publish' && val === true && !targetCh?.publish_destination_id) {
      setError('Cannot enable auto-publish: Please select a destination channel first.');
      return;
    }
    if (field === 'publish_destination_id' && !val && targetCh?.auto_publish) {
      try {
        await updateChannel(id, { publish_destination_id: null, auto_publish: false });
        setChannels(ch => ch.map(c => c.id === id ? { ...c, publish_destination_id: null, auto_publish: false } : c));
      } catch (e: any) {
        setError(e.message || 'Failed to update destination');
      }
      return;
    }
    try {
      await updateChannel(id, { [field]: val });
      setChannels(ch => ch.map(c => c.id === id ? { ...c, [field]: val } : c));
    } catch (e: any) {
      setError(e.message || `Failed to update ${field}`);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Remove this channel from 24/7 monitoring?')) return;
    try {
      await deleteChannel(id);
      setChannels(ch => ch.filter(c => c.id !== id));
      if (selectedChannelId === id) {
        setSelectedChannelId('');
        setSelectedVideo(null);
        if (typeof window !== 'undefined') {
          localStorage.removeItem('last_automation_channel_id');
          localStorage.removeItem('last_automation_video_id');
        }
      }
      setMsg('Channel removed from monitoring.');
    } catch (e: any) {
      setError(e.message || 'Failed to delete channel');
    }
  };

  const handleCheckNow = async (id: string) => {
    setChecking(id);
    setError('');
    setMsg('');
    try {
      const res = await checkChannelNow(id);
      setMsg(`Found ${res.new_videos_found} new video(s) during check.`);
      if (expandedChannels[id]) {
        fetchChannelVideos(id, videoPages[id] || 1);
      }
      loadHistory();
    } catch (e: any) { 
      setError(e.message || 'Failed to check channel uploads'); 
    }
    setChecking(null);
    load();
  };

  // ── Paginated Videos ─────────────────────────────────────────────────
  const fetchChannelVideos = async (channelId: string, page: number = 1, overrideSort?: 'latest' | 'most_viewed') => {
    setLoadingVideos(prev => ({ ...prev, [channelId]: true }));
    const activeSort = overrideSort || videoSortModes[channelId] || 'latest';
    try {
      const res = await getChannelVideos(channelId, page, 8, activeSort, 50);
      setVideoData(prev => ({ ...prev, [channelId]: res }));
      setVideoPages(prev => ({ ...prev, [channelId]: page }));
      setExpandedChannels(prev => ({ ...prev, [channelId]: true }));

      // Restore selected video if previously saved for this channel
      if (typeof window !== 'undefined') {
        const sp = new URLSearchParams(window.location.search);
        const storedVidId = sp.get('video') || localStorage.getItem('last_automation_video_id');
        if (storedVidId && res.items) {
          const match = res.items.find(v => v.id === storedVidId);
          if (match) {
            setSelectedVideo({
              id: match.id,
              url: match.url,
              title: match.title,
              channelId
            });
          }
        }
      }
    } catch (e: any) {
      console.error('Failed to load channel videos:', e);
      setError(`Failed to retrieve channel videos: ${e.message}`);
    }
    setLoadingVideos(prev => ({ ...prev, [channelId]: false }));
  };

  const handleToggleSortMode = (channelId: string, mode: 'latest' | 'most_viewed') => {
    setVideoSortModes(prev => ({ ...prev, [channelId]: mode }));
    setVideoPages(prev => ({ ...prev, [channelId]: 1 }));
    fetchChannelVideos(channelId, 1, mode);
  };

  const handleSelectChannel = (channelId: string) => {
    setSelectedChannelId(channelId);
    if (typeof window !== 'undefined') {
      localStorage.setItem('last_automation_channel_id', channelId);
    }
    if (selectedVideo && selectedVideo.channelId !== channelId) {
      setSelectedVideo(null);
      if (typeof window !== 'undefined') {
        localStorage.removeItem('last_automation_video_id');
      }
    }
    if (!videoData[channelId]) {
      fetchChannelVideos(channelId, 1);
    }
  };

  const handleSelectVideo = (channelId: string, vid: any) => {
    if (vid.is_generated_short) {
      return; // Output Shorts cannot be selected as source videos
    }
    setSelectedChannelId(channelId);
    toggleSelectVideo(channelId, vid);
    const videoDataObj = {
      id: vid.id,
      url: vid.url,
      title: vid.title,
      channelId
    };
    setSelectedVideo(videoDataObj);
    if (typeof window !== 'undefined') {
      localStorage.setItem('last_automation_channel_id', channelId);
      localStorage.setItem('last_automation_video_id', videoDataObj.id);
    }
  };

  const toggleSelectVideo = (channelId: string, vid: any) => {
    if (vid.is_generated_short) {
      return; // Output Shorts cannot be selected as source videos
    }
    setSelectedChannelId(channelId);
    setSelectedVideos(prev => {
      const copy = { ...prev };
      if (copy[vid.id]) {
        delete copy[vid.id];
      } else {
        copy[vid.id] = {
          id: vid.id,
          url: vid.url,
          title: vid.title,
          duration: vid.duration,
          channelId
        };
      }
      return copy;
    });
  };

  const selectAllEligibleOnPage = (channelId: string) => {
    const pData = videoData[channelId];
    if (!pData || !pData.items) return;
    setSelectedChannelId(channelId);
    setSelectedVideos(prev => {
      const copy = { ...prev };
      pData.items.forEach((v: any) => {
        const isEligible = !v.is_processed && !v.job_id && !v.is_generated_short;
        if (isEligible) {
          copy[v.id] = {
            id: v.id,
            url: v.url,
            title: v.title,
            duration: v.duration,
            channelId
          };
        }
      });
      return copy;
    });
  };

  const clearSelection = () => {
    setSelectedVideos({});
  };

  // ── Batch Outcome & Selection Reconciliation Helper ────────────────────────
  const reconcileBatchOutcomes = (
    submittedVids: Array<{ id: string; title: string; channelId: string }>,
    res: any
  ) => {
    const succeededIds = new Set<string>();
    const returnedMap = new Map<string, any>();
    if (Array.isArray(res?.items)) {
      res.items.forEach((item: any) => {
        if (item.video_id) returnedMap.set(item.video_id, item);
      });
    }

    let queuedCount = 0;
    let alreadyCount = 0;
    let rejectedCount = 0;
    let failedCount = 0;
    let unresolvedCount = 0;
    const details: string[] = [];

    for (const v of submittedVids) {
      const item = returnedMap.get(v.id);
      if (!item) {
        unresolvedCount++;
        details.push(`"${v.title}": Unresolved (no outcome returned from server)`);
      } else if (item.status === 'queued') {
        queuedCount++;
        succeededIds.add(v.id);
      } else if (item.status === 'already_processing') {
        alreadyCount++;
        succeededIds.add(v.id);
      } else if (item.status === 'rejected') {
        rejectedCount++;
        details.push(`"${v.title}": Rejected (${item.error || 'Validation error'})`);
      } else if (item.status === 'failed') {
        failedCount++;
        details.push(`"${v.title}": Failed (${item.error || 'Dispatch error'})`);
      } else {
        unresolvedCount++;
        details.push(`"${v.title}": Unresolved (status: ${item.status})`);
      }
    }

    return {
      succeededIds,
      queuedCount,
      alreadyCount,
      rejectedCount,
      failedCount,
      unresolvedCount,
      details
    };
  };

  // ── Behavior B: Explicit Channel-Scoped Batch Action ──────────────────────
  const handleProcessChannelBatch = async (channelId: string) => {
    const vids = Object.values(selectedVideos).filter(v => v.channelId === channelId);
    if (vids.length === 0) return;

    setIsBatchProcessing(true);
    setError('');
    setMsg('');

    try {
      const payload = vids.map(v => ({
        video_id: v.id,
        video_url: v.url,
        video_title: v.title,
      }));
      const res = await processChannelVideosBatch(channelId, payload);
      const reconciliation = reconcileBatchOutcomes(vids, res);

      // Remove ONLY confirmed succeeded items for this channel; leave rejected/failed/unresolved items
      setSelectedVideos(prev => {
        const next = { ...prev };
        reconciliation.succeededIds.forEach(id => delete next[id]);
        return next;
      });

      const remainingForChannel = vids.length - reconciliation.succeededIds.size;
      const chObj = channels.find(c => c.id === channelId);
      const chName = chObj?.channel_name || channelId;

      if (reconciliation.rejectedCount > 0 || reconciliation.failedCount > 0 || reconciliation.unresolvedCount > 0) {
        setError(
          `⚠️ ${chName} batch partial result: ${reconciliation.queuedCount} queued, ` +
          `${reconciliation.alreadyCount} already processing. ${remainingForChannel} video(s) remain selected. ` +
          `Issues: [${reconciliation.details.join('; ')}]`
        );
      } else {
        let successMsg = `🚀 ${chName}: ${reconciliation.queuedCount} video${reconciliation.queuedCount === 1 ? '' : 's'} queued for processing!`;
        if (reconciliation.alreadyCount > 0) successMsg += ` (${reconciliation.alreadyCount} already processing)`;
        setMsg(successMsg);
      }

      fetchChannelVideos(channelId, videoPages[channelId] || 1);
      loadHistory();
    } catch (e: any) {
      setError(
        `Failed to dispatch batch for channel: ${e.message || 'Network / server error'}. ` +
        `Outcome uncertain; selection preserved. Retrying is safe against active jobs.`
      );
    }
    setIsBatchProcessing(false);
  };

  // ── Behavior A: Global Sticky Multi-Channel Action ───────────────────────
  const handleProcessGlobalBatch = async () => {
    const entries = Object.values(selectedVideos);
    if (entries.length === 0) return;

    // Group strictly by each video's own stored channelId
    const byChannel: Record<string, typeof entries> = {};
    const unassigned: typeof entries = [];

    entries.forEach(v => {
      if (!v.channelId) {
        unassigned.push(v);
      } else {
        if (!byChannel[v.channelId]) byChannel[v.channelId] = [];
        byChannel[v.channelId].push(v);
      }
    });

    if (unassigned.length > 0) {
      setError(`Cannot process ${unassigned.length} video(s): Missing channel association.`);
      return;
    }

    setIsBatchProcessing(true);
    setError('');
    setMsg('');

    const allSucceededIds = new Set<string>();
    const channelReports: Array<{
      channelId: string;
      channelName: string;
      queued: number;
      already: number;
      rejected: number;
      failed: number;
      unresolved: number;
      error?: string;
      details: string[];
    }> = [];

    for (const [chId, vids] of Object.entries(byChannel)) {
      const chObj = channels.find(c => c.id === chId);
      const chName = chObj?.channel_name || chId;
      try {
        const payload = vids.map(v => ({
          video_id: v.id,
          video_url: v.url,
          video_title: v.title,
        }));
        const res = await processChannelVideosBatch(chId, payload);
        const reconciliation = reconcileBatchOutcomes(vids, res);
        reconciliation.succeededIds.forEach(id => allSucceededIds.add(id));
        channelReports.push({
          channelId: chId,
          channelName: chName,
          queued: reconciliation.queuedCount,
          already: reconciliation.alreadyCount,
          rejected: reconciliation.rejectedCount,
          failed: reconciliation.failedCount,
          unresolved: reconciliation.unresolvedCount,
          details: reconciliation.details,
        });
      } catch (err: any) {
        channelReports.push({
          channelId: chId,
          channelName: chName,
          queued: 0,
          already: 0,
          rejected: 0,
          failed: vids.length,
          unresolved: 0,
          error: err.message || 'Network / server error',
          details: [`All ${vids.length} videos unresolved due to request error`],
        });
      }
    }

    // Reconcile selection state: remove only confirmed succeeded items across all channels
    setSelectedVideos(prev => {
      const next = { ...prev };
      allSucceededIds.forEach(id => delete next[id]);
      return next;
    });

    const totalQueued = channelReports.reduce((acc, r) => acc + r.queued, 0);
    const totalAlready = channelReports.reduce((acc, r) => acc + r.already, 0);
    const hasIssues = channelReports.some(r => r.rejected > 0 || r.failed > 0 || r.unresolved > 0 || r.error);

    if (hasIssues) {
      const remainingCount = entries.length - allSucceededIds.size;
      const issueSummaries = channelReports
        .filter(r => r.rejected > 0 || r.failed > 0 || r.unresolved > 0 || r.error)
        .map(r => {
          if (r.error) return `${r.channelName}: ${r.error} (outcome uncertain)`;
          return `${r.channelName}: ${r.details.join(', ')}`;
        });
      setError(
        `⚠️ Partial batch result: ${totalQueued} queued, ${totalAlready} already processing. ` +
        `Issues: [${issueSummaries.join('; ')}]. ${remainingCount} video(s) remain selected for review/retry.`
      );
    } else {
      let successMsg = `🚀 Successfully queued ${totalQueued} video${totalQueued === 1 ? '' : 's'} across ${Object.keys(byChannel).length} channel(s)!`;
      if (totalAlready > 0) successMsg += ` (${totalAlready} already processing)`;
      setMsg(successMsg);
    }

    // Refresh video lists for channels with successful submissions
    channelReports.filter(r => r.queued > 0 || r.already > 0).forEach(r => {
      fetchChannelVideos(r.channelId, videoPages[r.channelId] || 1);
    });
    loadHistory();
    setIsBatchProcessing(false);
  };

  const openBatchCustomizer = (channel: any) => {
    const channelId = channel.id;
    const vids = channelId === 'global'
      ? Object.values(selectedVideos)
      : Object.values(selectedVideos).filter(v => v.channelId === channelId);
    if (vids.length === 0) return;
    const tempDecision: VideoDecision = {
      id: `batch_${channelId}`,
      channel_id: channelId,
      channel_name: channel.channel_name || 'Channel',
      youtube_id: vids[0].id,
      video_title: `${vids.length} Selected Videos (Batch Overrides)`,
      youtube_url: vids[0].url,
      thumbnail_url: undefined,
      status: 'customizing',
      remaining_seconds: 120,
      channel_profile_snapshot: channel.processing_profile || DEFAULT_PROFILE,
      overrides: {}
    };
    setCustomizingDecision(tempDecision);
    setCustomOverrides({
      ...DEFAULT_PROFILE,
      ...(channel.processing_profile || {})
    });
  };

  const handleSaveBatchCustom = async () => {
    if (!customizingDecision) return;
    const targetChannelId = customizingDecision.channel_id;
    const entries = targetChannelId === 'global'
      ? Object.values(selectedVideos)
      : Object.values(selectedVideos).filter(v => v.channelId === targetChannelId);
    if (entries.length === 0) return;

    setSavingCustomOverrides(true);
    setError('');

    // Group by channel
    const byChannel: Record<string, typeof entries> = {};
    entries.forEach(v => {
      if (v.channelId) {
        if (!byChannel[v.channelId]) byChannel[v.channelId] = [];
        byChannel[v.channelId].push(v);
      }
    });

    const allSucceededIds = new Set<string>();
    const channelReports: Array<{
      channelId: string;
      channelName: string;
      queued: number;
      already: number;
      rejected: number;
      failed: number;
      unresolved: number;
      error?: string;
      details: string[];
    }> = [];

    try {
      for (const [chId, vids] of Object.entries(byChannel)) {
        const chObj = channels.find(c => c.id === chId);
        const chName = chObj?.channel_name || chId;
        try {
          const payload = vids.map(v => ({
            video_id: v.id,
            video_url: v.url,
            video_title: v.title,
          }));
          const res = await processChannelVideosBatch(chId, payload, customOverrides);
          const reconciliation = reconcileBatchOutcomes(vids, res);
          reconciliation.succeededIds.forEach(id => allSucceededIds.add(id));
          channelReports.push({
            channelId: chId,
            channelName: chName,
            queued: reconciliation.queuedCount,
            already: reconciliation.alreadyCount,
            rejected: reconciliation.rejectedCount,
            failed: reconciliation.failedCount,
            unresolved: reconciliation.unresolvedCount,
            details: reconciliation.details,
          });
        } catch (err: any) {
          channelReports.push({
            channelId: chId,
            channelName: chName,
            queued: 0,
            already: 0,
            rejected: 0,
            failed: vids.length,
            unresolved: 0,
            error: err.message || 'Network / server error',
            details: [`All ${vids.length} videos unresolved due to request error`],
          });
        }
      }

      setSelectedVideos(prev => {
        const next = { ...prev };
        allSucceededIds.forEach(id => delete next[id]);
        return next;
      });

      const totalQueued = channelReports.reduce((acc, r) => acc + r.queued, 0);
      const totalAlready = channelReports.reduce((acc, r) => acc + r.already, 0);
      const hasIssues = channelReports.some(r => r.rejected > 0 || r.failed > 0 || r.unresolved > 0 || r.error);

      if (hasIssues) {
        const remainingCount = entries.length - allSucceededIds.size;
        const issueSummaries = channelReports
          .filter(r => r.rejected > 0 || r.failed > 0 || r.unresolved > 0 || r.error)
          .map(r => {
            if (r.error) return `${r.channelName}: ${r.error} (outcome uncertain)`;
            return `${r.channelName}: ${r.details.join(', ')}`;
          });
        setError(
          `⚠️ Partial custom batch: ${totalQueued} queued, ${totalAlready} already processing. ` +
          `Issues: [${issueSummaries.join('; ')}]. ${remainingCount} video(s) remain selected for retry.`
        );
      } else {
        let successMsg = `🚀 Queued ${totalQueued} video${totalQueued === 1 ? '' : 's'} with custom overrides across ${Object.keys(byChannel).length} channel(s)!`;
        if (totalAlready > 0) successMsg += ` (${totalAlready} already processing)`;
        setMsg(successMsg);
      }

      setCustomizingDecision(null);
      channelReports.filter(r => r.queued > 0 || r.already > 0).forEach(r => {
        fetchChannelVideos(r.channelId, videoPages[r.channelId] || 1);
      });
      loadHistory();
    } catch (e: any) {
      setError(e.message || 'Failed to dispatch batch custom processing');
    }
    setSavingCustomOverrides(false);
  };

  const toggleDiscoverVideos = (channelId: string) => {
    handleSelectChannel(channelId);
    if (expandedChannels[channelId]) {
      setExpandedChannels(prev => ({ ...prev, [channelId]: false }));
    } else {
      fetchChannelVideos(channelId, videoPages[channelId] || 1);
    }
  };

  const handleProcessVideoDefaults = async (channelId: string, vid: any) => {
    setProcessingVideo(vid.id);
    setError('');
    setMsg('');
    try {
      const res = await processChannelVideo(channelId, {
        video_id: vid.id,
        video_title: vid.title,
        video_url: vid.url,
      });
      if (res.status === 'already_processing') {
        setMsg(`ℹ️ "${vid.title}" is already being processed! (Job: ${res.job_id || 'Active'})`);
      } else {
        setMsg(`🚀 Processing initiated for "${vid.title}" with channel defaults! (Job: ${res.job_id || 'Queued'})`);
      }
      fetchChannelVideos(channelId, videoPages[channelId] || 1);
      loadHistory();
    } catch (e: any) {
      setError(e.message || 'Failed to process video');
    }
    setProcessingVideo(null);
  };

  // ── Channel Profile Modal ────────────────────────────────────────────
  const openEditProfileModal = (ch: any, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingChannel(ch);
    setEditProfile({
      ...DEFAULT_PROFILE,
      ...(ch.processing_profile || {})
    });
  };

  const handleSaveChannelProfile = async () => {
    if (!editingChannel) return;
    setSavingProfile(true);
    setError('');
    try {
      await updateChannel(editingChannel.id, {
        processing_profile: editProfile
      });
      setMsg(`Updated default processing profile for ${editingChannel.channel_name}`);
      setChannels(prev => prev.map(c => c.id === editingChannel.id ? { ...c, processing_profile: editProfile } : c));
      setEditingChannel(null);
    } catch (e: any) {
      setError(e.message || 'Failed to update channel profile');
    }
    setSavingProfile(false);
  };

  // ── Decision Toast Actions ───────────────────────────────────────────
  const handleApplyDefaultsDecision = async (decisionId: string) => {
    setActionInProgress(decisionId);
    setError('');
    try {
      const res = await applyDefaultsDecision(decisionId);
      setMsg(`✅ Applied defaults for video! Job ${res.job_id} scheduled.`);
      setActiveDecision(null);
      loadHistory();
    } catch (e: any) {
      setError(e.message || 'Failed to apply defaults');
    }
    setActionInProgress(null);
  };

  const handleOpenCustomizer = async (decision: VideoDecision) => {
    setActionInProgress(decision.id);
    setError('');
    try {
      // Transition decision to customizing & acquire 120s lease
      const res = await customizeDecision(decision.id, undefined, decision.channel_id);
      setCustomizingDecision({
        ...decision,
        lease_token: res.lease_token,
      });
      const snapshot = decision.channel_profile_snapshot || DEFAULT_PROFILE;
      setCustomOverrides({
        ...DEFAULT_PROFILE,
        ...snapshot,
        ...(decision.overrides || {})
      });
    } catch (e: any) {
      setError(e.message || 'Failed to enter customization mode');
    }
    setActionInProgress(null);
  };

  const handleSaveAndProcessDecision = async () => {
    if (!customizingDecision) return;
    setSavingCustomOverrides(true);
    setError('');
    try {
      const res = await saveAndProcessDecision(
        customizingDecision.id,
        customOverrides,
        {
          lease_token: customizingDecision.lease_token,
          expected_status: 'customizing',
          channelId: customizingDecision.channel_id,
        }
      );
      setMsg(`🚀 Processing initiated with custom overrides! (Job: ${res.job_id})`);
      setCustomizingDecision(null);
      setActiveDecision(null);
      loadHistory();
    } catch (e: any) {
      setError(e.message || 'Failed to save and process decision');
    }
    setSavingCustomOverrides(false);
  };

  const handleCancelDecisionAction = async (decisionId: string) => {
    if (!confirm('Are you sure you want to cancel processing for this video?')) return;
    setActionInProgress(decisionId);
    setError('');
    try {
      await cancelDecision(decisionId);
      setMsg('Video processing cancelled.');
      if (customizingDecision?.id === decisionId) {
        setCustomizingDecision(null);
      }
      setActiveDecision(null);
      loadHistory();
    } catch (e: any) {
      setError(e.message || 'Failed to cancel decision');
    }
    setActionInProgress(null);
  };

  const openCustomizerFromDiscoveredVideo = (channel: any, vid: any) => {
    // Manually create mock/temporary decision state for this discovered video
    const tempDecision: VideoDecision = {
      id: `manual_${vid.id}`,
      channel_id: channel.id,
      channel_name: channel.channel_name,
      youtube_id: vid.id,
      video_title: vid.title,
      youtube_url: vid.url,
      thumbnail_url: vid.thumbnail,
      status: 'customizing',
      remaining_seconds: 120,
      channel_profile_snapshot: channel.processing_profile || DEFAULT_PROFILE,
      overrides: {}
    };
    setCustomizingDecision(tempDecision);
    setCustomOverrides({
      ...DEFAULT_PROFILE,
      ...(channel.processing_profile || {})
    });
  };

  const handleSaveDiscoveredVideoCustom = async () => {
    if (!customizingDecision) return;
    setSavingCustomOverrides(true);
    setError('');
    try {
      if (customizingDecision.id.startsWith('manual_')) {
        const res = await processChannelVideo(
          customizingDecision.channel_id,
          {
            video_id: customizingDecision.youtube_id,
            video_title: customizingDecision.video_title,
            video_url: customizingDecision.youtube_url,
          },
          customOverrides
        );
        setMsg(`🚀 Custom processing queued for "${customizingDecision.video_title}"! (Job: ${res.job_id})`);
      } else {
        await saveAndProcessDecision(customizingDecision.id, customOverrides);
      }
      setCustomizingDecision(null);
      loadHistory();
    } catch (e: any) {
      setError(e.message || 'Failed to dispatch custom video processing');
    }
    setSavingCustomOverrides(false);
  };

  return (
    <>
      <div className="animate-fade-up" style={{ paddingBottom: 60 }}>
        {/* ── Top Header ──────────────────────────────────────────────── */}
      <div style={{ marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 28, fontWeight: 800, fontFamily: "'Space Grotesk', sans-serif" }}>
            🤖 Autonomous Channel Monitoring & Intelligent Pipeline
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 6, maxWidth: 840 }}>
            Continuous 24/7 YouTube channel monitoring with persistent channel profiles, 20-second restart-safe configuration countdown, per-video customization overrides, and truthful Shorts duration compliance (&le; 30.0s).
          </p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button className="btn-ghost" onClick={() => { load(); loadHistory(); }} style={{ fontSize: 13 }}>
            🔄 Refresh Status
          </button>
        </div>
      </div>

      {/* ── 20-Second Decision Alert Banner (Live Countdown Toast) ───── */}
      {activeDecision && activeDecision.status === 'awaiting_settings' && (
        <div 
          className="glass glow-accent" 
          style={{ 
            padding: '18px 24px', 
            marginBottom: 24, 
            background: 'linear-gradient(135deg, rgba(99,102,241,0.18) 0%, rgba(192,193,255,0.08) 100%)',
            borderColor: 'var(--accent)',
            position: 'relative',
            overflow: 'hidden'
          }}
        >
          {/* Animated Countdown Bar */}
          <div 
            style={{
              position: 'absolute',
              bottom: 0,
              left: 0,
              height: 4,
              background: 'linear-gradient(90deg, var(--accent), var(--accent-2))',
              width: `${Math.min(100, (countdownRemaining / 20) * 100)}%`,
              transition: 'width 1s linear'
            }}
          />

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <div style={{ 
                fontSize: 26, 
                background: 'rgba(99,102,241,0.25)', 
                width: 48, 
                height: 48, 
                borderRadius: '50%', 
                display: 'flex', 
                alignItems: 'center', 
                justifyContent: 'center' 
              }}>
                ⏳
              </div>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>
                    New Video Detected: {activeDecision.video_title}
                  </span>
                  <span className="badge badge-warning" style={{ fontSize: 11, fontWeight: 700 }}>
                    {countdownRemaining}s Remaining
                  </span>
                </div>
                <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 2 }}>
                  From <strong>{activeDecision.channel_name}</strong> · Auto-starts with channel defaults when timer reaches 0.
                </div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <button
                className="btn-primary"
                style={{ fontSize: 13, padding: '8px 16px' }}
                disabled={actionInProgress === activeDecision.id}
                onClick={() => handleApplyDefaultsDecision(activeDecision.id)}
              >
                {actionInProgress === activeDecision.id ? '⏳ Applying...' : '⚡ Apply Defaults Now'}
              </button>
              <button
                className="btn-secondary"
                style={{ fontSize: 13, padding: '8px 16px', background: 'rgba(255,255,255,0.08)', color: 'var(--text-primary)' }}
                disabled={actionInProgress === activeDecision.id}
                onClick={() => handleOpenCustomizer(activeDecision)}
              >
                ⚙️ Customize (Pause)
              </button>
              <button
                className="btn-danger"
                style={{ fontSize: 12, padding: '8px 12px' }}
                disabled={actionInProgress === activeDecision.id}
                onClick={() => handleCancelDecisionAction(activeDecision.id)}
                title="Cancel processing for this video"
              >
                ✖ Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Active Customization Mode Banner (If Lease Active) ───────── */}
      {activeDecision && activeDecision.status === 'customizing' && !customizingDecision && (
        <div 
          className="glass" 
          style={{ 
            padding: '14px 20px', 
            marginBottom: 24, 
            borderColor: 'var(--warning)', 
            background: 'rgba(245,158,11,0.08)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 16
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 20 }}>⏸️</span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>
                Customization in Progress for &ldquo;{activeDecision.video_title}&rdquo;
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                120-second lease active ({countdownRemaining}s remaining). Countdown is paused while you configure settings.
              </div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button 
              className="btn-primary" 
              style={{ fontSize: 12, padding: '6px 12px' }}
              onClick={() => handleOpenCustomizer(activeDecision)}
            >
              Resume Customizer
            </button>
            <button 
              className="btn-ghost" 
              style={{ fontSize: 12, padding: '6px 12px' }}
              onClick={() => handleApplyDefaultsDecision(activeDecision.id)}
            >
              Discard &amp; Use Defaults
            </button>
          </div>
        </div>
      )}

      {/* ── Feedback Banners ────────────────────────────────────────── */}
      {(msg || error) && (
        <div className="glass" style={{ padding: 16, marginBottom: 24, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            {msg && <div style={{ color: 'var(--success)', fontSize: 13, fontWeight: 600 }}>{msg}</div>}
            {error && <div style={{ color: 'var(--danger)', fontSize: 13, fontWeight: 600 }}>⚠️ {error}</div>}
          </div>
          {msg && (msg.includes('queued') || msg.includes('Processing initiated') || msg.includes('scheduled')) && (
            <a 
              href="/" 
              className="btn-primary" 
              style={{ fontSize: 12, padding: '6px 14px', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              📊 View on Dashboard &rarr;
            </a>
          )}
        </div>
      )}

      {/* ── Add Monitored Channel with Processing Profile ───────────── */}
      <div className="glass" style={{ padding: 24, marginBottom: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700 }}>➕ Add Monitored Channel</h2>
          <button 
            type="button" 
            className="btn-ghost" 
            style={{ fontSize: 12, padding: '4px 10px' }}
            onClick={() => setShowAdvancedAdd(!showAdvancedAdd)}
          >
            {showAdvancedAdd ? 'Hide Default Profile Settings ▲' : '⚙️ Configure Default Profile ▼'}
          </button>
        </div>

        <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
          <input 
            className="input-field" 
            style={{ flex: 1, minWidth: 'min(100%, 260px)' }}
            placeholder="https://www.youtube.com/@ChannelHandle or Channel URL"
            value={form.channel_url}
            onChange={e => setForm(f => ({ ...f, channel_url: e.target.value }))}
            onKeyDown={e => e.key === 'Enter' && handleAdd()}
          />
          <button className="btn-primary" onClick={handleAdd} disabled={adding || !form.channel_url.trim()}>
            {adding ? '⏳ Adding Channel...' : '➕ Add Channel'}
          </button>
        </div>

        {/* Toggles & Destination Row */}
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center', marginBottom: showAdvancedAdd ? 18 : 0 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>
            <input 
              type="checkbox" 
              checked={form.auto_clip} 
              onChange={e => setForm(f => ({ ...f, auto_clip: e.target.checked }))} 
            />
            Auto-clip new uploads (20s decision window)
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>
            <input 
              type="checkbox" 
              checked={form.auto_publish} 
              onChange={e => setForm(f => ({ ...f, auto_publish: e.target.checked }))} 
            />
            Auto-publish generated clips (Mock Mode)
          </label>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>Publish Destination:</span>
            <select
              className="input-field"
              style={{ fontSize: 12, padding: '6px 10px', width: 'auto', minWidth: 0, maxWidth: '100%' }}
              value={form.publish_destination_id}
              onChange={e => setForm(f => ({ ...f, publish_destination_id: e.target.value }))}
            >
              <option value="">None (Select at publish time)</option>
              {destinations.map(d => (
                <option key={d.id} value={d.id} disabled={d.is_authorized === false}>
                  {d.channel_name} ({d.youtube_channel_id}){d.is_default_destination ? ' (Default)' : ''}
                  {d.is_authorized === false ? ' (Needs Reauthorization)' : ''}
                </option>
              ))}
            </select>
            {destinations.length === 0 ? (
              <span style={{ fontSize: 11, color: '#f59e0b' }}>
                ⚠️ No destinations connected.{' '}
                <a href="/youtube-channels" style={{ color: '#f59e0b', textDecoration: 'underline' }}>Connect channel</a>
              </span>
            ) : (
              <a href="/youtube-channels" style={{ fontSize: 11, color: 'var(--text-muted)', textDecoration: 'none' }}>
                Manage destinations →
              </a>
            )}
          </div>
        </div>

        {/* Advanced Default Profile Settings Drawer */}
        {showAdvancedAdd && (
          <div style={{ 
            marginTop: 18, 
            padding: 18, 
            borderRadius: 12, 
            background: 'rgba(0,0,0,0.25)', 
            border: '1px solid var(--border)' 
          }}>
            <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)', marginBottom: 14 }}>
              🎯 Channel Default Processing Profile (Shorts Duration &le; 30.0s)
            </h4>
            <ProfileFormFields 
              profile={form.profile} 
              onChange={updated => setForm(f => ({ ...f, profile: updated }))} 
            />
          </div>
        )}
      </div>

      {/* ── Monitored Channels List ─────────────────────────────────── */}
      <div className="glass" style={{ padding: 24, marginBottom: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 18 }}>
          <h2 style={{ fontSize: 17, fontWeight: 700 }}>
            📡 Monitored Channels
            <span style={{ marginLeft: 10, fontSize: 13, fontWeight: 400, color: 'var(--text-muted)' }}>
              {channels.filter(c => c.is_active).length} active
            </span>
          </h2>
          <button className="btn-ghost" onClick={load} style={{ fontSize: 12, padding: '6px 12px' }}>
            🔄 Refresh Channels
          </button>
        </div>

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {[...Array(3)].map((_, i) => <div key={i} className="skeleton" style={{ height: 80, borderRadius: 10 }} />)}
          </div>
        ) : channels.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📡</div>
            <div style={{ fontSize: 14 }}>No channels added yet.<br />Add a YouTube channel above to start automating your clips pipeline.</div>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {channels.map(ch => {
              const profile = ch.processing_profile || DEFAULT_PROFILE;
              const hasExpanded = !!expandedChannels[ch.id];
              const pData = videoData[ch.id];
              const isVidsLoading = !!loadingVideos[ch.id];
              const currentPage = videoPages[ch.id] || 1;

              return (
                <div 
                  key={ch.id} 
                  onClick={() => handleSelectChannel(ch.id)}
                  style={{ 
                    borderRadius: 12, 
                    background: selectedChannelId === ch.id ? 'rgba(99,102,241,0.06)' : 'var(--bg-secondary)', 
                    border: selectedChannelId === ch.id ? '2px solid var(--accent)' : '1px solid var(--border)', 
                    overflow: 'hidden',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {/* Channel Header Row */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '16px 18px', flexWrap: 'wrap' }}>
                    {/* Status Indicator */}
                    <div style={{ 
                      width: 10, 
                      height: 10, 
                      borderRadius: '50%', 
                      background: ch.is_active ? 'var(--success)' : 'var(--text-muted)', 
                      boxShadow: ch.is_active ? '0 0 8px var(--success)' : 'none', 
                      flexShrink: 0 
                    }} />

                    {/* Channel Info */}
                    <div style={{ flex: 1, minWidth: 220 }}>
                      <div style={{ fontSize: 15, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                        {ch.channel_name}
                        {selectedChannelId === ch.id && (
                          <span className="badge badge-primary" style={{ fontSize: 10, fontWeight: 700 }}>
                            Active
                          </span>
                        )}
                        {ch.publish_destination_id && (
                          <span className="badge badge-info" style={{ fontSize: 10 }}>
                            🎯 Linked Destination
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                        {ch.clips_generated} clips generated · Last checked: {ch.last_checked_at_ist || (ch.last_checked_at ? new Date(ch.last_checked_at).toLocaleString() : 'Never')}
                      </div>

                      {/* Profile Settings Badges */}
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                        <span className="badge" style={{ fontSize: 10, background: 'rgba(255,255,255,0.06)' }}>
                          📐 Layout: {formatLayoutLabel(profile.video_layout)}
                        </span>
                        <span className="badge" style={{ fontSize: 10, background: 'rgba(255,255,255,0.06)' }}>
                          ⏱️ {profile.min_clip_duration || 15}s&ndash;{profile.max_clip_duration || 30}s (Shorts Cap)
                        </span>
                        <span className="badge" style={{ fontSize: 10, background: 'rgba(255,255,255,0.06)' }}>
                          🎬 {profile.clips_count || 3} Clips
                        </span>
                        <span className="badge" style={{ fontSize: 10, background: 'rgba(255,255,255,0.06)' }}>
                          ✂️ {profile.segmentation_strategy || 'hook_peak_fall'}
                        </span>
                        <span className="badge" style={{ fontSize: 10, background: 'rgba(255,255,255,0.06)' }}>
                          🧠 {profile.scoring_mode || 'ai'}
                        </span>
                      </div>
                    </div>

                    {/* Destination Assignment Selector */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={e => e.stopPropagation()}>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Destination:</span>
                      <select
                        className="input-field"
                        style={{ fontSize: 11, padding: '4px 8px', minWidth: 150 }}
                        value={ch.publish_destination_id || ''}
                        onChange={e => handleToggle(ch.id, 'publish_destination_id', e.target.value || null)}
                      >
                        <option value="">None (Select at publish time)</option>
                        {destinations.map(d => (
                          <option key={d.id} value={d.id} disabled={d.is_authorized === false}>
                            {d.channel_name} ({d.youtube_channel_id})
                            {d.is_authorized === false ? ' (Needs Reauthorization)' : ''}
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Toggles */}
                    <div style={{ display: 'flex', gap: 12, alignItems: 'center' }} onClick={e => e.stopPropagation()}>
                      <Toggle label="Auto-clip" checked={ch.auto_clip} onChange={v => handleToggle(ch.id, 'auto_clip', v)} />
                      <Toggle label="Auto-publish" checked={ch.auto_publish} onChange={v => handleToggle(ch.id, 'auto_publish', v)} />
                      <Toggle label="Active" checked={ch.is_active} onChange={v => handleToggle(ch.id, 'is_active', v)} color="var(--success)" />
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', gap: 6, alignItems: 'center' }} onClick={e => e.stopPropagation()}>
                      <button 
                        className="btn-ghost" 
                        style={{ fontSize: 11, padding: '6px 10px' }}
                        onClick={(e) => openEditProfileModal(ch, e)}
                        title="Edit default processing profile"
                      >
                        ⚙️ Edit Profile
                      </button>
                      <button 
                        type="button"
                        className="btn-primary" 
                        style={{ 
                          fontSize: 11, 
                          padding: '6px 12px', 
                          background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                          color: '#fff',
                          fontWeight: 600,
                          border: 'none',
                          boxShadow: '0 2px 8px rgba(99,102,241,0.3)'
                        }}
                        onClick={() => openHistoricalProcessor(ch.id)}
                        title="Historical Video Processing"
                      >
                        ⏳ Historical Batch
                      </button>
                      <button 
                        className="btn-ghost" 
                        style={{ fontSize: 11, padding: '6px 10px', background: hasExpanded ? 'rgba(99,102,241,0.15)' : undefined }}
                        onClick={() => toggleDiscoverVideos(ch.id)}
                      >
                        {isVidsLoading ? '⏳ Loading...' : (hasExpanded ? '📂 Hide Videos' : '🎬 Discover Videos')}
                      </button>
                      <button 
                        className="btn-ghost" 
                        style={{ fontSize: 11, padding: '6px 10px' }}
                        onClick={() => handleCheckNow(ch.id)} 
                        disabled={checking === ch.id}
                      >
                        {checking === ch.id ? '⏳' : '🔍 Scan RSS'}
                      </button>
                      <button 
                        className="btn-danger" 
                        onClick={() => handleDelete(ch.id)} 
                        style={{ padding: '6px 9px', fontSize: 12 }}
                        title="Remove monitored channel"
                      >
                        🗑
                      </button>
                    </div>
                  </div>

                  {/* ── Paginated Discovered Videos Sub-Panel ───────────── */}
                  {hasExpanded && (
                    <div 
                      onClick={e => e.stopPropagation()}
                      style={{ 
                        background: 'rgba(0,0,0,0.3)', 
                        borderTop: '1px solid var(--border)', 
                        padding: '16px 20px' 
                      }}
                    >
                      {/* ── Historical Video Processing Section ───────────── */}
                      <div style={{
                        background: 'linear-gradient(135deg, rgba(30,27,75,0.7) 0%, rgba(15,23,42,0.85) 100%)',
                        border: '1px solid rgba(139,92,246,0.3)',
                        borderRadius: 12,
                        padding: '16px 20px',
                        marginBottom: 18,
                        boxShadow: '0 4px 20px rgba(0,0,0,0.3)'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 12 }}>
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 16 }}>⏳</span>
                              <h4 style={{ fontSize: 14, fontWeight: 700, color: '#fff', margin: 0 }}>
                                Historical Video Processing
                              </h4>
                            </div>
                            <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, marginBottom: 0 }}>
                              Choose which previously uploaded videos to process. New videos will continue to be monitored automatically.
                            </p>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11, color: '#34d399', background: 'rgba(16,185,129,0.08)', padding: '4px 10px', borderRadius: 6, border: '1px solid rgba(16,185,129,0.2)' }}>
                            <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
                            <span>24/7 Auto Monitor Active for New Uploads</span>
                          </div>
                        </div>

                        {/* Two Primary Action Cards */}
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12, marginTop: 8 }}>
                          <div 
                            onClick={() => openHistoricalProcessor(ch.id, 'recent')}
                            style={{
                              padding: '14px 16px',
                              background: 'linear-gradient(135deg, rgba(99,102,241,0.12) 0%, rgba(255,255,255,0.03) 100%)',
                              borderRadius: 10,
                              border: '1px solid rgba(99,102,241,0.3)',
                              cursor: 'pointer',
                              transition: 'all 0.15s ease',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 4
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--accent)' }}>⚡ Upload Recent Videos</span>
                              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Primary Choice 1 &rarr;</span>
                            </div>
                            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.35 }}>
                              Process the newest historical uploads with optional count and date cutoff.
                            </div>
                          </div>

                          <div 
                            onClick={() => openHistoricalProcessor(ch.id, 'old')}
                            style={{
                              padding: '14px 16px',
                              background: 'linear-gradient(135deg, rgba(236,72,153,0.12) 0%, rgba(255,255,255,0.03) 100%)',
                              borderRadius: 10,
                              border: '1px solid rgba(236,72,153,0.3)',
                              cursor: 'pointer',
                              transition: 'all 0.15s ease',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: 4
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                              <span style={{ fontSize: 13, fontWeight: 700, color: '#ec4899' }}>⏳ Upload Old Videos</span>
                              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>Primary Choice 2 &rarr;</span>
                            </div>
                            <div style={{ fontSize: 11.5, color: 'var(--text-secondary)', lineHeight: 1.35 }}>
                              Backfill earlier channel uploads, ranked by verified YouTube view counts or date.
                            </div>
                          </div>
                        </div>
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                          <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', margin: 0 }}>
                            🎥 Discovered Videos from {ch.channel_name} (Page {currentPage})
                          </h4>
                          {pData && (
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                              Showing {pData.items?.length || 0} videos
                            </span>
                          )}

                          {/* Segmented Sort Controls (Latest vs Most Viewed) */}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 4, background: 'rgba(255,255,255,0.04)', padding: '2px 4px', borderRadius: 8, border: '1px solid var(--border)' }}>
                            <button
                              type="button"
                              onClick={() => handleToggleSortMode(ch.id, 'latest')}
                              style={{
                                fontSize: 11,
                                padding: '3px 8px',
                                borderRadius: 6,
                                border: 'none',
                                cursor: 'pointer',
                                background: (videoSortModes[ch.id] || 'latest') === 'latest' ? 'var(--accent)' : 'transparent',
                                color: (videoSortModes[ch.id] || 'latest') === 'latest' ? '#fff' : 'var(--text-muted)',
                                fontWeight: (videoSortModes[ch.id] || 'latest') === 'latest' ? 600 : 400,
                                transition: 'all 0.15s ease'
                              }}
                            >
                              📅 Latest
                            </button>
                            <button
                              type="button"
                              onClick={() => handleToggleSortMode(ch.id, 'most_viewed')}
                              style={{
                                fontSize: 11,
                                padding: '3px 8px',
                                borderRadius: 6,
                                border: 'none',
                                cursor: 'pointer',
                                background: videoSortModes[ch.id] === 'most_viewed' ? '#ec4899' : 'transparent',
                                color: videoSortModes[ch.id] === 'most_viewed' ? '#fff' : 'var(--text-muted)',
                                fontWeight: videoSortModes[ch.id] === 'most_viewed' ? 600 : 400,
                                transition: 'all 0.15s ease'
                              }}
                            >
                              🔥 Most Viewed
                            </button>
                          </div>
                          {videoSortModes[ch.id] === 'most_viewed' && (
                            <span className="badge badge-primary" style={{ fontSize: 10, background: 'rgba(236,72,153,0.15)', color: '#f472b6', border: '1px solid rgba(236,72,153,0.3)' }}>
                              Ranked by YouTube view count (50 scan depth)
                            </span>
                          )}
                        </div>

                        {/* Pagination & Multi-Selection Controls */}
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <button
                            type="button"
                            className="btn-ghost"
                            style={{ fontSize: 11, padding: '4px 8px', color: 'var(--accent)' }}
                            onClick={() => selectAllEligibleOnPage(ch.id)}
                            title="Select all uncompleted videos on this page"
                          >
                            ☑️ Select All Eligible
                          </button>
                          {Object.values(selectedVideos).filter(v => v.channelId === ch.id).length > 0 && (
                            <button
                              type="button"
                              className="btn-ghost"
                              style={{ fontSize: 11, padding: '4px 8px' }}
                              onClick={clearSelection}
                            >
                              ✖️ Clear ({Object.values(selectedVideos).filter(v => v.channelId === ch.id).length})
                            </button>
                          )}
                          <div style={{ width: 1, height: 16, background: 'var(--border)', margin: '0 4px' }} />
                          <button
                            className="btn-ghost"
                            style={{ fontSize: 11, padding: '4px 10px' }}
                            disabled={currentPage <= 1 || isVidsLoading}
                            onClick={() => fetchChannelVideos(ch.id, currentPage - 1)}
                          >
                            &larr; Prev
                          </button>
                          <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>
                            Page {currentPage}
                          </span>
                          <button
                            className="btn-ghost"
                            style={{ fontSize: 11, padding: '4px 10px' }}
                            disabled={!pData?.has_more || isVidsLoading}
                            onClick={() => fetchChannelVideos(ch.id, currentPage + 1)}
                          >
                            Next &rarr;
                          </button>
                          <button 
                            className="btn-ghost" 
                            style={{ fontSize: 11, padding: '4px 8px', marginLeft: 4 }}
                            onClick={() => fetchChannelVideos(ch.id, currentPage)}
                            disabled={isVidsLoading}
                            title="Refresh videos"
                          >
                            🔄
                          </button>
                        </div>
                      </div>

                      {/* Channel Batch Action Bar (if videos selected for this channel) */}
                      {Object.values(selectedVideos).filter(v => v.channelId === ch.id).length > 0 && (
                        <div style={{
                          background: 'linear-gradient(135deg, rgba(99,102,241,0.18) 0%, rgba(30,41,59,0.9) 100%)',
                          border: '1px solid var(--accent)',
                          borderRadius: 10,
                          padding: '12px 16px',
                          marginBottom: 16,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: 12,
                          flexWrap: 'wrap'
                        }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 16 }}>📌</span>
                            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                              {Object.values(selectedVideos).filter(v => v.channelId === ch.id).length} video(s) selected
                            </span>
                            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                              Ready for batch clipping &amp; processing
                            </span>
                          </div>
                          <div style={{ display: 'flex', gap: 8 }}>
                            <button
                              type="button"
                              className="btn-secondary"
                              style={{ fontSize: 11, padding: '6px 12px', background: 'rgba(255,255,255,0.06)' }}
                              onClick={() => openBatchCustomizer(ch)}
                            >
                              ⚙️ Custom Settings...
                            </button>
                            <button
                              type="button"
                              className="btn-primary"
                              style={{ fontSize: 11, padding: '6px 14px' }}
                              disabled={isBatchProcessing}
                              onClick={() => handleProcessChannelBatch(ch.id)}
                            >
                              {isBatchProcessing ? '⏳ Queuing...' : `🚀 Start Processing (${Object.values(selectedVideos).filter(v => v.channelId === ch.id).length})`}
                            </button>
                          </div>
                        </div>
                      )}

                      {isVidsLoading ? (
                        <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-muted)', fontSize: 12 }}>
                          Fetching channel videos with pagination...
                        </div>
                      ) : !pData || pData.items.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted)', fontSize: 12 }}>
                          No videos found on this page. Click &ldquo;Scan RSS&rdquo; above to check for recent uploads.
                        </div>
                      ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14 }}>
                          {pData.items.map((v: any) => {
                            const isSelected = !!selectedVideos[v.id] || selectedVideo?.id === v.id;
                            const isFailed = v.job_status === 'failed' || v.decision_status === 'failed';
                            const isProcessed = v.is_processed || (v.job_status === 'completed');

                            return (
                              <div 
                                key={v.id}
                                onClick={() => handleSelectVideo(ch.id, v)}
                                style={{ 
                                  padding: 12, 
                                  borderRadius: 10, 
                                  background: isSelected ? 'rgba(99,102,241,0.14)' : 'rgba(255,255,255,0.03)', 
                                  border: isSelected ? '2px solid var(--accent)' : '1px solid var(--border)', 
                                  boxShadow: isSelected ? '0 0 14px rgba(99,102,241,0.3)' : 'none',
                                  display: 'flex',
                                  flexDirection: 'column',
                                  justifyContent: 'space-between',
                                  gap: 10,
                                  cursor: 'pointer',
                                  transition: 'all 0.15s ease',
                                }}
                              >
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                  {/* 16:9 YouTube Video Thumbnail */}
                                  <YouTubeVideoThumbnail
                                    videoId={v.id}
                                    title={v.title}
                                    thumbnailUrl={v.thumbnail}
                                    duration={v.duration}
                                  />

                                  {/* Title, Checkbox and Badges */}
                                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, flex: 1, minWidth: 0 }}>
                                      <input
                                        type="checkbox"
                                        checked={isSelected}
                                        disabled={v.is_generated_short}
                                        onChange={() => toggleSelectVideo(ch.id, v)}
                                        onClick={(e) => e.stopPropagation()}
                                        title={v.is_generated_short ? "ClipForge-generated output Short cannot be selected as a source video." : undefined}
                                        style={{ 
                                          marginTop: 2, 
                                          cursor: v.is_generated_short ? 'not-allowed' : 'pointer', 
                                          accentColor: 'var(--accent)', 
                                          flexShrink: 0,
                                          opacity: v.is_generated_short ? 0.35 : 1
                                        }}
                                      />
                                      <div 
                                        title={v.title}
                                        style={{ 
                                          fontSize: 13, 
                                          fontWeight: 600, 
                                          color: 'var(--text-primary)', 
                                          lineHeight: '1.4',
                                          display: '-webkit-box',
                                          WebkitLineClamp: 2,
                                          WebkitBoxOrient: 'vertical',
                                          overflow: 'hidden',
                                          textOverflow: 'ellipsis',
                                          minHeight: '2.8em',
                                        }}
                                      >
                                        {v.title}
                                      </div>
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 3 }}>
                                      {v.is_generated_short && (
                                        <span 
                                          className="badge" 
                                          style={{ 
                                            fontSize: 9, 
                                            flexShrink: 0, 
                                            marginTop: 1,
                                            background: 'rgba(168,85,247,0.18)',
                                            color: '#c084fc',
                                            border: '1px solid rgba(168,85,247,0.4)'
                                          }}
                                          title={`ClipForge output Short generated from: ${v.parent_source_title || v.parent_source_id || 'source video'}`}
                                        >
                                          🎬 ClipForge Short
                                        </span>
                                      )}
                                      {isFailed ? (
                                        <span 
                                          className="badge badge-danger" 
                                          style={{ fontSize: 9, flexShrink: 0, marginTop: 1 }}
                                          title={v.job_error || 'Processing failed'}
                                        >
                                          {v.is_generated_short ? '❌ Self-Ingestion Failed' : '❌ Failed'}
                                        </span>
                                      ) : isProcessed && !v.is_generated_short ? (
                                        <span className="badge badge-success" style={{ fontSize: 9, flexShrink: 0, marginTop: 1 }}>
                                          ✓ Processed
                                        </span>
                                      ) : v.job_status ? (
                                        <span className="badge badge-warning" style={{ fontSize: 9, flexShrink: 0, marginTop: 1 }}>
                                          ⏳ {v.job_status}
                                        </span>
                                      ) : v.decision_status ? (
                                        <span className="badge badge-warning" style={{ fontSize: 9, flexShrink: 0, marginTop: 1 }}>
                                          {v.decision_status}
                                        </span>
                                      ) : null}
                                    </div>
                                  </div>

                                  {v.is_generated_short && (v.parent_source_title || v.parent_source_id) && (
                                    <div style={{ fontSize: 10.5, color: '#c084fc', paddingLeft: 22, display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap' }}>
                                      <span>Origin:</span>
                                      {v.parent_source_id ? (
                                        <a
                                          href={`https://www.youtube.com/watch?v=${v.parent_source_id}`}
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          onClick={e => e.stopPropagation()}
                                          style={{ color: 'var(--accent)', textDecoration: 'underline' }}
                                        >
                                          {v.parent_source_title || v.parent_source_id}
                                        </a>
                                      ) : (
                                        <span>{v.parent_source_title}</span>
                                      )}
                                    </div>
                                  )}

                                  <div style={{ fontSize: 11, color: 'var(--text-muted)', paddingLeft: 22 }}>
                                    Duration: {v.duration ? `${Math.round(v.duration)}s` : 'Unknown'} · {v.published_at || 'Recent'}{typeof v.view_count === 'number' ? ` · 👁️ ${v.view_count.toLocaleString()} views` : ''}
                                  </div>
                                </div>

                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, paddingTop: 4 }}>
                                  <a 
                                    href={v.url} 
                                    target="_blank" 
                                    rel="noopener noreferrer" 
                                    onClick={e => e.stopPropagation()}
                                    style={{ fontSize: 11, color: 'var(--accent)', textDecoration: 'none' }}
                                  >
                                    🔗 Watch on YouTube
                                  </a>

                                  <div style={{ display: 'flex', gap: 6 }}>
                                    <button
                                      className="btn-primary"
                                      style={{ 
                                        fontSize: 10, 
                                        padding: '5px 10px',
                                        opacity: v.is_generated_short ? 0.4 : 1,
                                        cursor: v.is_generated_short ? 'not-allowed' : 'pointer'
                                      }}
                                      disabled={processingVideo === v.id || v.is_generated_short}
                                      title={v.is_generated_short ? "ClipForge-generated output Short cannot be reprocessed as a source video." : undefined}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        if (!v.is_generated_short) handleProcessVideoDefaults(ch.id, v);
                                      }}
                                    >
                                      {processingVideo === v.id ? '⏳' : '⚡ Defaults'}
                                    </button>
                                    <button
                                      className="btn-secondary"
                                      style={{ 
                                        fontSize: 10, 
                                        padding: '5px 8px', 
                                        background: 'rgba(255,255,255,0.06)',
                                        opacity: v.is_generated_short ? 0.4 : 1,
                                        cursor: v.is_generated_short ? 'not-allowed' : 'pointer'
                                      }}
                                      disabled={v.is_generated_short}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        if (!v.is_generated_short) openCustomizerFromDiscoveredVideo(ch, v);
                                      }}
                                      title={v.is_generated_short ? "ClipForge-generated output Short cannot be reprocessed as a source video." : "Process with per-video custom settings"}
                                    >
                                      ⚙️ Custom
                                    </button>
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── Sticky Multi-Video Batch Action Bar ──────────────────────── */}
      {Object.keys(selectedVideos).length > 0 && (
        <div style={{
          position: 'sticky',
          bottom: 20,
          zIndex: 90,
          background: 'rgba(15, 23, 42, 0.95)',
          backdropFilter: 'blur(16px)',
          border: '2px solid var(--accent)',
          borderRadius: 14,
          padding: '14px 24px',
          boxShadow: '0 10px 30px rgba(0,0,0,0.6), 0 0 25px rgba(99,102,241,0.35)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          marginBottom: 24,
          flexWrap: 'wrap'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 20 }}>📌</span>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                {Object.keys(selectedVideos).length} Video{Object.keys(selectedVideos).length === 1 ? '' : 's'} Selected
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                Ready to queue into autonomous clipping and processing pipeline
              </div>
            </div>
            <button 
              type="button"
              className="btn-ghost" 
              style={{ fontSize: 11, padding: '4px 10px', marginLeft: 8 }}
              onClick={clearSelection}
            >
              Clear All
            </button>
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <button
              type="button"
              className="btn-secondary"
              style={{ fontSize: 12, padding: '8px 16px', background: 'rgba(255,255,255,0.08)' }}
              disabled={isBatchProcessing}
              onClick={() => {
                const uniqueChIds = Array.from(new Set(Object.values(selectedVideos).map(v => v.channelId).filter(Boolean)));
                if (uniqueChIds.length === 1) {
                  const ch = channels.find(c => c.id === uniqueChIds[0]);
                  if (ch) openBatchCustomizer(ch);
                } else if (uniqueChIds.length > 1) {
                  openBatchCustomizer({ id: 'global', channel_name: 'All Selected Channels', processing_profile: DEFAULT_PROFILE });
                }
              }}
            >
              ⚙️ Batch Settings...
            </button>
            <button
              type="button"
              className="btn-primary"
              style={{ fontSize: 12, padding: '8px 20px', fontWeight: 700 }}
              disabled={isBatchProcessing}
              onClick={() => handleProcessGlobalBatch()}
            >
              {isBatchProcessing ? '⏳ Queuing Videos...' : `🚀 Start Processing (${Object.keys(selectedVideos).length})`}
            </button>
          </div>
        </div>
      )}

      {/* ── Decision History Audit Table ────────────────────────────── */}
      <div className="glass" style={{ padding: 24 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 17, fontWeight: 700 }}>
              📜 Decision Lifecycle &amp; Processing History
            </h2>
            <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>
              Truthful timestamps recorded in Asia/Kolkata (IST). Shows decision resolutions, customization overrides, and background job statuses.
            </p>
          </div>
          <button 
            className="btn-ghost" 
            style={{ fontSize: 12, padding: '6px 12px' }}
            onClick={loadHistory}
            disabled={loadingHistory}
          >
            {loadingHistory ? '⏳ Loading...' : '🔄 Refresh History'}
          </button>
        </div>

        {loadingHistory && decisionHistory.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-muted)' }}>
            Loading audit history...
          </div>
        ) : decisionHistory.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '30px 0', color: 'var(--text-muted)', fontSize: 13 }}>
            No video decisions recorded yet. Decisions are automatically logged when new uploads are discovered.
          </div>
        ) : (
          <div className="table-responsive-wrapper">
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', textAlign: 'left', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '10px 12px' }}>Video / Title</th>
                  <th style={{ padding: '10px 12px' }}>Channel</th>
                  <th style={{ padding: '10px 12px' }}>Decision Status</th>
                  <th style={{ padding: '10px 12px' }}>Settings Used</th>
                  <th style={{ padding: '10px 12px' }}>Job Status</th>
                  <th style={{ padding: '10px 12px' }}>Created (IST)</th>
                  <th style={{ padding: '10px 12px' }}>Pipeline Started (IST)</th>
                  <th style={{ padding: '10px 12px' }}>Completed (IST)</th>
                </tr>
              </thead>
              <tbody>
                {decisionHistory.map(item => {
                  let statusBadge = <span className="badge badge-info">{item.status}</span>;
                  if (item.status === 'resolved_defaults') {
                    statusBadge = <span className="badge badge-success">✓ Channel Defaults</span>;
                  } else if (item.status === 'resolved_custom') {
                    statusBadge = <span className="badge badge-primary">✨ Custom Overrides</span>;
                  } else if (item.status === 'customizing') {
                    statusBadge = <span className="badge badge-warning">⏳ Customizing</span>;
                  } else if (item.status === 'awaiting_settings') {
                    statusBadge = <span className="badge badge-info">⏱️ Awaiting Decision</span>;
                  } else if (item.status === 'cancelled') {
                    statusBadge = <span className="badge badge-danger">✖ Cancelled</span>;
                  }

                  const ov = item.overrides || {};
                  const settingsSummary = ov.video_layout 
                    ? `${formatLayoutLabel(ov.video_layout)} · ${ov.min_clip_duration || 15}-${ov.max_clip_duration || 30}s`
                    : 'Channel Defaults';

                  return (
                    <tr key={item.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)' }}>
                      <td style={{ padding: '12px', minWidth: 260, maxWidth: 320 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          {item.thumbnail_url && (
                            <img
                              src={item.thumbnail_url}
                              alt=""
                              style={{ width: 52, height: 32, objectFit: 'cover', borderRadius: 4, flexShrink: 0, border: '1px solid rgba(255,255,255,0.1)' }}
                            />
                          )}
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div 
                              style={{ fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: 12.5 }}
                              title={item.source_video_title || item.video_title}
                            >
                              {item.source_video_title || item.video_title}
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                                <span>Source:</span>
                                <a 
                                  href={item.source_youtube_url || item.youtube_url} 
                                  target="_blank" 
                                  rel="noopener noreferrer" 
                                  style={{ color: 'var(--accent)', textDecoration: 'none' }}
                                >
                                  🔗 {item.source_youtube_id || item.youtube_id}
                                </a>
                              </div>
                              {item.is_generated_short && item.generated_short_id && (
                                <div style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
                                  <span style={{ color: '#ec4899', fontWeight: 600 }}>Short:</span>
                                  <a 
                                    href={item.generated_short_url || `https://www.youtube.com/shorts/${item.generated_short_id}`} 
                                    target="_blank" 
                                    rel="noopener noreferrer" 
                                    style={{ color: '#ec4899', textDecoration: 'none' }}
                                    title={item.generated_short_title || undefined}
                                  >
                                    🎬 {item.generated_short_id}
                                  </a>
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: '12px', whiteSpace: 'nowrap' }}>
                        {item.channel_name}
                      </td>
                      <td style={{ padding: '12px', whiteSpace: 'nowrap' }}>
                        {statusBadge}
                      </td>
                      <td style={{ padding: '12px', color: 'var(--text-secondary)' }}>
                        <span style={{ fontSize: 11 }}>{settingsSummary}</span>
                      </td>
                      <td style={{ padding: '12px', minWidth: 160 }}>
                        {item.job_id ? (
                          <div>
                            <span className={`badge badge-${item.job_status === 'completed' ? 'success' : item.job_status === 'failed' ? 'danger' : 'warning'}`} style={{ fontSize: 10 }}>
                              {item.job_status === 'failed' ? '❌ Failed' : item.job_status === 'completed' ? '✓ Completed' : item.job_status || 'queued'}
                            </span>
                            {item.job_status === 'failed' && (item.error_message || item.job_error) && (
                              <div 
                                style={{
                                  fontSize: 10,
                                  color: '#f87171',
                                  marginTop: 4,
                                  maxWidth: 240,
                                  maxHeight: 64,
                                  overflowY: 'auto',
                                  wordBreak: 'break-word',
                                  background: 'rgba(239,68,68,0.1)',
                                  padding: '4px 6px',
                                  borderRadius: 4,
                                  border: '1px solid rgba(239,68,68,0.2)'
                                }}
                                title={formatUserFacingError(item.error_message || item.job_error, item.current_step)}
                              >
                                {formatUserFacingError(item.error_message || item.job_error, item.current_step)}
                              </div>
                            )}
                          </div>
                        ) : (
                          <span style={{ color: 'var(--text-muted)' }}>&mdash;</span>
                        )}
                      </td>
                      <td style={{ padding: '12px', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                        {item.created_at_ist || item.created_at || '&mdash;'}
                      </td>
                      <td style={{ padding: '12px', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                        {item.pipeline_started_at_ist || item.pipeline_started_at || '&mdash;'}
                      </td>
                      <td style={{ padding: '12px', whiteSpace: 'nowrap', color: 'var(--text-secondary)' }}>
                        {item.completed_at_ist || item.completed_at || '&mdash;'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>

      {/* ── Modal: Edit Channel Processing Profile ──────────────────── */}
      {editingChannel && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.7)',
          backdropFilter: 'blur(6px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '12px 10px'
        }}>
          <div className="glass" style={{ maxWidth: 760, width: '100%', maxHeight: 'min(96vh, 720px)', overflowY: 'auto', padding: '12px 16px', borderRadius: 12 }}>
            <h3 style={{ fontSize: 14, fontWeight: 700, marginBottom: 2 }}>
              ⚙️ Default Profile for {editingChannel.channel_name}
            </h3>
            <p style={{ fontSize: 11, color: 'var(--text-secondary)', marginBottom: 8, lineHeight: 1.3 }}>
              These settings will automatically apply to all newly discovered uploads from this channel when the 20-second decision window concludes.
            </p>

            <ProfileFormFields 
              profile={editProfile} 
              onChange={setEditProfile} 
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 6, marginTop: 8 }}>
              <button 
                type="button" 
                className="btn-ghost" 
                style={{ fontSize: 11.5, padding: '5px 12px' }}
                onClick={() => setEditingChannel(null)}
                disabled={savingProfile}
              >
                Cancel
              </button>
              <button 
                type="button" 
                className="btn-primary" 
                style={{ fontSize: 11.5, padding: '5px 14px' }}
                onClick={handleSaveChannelProfile}
                disabled={savingProfile}
              >
                {savingProfile ? '⏳ Saving...' : 'Save Profile Defaults'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Per-Video Customization Overrides (120s Lease) ─────── */}
      {customizingDecision && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.75)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '12px 10px'
        }}>
          <div className="glass glow-accent" style={{ maxWidth: 760, width: '100%', maxHeight: 'min(96vh, 720px)', overflowY: 'auto', padding: '12px 16px', borderRadius: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
              <div>
                <h3 style={{ fontSize: 14, fontWeight: 700, margin: 0 }}>
                  ✨ Per-Video Customization Overrides
                </h3>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 1 }}>
                  {customizingDecision.video_title}
                </div>
              </div>
              <span className="badge badge-warning" style={{ fontSize: 9.5, fontWeight: 700, padding: '1px 5px' }}>
                120s Lease Active
              </span>
            </div>

            <div style={{ 
              background: 'rgba(245,158,11,0.1)', 
              border: '1px solid rgba(245,158,11,0.3)', 
              borderRadius: 6, 
              padding: '5px 8px', 
              fontSize: 10.5, 
              color: 'var(--text-secondary)',
              marginBottom: 8 
            }}>
              ⏸️ Auto-processing countdown is paused. Configure specific overrides below or discard to return to channel defaults.
            </div>

            <ProfileFormFields 
              profile={customOverrides} 
              onChange={setCustomOverrides} 
            />

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
              <button
                type="button"
                className="btn-danger"
                style={{ fontSize: 11, padding: '5px 10px' }}
                onClick={() => {
                  if (customizingDecision.id.startsWith('batch_') || customizingDecision.id.startsWith('manual_')) {
                    setCustomizingDecision(null);
                  } else {
                    handleCancelDecisionAction(customizingDecision.id);
                  }
                }}
              >
                {customizingDecision.id.startsWith('batch_') ? 'Close Customizer' : 'Cancel Video'}
              </button>

              <div style={{ display: 'flex', gap: 6 }}>
                <button 
                  type="button" 
                  className="btn-ghost" 
                  style={{ fontSize: 11.5, padding: '5px 12px' }}
                  onClick={() => {
                    if (customizingDecision.id.startsWith('manual_') || customizingDecision.id.startsWith('batch_')) {
                      setCustomizingDecision(null);
                    } else {
                      handleApplyDefaultsDecision(customizingDecision.id);
                      setCustomizingDecision(null);
                    }
                  }}
                  disabled={savingCustomOverrides}
                >
                  Discard &amp; Use Defaults
                </button>
                <button 
                  type="button" 
                  className="btn-primary" 
                  style={{ fontSize: 11.5, padding: '5px 14px' }}
                  onClick={
                    customizingDecision.id.startsWith('batch_')
                      ? handleSaveBatchCustom
                      : customizingDecision.id.startsWith('manual_') 
                      ? handleSaveDiscoveredVideoCustom 
                      : handleSaveAndProcessDecision
                  }
                  disabled={savingCustomOverrides}
                >
                  {savingCustomOverrides ? '⏳ Dispatching...' : '🚀 Save &amp; Start Processing'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal: Historical Video Processing & Candidate Preview ──── */}
      {showHistoricalModal && (
        <div style={{
          position: 'fixed',
          top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.8)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '16px'
        }}>
          <div className="glass glow-accent" style={{
            maxWidth: 920,
            width: '100%',
            maxHeight: '92vh',
            display: 'flex',
            flexDirection: 'column',
            borderRadius: 16,
            border: '1px solid rgba(99,102,241,0.3)',
            background: 'linear-gradient(180deg, rgba(20,20,35,0.98) 0%, rgba(15,15,25,0.98) 100%)',
            boxShadow: '0 20px 50px rgba(0,0,0,0.6)',
            overflow: 'hidden'
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '18px 24px',
              borderBottom: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'rgba(255,255,255,0.02)'
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 20 }}>⏳</span>
                  <h3 style={{ fontSize: 17, fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                    Historical Video Processing
                  </h3>
                  {historicalChannelId && (
                    <span className="badge badge-primary" style={{ fontSize: 11 }}>
                      {channels.find(c => c.id === historicalChannelId)?.channel_name || 'Channel'}
                    </span>
                  )}
                </div>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4, marginBottom: 0 }}>
                  Choose which previously uploaded videos to process. New videos will continue to be monitored automatically when Auto Monitor is enabled.
                </p>
              </div>
              <button
                type="button"
                className="btn-ghost"
                style={{ fontSize: 18, lineHeight: 1, padding: '4px 8px', borderRadius: 6 }}
                onClick={() => { setShowHistoricalModal(false); setHistoricalPreview(null); }}
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '20px 24px', overflowY: 'auto', flex: 1, display: 'flex', flexDirection: 'column', gap: 18 }}>
              
              {/* Primary Action Selection: Two Clear Choices */}
              <div>
                <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8, display: 'block' }}>
                  Choose Historical Upload Action
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
                  
                  {/* Primary Action 1: Upload Recent Videos */}
                  <div
                    onClick={() => {
                      setHistoricalPrimaryAction('recent');
                      setHistoricalMode('latest');
                      setHistoricalCount(3);
                      setHistoricalPreview(null);
                    }}
                    style={{
                      padding: '14px 16px',
                      borderRadius: 12,
                      border: historicalPrimaryAction === 'recent' ? '2px solid var(--accent)' : '1px solid var(--border)',
                      background: historicalPrimaryAction === 'recent' ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.03)',
                      boxShadow: historicalPrimaryAction === 'recent' ? '0 0 16px rgba(99,102,241,0.25)' : 'none',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: historicalPrimaryAction === 'recent' ? 'var(--accent)' : 'var(--text-primary)' }}>
                        ⚡ Upload Recent Videos
                      </span>
                      <input 
                        type="radio" 
                        name="historical_primary_action" 
                        checked={historicalPrimaryAction === 'recent'} 
                        onChange={() => {
                          setHistoricalPrimaryAction('recent');
                          setHistoricalMode('latest');
                          setHistoricalCount(3);
                          setHistoricalPreview(null);
                        }} 
                        style={{ accentColor: 'var(--accent)' }}
                      />
                    </div>
                    <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.35 }}>
                      Process the newest historical uploads from the channel. Ideal for quickly processing recent videos.
                    </div>
                  </div>

                  {/* Primary Action 2: Upload Old Videos */}
                  <div
                    onClick={() => {
                      setHistoricalPrimaryAction('old');
                      setHistoricalMode(historicalOldRanking);
                      setHistoricalCount(5);
                      setHistoricalPreview(null);
                    }}
                    style={{
                      padding: '14px 16px',
                      borderRadius: 12,
                      border: historicalPrimaryAction === 'old' ? '2px solid #ec4899' : '1px solid var(--border)',
                      background: historicalPrimaryAction === 'old' ? 'rgba(236,72,153,0.15)' : 'rgba(255,255,255,0.03)',
                      boxShadow: historicalPrimaryAction === 'old' ? '0 0 16px rgba(236,72,153,0.25)' : 'none',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 14, fontWeight: 700, color: historicalPrimaryAction === 'old' ? '#ec4899' : 'var(--text-primary)' }}>
                        ⏳ Upload Old Videos
                      </span>
                      <input 
                        type="radio" 
                        name="historical_primary_action" 
                        checked={historicalPrimaryAction === 'old'} 
                        onChange={() => {
                          setHistoricalPrimaryAction('old');
                          setHistoricalMode(historicalOldRanking);
                          setHistoricalCount(5);
                          setHistoricalPreview(null);
                        }} 
                        style={{ accentColor: '#ec4899' }}
                      />
                    </div>
                    <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.35 }}>
                      Backfill earlier channel uploads, ranked either by YouTube popularity or chronological order.
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Parameters & Controls */}
              <div style={{
                background: 'rgba(255,255,255,0.02)',
                border: '1px solid var(--border)',
                borderRadius: 12,
                padding: '16px 20px',
                display: 'flex',
                flexDirection: 'column',
                gap: 16
              }}>
                {/* Secondary Ranking Preference (Only for Old Videos) */}
                {historicalPrimaryAction === 'old' && (
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8, display: 'block' }}>
                      Old Video Ranking Priority
                    </label>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
                      <div
                        onClick={() => {
                          setHistoricalOldRanking('most_viewed');
                          setHistoricalMode('most_viewed');
                          setHistoricalPreview(null);
                        }}
                        style={{
                          padding: '10px 12px',
                          borderRadius: 8,
                          border: historicalOldRanking === 'most_viewed' ? '2px solid #ec4899' : '1px solid var(--border)',
                          background: historicalOldRanking === 'most_viewed' ? 'rgba(236,72,153,0.12)' : 'rgba(255,255,255,0.02)',
                          cursor: 'pointer'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: 12.5, fontWeight: 700, color: historicalOldRanking === 'most_viewed' ? '#ec4899' : 'var(--text-primary)' }}>
                            🔥 Most-Viewed (Recommended)
                          </span>
                          <input 
                            type="radio" 
                            name="old_ranking" 
                            checked={historicalOldRanking === 'most_viewed'} 
                            onChange={() => {}} 
                            style={{ accentColor: '#ec4899' }}
                          />
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                          Ranks candidates by verified numeric YouTube view counts.
                        </div>
                      </div>

                      <div
                        onClick={() => {
                          setHistoricalOldRanking('latest');
                          setHistoricalMode('latest');
                          setHistoricalPreview(null);
                        }}
                        style={{
                          padding: '10px 12px',
                          borderRadius: 8,
                          border: historicalOldRanking === 'latest' ? '2px solid var(--accent)' : '1px solid var(--border)',
                          background: historicalOldRanking === 'latest' ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.02)',
                          cursor: 'pointer'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: 12.5, fontWeight: 700, color: historicalOldRanking === 'latest' ? 'var(--accent)' : 'var(--text-primary)' }}>
                            📅 Chronological Order
                          </span>
                          <input 
                            type="radio" 
                            name="old_ranking" 
                            checked={historicalOldRanking === 'latest'} 
                            onChange={() => {}} 
                            style={{ accentColor: 'var(--accent)' }}
                          />
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                          Processes earlier videos in order of upload date.
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Common Inputs: Count & Scan Depth */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 4 }}>
                      Number of videos to process (1–20)
                    </label>
                    <input
                      type="number"
                      min="1"
                      max="20"
                      className="input-field"
                      style={{ width: '100%', fontSize: 13 }}
                      value={historicalCount}
                      onChange={e => { setHistoricalCount(parseInt(e.target.value) || 1); setHistoricalPreview(null); }}
                    />
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, display: 'block' }}>
                      {historicalPrimaryAction === 'recent' 
                        ? 'Processes the N most recently uploaded eligible videos.' 
                        : historicalOldRanking === 'most_viewed'
                        ? 'Processes top N most-viewed videos within scan depth.'
                        : 'Processes N earlier eligible videos.'}
                    </span>
                  </div>

                  <div>
                    <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 4 }}>
                      🔍 Historical Scan Depth
                    </label>
                    <select
                      className="input-field"
                      style={{ width: '100%', fontSize: 12, padding: '6px 10px', height: 38 }}
                      value={historicalSearchDepth}
                      onChange={e => { setHistoricalSearchDepth(parseInt(e.target.value) || 50); setHistoricalPreview(null); }}
                    >
                      <option value={30}>30 videos (Fast scan)</option>
                      <option value={50}>50 videos (Default recommendation)</option>
                      <option value={100}>100 videos (Deep scan)</option>
                      <option value={200}>200 videos (Extended catalog scan)</option>
                    </select>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, display: 'block' }}>
                      Scope of channel uploads evaluated for eligibility and ranking.
                    </span>
                  </div>
                </div>

                {/* Collapsible Advanced Filters (Date Cutoff) */}
                <div>
                  <button
                    type="button"
                    onClick={() => setShowAdvancedHistorical(prev => !prev)}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--accent)',
                      fontSize: 12,
                      cursor: 'pointer',
                      padding: 0,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4
                    }}
                  >
                    <span>{showAdvancedHistorical ? '▼' : '▶'}</span>
                    <span>Advanced Filters: Date Cutoff ({historicalSinceDate ? `After ${historicalSinceDate}` : 'None'})</span>
                  </button>

                  {showAdvancedHistorical && (
                    <div style={{ marginTop: 10, padding: '12px 14px', background: 'rgba(255,255,255,0.02)', borderRadius: 8, border: '1px solid var(--border)' }}>
                      <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', display: 'block', marginBottom: 4 }}>
                        Uploaded on or after (inclusive, optional)
                      </label>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <input
                          type="date"
                          className="input-field"
                          style={{ maxWidth: 220, fontSize: 13 }}
                          value={historicalSinceDate}
                          onChange={e => { setHistoricalSinceDate(e.target.value); setHistoricalPreview(null); }}
                        />
                        {historicalSinceDate && (
                          <button
                            type="button"
                            className="btn-ghost"
                            style={{ fontSize: 11, padding: '4px 8px' }}
                            onClick={() => { setHistoricalSinceDate(''); setHistoricalPreview(null); }}
                          >
                            ✖ Clear Date
                          </button>
                        )}
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, display: 'block' }}>
                        Filters out videos uploaded before this date UTC. Leave blank to consider all uploads in scan depth.
                      </span>
                    </div>
                  )}
                </div>

                {/* Continuous 24/7 Monitoring Notice */}
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 10,
                  padding: '10px 14px',
                  background: 'rgba(16,185,129,0.06)',
                  borderRadius: 8,
                  border: '1px solid rgba(16,185,129,0.25)'
                }}>
                  <span style={{ fontSize: 16 }}>🟢</span>
                  <div style={{ fontSize: 11.5, color: 'var(--text-secondary)' }}>
                    <strong style={{ color: '#34d399' }}>Continuous 24/7 Monitoring is Active:</strong> New videos published after channel addition will continue to be monitored and clipped automatically. Historical backfill only queues already published catalog videos.
                  </div>
                </div>
              </div>

                {/* Preview Trigger Button */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 14 }}>
                  <button
                    type="button"
                    className="btn-primary"
                    style={{
                      fontSize: 12,
                      padding: '8px 18px',
                      background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                      fontWeight: 600,
                      boxShadow: '0 2px 10px rgba(99,102,241,0.35)'
                    }}
                    onClick={loadHistoricalPreview}
                    disabled={isLoadingPreview || (historicalMode === 'uploaded_since' && !historicalSinceDate)}
                  >
                    {isLoadingPreview ? '⏳ Fetching Candidates...' : '🔍 Preview Candidates & Summary'}
                  </button>
                </div>

              {/* Preview Results & Metrics Section */}
              {historicalPreview && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  
                  {/* Summary Metric Cards */}
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10 }}>
                    <div style={{ padding: '12px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 10, border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Requested Count</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>
                        {historicalPreview.requested_count}
                      </div>
                    </div>
                    <div style={{ padding: '12px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 10, border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Eligible Found</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>
                        {historicalPreview.eligible_found}
                      </div>
                    </div>
                    <div style={{ padding: '12px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 10, border: '1px solid var(--border)' }}>
                      <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Already Processed</div>
                      <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-secondary)', marginTop: 2 }}>
                        {historicalPreview.already_processed}
                      </div>
                    </div>
                    <div style={{
                      padding: '12px 14px',
                      background: 'rgba(16,185,129,0.12)',
                      borderRadius: 10,
                      border: '1px solid rgba(16,185,129,0.4)',
                      boxShadow: '0 0 14px rgba(16,185,129,0.15)'
                    }}>
                      <div style={{ fontSize: 11, color: '#34d399', fontWeight: 600 }}>Will Actually Queue</div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: '#10b981', marginTop: 2 }}>
                        {historicalPreview.will_queue} video(s)
                      </div>
                    </div>
                  </div>

                  {/* Summary Details & Pipeline Settings Bar */}
                  <div style={{
                    padding: '12px 16px',
                    background: 'rgba(99,102,241,0.08)',
                    borderRadius: 10,
                    border: '1px solid rgba(99,102,241,0.25)',
                    display: 'flex',
                    flexWrap: 'wrap',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    fontSize: 12
                  }}>
                    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                      <div>
                        <span style={{ color: 'var(--text-muted)' }}>Channel: </span>
                        <strong>{historicalPreview.channel_name}</strong>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-muted)' }}>Destination: </span>
                        <strong>{historicalPreview.destination_channel_name}</strong>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-muted)' }}>Date Scope: </span>
                        <strong>{historicalPreview.since_date ? `On/after ${historicalPreview.since_date}` : 'All eligible history'}</strong>
                      </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span className="badge badge-success" style={{ fontSize: 10, fontWeight: 700 }}>
                        🔒 {historicalPreview.effective_privacy.toUpperCase()}
                      </span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        (Guaranteed Private Upload)
                      </span>
                    </div>
                  </div>

                  {/* Candidate Scope Banner */}
                  {historicalPreview.candidate_scope && (
                    <div style={{
                      padding: '10px 14px',
                      background: historicalPreview.candidate_scope.scope_type === 'exhaustive' ? 'rgba(16,185,129,0.08)' : 'rgba(56,189,248,0.08)',
                      borderRadius: 8,
                      border: `1px solid ${historicalPreview.candidate_scope.scope_type === 'exhaustive' ? 'rgba(16,185,129,0.3)' : 'rgba(56,189,248,0.3)'}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                      fontSize: 11
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontWeight: 700, color: historicalPreview.candidate_scope.scope_type === 'exhaustive' ? '#10b981' : '#38bdf8' }}>
                          {historicalPreview.candidate_scope.scope_type === 'exhaustive' ? '✓ Exhaustive Discovery:' : '🔍 Candidate Scope:'}
                        </span>
                        <span style={{ color: 'var(--text-secondary)' }}>
                          {historicalPreview.candidate_scope.description}
                        </span>
                      </div>
                      <span className={`badge ${historicalPreview.candidate_scope.scope_type === 'exhaustive' ? 'badge-success' : 'badge-primary'}`} style={{ fontSize: 9.5, whiteSpace: 'nowrap' }}>
                        {historicalPreview.candidate_scope.scanned_count} Videos Evaluated
                      </span>
                    </div>
                  )}

                  {/* Limitations Warning (if any) */}
                  {historicalPreview.limitations && historicalPreview.limitations.length > 0 && (
                    <div style={{
                      padding: '10px 14px',
                      background: 'rgba(234,179,8,0.08)',
                      borderRadius: 8,
                      border: '1px solid rgba(234,179,8,0.3)',
                      color: '#fbbf24',
                      fontSize: 11
                    }}>
                      <strong>⚠️ Discovery Notice:</strong>
                      <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                        {historicalPreview.limitations.map((lim, idx) => (
                          <li key={idx}>{lim}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Candidate Videos List */}
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <h4 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-secondary)', margin: 0 }}>
                        Preview Candidate Videos ({historicalPreview.items.length})
                      </h4>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                        Items marked &quot;Will Queue&quot; will be dispatched to the Celery pipeline
                      </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
                      {historicalPreview.items.map((item) => (
                        <div
                          key={item.id}
                          style={{
                            padding: 10,
                            borderRadius: 10,
                            background: item.selected_for_queue ? 'rgba(99,102,241,0.12)' : 'rgba(255,255,255,0.02)',
                            border: item.selected_for_queue ? '2px solid var(--accent)' : '1px solid var(--border)',
                            boxShadow: item.selected_for_queue ? '0 0 12px rgba(99,102,241,0.25)' : 'none',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 8,
                            transition: 'all 0.15s ease'
                          }}
                        >
                          <YouTubeVideoThumbnail
                            videoId={item.id}
                            title={item.title}
                            thumbnailUrl={item.thumbnail}
                            duration={item.duration}
                          />
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                            <div
                              title={item.title}
                              style={{
                                fontSize: 12,
                                fontWeight: 600,
                                color: 'var(--text-primary)',
                                lineHeight: '1.3',
                                display: '-webkit-box',
                                WebkitLineClamp: 2,
                                WebkitBoxOrient: 'vertical',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                minHeight: '2.6em'
                              }}
                            >
                              {item.title}
                            </div>
                          </div>

                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: 11, color: 'var(--text-muted)' }}>
                            <span>📅 {item.published_at || 'Recent'}</span>
                            {item.view_count != null && (
                              <span style={{ fontWeight: 600, color: '#ec4899' }}>
                                👁️ {item.view_count.toLocaleString()} views
                              </span>
                            )}
                          </div>

                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto', paddingTop: 4 }}>
                            {item.is_generated_short || item.publication_status === 'clipforge_short' ? (
                              <span 
                                className="badge" 
                                style={{ 
                                  fontSize: 9.5, 
                                  background: 'rgba(168,85,247,0.18)', 
                                  color: '#c084fc', 
                                  border: '1px solid rgba(168,85,247,0.4)' 
                                }}
                                title={`ClipForge output Short generated from: ${item.parent_source_title || item.parent_source_id || 'source video'}`}
                              >
                                🎬 ClipForge Short (Excluded)
                              </span>
                            ) : item.selected_for_queue ? (
                              <span className="badge badge-primary" style={{ fontSize: 9.5, fontWeight: 700, background: 'var(--accent)' }}>
                                🚀 Will Queue for Processing
                              </span>
                            ) : item.is_processed ? (
                              <span className="badge badge-success" style={{ fontSize: 9.5 }}>
                                ✓ Already Processed
                              </span>
                            ) : item.processing_status === 'processing' ? (
                              <span className="badge badge-warning" style={{ fontSize: 9.5 }}>
                                ⏳ In Flight
                              </span>
                            ) : (
                              <span className="badge" style={{ fontSize: 9.5, background: 'rgba(255,255,255,0.06)' }}>
                                Outside Top Limit
                              </span>
                            )}

                            {item.publication_status && item.publication_status !== 'none' && item.publication_status !== 'clipforge_short' && (
                              <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                                Pub: {item.publication_status}
                              </span>
                            )}
                          </div>
                          {item.parent_source_title && (
                            <div style={{ fontSize: 10, color: '#c084fc', marginTop: 2 }}>
                              Origin: {item.parent_source_title}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer Actions */}
            <div style={{
              padding: '14px 24px',
              borderTop: '1px solid var(--border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'rgba(255,255,255,0.02)'
            }}>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => { setShowHistoricalModal(false); setHistoricalPreview(null); }}
                disabled={isSubmittingHistorical}
              >
                Cancel
              </button>

              <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                {historicalMode === 'new_only' ? (
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ fontSize: 12, padding: '8px 20px', background: '#10b981', fontWeight: 600 }}
                    onClick={executeHistoricalBatch}
                    disabled={isSubmittingHistorical}
                  >
                    {isSubmittingHistorical ? '⏳ Updating...' : '✓ Confirm Continuous Monitoring Only'}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="btn-primary"
                    style={{
                      fontSize: 12,
                      padding: '8px 22px',
                      background: 'linear-gradient(135deg, #6366f1 0%, #a855f7 100%)',
                      fontWeight: 700,
                      boxShadow: '0 4px 14px rgba(99,102,241,0.4)'
                    }}
                    onClick={executeHistoricalBatch}
                    disabled={isSubmittingHistorical || !historicalPreview || historicalPreview.will_queue === 0}
                  >
                    {isSubmittingHistorical 
                      ? '⏳ Submitting Batch...' 
                      : `🚀 Start Historical Processing (${historicalPreview?.will_queue || 0} videos)`}
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── Reusable Profile Form Component ──────────────────────────────────
function ProfileFormFields({ 
  profile, 
  onChange 
}: { 
  profile: ChannelProcessingProfile; 
  onChange: (p: ChannelProcessingProfile) => void;
}) {
  const updateField = (field: keyof ChannelProcessingProfile, val: any) => {
    onChange({ ...profile, [field]: val });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* Interactive Video Layout Preview Gallery */}
      <LayoutPreviewSelector
        value={profile.video_layout || 'fill_blur'}
        onChange={val => updateField('video_layout', val)}
      />

      {/* Duration Range & Shorts Cap Enforcement */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <label style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginBottom: 1 }}>
            Min Duration ({profile.min_clip_duration || 15}s)
          </label>
          <input 
            type="range"
            min="15"
            max={profile.max_clip_duration || 30}
            step="1"
            value={profile.min_clip_duration || 15}
            onChange={e => {
              const val = parseFloat(e.target.value);
              updateField('min_clip_duration', val);
            }}
            style={{ width: '100%' }}
          />
          <span style={{ fontSize: 9.5, color: 'var(--text-muted)' }}>Min: 15.0s</span>
        </div>

        <div>
          <label style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginBottom: 1 }}>
            Max Duration ({profile.max_clip_duration || 30}s &mdash; Shorts Cap)
          </label>
          <input 
            type="range"
            min={profile.min_clip_duration || 15}
            max="30"
            step="1"
            value={Math.min(30, profile.max_clip_duration || 30)}
            onChange={e => {
              const val = Math.min(30, parseFloat(e.target.value));
              updateField('max_clip_duration', val);
            }}
            style={{ width: '100%' }}
          />
          <span style={{ fontSize: 9.5, color: 'var(--accent)' }}>Capped at 30.0s for Shorts</span>
        </div>
      </div>

      {/* Target Clips Count & Duration Mode */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <label style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginBottom: 1 }}>
            Clips Count: {profile.clips_count || 3} clips
          </label>
          <input 
            type="range"
            min="1"
            max="10"
            step="1"
            value={profile.clips_count || 3}
            onChange={e => updateField('clips_count', parseInt(e.target.value))}
            style={{ width: '100%' }}
          />
        </div>

        <div>
          <label style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginBottom: 1 }}>
            Duration Mode
          </label>
          <select
            className="input-field"
            style={{ width: '100%', fontSize: 11, padding: '4px 8px', height: 28 }}
            value={profile.duration_mode || 'adaptive'}
            onChange={e => updateField('duration_mode', e.target.value)}
          >
            <option value="adaptive">Adaptive (Content-Aware Length)</option>
            <option value="fixed">Fixed Target Duration</option>
          </select>
        </div>
      </div>

      {/* Segmentation Strategy & Scoring Mode */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <div>
          <label style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginBottom: 1 }}>
            Segmentation Strategy
          </label>
          <select
            className="input-field"
            style={{ width: '100%', fontSize: 11, padding: '4px 8px', height: 28 }}
            value={profile.segmentation_strategy || 'hook_peak_fall'}
            onChange={e => updateField('segmentation_strategy', e.target.value)}
          >
            <option value="hook_peak_fall">Hook &rarr; Peak &rarr; Resolution (Smart)</option>
            <option value="equal_splits">Equal Splits (Even Slices)</option>
          </select>
        </div>

        <div>
          <label style={{ fontSize: 10.5, color: 'var(--text-muted)', display: 'block', marginBottom: 1 }}>
            Scoring Mode
          </label>
          <select
            className="input-field"
            style={{ width: '100%', fontSize: 11, padding: '4px 8px', height: 28 }}
            value={profile.scoring_mode || 'ai'}
            onChange={e => updateField('scoring_mode', e.target.value)}
          >
            <option value="ai">AI Multimodal Scoring (Gemini)</option>
          </select>
        </div>
      </div>
    </div>
  );
}

// ── Reusable Toggle Component ─────────────────────────────────────────
function Toggle({ 
  label, 
  checked, 
  onChange, 
  color = 'var(--accent)' 
}: { 
  label: string; 
  checked: boolean; 
  onChange: (v: boolean) => void; 
  color?: string;
}) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, cursor: 'pointer' }}>
      <div 
        onClick={() => onChange(!checked)} 
        style={{
          width: 36, 
          height: 20, 
          borderRadius: 10, 
          position: 'relative', 
          cursor: 'pointer',
          background: checked ? color : 'var(--border)', 
          transition: 'background 0.2s',
        }}
      >
        <div style={{
          position: 'absolute', 
          top: 2, 
          left: checked ? 18 : 2, 
          width: 16, 
          height: 16,
          borderRadius: '50%', 
          background: 'white', 
          transition: 'left 0.2s', 
          boxShadow: '0 1px 3px rgba(0,0,0,0.3)'
        }} />
      </div>
      <span style={{ fontSize: 10, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{label}</span>
    </label>
  );
}
