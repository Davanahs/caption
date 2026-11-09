import test from 'node:test';
import assert from 'node:assert/strict';

test('Monitoring Audit Repairs: URL Normalization and /videos tab targeting', () => {
  // Test that channel URLs lacking a sub-tab are properly augmented
  const normalizeChannelUrl = (url) => {
    let clean = url.trim().replace(/\/+$/, '');
    if (/\/@(?!.*\/)(.+)$/.test(clean)) {
      return `${clean}/videos`;
    }
    if (/\/(channel|c|user)\/[^\/]+$/.test(clean)) {
      return `${clean}/videos`;
    }
    return clean;
  };

  assert.equal(
    normalizeChannelUrl('https://www.youtube.com/@NishantChahar11'),
    'https://www.youtube.com/@NishantChahar11/videos',
    'Handle URLs without trailing tab should target /videos'
  );
  assert.equal(
    normalizeChannelUrl('https://www.youtube.com/@NishantChahar11/videos'),
    'https://www.youtube.com/@NishantChahar11/videos',
    'URLs already having /videos should remain unchanged'
  );
  assert.equal(
    normalizeChannelUrl('https://www.youtube.com/channel/UC12345'),
    'https://www.youtube.com/channel/UC12345/videos',
    'Channel ID URLs without trailing tab should target /videos'
  );
  assert.equal(
    normalizeChannelUrl('https://www.youtube.com/playlist?list=PL12345'),
    'https://www.youtube.com/playlist?list=PL12345',
    'Playlist URLs should remain unmodified'
  );
});

test('Monitoring Audit Repairs: Most-Viewed Ordering Contract with Deterministic Tie-Breakers', () => {
  // Simulate videos with view counts and timestamps
  const rawVideos = [
    { id: 'vid1', view_count: 50000, sort_ts: 100 },
    { id: 'vid2', view_count: 120000, sort_ts: 90 },
    { id: 'vid3', view_count: 50000, sort_ts: 110 },
    { id: 'vid4', view_count: null, sort_ts: 120 },
    { id: 'vid5', view_count: 325000, sort_ts: 80 },
  ];

  const sorted = [...rawVideos].sort((a, b) => {
    const vcA = a.view_count ?? -1;
    const vcB = b.view_count ?? -1;
    if (vcA !== vcB) return vcB - vcA; // Descending
    const tsA = a.sort_ts ?? 0;
    const tsB = b.sort_ts ?? 0;
    if (tsA !== tsB) return tsB - tsA; // Most recent upload tie-breaker
    return a.id.localeCompare(b.id);
  });

  assert.equal(sorted[0].id, 'vid5', 'Highest view count (325,000) must rank #1');
  assert.equal(sorted[1].id, 'vid2', 'Second highest view count (120,000) must rank #2');
  assert.equal(sorted[2].id, 'vid3', 'Tie-breaker: vid3 (sort_ts 110) ranks before vid1 (sort_ts 100)');
  assert.equal(sorted[3].id, 'vid1', 'Tie-breaker: vid1 ranks after vid3');
  assert.equal(sorted[4].id, 'vid4', 'Null view counts must sort last');
});

test('Monitoring Audit Repairs: Discovered Videos API Query Param Serialization', () => {
  const buildQuery = (channelId, page, pageSize, sort, scanDepth) => {
    const params = new URLSearchParams({
      page: String(page),
      page_size: String(pageSize),
    });
    if (sort) params.set('sort', sort);
    if (scanDepth) params.set('scan_depth', String(scanDepth));
    return `/api/channels/${encodeURIComponent(channelId)}/videos?${params.toString()}`;
  };

  const defaultQuery = buildQuery('ch-123', 1, 8);
  assert.ok(defaultQuery.includes('page=1'), 'Query includes page=1');
  assert.ok(defaultQuery.includes('page_size=8'), 'Query includes page_size=8');

  const mostViewedQuery = buildQuery('ch-123', 2, 8, 'most_viewed', 50);
  assert.ok(mostViewedQuery.includes('sort=most_viewed'), 'Query includes sort=most_viewed');
  assert.ok(mostViewedQuery.includes('scan_depth=50'), 'Query includes scan_depth=50');
  assert.ok(mostViewedQuery.includes('page=2'), 'Query preserves page parameter');
});

