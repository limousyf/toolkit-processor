// Toolkit Processor App

// ==================== GLOBALS ====================
let templates = [];
let toolkits = [];
let currentToolkitId = null;

// ROI colors - shared between canvas and tool list
const ROI_COLORS = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6'];

// Template editor state
let templateState = {
    image: null,
    imageFile: null,  // The actual file to upload
    imageWidth: 0,
    imageHeight: 0,
    zoom: 1,
    tools: [],
    selectedIndex: -1,
    isDrawing: false,
    drawStart: null,
    currentRect: null,
    editingIndex: -1,
    editingTemplateId: null  // null = creating, string = editing
};

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    setupNavigation();
    setupTemplateEditor();
    setupToolkitCreation();
    setupCheckin();
    loadDashboard();
});

// ==================== NAVIGATION ====================
function setupNavigation() {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            showPage(link.dataset.page);
        });
    });
}

function showPage(pageName) {
    // Update nav
    document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
    document.querySelector(`.nav-link[data-page="${pageName}"]`)?.classList.add('active');

    // Update pages
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`${pageName}-page`)?.classList.add('active');

    // Load page data
    if (pageName === 'dashboard') loadDashboard();
    else if (pageName === 'templates') loadTemplates();
    else if (pageName === 'toolkits') loadToolkits();
    else if (pageName === 'checkin') loadCheckinPage();
}

// ==================== DASHBOARD ====================
async function loadDashboard() {
    try {
        const [statsRes, toolkitsRes] = await Promise.all([
            fetch('/api/dashboard/stats'),
            fetch('/api/toolkits')
        ]);

        const stats = await statsRes.json();
        toolkits = (await toolkitsRes.json()).toolkits;

        // Render stats
        document.getElementById('statsGrid').innerHTML = `
            <div class="stat-card"><div class="value">${stats.total_toolkits}</div><div class="label">Total Toolkits</div></div>
            <div class="stat-card success"><div class="value">${stats.checked_in}</div><div class="label">Checked In</div></div>
            <div class="stat-card"><div class="value">${stats.checked_out}</div><div class="label">Checked Out</div></div>
            <div class="stat-card danger"><div class="value">${stats.incomplete}</div><div class="label">Incomplete</div></div>
            <div class="stat-card warning"><div class="value">${stats.never_checked}</div><div class="label">Never Checked</div></div>
            <div class="stat-card"><div class="value">${stats.total_templates}</div><div class="label">Templates</div></div>
        `;

        // Render toolkit table
        const tbody = document.getElementById('dashboardToolkitBody');
        const empty = document.getElementById('dashboardEmpty');

        if (toolkits.length === 0) {
            tbody.innerHTML = '';
            empty.style.display = 'block';
        } else {
            empty.style.display = 'none';
            tbody.innerHTML = toolkits.map(t => {
                // Determine action button based on status
                let actionBtn = '';
                if (t.status === 'checked_in') {
                    actionBtn = `<button class="btn btn-small btn-secondary" onclick="checkoutToolkit('${t.toolkit_id}')">Check Out</button>`;
                } else if (t.status === 'checked_out') {
                    actionBtn = `<button class="btn btn-small btn-primary" onclick="goToCheckin('${t.toolkit_id}')">Check In</button>`;
                } else if (t.status === 'incomplete') {
                    actionBtn = `<button class="btn btn-small btn-danger" onclick="goToCheckin('${t.toolkit_id}')">Re-verify</button>`;
                } else {
                    actionBtn = `<button class="btn btn-small btn-primary" onclick="goToCheckin('${t.toolkit_id}')">Check In</button>`;
                }
                return `
                <tr>
                    <td><strong>${t.toolkit_id}</strong></td>
                    <td>${t.name}</td>
                    <td>${t.template_id}</td>
                    <td><span class="status-badge ${t.status}">${formatStatus(t.status)}</span></td>
                    <td>${t.last_checkin ? formatDate(t.last_checkin) : '-'}</td>
                    <td>
                        <button class="btn btn-small btn-secondary" onclick="viewToolkitDetails('${t.toolkit_id}')">View</button>
                        ${actionBtn}
                    </td>
                </tr>
            `}).join('');
        }
    } catch (err) {
        console.error('Failed to load dashboard:', err);
    }
}

