// --- Minimalist Transcript Web Application (YouTube & Local Media) ---

(function() {
  "use strict";

  // App State
  let currentData = null;
  let activeTab = "segments"; // "segments" | "continuous"
  let activeSource = "youtube"; // "youtube" | "local"
  let searchQuery = "";
  let selectedLocalFile = null;

  const STORAGE_KEY_THEME = "yt_transcript_theme";
  const STORAGE_KEY_HISTORY = "transcript_tool_history";

  // DOM Elements - Navigation & Global
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
  const localVideoPlayer = document.getElementById("localVideoPlayer");

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
  const tabSegments = document.getElementById("tabSegments");
  const tabContinuous = document.getElementById("tabContinuous");
  const searchInput = document.getElementById("transcriptSearchInput");
  const matchesCountBadge = document.getElementById("searchMatchesCount");
  const btnCopyPlain = document.getElementById("btnCopyPlain");
  const btnCopyTimestamps = document.getElementById("btnCopyTimestamps");
  const btnExportMenu = document.getElementById("btnExportMenu");
  const exportDropdown = document.getElementById("exportDropdown");

  // Content Views
  const segmentsView = document.getElementById("segmentsView");
  const continuousView = document.getElementById("continuousView");

  // History Elements
  const historyOverlay = document.getElementById("historyOverlay");
  const btnCloseHistory = document.getElementById("btnCloseHistory");
  const btnClearHistory = document.getElementById("btnClearHistory");
  const historyList = document.getElementById("historyList");

  // Toast
  const toastEl = document.getElementById("toast");
  let toastTimer = null;

  // --- Theme Management ---
  function initTheme() {
    const savedTheme = localStorage.getItem(STORAGE_KEY_THEME);
    if (savedTheme) {
      if (savedTheme === "dark") {
        document.documentElement.classList.add("dark");
      } else {
        document.documentElement.classList.remove("dark");
      }
    } else {
      if (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches) {
        document.documentElement.classList.add("dark");
      }
    }
  }

  function toggleTheme() {
    const isDark = document.documentElement.classList.toggle("dark");
    localStorage.setItem(STORAGE_KEY_THEME, isDark ? "dark" : "light");
  }

  // --- Toast Notification ---
  function showToast(message, duration = 2400) {
    if (toastTimer) clearTimeout(toastTimer);
    toastEl.textContent = message;
    toastEl.classList.remove("hidden");
    toastTimer = setTimeout(() => {
      toastEl.classList.add("hidden");
    }, duration);
  }

  // --- Alert System ---
  function showAlert(msg) {
    alertMessage.textContent = msg;
    statusAlert.classList.remove("hidden");
  }

  function hideAlert() {
    statusAlert.classList.add("hidden");
  }

  // --- Loading State ---
  function setLoading(isLoading, message = "Procesando transcripción...") {
    if (isLoading) {
      hideAlert();
      loadingMessage.textContent = message;
      loadingState.classList.remove("hidden");
      resultSection.classList.add("hidden");
      btnSubmitYoutube.disabled = true;
      btnSubmitLocal.disabled = true;
    } else {
      loadingState.classList.add("hidden");
      btnSubmitYoutube.disabled = false;
      btnSubmitLocal.disabled = false;
    }
  }

  // --- Source Tabs Switching ---
  function switchSource(source) {
    activeSource = source;
    if (source === "youtube") {
      tabSourceYoutube.classList.add("active");
      tabSourceYoutube.setAttribute("aria-selected", "true");
      tabSourceLocal.classList.remove("active");
      tabSourceLocal.setAttribute("aria-selected", "false");
      youtubePanel.classList.remove("hidden");
      localPanel.classList.add("hidden");
    } else {
      tabSourceLocal.classList.add("active");
      tabSourceLocal.setAttribute("aria-selected", "true");
      tabSourceYoutube.classList.remove("active");
      tabSourceYoutube.setAttribute("aria-selected", "false");
      localPanel.classList.remove("hidden");
      youtubePanel.classList.add("hidden");
    }
    hideAlert();
  }

  // --- File Selection & Drag & Drop Handling ---
  function setLocalFile(file) {
    selectedLocalFile = file;
    if (file) {
      fileBadgeName.textContent = `${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)`;
      fileSelectedBadge.classList.remove("hidden");
      localFilePathInput.value = "";
    } else {
      selectedLocalFile = null;
      localFileInput.value = "";
      fileSelectedBadge.classList.add("hidden");
    }
  }

  // --- Helper: Escape HTML ---
  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  // --- Helper: Highlight text ---
  function highlightText(text, query) {
    if (!query) return escapeHtml(text);
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi");
    return escapeHtml(text).replace(regex, "<mark class=\"search-highlight\">$1</mark>");
  }

  // --- Clipboard Copy ---
  async function copyToClipboard(text, message = "Copiado al portapapeles") {
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
      console.error("Error al copiar:", err);
      showToast("No se pudo copiar al portapapeles");
    }
  }

  // --- Transcribe Actions ---
  async function transcribeYouTube(url, language = null) {
    if (!url || !url.trim()) return;
    setLoading(true, "Consultando subtítulos de YouTube...");

    try {
      const response = await fetch("/api/transcribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim(), language: language })
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Error al procesar la transcripción de YouTube.");
      }

      currentData = data;
      renderResult(data);
      addToHistory(data);
      resultSection.classList.remove("hidden");
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
      showAlert("Por favor, selecciona o arrastra un archivo de video/audio, o introduce una ruta en disco.");
      return;
    }

    const modelSize = localModelSelect.value;
    const language = localLangSelect.value;

    setLoading(true, `Procesando con Whisper (${modelSize})... esto puede tomar unos segundos.`);

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
        throw new Error(data.detail || "Error durante la transcripción local.");
      }

      currentData = data;
      renderResult(data);
      addToHistory(data);
      resultSection.classList.remove("hidden");
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

    metaTitle.textContent = meta.title || "Archivo Multimedia";
    metaAuthor.textContent = meta.author || (isLocal ? "Archivo local" : "Canal");
    metaSourceBadge.textContent = isLocal ? "Local (Whisper)" : "YouTube";

    // Thumbnail / Preview image
    if (meta.thumbnail_url) {
      metaThumb.src = meta.thumbnail_url;
      metaThumb.style.display = "block";
    } else {
      // Default SVG placeholder for local audio
      metaThumb.src = "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='70' viewBox='0 0 120 70' fill='%231e293b'><rect width='120' height='70' rx='8'/><circle cx='60' cy='35' r='18' fill='%23334155'/><polygon points='56,26 68,35 56,44' fill='%23f8fafc'/></svg>";
    }

    if (isLocal) {
      metaVideoLink.removeAttribute("href");
      metaVideoLink.title = "Reproducir localmente";
      metaVideoLink.onclick = (e) => {
        e.preventDefault();
        if (meta.media_url && localVideoPlayer) {
          localPlayerCard.scrollIntoView({ behavior: "smooth", block: "center" });
          localVideoPlayer.play();
        }
      };
    } else {
      metaVideoLink.href = meta.url || `https://www.youtube.com/watch?v=${meta.video_id}`;
      metaVideoLink.title = "Ver en YouTube";
      metaVideoLink.onclick = null;
    }

    metaDurationBadge.textContent = stats.duration_formatted || "00:00";
    metaWordsBadge.textContent = `${stats.total_words?.toLocaleString() || 0} palabras`;
    metaSegmentsBadge.textContent = `${stats.total_segments || 0} fragmentos`;

    // Local player setup
    if (isLocal && meta.media_url) {
      localVideoPlayer.src = meta.media_url;
      localPlayerCard.classList.remove("hidden");
    } else {
      localPlayerCard.classList.add("hidden");
      localVideoPlayer.removeAttribute("src");
    }

    // Populate language selector
    langSelect.innerHTML = "";
    (data.available_languages || []).forEach(track => {
      const opt = document.createElement("option");
      opt.value = track.language_code;
      opt.textContent = track.display_name || `${track.language} (${track.is_generated ? "autogenerado" : "manual"})`;
      if (track.language_code === currLang.language_code) {
        opt.selected = true;
      }
      langSelect.appendChild(opt);
    });
  }

  // --- Render Transcript Content ---
  function renderTranscript() {
    if (!currentData || !currentData.segments) return;

    const query = searchQuery.trim().toLowerCase();
    let matchesCount = 0;
    const isLocal = !!currentData.metadata?.is_local;

    // 1. Render Segments View
    segmentsView.innerHTML = "";
    if (currentData.segments.length === 0) {
      segmentsView.innerHTML = `<div class="empty-transcript-note">No se detectaron fragmentos de voz o palabras en el audio.</div>`;
    }

    currentData.segments.forEach(seg => {
      const segTextLower = seg.text.toLowerCase();
      const isMatch = query && segTextLower.includes(query);
      if (isMatch) matchesCount++;

      if (query && !isMatch) return;

      const segItem = document.createElement("div");
      segItem.className = "segment-item";

      const timeBtn = document.createElement("button");
      timeBtn.className = "segment-time";
      timeBtn.title = isLocal ? "Saltar a este segundo en el reproductor" : "Abrir video de YouTube en este segundo";
      timeBtn.textContent = `[${seg.start_formatted}]`;

      timeBtn.addEventListener("click", () => {
        if (isLocal && localVideoPlayer) {
          localPlayerCard.classList.remove("hidden");
          localVideoPlayer.currentTime = seg.start;
          localVideoPlayer.play();
          showToast(`Reproduciendo desde ${seg.start_formatted}`);
        } else {
          const vidId = currentData.metadata.video_id;
          const jumpSeconds = Math.floor(seg.start);
          window.open(`https://youtu.be/${vidId}?t=${jumpSeconds}`, "_blank");
        }
      });

      const textSpan = document.createElement("span");
      textSpan.className = "segment-text";
      textSpan.innerHTML = highlightText(seg.text, query);

      const actionsDiv = document.createElement("div");
      actionsDiv.className = "segment-actions";

      const copyBtn = document.createElement("button");
      copyBtn.className = "btn-seg-copy";
      copyBtn.textContent = "Copiar";
      copyBtn.title = "Copiar este fragmento";
      copyBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        copyToClipboard(seg.text, "Fragmento copiado");
      });

      actionsDiv.appendChild(copyBtn);
      segItem.appendChild(timeBtn);
      segItem.appendChild(textSpan);
      segItem.appendChild(actionsDiv);
      segmentsView.appendChild(segItem);
    });

    // 2. Render Continuous Paragraph View
    continuousView.innerHTML = "";
    const segments = currentData.segments;
    let currentParagraph = [];

    if (segments.length === 0) {
      continuousView.innerHTML = `<div class="empty-transcript-note">No se detectaron palabras en el audio.</div>`;
    }

    segments.forEach((seg, idx) => {
      currentParagraph.push(seg.text);
      if ((idx + 1) % 5 === 0 || idx === segments.length - 1) {
        const pText = currentParagraph.join(" ");
        const pEl = document.createElement("p");
        pEl.className = "continuous-paragraph";
        pEl.innerHTML = highlightText(pText, query);
        continuousView.appendChild(pEl);
        currentParagraph = [];
      }
    });

    // Update match count badge
    if (query) {
      matchesCountBadge.textContent = `${matchesCount} ${matchesCount === 1 ? "coincidencia" : "coincidencias"}`;
      matchesCountBadge.classList.remove("hidden");
    } else {
      matchesCountBadge.classList.add("hidden");
    }
  }

  function renderResult(data) {
    renderMetadata(data);
    renderTranscript();
  }

  // --- Export Handling ---
  async function triggerExport(format, includeTimestamps = true) {
    if (!currentData) return;

    showToast(`Preparando exportación .${format.toUpperCase()}...`);

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
        throw new Error(errJson.detail || "Error al exportar");
      }

      let filename = `transcripcion.${format}`;
      const disposition = response.headers.get("Content-Disposition");
      if (disposition && disposition.includes("filename=")) {
        const match = disposition.match(/filename="?([^"]+)"?/);
        if (match && match[1]) filename = match[1];
      }

      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(downloadUrl);

      showToast(`Descarga de ${filename} lista`);
    } catch (err) {
      console.error(err);
      showAlert(`Error en la exportación: ${err.message}`);
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

  function addToHistory(data) {
    try {
      let list = getHistory();
      const vidId = data.metadata?.video_id;
      list = list.filter(item => item.metadata?.video_id !== vidId);
      list.unshift({
        metadata: data.metadata,
        stats: data.stats,
        current_language: data.current_language,
        timestamp: Date.now()
      });
      if (list.length > 25) list = list.slice(0, 25);
      localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(list));
      updateHistoryCount();
    } catch (e) {
      console.warn("No se pudo guardar en el historial:", e);
    }
  }

  function renderHistoryDrawer() {
    const list = getHistory();
    historyList.innerHTML = "";

    if (list.length === 0) {
      historyList.innerHTML = `<div class="history-empty">No hay transcripciones recientes</div>`;
      return;
    }

    list.forEach(item => {
      const row = document.createElement("div");
      row.className = "history-item";

      const thumb = document.createElement("img");
      thumb.className = "history-thumb";
      thumb.src = item.metadata?.thumbnail_url || "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='48' height='36' viewBox='0 0 48 36' fill='%231e293b'><rect width='48' height='36' rx='4'/></svg>";
      thumb.alt = "";

      const info = document.createElement("div");
      info.className = "history-info";

      const title = document.createElement("div");
      title.className = "history-title";
      title.textContent = item.metadata?.title || "Video";

      const sub = document.createElement("div");
      sub.className = "history-sub";
      sub.textContent = `${item.metadata?.author || "Origen"} • ${item.stats?.duration_formatted || ""}`;

      info.appendChild(title);
      info.appendChild(sub);
      row.appendChild(thumb);
      row.appendChild(info);

      row.addEventListener("click", () => {
        historyOverlay.classList.add("hidden");
        if (item.metadata?.is_local) {
          switchSource("local");
          if (item.metadata?.url && item.metadata.url.includes("/")) {
            localFilePathInput.value = item.metadata.url;
          }
          showToast("Archivo local cargado del historial");
        } else {
          switchSource("youtube");
          inputUrl.value = item.metadata?.url || `https://www.youtube.com/watch?v=${item.metadata?.video_id}`;
          transcribeYouTube(inputUrl.value, item.current_language?.language_code);
        }
      });

      historyList.appendChild(row);
    });
  }

  // --- Event Listeners Setup ---
  function setupEventListeners() {
    // Source Tabs
    tabSourceYoutube.addEventListener("click", () => switchSource("youtube"));
    tabSourceLocal.addEventListener("click", () => switchSource("local"));

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
      } catch (err) {
        inputUrl.focus();
      }
    });

    // Quick Sample buttons
    document.querySelectorAll(".btn-chip").forEach(btn => {
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
    dropZone.addEventListener("click", (e) => {
      if (e.target.closest("#btnRemoveFile")) return;
      localFileInput.click();
    });

    localFileInput.addEventListener("change", (e) => {
      if (e.target.files && e.target.files[0]) {
        setLocalFile(e.target.files[0]);
      }
    });

    btnRemoveFile.addEventListener("click", (e) => {
      e.stopPropagation();
      setLocalFile(null);
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
      pathInputWrapper.classList.toggle("hidden");
      if (!pathInputWrapper.classList.contains("hidden")) {
        localFilePathInput.focus();
      }
    });

    // Local Transcribe Submit
    btnSubmitLocal.addEventListener("click", () => {
      transcribeLocal();
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

    // View tab switching (Segments vs Continuous)
    tabSegments.addEventListener("click", () => {
      activeTab = "segments";
      tabSegments.classList.add("active");
      tabSegments.setAttribute("aria-selected", "true");
      tabContinuous.classList.remove("active");
      tabContinuous.setAttribute("aria-selected", "false");
      segmentsView.classList.remove("hidden");
      continuousView.classList.add("hidden");
    });

    tabContinuous.addEventListener("click", () => {
      activeTab = "continuous";
      tabContinuous.classList.add("active");
      tabContinuous.setAttribute("aria-selected", "true");
      tabSegments.classList.remove("active");
      tabSegments.setAttribute("aria-selected", "false");
      continuousView.classList.remove("hidden");
      segmentsView.classList.add("hidden");
    });

    // In-transcript search
    searchInput.addEventListener("input", (e) => {
      searchQuery = e.target.value;
      renderTranscript();
    });

    // Copy actions
    btnCopyPlain.addEventListener("click", () => {
      if (!currentData || !currentData.full_text) return;
      copyToClipboard(currentData.full_text, "Texto copiado al portapapeles");
    });

    btnCopyTimestamps.addEventListener("click", () => {
      if (!currentData || !currentData.segments) return;
      const text = currentData.segments
        .map(s => `[${s.start_formatted}] ${s.text}`)
        .join("\n");
      copyToClipboard(text, "Texto con marcas de tiempo copiado");
    });

    // Export dropdown toggle
    btnExportMenu.addEventListener("click", (e) => {
      e.stopPropagation();
      const isExpanded = btnExportMenu.getAttribute("aria-expanded") === "true";
      btnExportMenu.setAttribute("aria-expanded", !isExpanded);
      exportDropdown.classList.toggle("hidden");
    });

    document.addEventListener("click", (e) => {
      if (!btnExportMenu.contains(e.target) && !exportDropdown.contains(e.target)) {
        btnExportMenu.setAttribute("aria-expanded", "false");
        exportDropdown.classList.add("hidden");
      }
    });

    // Export dropdown item click
    document.querySelectorAll(".dropdown-item").forEach(item => {
      item.addEventListener("click", (e) => {
        const fmt = item.getAttribute("data-format");
        const includeTime = item.getAttribute("data-timestamps") !== "false";
        exportDropdown.classList.add("hidden");
        btnExportMenu.setAttribute("aria-expanded", "false");
        triggerExport(fmt, includeTime);
      });
    });

    // History Drawer
    btnHistory.addEventListener("click", () => {
      renderHistoryDrawer();
      historyOverlay.classList.remove("hidden");
    });

    btnCloseHistory.addEventListener("click", () => {
      historyOverlay.classList.add("hidden");
    });

    historyOverlay.addEventListener("click", (e) => {
      if (e.target === historyOverlay) {
        historyOverlay.classList.add("hidden");
      }
    });

    btnClearHistory.addEventListener("click", () => {
      localStorage.removeItem(STORAGE_KEY_HISTORY);
      updateHistoryCount();
      renderHistoryDrawer();
      showToast("Historial eliminado");
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