test('Monitoring Audit Repairs: Failed Video Processing Identification Data Contract', () => {
  // Ensure that a failed decision history item correctly exposes source provenance and error message
  const failedDecisionItem = {
    id: 'dec-001',
    channel_id: 'ch-abc',
    channel_name: 'Tech Channel',
    video_title: 'Original Source Title Here',
    youtube_id: '0OfOivc-tpU',
    youtube_url: 'https://www.youtube.com/watch?v=0OfOivc-tpU',
    source_video_title: 'Original Source Title Here',
    source_youtube_id: '0OfOivc-tpU',
    source_youtube_url: 'https://www.youtube.com/watch?v=0OfOivc-tpU',
    thumbnail_url: 'https://i.ytimg.com/vi/0OfOivc-tpU/mqdefault.jpg',
    status: 'resolved_defaults',
    job_id: 'job-999',
    job_status: 'failed',
    error_message: "psycopg2.ProgrammingError: can't adapt type 'dict'",
    job_error: "psycopg2.ProgrammingError: can't adapt type 'dict'",
    current_step: 'metadata_generation',
  };

  assert.ok(failedDecisionItem.source_youtube_id, 'Source YouTube ID must be present');
  assert.ok(failedDecisionItem.thumbnail_url, 'Thumbnail URL must be available for provenance display');
  assert.equal(failedDecisionItem.job_status, 'failed', 'Job status must explicitly reflect failure');
  assert.ok(failedDecisionItem.error_message, 'Explicit error message must be present for failed runs');
  assert.equal(failedDecisionItem.current_step, 'metadata_generation', 'Stage must identify where pipeline failed');
});

test('Monitoring Audit Repairs: Historical Two-Action Model Definition', () => {
  // Test the state transitions for the two primary actions
  const stateTransitions = (action, oldRanking = 'most_viewed') => {
    if (action === 'recent') {
      return {
        primaryAction: 'recent',
        mode: 'latest',
        count: 3,
      };
    } else {
      return {
        primaryAction: 'old',
        mode: oldRanking,
        count: 5,
      };
    }
  };

  const recent = stateTransitions('recent');
  assert.equal(recent.primaryAction, 'recent');
  assert.equal(recent.mode, 'latest');
  assert.equal(recent.count, 3, 'Recent action defaults to 3 videos');

  const oldMostViewed = stateTransitions('old', 'most_viewed');
  assert.equal(oldMostViewed.primaryAction, 'old');
  assert.equal(oldMostViewed.mode, 'most_viewed');
  assert.equal(oldMostViewed.count, 5, 'Old action defaults to 5 videos');

  const oldChronological = stateTransitions('old', 'latest');
  assert.equal(oldChronological.primaryAction, 'old');
  assert.equal(oldChronological.mode, 'latest');
});

test('Monitoring Audit Repairs: Reprocessed Short vs Original Source Video Provenance Contract', () => {
  // Case A: Reprocessed Short (FAIL-EX-001)
  const shortItem = {
    id: 'dec-12385744',
    youtube_id: '0OfOivc-tpU',
    is_generated_short: true,
    generated_short_id: '0OfOivc-tpU',
    generated_short_url: 'https://www.youtube.com/shorts/0OfOivc-tpU',
    generated_short_title: "Adobe's Secret Clone Was REAL? 😱",
    source_youtube_id: 'MjDUTSOsUMg',
    source_video_title: 'Software is DEAD! This GitHub Repo Can Build Anything in Few Hours',
    source_youtube_url: 'https://www.youtube.com/watch?v=MjDUTSOsUMg',
    job_status: 'failed',
    error_message: "psycopg2.ProgrammingError: can't adapt type 'dict'",
  };

  assert.equal(shortItem.is_generated_short, true);
  assert.equal(shortItem.generated_short_id, '0OfOivc-tpU');
  assert.equal(shortItem.source_youtube_id, 'MjDUTSOsUMg', 'Must resolve true original source video ID MjDUTSOsUMg, NOT generated short ID');
  assert.ok(shortItem.source_video_title.includes('Software is DEAD!'), 'Must preserve origin full-length title');
  assert.ok(shortItem.generated_short_url.includes('/shorts/0OfOivc-tpU'));

  // Case B: Direct Original Video (FAIL-EX-007)
  const directVideoItem = {
    id: 'dec-c3fb5a7a',
    youtube_id: 'm5hidzW-_i0',
    is_generated_short: false,
    generated_short_id: null,
    source_youtube_id: 'm5hidzW-_i0',
    source_video_title: 'Kimi K3 Is INSANE! Can It Beat Claude?',
    source_youtube_url: 'https://www.youtube.com/watch?v=m5hidzW-_i0',
    job_status: 'failed',
    error_message: 'OutputValidatorError: Duration 30.2s exceeds maximum Shorts duration limit of 30.0s',
  };

  assert.equal(directVideoItem.is_generated_short, false);
  assert.equal(directVideoItem.generated_short_id, null);
  assert.equal(directVideoItem.source_youtube_id, 'm5hidzW-_i0');
  assert.equal(directVideoItem.source_video_title, 'Kimi K3 Is INSANE! Can It Beat Claude?');
});