// ==================== TEMPLATES ====================
async function loadTemplates() {
    try {
        const res = await fetch('/api/templates');
        templates = (await res.json()).templates;

        const grid = document.getElementById('templateGrid');
        const empty = document.getElementById('templatesEmpty');

        if (templates.length === 0) {
            grid.innerHTML = '';
            empty.style.display = 'block';
        } else {
            empty.style.display = 'none';
            grid.innerHTML = templates.map(t => `
                <div class="template-card">
                    <h4>${t.name}</h4>
                    <div class="meta">${t.tools.length} tools | ID: ${t.template_id}</div>
                    <div class="actions">
                        <button class="btn btn-small btn-primary" onclick="editTemplate('${t.template_id}')">Edit</button>
                        <button class="btn btn-small btn-danger" onclick="deleteTemplate('${t.template_id}')">Delete</button>
                    </div>
                </div>
            `).join('');
        }
    } catch (err) {
        console.error('Failed to load templates:', err);
    }
}

function setupTemplateEditor() {
    document.getElementById('createTemplateBtn').addEventListener('click', openTemplateEditor);
    document.getElementById('templateImageInput').addEventListener('change', handleTemplateImage);
    document.getElementById('toolForm').addEventListener('submit', saveToolInTemplate);

    const canvas = document.getElementById('templateCanvas');
    canvas.addEventListener('mousedown', handleCanvasMouseDown);
    canvas.addEventListener('mousemove', handleCanvasMouseMove);
    canvas.addEventListener('mouseup', handleCanvasMouseUp);
    canvas.addEventListener('mouseleave', handleCanvasMouseUp);
}

function openTemplateEditor() {
    // Reset state for new template
    templateState = {
        image: null, imageWidth: 0, imageHeight: 0, zoom: 1,
        tools: [], selectedIndex: -1, isDrawing: false,
        drawStart: null, currentRect: null, editingIndex: -1,
        editingTemplateId: null
    };

    document.getElementById('templateEditorTitle').textContent = 'Create Template';
    document.getElementById('templateId').value = '';
    document.getElementById('templateId').disabled = false;
    document.getElementById('templateName').value = '';
    document.getElementById('templateDesc').value = '';
    document.getElementById('templatePlaceholder').style.display = 'flex';
    document.getElementById('canvasWrapper').style.display = 'none';
    document.getElementById('canvasControls').style.display = 'none';
    document.getElementById('templateImageInput').style.display = 'block';
    document.getElementById('templateImageInput').value = '';

    renderTemplateTools();

    // Show full-screen editor
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById('template-editor-page').classList.add('active');
}

async function editTemplate(templateId) {
    showLoading('Loading template...');

    try {
        const res = await fetch(`/api/templates/${templateId}`);
        if (!res.ok) throw new Error('Template not found');

        const template = await res.json();

        // Set state for editing
        templateState = {
            image: null, imageFile: null, imageWidth: template.image_width || 0, imageHeight: template.image_height || 0, zoom: 1,
            tools: template.tools.map(t => ({
                tool_id: t.tool_id,
                name: t.name,
                description: t.description,
                slot_index: t.slot_index,
                roi: t.roi
            })),
            selectedIndex: -1, isDrawing: false,
            drawStart: null, currentRect: null, editingIndex: -1,
            editingTemplateId: templateId
        };

        document.getElementById('templateEditorTitle').textContent = 'Edit Template';
        document.getElementById('templateId').value = template.template_id;
        document.getElementById('templateId').disabled = true;  // Can't change ID when editing
        document.getElementById('templateName').value = template.name;
        document.getElementById('templateDesc').value = template.description || '';

        // Check if the template has a saved image
        const hasImageRes = await fetch(`/api/templates/${templateId}/has-image`);
        const { has_image } = await hasImageRes.json();

        if (has_image) {
            // Load the saved image
            const img = new Image();
            img.onload = () => {
                templateState.image = img;
                templateState.imageWidth = img.width;
                templateState.imageHeight = img.height;

                document.getElementById('templatePlaceholder').style.display = 'none';
                document.getElementById('canvasWrapper').style.display = 'block';
                document.getElementById('canvasControls').style.display = 'flex';
                document.getElementById('templateImageInput').style.display = 'none';

                fitTemplate();
            };
            img.src = `/api/templates/${templateId}/image?t=${Date.now()}`;  // Cache bust
        } else {
            // No saved image, show upload placeholder
            document.getElementById('templatePlaceholder').style.display = 'flex';
            document.getElementById('templatePlaceholder').innerHTML = `
                <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="3" y="3" width="18" height="18" rx="2"></rect>
                    <circle cx="8.5" cy="8.5" r="1.5"></circle>
                    <polyline points="21 15 16 10 5 21"></polyline>
                </svg>
                <p>Upload reference image</p>
                <small>Upload an image to view and edit tool positions</small>
            `;
            document.getElementById('canvasWrapper').style.display = 'none';
            document.getElementById('canvasControls').style.display = 'none';
        }
        document.getElementById('templateImageInput').style.display = 'block';
        document.getElementById('templateImageInput').value = '';

        renderTemplateTools();

        // Show full-screen editor
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.getElementById('template-editor-page').classList.add('active');
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    } finally {
        hideLoading();
    }
}

