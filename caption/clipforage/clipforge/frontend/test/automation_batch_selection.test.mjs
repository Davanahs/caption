import test from 'node:test';
import assert from 'node:assert/strict';

// Helper simulating reconcileBatchOutcomes from AutomationPage
function reconcileBatchOutcomes(submittedVids, res) {
  const succeededIds = new Set();
  const returnedMap = new Map();
  if (Array.isArray(res?.items)) {
    res.items.forEach(item => {
      if (item.video_id) returnedMap.set(item.video_id, item);
    });
  }

  let queuedCount = 0;
  let alreadyCount = 0;
  let rejectedCount = 0;
  let failedCount = 0;
  let unresolvedCount = 0;
  const details = [];

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
}

// Simulates Behavior A: Global Sticky Batch Action
async function executeGlobalBatch(selectedVideos, channels, mockApi) {
  const entries = Object.values(selectedVideos);
  if (entries.length === 0) {
    return { error: 'Empty selection', dispatchedRequests: [], remainingSelection: selectedVideos };
  }

  const byChannel = {};
  const unassigned = [];

  entries.forEach(v => {
    if (!v.channelId) {
      unassigned.push(v);
    } else {
      if (!byChannel[v.channelId]) byChannel[v.channelId] = [];
      byChannel[v.channelId].push(v);
    }
  });

  if (unassigned.length > 0) {
    return {
      error: `Cannot process ${unassigned.length} video(s): Missing channel association.`,
      dispatchedRequests: [],
      remainingSelection: selectedVideos
    };
  }

  const allSucceededIds = new Set();
  const dispatchedRequests = [];
  const channelReports = [];

  for (const [chId, vids] of Object.entries(byChannel)) {
    const chObj = channels.find(c => c.id === chId);
    const chName = chObj?.channel_name || chId;
    const payload = vids.map(v => ({
      video_id: v.id,
      video_url: v.url,
      video_title: v.title,
    }));
    dispatchedRequests.push({ channelId: chId, payload });

    try {
      const res = await mockApi(chId, payload);
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
    } catch (err) {
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

  // Reconcile remaining selection state
  const remainingSelection = { ...selectedVideos };
  allSucceededIds.forEach(id => delete remainingSelection[id]);

  const totalQueued = channelReports.reduce((acc, r) => acc + r.queued, 0);
  const totalAlready = channelReports.reduce((acc, r) => acc + r.already, 0);
  const hasIssues = channelReports.some(r => r.rejected > 0 || r.failed > 0 || r.unresolved > 0 || r.error);

  let feedback;
  if (hasIssues) {
    const issueSummaries = channelReports
      .filter(r => r.rejected > 0 || r.failed > 0 || r.unresolved > 0 || r.error)
      .map(r => r.error ? `${r.channelName}: ${r.error} (outcome uncertain)` : `${r.channelName}: ${r.details.join(', ')}`);
    feedback = {
      isPartial: true,
      message: `Partial batch result: ${totalQueued} queued, ${totalAlready} already processing. Issues: [${issueSummaries.join('; ')}]. ${Object.keys(remainingSelection).length} video(s) remain selected for review/retry.`
    };
  } else {
    feedback = {
      isPartial: false,
      message: `Successfully queued ${totalQueued} video(s) across ${Object.keys(byChannel).length} channel(s)!`
    };
  }

  return { dispatchedRequests, channelReports, remainingSelection, feedback };
}

// Simulates Behavior B: Explicit Channel-Scoped Batch Action
async function executeChannelBatch(selectedVideos, channelId, channels, mockApi) {
  const vids = Object.values(selectedVideos).filter(v => v.channelId === channelId);
  if (vids.length === 0) {
    return { error: 'No videos for channel', dispatchedRequests: [], remainingSelection: selectedVideos };
  }

  const payload = vids.map(v => ({
    video_id: v.id,
    video_url: v.url,
    video_title: v.title,
  }));
  const dispatchedRequests = [{ channelId, payload }];

  const res = await mockApi(channelId, payload);
  const reconciliation = reconcileBatchOutcomes(vids, res);

  const remainingSelection = { ...selectedVideos };
  reconciliation.succeededIds.forEach(id => delete remainingSelection[id]);

  return { dispatchedRequests, reconciliation, remainingSelection };
}

// ── TESTS ───────────────────────────────────────────────────────────────────

test('Case 1: Multi-Channel Grouping - 2 from Ch A, 1 from Ch B yields exactly 2 requests', async () => {
  const selected = {
    'vid_a1': { id: 'vid_a1', url: 'https://youtu.be/a1', title: 'Video A1', channelId: 'ch_A' },
    'vid_a2': { id: 'vid_a2', url: 'https://youtu.be/a2', title: 'Video A2', channelId: 'ch_A' },
    'vid_b1': { id: 'vid_b1', url: 'https://youtu.be/b1', title: 'Video B1', channelId: 'ch_B' },
  };
  const channels = [
    { id: 'ch_A', channel_name: 'Channel Alpha' },
    { id: 'ch_B', channel_name: 'Channel Beta' },
  ];

  const mockApi = async (chId, payload) => ({
    total_requested: payload.length,
    queued_count: payload.length,
    already_processing_count: 0,
    rejected_count: 0,
    items: payload.map(p => ({ video_id: p.video_id, status: 'queued', job_id: `job_${p.video_id}` }))
  });

  const res = await executeGlobalBatch(selected, channels, mockApi);
  assert.equal(res.dispatchedRequests.length, 2, 'Must produce exactly 2 requests');
  assert.equal(res.dispatchedRequests[0].channelId, 'ch_A');
  assert.equal(res.dispatchedRequests[0].payload.length, 2);
  assert.equal(res.dispatchedRequests[1].channelId, 'ch_B');
  assert.equal(res.dispatchedRequests[1].payload.length, 1);
  assert.equal(Object.keys(res.remainingSelection).length, 0, 'All succeeded items dequeued');
});

test('Case 2: Channel Identity Matching - Each request contains only videos matching its channel ID', async () => {
  const selected = {
    'vid_a1': { id: 'vid_a1', url: 'https://youtu.be/a1', title: 'Video A1', channelId: 'ch_A' },
    'vid_b1': { id: 'vid_b1', url: 'https://youtu.be/b1', title: 'Video B1', channelId: 'ch_B' },
  };
  const channels = [{ id: 'ch_A' }, { id: 'ch_B' }];

  const mockApi = async (chId, payload) => ({
    items: payload.map(p => ({ video_id: p.video_id, status: 'queued' }))
  });

  const res = await executeGlobalBatch(selected, channels, mockApi);
  for (const req of res.dispatchedRequests) {
    for (const item of req.payload) {
      assert.equal(selected[item.video_id].channelId, req.channelId, 'Video channelId must match request target channel');
    }
  }
});

test('Case 3: Explicit Channel Action - Processing Ch A does not misroute or clear Ch B selections', async () => {
  const selected = {
    'vid_a1': { id: 'vid_a1', url: 'https://youtu.be/a1', title: 'Video A1', channelId: 'ch_A' },
    'vid_b1': { id: 'vid_b1', url: 'https://youtu.be/b1', title: 'Video B1', channelId: 'ch_B' },
  };
  const channels = [{ id: 'ch_A' }, { id: 'ch_B' }];

  const mockApi = async (chId, payload) => ({
    items: payload.map(p => ({ video_id: p.video_id, status: 'queued' }))
  });

  const res = await executeChannelBatch(selected, 'ch_A', channels, mockApi);
  assert.equal(res.dispatchedRequests.length, 1);
  assert.equal(res.dispatchedRequests[0].channelId, 'ch_A');
  assert.equal(res.dispatchedRequests[0].payload.length, 1);
  assert.equal(res.dispatchedRequests[0].payload[0].video_id, 'vid_a1');
  assert.ok(!res.remainingSelection['vid_a1'], 'Ch A video removed from selection');
  assert.ok(res.remainingSelection['vid_b1'], 'Ch B video remains safely in selection');
});

test('Case 4: Partial Failure Simulation - Ch A succeeds, Ch B fails with network error', async () => {
  const selected = {
    'vid_a1': { id: 'vid_a1', url: 'https://youtu.be/a1', title: 'Video A1', channelId: 'ch_A' },
    'vid_b1': { id: 'vid_b1', url: 'https://youtu.be/b1', title: 'Video B1', channelId: 'ch_B' },
  };
  const channels = [
    { id: 'ch_A', channel_name: 'Channel Alpha' },
    { id: 'ch_B', channel_name: 'Channel Beta' },
  ];

  const mockApi = async (chId, payload) => {
    if (chId === 'ch_B') throw new Error('ECONNRESET: Connection dropped by server');
    return { items: [{ video_id: 'vid_a1', status: 'queued' }] };
  };

  const res = await executeGlobalBatch(selected, channels, mockApi);
  assert.ok(!res.remainingSelection['vid_a1'], 'Ch A video was queued and removed from selection');
  assert.ok(res.remainingSelection['vid_b1'], 'Ch B video failed and remains selected for retry');
  assert.equal(Object.keys(res.remainingSelection).length, 1);
  assert.equal(res.feedback.isPartial, true);
  assert.match(res.feedback.message, /Channel Beta: ECONNRESET/);
  assert.match(res.feedback.message, /1 video\(s\) remain selected for review\/retry/);
});

test('Case 5: Item-Level Rejection - 1 queued, 1 rejected leaves rejected video selected', async () => {
  const selected = {
    'vid_a1': { id: 'vid_a1', url: 'https://youtu.be/a1', title: 'Valid Video', channelId: 'ch_A' },
    'vid_a2': { id: 'vid_a2', url: '', title: 'Invalid Video', channelId: 'ch_A' },
  };
  const channels = [{ id: 'ch_A', channel_name: 'Channel Alpha' }];

  const mockApi = async (chId, payload) => ({
    queued_count: 1,
    rejected_count: 1,
    items: [
      { video_id: 'vid_a1', status: 'queued', job_id: 'job_01' },
      { video_id: 'vid_a2', status: 'rejected', error: 'Missing video_url' }
    ]
  });

  const res = await executeGlobalBatch(selected, channels, mockApi);
  assert.ok(!res.remainingSelection['vid_a1'], 'Valid queued video removed');
  assert.ok(res.remainingSelection['vid_a2'], 'Rejected video remains selected');
  assert.equal(res.feedback.isPartial, true);
  assert.match(res.feedback.message, /Missing video_url/);
});

test('Case 6: Deselection Integrity - Deselected item is absent from outgoing payload', async () => {
  const selected = {
    'vid_a1': { id: 'vid_a1', url: 'https://youtu.be/a1', title: 'Video A1', channelId: 'ch_A' },
    'vid_a2': { id: 'vid_a2', url: 'https://youtu.be/a2', title: 'Video A2', channelId: 'ch_A' },
  };
  delete selected['vid_a2']; // User unchecked vid_a2

  const channels = [{ id: 'ch_A' }];
  const mockApi = async (chId, payload) => ({
    items: payload.map(p => ({ video_id: p.video_id, status: 'queued' }))
  });

  const res = await executeGlobalBatch(selected, channels, mockApi);
  assert.equal(res.dispatchedRequests[0].payload.length, 1);
  assert.equal(res.dispatchedRequests[0].payload[0].video_id, 'vid_a1');
});

test('Case 7: Empty Selection Protection - Empty selection returns early without dispatching', async () => {
  const selected = {};
  const channels = [{ id: 'ch_A' }];
  let apiCalled = false;
  const mockApi = async () => { apiCalled = true; };

  const res = await executeGlobalBatch(selected, channels, mockApi);
  assert.equal(apiCalled, false, 'API must not be invoked on empty selection');
  assert.equal(res.dispatchedRequests.length, 0);
  assert.equal(res.error, 'Empty selection');
});

test('Case 8: Idempotent already_processing status is safely removed from selection', async () => {
  const selected = {
    'vid_a1': { id: 'vid_a1', url: 'https://youtu.be/a1', title: 'Video A1', channelId: 'ch_A' },
  };
  const channels = [{ id: 'ch_A', channel_name: 'Channel Alpha' }];

  const mockApi = async (chId, payload) => ({
    queued_count: 0,
    already_processing_count: 1,
    items: [{ video_id: 'vid_a1', status: 'already_processing', job_id: 'job_existing' }]
  });

  const res = await executeGlobalBatch(selected, channels, mockApi);
  assert.equal(Object.keys(res.remainingSelection).length, 0, 'already_processing is confirmed handled and removed');
  assert.equal(res.feedback.isPartial, false);
});
