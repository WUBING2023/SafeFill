/**
 * SafeFill ReviewUI v2 — HTML table preview editor
 * Fixed: clear old state, validate draft before save, show clear feedback
 */
(function () {
    'use strict';

    var state = { items: [], activeItem: null, activeHtml: "", showAll: false };

    var $ = function(s) { return document.querySelector(s); };
    var dom = {
        previewList: $('#preview-list'), contentPlaceholder: $('#content-placeholder'),
        contentEditor: $('#content-editor'), editorTitle: $('#editor-title'),
        editorTable: $('#editor-table'), btnSaveReview: $('#btn-save-review'),
        textboxSection: $('#textbox-section'), textboxList: $('#textbox-list'),
        saveStatus: $('#save-status'),
        btnRefresh: $('#btn-refresh'), btnToggleAll: $('#btn-toggle-all'),
        btnOldMode: $('#btn-old-mode'), toast: $('#toast'),
    };

    function showToast(msg, type) {
        if (!type) type = 'info';
        var t = dom.toast; t.textContent = msg; t.className = 'toast ' + type;
        t.classList.remove('hidden');
        setTimeout(function() { t.classList.add('hidden'); }, 5000);
    }

    // ---- API ----
    function apiGetItems() {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/api/html-items' + (state.showAll ? '?all=1' : ''));
        xhr.onload = function() {
            if (xhr.status === 200) {
                var d = JSON.parse(xhr.responseText);
                state.items = d.items || [];
                // Clear stale activeItem if not in current items
                if (state.activeItem) {
                    var stillValid = state.items.some(function(it) {
                        return it.html_file && state.activeItem && it.html_file.endsWith(state.activeItem);
                    });
                    if (!stillValid) {
                        state.activeItem = null;
                        state.activeHtml = '';
                        dom.contentEditor.style.display = 'none';
                        dom.contentPlaceholder.style.display = 'block';
                        dom.btnSaveReview.disabled = true;
                    }
                }
                renderItems();
                if (dom.btnToggleAll) {
                    dom.btnToggleAll.textContent = state.showAll ? '只看当前任务' : '显示本轮全部';
                }
                // Auto-select first item if nothing selected
                if (!state.activeItem && state.items.length > 0) {
                    var firstName = state.items[0].html_file.split('\\').pop();
                    apiGetPreview(firstName);
                }
            } else { showToast('加载预览列表失败', 'error'); }
        };
        xhr.onerror = function() { showToast('无法连接服务器', 'error'); };
        xhr.send();
    }

    function apiGetPreview(filename) {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/api/html-preview?file=' + encodeURIComponent(filename));
        xhr.onload = function() {
            if (xhr.status === 200) {
                var d = JSON.parse(xhr.responseText);
                state.activeHtml = d.html || '';
                state.activeItem = filename;
                renderEditor();
            } else { showToast('加载预览失败', 'error'); }
        };
        xhr.send();
    }

    function apiSaveReview(data, callback) {
        var xhr = new XMLHttpRequest();
        xhr.open('POST', '/api/save-html-review');
        xhr.setRequestHeader('Content-Type', 'application/json');
        xhr.onload = function() {
            try {
                var d = JSON.parse(xhr.responseText);
                callback(null, d);
            } catch(e) {
                callback('服务器返回异常: ' + xhr.responseText.substring(0, 200));
            }
        };
        xhr.onerror = function() { callback('无法连接服务器，请确认 ReviewUI 仍在运行'); };
        xhr.send(JSON.stringify(data));
    }

    // ---- Render ----
    function renderItems() {
        var list = dom.previewList;
        list.innerHTML = '';
        if (state.items.length === 0) {
            list.innerHTML = '<p class="empty-hint">暂无 HTML 预览<br>请先运行 SafeFill-FormReview</p>';
            return;
        }
        state.items.forEach(function(item) {
            var card = document.createElement('div');
            card.className = 'report-card';
            if (state.activeItem && item.html_file.endsWith(state.activeItem)) card.classList.add('active');
            var srcName = item.source_file ? item.source_file.split('\\').pop() : '?';
            card.innerHTML = '<div class="rc-name">' + srcName + '</div>' +
                '<div class="rc-stats"><span class="st-filled">已填 ' + (item.filled_count || 0) + '</span></div>';
            card.addEventListener('click', function() {
                var hname = item.html_file.split('\\').pop();
                apiGetPreview(hname);
                document.querySelectorAll('.report-card').forEach(function(el) { el.classList.remove('active'); });
                card.classList.add('active');
            });
            list.appendChild(card);
        });
    }

    function renderEditor() {
        if (!state.activeHtml) return;
        dom.contentPlaceholder.style.display = 'none';
        dom.contentEditor.style.display = 'block';

        var activeItem = findActiveItem();
        if (activeItem && activeItem.source_file) {
            dom.editorTitle.textContent = activeItem.source_file.split('\\').pop();
        }

        // Check if this is the latest task
        if (!activeItem || !activeItem.draft_file) {
            dom.editorTitle.textContent = '[WARN] 当前页面不是最新 FormReview 结果，请刷新页面';
            dom.editorTitle.style.color = '#e65100';
            dom.btnSaveReview.disabled = true;
            dom.editorTable.innerHTML = '<p style="color:#e65100">当前任务信息不完整，无法保存。请刷新页面后重试。</p>';
            return;
        }
        dom.editorTitle.style.color = '';

        // Extract tables from HTML
        var temp = document.createElement('div');
        temp.innerHTML = state.activeHtml;
        var tables = temp.querySelectorAll('table');
        var tableHtml = '';
        tables.forEach(function(t) {
            t.querySelectorAll('td').forEach(function(td) {
                td.setAttribute('contenteditable', 'true');
            });
            tableHtml += '<table style="border-collapse:collapse;width:100%;margin-bottom:12px">' + t.innerHTML + '</table>';
        });
        dom.editorTable.innerHTML = tableHtml || '<p>无表格内容</p>';
        dom.btnSaveReview.disabled = false;

        dom.editorTable.querySelectorAll('td').forEach(function(td) {
            var txt = td.textContent.trim();
            if (!txt) { td.style.background = '#fff9c4'; }
            else if (!td.style.background) { td.style.background = '#ffffff'; }
            td.style.padding = '4px 8px'; td.style.border = '1px solid #ccc';
        });

        renderTextboxFields(activeItem);
    }

    function findActiveItem() {
        if (!state.activeItem) return null;
        return state.items.find(function(it) { return it.html_file.endsWith(state.activeItem); }) || null;
    }

    // ---- Textbox fields ----
    function renderTextboxFields(activeItem) {
        // For now, show hint that textbox info is in the Word draft
        dom.textboxSection.style.display = 'block';
        dom.textboxList.innerHTML = '<p style="color:#888;font-size:13px;margin:0">' +
            '文本框字段已写入草稿 Word 文件，请在草稿中检查。点击保存后将记录到 review_result。</p>';
    }

    // ---- Save ----
    function saveReview() {
        var activeItem = findActiveItem();
        if (!activeItem) {
            showToast('未找到当前任务，请刷新页面', 'error');
            return;
        }
        if (!activeItem.draft_file) {
            showToast('当前任务 draft_file 不完整，请刷新页面', 'error');
            dom.btnSaveReview.disabled = true;
            return;
        }

        // Build tables array
        var tables = [];
        dom.editorTable.querySelectorAll('table').forEach(function(t, ti) {
            var rows = [];
            t.querySelectorAll('tr').forEach(function(r) {
                var cells = [];
                r.querySelectorAll('td').forEach(function(c) { cells.push(c.textContent.trim()); });
                rows.push(cells);
            });
            tables.push({ table_index: ti + 1, rows: rows });
        });

        if (!tables.length) {
            showToast('未找到表格内容，无法保存', 'error');
            return;
        }

        // Disable button + show saving state
        dom.btnSaveReview.disabled = true;
        dom.btnSaveReview.textContent = '保存中...';

        var payload = {
            source_file: activeItem.source_file || '',
            draft_file: activeItem.draft_file,
            html_file: activeItem.html_file || '',
            tables: tables,
            textbox_fields: [],
            confirmed_by_user: true,
        };

        console.log('[SafeFill] Saving review:', {
            draft: payload.draft_file,
            tables: payload.tables.length,
            html: payload.html_file.split('\\').pop()
        });

        apiSaveReview(payload, function(err, resp) {
            dom.btnSaveReview.disabled = false;
            dom.btnSaveReview.textContent = '保存检查结果';

            if (err) {
                dom.saveStatus.innerHTML = '<div class="save-msg save-error">保存失败: ' + err + '</div>';
                showToast('保存失败', 'error');
                return;
            }
            if (resp && resp.ok) {
                dom.saveStatus.innerHTML = '<div class="save-msg save-success">已保存检查结果: ' + (resp.file || 'OK') + '。下一步: 回到 ControlCenter 点击【导出最终文件】。</div>';
                showToast('保存成功', 'success');
                // Verify server still alive
                fetch('/api/health').catch(function() {
                    dom.saveStatus.innerHTML += '<div class="save-msg save-error">保存成功，但 ReviewUI 服务可能已停止。</div>';
                });
            } else {
                dom.saveStatus.innerHTML = '<div class="save-msg save-error">保存失败: ' + (resp ? resp.error : '未知错误') + '</div>';
                showToast('保存失败', 'error');
            }
        });
    }

    // ---- Events ----
    dom.btnRefresh.addEventListener('click', function() {
        state.activeItem = null; state.activeHtml = '';
        dom.contentEditor.style.display = 'none';
        dom.contentPlaceholder.style.display = 'block';
        dom.btnSaveReview.disabled = true;
        apiGetItems();
    });
    if (dom.btnToggleAll) {
        dom.btnToggleAll.addEventListener('click', function() {
            state.showAll = !state.showAll;
            state.activeItem = null; state.activeHtml = '';
            apiGetItems();
        });
    }
    dom.btnSaveReview.addEventListener('click', saveReview);
    dom.btnOldMode.addEventListener('click', function() {
        window.location.href = '/index_old.html';
    });

    // ---- Init ----
    apiGetItems();
})();