function closeTemplateEditor() {
    document.getElementById('template-editor-page').classList.remove('active');
    showPage('templates');
}

function triggerImageReupload() {
    // Show the file input and trigger click
    const input = document.getElementById('templateImageInput');
    input.style.display = 'block';
    input.click();
}

function handleTemplateImage(e) {
    const file = e.target.files[0];
    if (!file) return;

    templateState.imageFile = file;  // Save the file for upload

    const reader = new FileReader();
    reader.onload = (event) => {
        const img = new Image();
        img.onload = () => {
            templateState.image = img;
            templateState.imageWidth = img.width;
            templateState.imageHeight = img.height;

            document.getElementById('templatePlaceholder').style.display = 'none';
            document.getElementById('canvasWrapper').style.display = 'block';
            document.getElementById('canvasControls').style.display = 'flex';
            document.getElementById('templateImageInput').style.display = 'none';

            fitTemplate();
        };
        img.src = event.target.result;
    };
    reader.readAsDataURL(file);
}

function fitTemplate() {
    const container = document.getElementById('canvasWrapper');
    const maxW = container.clientWidth - 20;
    const maxH = container.clientHeight - 20;
    const scale = Math.min(maxW / templateState.imageWidth, maxH / templateState.imageHeight, 1);
    templateState.zoom = scale;
    document.getElementById('templateZoomLevel').textContent = `${Math.round(scale * 100)}%`;
    redrawTemplateCanvas();
}

function zoomTemplate(delta) {
    templateState.zoom = Math.max(0.1, Math.min(3, templateState.zoom + delta));
    document.getElementById('templateZoomLevel').textContent = `${Math.round(templateState.zoom * 100)}%`;
    redrawTemplateCanvas();
}

function redrawTemplateCanvas() {
    if (!templateState.image) return;

    const canvas = document.getElementById('templateCanvas');
    const ctx = canvas.getContext('2d');
    const z = templateState.zoom;

    canvas.width = templateState.imageWidth * z;
    canvas.height = templateState.imageHeight * z;

    ctx.drawImage(templateState.image, 0, 0, canvas.width, canvas.height);

    // Draw ROIs
    templateState.tools.forEach((tool, i) => {
        if (tool.roi) {
            const selected = i === templateState.selectedIndex;
            const color = ROI_COLORS[i % ROI_COLORS.length];

            ctx.strokeStyle = selected ? '#2563eb' : color;
            ctx.lineWidth = selected ? 3 : 2;
            ctx.strokeRect(tool.roi.x * z, tool.roi.y * z, tool.roi.width * z, tool.roi.height * z);

            if (selected) {
                ctx.fillStyle = 'rgba(37, 99, 235, 0.1)';
                ctx.fillRect(tool.roi.x * z, tool.roi.y * z, tool.roi.width * z, tool.roi.height * z);
            }

            // Label
            ctx.fillStyle = selected ? '#2563eb' : color;
            const label = `${i + 1}: ${tool.name}`;
            ctx.font = `${Math.max(12, 14 * z)}px sans-serif`;
            const textW = ctx.measureText(label).width;
            ctx.fillRect(tool.roi.x * z, tool.roi.y * z - 18 * z, textW + 8, 18 * z);
            ctx.fillStyle = '#fff';
            ctx.fillText(label, tool.roi.x * z + 4, tool.roi.y * z - 4 * z);
        }
    });

    // Draw current rect
    if (templateState.currentRect) {
        ctx.strokeStyle = '#2563eb';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(
            templateState.currentRect.x * z,
            templateState.currentRect.y * z,
            templateState.currentRect.width * z,
            templateState.currentRect.height * z
        );
        ctx.setLineDash([]);
    }
}

