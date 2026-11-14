self.CaptionSocket = (() => {
  const JOB_STORAGE_KEY = "captionPreparationJob";
  const activeSockets = new Map();

  function connectToJob(job) {
    if (activeSockets.has(job.jobId)) return;
    const socketUrl = new URL(
      `/api/videos/captions/jobs/${job.jobId}/ws`,
      job.apiUrl
    );
    socketUrl.protocol = socketUrl.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(socketUrl.toString());
    activeSockets.set(job.jobId, socket);
    socket.onmessage = (event) => handleSocketMessage(job, socket, event.data);
    socket.onclose = () => handleSocketClose(job, socket);
    socket.onerror = () => socket.close();
  }

  function handleSocketMessage(job, socket, data) {
    let message;
    try {
      message = JSON.parse(data);
    } catch (_error) {
      return;
    }
    if (message.type === "heartbeat") return;
    if (message.type === "snapshot" || message.type === "partial") {
      notifyTab(job.tabId, "captions:partial", {
        message: message.job.message,
        cues: message.job.cues,
        blocksDone: message.job.blocks_done
      });
      return;
    }
    if (message.type === "failed") {
      if (message.message === "Задача подготовки не найдена") {
        activeSockets.delete(job.jobId);
        socket.close(1000);
        resumePreparation(job);
      } else {
        finishJob(job, socket, "captions:failed", { message: message.message });
      }
      return;
    }
    if (message.type !== "update") return;
    const state = message.job;
    if (state.status === "complete") {
      finishJob(job, socket, "captions:prepared", {
        cues: state.cues,
        assetKey: state.asset_key,
        cached: false
      });
    } else if (state.status === "failed") {
      finishJob(job, socket, "captions:failed", { message: state.message });
    } else {
      notifyState(job.tabId, state);
    }
  }

  function handleSocketClose(job, socket) {
    if (activeSockets.get(job.jobId) !== socket) return;
    activeSockets.delete(job.jobId);
    reconnectJob(job);
  }

  async function finishJob(job, socket, type, values) {
    activeSockets.delete(job.jobId);
    socket.close(1000);
    await chrome.storage.local.remove(JOB_STORAGE_KEY);
    await chrome.alarms.clear("caption-websocket-reconnect");
    notifyTab(job.tabId, type, values);
  }

  async function reconnectJob(job) {
    const stored = await chrome.storage.local.get(JOB_STORAGE_KEY);
    if (stored[JOB_STORAGE_KEY]?.jobId !== job.jobId) return;
    try {
      const response = await fetch(`${job.apiUrl}/api/videos/captions/jobs/${job.jobId}`);
      if (!response.ok) {
        await resumePreparation(job);
        return;
      }
      const state = await response.json();
      if (state.status === "complete" || state.status === "failed") {
        const type = state.status === "complete" ? "captions:prepared" : "captions:failed";
        const values = state.status === "complete"
          ? { cues: state.cues, assetKey: state.asset_key, cached: false }
          : { message: state.message };
        await finishJob(job, { close: () => {} }, type, values);
        return;
      }
      notifyState(job.tabId, state);
      setTimeout(() => connectToJob(job), 2000);
    } catch (_error) {
      setTimeout(() => reconnectJob(job), 5000);
    }
  }

  async function resumePreparation(job) {
    try {
      const response = await fetch(`${job.apiUrl}/api/videos/captions/prepare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_url: job.videoUrl, mode: job.mode })
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || "Не удалось восстановить задачу");
      if (result.status === "complete") {
        await finishJob(job, { close: () => {} }, "captions:prepared", {
          cues: result.cues,
          assetKey: result.asset_key,
          cached: true
        });
        return;
      }
      const resumedJob = { ...job, jobId: result.job_id };
      await chrome.storage.local.set({ [JOB_STORAGE_KEY]: resumedJob });
      connectToJob(resumedJob);
    } catch (_error) {
      setTimeout(() => resumePreparation(job), 5000);
    }
  }

  function notifyTab(tabId, type, values) {
    chrome.tabs.sendMessage(tabId, { type, tabId, ...values }).catch(() => {});
  }

  function notifyState(tabId, state) {
    if (Array.isArray(state.cues) && state.cues.length) {
      notifyTab(tabId, "captions:partial", {
        message: state.message,
        cues: state.cues,
        blocksDone: state.blocks_done
      });
      return;
    }
    notifyTab(tabId, "captions:status", {
      message: state.message,
      progress: state.progress
    });
  }

  return { connectToJob, notifyTab };
})();
