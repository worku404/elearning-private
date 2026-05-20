// Notes panel behavior script.
document.addEventListener("DOMContentLoaded", function () {
    // Cache the document body for class toggles.
    const bodyEl = document.body;
    // Locate the notes panel container.
    const panelEl = document.querySelector("[data-notes-panel]");
    // Abort setup if the panel is missing.
    if (!panelEl) return;

    // Grab the open button in the topbar.
    const openBtn = document.getElementById("notes-open-btn");
    // Grab the close button inside the panel.
    const closeBtn = panelEl.querySelector("[data-notes-close]");
    // Grab the delete button inside the panel.
    const deleteBtn = panelEl.querySelector("[data-notes-delete]");
    // Grab the backdrop element.
    const backdropEl = document.querySelector("[data-notes-backdrop]");
    // Grab the sidebar element.
    const sidebarEl = panelEl.querySelector("[data-notes-sidebar]");
    // Grab the sidebar toggle button.
    const sidebarToggleBtn = panelEl.querySelector("[data-notes-sidebar-toggle]");
    // Grab the clear filter button.
    const clearFilterBtn = panelEl.querySelector("[data-notes-clear-filter]");
    // Grab the filter label element.
    const filterLabelEl = panelEl.querySelector("[data-notes-filter-label]");
    // Grab the tag search input (filters notes by tag).
    const tagSearchInputEl = panelEl.querySelector("[data-notes-tag-search]");
    // Grab the (optional) tag search clear button.
    const tagSearchClearBtn = panelEl.querySelector("[data-notes-tag-search-clear]");
    // Grab the tag search submit button (search icon).
    const tagSearchSubmitBtn = panelEl.querySelector("[data-notes-tag-search-submit]");
    // Prefer the explicit submit button; fallback to the legacy clear button.
    const tagSearchActionBtn = tagSearchSubmitBtn || tagSearchClearBtn;
    // Only treat a separate element as the "clear" button.
    const tagSearchEffectiveClearBtn = tagSearchClearBtn && tagSearchClearBtn !== tagSearchActionBtn
        ? tagSearchClearBtn
        : null;
    // Grab the datalist used for tag suggestions.
    const tagDatalistEl = panelEl.querySelector("[data-notes-tag-datalist]");
    // Grab the notes list container.
    const listEl = panelEl.querySelector("[data-notes-list]");
    // Grab the empty state element.
    const emptyEl = panelEl.querySelector("[data-notes-empty]");
    // Grab the editor mount element.
    const editorMountEl = document.getElementById("notes-editor");
    // Grab the save modal overlay.
    const saveModalEl = panelEl.querySelector("[data-notes-save-modal]");
    // Grab the title input for save prompt.
    const titleInputEl = panelEl.querySelector("[data-notes-title-input]");
    // Grab the tag input for save prompt.
    const tagInputEl = panelEl.querySelector("[data-notes-tag-input]");
    // Grab the save button inside modal.
    const saveBtn = panelEl.querySelector("[data-notes-save]");
    // Grab the exit button inside modal.
    const exitBtn = panelEl.querySelector("[data-notes-exit]");
    // Grab the save error message element.
    const saveErrorEl = panelEl.querySelector("[data-notes-save-error]");
    // Collect the color buttons for text color selection.
    const colorButtons = Array.from(panelEl.querySelectorAll("[data-notes-color]"));

    // Limit tags per note to match backend validation.
    const MAX_NOTE_TAGS = 3;

    // Read the list endpoint URL from data attributes.
    const listUrl = panelEl.dataset.notesListUrl || "";
    // Read the detail endpoint URL template from data attributes.
    const detailUrlTemplate = panelEl.dataset.notesDetailUrlTemplate || "";

    // Store the Quill editor instance.
    let quill = null;
    // Track the currently open note ID.
    let currentNoteId = null;
    // Track whether the editor has unsaved changes.
    let isDirty = false;
    // Track whether the user has typed in the editor at least once.
    let hasUserTyped = false;
    // Track autosave debounce timer ID.
    let autosaveTimer = null;
    // Track the active tag filter slug.
    let activeTagSlug = "";
    // Remember the last known editor selection to restore focus safely.
    let lastSelection = null;
    // Track the shared code-copy overlay instance.
    let notesCopyOverlay = null;

    // Cache known tag slugs to names for search suggestions.
    const tagNameBySlug = new Map();
    // Cache known tag names to slugs for quick lookup.
    const tagSlugByName = new Map();

    // Return true when shortcuts should be ignored (mobile).
    const shortcutsDisabled = () => {
        // Disable shortcuts on small screens.
        return window.matchMedia("(max-width: 900px)").matches;
    };

    // Read a cookie by name for CSRF protection.
    const getCookie = (name) => {
        // Split document cookies into key-value pairs.
        const cookies = document.cookie ? document.cookie.split("; ") : [];
        // Loop through cookies to find a matching name.
        for (const c of cookies) {
            // Split the cookie into key and value parts.
            const [key, ...rest] = c.split("=");
            // Return decoded value when name matches.
            if (key === name) return decodeURIComponent(rest.join("="));
        }
        // Return an empty string when not found.
        return "";
    };

    // Build the detail URL for a specific note ID.
    const buildDetailUrl = (noteId) => {
        // Replace the placeholder "0" with the actual note ID.
        return detailUrlTemplate.replace("0", String(noteId));
    };

    // Toggle the notes panel open/closed.
    const setPanelOpen = (isOpen) => {
        // Toggle the body class for open state.
        bodyEl.classList.toggle("notes-open", isOpen);
        // Update panel aria-hidden state.
        panelEl.setAttribute("aria-hidden", String(!isOpen));
        // Update the launcher button expanded state.
        if (openBtn) openBtn.setAttribute("aria-expanded", String(isOpen));
        // Toggle backdrop visibility.
        if (backdropEl) backdropEl.hidden = !isOpen;
    };

    // Toggle the sidebar open/closed.
    const setSidebarOpen = (isOpen) => {
        // Toggle sidebar-open class on panel.
        panelEl.classList.toggle("notes-sidebar-open", isOpen);
        // Update sidebar aria-hidden state.
        if (sidebarEl) sidebarEl.setAttribute("aria-hidden", String(!isOpen));
        // Update sidebar toggle button expanded state.
        if (sidebarToggleBtn) sidebarToggleBtn.setAttribute("aria-expanded", String(isOpen));
    };

    // Clear editor content and reset state for a new note.
    const resetEditor = () => {
        // Guard against missing editor.
        if (!quill) return;
        // Clear the editor contents.
        quill.setText("");
        // Reset text color formatting to default.
        quill.format("color", false);
        // Clear any active color button state.
        colorButtons.forEach((btn) => btn.classList.remove("is-active"));
        // Reset current note tracking.
        currentNoteId = null;
        // Reset dirty state.
        isDirty = false;
        // Clear last known selection on reset.
        lastSelection = null;
        // Disable delete button for new notes.
        if (deleteBtn) deleteBtn.disabled = true;
    };

    // Show the save modal for unsaved notes.
    const showSaveModal = () => {
        // Guard against missing modal.
        if (!saveModalEl) return;
        // Reset any prior error message.
        if (saveErrorEl) {
            saveErrorEl.textContent = "";
            saveErrorEl.hidden = true;
        }
        // Clear title input before prompting.
        if (titleInputEl) titleInputEl.value = "";
        // Clear tag input before prompting.
        if (tagInputEl) tagInputEl.value = "";
        // Display the modal overlay.
        saveModalEl.hidden = false;
        // Focus title input for quick entry.
        if (titleInputEl) titleInputEl.focus();
    };

    // Hide the save modal.
    const hideSaveModal = () => {
        // Guard against missing modal.
        if (!saveModalEl) return;
        // Hide the modal overlay.
        saveModalEl.hidden = true;
    };

    // Determine whether a new note should prompt for save.
    const shouldPromptSave = () => {
        // Only prompt for new notes without IDs.
        if (currentNoteId !== null) return false;
        // Guard against missing editor.
        if (!quill) return false;
        // Require that the user actually typed content.
        if (!hasUserTyped) return false;
        // Check for non-empty editor content.
        const hasContent = quill.getText().trim().length > 0;
        // Prompt only when there is content.
        return hasContent;
    };

    // Sync tag search clear button state.
    const syncTagSearchClearButton = () => {
        if (!tagSearchInputEl || !tagSearchEffectiveClearBtn) return;
        tagSearchEffectiveClearBtn.hidden = tagSearchInputEl.value.trim().length === 0;
    };

    // Sync tag search input to reflect the active filter (when not focused).
    const syncTagSearchInputForActiveFilter = () => {
        if (!tagSearchInputEl) return;
        if (document.activeElement === tagSearchInputEl) {
            syncTagSearchClearButton();
            return;
        }
        if (!activeTagSlug) {
            tagSearchInputEl.value = "";
        } else {
            tagSearchInputEl.value = tagNameBySlug.get(activeTagSlug) || activeTagSlug;
        }
        syncTagSearchClearButton();
    };

    // Render available tags into the datalist for quick selection.
    const renderTagDatalist = () => {
        if (!tagDatalistEl) return;
        tagDatalistEl.innerHTML = "";
        const tags = Array.from(tagNameBySlug.entries())
            .map(([slug, name]) => ({ slug, name: String(name || slug) }))
            .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base" }));
        tags.forEach(({ slug, name }) => {
            const option = document.createElement("option");
            option.value = name;
            option.label = `#${slug}`;
            tagDatalistEl.appendChild(option);
        });
    };

    // Remember tags from a notes payload to power tag suggestions.
    const rememberTagsFromNotes = (notes) => {
        if (!Array.isArray(notes) || !notes.length) return;
        let changed = false;
        notes.forEach((note) => {
            const noteTags = Array.isArray(note.tags)
                ? note.tags
                : (note.tag ? [note.tag] : []);
            noteTags.forEach((tag) => {
                if (!tag || !tag.slug) return;
                const slug = String(tag.slug);
                const name = String(tag.name || tag.slug || "");
                if (!tagNameBySlug.has(slug) || (name && tagNameBySlug.get(slug) !== name)) {
                    tagNameBySlug.set(slug, name || slug);
                    changed = true;
                }
                if (name) {
                    const key = name.toLowerCase();
                    if (!tagSlugByName.has(key)) {
                        tagSlugByName.set(key, slug);
                        changed = true;
                    }
                }
            });
        });
        if (changed) {
            renderTagDatalist();
        }
    };

    // Basic slugify for tag input to match server-side `slugify`.
    const slugifyTagText = (value) => {
        const raw = String(value || "").trim().replace(/^#+/, "");
        if (!raw) return "";
        let normalized = raw;
        try {
            normalized = normalized.normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
        } catch (error) {
            // Ignore normalize failures (older browsers).
        }
        let slug = normalized.toLowerCase();
        slug = slug.replace(/['"]/g, "");
        slug = slug.replace(/[^a-z0-9\s_-]/g, "");
        slug = slug.replace(/[\s_]+/g, "-");
        slug = slug.replace(/-+/g, "-");
        slug = slug.replace(/^-+|-+$/g, "");
        slug = slug.slice(0, 70);
        return slug || "tag";
    };

    // Clear tag search input and remove active tag filter when present.
    const clearTagSearch = () => {
        if (tagSearchInputEl) {
            tagSearchInputEl.value = "";
        }
        syncTagSearchClearButton();
        if (activeTagSlug) {
            loadNotesList("");
        }
    };

    // Apply tag search input as a tag filter.
    const applyTagSearch = () => {
        if (!tagSearchInputEl) return;
        const rawValue = tagSearchInputEl.value.trim();
        if (!rawValue) {
            if (activeTagSlug) loadNotesList("");
            return;
        }
        const firstTag = (parseTagInput(rawValue)[0] || rawValue || "").trim();
        const cleaned = firstTag.replace(/^#+/, "").trim();
        if (!cleaned) {
            if (activeTagSlug) loadNotesList("");
            return;
        }
        const knownSlug = tagSlugByName.get(cleaned.toLowerCase()) || "";
        const slug = knownSlug || slugifyTagText(cleaned);
        loadNotesList(slug);
    };

    // Render the notes list into the sidebar.
    const renderNotesList = (notes) => {
        // Guard against missing list element.
        if (!listEl) return;
        // Remember tag options for the search suggestions.
        rememberTagsFromNotes(notes);
        // Clear existing list content.
        listEl.innerHTML = "";
        // Toggle empty state visibility.
        if (emptyEl) emptyEl.hidden = notes.length > 0;
        // Show or hide clear filter button.
        if (clearFilterBtn) clearFilterBtn.hidden = !activeTagSlug;
        // Show or hide filter label.
        if (filterLabelEl) {
            filterLabelEl.hidden = !activeTagSlug;
            filterLabelEl.textContent = activeTagSlug ? `Filter: #${activeTagSlug}` : "";
        }
        // Build list entries.
        notes.forEach((note) => {
            // Create list item wrapper.
            const item = document.createElement("li");
            // Create clickable note container.
            const button = document.createElement("div");
            // Apply the base item class.
            button.className = "notes-item";
            // Mark the item as active when it matches current note.
            if (currentNoteId === note.id) {
                button.classList.add("is-active");
            }
            // Make the item focusable and clickable.
            button.setAttribute("role", "button");
            // Allow keyboard focus.
            button.setAttribute("tabindex", "0");
            // Store the note id for event handling.
            button.dataset.noteId = String(note.id);
            // Set ARIA label for screen readers.
            button.setAttribute("aria-label", `Open note: ${note.title || "Untitled"}`);
            // Create title element.
            const titleEl = document.createElement("div");
            // Apply title class.
            titleEl.className = "notes-item__title";
            // Set title text.
            titleEl.textContent = note.title || "Untitled";
            // Append title into item.
            button.appendChild(titleEl);
            // Add tag badges when present.
            const noteTags = Array.isArray(note.tags)
                ? note.tags
                : (note.tag ? [note.tag] : []);
            if (noteTags.length) {
                // Create tag group wrapper.
                const tagsWrap = document.createElement("div");
                tagsWrap.className = "notes-item__tags";
                // Add each tag badge.
                noteTags.forEach((tag) => {
                    if (!tag || !tag.slug) return;
                    const tagBtn = document.createElement("button");
                    tagBtn.className = "notes-item__tag";
                    tagBtn.type = "button";
                    tagBtn.dataset.tagSlug = tag.slug;
                    tagBtn.textContent = tag.name || tag.slug;
                    tagsWrap.appendChild(tagBtn);
                });
                if (tagsWrap.childElementCount) {
                    button.appendChild(tagsWrap);
                }
            }
            // Create open indicator.
            const openEl = document.createElement("span");
            // Apply open indicator class.
            openEl.className = "notes-item__open";
            // Set open label.
            openEl.textContent = "Open";
            // Append open label to item.
            button.appendChild(openEl);
            // Append the button into the list item.
            item.appendChild(button);
            // Append the list item into the list.
            listEl.appendChild(item);
        });
    };

    // Fetch notes list from the server.
    const loadNotesList = async (tagSlug) => {
        // Update active tag filter state.
        activeTagSlug = tagSlug || "";
        // Keep the tag search input in sync with the active filter.
        syncTagSearchInputForActiveFilter();
        // Build list URL with optional tag filter.
        const url = activeTagSlug
            ? `${listUrl}?tag=${encodeURIComponent(activeTagSlug)}`
            : listUrl;
        // Guard when list URL is missing.
        if (!url) return;
        // Fetch notes from backend.
        try {
            // Issue GET request to list endpoint.
            const response = await fetch(url, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                credentials: "same-origin",
            });
            // Parse JSON response.
            const data = await response.json();
            // Render the notes list.
            renderNotesList(Array.isArray(data.notes) ? data.notes : []);
        } catch (error) {
            // Render empty list on failure.
            renderNotesList([]);
        }
    };

    // Load a single note into the editor.
    const loadNote = async (noteId) => {
        // Guard against missing editor.
        if (!quill) return;
        // Build the detail URL.
        const detailUrl = buildDetailUrl(noteId);
        // Fetch the note from backend.
        try {
            // Issue GET request to detail endpoint.
            const response = await fetch(detailUrl, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                credentials: "same-origin",
            });
            // Parse JSON response.
            const data = await response.json();
            // Extract note object from payload.
            const note = data.note || null;
            // Skip when payload is missing.
            if (!note) return;
            // Set current note ID.
            currentNoteId = note.id;
        // Reset dirty state.
        isDirty = false;
        // Reset typed state for a fresh note.
        hasUserTyped = false;
            // Enable delete button for existing notes.
            if (deleteBtn) deleteBtn.disabled = false;
        // Inject HTML into the editor.
        quill.setText("");
        // Paste HTML content from the note.
        quill.clipboard.dangerouslyPasteHTML(
            sanitizeNoteHtml(note.content_html || "")
        );
        // Reset typed state because this is a programmatic load.
        hasUserTyped = false;
            // Reload list to highlight active note.
            await loadNotesList(activeTagSlug);
        } catch (error) {
            // Ignore load failures.
        }
    };

    // Apply a selected text color to the editor.
    const applyTextColor = (color, buttonEl) => {
        // Guard against missing editor.
        if (!quill) return;
        // Apply the color format to the editor.
        quill.format("color", color);
        // Update active button state.
        colorButtons.forEach((btn) => {
            btn.classList.toggle("is-active", btn === buttonEl);
        });
        // Refocus the editor for typing.
        quill.focus();
    };

    // Enter a code block at the current cursor position.
    const enterCodeBlock = () => {
        // Guard against missing editor.
        if (!quill) return;
        // Ensure the editor is focused before reading selection.
        quill.focus();
        // Read the current selection (or fall back to the last known one).
        let range = quill.getSelection();
        if (!range && lastSelection) {
            range = { index: lastSelection.index, length: lastSelection.length };
        }
        // When no selection exists, move the cursor to the end.
        if (!range) {
            const length = quill.getLength();
            range = { index: Math.max(0, length - 1), length: 0 };
        }
        // Exit if selection still fails to resolve.
        if (!range) return;
        // Restore the selection so the caret stays visible.
        quill.setSelection(range.index, range.length, "api");
        // Skip if already inside a code block.
        const formats = quill.getFormat(range);
        if (formats["code-block"]) {
            // Keep focus and selection visible when already in code mode.
            quill.focus();
            quill.setSelection(range.index, range.length, "api");
            return;
        }
        // Use a mutable index for inserting a new line.
        let index = range.index;
        // Determine line offset at the cursor.
        const lineInfo = quill.getLine(index);
        const offset = lineInfo ? lineInfo[1] : 0;
        // Insert a newline when not at the line start.
        if (offset !== 0) {
            quill.insertText(index, "\n", "user");
            index += 1;
        }
        // Clear any inline color before entering code block.
        quill.format("color", false);
        // Apply code block formatting on the current line.
        quill.formatLine(index, 1, "code-block", true);
        // Move cursor into the code block.
        quill.setSelection(index, 0, "api");
        // Ensure the editor keeps focus after the shortcut.
        quill.focus();
    };

    // Indent code block lines at the current selection.
    const indentCodeBlockRange = (range) => {
        if (!quill || !range) return;
        const indent = "    ";
        if (range.length === 0) {
            quill.insertText(range.index, indent, "user");
            quill.setSelection(range.index + indent.length, 0, "silent");
            return;
        }
        // Avoid including the next line when selection ends at its start.
        const effectiveLength = Math.max(0, range.length - 1);
        const lines = quill.getLines(range.index, effectiveLength);
        if (!lines || lines.length === 0) return;
        const lineStarts = lines.map((line) => quill.getIndex(line));
        for (let i = lineStarts.length - 1; i >= 0; i -= 1) {
            quill.insertText(lineStarts[i], indent, "user");
        }
        const firstLineStart = lineStarts[0];
        let newIndex = range.index;
        if (range.index > firstLineStart) {
            newIndex += indent.length;
        }
        const newLength = range.length + indent.length * lineStarts.length;
        quill.setSelection(newIndex, newLength, "silent");
    };

    // Remove empty paragraphs that Quill may insert around code blocks.
    const sanitizeNoteHtml = (html) => {
        if (!html) return "";
        let cleaned = html;
        // Drop empty paragraphs that appear right before code blocks.
        cleaned = cleaned.replace(
            /(?:<p>\s*(?:&nbsp;|<br\s*\/?>)\s*<\/p>\s*)+(?=<pre\b[^>]*class=["'][^"']*\bql-syntax\b[^"']*["'][^>]*>)/gi,
            ""
        );
        // Drop trailing empty paragraphs at the end.
        cleaned = cleaned.replace(
            /(?:<p>\s*(?:&nbsp;|<br\s*\/?>)\s*<\/p>\s*)+$/gi,
            ""
        );

        const legacyColorMap = new Map([
            ["rgb(255,255,255)", "var(--notes-color-contrast)"],
            ["rgba(255,255,255,1)", "var(--notes-color-contrast)"],
            ["#ffffff", "var(--notes-color-contrast)"],
            ["#fff", "var(--notes-color-contrast)"],
            ["white", "var(--notes-color-contrast)"],
            ["rgb(46,204,113)", "var(--notes-color-green)"],
            ["#2ecc71", "var(--notes-color-green)"],
            ["rgb(52,152,219)", "var(--notes-color-blue)"],
            ["#3498db", "var(--notes-color-blue)"],
            ["rgb(241,196,15)", "var(--notes-color-yellow)"],
            ["#f1c40f", "var(--notes-color-yellow)"],
            ["rgb(231,76,60)", "var(--notes-color-red)"],
            ["#e74c3c", "var(--notes-color-red)"],
        ]);

        if (typeof DOMParser !== "undefined") {
            try {
                const parser = new DOMParser();
                const documentFragment = parser.parseFromString(`<div>${cleaned}</div>`, "text/html");
                const root = documentFragment.body && documentFragment.body.firstElementChild;
                if (root) {
                    root.querySelectorAll("[style]").forEach((node) => {
                        if (node.closest("pre")) return;
                        const colorValue = String(node.style.color || "")
                            .trim()
                            .toLowerCase()
                            .replace(/\s+/g, "");
                        const replacement = legacyColorMap.get(colorValue);
                        if (replacement) {
                            node.style.color = replacement;
                        }
                    });
                    cleaned = root.innerHTML;
                }
            } catch (error) {
                // Ignore normalization failures and keep the original HTML.
            }
        }

        return cleaned;
    };

    // Format a timestamp like "April 11, 2026 4:00PM" (Notion-style).
    const formatTimestampDisplay = (dateObj) => {
        try {
            const dateFormatter = new Intl.DateTimeFormat("en-US", {
                month: "long",
                day: "numeric",
                year: "numeric",
            });
            const timeFormatter = new Intl.DateTimeFormat("en-US", {
                hour: "numeric",
                minute: "2-digit",
                hour12: true,
            });
            const datePart = dateFormatter.format(dateObj);
            const timePart = timeFormatter.format(dateObj).replace(/\s+/g, "");
            return `${datePart} ${timePart}`;
        } catch (error) {
            // Fallback for older browsers.
            return String(dateObj ? dateObj.toLocaleString() : "");
        }
    };

    // Register a custom, non-editable timestamp embed for the notes editor.
    const registerNotesTimestampBlot = () => {
        if (!window.Quill) return;
        if (window.__notesTimestampBlotRegistered) return;
        try {
            const Embed = window.Quill.import("blots/embed");
            class NotesTimestampBlot extends Embed {
                static create(value) {
                    const node = super.create();
                    const isoValue = value && value.iso ? String(value.iso) : "";
                    const displayValue = value && value.display ? String(value.display) : "";
                    if (isoValue) node.setAttribute("data-date_time_now", isoValue);
                    if (displayValue) node.setAttribute("data-display", displayValue);
                    node.setAttribute("contenteditable", "false");
                    node.textContent = displayValue || isoValue || "";
                    if (displayValue) node.setAttribute("title", displayValue);
                    return node;
                }

                static value(node) {
                    return {
                        iso: node.getAttribute("data-date_time_now") || "",
                        display: node.getAttribute("data-display") || node.textContent || "",
                    };
                }
            }
            NotesTimestampBlot.blotName = "timestamp";
            NotesTimestampBlot.tagName = "span";
            NotesTimestampBlot.className = "notes-timestamp";
            window.Quill.register(NotesTimestampBlot);
            window.__notesTimestampBlotRegistered = true;
        } catch (error) {
            // Ignore registration failures; editor will fall back to plain text.
        }
    };

    // Insert a non-editable timestamp token at the current selection.
    const insertTimestampToken = (range, source = "user") => {
        if (!quill || !range) return;
        const index = range.index || 0;
        const length = range.length || 0;
        if (length > 0) {
            quill.deleteText(index, length, source);
        }
        const now = new Date();
        const iso = String(now.toISOString() || "").replace(/Z$/, "+00:00");
        const display = formatTimestampDisplay(now);
        quill.insertEmbed(index, "timestamp", { iso, display }, source);
        // Add a trailing space so typing can continue naturally.
        quill.insertText(index + 1, " ", source);
        quill.setSelection(index + 2, 0, "silent");
        quill.focus();
    };

    // Convert a freshly typed "@" into a timestamp token when appropriate.
    const maybeConvertRecentAtToTimestamp = (delta) => {
        if (!quill) return;
        let range = quill.getSelection();
        if (!range && lastSelection) {
            range = { index: lastSelection.index, length: lastSelection.length };
        }

        let atIndex = null;
        if (range && range.length === 0) {
            const recentIndex = range.index - 1;
            const recentChar = recentIndex >= 0 ? (quill.getText(recentIndex, 1) || "") : "";
            if (recentChar === "@") {
                atIndex = recentIndex;
            }
        }

        // Fallback: Quill keyboard bindings use keyCodes, so detect single "@" inserts via delta.
        if (atIndex === null) {
            const ops = delta && Array.isArray(delta.ops) ? delta.ops : [];
            let cursor = 0;
            let insertedAtIndex = null;
            for (let i = 0; i < ops.length; i += 1) {
                const op = ops[i] || {};
                if (typeof op.retain === "number") {
                    cursor += op.retain;
                    continue;
                }
                if (typeof op.insert === "string") {
                    if (op.insert === "@") {
                        insertedAtIndex = cursor;
                        break;
                    }
                    continue;
                }
            }
            if (insertedAtIndex === null) return;
            atIndex = insertedAtIndex;
        }

        if (typeof atIndex !== "number" || atIndex < 0) return;
        const typedChar = quill.getText(atIndex, 1) || "";
        if (typedChar !== "@") return;

        const formats = quill.getFormat(atIndex, 1) || {};
        if (formats["code-block"] || formats.code) return;

        if (atIndex > 0) {
            const prevChar = quill.getText(atIndex - 1, 1) || "";
            const isWhitespace = /\s/.test(prevChar) || prevChar === "\uFFFC";
            if (!isWhitespace) return;
        }

        insertTimestampToken({ index: atIndex, length: 1 }, "api");
    };

    // Split, trim, and dedupe tag input text.
    const parseTagInput = (rawValue) => {
        if (!rawValue) return [];
        const parts = String(rawValue)
            .split(",")
            .map((text) => text.trim())
            .filter(Boolean);
        const unique = [];
        const seen = new Set();
        parts.forEach((tag) => {
            const key = tag.toLowerCase();
            if (seen.has(key)) return;
            seen.add(key);
            unique.push(tag);
        });
        return unique;
    };

    // Schedule a safe overlay refresh via the shared copy utility.
    const scheduleNotesCopyOverlayUpdate = () => {
        if (notesCopyOverlay && typeof notesCopyOverlay.scheduleUpdate === "function") {
            notesCopyOverlay.scheduleUpdate();
            return;
        }
        if (window.copyUtils && typeof window.copyUtils.refreshCodeCopyOverlays === "function") {
            window.copyUtils.refreshCodeCopyOverlays();
        }
    };

    // Create a new note on the server.
    const createNote = async (title, tags) => {
        // Guard against missing editor.
        if (!quill) return null;
        // Build payload for creation.
        const payload = {
            title: title,
            tags: Array.isArray(tags) ? tags : [],
            content_html: sanitizeNoteHtml(quill.root.innerHTML || ""),
        };
        // Send POST request to list endpoint.
        try {
            // Issue POST request with JSON payload.
            const response = await fetch(listUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "same-origin",
                body: JSON.stringify(payload),
            });
            // Parse response JSON.
            const data = await response.json();
            // Return created note payload when successful.
            return data.note || null;
        } catch (error) {
            // Return null on failure.
            return null;
        }
    };

    // Save changes for an existing note (autosave).
    const updateNote = async () => {
        // Guard against missing note ID.
        if (!currentNoteId) return;
        // Guard against missing editor.
        if (!quill) return;
        // Build detail URL for update.
        const detailUrl = buildDetailUrl(currentNoteId);
        // Build update payload.
        const payload = {
            content_html: sanitizeNoteHtml(quill.root.innerHTML || ""),
        };
        // Send POST request to update endpoint.
        try {
            // Issue POST request with JSON payload.
            await fetch(detailUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "same-origin",
                body: JSON.stringify(payload),
            });
            // Clear dirty state after save.
            isDirty = false;
        } catch (error) {
            // Keep dirty state on failure.
        }
    };

    // Schedule autosave with debounce.
    const scheduleAutosave = () => {
        // Only autosave existing notes.
        if (!currentNoteId) return;
        // Clear any existing debounce timer.
        if (autosaveTimer) window.clearTimeout(autosaveTimer);
        // Set new debounce timer.
        autosaveTimer = window.setTimeout(() => {
            // Clear timer reference.
            autosaveTimer = null;
            // Trigger update on debounce.
            updateNote();
        }, 1200);
    };

    // Delete the current note.
    const deleteCurrentNote = async () => {
        // Guard against missing note ID.
        if (!currentNoteId) return;
        // Ask for confirmation before permanent delete.
        const confirmDelete = window.confirm(
            "Delete this note? This action cannot be undone."
        );
        // Exit when the user cancels.
        if (!confirmDelete) return;
        // Build detail URL for deletion.
        const detailUrl = buildDetailUrl(currentNoteId);
        // Send DELETE request.
        try {
            // Issue DELETE request to backend.
            await fetch(detailUrl, {
                method: "DELETE",
                headers: {
                    "X-CSRFToken": getCookie("csrftoken"),
                    "X-Requested-With": "XMLHttpRequest",
                },
                credentials: "same-origin",
            });
            // Reset editor after delete.
            resetEditor();
            // Refresh the notes list.
            await loadNotesList(activeTagSlug);
        } catch (error) {
            // Ignore delete failures for now.
        }
    };

    // Initialize the Quill editor.
    const initQuill = () => {
        // Guard against missing mount element.
        if (!editorMountEl) return;
        // Guard against missing Quill dependency.
        if (!window.Quill) return;
        // Ensure the timestamp embed is registered before instantiating Quill.
        registerNotesTimestampBlot();
        // Create a new Quill instance with custom shortcuts.
        quill = new window.Quill(editorMountEl, {
            theme: "snow",
            modules: {
                toolbar: false,
                // Enable syntax highlighting for code blocks.
                syntax: true,
                keyboard: {
                    bindings: {
                        timestampNow: {
                            key: "@",
                            handler: function (range, context) {
                                // Allow literal @ inside code blocks / inline code.
                                if (context && context.format) {
                                    if (context.format["code-block"] || context.format.code) {
                                        return true;
                                    }
                                }
                                // Only trigger on a collapsed caret selection.
                                if (!range || range.length !== 0) return true;
                                // Only trigger when at line start or after whitespace.
                                if (quill && range.index > 0) {
                                    const prevChar = quill.getText(range.index - 1, 1) || "";
                                    const isWhitespace = /\s/.test(prevChar) || prevChar === "\uFFFC";
                                    if (!isWhitespace) return true;
                                }
                                insertTimestampToken(range);
                                return false;
                            },
                        },
                        heading1: {
                            key: "1",
                            shortKey: true,
                            handler: function (range) {
                                if (shortcutsDisabled()) return true;
                                this.quill.formatLine(range.index, range.length, "header", 1);
                                return false;
                            },
                        },
                        heading2: {
                            key: "2",
                            shortKey: true,
                            handler: function (range) {
                                if (shortcutsDisabled()) return true;
                                this.quill.formatLine(range.index, range.length, "header", 2);
                                return false;
                            },
                        },
                        paragraph: {
                            key: "P",
                            altKey: true,
                            handler: function () {
                                if (shortcutsDisabled()) return true;
                                this.quill.format("header", false);
                                this.quill.format("code-block", false);
                                this.quill.format("blockquote", false);
                                this.quill.format("list", false);
                                this.quill.format("code", false);
                                return false;
                            },
                        },
                        bold: {
                            key: "B",
                            shortKey: true,
                            handler: function (range, context) {
                                if (shortcutsDisabled()) return true;
                                this.quill.format("bold", !context.format.bold);
                                return false;
                            },
                        },
                        codeBlock: {
                            key: "X",
                            // shortKey: true,
                            shiftKey: true,
                            handler: function (range, context) {
                                // Skip shortcut handling on mobile.
                                if (shortcutsDisabled()) return true;
                                // Enter a code block at the cursor.
                                enterCodeBlock();
                                return false;
                            },
                        },
                        codeBlockTab: {
                            key: 9,
                            shiftKey: false,
                            format: ["code-block"],
                            handler: function (range, context) {
                                // Skip shortcut handling on mobile.
                                if (shortcutsDisabled()) return true;
                                // Only handle when inside a code block.
                                if (!context.format["code-block"]) return true;
                                indentCodeBlockRange(range);
                                return false;
                            },
                        },
                        codeBlockEnter: {
                            key: 13,
                            shiftKey: false,
                            format: ["code-block"],
                            handler: function (range, context) {
                                // Skip shortcut handling on mobile.
                                if (shortcutsDisabled()) return true;
                                // Only handle when inside a code block.
                                if (!context.format["code-block"]) return true;
                                // Remove any selected text first.
                                if (range.length > 0) {
                                    this.quill.deleteText(range.index, range.length, "user");
                                }
                                // Read the current line indentation.
                                const lineInfo = this.quill.getLine(range.index);
                                const line = lineInfo ? lineInfo[0] : null;
                                let indent = "";
                                if (line) {
                                    const lineStart = this.quill.getIndex(line);
                                    const lineText = this.quill.getText(lineStart, line.length());
                                    const match = lineText.match(/^[\t ]+/);
                                    if (match) indent = match[0];
                                }
                                this.quill.insertText(range.index, `\n${indent}`, "user");
                                this.quill.setSelection(range.index + 1 + indent.length, 0, "silent");
                                return false;
                            },
                        },
                        exitCodeBlock: {
                            key: "Enter",
                            shiftKey: true,
                            handler: function (range, context) {
                                // Skip shortcut handling on mobile.
                                if (shortcutsDisabled()) return true;
                                // Only handle exit when currently in a code block.
                                if (!context.format["code-block"]) return true;
                                // Insert a newline.
                                this.quill.insertText(range.index, "\n", "user");
                                // Remove code block formatting on the next line.
                                this.quill.formatLine(range.index + 1, 1, "code-block", false);
                                // Move cursor to the new normal line.
                                this.quill.setSelection(range.index + 1, 0, "silent");
                                return false;
                            },
                        },
                    },
                },
            },
            placeholder: "Start typing your notes here... Press Ctrl+X for a code block. Press Ctrl+1, Ctrl+2, or Ctrl+3 for headings.",
        });
        // Enable spellcheck for writing notes.
        quill.root.setAttribute("spellcheck", "true");
        // Register floating copy buttons for code blocks.
        const overlayHost = editorMountEl
            ? (editorMountEl.closest(".notes-editor-wrap") || editorMountEl.parentElement)
            : null;
        if (window.copyUtils && typeof window.copyUtils.registerCodeCopyOverlay === "function") {
            notesCopyOverlay = window.copyUtils.registerCodeCopyOverlay({
                root: quill.root,
                host: overlayHost || quill.root,
                scrollContainer: quill.root,
                codeSelector: "pre.ql-syntax",
                offsetX: 8,
                offsetY: 8,
            });
        }
        // Listen for editor changes to set dirty state and autosave.
        quill.on("text-change", function (delta, oldDelta, source) {
            // Only mark dirty when the user edits directly.
            if (source === "user") {
                // Mark the editor as dirty on change.
                isDirty = true;
                // Mark that the user has typed content.
                hasUserTyped = true;
                // Schedule autosave for existing notes.
                scheduleAutosave();
                // Replace a freshly typed "@" with a timestamp token.
                maybeConvertRecentAtToTimestamp(delta);
            }
            // Refresh overlay copy buttons after changes.
            scheduleNotesCopyOverlayUpdate();
        });
        // Track the last known selection so shortcuts can restore focus.
        quill.on("selection-change", function (range) {
            if (range) {
                lastSelection = { index: range.index, length: range.length };
            }
        });
        // Force Tab to indent only at the caret inside code blocks.
        quill.root.addEventListener("keydown", function (event) {
            if (shortcutsDisabled()) return;
            if (!quill) return;
            if (event.key !== "Tab") return;
            const range = quill.getSelection();
            if (!range) return;
            const formats = quill.getFormat(range);
            if (!formats["code-block"]) return;
            // Stop Quill's default multi-line indent handler.
            event.preventDefault();
            event.stopPropagation();
            indentCodeBlockRange(range);
        }, true);
        // Keep overlay buttons aligned while scrolling inside the editor.
        quill.root.addEventListener("scroll", scheduleNotesCopyOverlayUpdate, { passive: true });
        // Update overlay on window resize.
        window.addEventListener("resize", scheduleNotesCopyOverlayUpdate);
        // Ensure overlay is attached on init.
        scheduleNotesCopyOverlayUpdate();
    };

    // Handle opening the notes panel.
    const handleOpen = () => {
        // Open the panel UI.
        setPanelOpen(true);
        // Hide any lingering save modal.
        hideSaveModal();
        // Ensure sidebar starts closed by default.
        setSidebarOpen(false);
        // Reset editor to a blank note.
        resetEditor();
        // Load the notes list for sidebar.
        loadNotesList(activeTagSlug);
    };

    // Toggle the notes panel open/close (Alt+N shortcut).
    const toggleNotesPanel = () => {
        // Check current open state.
        const isOpen = bodyEl.classList.contains("notes-open");
        // Close when open, otherwise open.
        if (isOpen) {
            handleClose();
        } else {
            handleOpen();
        }
    };

    // Handle closing the notes panel.
    const handleClose = () => {
        // Prompt for save when a new note has content.
        if (shouldPromptSave()) {
            showSaveModal();
            return;
        }
        // Close the panel immediately.
        setPanelOpen(false);
    };

    // Handle save from the modal.
    const handleSave = async () => {
        // Guard against missing inputs.
        if (!titleInputEl) return;
        // Read title input.
        const title = titleInputEl.value.trim();
        // Validate title input.
        if (!title) {
            if (saveErrorEl) {
                saveErrorEl.textContent = "Title is required.";
                saveErrorEl.hidden = false;
            }
            return;
        }
        // Read tag input.
        const tagText = tagInputEl ? tagInputEl.value.trim() : "";
        const tags = parseTagInput(tagText);
        if (tags.length > MAX_NOTE_TAGS) {
            if (saveErrorEl) {
                saveErrorEl.textContent = `Use up to ${MAX_NOTE_TAGS} tags (comma-separated).`;
                saveErrorEl.hidden = false;
            }
            return;
        }
        // Create the note in the backend.
        const createdNote = await createNote(title, tags);
        // Handle creation failure.
        if (!createdNote) {
            if (saveErrorEl) {
                saveErrorEl.textContent = "Save failed. Try again.";
                saveErrorEl.hidden = false;
            }
            return;
        }
        // Hide the save modal.
        hideSaveModal();
        // Reset editor after saving.
        resetEditor();
        // Refresh the list to include the new note.
        await loadNotesList(activeTagSlug);
        // Close panel after saving per requirement.
        setPanelOpen(false);
        // Clear pending close flag.
    };

    // Handle exit from the modal (discard).
    const handleExit = () => {
        // Hide the modal overlay.
        hideSaveModal();
        // Reset editor state.
        resetEditor();
        // Close panel after discard.
        setPanelOpen(false);
        // Clear pending close flag.
    };

    // Handle clicks inside the notes list.
    const handleListClick = (event) => {
        // Identify tag button clicks.
        const tagBtn = event.target.closest("[data-tag-slug]");
        // Apply tag filter when tag clicked.
        if (tagBtn) {
            event.preventDefault();
            loadNotesList(tagBtn.dataset.tagSlug || "");
            return;
        }
        // Identify note item clicks.
        const noteEl = event.target.closest("[data-note-id]");
        // Exit when no note element is clicked.
        if (!noteEl) return;
        // Prevent default behavior.
        event.preventDefault();
        // Extract note ID.
        const noteId = Number(noteEl.dataset.noteId || 0);
        // Ignore invalid IDs.
        if (!noteId) return;
        // If there is an unsaved new note, prompt before switching.
        if (shouldPromptSave()) {
            showSaveModal();
            return;
        }
        // Load the selected note into the editor.
        loadNote(noteId);
    };

    // Handle keyboard activation for note items.
    const handleListKeydown = (event) => {
        // Only handle Enter or Space.
        if (event.key !== "Enter" && event.key !== " ") return;
        // Ignore key events coming from tag buttons.
        if (event.target.closest("[data-tag-slug]")) return;
        // Identify note item.
        const noteEl = event.target.closest("[data-note-id]");
        // Exit when not on a note element.
        if (!noteEl) return;
        // Prevent default scroll for spacebar.
        event.preventDefault();
        // Trigger click handler.
        noteEl.click();
    };

    // Initialize Quill editor.
    initQuill();

    // Attach open button handler.
    if (openBtn) openBtn.addEventListener("click", handleOpen);
    // Attach close button handler.
    if (closeBtn) closeBtn.addEventListener("click", handleClose);
    // Do not close on backdrop click (close only via Close button).
    // Attach delete button handler.
    if (deleteBtn) deleteBtn.addEventListener("click", deleteCurrentNote);
    // Attach sidebar toggle handler.
    if (sidebarToggleBtn) {
        sidebarToggleBtn.addEventListener("click", function () {
            setSidebarOpen(!panelEl.classList.contains("notes-sidebar-open"));
        });
    }
    // Attach clear filter handler.
    if (clearFilterBtn) {
        clearFilterBtn.addEventListener("click", function () {
            clearTagSearch();
        });
    }
    // Attach tag search handlers.
    if (tagSearchInputEl) {
        tagSearchInputEl.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                applyTagSearch();
                return;
            }
            if (event.key === "Escape") {
                event.preventDefault();
                clearTagSearch();
            }
        });
        tagSearchInputEl.addEventListener("input", function () {
            syncTagSearchClearButton();
            if (!tagSearchInputEl.value.trim() && activeTagSlug) {
                loadNotesList("");
            }
        });
    }
    if (tagSearchEffectiveClearBtn) {
        tagSearchEffectiveClearBtn.addEventListener("click", function () {
            clearTagSearch();
            if (tagSearchInputEl) tagSearchInputEl.focus();
        });
    }
    if (tagSearchActionBtn) {
        tagSearchActionBtn.addEventListener("click", function () {
            applyTagSearch();
            if (tagSearchInputEl) tagSearchInputEl.focus();
        });
    }
    // Attach list click handler.
    if (listEl) listEl.addEventListener("click", handleListClick);
    // Attach list keydown handler for accessibility.
    if (listEl) listEl.addEventListener("keydown", handleListKeydown);
    // Attach save modal save handler.
    if (saveBtn) saveBtn.addEventListener("click", handleSave);
    // Attach save modal exit handler.
    if (exitBtn) exitBtn.addEventListener("click", handleExit);
    // Attach color button handlers for text color.
    colorButtons.forEach((buttonEl) => {
        buttonEl.addEventListener("click", function () {
            // Read the color value from the data attribute.
            const colorValue = buttonEl.dataset.notesColor || "";
            // Skip when no color is provided.
            if (!colorValue) return;
            // Apply the selected color to the editor.
            applyTextColor(colorValue, buttonEl);
        });
    });
    // Close modal on Escape key.
    document.addEventListener("keydown", function (event) {
        if (event.key !== "Escape") return;
        if (!saveModalEl || saveModalEl.hidden) return;
        event.preventDefault();
        handleExit();
    });

    // Open a note directly from search params (note_id + note_q).
    const openNoteFromSearchParams = async () => {
        const params = new URLSearchParams(window.location.search);
        const noteId = Number(params.get("note_id") || 0);
        const noteQuery = (params.get("note_q") || params.get("q") || "").trim();
        if (!noteId) return;
        handleOpen();
        await loadNote(noteId);
        if (!quill || !noteQuery) return;
        const fullText = quill.getText() || "";
        const index = fullText.toLowerCase().indexOf(noteQuery.toLowerCase());
        if (index < 0) return;
        quill.focus();
        quill.setSelection(index, noteQuery.length, "api");
    };

    // Toggle notes panel with Alt+N.
    document.addEventListener("keydown", function (event) {
        // Use Alt+N without Ctrl/Shift/Meta.
        const isAltN = event.altKey
            && !event.ctrlKey
            && !event.shiftKey
            && !event.metaKey
            && String(event.key).toLowerCase() === "n";
        // Ignore non-matching keys.
        if (!isAltN) return;
        // Prevent browser default behavior.
        event.preventDefault();
        // Toggle the notes panel.
        toggleNotesPanel();
    });

    // Auto-open notes when coming from search results.
    openNoteFromSearchParams();
});