function getCanvasCoords(e) {
    const canvas = document.getElementById('templateCanvas');
    const rect = canvas.getBoundingClientRect();
    return {
        x: Math.round((e.clientX - rect.left) / templateState.zoom),
        y: Math.round((e.clientY - rect.top) / templateState.zoom)
    };
}

function handleCanvasMouseDown(e) {
    if (templateState.selectedIndex < 0) {
        showToast('Please add and select a tool first', 'warning');
        return;
    }

    const coords = getCanvasCoords(e);
    templateState.isDrawing = true;
    templateState.drawStart = coords;
    templateState.currentRect = { x: coords.x, y: coords.y, width: 0, height: 0 };
}

function handleCanvasMouseMove(e) {
    if (!templateState.isDrawing) return;

    const coords = getCanvasCoords(e);
    templateState.currentRect = {
        x: Math.min(templateState.drawStart.x, coords.x),
        y: Math.min(templateState.drawStart.y, coords.y),
        width: Math.abs(coords.x - templateState.drawStart.x),
        height: Math.abs(coords.y - templateState.drawStart.y)
    };
    redrawTemplateCanvas();
}

function handleCanvasMouseUp(e) {
    if (!templateState.isDrawing) return;
    templateState.isDrawing = false;

    if (templateState.currentRect && templateState.currentRect.width > 10 && templateState.currentRect.height > 10) {
        templateState.tools[templateState.selectedIndex].roi = { ...templateState.currentRect };
        renderTemplateTools();
    }

    templateState.currentRect = null;
    redrawTemplateCanvas();
}

function addTemplateTool() {
    templateState.editingIndex = -1;
    document.getElementById('toolModalTitle').textContent = 'Add Tool';
    document.getElementById('toolIdInput').value = '';
    document.getElementById('toolNameInput').value = '';
    document.getElementById('toolDescInput').value = '';
    document.getElementById('toolRoiText').textContent = 'Draw on image after saving';
    document.getElementById('toolModal').classList.add('active');
}

function editTemplateTool(index) {
    templateState.editingIndex = index;
    const tool = templateState.tools[index];
    document.getElementById('toolModalTitle').textContent = 'Edit Tool';
    document.getElementById('toolIdInput').value = tool.tool_id;
    document.getElementById('toolNameInput').value = tool.name;
    document.getElementById('toolDescInput').value = tool.description || '';
    document.getElementById('toolRoiText').textContent = tool.roi
        ? `(${tool.roi.x}, ${tool.roi.y}) ${tool.roi.width}x${tool.roi.height}`
        : 'Not set';
    document.getElementById('toolModal').classList.add('active');
}

function closeToolModal() {
    document.getElementById('toolModal').classList.remove('active');
}

function saveToolInTemplate(e) {
    e.preventDefault();

    const toolId = document.getElementById('toolIdInput').value.trim();
    const toolName = document.getElementById('toolNameInput').value.trim();
    const toolDesc = document.getElementById('toolDescInput').value.trim();

    if (templateState.editingIndex >= 0) {
        templateState.tools[templateState.editingIndex].tool_id = toolId;
        templateState.tools[templateState.editingIndex].name = toolName;
        templateState.tools[templateState.editingIndex].description = toolDesc;
    } else {
        templateState.tools.push({
            tool_id: toolId,
            name: toolName,
            description: toolDesc,
            slot_index: templateState.tools.length + 1,
            roi: null
        });
        templateState.selectedIndex = templateState.tools.length - 1;
    }

    renderTemplateTools();
    redrawTemplateCanvas();
    closeToolModal();
}

function selectTemplateTool(index) {
    templateState.selectedIndex = index;
    renderTemplateTools();
    redrawTemplateCanvas();
}

