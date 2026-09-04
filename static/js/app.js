(() => {
    const fileInput = document.getElementById("file-input");
    const dropzone = document.getElementById("dropzone");
    const formatList = document.getElementById("format-list");
    const ffmpegNote = document.getElementById("ffmpeg-note");
    const fileList = document.getElementById("file-list");
    const detectPanel = document.getElementById("detect-panel");
    const outputName = document.getElementById("output-name");
    const progressFill = document.getElementById("progress-fill");
    const progressPercent = document.getElementById("progress-percent");
    const progressFile = document.getElementById("progress-file");
    const progressStatus = document.getElementById("progress-status");
    const progressBar = document.getElementById("progress-bar");
    const resultMeta = document.getElementById("result-meta");
    const errorText = document.getElementById("error-text");
    const btnDownload = document.getElementById("btn-download");

    const panels = {
        select: document.getElementById("panel-select"),
        files: document.getElementById("panel-files"),
        progress: document.getElementById("panel-progress"),
        success: document.getElementById("panel-success"),
        error: document.getElementById("panel-error"),
    };

    const state = {
        files: [],
        config: null,
        jobId: null,
        pollTimer: null,
        downloadUrl: null,
        resultName: null,
    };

    const showPanel = (name) => {
        Object.entries(panels).forEach(([key, node]) => {
            node.hidden = key !== name;
        });
    };

    const formatBytes = (bytes) => {
        if (bytes < 1024) return `${bytes} B`;
        const units = ["KB", "MB", "GB"];
        let value = bytes / 1024;
        let unit = units[0];
        for (let i = 0; i < units.length; i += 1) {
            unit = units[i];
            if (value < 1024 || i === units.length - 1) break;
            value /= 1024;
        }
        return `${value.toFixed(1)} ${unit}`;
    };

    const extensionOf = (name) => {
        const parts = name.split(".");
        return parts.length > 1 ? parts.pop().toUpperCase() : "—";
    };

    const resetProgress = () => {
        progressFill.style.width = "0%";
        progressPercent.textContent = "0%";
        progressStatus.textContent = "0%";
        progressFile.textContent = "Preparando";
        progressBar.classList.remove("is-indeterminate");
    };

    const setProgress = (percent, message) => {
        const value = Math.max(0, Math.min(100, Number(percent) || 0));
        progressFill.style.width = `${value}%`;
        progressPercent.textContent = `${value}%`;
        progressStatus.textContent = `${value}%`;
        if (message) progressFile.textContent = message;
    };

    const renderFormats = (formats) => {
        formatList.innerHTML = "";
        (formats || []).forEach((group) => {
            const block = document.createElement("section");
            block.className = "format-group";
            const title = document.createElement("strong");
            title.textContent = group.label || group.category || "";
            const list = document.createElement("ul");
            list.className = "formats";
            (group.extensions || []).forEach((ext) => {
                const item = document.createElement("li");
                item.textContent = ext;
                list.appendChild(item);
            });
            block.append(title, list);
            formatList.appendChild(block);
        });
    };

    const renderDetect = async () => {
        detectPanel.innerHTML = "";
        if (state.files.length < 2) {
            detectPanel.innerHTML = '<div class="detect-chip is-warn">Selecione pelo menos dois arquivos</div>';
            return;
        }
        try {
            const response = await fetch("/api/detect", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ names: state.files.map((item) => item.name) }),
            });
            const data = await response.json();
            if (!data.ok) {
                detectPanel.innerHTML = `<div class="detect-chip is-warn">${data.error}</div>`;
                return;
            }
            const info = data.detected;
            detectPanel.innerHTML = `
                <div class="detect-chip">Tipo: <span>${info.category_label}</span></div>
                <div class="detect-chip">Formato: <span>${info.format_label}</span></div>
                <div class="detect-chip">Saída: <span>${String(info.output_ext || "").replace(".", "").toUpperCase()}</span></div>
            `;
            if (info.needs_ffmpeg && state.config && !state.config.ffmpeg) {
                detectPanel.insertAdjacentHTML(
                    "beforeend",
                    '<div class="detect-chip is-warn">FFmpeg necessário para este formato</div>'
                );
            }
        } catch (_error) {
            detectPanel.innerHTML = '<div class="detect-chip is-warn">Não foi possível identificar o formato.</div>';
        }
    };

    const renderList = () => {
        fileList.innerHTML = "";
        state.files.forEach((file, index) => {
            const row = document.createElement("li");
            row.className = "file-row";
            row.draggable = true;
            row.dataset.index = String(index);
            row.innerHTML = `
                <span class="drag-handle" title="Arrastar">☰</span>
                <span class="file-pos">${index + 1}</span>
                <div class="file-info">
                    <strong>${file.name}</strong>
                    <small>${extensionOf(file.name)} · ${formatBytes(file.size)} · posição ${index + 1}</small>
                </div>
                <div class="file-actions">
                    <button class="icon-btn" data-act="up" ${index === 0 ? "disabled" : ""} title="Mover para cima">↑</button>
                    <button class="icon-btn" data-act="down" ${index === state.files.length - 1 ? "disabled" : ""} title="Mover para baixo">↓</button>
                    <button class="icon-btn is-danger" data-act="remove" title="Remover">×</button>
                </div>
            `;
            fileList.appendChild(row);
        });
        const ready = state.files.length >= 2;
        showPanel(ready || state.files.length ? "files" : "select");
        if (!state.files.length) {
            showPanel("select");
        }
        renderDetect();
    };

    const sameFile = (left, right) =>
        left.name === right.name && left.size === right.size && left.lastModified === right.lastModified;

    const addFiles = (fileListLike) => {
        const incoming = Array.from(fileListLike || []);
        incoming.forEach((file) => {
            if (!state.files.some((existing) => sameFile(existing, file))) {
                state.files.push(file);
            }
        });
        renderList();
    };

    const moveFile = (index, delta) => {
        const next = index + delta;
        if (next < 0 || next >= state.files.length) return;
        const copy = state.files.splice(index, 1)[0];
        state.files.splice(next, 0, copy);
        renderList();
    };

    const clearFiles = () => {
        state.files = [];
        outputName.value = "";
        fileInput.value = "";
        showPanel("select");
    };

    const showError = (message) => {
        errorText.textContent = message;
        showPanel("error");
    };

    const pollJob = async (jobId) => {
        const response = await fetch(`/api/jobs/${jobId}`);
        const data = await response.json();
        if (!data.ok) {
            throw new Error(data.error || "Operação não encontrada.");
        }
        const job = data.job;
        setProgress(job.progress, job.message);
        if (job.status === "done") {
            state.downloadUrl = `/api/download/${jobId}`;
            state.resultName = job.result_name;
            btnDownload.href = state.downloadUrl;
            resultMeta.textContent = `Arquivo: ${job.result_name}  ·  Tamanho: ${job.result_size_label}`;
            showPanel("success");
            return true;
        }
        if (job.status === "error") {
            throw new Error(job.error || "Não foi possível concluir a mesclagem.");
        }
        return false;
    };

    const startMerge = () => {
        if (state.files.length < 2) {
            showError("Selecione pelo menos dois arquivos para mesclar.");
            return;
        }
        const form = new FormData();
        state.files.forEach((file) => form.append("files", file, file.name));
        form.append("output_name", outputName.value.trim());

        resetProgress();
        progressBar.classList.add("is-indeterminate");
        showPanel("progress");
        setProgress(5, "Enviando arquivos...");

        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/merge");
        xhr.upload.onprogress = (event) => {
            if (!event.lengthComputable) return;
            const percent = Math.max(5, Math.min(20, Math.round((event.loaded / event.total) * 20)));
            progressBar.classList.remove("is-indeterminate");
            setProgress(percent, "Enviando arquivos...");
        };
        xhr.onload = async () => {
            progressBar.classList.remove("is-indeterminate");
            let payload = {};
            try {
                payload = JSON.parse(xhr.responseText || "{}");
            } catch (_error) {
                showError("Não foi possível iniciar a mesclagem. Tente novamente.");
                return;
            }
            if (xhr.status >= 400 || !payload.ok) {
                showError(payload.error || "Não foi possível iniciar a mesclagem.");
                return;
            }
            state.jobId = payload.job_id;
            setProgress(22, "Processando arquivos...");
            const tick = async () => {
                try {
                    const done = await pollJob(state.jobId);
                    if (!done) {
                        state.pollTimer = window.setTimeout(tick, 400);
                    }
                } catch (error) {
                    showError(error.message);
                }
            };
            tick();
        };
        xhr.onerror = () => {
            showError("Falha de comunicação com o servidor. Verifique se o aplicativo está em execução.");
        };
        xhr.send(form);
    };

    const shareWhatsApp = async () => {
        if (!state.downloadUrl) return;
        try {
            const response = await fetch(state.downloadUrl);
            const blob = await response.blob();
            const file = new File([blob], state.resultName || "arquivo_mesclado", { type: blob.type });
            if (navigator.canShare && navigator.canShare({ files: [file] })) {
                await navigator.share({
                    files: [file],
                    title: state.resultName,
                    text: "Arquivo mesclado pelo Mesclador Universal",
                });
                return;
            }
        } catch (_error) {
            // fallback abaixo
        }
        window.open("https://web.whatsapp.com/", "_blank", "noopener");
    };

    fileList.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-act]");
        if (!button) return;
        const row = button.closest(".file-row");
        const index = Number(row.dataset.index);
        const action = button.dataset.act;
        if (action === "up") moveFile(index, -1);
        if (action === "down") moveFile(index, 1);
        if (action === "remove") {
            state.files.splice(index, 1);
            renderList();
        }
    });

    let dragIndex = null;
    fileList.addEventListener("dragstart", (event) => {
        const row = event.target.closest(".file-row");
        if (!row) return;
        dragIndex = Number(row.dataset.index);
        row.classList.add("is-dragging");
        event.dataTransfer.effectAllowed = "move";
    });
    fileList.addEventListener("dragend", (event) => {
        const row = event.target.closest(".file-row");
        if (row) row.classList.remove("is-dragging");
        dragIndex = null;
    });
    fileList.addEventListener("dragover", (event) => {
        event.preventDefault();
        const row = event.target.closest(".file-row");
        if (!row || dragIndex === null) return;
        const targetIndex = Number(row.dataset.index);
        if (targetIndex === dragIndex) return;
        const item = state.files.splice(dragIndex, 1)[0];
        state.files.splice(targetIndex, 0, item);
        dragIndex = targetIndex;
        renderList();
        const next = fileList.querySelector(`[data-index="${targetIndex}"]`);
        if (next) next.classList.add("is-dragging");
    });

    dropzone.addEventListener("dragover", (event) => {
        event.preventDefault();
        dropzone.classList.add("is-dragover");
    });
    dropzone.addEventListener("dragleave", () => dropzone.classList.remove("is-dragover"));
    dropzone.addEventListener("drop", (event) => {
        event.preventDefault();
        dropzone.classList.remove("is-dragover");
        addFiles(event.dataTransfer.files);
    });

    fileInput.addEventListener("change", () => {
        addFiles(fileInput.files);
        fileInput.value = "";
    });

    document.getElementById("btn-add").addEventListener("click", () => fileInput.click());
    document.getElementById("btn-clear").addEventListener("click", clearFiles);
    document.getElementById("btn-merge").addEventListener("click", startMerge);
    document.getElementById("btn-back").addEventListener("click", () => {
        showPanel(state.files.length ? "files" : "select");
    });
    document.getElementById("btn-new").addEventListener("click", () => {
        state.jobId = null;
        state.downloadUrl = null;
        clearFiles();
    });
    document.getElementById("btn-whatsapp").addEventListener("click", shareWhatsApp);

    const loadConfig = async () => {
        try {
            const response = await fetch("/api/config");
            const data = await response.json();
            state.config = data;
            renderFormats(data.formats);
            ffmpegNote.hidden = Boolean(data.ffmpeg);
            const accept = (data.formats || [])
                .flatMap((group) => group.extensions.map((ext) => `.${ext.toLowerCase()}`))
                .join(",");
            fileInput.setAttribute("accept", accept);
        } catch (_error) {
            formatList.innerHTML = (
                "<section class=\"format-group\"><strong>Dados</strong><ul class=\"formats\"><li>JSON</li></ul></section>"
                + "<section class=\"format-group\"><strong>Áudio</strong><ul class=\"formats\"><li>MP3</li></ul></section>"
                + "<section class=\"format-group\"><strong>Vídeo</strong><ul class=\"formats\"><li>MP4</li></ul></section>"
                + "<section class=\"format-group\"><strong>Documento</strong><ul class=\"formats\"><li>PDF</li><li>DOCX</li><li>TXT</li></ul></section>"
                + "<section class=\"format-group\"><strong>Planilha</strong><ul class=\"formats\"><li>XLSX</li></ul></section>"
                + "<section class=\"format-group\"><strong>Apresentações</strong><ul class=\"formats\"><li>PPTX</li></ul></section>"
            );
        }
    };

    loadConfig();
})();
