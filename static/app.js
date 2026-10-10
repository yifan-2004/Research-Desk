'use strict';
let state, activeTab = 'sources', editorKind = 'sources', chatBusy = false;
const $ = selector => document.querySelector(selector);
const text = (tag, content, className) => { const el = document.createElement(tag); el.textContent = content; if (className) el.className = className; return el; };
let toastTimer;
function toast(message) { $('#toast').textContent = message; $('#toast').hidden = false; clearTimeout(toastTimer); toastTimer = setTimeout(() => $('#toast').hidden = true, 4500); }
async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Desk-Token': state.csrf}, body: JSON.stringify(body)});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || '操作失败，请重试。');
  return result;
}
function link(url, label) { const a = text('a', label); a.href = url; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a; }
function empty(container, message) { container.append(text('div', message, 'empty')); }
async function refresh() {
  state = await api('/api/state');
  $('#source-count').textContent = state.sources.length;
  $('#note-count').textContent = state.notes.length;
  $('#task-count').textContent = state.tasks.filter(task => !task.done).length;
  $('#mode').textContent = state.mode === 'offline' ? '离线检索 · 无需密钥' : `模型已配置 · ${state.model}`;
  $('#privacy-note').textContent = state.mode === 'offline' ? '离线模式只做关键词检索，不会生成 AI 回答，也不会上传资料。' : '模型模式：发送时，问题和最多 5 条匹配的资料片段会传给你配置的模型服务。';
  renderItems(); renderTasks();
}
function renderItems() {
  const container = $('#items'); container.replaceChildren();
  const query = $('#filter').value.toLowerCase();
  const rows = state[activeTab].filter(row => (row.title + row.content).toLowerCase().includes(query));
  if (!rows.length) empty(container, query ? '没有匹配内容。' : '还没有内容。添加第一条研究记录吧。');
  for (const row of rows) {
    const item = text('article', '', 'item');
    const title = text('div', '', 'item-title');
    title.append(text('span', `[${activeTab === 'sources' ? 'S' : 'N'}${row.id}]`, 'source-id'), document.createTextNode(row.title));
    item.append(title, text('p', row.content.slice(0, 130) + (row.content.length > 130 ? '…' : '')));
    const detail = text('details', ''); detail.append(text('summary', '展开全文')); detail.append(text('p', row.content)); item.append(detail);
    if (row.url) item.append(link(row.url, '打开原文 ↗'));
    const remove = text('button', '×', 'delete'); remove.setAttribute('aria-label', `删除 ${row.title}`);
    remove.onclick = async () => { if (confirm(`删除“${row.title}”？此操作无法撤销。`)) { try { await api(`/api/${activeTab}/${row.id}/delete`, {}); await refresh(); } catch (error) { toast(error.message); } } };
    item.append(remove); container.append(item);
  }
}
function renderTasks() {
  const container = $('#task-list'); container.replaceChildren();
  $('#task-progress').textContent = `${state.tasks.filter(task => task.done).length} / ${state.tasks.length}`;
  if (!state.tasks.length) empty(container, '把研究问题拆成一个可完成的小任务。');
  for (const task of state.tasks) {
    const row = text('div', '', 'task-row' + (task.done ? ' done' : ''));
    const check = document.createElement('input'); check.type = 'checkbox'; check.checked = Boolean(task.done); check.id = `task-${task.id}`;
    check.onchange = async () => { try { await api(`/api/tasks/${task.id}/toggle`, {done: check.checked}); await refresh(); } catch (error) { toast(error.message); check.checked = !check.checked; } };
    const label = text('label', task.title); label.htmlFor = check.id;
    const remove = text('button', '×', 'delete'); remove.setAttribute('aria-label', `删除任务 ${task.title}`);
    remove.onclick = async () => { if (confirm(`删除任务“${task.title}”？`)) { try { await api(`/api/tasks/${task.id}/delete`, {}); await refresh(); } catch (error) { toast(error.message); } } };
    row.append(check, label, remove); container.append(row);
  }
}
function openEditor(kind) {
  editorKind = kind; $('#editor-form').reset();
  $('#editor-title').textContent = kind === 'sources' ? '添加参考资料' : '写一条研究笔记';
  $('#url-field').hidden = kind !== 'sources'; $('#editor').showModal();
}
$('#add-source').onclick = () => openEditor('sources');
$('#add-note').onclick = () => openEditor('notes');
$('#close-editor').onclick = () => $('#editor').close();
$('#editor-form').onsubmit = async event => {
  event.preventDefault(); const button = event.submitter; button.disabled = true;
  try { await api(`/api/${editorKind}`, Object.fromEntries(new FormData(event.target))); $('#editor').close(); activeTab = editorKind; updateTabs(); await refresh(); toast('已保存到本机。'); }
  catch (error) { toast(error.message); } finally { button.disabled = false; }
};
function updateTabs() { document.querySelectorAll('.tab').forEach(tab => tab.classList.toggle('active', tab.dataset.tab === activeTab)); }
document.querySelectorAll('.tab').forEach(tab => tab.onclick = () => { activeTab = tab.dataset.tab; updateTabs(); renderItems(); });
$('#filter').oninput = () => state && renderItems();
$('#task-form').onsubmit = async event => {
  event.preventDefault();
  try { await api('/api/tasks', {title: $('#task-title').value}); $('#task-title').value = ''; await refresh(); } catch (error) { toast(error.message); }
};
function appendMessage(role, body) {
  const box = text('article', '', `message ${role}`);
  box.append(text('div', role === 'user' ? '你' : 'Research Desk', 'message-heading'), text('div', body, 'message-body'));
  $('#conversation').append(box); $('#conversation').scrollTop = $('#conversation').scrollHeight;
  return box;
}
$('#chat-form').onsubmit = async event => {
  event.preventDefault(); if (chatBusy || !state) return;
  const message = $('#message').value.trim(); if (!message) return;
  if (state.mode === 'connected' && !confirm('本次问题和匹配的资料片段将发送到你配置的模型服务。继续？')) return;
  chatBusy = true; $('#send').disabled = true;
  $('.welcome')?.remove(); appendMessage('user', message); $('#message').value = '';
  const answer = appendMessage('assistant', '正在检索资料…');
  try {
    const result = await api('/api/chat', {message}); answer.querySelector('.message-body').textContent = result.answer;
    for (const source of result.sources) {
      const details = text('details', '', 'source-card'); details.append(text('summary', `[${source.id}] ${source.title}`), text('pre', source.excerpt));
      if (source.url) details.append(link(source.url, '核对原文 ↗')); answer.append(details);
    }
    $('#conversation').scrollTop = $('#conversation').scrollHeight;
  } catch (error) { answer.querySelector('.message-body').textContent = error.message; }
  finally { chatBusy = false; $('#send').disabled = false; }
};
document.querySelectorAll('.preset').forEach(button => button.onclick = () => { $('#message').value = button.dataset.prompt; $('#message').focus(); });
$('#export').onclick = async () => {
  try { const data = await api('/api/export'); const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type: 'application/json'})); const anchor = link(url, ''); anchor.download = `research-desk-${new Date().toISOString().slice(0,10)}.json`; anchor.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  catch (error) { toast(error.message); }
};
$('#load-example').onclick = async () => {
  if (!state) return;
  if (!confirm('添加 2 条明确标记为示例的研究记录和 2 个待办？这些内容不包含真实实验结果。')) return;
  try {
    await api('/api/sources', {title: '示例 · 低照度增强评测计划', content: '示例研究计划，不是已完成实验。\n\n低照度图像增强需记录训练、验证、测试的数据划分，确认是否存在同场景图像泄漏。评测 PSNR 和 SSIM 时，需要固定颜色空间、图像范围、裁剪边界与输出分辨率。\n\n消融实验建议固定训练预算和随机种子，逐项移除模块。尚无数值结果，不能据此宣称性能提升。', url: ''});
    await api('/api/notes', {title: '示例 · 单目 3D 检测复现检查', content: '示例笔记：单目 3D 检测需要保留相机标定和图像预处理信息。核对 KITTI 官方数据划分、类别、IoU 阈值，以及 AP_R40/AP_R11 的区别。可视化中投影框看起来正确并不代表 3D 定位准确。还需要核对深度误差与遮挡条件。'});
    await api('/api/tasks', {title: '确认增强评测的颜色空间与数据划分'});
    await api('/api/tasks', {title: '记录 3D 检测可视化使用的相机标定'});
    await refresh(); toast('示例已添加；没有虚构实验数值。');
  } catch (error) { toast(error.message); }
};
refresh().catch(error => { $('#mode').textContent = '连接失败'; toast(error.message + ' 请确认本机服务正在运行。'); });
