'use client';

import { useState, useEffect, Suspense } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { 
  listClips, 
  publishNow, 
  schedulePublish, 
  getPublishQueue, 
  getAuthStatus, 
  getChannelInfo, 
  getDestinations,
  submitOAuthCode,
  thumbnailUrl,
  cancelPublish,
  retryPublish,
  getClipPublishMetadata,
  updateClipPublishMetadata,
  type PublishQueueItem,
  type ClipPublishMetadata
} from '@/lib/api';
import VisualClipPicker, { SquareClipThumbnail } from '@/components/publish/VisualClipPicker';

// SVG Icons
const BackIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 12H5M12 19l-7-7 7-7"/>
  </svg>
);

const ChevronRight = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 18l6-6-6-6"/>
  </svg>
);

const GlobeIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/>
    <line x1="2" y1="12" x2="22" y2="12"/>
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
  </svg>
);

const LockIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
    <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
  </svg>
);

const EyeOffIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
    <line x1="1" y1="1" x2="23" y2="23"/>
  </svg>
);

const DescriptionIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="21" y1="10" x2="3" y2="10"/>
    <line x1="21" y1="6" x2="3" y2="6"/>
    <line x1="21" y1="14" x2="3" y2="14"/>
    <line x1="21" y1="18" x2="3" y2="18"/>
  </svg>
);

const AudienceIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
    <circle cx="9" cy="7" r="4"/>
    <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
    <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
  </svg>
);

const AttributesIcon = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="4" y1="21" x2="4" y2="14"/>
    <line x1="4" y1="10" x2="4" y2="3"/>
    <line x1="12" y1="21" x2="12" y2="12"/>
    <line x1="12" y1="8" x2="12" y2="3"/>
    <line x1="20" y1="21" x2="20" y2="16"/>
    <line x1="20" y1="12" x2="20" y2="3"/>
    <line x1="1" y1="14" x2="7" y2="14"/>
    <line x1="9" y1="8" x2="15" y2="8"/>
    <line x1="17" y1="16" x2="23" y2="16"/>
  </svg>
);

const getCategoryName = (id: string) => {
  const categories: { [key: string]: string } = {
    '22': 'People & Blogs',
    '24': 'Entertainment',
    '23': 'Comedy',
    '20': 'Gaming',
    '27': 'Education',
    '28': 'Science & Tech',
    '1': 'Film & Animation',
    '2': 'Autos & Vehicles',
    '10': 'Music',
    '17': 'Sports',
  };
  return categories[id] || 'People & Blogs';
};

const getLicenseName = (id: string) => {
  return id === 'youtube' ? 'Standard YouTube License' : 'Creative Commons - Attribution';
};

function PublishPageContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const clipParam = searchParams.get('clip');
  const channelParam = searchParams.get('channel');
  const oauthSuccess = searchParams.get('oauth');

  const [clips, setClips] = useState<any[]>([]);
  const [selectedClip, setSelectedClip] = useState<any>(null);
  const [destinations, setDestinations] = useState<any[]>([]);
  const [selectedDestinationId, setSelectedDestinationId] = useState<string>('');
  const [queue, setQueue] = useState<PublishQueueItem[]>([]);
  const [queueLoading, setQueueLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState<{ [clipId: string]: 'cancel' | 'retry' | null }>({});
  const [authInfo, setAuthInfo] = useState<{ authenticated: boolean; oauth_url?: string } | null>(null);
  const [channelInfo, setChannelInfo] = useState<{ id: string; title: string; thumbnail: string; subscribers: number } | null>(null);

  // Subscreen navigation inside mobile mockup: 'main' | 'description' | 'visibility' | 'audience' | 'attributes'
  const [activeSubScreen, setActiveSubScreen] = useState<'main' | 'description' | 'visibility' | 'audience' | 'attributes'>('main');

  const [form, setForm] = useState({
    title: '',
    description: '',
    privacy: 'public',
    scheduleDate: '',
    madeForKids: false,
    ageRestricted: false,
    tags: '',
    category: '22',
    license: 'youtube'
  });

  const [publishing, setPublishing] = useState(false);
  const [isSavingMetadata, setIsSavingMetadata] = useState(false);
  const [metadataDirty, setMetadataDirty] = useState(false);
  const [msg, setMsg] = useState('');
  const [error, setError] = useState('');
  const [thumbSrc, setThumbSrc] = useState<string>('');
  
  // OAuth manual code entry
  const [oauthPasteUrl, setOAuthPasteUrl] = useState('');
  const [submitAuthLoading, setSubmitAuthLoading] = useState(false);

  // Load destinations once on mount and synchronize with URL / localStorage
  useEffect(() => {
    getDestinations().then(data => {
      const destList = data || [];
      setDestinations(destList);
      
      const storedChannel = typeof window !== 'undefined' ? localStorage.getItem('last_publish_channel_id') : null;
      let initialChannelId = '';

      if (channelParam && destList.some((d: any) => d.id === channelParam)) {
        initialChannelId = channelParam;
      } else if (storedChannel && destList.some((d: any) => d.id === storedChannel)) {
        initialChannelId = storedChannel;
      } else if (storedChannel && !destList.some((d: any) => d.id === storedChannel)) {
        // Stale or unrecognized channel ID in localStorage -> purge it safely
        if (typeof window !== 'undefined') {
          localStorage.removeItem('last_publish_channel_id');
        }
      }

      // Preserve explicit choice (including empty / None)
      setSelectedDestinationId(initialChannelId);
      if (typeof window !== 'undefined' && initialChannelId) {
        localStorage.setItem('last_publish_channel_id', initialChannelId);
      }
    }).catch(err => {
      console.error('Error fetching destinations:', err);
    });
  }, [channelParam]);

  useEffect(() => {
    // Handle OAuth callback redirect
    if (oauthSuccess === 'success') {
      setMsg('✅ YouTube account connected successfully! You can now publish videos.');
      // Refresh auth status and destinations
      getAuthStatus().then(setAuthInfo).catch(() => {});
      getDestinations().then(setDestinations).catch(() => {});
      // Clean up URL parameter
      router.replace('/publish');
      return;
    }

    getAuthStatus().then(setAuthInfo).catch(() => {});
    listClips().then(data => {
      // Sort clips by date created / rating descending
      const sorted = [...data].sort((a, b) => b.score - a.score);
      setClips(sorted);
      
      const targetId = clipParam || (sorted.length > 0 ? sorted[0].id : null);
      if (targetId) {
        const found = sorted.find(c => c.id === targetId);
        if (found) {
          setSelectedClip(found);
          setThumbSrc(thumbnailUrl(found.id));
          setForm(f => ({
            ...f,
            title: found.title || '',
            description: found.description || '',
            tags: found.tags || '',
            category: found.category || '22',
            license: found.license || 'youtube',
            madeForKids: found.made_for_kids || false,
            ageRestricted: found.age_restricted || false,
            privacy: found.privacy || 'public'
          }));

          // Synchronize destination with clip's assigned destination
          if (found.publish_destination_id) {
            setSelectedDestinationId(found.publish_destination_id);
            if (typeof window !== 'undefined') {
              localStorage.setItem('last_publish_channel_id', found.publish_destination_id);
            }
          } else {
            setSelectedDestinationId('');
          }
        }
      }
    }).catch(() => {});
    fetchQueue();
  }, [clipParam, oauthSuccess]);

  const fetchQueue = async () => {
    try {
      setQueueLoading(true);
      const data = await getPublishQueue();
      setQueue(data || []);
    } catch (err: any) {
      console.error('Error fetching publish queue:', err);
    } finally {
      setQueueLoading(false);
    }
  };

  const handleCancelPublish = async (clipId: string) => {
    try {
      setActionLoading(prev => ({ ...prev, [clipId]: 'cancel' }));
      setError('');
      setMsg('');
      const res = await cancelPublish(clipId);
      setMsg(`✅ ${res.message || 'Publication cancelled successfully.'}`);
      setQueue(prev => prev.map(item => item.id === clipId ? { ...item, publish_status: res.status || 'cancelled', publish_stage: 'cancelled' } : item));
      await fetchQueue();
    } catch (err: any) {
      setError(err.message || 'Failed to cancel publication.');
    } finally {
      setActionLoading(prev => ({ ...prev, [clipId]: null }));
    }
  };

  const handleRetryPublish = async (clipId: string, force: boolean = false) => {
    try {
      setActionLoading(prev => ({ ...prev, [clipId]: 'retry' }));
      setError('');
      setMsg('');
      const res = await retryPublish(clipId, force);
      setMsg(`🚀 ${res.message || 'Retry publication queued successfully.'}`);
      setQueue(prev => prev.map(item => item.id === clipId ? { ...item, publish_status: 'queued', publish_stage: 'queued', publish_error: null } : item));
      await fetchQueue();
    } catch (err: any) {
      setError(err.message || 'Failed to retry publication.');
    } finally {
      setActionLoading(prev => ({ ...prev, [clipId]: null }));
    }
  };

  // Auto-poll queue every 4 seconds if any active publishing job exists
  useEffect(() => {
    const hasActive = queue.some(q => 
      ['queued', 'uploading', 'finalizing', 'publishing', 'cancelling'].includes(q.publish_status)
    );
    if (!hasActive) return;

    const interval = setInterval(() => {
      getPublishQueue().then(data => {
        if (data) setQueue(data);
      }).catch(() => {});
    }, 4000);

    return () => clearInterval(interval);
  }, [queue]);

  useEffect(() => {
    if (authInfo?.authenticated) {
      getChannelInfo().then(setChannelInfo).catch(err => {
        console.error('Error fetching channel details:', err);
      });
    }
  }, [authInfo]);

  const handleDestinationChange = (destId: string) => {
    setSelectedDestinationId(destId);
    if (selectedClip) {
      setMetadataDirty(true);
    }
    if (typeof window !== 'undefined') {
      if (destId) {
        localStorage.setItem('last_publish_channel_id', destId);
      } else {
        localStorage.removeItem('last_publish_channel_id');
      }
    }

    // Stale selection check: if currently selected clip belongs to a different destination channel,
    // clear it so it cannot remain selected when no longer eligible.
    let activeClip = selectedClip;
    if (selectedClip && selectedClip.publish_destination_id && destId && selectedClip.publish_destination_id !== destId) {
      activeClip = null;
      setSelectedClip(null);
      setThumbSrc('');
      setForm({
        title: '',
        description: '',
        privacy: 'public',
        scheduleDate: '',
        madeForKids: false,
        ageRestricted: false,
        tags: '',
        category: '22',
        license: 'youtube'
      });
    }

    const clipPart = activeClip ? `clip=${activeClip.id}` : '';
    const destPart = destId ? `channel=${destId}` : '';
    const query = [clipPart, destPart].filter(Boolean).join('&');
    router.push(query ? `/publish?${query}` : '/publish');
  };

  const handleSelectClip = async (clipId: string) => {
    if (!clipId) {
      setSelectedClip(null);
      setThumbSrc('');
      setForm({
        title: '',
        description: '',
        privacy: 'public',
        scheduleDate: '',
        madeForKids: false,
        ageRestricted: false,
        tags: '',
        category: '22',
        license: 'youtube'
      });
      setMetadataDirty(false);
      router.push('/publish');
      return;
    }

    const found = clips.find(c => c.id === clipId);
    setSelectedClip(found || { id: clipId, title: 'Selected Clip' });
    setThumbSrc(thumbnailUrl(clipId));
    setActiveSubScreen('main');
    setMsg('');
    setError('');

    // Try fetching authoritative persisted metadata from backend
    try {
      const meta = await getClipPublishMetadata(clipId);
      if (meta) {
        setForm({
          title: meta.title || '',
          description: meta.description || '',
          privacy: meta.privacy || 'public',
          scheduleDate: meta.scheduled_at ? new Date(meta.scheduled_at).toISOString().slice(0, 16) : '',
          madeForKids: meta.made_for_kids || false,
          ageRestricted: meta.age_restricted || false,
          tags: Array.isArray(meta.tags) ? meta.tags.join(', ') : (meta.tags || ''),
          category: meta.category || '22',
          license: meta.license || 'youtube'
        });

        if (meta.publish_destination_id) {
          setSelectedDestinationId(meta.publish_destination_id);
          if (typeof window !== 'undefined') {
            localStorage.setItem('last_publish_channel_id', meta.publish_destination_id);
          }
        }
      }
    } catch {
      // Fallback to local clip attributes if network or offline
      if (found) {
        setForm({
          title: found.title || '',
          description: found.description || '',
          privacy: found.privacy || 'public',
          scheduleDate: found.scheduled_at ? new Date(found.scheduled_at).toISOString().slice(0, 16) : '',
          madeForKids: found.made_for_kids || false,
          ageRestricted: found.age_restricted || false,
          tags: found.tags || '',
          category: found.category || '22',
          license: found.license || 'youtube'
        });
        if (found.publish_destination_id) {
          setSelectedDestinationId(found.publish_destination_id);
        }
      }
    }

    setMetadataDirty(false);
    const destId = found?.publish_destination_id || '';
    const query = [`clip=${clipId}`, destId ? `channel=${destId}` : ''].filter(Boolean).join('&');
    router.push(`/publish?${query}`);
  };

  const handleSaveMetadata = async () => {
    if (!selectedClip) return;
    const cleanTitle = form.title.trim();
    if (!cleanTitle) {
      setError('Title cannot be empty.');
      return;
    }
    if (cleanTitle.length > 100) {
      setError('Title cannot exceed 100 characters.');
      return;
    }
    if (form.description.length > 5000) {
      setError('Description cannot exceed 5000 characters.');
      return;
    }

    setIsSavingMetadata(true);
    setError('');
    setMsg('');

    try {
      const res = await updateClipPublishMetadata(selectedClip.id, {
        title: cleanTitle,
        description: form.description,
        tags: form.tags,
        category: form.category,
        license: form.license,
        privacy: form.privacy,
        made_for_kids: form.madeForKids,
        age_restricted: form.ageRestricted,
        publish_destination_id: selectedDestinationId || null,
      });

      // Update UI only after persistence succeeds
      const savedMeta = res.metadata;
      setSelectedClip((prev: any) => prev ? {
        ...prev,
        title: savedMeta.title,
        description: savedMeta.description,
        tags: savedMeta.tags.join(', '),
        category: savedMeta.category,
        license: savedMeta.license,
        privacy: savedMeta.privacy,
        made_for_kids: savedMeta.made_for_kids,
        age_restricted: savedMeta.age_restricted,
        publish_destination_id: savedMeta.publish_destination_id,
      } : prev);

      // Update clips list item
      setClips((prevClips: any[]) => prevClips.map((c: any) =>
        c.id === selectedClip.id
          ? { ...c, title: savedMeta.title, description: savedMeta.description, tags: savedMeta.tags.join(', ') }
          : c
      ));

      // Update queue item title if it exists in queue
      setQueue((prevQueue: PublishQueueItem[]) => prevQueue.map(q =>
        q.id === selectedClip.id
          ? { ...q, title: savedMeta.title }
          : q
      ));

      setMsg('💾 Clip metadata saved successfully!');
      setMetadataDirty(false);
    } catch (err: any) {
      setError(err.message || 'Failed to save clip metadata.');
    } finally {
      setIsSavingMetadata(false);
    }
  };

  const handleActionSubmit = async () => {
    if (!selectedClip) return;
    if (!selectedDestinationId) {
      setError('Please select an authorized publishing destination channel before publishing.');
      return;
    }
    const matchedDest = destinations.find(d => d.id === selectedDestinationId);
    if (!matchedDest || matchedDest.is_authorized === false) {
      setError('The selected destination channel is inactive, unauthorized, or not configured.');
      return;
    }
    setPublishing(true);
    setError('');
    setMsg('');
    try {
      if (form.scheduleDate) {
        await schedulePublish({
          clip_id: selectedClip.id,
          destination_channel_id: selectedDestinationId,
          scheduled_at: new Date(form.scheduleDate).toISOString(),
          title: form.title,
          description: form.description,
          privacy: form.privacy,
          made_for_kids: form.madeForKids,
          age_restricted: form.ageRestricted,
          tags: form.tags,
          category: form.category,
          license: form.license
        });
        setMsg(`📅 Scheduled for ${new Date(form.scheduleDate).toLocaleString()}`);
      } else {
        const res = await publishNow({
          clip_id: selectedClip.id,
          destination_channel_id: selectedDestinationId,
          title: form.title,
          description: form.description,
          privacy: form.privacy,
          made_for_kids: form.madeForKids,
          age_restricted: form.ageRestricted,
          tags: form.tags,
          category: form.category,
          license: form.license
        });
        setMsg(`🚀 Upload Successful! Video ID: ${res.video_id}`);
      }
      fetchQueue();
    } catch (e: any) {
      setError(e.message || 'Publish operations failed');
    }
    setPublishing(false);
  };

  const handleSubmitOAuthUrl = async () => {
    const trimmedUrl = oauthPasteUrl.trim();
    if (!trimmedUrl) {
      setError('Please paste the authorization URL or code');
      return;
    }
    
    setSubmitAuthLoading(true);
    setError('');
    setMsg('');
    
    console.log('[OAuth] Submitting URL/code:', trimmedUrl);
    console.log('[OAuth] Contains code=:', trimmedUrl.includes('code='));
    
    try {
      await submitOAuthCode(trimmedUrl);
      setMsg('Γ£à YouTube account connected successfully!');
      setOAuthPasteUrl('');
      // Refresh auth status
      await getAuthStatus().then(setAuthInfo).catch(() => {});
    } catch (e: any) {
      console.error('[OAuth Error]', e);
      setError(e.message || 'Failed to authenticate with YouTube. Make sure you pasted the complete URL with the code parameter.');
    }
    setSubmitAuthLoading(false);
  };

  // Helper to get privacy details matching icon
  const getPrivacyDetails = () => {
    if (form.scheduleDate) {
      return { label: 'Scheduled', icon: <GlobeIcon /> };
    }
    switch (form.privacy) {
      case 'public': return { label: 'Public', icon: <GlobeIcon /> };
      case 'unlisted': return { label: 'Unlisted', icon: <EyeOffIcon /> };
      case 'private': return { label: 'Private', icon: <LockIcon /> };
      default: return { label: 'Public', icon: <GlobeIcon /> };
    }
  };

  const currentPrivacy = getPrivacyDetails();
  const isSubmitDisabled =
    publishing ||
    !selectedClip ||
    !form.title.trim() ||
    !selectedDestinationId ||
    destinations.find(d => d.id === selectedDestinationId)?.is_authorized === false;

  return (
    <div className="animate-fade-up">
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 28, fontWeight: 800, fontFamily: "'Space Grotesk', sans-serif" }} className="gradient-text">
          ≡ƒÜÇ Publish to YouTube Shorts
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: 14, marginTop: 4 }}>
          Adjust audience configurations, descriptors, classification categories, and tags via our interactive simulator.
        </p>
      </div>

      {/* Auth Notification Block */}
      {authInfo && !authInfo.authenticated && (
        <div className="glass" style={{ padding: '16px 20px', marginBottom: 28, borderColor: 'rgba(245,158,11,0.3)', background: 'rgba(245,158,11,0.05)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 16 }}>
            <div>
              <h3 style={{ fontSize: 15, fontWeight: 600, color: 'var(--warning)', display: 'flex', alignItems: 'center', gap: 6 }}>
                ΓÜá∩╕Å YouTube Account Not Connected
              </h3>
              <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
                OAuth credentials required to submit or schedule direct uploads.
              </p>
            </div>
            {authInfo.oauth_url && (
              <a href={authInfo.oauth_url} target="_blank" rel="noopener noreferrer" className="btn-primary" style={{ background: 'var(--warning)', boxShadow: 'none', color: '#0d141d' }}>
                ≡ƒöù Connect Google Account
              </a>
            )}
          </div>
        </div>
      )}

      {/* Manual OAuth Code Entry for Desktop Apps */}
      {authInfo && !authInfo.authenticated && (
        <div className="glass" style={{ padding: 20, marginBottom: 28, borderColor: 'rgba(59,130,246,0.3)', background: 'rgba(59,130,246,0.05)' }}>
          <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 6, color: 'var(--accent)' }}>
            ≡ƒÆ╗ Or Paste Authorization Code
          </h3>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
            If you selected "Desktop application" in Google Cloud Console, paste the full redirect URL or authorization code below:
          </p>
          <textarea
            placeholder="Paste the full URL (http://localhost:8080/?code=...) or just the authorization code"
            value={oauthPasteUrl}
            onChange={(e) => setOAuthPasteUrl(e.target.value)}
            style={{
              width: '100%',
              minHeight: '80px',
              padding: '10px 12px',
              background: 'rgba(255,255,255,0.03)',
              border: '1px solid var(--border)',
              borderRadius: 8,
              color: 'var(--text-primary)',
              fontFamily: 'monospace',
              fontSize: 12,
              marginBottom: 12,
              resize: 'vertical'
            }}
          />
          <button
            onClick={handleSubmitOAuthUrl}
            disabled={submitAuthLoading || !oauthPasteUrl.trim()}
            style={{
              padding: '8px 16px',
              background: submitAuthLoading ? 'rgba(59,130,246,0.5)' : 'var(--accent)',
              color: '#fff',
              border: 'none',
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              cursor: submitAuthLoading || !oauthPasteUrl.trim() ? 'not-allowed' : 'pointer',
              opacity: submitAuthLoading || !oauthPasteUrl.trim() ? 0.5 : 1
            }}
          >
            {submitAuthLoading ? 'ΓÅ│ Authenticating...' : 'Γ£ô Submit Authorization Code'}
          </button>
        </div>
      )}

      <div className="publish-page-grid" style={{ minWidth: 0, width: '100%' /* minmax responsive grid columns */ }}>
        
        {/* LEFT COLUMN: Selector and stats */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div className="glass" style={{ padding: 20 }}>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              🎬 Choose Clip
            </h3>
            
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8 }}>
                Select Clip
              </label>
              <VisualClipPicker
                clips={clips}
                selectedClipId={selectedClip?.id || null}
                onSelectClip={handleSelectClip}
                selectedDestinationId={selectedDestinationId}
              />
            </div>

            {/* Destination Channel Selector */}
            <div style={{ marginBottom: 16 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
                🎯 Publishing Destination Channel
              </label>
              <select
                className="input-field"
                value={selectedDestinationId}
                onChange={e => handleDestinationChange(e.target.value)}
                style={{ fontSize: 13, padding: '10px 12px' }}
              >
                <option value="">None (Select at publish time)</option>
                {destinations.map(d => (
                  <option key={d.id} value={d.id} disabled={d.is_authorized === false}>
                    {d.channel_name} ({d.youtube_channel_id})
                    {d.is_default_destination ? ' (Default)' : ''}
                    {d.is_authorized === false ? ' (Needs Reauthorization)' : ''}
                  </option>
                ))}
              </select>
              {selectedDestinationId ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
                  {destinations.find(d => d.id === selectedDestinationId)?.thumbnail_url && (
                    <img 
                      src={destinations.find(d => d.id === selectedDestinationId)?.thumbnail_url} 
                      alt="avatar" 
                      style={{ width: 16, height: 16, borderRadius: '50%', objectFit: 'cover' }} 
                    />
                  )}
                  <span>Target: <strong style={{ color: 'var(--accent)' }}>
                    {destinations.find(d => d.id === selectedDestinationId)?.channel_name || selectedDestinationId}
                  </strong></span>
                  <span style={{ color: 'var(--success)' }}>● Authorized</span>
                </div>
              ) : (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                  ℹ️ Clips published without an assigned destination will remain in draft/unassigned state.{' '}
                  <a href="/youtube-channels" style={{ color: 'var(--accent)', textDecoration: 'underline' }}>Manage channels</a>
                </div>
              )}
              {destinations.length === 0 && (
                <div style={{ fontSize: 11, color: '#f59e0b', marginTop: 6 }}>
                  ⚠️ No authorized YouTube channels connected.{' '}
                  <a href="/youtube-channels" style={{ color: '#f59e0b', textDecoration: 'underline', fontWeight: 600 }}>Connect channel</a>
                </div>
              )}
            </div>

            {selectedClip && (
              <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: 10, padding: 12, border: '1px solid var(--border)', fontSize: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Duration:</span>
                  <span style={{ fontWeight: 600 }}>{selectedClip.duration.toFixed(1)}s</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Scoring:</span>
                  <span style={{ fontWeight: 600, color: 'var(--accent)' }}>{(selectedClip.score || 0).toFixed(1)} Γÿà</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Timestamp:</span>
                  <span>{selectedClip.start_time.toFixed(1)}s - {selectedClip.end_time.toFixed(1)}s</span>
                </div>
              </div>
            )}
          </div>

          {/* Feedback panels */}
          {(msg || error) && (
            <div className="glass" style={{ padding: 16 }}>
              {msg && (
                <div style={{ padding: 12, background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)', color: 'var(--success)', borderRadius: 8, fontSize: 13 }}>
                  {msg}
                </div>
              )}
              {error && (
                <div style={{ padding: 12, background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: 'var(--danger)', borderRadius: 8, fontSize: 13 }}>
                  ΓÜá∩╕Å {error}
                </div>
              )}
            </div>
          )}
        </div>

        {/* MIDDLE COLUMN: YouTube Mobile Mockup */}
        <div style={{ display: 'flex', justifyContent: 'center', width: '100%', maxWidth: '100%' }}>
          {selectedClip ? (
            <div className="yt-phone-frame">
              {/* Top Notch speaker bar */}
              <div className="yt-phone-notch"></div>

              {/* PHONE SCREEN CONTAINER */}
              <div className="yt-phone-screen">
                
                {/* 1. MAIN MENU SCREEN */}
                {activeSubScreen === 'main' && (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {/* Header bar */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid #222' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                        <button 
                          style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: 0 }}
                          onClick={() => handleSelectClip('')}
                          title="Cancel selection"
                        >
                          <BackIcon />
                        </button>
                        <span style={{ fontSize: 16, fontWeight: 700 }}>Add details</span>
                      </div>
                      
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <button
                          onClick={handleSaveMetadata}
                          disabled={isSavingMetadata || !selectedClip || !form.title.trim()}
                          data-testid="btn-save-metadata"
                          style={{
                            background: metadataDirty ? 'rgba(59, 130, 246, 0.2)' : 'rgba(255, 255, 255, 0.08)',
                            color: metadataDirty ? '#60a5fa' : '#bbb',
                            border: metadataDirty ? '1px solid rgba(59, 130, 246, 0.5)' : '1px solid #444',
                            borderRadius: 18,
                            padding: '6px 12px',
                            fontSize: 12,
                            fontWeight: 600,
                            cursor: isSavingMetadata || !selectedClip || !form.title.trim() ? 'not-allowed' : 'pointer',
                            transition: 'all 0.2s',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4
                          }}
                          title="Save metadata draft to database without publishing"
                        >
                          {isSavingMetadata ? '⏳ Saving...' : (metadataDirty ? '💾 Save Draft •' : '✓ Saved')}
                        </button>

                        <button 
                          onClick={handleActionSubmit}
                          disabled={isSubmitDisabled}
                          style={{
                            background: isSubmitDisabled ? '#333' : '#3ea6ff',
                            color: isSubmitDisabled ? '#777' : '#000',
                            border: 'none',
                            borderRadius: 18,
                            padding: '6px 14px',
                            fontSize: 12,
                            fontWeight: 700,
                            cursor: isSubmitDisabled ? 'not-allowed' : 'pointer',
                            transition: 'all 0.2s'
                          }}
                        >
                          {publishing ? '...' : (form.scheduleDate ? 'Schedule' : 'UPLOAD')}
                        </button>
                      </div>
                    </div>

                    {/* Content Area */}
                    <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>
                      
                      {/* Title & Thumbnail Section */}
                      <div style={{ display: 'flex', gap: 12, alignItems: 'start' }}>
                        {/* Title text area */}
                        <div style={{ flex: 1, position: 'relative' }}>
                          <textarea
                            value={form.title}
                            onChange={e => {
                              setForm(f => ({ ...f, title: e.target.value.slice(0, 100) }));
                              setMetadataDirty(true);
                            }}
                            placeholder="Title your Short (e.g. #Shorts)"
                            maxLength={100}
                            style={{
                              width: '100%',
                              height: 90,
                              background: 'transparent',
                              border: 'none',
                              borderBottom: '1px solid #333',
                              color: '#fff',
                              fontSize: 14,
                              fontFamily: 'inherit',
                              resize: 'none',
                              outline: 'none',
                              padding: 0,
                              lineHeight: '1.4'
                            }}
                          />
                          <div style={{ position: 'absolute', right: 0, bottom: -18, fontSize: 10, color: '#888' }}>
                            {form.title.length}/100
                          </div>
                        </div>

                        {/* Video Thumbnail Box */}
                        <div 
                          style={{
                            width: 75,
                            height: 110,
                            borderRadius: 8,
                            overflow: 'hidden',
                            background: '#1f1f1f',
                            position: 'relative',
                            border: '1px solid #333',
                            flexShrink: 0
                          }}
                        >
                          {thumbSrc ? (
                            <img 
                              src={thumbSrc} 
                              alt="Thumbnail preview" 
                              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              onError={() => setThumbSrc('')}
                            />
                          ) : (
                            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', color: '#666', fontSize: 10 }}>
                              9:16
                            </div>
                          )}
                          <div style={{
                            position: 'absolute',
                            bottom: 4,
                            left: '50%',
                            transform: 'translateX(-50%)',
                            background: 'rgba(235, 12, 12, 0.85)',
                            color: '#fff',
                            fontSize: 7,
                            fontWeight: 800,
                            padding: '2px 4px',
                            borderRadius: 2,
                            letterSpacing: '0.05em'
                          }}>
                            SHORTS
                          </div>
                        </div>
                      </div>

                      {/* Divider */}
                      <div style={{ height: 1, background: '#222', margin: '8px 0' }} />

                      {/* Channel profile row */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <div 
                          style={{ 
                            width: 32, 
                            height: 32, 
                            borderRadius: '50%', 
                            background: '#2c3e50', 
                            overflow: 'hidden',
                            border: '1px solid #444',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center'
                          }}
                        >
                          {channelInfo?.thumbnail ? (
                            <img src={channelInfo.thumbnail} alt="Channel Avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                          ) : (
                            <span style={{ fontSize: 12, fontWeight: 700 }}>CF</span>
                          )}
                        </div>
                        <div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>
                            {destinations.find(d => d.id === selectedDestinationId)?.channel_name || channelInfo?.title || 'Creator Channel'}
                          </div>
                          <div style={{ fontSize: 11, color: '#aaa', marginTop: 2 }}>
                            {destinations.find(d => d.id === selectedDestinationId)
                              ? 'Publishing Target Destination'
                              : (channelInfo ? `${(channelInfo.subscribers).toLocaleString()} subscribers` : 'Connecting channel...')}
                          </div>
                        </div>
                      </div>

                      {/* Divider */}
                      <div style={{ height: 1, background: '#222', margin: '4px 0' }} />

                      {/* Options Rows */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        
                        {/* Description option */}
                        <div 
                          onClick={() => setActiveSubScreen('description')}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '12px 8px',
                            borderRadius: 8,
                            cursor: 'pointer',
                            transition: 'background 0.2s',
                          }}
                          onMouseEnter={e => e.currentTarget.style.backgroundColor = '#1c1c1c'}
                          onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                            <div style={{ color: '#aaa' }}><DescriptionIcon /></div>
                            <span style={{ fontSize: 14 }}>Add description</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#aaa' }}>
                            <span style={{ fontSize: 12, color: '#777', maxWidth: 120, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {form.description || 'None'}
                            </span>
                            <ChevronRight />
                          </div>
                        </div>

                        {/* Visibility Option */}
                        <div 
                          onClick={() => setActiveSubScreen('visibility')}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '12px 8px',
                            borderRadius: 8,
                            cursor: 'pointer',
                            transition: 'background 0.2s'
                          }}
                          onMouseEnter={e => e.currentTarget.style.backgroundColor = '#1c1c1c'}
                          onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                            <div style={{ color: '#aaa' }}>{currentPrivacy.icon}</div>
                            <span style={{ fontSize: 14 }}>Visibility</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#aaa' }}>
                            <span style={{ fontSize: 12, color: form.scheduleDate ? 'var(--warning)' : '#777' }}>
                              {currentPrivacy.label}
                            </span>
                            <ChevronRight />
                          </div>
                        </div>

                        {/* Audience Option */}
                        <div 
                          onClick={() => setActiveSubScreen('audience')}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '12px 8px',
                            borderRadius: 8,
                            cursor: 'pointer',
                            transition: 'background 0.2s'
                          }}
                          onMouseEnter={e => e.currentTarget.style.backgroundColor = '#1c1c1c'}
                          onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                            <div style={{ color: '#aaa' }}><AudienceIcon /></div>
                            <span style={{ fontSize: 14 }}>Select audience</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#aaa' }}>
                            <span style={{ fontSize: 12, color: '#777' }}>
                              {form.madeForKids ? 'Made for kids' : 'No, not for kids'}
                            </span>
                            <ChevronRight />
                          </div>
                        </div>

                        {/* Advanced attributes / categories option */}
                        <div 
                          onClick={() => setActiveSubScreen('attributes')}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '12px 8px',
                            borderRadius: 8,
                            cursor: 'pointer',
                            transition: 'background 0.2s'
                          }}
                          onMouseEnter={e => e.currentTarget.style.backgroundColor = '#1c1c1c'}
                          onMouseLeave={e => e.currentTarget.style.backgroundColor = 'transparent'}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                            <div style={{ color: '#aaa' }}><AttributesIcon /></div>
                            <span style={{ fontSize: 14 }}>Advanced Attributes</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#aaa' }}>
                            <span style={{ fontSize: 12, color: '#777' }}>
                              {getCategoryName(form.category)}
                            </span>
                            <ChevronRight />
                          </div>
                        </div>

                      </div>

                      {/* Footer YouTube notice text */}
                      <div style={{ marginTop: 'auto', fontSize: 10, color: '#555', textAlign: 'center', lineHeight: '1.4', padding: '0 8px' }}>
                        By tapping Upload Short, you accept terms and authorize ClipForge pipeline metadata updates.
                      </div>
                    </div>

                    {/* Bottom Action button */}
                    <div style={{ padding: 12, borderTop: '1px solid #222' }}>
                      <button
                        onClick={handleActionSubmit}
                        disabled={isSubmitDisabled}
                        style={{
                          width: '100%',
                          background: isSubmitDisabled ? '#2c2c2c' : 'linear-gradient(135deg, var(--accent), var(--accent-2))',
                          color: isSubmitDisabled ? '#666' : '#0d141d',
                          border: 'none',
                          borderRadius: 20,
                          padding: '12px 0',
                          fontSize: 14,
                          fontWeight: 700,
                          cursor: isSubmitDisabled ? 'not-allowed' : 'pointer',
                          transition: 'all 0.2s'
                        }}
                      >
                        {publishing ? 'Publishing Pipeline Active...' : (form.scheduleDate ? 'Schedule Upload' : 'Upload Short')}
                      </button>
                    </div>

                  </div>
                )}

                {/* 2. DESCRIPTION SUBSCREEN */}
                {activeSubScreen === 'description' && (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {/* Header */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px', borderBottom: '1px solid #222' }}>
                      <button 
                        style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: 0 }}
                        onClick={() => setActiveSubScreen('main')}
                      >
                        <BackIcon />
                      </button>
                      <span style={{ fontSize: 16, fontWeight: 700 }}>Add description</span>
                    </div>

                    {/* Text area body */}
                    <div style={{ flex: 1, padding: 16, position: 'relative' }}>
                      <textarea
                        value={form.description}
                        onChange={e => {
                          setForm(f => ({ ...f, description: e.target.value.slice(0, 5000) }));
                          setMetadataDirty(true);
                        }}
                        placeholder="Describe your short video here..."
                        maxLength={5000}
                        style={{
                          width: '100%',
                          height: '90%',
                          background: 'transparent',
                          border: 'none',
                          color: '#fff',
                          fontSize: 14,
                          fontFamily: 'inherit',
                          resize: 'none',
                          outline: 'none',
                          lineHeight: '1.5'
                        }}
                      />
                      <div style={{ position: 'absolute', right: 16, bottom: 16, fontSize: 11, color: '#888' }}>
                        {form.description.length}/5000
                      </div>
                    </div>
                  </div>
                )}

                {/* 3. VISIBILITY SUBSCREEN */}
                {activeSubScreen === 'visibility' && (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {/* Header */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px', borderBottom: '1px solid #222' }}>
                      <button 
                        style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: 0 }}
                        onClick={() => setActiveSubScreen('main')}
                      >
                        <BackIcon />
                      </button>
                      <span style={{ fontSize: 16, fontWeight: 700 }}>Visibility</span>
                    </div>

                    {/* Radio Selectors */}
                    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 20 }}>
                      
                      {/* Public */}
                      <label style={{ display: 'flex', alignItems: 'start', gap: 14, cursor: 'pointer' }}>
                        <input 
                          type="radio" 
                          name="privacy" 
                          value="public"
                          checked={form.privacy === 'public'}
                          onChange={() => {
                            setForm(f => ({ ...f, privacy: 'public' }));
                            setMetadataDirty(true);
                          }}
                          style={{ marginTop: 4 }}
                        />
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600 }}>Public</div>
                          <div style={{ fontSize: 12, color: '#aaa', marginTop: 2 }}>Everyone can watch your video</div>
                        </div>
                      </label>

                      {/* Unlisted */}
                      <label style={{ display: 'flex', alignItems: 'start', gap: 14, cursor: 'pointer' }}>
                        <input 
                          type="radio" 
                          name="privacy" 
                          value="unlisted"
                          checked={form.privacy === 'unlisted'}
                          onChange={() => {
                            setForm(f => ({ ...f, privacy: 'unlisted' }));
                            setMetadataDirty(true);
                          }}
                          style={{ marginTop: 4 }}
                        />
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600 }}>Unlisted</div>
                          <div style={{ fontSize: 12, color: '#aaa', marginTop: 2 }}>Anyone with the link can watch your video</div>
                        </div>
                      </label>

                      {/* Private */}
                      <label style={{ display: 'flex', alignItems: 'start', gap: 14, cursor: 'pointer' }}>
                        <input 
                          type="radio" 
                          name="privacy" 
                          value="private"
                          checked={form.privacy === 'private'}
                          onChange={() => {
                            setForm(f => ({ ...f, privacy: 'private' }));
                            setMetadataDirty(true);
                          }}
                          style={{ marginTop: 4 }}
                        />
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 600 }}>Private</div>
                          <div style={{ fontSize: 12, color: '#aaa', marginTop: 2 }}>Only you and people you choose can watch</div>
                        </div>
                      </label>

                      {/* Divider */}
                      <div style={{ height: 1, background: '#222', margin: '8px 0' }} />

                      {/* Scheduling section */}
                      <div>
                        <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 10 }}>Schedule Publication</h4>
                        <p style={{ fontSize: 11, color: '#888', marginBottom: 12 }}>
                          Select date/time to delay publish. Video will be private before scheduled time.
                        </p>
                        
                        <input 
                          type="datetime-local" 
                          value={form.scheduleDate}
                          onChange={e => {
                            setForm(f => ({ ...f, scheduleDate: e.target.value }));
                            setMetadataDirty(true);
                          }}
                          style={{
                            width: '100%',
                            background: '#1c1c1c',
                            border: '1px solid #333',
                            borderRadius: 8,
                            padding: '10px 12px',
                            color: '#fff',
                            fontSize: 13,
                            outline: 'none'
                          }}
                        />

                        {/* Quick Presets */}
                        <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
                          <button
                            type="button"
                            onClick={() => {
                              const d = new Date(Date.now() + 3600000);
                              d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
                              setForm(f => ({ ...f, scheduleDate: d.toISOString().slice(0, 16) }));
                              setMetadataDirty(true);
                            }}
                            style={{ padding: '4px 8px', borderRadius: 6, background: '#262626', border: '1px solid #404040', color: '#ccc', fontSize: 11, cursor: 'pointer' }}
                          >
                            +1 Hour
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              const d = new Date();
                              d.setDate(d.getDate() + 1);
                              d.setHours(9, 0, 0, 0);
                              d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
                              setForm(f => ({ ...f, scheduleDate: d.toISOString().slice(0, 16) }));
                              setMetadataDirty(true);
                            }}
                            style={{ padding: '4px 8px', borderRadius: 6, background: '#262626', border: '1px solid #404040', color: '#ccc', fontSize: 11, cursor: 'pointer' }}
                          >
                            Tomorrow 9 AM
                          </button>
                          <button
                            type="button"
                            onClick={() => {
                              const d = new Date();
                              d.setDate(d.getDate() + 1);
                              d.setHours(18, 0, 0, 0);
                              d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
                              setForm(f => ({ ...f, scheduleDate: d.toISOString().slice(0, 16) }));
                              setMetadataDirty(true);
                            }}
                            style={{ padding: '4px 8px', borderRadius: 6, background: '#262626', border: '1px solid #404040', color: '#ccc', fontSize: 11, cursor: 'pointer' }}
                          >
                            Tomorrow 6 PM
                          </button>
                        </div>

                        {form.scheduleDate && (
                          <button
                            onClick={() => {
                              setForm(f => ({ ...f, scheduleDate: '' }));
                              setMetadataDirty(true);
                            }}
                            style={{
                              marginTop: 10,
                              background: 'none',
                              border: 'none',
                              color: 'var(--danger)',
                              fontSize: 12,
                              cursor: 'pointer',
                              padding: 0
                            }}
                          >
                            ✕ Clear Scheduled Time
                          </button>
                        )}

                      </div>

                    </div>
                  </div>
                )}

                {/* 4. AUDIENCE SUBSCREEN (COPPA) */}
                {activeSubScreen === 'audience' && (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {/* Header */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px', borderBottom: '1px solid #222' }}>
                      <button 
                        style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: 0 }}
                        onClick={() => setActiveSubScreen('main')}
                      >
                        <BackIcon />
                      </button>
                      <span style={{ fontSize: 16, fontWeight: 700 }}>Select audience</span>
                    </div>

                    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 20 }}>
                      <div>
                        <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Is this video made for kids? (Required)</h4>
                        <p style={{ fontSize: 11, color: '#aaa', lineHeight: '1.4', marginBottom: 16 }}>
                          Regardless of your location, you're legally required to comply with the Children's Online Privacy Protection Act (COPPA) and/or other laws. You're required to tell us if your videos are made for kids.
                        </p>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                            <input 
                              type="radio" 
                              name="madeForKids" 
                              checked={form.madeForKids === true}
                              onChange={() => {
                                setForm(f => ({ ...f, madeForKids: true }));
                                setMetadataDirty(true);
                              }}
                            />
                            <span style={{ fontSize: 13 }}>Yes, it's made for kids.</span>
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                            <input 
                              type="radio" 
                              name="madeForKids" 
                              checked={form.madeForKids === false}
                              onChange={() => {
                                setForm(f => ({ ...f, madeForKids: false }));
                                setMetadataDirty(true);
                              }}
                            />
                            <span style={{ fontSize: 13 }}>No, it's not made for kids.</span>
                          </label>
                        </div>
                      </div>

                      {/* Divider */}
                      <div style={{ height: 1, background: '#222', margin: '8px 0' }} />

                      <div>
                        <h4 style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>Age restriction (Advanced)</h4>
                        <p style={{ fontSize: 11, color: '#aaa', lineHeight: '1.4', marginBottom: 16 }}>
                          Age-restricted videos aren't shown in certain areas of YouTube, and may have limited or no ads.
                        </p>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                            <input 
                              type="radio" 
                              name="ageRestricted" 
                              checked={form.ageRestricted === true}
                              onChange={() => {
                                setForm(f => ({ ...f, ageRestricted: true }));
                                setMetadataDirty(true);
                              }}
                            />
                            <span style={{ fontSize: 13 }}>Yes, restrict my video to viewers over 18</span>
                          </label>

                          <label style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}>
                            <input 
                              type="radio" 
                              name="ageRestricted" 
                              checked={form.ageRestricted === false}
                              onChange={() => {
                                setForm(f => ({ ...f, ageRestricted: false }));
                                setMetadataDirty(true);
                              }}
                            />
                            <span style={{ fontSize: 13 }}>No, don't restrict my video to viewers over 18</span>
                          </label>
                        </div>
                      </div>

                    </div>
                  </div>
                )}

                {/* 5. ATTRIBUTES SUBSCREEN */}
                {activeSubScreen === 'attributes' && (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    {/* Header */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px', borderBottom: '1px solid #222' }}>
                      <button 
                        style={{ background: 'none', border: 'none', color: '#fff', cursor: 'pointer', padding: 0 }}
                        onClick={() => setActiveSubScreen('main')}
                      >
                        <BackIcon />
                      </button>
                      <span style={{ fontSize: 16, fontWeight: 700 }}>Advanced Attributes</span>
                    </div>

                    <div style={{ padding: 16, display: 'flex', flexDirection: 'column', gap: 18 }}>
                      
                      {/* Category */}
                      <div>
                        <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#aaa', marginBottom: 6 }}>
                          YouTube Category
                        </label>
                        <select
                          value={form.category}
                          onChange={e => {
                            setForm(f => ({ ...f, category: e.target.value }));
                            setMetadataDirty(true);
                          }}
                          style={{
                            width: '100%',
                            background: '#1c1c1c',
                            border: '1px solid #333',
                            borderRadius: 8,
                            padding: '10px',
                            color: '#fff',
                            fontSize: 13,
                            outline: 'none'
                          }}
                        >
                          <option value="22">People & Blogs</option>
                          <option value="24">Entertainment</option>
                          <option value="23">Comedy</option>
                          <option value="20">Gaming</option>
                          <option value="27">Education</option>
                          <option value="28">Science & Tech</option>
                          <option value="1">Film & Animation</option>
                          <option value="10">Music</option>
                          <option value="17">Sports</option>
                        </select>
                      </div>

                      {/* License */}
                      <div>
                        <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#aaa', marginBottom: 6 }}>
                          Content License
                        </label>
                        <select
                          value={form.license}
                          onChange={e => {
                            setForm(f => ({ ...f, license: e.target.value }));
                            setMetadataDirty(true);
                          }}
                          style={{
                            width: '100%',
                            background: '#1c1c1c',
                            border: '1px solid #333',
                            borderRadius: 8,
                            padding: '10px',
                            color: '#fff',
                            fontSize: 13,
                            outline: 'none'
                          }}
                        >
                          <option value="youtube">Standard YouTube License</option>
                          <option value="creativeCommon">Creative Commons - Attribution</option>
                        </select>
                      </div>

                      {/* Tags */}
                      <div>
                        <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#aaa', marginBottom: 4 }}>
                          Search Tags
                        </label>
                        <p style={{ fontSize: 10, color: '#888', marginBottom: 8 }}>
                          Comma-separated tags (e.g. funny, viral, shorts)
                        </p>
                        <textarea
                          value={form.tags}
                          onChange={e => {
                            setForm(f => ({ ...f, tags: e.target.value }));
                            setMetadataDirty(true);
                          }}
                          placeholder="gaming, shorts, funny"
                          style={{
                            width: '100%',
                            height: 70,
                            background: '#1c1c1c',
                            border: '1px solid #333',
                            borderRadius: 8,
                            padding: '10px',
                            color: '#fff',
                            fontSize: 13,
                            fontFamily: 'inherit',
                            resize: 'none',
                            outline: 'none'
                          }}
                        />

                        {/* Keyword badge list */}
                        {form.tags.trim() && (
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                            {form.tags.split(',')
                              .map(t => t.trim())
                              .filter(t => t.length > 0)
                              .map((tag, idx) => (
                                <span 
                                  key={idx} 
                                  style={{ 
                                    background: 'rgba(192, 193, 255, 0.1)', 
                                    border: '1px solid rgba(192, 193, 255, 0.2)',
                                    color: 'var(--accent)',
                                    borderRadius: 6,
                                    padding: '2px 8px',
                                    fontSize: 10,
                                    fontWeight: 600
                                  }}
                                >
                                  #{tag}
                                </span>
                              ))
                            }
                          </div>
                        )}
                      </div>

                    </div>
                  </div>
                )}

              </div>
            </div>
          ) : (
            <div className="glass" style={{ padding: '40px 20px', width: '100%', maxWidth: 360, minHeight: 400, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', textAlign: 'center', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 48, marginBottom: 16 }}>📱</div>
              <h4 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 8 }}>Simulator Offline</h4>
              <p style={{ fontSize: 12, lineHeight: 1.4 }}>
                Select a video clip from the left dropdown list to initialize high-fidelity YouTube Mobile screen emulation.
              </p>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Queue status and lists */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          
          <div className="glass" style={{ padding: 20, width: '100%', minWidth: 0 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ fontSize: 15, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                📋 Publishing Queue
                {queue.length > 0 && (
                  <span style={{ fontSize: 11, background: 'rgba(255,255,255,0.08)', padding: '2px 8px', borderRadius: 12, color: 'var(--text-secondary)' }}>
                    {queue.length}
                  </span>
                )}
              </h3>
              <button
                onClick={fetchQueue}
                disabled={queueLoading}
                data-testid="btn-refresh-queue"
                style={{
                  background: 'transparent',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '4px 10px',
                  color: 'var(--text-secondary)',
                  fontSize: 11,
                  fontWeight: 600,
                  cursor: queueLoading ? 'not-allowed' : 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                  transition: 'all 0.15s ease'
                }}
              >
                <span style={{ display: 'inline-block', transform: queueLoading ? 'rotate(180deg)' : 'none', transition: 'transform 0.4s ease' }}>🔄</span>
                Refresh
              </button>
            </div>
            
            {queue.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '36px 0', color: 'var(--text-muted)' }}>
                <div style={{ fontSize: 32, marginBottom: 8 }}>📦</div>
                <div style={{ fontSize: 12 }}>Queue empty. Broadcasts will display here.</div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12, maxHeight: 'calc(100vh - 240px)', overflowY: 'auto', paddingRight: 4 }}>
                {queue.map(q => {
                  const matchingClip = clips.find(c => c.id === q.id);
                  const destinationChannel = destinations.find(d => d.id === q.publish_destination_id);
                  const canCancel = ['queued', 'scheduled', 'draft', 'uploading', 'finalizing', 'publishing'].includes(q.publish_status);
                  const canRetry = ['failed', 'cancelled', 'manual_review'].includes(q.publish_status);
                  const isUploading = ['uploading', 'finalizing', 'publishing'].includes(q.publish_status);
                  const isManualReview = q.publish_status === 'manual_review';

                  // Badge styling logic
                  let badgeClass = 'badge-warning';
                  let badgeIcon = '⏱';
                  let badgeText = q.publish_status;

                  if (q.publish_status === 'published') {
                    badgeClass = 'badge-success';
                    badgeIcon = '✓';
                    badgeText = 'published';
                  } else if (q.publish_status === 'failed') {
                    badgeClass = 'badge-danger';
                    badgeIcon = '⚠';
                    badgeText = 'failed';
                  } else if (q.publish_status === 'cancelled') {
                    badgeClass = '';
                    badgeIcon = '✕';
                    badgeText = 'cancelled';
                  } else if (q.publish_status === 'cancelling') {
                    badgeClass = 'badge-warning';
                    badgeIcon = '⏳';
                    badgeText = 'cancelling...';
                  } else if (q.publish_status === 'manual_review') {
                    badgeClass = 'badge-warning';
                    badgeIcon = '🔍';
                    badgeText = 'manual review';
                  } else if (isUploading) {
                    badgeClass = '';
                    badgeIcon = '⚡';
                    badgeText = q.publish_stage ? `${q.publish_stage} (${q.publish_progress || 0}%)` : `uploading (${q.publish_progress || 0}%)`;
                  } else if (q.publish_status === 'scheduled') {
                    badgeClass = '';
                    badgeIcon = '📅';
                    badgeText = 'scheduled';
                  }

                  return (
                    <div 
                      key={q.id} 
                      data-testid={`publish-queue-item-${q.id}`}
                      style={{ 
                        padding: 12, 
                        borderRadius: 10, 
                        background: 'rgba(255,255,255,0.02)', 
                        border: '1px solid var(--border)', 
                        fontSize: 12,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 10,
                        transition: 'border-color 0.2s ease'
                      }}
                    >
                      {/* Top Row: Square Thumbnail + Details + Badge */}
                      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                        {/* 1:1 Square Thumbnail (56x56 px) */}
                        <SquareClipThumbnail
                          clipId={q.id}
                          alt={q.title || 'Published Short'}
                          size={56}
                          youtubeShortId={q.youtube_short_id}
                        />

                        {/* Text Metadata */}
                        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 6 }}>
                            <div 
                              style={{ 
                                fontWeight: 600, 
                                color: 'var(--text-primary)', 
                                overflow: 'hidden', 
                                textOverflow: 'ellipsis', 
                                whiteSpace: 'nowrap', 
                                maxWidth: 170,
                                fontSize: 13,
                              }} 
                              title={q.title || 'Untitled Short'}
                            >
                              {q.title || 'Untitled Short'}
                            </div>
                            <span 
                              className={`badge ${badgeClass}`} 
                              style={{ 
                                fontSize: 9, 
                                textTransform: 'uppercase', 
                                letterSpacing: '0.04em',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 3,
                                whiteSpace: 'nowrap',
                                padding: '2px 6px',
                                flexShrink: 0
                              }}
                            >
                              <span>{badgeIcon}</span>
                              <span>{badgeText}</span>
                            </span>
                          </div>

                          {/* Source Video Title */}
                          <div 
                            style={{ 
                              fontSize: 11, 
                              color: 'var(--text-muted)', 
                              overflow: 'hidden', 
                              textOverflow: 'ellipsis', 
                              whiteSpace: 'nowrap' 
                            }}
                            title={matchingClip?.source_title ? `Source: ${matchingClip.source_title}` : 'Source video'}
                          >
                            Source: {matchingClip?.source_title || 'Original Video'}
                          </div>

                          {/* Channel & Timestamp Info */}
                          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                            {q.privacy && (
                              <span style={{ padding: '1px 5px', borderRadius: 3, background: 'rgba(255,255,255,0.06)', color: 'var(--text-secondary)' }}>
                                {q.privacy}
                              </span>
                            )}
                            {destinationChannel && (
                              <span style={{ color: 'var(--accent)', fontWeight: 500 }} title={`Target: ${destinationChannel.channel_name}`}>
                                📺 {destinationChannel.channel_name}
                              </span>
                            )}
                            {q.publish_attempt && q.publish_attempt > 1 ? (
                              <span style={{ color: '#f59e0b' }}>
                                Attempt #{q.publish_attempt}
                              </span>
                            ) : null}
                            <span>
                              {q.publish_status === 'published'
                                ? (q.published_at ? new Date(q.published_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : '')
                                : (q.scheduled_at ? new Date(q.scheduled_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : (
                                  q.publish_started_at ? new Date(q.publish_started_at).toLocaleString(undefined, { dateStyle: 'short', timeStyle: 'short' }) : ''
                                ))
                              }
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* In-flight progress bar */}
                      {isUploading && (
                        <div style={{ marginTop: 2, display: 'flex', flexDirection: 'column', gap: 4 }}>
                          <div style={{ height: 4, width: '100%', background: 'rgba(255,255,255,0.08)', borderRadius: 2, overflow: 'hidden' }}>
                            <div 
                              style={{ 
                                height: '100%', 
                                width: `${Math.max(q.publish_progress || 0, 5)}%`, 
                                background: 'linear-gradient(90deg, #3b82f6, #8b5cf6)', 
                                transition: 'width 0.3s ease' 
                              }} 
                            />
                          </div>
                        </div>
                      )}

                      {/* Error details box */}
                      {q.publish_error && (
                        <div style={{ 
                          padding: '6px 10px', 
                          borderRadius: 6, 
                          background: 'rgba(239, 68, 68, 0.08)', 
                          border: '1px solid rgba(239, 68, 68, 0.2)', 
                          color: '#fca5a5', 
                          fontSize: 11, 
                          lineHeight: 1.35,
                          wordBreak: 'break-word' 
                        }}>
                          <div style={{ fontWeight: 600, fontSize: 10, textTransform: 'uppercase', marginBottom: 2, color: '#ef4444' }}>
                            Error Details
                          </div>
                          {q.publish_error}
                        </div>
                      )}

                      {/* Interactive Controls Row */}
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          {canCancel && (
                            <button
                              onClick={() => handleCancelPublish(q.id)}
                              disabled={actionLoading[q.id] === 'cancel'}
                              data-testid={`btn-cancel-publish-${q.id}`}
                              style={{
                                background: 'rgba(239, 68, 68, 0.1)',
                                border: '1px solid rgba(239, 68, 68, 0.3)',
                                color: '#ef4444',
                                borderRadius: 6,
                                padding: '4px 10px',
                                fontSize: 11,
                                fontWeight: 600,
                                cursor: actionLoading[q.id] === 'cancel' ? 'not-allowed' : 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4,
                                transition: 'all 0.15s ease'
                              }}
                            >
                              {actionLoading[q.id] === 'cancel' ? '⏳ Cancelling...' : '✕ Cancel'}
                            </button>
                          )}

                          {canRetry && (
                            <button
                              onClick={() => handleRetryPublish(q.id, isManualReview)}
                              disabled={actionLoading[q.id] === 'retry'}
                              data-testid={isManualReview ? `btn-force-retry-${q.id}` : `btn-retry-publish-${q.id}`}
                              title={isManualReview ? 'Force retry after checking YouTube remote state' : 'Retry publication'}
                              style={{
                                background: isManualReview ? 'rgba(249, 115, 22, 0.15)' : 'rgba(59, 130, 246, 0.15)',
                                border: isManualReview ? '1px solid rgba(249, 115, 22, 0.4)' : '1px solid rgba(59, 130, 246, 0.4)',
                                color: isManualReview ? '#f97316' : '#60a5fa',
                                borderRadius: 6,
                                padding: '4px 10px',
                                fontSize: 11,
                                fontWeight: 600,
                                cursor: actionLoading[q.id] === 'retry' ? 'not-allowed' : 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4,
                                transition: 'all 0.15s ease'
                              }}
                            >
                              {actionLoading[q.id] === 'retry' ? '⏳ Queuing...' : (isManualReview ? '⚠️ Force Retry' : '🔄 Retry')}
                            </button>
                          )}

                          {['queued', 'draft', 'failed', 'cancelled', 'manual_review'].includes(q.publish_status) && (
                            <button
                              onClick={() => handleSelectClip(q.id)}
                              data-testid={`btn-edit-metadata-${q.id}`}
                              title="Edit clip metadata in editor"
                              style={{
                                background: 'rgba(255, 255, 255, 0.06)',
                                border: '1px solid rgba(255, 255, 255, 0.15)',
                                color: 'var(--text-secondary)',
                                borderRadius: 6,
                                padding: '4px 10px',
                                fontSize: 11,
                                fontWeight: 600,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 4,
                                transition: 'all 0.15s ease'
                              }}
                            >
                              ✏️ Edit
                            </button>
                          )}
                        </div>

                        {q.youtube_short_id && (
                          <a 
                            href={q.youtube_url || `https://youtube.com/shorts/${q.youtube_short_id}`} 
                            target="_blank" 
                            rel="noopener noreferrer" 
                            data-testid={`link-youtube-${q.id}`}
                            style={{ 
                              color: 'var(--accent)', 
                              textDecoration: 'none', 
                              fontSize: 11, 
                              fontWeight: 600,
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: 4
                            }}
                          >
                            🔗 View Short
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

        </div>

      </div>
    </div>
  );
}

export default function PublishPage() {
  return (
    <Suspense fallback={<div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>Loading YouTube integration options...</div>}>
      <PublishPageContent />
    </Suspense>
  );
}