function deleteTemplateTool(index) {
    if (confirm(`Delete ${templateState.tools[index].name}?`)) {
        templateState.tools.splice(index, 1);
        templateState.tools.forEach((t, i) => t.slot_index = i + 1);
        if (templateState.selectedIndex >= templateState.tools.length) {
            templateState.selectedIndex = templateState.tools.length - 1;
        }
        renderTemplateTools();
        redrawTemplateCanvas();
    }
}

function renderTemplateTools() {
    document.getElementById('toolCount').textContent = templateState.tools.length;
    const list = document.getElementById('templateToolsList');

    if (templateState.tools.length === 0) {
        list.innerHTML = '<p class="empty-state" style="padding:1rem;">No tools added</p>';
        return;
    }

    list.innerHTML = templateState.tools.map((tool, i) => {
        const hasRoi = tool.roi !== null;
        const selected = i === templateState.selectedIndex;
        const color = ROI_COLORS[i % ROI_COLORS.length];
        return `
            <div class="tool-item-config ${hasRoi ? 'has-roi' : 'no-roi'} ${selected ? 'selected' : ''}" onclick="selectTemplateTool(${i})" style="border-left: 4px solid ${color};">
                <div class="tool-item-color" style="background-color: ${color};"></div>
                <div class="tool-item-info">
                    <div class="tool-item-name">${i + 1}. ${tool.name}</div>
                    <div class="tool-item-roi">${hasRoi ? `ROI: (${tool.roi.x}, ${tool.roi.y}) ${tool.roi.width}x${tool.roi.height}` : 'No ROI - select and draw'}</div>
                </div>
                <div class="tool-item-actions">
                    <button type="button" class="btn btn-small btn-secondary" onclick="event.stopPropagation(); editTemplateTool(${i})">Edit</button>
                    <button type="button" class="btn btn-small btn-danger" onclick="event.stopPropagation(); deleteTemplateTool(${i})">X</button>
                </div>
            </div>
        `;
    }).join('');
}

