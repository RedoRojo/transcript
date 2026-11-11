// --- Minimalist Transcript Web Application (YouTube & Local Media) ---

(function() {
  "use strict";

  // App State
  let currentData = null;
  let activeTab = "segments"; // "segments" | "continuous"
  let activeSource = "youtube"; // "youtube" | "local"
  let searchQuery = "";
  let selectedLocalFile = null;
  let activePlayingSegIndex = null;

  const STORAGE_KEY_SCHEME = "color-scheme";
  const LEGACY_KEY_THEME = "yt_transcript_theme";
  const STORAGE_KEY_HISTORY = "transcript_tool_history";

  const DEFAULT_THUMB_SVG =
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='70' viewBox='0 0 120 70' fill='%231e293b'><rect width='120' height='70' rx='8'/><circle cx='60' cy='35' r='18' fill='%23334155'/><polygon points='56,26 68,35 56,44' fill='%23f8fafc'/></svg>";
  const HISTORY_THUMB_SVG =
    "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='48' height='36' viewBox='0 0 48 36' fill='%231e293b'><rect width='48' height='36' rx='4'/></svg>";

  // DOM Elements - Navigation & Global
  const colorSchemeMeta = document.querySelector('meta[name="color-scheme"]');
  const btnThemeToggle = document.getElementById("btnThemeToggle");
  const btnHistory = document.getElementById("btnHistory");
  const historyCountBadge = document.getElementById("historyCount");
  const statusAlert = document.getElementById("statusAlert");
  const alertMessage = document.getElementById("alertMessage");
  const btnCloseAlert = document.getElementById("btnCloseAlert");
  const loadingState = document.getElementById("loadingState");
  const loadingMessage = document.getElementById("loadingMessage");
  const resultSection = document.getElementById("resultSection");

  // Source Selector
  const sourceTablist = document.getElementById("sourceTablist");
  const tabSourceYoutube = document.getElementById("tabSourceYoutube");
  const tabSourceLocal = document.getElementById("tabSourceLocal");
  const youtubePanel = document.getElementById("youtubePanel");
  const localPanel = document.getElementById("localPanel");

  // YouTube Inputs
  const youtubeForm = document.getElementById("transcribeForm");
  const inputUrl = document.getElementById("videoUrlInput");
  const btnPaste = document.getElementById("btnPaste");
  const btnSubmitYoutube = document.getElementById("btnSubmit");

  // Local Media Inputs
  const dropZone = document.getElementById("dropZone");
  const btnChooseLocalFile = document.getElementById("btnChooseLocalFile");
  const localFileInput = document.getElementById("localFileInput");
  const fileSelectedBadge = document.getElementById("fileSelectedBadge");
  const fileBadgeName = document.getElementById("fileBadgeName");
  const btnRemoveFile = document.getElementById("btnRemoveFile");
  const btnTogglePath = document.getElementById("btnTogglePath");
  const pathInputWrapper = document.getElementById("pathInputWrapper");
  const localFilePathInput = document.getElementById("localFilePathInput");
  const localModelSelect = document.getElementById("localModelSelect");
  const localLangSelect = document.getElementById("localLangSelect");
  const btnSubmitLocal = document.getElementById("btnSubmitLocal");

  // Local Player
  const localPlayerCard = document.getElementById("localPlayerCard");
  const playerBody = document.getElementById("playerBody");
  const localVideoPlayer = document.getElementById("localVideoPlayer");
  const localAudioPlayer = document.getElementById("localAudioPlayer");

  // Metadata Card Elements
  const metaThumb = document.getElementById("metaThumb");
  const metaVideoLink = document.getElementById("metaVideoLink");
  const metaTitle = document.getElementById("metaTitle");
  const metaAuthor = document.getElementById("metaAuthor");
  const metaSourceBadge = document.getElementById("metaSourceBadge");
  const metaDurationBadge = document.getElementById("metaDurationBadge");
  const metaWordsBadge = document.getElementById("metaWordsBadge");
  const metaSegmentsBadge = document.getElementById("metaSegmentsBadge");
  const langSelect = document.getElementById("langSelect");

  // Toolbar Elements
  const viewTablist = document.getElementById("viewTablist");
  const tabSegments = document.getElementById("tabSegments");
  const tabContinuous = document.getElementById("tabContinuous");
  const searchInput = document.getElementById("transcriptSearchInput");
  const matchesCountBadge = document.getElementById("searchMatchesCount");
  const btnCopyPlain = document.getElementById("btnCopyPlain");
  const btnCopyTimestamps = document.getElementById("btnCopyTimestamps");
  const btnExportMenu = document.getElementById("btnExportMenu");
  const exportDropdown = document.getElementById("exportDropdown");
  const exportMenuItems = Array.from(exportDropdown.querySelectorAll('[role="menuitem"]'));

  // Content Views
  const segmentsView = document.getElementById("segmentsView");
  const continuousView = document.getElementById("continuousView");

  // Native History Dialog Elements
  const historyDialog = document.getElementById("historyDialog");
  const btnCloseHistory = document.getElementById("btnCloseHistory");
  const btnClearHistory = document.getElementById("btnClearHistory");
  const historyList = document.getElementById("historyList");

  // Toast
  const toastEl = document.getElementById("toast");
  let toastTimer = null;

  // --- Theme Management (via <meta name="color-scheme">) ---
  function getSystemScheme() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function applyColorSchemeMeta(value) {
    if (!colorSchemeMeta) return;
    colorSchemeMeta.content = value === "light" || value === "dark" ? value : "light dark";
  }

  function initTheme() {
    try {
      let saved = localStorage.getItem(STORAGE_KEY_SCHEME);
      if (!saved) {
        const legacy = localStorage.getItem(LEGACY_KEY_THEME);
        if (legacy === "light" || legacy === "dark") {
          saved = legacy;
          localStorage.setItem(STORAGE_KEY_SCHEME, legacy);
          localStorage.removeItem(LEGACY_KEY_THEME);
        }
      }
      applyColorSchemeMeta(saved);
    } catch {
      applyColorSchemeMeta("light dark");
    }

    window.addEventListener("storage", (e) => {
      if (e.key === STORAGE_KEY_SCHEME) {
        applyColorSchemeMeta(e.newValue);
      }
    });
  }

  function toggleTheme() {
    let stored = null;
    try {
      stored = localStorage.getItem(STORAGE_KEY_SCHEME);
    } catch {
      stored = null;
    }

    const systemPref = getSystemScheme();
    const currentRendered = stored === "light" || stored === "dark" ? stored : systemPref;
    const targetScheme = currentRendered === "dark" ? "light" : "dark";

    try {
      localStorage.removeItem(LEGACY_KEY_THEME);
      if (targetScheme === systemPref) {
        localStorage.removeItem(STORAGE_KEY_SCHEME);
        applyColorSchemeMeta("light dark");
      } else {
        localStorage.setItem(STORAGE_KEY_SCHEME, targetScheme);
        applyColorSchemeMeta(targetScheme);
      }
    } catch {
      applyColorSchemeMeta(targetScheme);
    }
  }

  // --- Toast Notification ---
  const supportsPopover = Object.hasOwn(HTMLElement.prototype, "popover");
  if (supportsPopover && toastEl) {
    toastEl.setAttribute("popover", "manual");
  }

  function showToast(message, duration = 2400) {
    if (toastTimer) clearTimeout(toastTimer);
    toastEl.textContent = message;
    toastEl.hidden = false;
    if (supportsPopover) {
      try {
        if (!toastEl.matches(":popover-open")) {
          toastEl.showPopover();
        }
      } catch {}
    }
    toastTimer = setTimeout(() => {
      if (supportsPopover) {
        try {
          if (toastEl.matches(":popover-open")) {
            toastEl.hidePopover();
          }
        } catch {}
      }
      toastEl.hidden = true;
    }, duration);
  }

  // --- Alert System ---
  function showAlert(msg) {
    alertMessage.textContent = msg;
    statusAlert.hidden = false;
  }

  function hideAlert() {
    statusAlert.hidden = true;
  }

  // --- Loading State ---
  function setLoading(isLoading, message = "Processing transcription...") {
    if (isLoading) {
      hideAlert();
      loadingMessage.textContent = message;
      loadingState.hidden = false;
      resultSection.hidden = true;
      btnSubmitYoutube.disabled = true;
      btnSubmitLocal.disabled = true;
    } else {
      loadingState.hidden = true;
      btnSubmitYoutube.disabled = false;
      btnSubmitLocal.disabled = false;
    }
  }

  // --- Accessible Roving Tabindex Setup ---
  function setupTablist(tablistEl, tabs, onSelect) {
    tablistEl.addEventListener("keydown", (e) => {
      const idx = tabs.indexOf(document.activeElement);
      if (idx === -1) return;

      let nextIdx = null;
      if (e.key === "ArrowRight") {
        nextIdx = (idx + 1) % tabs.length;
      } else if (e.key === "ArrowLeft") {
        nextIdx = (idx - 1 + tabs.length) % tabs.length;
      } else if (e.key === "Home") {
        nextIdx = 0;
      } else if (e.key === "End") {
        nextIdx = tabs.length - 1;
      }

      if (nextIdx !== null) {
        e.preventDefault();
        tabs[nextIdx].focus();
        onSelect(tabs[nextIdx]);
      }
    });
  }

  // --- Source Tabs Switching ---
  function switchSource(source) {
    activeSource = source;
    const isYoutube = source === "youtube";

    tabSourceYoutube.setAttribute("aria-selected", String(isYoutube));
    tabSourceYoutube.tabIndex = isYoutube ? 0 : -1;
    tabSourceLocal.setAttribute("aria-selected", String(!isYoutube));
    tabSourceLocal.tabIndex = !isYoutube ? 0 : -1;

    youtubePanel.hidden = !isYoutube;
    localPanel.hidden = isYoutube;
    hideAlert();
  }

  // --- Transcript View Tabs Switching ---
  function switchViewTab(mode) {
    activeTab = mode;
    const isSegments = mode === "segments";

    tabSegments.setAttribute("aria-selected", String(isSegments));
    tabSegments.tabIndex = isSegments ? 0 : -1;
    tabContinuous.setAttribute("aria-selected", String(!isSegments));
    tabContinuous.tabIndex = !isSegments ? 0 : -1;

    segmentsView.hidden = !isSegments;
    continuousView.hidden = isSegments;

    if (currentData) {
      applySearchHighlights(searchQuery.trim());
    }
  }

  // --- File Selection & Drag & Drop Handling ---
  function setLocalFile(file, clearPath = true) {
    selectedLocalFile = file;
    if (file) {
      fileBadgeName.textContent = `${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)`;
      fileSelectedBadge.hidden = false;
      if (clearPath) {
        localFilePathInput.value = "";
      }
    } else {
      selectedLocalFile = null;
      localFileInput.value = "";
      fileSelectedBadge.hidden = true;
    }
  }

  // --- Media Player Helpers ---
  function getActiveMediaElement() {
    if (!localVideoPlayer.hidden) return localVideoPlayer;
    if (!localAudioPlayer.hidden) return localAudioPlayer;
    return null;
  }

  function pauseAndResetPlayers(clearSources = false) {
    [localVideoPlayer, localAudioPlayer].forEach((el) => {
      try {
        el.pause();
      } catch {}
      if (clearSources) {
        el.removeAttribute("src");
        el.load();
        el.hidden = true;
      }
    });
    activePlayingSegIndex = null;
  }

  function updatePlayingSegment(currentTime) {
    if (!currentData || !Array.isArray(currentData.segments) || currentData.segments.length === 0) {
      return;
    }

    const segs = currentData.segments;
    let activeSeg = null;
    for (let i = 0; i < segs.length; i++) {
      const seg = segs[i];
      const nextStart = i + 1 < segs.length ? segs[i + 1].start : (seg.end || seg.start + 5) + 0.5;
      if (currentTime >= seg.start && currentTime < nextStart) {
        activeSeg = seg;
        break;
      }
    }

    const nextIdx = activeSeg ? String(activeSeg.index) : null;
    if (nextIdx === activePlayingSegIndex) return;

    const prevEl = segmentsView.querySelector(".segment-item.is-playing");
    if (prevEl) prevEl.classList.remove("is-playing");

    if (nextIdx !== null) {
      const targetEl = segmentsView.querySelector(`.segment-item[data-seg-index="${nextIdx}"]`);
      if (targetEl) targetEl.classList.add("is-playing");
    }
    activePlayingSegIndex = nextIdx;
  }

  // --- Highlight Helpers (CSS Custom Highlight API + safe DOM fallback) ---
  function supportsCustomHighlights() {
    return typeof CSS !== "undefined" && Boolean(CSS.highlights) && typeof Highlight !== "undefined";
  }

  function appendHighlightedDom(container, text, query) {
    if (!query) {
      container.textContent = text;
      return;
    }

    container.textContent = "";
    const lowerText = text.toLowerCase();
    const lowerQuery = query.toLowerCase();
    const frag = document.createDocumentFragment();
    let last = 0;
    let pos = lowerText.indexOf(lowerQuery);

    while (pos !== -1) {
      if (pos > last) {
        frag.append(text.slice(last, pos));
      }
      const mark = document.createElement("mark");
      mark.className = "search-highlight";
      mark.textContent = text.slice(pos, pos + lowerQuery.length);
      frag.append(mark);
      last = pos + lowerQuery.length;
      pos = lowerText.indexOf(lowerQuery, last);
    }

    if (last < text.length) {
      frag.append(text.slice(last));
    }
    container.append(frag);
  }

  function applySearchHighlights(query) {
    if (!supportsCustomHighlights()) return;

    CSS.highlights.clear();
    if (!query) return;

    const activeContainer = activeTab === "segments" ? segmentsView : continuousView;
    const textTargets = activeContainer.querySelectorAll(".segment-text, .continuous-paragraph");
    if (!textTargets.length) return;

    const lowerQuery = query.toLowerCase();
    const ranges = [];

    textTargets.forEach((target) => {
      const walker = document.createTreeWalker(target, NodeFilter.SHOW_TEXT);
      let node = walker.nextNode();
      while (node) {
        const value = node.textContent;
        const lowerValue = value.toLowerCase();
        let pos = lowerValue.indexOf(lowerQuery);
        while (pos !== -1) {
          const range = new Range();
          range.setStart(node, pos);
          range.setEnd(node, pos + lowerQuery.length);
          ranges.push(range);
          pos = lowerValue.indexOf(lowerQuery, pos + lowerQuery.length);
        }
        node = walker.nextNode();
      }
    });

    if (ranges.length > 0) {
      CSS.highlights.set("search-results", new Highlight(...ranges));
    }
  }

  // --- Clipboard Copy ---
  async function copyToClipboard(text, message = "Copied to clipboard") {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const textarea = document.createElement("textarea");
        textarea.value = text;
        textarea.style.position = "fixed";
        textarea.style.left = "-9999px";
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand("copy");
        document.body.removeChild(textarea);
      }
      showToast(message);
    } catch (err) {
      console.error("Copy failed:", err);
      showToast("Failed to copy to clipboard");
    }
  }

  // --- Transcribe Actions ---
  async function transcribeYouTube(url, language = null) {
    if (!url || !url.trim()) return;
    pauseAndResetPlayers(true);
    setLoading(true, "Fetching YouTube captions...");

    try {
      const response = await fetch("/api/transcribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), language: language })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Failed to fetch YouTube transcript.");
      }

      currentData = data;
      renderResult(data, { resetSearch: language === null });
      addToHistory(data);
      resultSection.hidden = false;
      resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showAlert(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function transcribeLocal() {
    const filePath = localFilePathInput.value.trim();
    if (!selectedLocalFile && !filePath) {
      showAlert("Please select or drop a video/audio file, or enter a local file path on disk.");
      return;
    }

    const modelSize = localModelSelect.value;
    const language = localLangSelect.value;

    pauseAndResetPlayers(true);
    setLoading(true, `Processing with Whisper (${modelSize})... this may take a few seconds.`);

    try {
      const formData = new FormData();
      if (selectedLocalFile) {
        formData.append("file", selectedLocalFile);
      }
      if (filePath) {
        formData.append("file_path", filePath);
      }
      formData.append("model_size", modelSize);
      if (language && language !== "auto") {
        formData.append("language", language);
      }

      const response = await fetch("/api/transcribe-local", {
        method: "POST",
        body: formData
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Local transcription failed.");
      }

      currentData = data;
      renderResult(data, { resetSearch: true });
      addToHistory(data);
      resultSection.hidden = false;
      resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
      showAlert(err.message);
    } finally {
      setLoading(false);
    }
  }

  // --- Render Metadata & Language Selector ---
  function renderMetadata(data) {
    const meta = data.metadata || {};
    const stats = data.stats || {};
    const currLang = data.current_language || {};
    const isLocal = !!meta.is_local;

    metaTitle.textContent = meta.title || "Media File";
    metaAuthor.textContent = meta.author || (isLocal ? "Local file" : "Channel");
    metaSourceBadge.textContent = isLocal ? "Local (Whisper)" : "YouTube";

    metaThumb.src = meta.thumbnail_url || DEFAULT_THUMB_SVG;

    const totalWords = stats.total_words ?? 0;
    const totalSegs = stats.total_segments ?? 0;
    metaDurationBadge.textContent = stats.duration_formatted || "00:00";
    metaWordsBadge.textContent = `${totalWords.toLocaleString()} ${totalWords === 1 ? "word" : "words"}`;
    metaSegmentsBadge.textContent = `${totalSegs} ${totalSegs === 1 ? "segment" : "segments"}`;

    pauseAndResetPlayers(true);

    if (isLocal && meta.media_url) {
      const hasVideo = meta.has_video !== false;
      localPlayerCard.hidden = false;
      if (hasVideo) {
        playerBody.classList.remove("is-audio");
        localAudioPlayer.hidden = true;
        localVideoPlayer.hidden = false;
        localVideoPlayer.src = meta.media_url;
      } else {
        playerBody.classList.add("is-audio");
        localVideoPlayer.hidden = true;
        localAudioPlayer.hidden = false;
        localAudioPlayer.src = meta.media_url;
      }

      metaVideoLink.hidden = false;
      metaVideoLink.href = "#localPlayerCard";
      metaVideoLink.removeAttribute("target");
      metaVideoLink.removeAttribute("rel");
      metaVideoLink.title = "Play locally";
      metaVideoLink.setAttribute("aria-label", "Play locally");
      metaVideoLink.onclick = (e) => {
        e.preventDefault();
        const mediaEl = getActiveMediaElement();
        if (mediaEl) {
          localPlayerCard.scrollIntoView({ behavior: "smooth", block: "center" });
          mediaEl.play().catch(() => {});
        }
      };
    } else if (isLocal) {
      localPlayerCard.hidden = true;
      metaVideoLink.hidden = true;
      metaVideoLink.onclick = null;
    } else {
      localPlayerCard.hidden = true;
      metaVideoLink.hidden = false;
      metaVideoLink.href = meta.url || `https://www.youtube.com/watch?v=${meta.video_id}`;
      metaVideoLink.target = "_blank";
      metaVideoLink.rel = "noopener noreferrer";
      metaVideoLink.title = "Watch on YouTube";
      metaVideoLink.setAttribute("aria-label", "Watch on YouTube");
      metaVideoLink.onclick = null;
    }

    // Populate language selector
    langSelect.innerHTML = "";
    (data.available_languages || []).forEach((track) => {
      const opt = document.createElement("option");
      opt.value = track.language_code;
      opt.textContent =
        track.display_name || `${track.language} (${track.is_generated ? "auto-generated" : "manual"})`;
      if (track.language_code === currLang.language_code) {
        opt.selected = true;
      }
      langSelect.appendChild(opt);
    });
  }

  // --- Render Transcript Content ---
  function renderTranscript() {
    if (!currentData || !currentData.segments) return;

    const trimmedQuery = searchQuery.trim();
    const queryLower = trimmedQuery.toLowerCase();
    const useNativeHighlight = supportsCustomHighlights();
    let matchesCount = 0;
    const isLocal = !!currentData.metadata?.is_local;

    if (useNativeHighlight) {
      CSS.highlights.clear();
    }

    // 1. Render Segments View
    segmentsView.innerHTML = "";
    if (currentData.segments.length === 0) {
      const emptyNote = document.createElement("div");
      emptyNote.className = "empty-transcript-note";
      emptyNote.textContent = "No speech segments were detected in this audio.";
      segmentsView.appendChild(emptyNote);
    }

    currentData.segments.forEach((seg) => {
      const segTextLower = seg.text.toLowerCase();
      const isMatch = queryLower && segTextLower.includes(queryLower);
      if (isMatch) matchesCount++;

      if (queryLower && !isMatch) return;

      const segItem = document.createElement("div");
      segItem.className = "segment-item";
      segItem.dataset.segIndex = String(seg.index);

      const timeBtn = document.createElement("button");
      timeBtn.type = "button";
      timeBtn.className = "segment-time";
      timeBtn.title = isLocal
        ? "Jump to this timestamp in player"
        : "Open YouTube video at this timestamp";
      timeBtn.textContent = `[${seg.start_formatted}]`;

      timeBtn.addEventListener("click", () => {
        const mediaEl = getActiveMediaElement();
        if (isLocal && mediaEl && !localPlayerCard.hidden) {
          mediaEl.currentTime = seg.start;
          mediaEl.play().catch(() => {});
          updatePlayingSegment(seg.start);
          showToast(`Playing from ${seg.start_formatted}`);
        } else if (isLocal) {
          showToast("Media playback is unavailable for this cached entry");
        } else {
          const vidId = currentData.metadata.video_id;
          const jumpSeconds = Math.floor(seg.start);
          window.open(`https://youtu.be/${vidId}?t=${jumpSeconds}`, "_blank", "noopener");
        }
      });

      const textSpan = document.createElement("span");
      textSpan.className = "segment-text";
      if (useNativeHighlight || !trimmedQuery) {
        textSpan.textContent = seg.text;
      } else {
        appendHighlightedDom(textSpan, seg.text, trimmedQuery);
      }

      const actionsDiv = document.createElement("div");
      actionsDiv.className = "segment-actions";

      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "btn-seg-copy";
      copyBtn.textContent = "Copy";
      copyBtn.title = "Copy this segment";
      copyBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        copyToClipboard(seg.text, "Segment copied");
      });

      actionsDiv.appendChild(copyBtn);
      segItem.appendChild(timeBtn);
      segItem.appendChild(textSpan);
      segItem.appendChild(actionsDiv);
      segmentsView.appendChild(segItem);
    });

    if (queryLower && currentData.segments.length > 0 && matchesCount === 0) {
      const noMatches = document.createElement("div");
      noMatches.className = "empty-transcript-note";
      noMatches.textContent = `No segments matched "${trimmedQuery}".`;
      segmentsView.appendChild(noMatches);
    }

    // 2. Render Continuous Paragraph View
    continuousView.innerHTML = "";
    const segments = currentData.segments;
    let currentParagraph = [];

    if (segments.length === 0) {
      const emptyNote = document.createElement("div");
      emptyNote.className = "empty-transcript-note";
      emptyNote.textContent = "No spoken words were detected in this audio.";
      continuousView.appendChild(emptyNote);
    }

    segments.forEach((seg, idx) => {
      currentParagraph.push(seg.text);
      if ((idx + 1) % 5 === 0 || idx === segments.length - 1) {
        const pText = currentParagraph.join(" ");
        const pEl = document.createElement("p");
        pEl.className = "continuous-paragraph";
        if (useNativeHighlight || !trimmedQuery) {
          pEl.textContent = pText;
        } else {
          appendHighlightedDom(pEl, pText, trimmedQuery);
        }
        continuousView.appendChild(pEl);
        currentParagraph = [];
      }
    });

    // Apply CSS Custom Highlight ranges across active view
    applySearchHighlights(trimmedQuery);

    // Update match count badge
    if (trimmedQuery) {
      matchesCountBadge.textContent = `${matchesCount} ${matchesCount === 1 ? "match" : "matches"}`;
      matchesCountBadge.hidden = false;
    } else {
      matchesCountBadge.hidden = true;
    }
  }

  function renderResult(data, { resetSearch = true } = {}) {
    if (resetSearch) {
      searchQuery = "";
      searchInput.value = "";
    }
    renderMetadata(data);
    renderTranscript();
  }

  // --- Export Handling ---
  function extractFilenameFromDisposition(disposition, fallback) {
    if (!disposition) return fallback;
    const utfMatch = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utfMatch && utfMatch[1]) {
      try {
        return decodeURIComponent(utfMatch[1].trim());
      } catch {}
    }
    const asciiMatch = disposition.match(/filename="?([^";]+)"?/i);
    if (asciiMatch && asciiMatch[1]) {
      return asciiMatch[1].trim();
    }
    return fallback;
  }

  async function triggerExport(format, includeTimestamps = true) {
    if (!currentData) return;

    showToast(`Preparing .${format.toUpperCase()} export...`);

    try {
      const response = await fetch("/api/export", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          format: format,
          include_timestamps: includeTimestamps,
          data: currentData
        })
      });

      if (!response.ok) {
        const errJson = await response.json();
        throw new Error(errJson.detail || "Export failed.");
      }

      const filename = extractFilenameFromDisposition(
        response.headers.get("Content-Disposition"),
        `transcript.${format}`
      );

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);

      showToast(`Downloaded ${filename}`);
    } catch (err) {
      console.error(err);
      showAlert(`Export error: ${err.message}`);
    }
  }

  // --- History Management ---
  function getHistory() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY_HISTORY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  function updateHistoryCount() {
    const list = getHistory();
    historyCountBadge.textContent = list.length;
  }

  function persistHistoryList(list) {
    try {
      localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(list));
      return true;
    } catch {
      // Strip bulky segments from older items first, then trim count if storage quota is tight
      for (let i = list.length - 1; i >= 0; i--) {
        if (list[i].segments) {
          delete list[i].segments;
          delete list[i].full_text;
          try {
            localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(list));
            return true;
          } catch {}
        }
      }
      while (list.length > 1) {
        list.pop();
        try {
          localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(list));
          return true;
        } catch {}
      }
      return false;
    }
  }

  function addToHistory(data) {
    try {
      let list = getHistory();
      const vidId = data.metadata?.video_id;
      list = list.filter((item) => item.metadata?.video_id !== vidId);
      list.unshift({
        metadata: data.metadata,
        stats: data.stats,
        current_language: data.current_language,
        available_languages: data.available_languages,
        segments: data.segments,
        full_text: data.full_text,
        timestamp: Date.now()
      });
      if (list.length > 20) list = list.slice(0, 20);
      persistHistoryList(list);
      updateHistoryCount();
    } catch (e) {
      console.warn("Could not save entry to history:", e);
    }
  }

  function renderHistoryDrawer() {
    const list = getHistory();
    historyList.innerHTML = "";

    if (list.length === 0) {
      const emptyEl = document.createElement("div");
      emptyEl.className = "history-empty";
      emptyEl.textContent = "No recent transcriptions";
      historyList.appendChild(emptyEl);
      return;
    }

    list.forEach((item) => {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "history-item";

      const thumb = document.createElement("img");
      thumb.className = "history-thumb";
      thumb.src = item.metadata?.thumbnail_url || HISTORY_THUMB_SVG;
      thumb.alt = "";

      const info = document.createElement("div");
      info.className = "history-info";

      const title = document.createElement("div");
      title.className = "history-title";
      title.textContent = item.metadata?.title || "Media";

      const sub = document.createElement("div");
      sub.className = "history-sub";
      const author = item.metadata?.author || "Source";
      const duration = item.stats?.duration_formatted || "";
      sub.textContent = duration ? `${author} • ${duration}` : author;

      info.appendChild(title);
      info.appendChild(sub);
      row.appendChild(thumb);
      row.appendChild(info);

      row.addEventListener("click", () => {
        historyDialog.close();
        if (item.metadata?.is_local) {
          switchSource("local");
          if (item.metadata?.url && item.metadata.url.includes("/")) {
            localFilePathInput.value = item.metadata.url;
          }
          if (Array.isArray(item.segments)) {
            currentData = item;
            renderResult(item, { resetSearch: true });
            resultSection.hidden = false;
            showToast("Loaded local transcript from history");
          } else {
            showToast("Loaded file info from history");
          }
        } else {
          switchSource("youtube");
          inputUrl.value =
            item.metadata?.url || `https://www.youtube.com/watch?v=${item.metadata?.video_id}`;
          transcribeYouTube(inputUrl.value, item.current_language?.language_code || null);
        }
      });

      historyList.appendChild(row);
    });
  }

  // --- Export Dropdown Helpers ---
  function setExportMenuOpen(open) {
    btnExportMenu.setAttribute("aria-expanded", String(open));
    exportDropdown.hidden = !open;
  }

  // --- Event Listeners Setup ---
  function setupEventListeners() {
    // Accessible tablists with keyboard navigation
    setupTablist(sourceTablist, [tabSourceYoutube, tabSourceLocal], (tab) => {
      switchSource(tab === tabSourceLocal ? "local" : "youtube");
    });
    tabSourceYoutube.addEventListener("click", () => switchSource("youtube"));
    tabSourceLocal.addEventListener("click", () => switchSource("local"));

    setupTablist(viewTablist, [tabSegments, tabContinuous], (tab) => {
      switchViewTab(tab === tabContinuous ? "continuous" : "segments");
    });
    tabSegments.addEventListener("click", () => switchViewTab("segments"));
    tabContinuous.addEventListener("click", () => switchViewTab("continuous"));

    // YouTube Form Submission
    youtubeForm.addEventListener("submit", (e) => {
      e.preventDefault();
      transcribeYouTube(inputUrl.value);
    });

    // YouTube Paste Button
    btnPaste.addEventListener("click", async () => {
      try {
        if (navigator.clipboard && navigator.clipboard.readText) {
          const text = await navigator.clipboard.readText();
          if (text) {
            inputUrl.value = text.trim();
            transcribeYouTube(text.trim());
          }
        } else {
          inputUrl.focus();
        }
      } catch {
        inputUrl.focus();
      }
    });

    // Quick Sample buttons
    document.querySelectorAll(".btn-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        const url = btn.getAttribute("data-url");
        if (url) {
          switchSource("youtube");
          inputUrl.value = url;
          transcribeYouTube(url);
        }
      });
    });

    // Drop Zone Click & Drag
    btnChooseLocalFile.addEventListener("click", () => {
      localFileInput.click();
    });

    dropZone.addEventListener("click", (e) => {
      if (e.target.closest("#btnRemoveFile") || e.target.closest("#btnChooseLocalFile")) return;
      localFileInput.click();
    });

    localFileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        setLocalFile(e.target.files[0]);
      }
    });

    btnRemoveFile.addEventListener("click", (e) => {
      e.stopPropagation();
      setLocalFile(null, false);
      btnChooseLocalFile.focus();
    });

    dropZone.addEventListener("dragover", (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
      dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        setLocalFile(e.dataTransfer.files[0]);
      }
    });

    // Toggle Path Input Accordion
    btnTogglePath.addEventListener("click", () => {
      const willOpen = pathInputWrapper.hidden;
      pathInputWrapper.hidden = !willOpen;
      btnTogglePath.setAttribute("aria-expanded", String(willOpen));
      if (willOpen) {
        localFilePathInput.focus();
      }
    });

    localFilePathInput.addEventListener("input", () => {
      if (localFilePathInput.value.trim() && selectedLocalFile) {
        setLocalFile(null, false);
      }
    });

    localFilePathInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        transcribeLocal();
      }
    });

    // Local Transcribe Submit
    btnSubmitLocal.addEventListener("click", () => {
      transcribeLocal();
    });

    // Sync active segment highlight & graceful expired preview handling
    [localVideoPlayer, localAudioPlayer].forEach((mediaEl) => {
      mediaEl.addEventListener("timeupdate", () => {
        if (!mediaEl.hidden) {
          updatePlayingSegment(mediaEl.currentTime);
        }
      });

      mediaEl.addEventListener("error", () => {
        if (mediaEl.getAttribute("src") && currentData?.metadata?.is_local) {
          localPlayerCard.hidden = true;
          metaVideoLink.hidden = true;
          showToast("Media file preview is no longer available on the server");
        }
      });
    });

    // Theme toggle
    btnThemeToggle.addEventListener("click", toggleTheme);

    // Alert close
    btnCloseAlert.addEventListener("click", hideAlert);

    // Language selector change in results
    langSelect.addEventListener("change", () => {
      if (!currentData) return;
      const selectedLang = langSelect.value;
      if (!currentData.metadata?.is_local) {
        transcribeYouTube(inputUrl.value || currentData.metadata.url, selectedLang);
      }
    });

    // In-transcript search
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value;
      renderTranscript();
    });

    // Copy actions
    btnCopyPlain.addEventListener("click", () => {
      if (!currentData || !currentData.full_text) return;
      copyToClipboard(currentData.full_text, "Transcript copied to clipboard");
    });

    btnCopyTimestamps.addEventListener("click", () => {
      if (!currentData || !currentData.segments) return;
      const text = currentData.segments
        .map((s) => `[${s.start_formatted}] ${s.text}`)
        .join("\n");
      copyToClipboard(text, "Timestamped transcript copied");
    });

    // Export dropdown toggle & keyboard handling
    btnExportMenu.addEventListener("click", (e) => {
      e.stopPropagation();
      const willOpen = exportDropdown.hidden;
      setExportMenuOpen(willOpen);
      if (willOpen && exportMenuItems.length > 0) {
        exportMenuItems[0].focus();
      }
    });

    exportDropdown.addEventListener("keydown", (e) => {
      if (exportDropdown.hidden) return;
      const idx = exportMenuItems.indexOf(document.activeElement);

      if (e.key === "Escape") {
        e.preventDefault();
        setExportMenuOpen(false);
        btnExportMenu.focus();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        const next = idx === -1 ? 0 : (idx + 1) % exportMenuItems.length;
        exportMenuItems[next].focus();
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        const prev = idx <= 0 ? exportMenuItems.length - 1 : idx - 1;
        exportMenuItems[prev].focus();
      } else if (e.key === "Home" && exportMenuItems.length > 0) {
        e.preventDefault();
        exportMenuItems[0].focus();
      } else if (e.key === "End" && exportMenuItems.length > 0) {
        e.preventDefault();
        exportMenuItems[exportMenuItems.length - 1].focus();
      }
    });

    document.addEventListener("click", (e) => {
      if (!btnExportMenu.contains(e.target) && !exportDropdown.contains(e.target)) {
        setExportMenuOpen(false);
      }
    });

    // Export dropdown item click
    exportMenuItems.forEach((item) => {
      item.addEventListener("click", () => {
        const fmt = item.getAttribute("data-format");
        const includeTime = item.getAttribute("data-timestamps") !== "false";
        setExportMenuOpen(false);
        triggerExport(fmt, includeTime);
      });
    });

    // Native History Modal Drawer (<dialog>)
    btnHistory.addEventListener("click", () => {
      renderHistoryDrawer();
      historyDialog.showModal();
    });

    btnCloseHistory.addEventListener("click", () => {
      historyDialog.close();
    });

    // Light-dismiss fallback for browsers without <dialog closedby="any">
    if (!("closedBy" in HTMLDialogElement.prototype)) {
      const outside = (e, dialog) => {
        const r = dialog.getBoundingClientRect();
        return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
      };
      let pressedOutside = false;
      historyDialog.addEventListener("pointerdown", (e) => {
        pressedOutside = outside(e, historyDialog);
      });
      historyDialog.addEventListener("pointerup", (e) => {
        if (pressedOutside && outside(e, historyDialog)) {
          historyDialog.close();
        }
      });
    }

    btnClearHistory.addEventListener("click", () => {
      localStorage.removeItem(STORAGE_KEY_HISTORY);
      updateHistoryCount();
      renderHistoryDrawer();
      showToast("History cleared");
    });
  }

  // Initialize
  function init() {
    initTheme();
    updateHistoryCount();
    setupEventListeners();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