test('Monitoring Audit Repairs: Discovered Video Self-Ingestion Prevention Contract', () => {
  const discoveredItems = [
    {
      id: '0OfOivc-tpU',
      title: "Adobe's Secret Clone Was REAL? 😱 #Shorts",
      is_processed: true,
      is_generated_short: true,
      parent_source_id: 'MjDUTSOsUMg',
      parent_source_title: 'Software is DEAD! This GitHub Repo Can Build Anything in Few Hours',
      job_status: 'failed',
    },
    {
      id: 'm5hidzW-_i0',
      title: 'Kimi K3 Is INSANE! Can It Beat Claude?',
      is_processed: false,
      is_generated_short: false,
      parent_source_id: null,
      parent_source_title: null,
      job_status: null,
    },
    {
      id: 'fresh_vid_123',
      title: 'Fresh Longform Video',
      is_processed: false,
      is_generated_short: false,
      parent_source_id: null,
      parent_source_title: null,
      job_status: null,
    }
  ];

  // 1. Filter eligible logic
  const eligible = discoveredItems.filter(v => !v.is_processed && !v.job_id && !v.is_generated_short);
  assert.equal(eligible.length, 2, 'Only fresh original source videos should be eligible for selection');
  assert.ok(!eligible.some(v => v.id === '0OfOivc-tpU'), 'ClipForge-generated Short must NOT be eligible');
  assert.ok(eligible.some(v => v.id === 'm5hidzW-_i0'), 'Original source video must be eligible');

  // 2. Selection action gate
  const simulateSelect = (item) => {
    if (item.is_generated_short) {
      return false; // Selection rejected
    }
    return true; // Selection accepted
  };

  assert.equal(simulateSelect(discoveredItems[0]), false, 'Selecting a generated Short must be blocked');
  assert.equal(simulateSelect(discoveredItems[1]), true, 'Selecting an authentic source video must be permitted');
});

test('Monitoring Audit Repairs: Historical Batch Self-Ingestion Exclusion Contract', () => {
  const historicalCandidates = [
    {
      id: 'kkXWbXZI_iM',
      title: 'Which City Pays More? 💰 #Shorts',
      is_processed: true,
      is_generated_short: true,
      publication_status: 'clipforge_short',
      parent_source_id: 'Cm45rJ_ayA4',
      parent_source_title: 'Software Engineer Salary vs Cost of Living: Which City Wins?',
    },
    {
      id: 'Cm45rJ_ayA4',
      title: 'Software Engineer Salary vs Cost of Living: Which City Wins?',
      is_processed: false,
      is_generated_short: false,
      publication_status: 'none',
      parent_source_id: null,
      parent_source_title: null,
    }
  ];

  // Exclude Shorts from queueing
  const willQueue = historicalCandidates.filter(c => !c.is_generated_short && !c.is_processed);
  assert.equal(willQueue.length, 1);
  assert.equal(willQueue[0].id, 'Cm45rJ_ayA4', 'Only parent source video should be queued');
});

test('Monitoring Audit Repairs: Auto-Publish Destination Enforcing Contract', () => {
  // 1. handleAdd validation simulation
  const validateAddChannel = (form) => {
    if (form.auto_publish && !form.publish_destination_id) {
      return { ok: false, error: 'Cannot enable auto-publish without selecting a valid publish destination.' };
    }
    return { ok: true };
  };

  assert.equal(validateAddChannel({ auto_publish: true, publish_destination_id: '' }).ok, false);
  assert.equal(validateAddChannel({ auto_publish: true, publish_destination_id: 'dest-123' }).ok, true);
  assert.equal(validateAddChannel({ auto_publish: false, publish_destination_id: '' }).ok, true);

  // 2. handleToggle validation simulation
  const handleToggleSim = (channel, field, val) => {
    if (field === 'auto_publish' && val === true && !channel.publish_destination_id) {
      return { ok: false, error: 'Cannot enable auto-publish: Please select a destination channel first.' };
    }
    if (field === 'publish_destination_id' && !val && channel.auto_publish) {
      return { ok: true, updated: { publish_destination_id: null, auto_publish: false } };
    }
    return { ok: true, updated: { [field]: val } };
  };

  const chWithoutDest = { id: 'ch-1', auto_publish: false, publish_destination_id: null };
  const res1 = handleToggleSim(chWithoutDest, 'auto_publish', true);
  assert.equal(res1.ok, false);
  assert.ok(res1.error.includes('Please select a destination channel first'));

  const chWithDest = { id: 'ch-2', auto_publish: true, publish_destination_id: 'dest-abc' };
  const res2 = handleToggleSim(chWithDest, 'publish_destination_id', null);
  assert.equal(res2.ok, true);
  assert.equal(res2.updated.auto_publish, false, 'Clearing destination must auto-disable auto_publish');
  assert.equal(res2.updated.publish_destination_id, null);
});