async function saveTemplateFromEditor() {
    const templateId = document.getElementById('templateId').value.trim();
    const name = document.getElementById('templateName').value.trim();
    const desc = document.getElementById('templateDesc').value.trim();

    if (!templateId || !name) {
        showToast('Template ID and Name are required', 'warning');
        return;
    }

    if (templateState.tools.length === 0) {
        showToast('Add at least one tool', 'warning');
        return;
    }

    const missingRoi = templateState.tools.filter(t => !t.roi);
    if (missingRoi.length > 0) {
        showToast(`These tools need ROIs: ${missingRoi.map(t => t.name).join(', ')}`, 'warning');
        return;
    }

    showLoading('Saving template...');

    try {
        const isEditing = templateState.editingTemplateId !== null;

        const templateData = {
            template_id: templateId,
            name: name,
            description: desc || null,
            foam_color: 'dark_grey',
            image_width: templateState.imageWidth || null,
            image_height: templateState.imageHeight || null,
            tools: templateState.tools
        };

        let res;
        if (isEditing) {
            // Update existing template
            res = await fetch(`/api/templates/${templateId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(templateData)
            });
        } else {
            // Create new template
            res = await fetch('/api/templates', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(templateData)
            });
        }

        if (!res.ok) throw new Error((await res.json()).detail);

        // Upload image if we have one
        if (templateState.imageFile) {
            const formData = new FormData();
            formData.append('file', templateState.imageFile);
            await fetch(`/api/templates/${templateId}/image`, {
                method: 'POST',
                body: formData
            });
        }

        showToast(isEditing ? 'Template updated!' : 'Template saved!', 'success');
        closeTemplateEditor();
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    } finally {
        hideLoading();
    }
}

async function deleteTemplate(id) {
    if (!confirm(`Delete template "${id}"?`)) return;

    try {
        await fetch(`/api/templates/${id}`, { method: 'DELETE' });
        showToast('Template deleted', 'success');
        loadTemplates();
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    }
}

// ==================== TOOLKITS ====================
async function loadToolkits() {
    try {
        const [toolkitsRes, templatesRes] = await Promise.all([
            fetch('/api/toolkits'),
            fetch('/api/templates')
        ]);

        toolkits = (await toolkitsRes.json()).toolkits;
        templates = (await templatesRes.json()).templates;

        const tbody = document.getElementById('toolkitsBody');
        const empty = document.getElementById('toolkitsEmpty');

        if (toolkits.length === 0) {
            tbody.innerHTML = '';
            empty.style.display = 'block';
        } else {
            empty.style.display = 'none';
            tbody.innerHTML = toolkits.map(t => {
                const present = t.tool_states.filter(ts => ts.status === 'present').length;
                const total = t.tool_states.length;
                return `
                    <tr>
                        <td><strong>${t.toolkit_id}</strong></td>
                        <td>${t.name}</td>
                        <td>${t.template_id}</td>
                        <td>${t.location || '-'}</td>
                        <td><span class="status-badge ${t.status}">${formatStatus(t.status)}</span></td>
                        <td>${present}/${total}</td>
                        <td>
                            <button class="btn btn-small btn-secondary" onclick="viewToolkitDetails('${t.toolkit_id}')">Details</button>
                            <button class="btn btn-small btn-primary" onclick="goToCheckin('${t.toolkit_id}')">Check In</button>
                            <button class="btn btn-small btn-danger" onclick="deleteToolkit('${t.toolkit_id}')">Delete</button>
                        </td>
                    </tr>
                `;
            }).join('');
        }
    } catch (err) {
        console.error('Failed to load toolkits:', err);
    }
}

function setupToolkitCreation() {
    document.getElementById('createToolkitBtn').addEventListener('click', openCreateToolkitModal);
    document.getElementById('createToolkitForm').addEventListener('submit', createToolkit);
}

async function openCreateToolkitModal() {
    // Load templates for dropdown
    try {
        const res = await fetch('/api/templates');
        templates = (await res.json()).templates;

        const select = document.getElementById('newToolkitTemplate');
        select.innerHTML = '<option value="">Select a template...</option>' +
            templates.map(t => `<option value="${t.template_id}">${t.name} (${t.tools.length} tools)</option>`).join('');

        document.getElementById('newToolkitId').value = '';
        document.getElementById('newToolkitName').value = '';
        document.getElementById('newToolkitLocation').value = '';
        document.getElementById('createToolkitModal').classList.add('active');
    } catch (err) {
        showToast('Failed to load templates', 'error');
    }
}

function closeCreateToolkitModal() {
    document.getElementById('createToolkitModal').classList.remove('active');
}

async function createToolkit(e) {
    e.preventDefault();

    const data = {
        toolkit_id: document.getElementById('newToolkitId').value.trim(),
        template_id: document.getElementById('newToolkitTemplate').value,
        name: document.getElementById('newToolkitName').value.trim(),
        location: document.getElementById('newToolkitLocation').value.trim() || null
    };

    showLoading('Creating toolkit...');

    try {
        const res = await fetch('/api/toolkits', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        if (!res.ok) throw new Error((await res.json()).detail);

        showToast('Toolkit created!', 'success');
        closeCreateToolkitModal();
        loadToolkits();
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    } finally {
        hideLoading();
    }
}

async function deleteToolkit(id) {
    if (!confirm(`Delete toolkit "${id}"? This will also delete all check-in history.`)) return;

    try {
        const res = await fetch(`/api/toolkits/${id}`, { method: 'DELETE' });
        if (!res.ok) throw new Error((await res.json()).detail);

        showToast('Toolkit deleted', 'success');

        // Reload current page data
        const activePage = document.querySelector('.page.active');
        if (activePage && activePage.id === 'dashboard-page') {
            loadDashboard();
        } else if (activePage && activePage.id === 'toolkits-page') {
            loadToolkits();
        } else if (activePage && activePage.id === 'details-page') {
            showPage('toolkits');
        }
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    }
}

// ==================== TOOLKIT DETAILS ====================
async function viewToolkitDetails(id) {
    currentToolkitId = id;
    showLoading('Loading details...');

    try {
        const [toolkitRes, historyRes] = await Promise.all([
            fetch(`/api/toolkits/${id}`),
            fetch(`/api/toolkits/${id}/history?limit=5`)
        ]);

        const { toolkit, template } = await toolkitRes.json();
        const history = await historyRes.json();

        document.getElementById('detailsTitle').textContent = toolkit.name;
        document.getElementById('detailsSubtitle').textContent = `ID: ${toolkit.toolkit_id} | Template: ${toolkit.template_id}`;

        // Status
        const statusDisplay = document.getElementById('detailsStatus');
        statusDisplay.className = `status-display ${toolkit.status}`;
        statusDisplay.textContent = formatStatus(toolkit.status);

        // Meta
        document.getElementById('detailsMeta').innerHTML = `
            <p><strong>Location:</strong> ${toolkit.location || 'Not set'}</p>
            <p><strong>Last Check-in:</strong> ${toolkit.last_checkin ? formatDate(toolkit.last_checkin) : 'Never'}</p>
            <p><strong>Last Check-out:</strong> ${toolkit.last_checkout ? formatDate(toolkit.last_checkout) : 'Never'}</p>
        `;

        // Tool status list
        document.getElementById('detailsToolList').innerHTML = toolkit.tool_states.map(ts => `
            <div class="tool-status-item ${ts.status}">
                <span>${ts.name}</span>
                <span class="status-badge ${ts.status}">${ts.status}</span>
            </div>
        `).join('');

        // History
        document.getElementById('detailsHistory').innerHTML = history.length === 0
            ? '<p class="empty-state">No check-in history</p>'
            : history.map(h => `
                <div class="history-item">
                    <div>
                        <strong>${formatDate(h.timestamp)}</strong>
                        <span class="status-badge ${h.status}">${formatStatus(h.status)}</span>
                    </div>
                    <div>${h.summary.present}/${h.summary.total_tools} present</div>
                </div>
            `).join('');

        // Button handlers
        document.getElementById('detailsCheckinBtn').onclick = () => goToCheckin(id);
        document.getElementById('detailsCheckoutBtn').onclick = () => checkoutToolkit(id, true);
        document.getElementById('detailsDeleteBtn').onclick = () => deleteToolkit(id);

        showPage('details');
    } catch (err) {
        showToast(`Error loading details: ${err.message}`, 'error');
    } finally {
        hideLoading();
    }
}

async function checkoutToolkit(id, returnToDetails = false) {
    if (!confirm('Mark this toolkit as checked out?')) return;

    try {
        const formData = new FormData();
        await fetch(`/api/toolkits/${id}/checkout`, {
            method: 'POST',
            body: formData
        });

        if (returnToDetails) {
            viewToolkitDetails(id);
        } else {
            // Reload current page data
            const activePage = document.querySelector('.page.active');
            if (activePage && activePage.id === 'dashboard-page') {
                loadDashboard();
            } else if (activePage && activePage.id === 'toolkits-page') {
                loadToolkits();
            }
        }
    } catch (err) {
        showToast(`Error: ${err.message}`, 'error');
    }
}

// ==================== CHECK-IN ====================
function setupCheckin() {
    document.getElementById('checkinForm').addEventListener('submit', performCheckin);
    document.getElementById('checkinImageInput').addEventListener('change', handleCheckinImage);
}

async function loadCheckinPage() {
    try {
        const res = await fetch('/api/toolkits');
        toolkits = (await res.json()).toolkits;

        const select = document.getElementById('checkinToolkitSelect');
        select.innerHTML = '<option value="">Select a toolkit...</option>' +
            toolkits.map(t => `<option value="${t.toolkit_id}">${t.name} (${t.toolkit_id})</option>`).join('');

        // Reset form
        document.getElementById('checkinImageInput').value = '';
        document.getElementById('checkinPlaceholder').style.display = 'flex';
        document.getElementById('checkinPreview').style.display = 'none';
        document.getElementById('checkinResultCard').style.display = 'none';
    } catch (err) {
        console.error('Failed to load toolkits:', err);
    }
}

function goToCheckin(toolkitId) {
    showPage('checkin');
    setTimeout(() => {
        document.getElementById('checkinToolkitSelect').value = toolkitId;
    }, 100);
}

function handleCheckinImage(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
        document.getElementById('checkinPreview').src = event.target.result;
        document.getElementById('checkinPreview').style.display = 'block';
        document.getElementById('checkinPlaceholder').style.display = 'none';
    };
    reader.readAsDataURL(file);
}

async function performCheckin(e) {
    e.preventDefault();

    const toolkitId = document.getElementById('checkinToolkitSelect').value;
    const file = document.getElementById('checkinImageInput').files[0];

    if (!toolkitId || !file) {
        showToast('Select a toolkit and upload an image', 'warning');
        return;
    }

    showLoading('Analyzing toolkit...');

    try {
        const formData = new FormData();
        formData.append('file', file);

        const res = await fetch(`/api/toolkits/${toolkitId}/checkin`, {
            method: 'POST',
            body: formData
        });

        if (!res.ok) throw new Error((await res.json()).detail);

        const result = await res.json();
        displayCheckinResult(result);
    } catch (err) {
        showToast(`Check-in failed: ${err.message}`, 'error');
    } finally {
        hideLoading();
    }
}

function displayCheckinResult(result) {
    document.getElementById('checkinResultCard').style.display = 'block';

    // Status banner
    const banner = document.getElementById('checkinStatusBanner');
    const isComplete = result.status === 'checked_in';
    banner.className = `checkin-status-banner ${isComplete ? 'complete' : 'incomplete'}`;
    banner.textContent = isComplete ? 'Toolkit Complete' : `Incomplete - ${result.summary.missing} Missing`;

    // Summary
    document.getElementById('checkinSummary').innerHTML = `
        <div class="stat present"><div class="num">${result.summary.present}</div><div>Present</div></div>
        <div class="stat missing"><div class="num">${result.summary.missing}</div><div>Missing</div></div>
        <div class="stat uncertain"><div class="num">${result.summary.uncertain}</div><div>Uncertain</div></div>
    `;

    // Tool lists
    const missing = result.tools.filter(t => t.status === 'missing');
    const uncertain = result.tools.filter(t => t.status === 'uncertain');
    const present = result.tools.filter(t => t.status === 'present');

    const missingSection = document.getElementById('checkinMissing');
    const uncertainSection = document.getElementById('checkinUncertain');
    const presentSection = document.getElementById('checkinPresent');

    missingSection.style.display = missing.length ? 'block' : 'none';
    uncertainSection.style.display = uncertain.length ? 'block' : 'none';
    presentSection.style.display = present.length ? 'block' : 'none';

    document.getElementById('checkinMissingList').innerHTML = missing.map(t => formatToolWithDebug(t)).join('');
    document.getElementById('checkinUncertainList').innerHTML = uncertain.map(t => formatToolWithDebug(t)).join('');
    document.getElementById('checkinPresentList').innerHTML = present.map(t => formatToolWithDebug(t)).join('');

    // Image
    if (result.image_annotated) {
        document.getElementById('checkinResultImage').src = result.image_annotated;
    }

    document.getElementById('checkinResultCard').scrollIntoView({ behavior: 'smooth' });
}

// ==================== UTILITIES ====================
function showLoading(text = 'Loading...') {
    document.getElementById('loadingText').textContent = text;
    document.getElementById('loadingOverlay').style.display = 'flex';
}

function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

function formatStatus(status) {
    const map = {
        'checked_in': 'Checked In',
        'checked_out': 'Checked Out',
        'incomplete': 'Incomplete',
        'never_checked': 'Never Checked'
    };
    return map[status] || status;
}

function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function formatToolWithDebug(tool) {
    let html = `<div class="tool-debug">
        <div class="tool-name">${tool.name} <small>(${Math.round(tool.confidence * 100)}%)</small></div>`;

    if (tool.debug_info) {
        const d = tool.debug_info;
        html += `<div class="debug-metrics">
            <span title="Brightness ratio">B: ${(d.brightness_ratio * 100).toFixed(1)}%</span>
            <span title="Saturation ratio">S: ${(d.saturation_ratio * 100).toFixed(1)}%</span>
            <span title="Edge density">E: ${(d.edge_density * 100).toFixed(1)}%</span>
            <span title="Mean brightness">μB: ${d.mean_brightness.toFixed(0)}</span>
        </div>`;
    }

    html += '</div>';
    return html;
}

// ==================== TOAST NOTIFICATIONS ====================
function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');

    const icons = {
        success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
        error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-icon">${icons[type]}</div>
        <div class="toast-message">${message}</div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    // Auto-remove after duration
    setTimeout(() => {
        toast.classList.add('hiding');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}
