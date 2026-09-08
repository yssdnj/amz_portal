from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
import ipaddress
import os
from pathlib import Path
import platform
import secrets
import socket
from urllib.parse import urlsplit
import uvicorn

from service_control import PROJECT_CONFIG, ServiceController

app = FastAPI(title="整合入口 - Amazon Tools Portal")

SERVICES = {
    "products": {"name": "产品列表", "port": 5003},
    "ads": {"name": "广告漏斗分析", "port": 5001},
    "toolkit": {"name": "运营工具箱", "port": 5002},
    "xiyou": {"name": "西柚关键词", "port": 5004},
    "amazon_official_sp": {"name": "亚马逊官方SP API", "port": 8015},
    "amazon_official_ads": {"name": "亚马逊官方广告API", "port": 5010},
}

controller = ServiceController(
    {key: {**service, **PROJECT_CONFIG[key]} for key, service in SERVICES.items()},
    os.environ.get("PORTAL_PROJECTS_ROOT", Path(__file__).resolve().parent.parent),
    Path(__file__).resolve().parent / ".portal-runtime",
)


def is_port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def get_service_statuses() -> dict[str, dict[str, object]]:
    return {
        key: {
            "name": service["name"],
            "port": service["port"],
            "online": is_port_open(service["port"]),
            **controller.details(key),
        }
        for key, service in SERVICES.items()
    }

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>整合入口 · Amazon Tools</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
  background: #0d0d1a;
  color: #e2e8f0;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Topbar ── */
.topbar {
  background: linear-gradient(135deg, #1a1a2e, #16213e);
  padding: 16px 32px;
  border-bottom: 1px solid rgba(59, 130, 246, 0.2);
  display: flex;
  align-items: center;
  gap: 14px;
  position: sticky;
  top: 0;
  z-index: 10;
}
.topbar-logo { font-size: 22px; line-height: 1; }
.topbar-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.3px;
  color: #f1f5f9;
}
.topbar-sub {
  font-size: 11px;
  color: #475569;
  margin-left: auto;
  letter-spacing: 0.3px;
}

/* ── Hero ── */
.hero {
  text-align: center;
  padding: 52px 24px 36px;
}
.hero h2 {
  font-size: 26px;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 8px;
  letter-spacing: -0.3px;
}
.hero p {
  font-size: 13px;
  color: #64748b;
}

/* ── Grid ── */
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  max-width: 1080px;
  margin: 0 auto;
  padding: 0 24px 64px;
  width: 100%;
}
@media (max-width: 860px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 540px) { .grid { grid-template-columns: 1fr; } }

/* ── Card base ── */
.card {
  background: #13131f;
  border: 1px solid #1e2035;
  border-radius: 14px;
  padding: 28px 24px 24px;
  position: relative;
  overflow: hidden;
}

/* Active card (clickable) */
a.card {
  display: block;
  text-decoration: none;
  color: inherit;
  cursor: pointer;
  transition: transform 0.22s ease, box-shadow 0.22s ease, border-color 0.22s ease;
}
a.card::before {
  content: '';
  position: absolute;
  top: 0; left: 24px; right: 24px;
  height: 2px;
  background: linear-gradient(90deg, transparent, #3b82f6, transparent);
  opacity: 0;
  transition: opacity 0.22s;
}
a.card:hover {
  transform: translateY(-5px);
  box-shadow: 0 16px 48px rgba(59, 130, 246, 0.16);
  border-color: rgba(59, 130, 246, 0.5);
}
a.card:hover::before { opacity: 1; }
a.card:hover .card-icon { transform: scale(1.12); }

/* Arrow indicator on active cards */
a.card .card-arrow {
  position: absolute;
  bottom: 20px; right: 20px;
  font-size: 14px;
  color: #334155;
  transition: color 0.22s, transform 0.22s;
}
a.card:hover .card-arrow {
  color: #3b82f6;
  transform: translate(2px, -2px);
}

/* Coming-soon card */
div.card {
  opacity: 0.42;
  cursor: not-allowed;
  filter: grayscale(0.25);
}

/* ── Card internals ── */
.card-icon {
  font-size: 38px;
  display: block;
  margin-bottom: 16px;
  line-height: 1;
  transition: transform 0.22s;
}
.card-name {
  font-size: 17px;
  font-weight: 700;
  color: #f1f5f9;
  margin-bottom: 4px;
}
.card-sub {
  font-size: 10px;
  color: #475569;
  text-transform: uppercase;
  letter-spacing: 0.8px;
  margin-bottom: 14px;
  font-weight: 600;
}
.card-desc {
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.65;
}

/* ── Badges ── */
.badge {
  position: absolute;
  top: 16px; right: 16px;
  font-size: 10px;
  font-weight: 700;
  padding: 3px 9px;
  border-radius: 20px;
  letter-spacing: 0.4px;
}
.badge-live {
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
  border: 1px solid rgba(59, 130, 246, 0.28);
}
.badge-checking {
  background: rgba(148, 163, 184, 0.1);
  color: #94a3b8;
  border: 1px solid rgba(148, 163, 184, 0.22);
}
.badge-offline {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.25);
}
.badge-soon {
  background: rgba(212, 168, 67, 0.12);
  color: #d4a843;
  border: 1px solid rgba(212, 168, 67, 0.28);
}

/* ── Footer ── */
.footer {
  margin-top: auto;
  text-align: center;
  padding: 20px 24px;
  font-size: 11px;
  color: #1e293b;
  border-top: 1px solid #13131f;
}

.service-card { padding: 0; display: flex; flex-direction: column; }
.service-card:hover { border-color: rgba(59, 130, 246, 0.5); }
.card-link { display: block; padding: 28px 24px 24px; color: inherit; text-decoration: none; flex: 1; }
.card-link .card-arrow { float: right; color: #64748b; }
.card-link:focus-visible, button:focus-visible { outline: 2px solid #60a5fa; outline-offset: -3px; }
.service-controls { display: flex; align-items: center; gap: 10px; padding: 12px 24px; border-top: 1px solid #252637; }
button { font: inherit; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: 0.45; }
.service-switch { width: 42px; height: 24px; flex: 0 0 42px; border: 1px solid #64748b; border-radius: 20px; background: #363b49; padding: 3px; }
.switch-thumb { display: block; width: 16px; height: 16px; background: #f1f5f9; border-radius: 50%; transition: transform 0.15s; }
.service-switch[aria-checked="true"] { background: #16805d; border-color: #33ba90; }
.service-switch[aria-checked="true"] .switch-thumb { transform: translateX(17px); }
.control-label { font-size: 12px; color: #a9b4c5; }
.restart-wrap { margin-left: auto; display: inline-flex; }
.restart-button { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid #45485d; border-radius: 6px; color: #cbd5e1; background: transparent; }
.restart-button:not(:disabled):hover { color: #f1f5f9; background: #303345; }
.restart-button svg { width: 17px; height: 17px; }
.service-message { color: #fca5a5; font-size: 12px; line-height: 1.6; padding: 0 24px 12px; overflow-wrap: anywhere; }
.service-message:empty { display: none; }
dialog { margin: auto; width: min(420px, calc(100% - 32px)); max-height: calc(100% - 32px); overflow: auto; background: #191a26; color: #e2e8f0; border: 1px solid #45485d; border-radius: 8px; padding: 24px; }
dialog::backdrop { background: rgba(0, 0, 0, 0.65); }
dialog h3 { font-size: 18px; overflow-wrap: anywhere; }
dialog p { margin-top: 14px; color: #b5c0d1; font-size: 14px; line-height: 1.7; }
dialog .warning { color: #efc178; }
.dialog-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
.dialog-actions button { border: 1px solid #545969; border-radius: 6px; padding: 9px 16px; background: #2a2d3a; color: #f1f5f9; }
.dialog-actions .confirm-button { background: #216b50; border-color: #319372; }
dialog input { margin-top: 16px; width: 100%; background: #11131c; border: 1px solid #636b7b; border-radius: 6px; color: #fff; padding: 10px; font: inherit; }
@media (prefers-reduced-motion: reduce) { .switch-thumb { transition: none; } }
</style>
</head>
<body>

<div class="topbar">
  <span class="topbar-logo">🚀</span>
  <span class="topbar-title">整合入口</span>
  <span class="topbar-sub">Amazon Tools Portal &nbsp;·&nbsp; 47.84.113.76</span>
</div>

<div class="hero">
  <h2>Amazon 运营工具中心</h2>
  <p>选择下方工具开始工作</p>
</div>

<div class="grid">

  <!-- 产品列表 -->
  <a class="card" href="/products/" target="_blank" rel="noopener" data-service="products" data-local-url="http://127.0.0.1:5003/">
    <span class="badge badge-checking" data-status-badge>● 检测中</span>
    <span class="card-icon">📦</span>
    <div class="card-name">产品列表</div>
    <div class="card-sub">Product Catalog</div>
    <p class="card-desc">产品 SKU 档案管理，含 ASIN / MSKU / FNSKU 映射、颜色尺寸属性查询</p>
    <span class="card-arrow">↗</span>
  </a>

  <!-- 广告漏斗分析 -->
  <a class="card" href="/ads/" target="_blank" rel="noopener" data-service="ads" data-local-url="http://127.0.0.1:5001/">
    <span class="badge badge-checking" data-status-badge>● 检测中</span>
    <span class="card-icon">📊</span>
    <div class="card-name">广告漏斗分析</div>
    <div class="card-sub">Ad Analytics Dashboard</div>
    <p class="card-desc">广告数据导入、漏斗分析、多维度可视化报告，支持多周对比与数据导出</p>
    <span class="card-arrow">↗</span>
  </a>

  <!-- 运营工具箱 -->
  <a class="card" href="/toolkit/" target="_blank" rel="noopener" data-service="toolkit" data-local-url="http://127.0.0.1:5002/">
    <span class="badge badge-checking" data-status-badge>● 检测中</span>
    <span class="card-icon">🛠️</span>
    <div class="card-name">运营工具箱</div>
    <div class="card-sub">Operations Toolkit</div>
    <p class="card-desc">周报数据清洗与写入、广告批量调价、FBA/FBM 自动化运营工具集合</p>
    <span class="card-arrow">↗</span>
  </a>

  <!-- 西柚关键词 -->
  <a class="card" href="/xiyou/" target="_blank" rel="noopener" data-service="xiyou" data-local-url="http://127.0.0.1:5004/">
    <span class="badge badge-checking" data-status-badge>● 检测中</span>
    <span class="card-icon">🍋</span>
    <div class="card-name">西柚关键词</div>
    <div class="card-sub">Xiyou Keyword Research</div>
    <p class="card-desc">关键词流量分析、搜索趋势、竞品词挖掘，数据缓存加速查询</p>
    <span class="card-arrow">↗</span>
  </a>

  <!-- 亚马逊官方SP API -->
  <a class="card" href="/amazon-official-sp/" target="_blank" rel="noopener" data-service="amazon_official_sp" data-local-url="http://127.0.0.1:8015/">
    <span class="badge badge-checking" data-status-badge>● 检测中</span>
    <span class="card-icon">🛍️</span>
    <div class="card-name">亚马逊官方SP API</div>
    <div class="card-sub">Amazon Selling Partner API</div>
    <p class="card-desc">官方促销与优惠券报告同步、每日快照、活动及 ASIN 表现分析</p>
    <span class="card-arrow">↗</span>
  </a>

  <!-- 亚马逊官方广告API -->
  <a class="card" href="/amazon-official-ads/" target="_blank" rel="noopener" data-service="amazon_official_ads" data-local-url="http://127.0.0.1:5010/">
    <span class="badge badge-checking" data-status-badge>● 检测中</span>
    <span class="card-icon">🔗</span>
    <div class="card-name">亚马逊官方广告API</div>
    <div class="card-sub">Amazon Ads API</div>
    <p class="card-desc">官方广告接口授权、报表拉取、广告数据同步与管理</p>
    <span class="card-arrow">↗</span>
  </a>

  <!-- 选品开发 -->
  <div class="card">
    <span class="badge badge-soon">开发中</span>
    <span class="card-icon">🔍</span>
    <div class="card-name">选品开发</div>
    <div class="card-sub">Product Selection</div>
    <p class="card-desc">市场调研、竞品分析、蓝海选品决策支持系统</p>
  </div>

  <!-- Listing 制作 -->
  <div class="card">
    <span class="badge badge-soon">开发中</span>
    <span class="card-icon">✍️</span>
    <div class="card-name">Listing 制作</div>
    <div class="card-sub">Listing Creator</div>
    <p class="card-desc">AI 辅助标题 / 五点 / 描述撰写，关键词优化与 A+ 内容管理</p>
  </div>

  <!-- 广告自动优化 -->
  <div class="card">
    <span class="badge badge-soon">开发中</span>
    <span class="card-icon">🤖</span>
    <div class="card-name">广告自动优化</div>
    <div class="card-sub">Ad Auto-Optimization</div>
    <p class="card-desc">规则引擎驱动的竞价调价、预算管理与广告策略自动执行</p>
  </div>

</div>

<div class="footer">Amazon Tools Portal &nbsp;·&nbsp; 整合入口 &nbsp;·&nbsp; 2026</div>

<dialog id="restart-dialog" aria-labelledby="restart-title">
  <form method="dialog">
    <h3 id="restart-title">确认重启</h3>
    <p>部署脚本可能更新代码，服务将短暂中断。</p>
    <p class="warning" id="restart-warning" hidden>此项目的部署脚本可能同时停止其他同名入口的服务。</p>
    <div class="dialog-actions">
      <button value="cancel" autofocus>取消</button>
      <button value="confirm" class="confirm-button">确认重启</button>
    </div>
  </form>
</dialog>
<dialog id="auth-dialog" aria-labelledby="auth-title">
  <form method="dialog">
    <h3 id="auth-title">管理员验证</h3>
    <input id="control-token" type="password" aria-label="管理员控制密钥" placeholder="管理员控制密钥" autocomplete="off">
    <div class="dialog-actions">
      <button value="cancel">取消</button>
      <button value="confirm" class="confirm-button">验证</button>
    </div>
  </form>
</dialog>

<script>
let serviceStatuses = {};
let controlSettings = {};
let controlToken = '';
let refreshing = false;
const pendingServices = new Set();

function initializeControls() {
  document.querySelectorAll('a.card[data-service]').forEach((link) => {
    const card = document.createElement('article');
    card.className = 'card service-card';
    card.dataset.service = link.dataset.service;
    delete link.dataset.service;
    link.className = 'card-link';
    link.before(card);
    card.append(link);
    const controls = document.createElement('div');
    controls.className = 'service-controls';
    // Lucide rotate-cw icon, ISC license: https://lucide.dev/license
    controls.innerHTML = `
      <button type="button" class="service-switch" role="switch" aria-checked="false" aria-label="服务开关" disabled><span class="switch-thumb"></span></button>
      <span class="control-label">检测中</span>
      <span class="restart-wrap" tabindex="0"><button type="button" class="restart-button" aria-label="重启" disabled>
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/></svg>
      </button></span>`;
    const message = document.createElement('p');
    message.className = 'service-message';
    message.setAttribute('role', 'status');
    card.append(controls, message);
    controls.querySelector('.service-switch').addEventListener('click', () => {
      const service = serviceStatuses[card.dataset.service];
      if (service) performAction(card, service.online ? 'stop' : 'start');
    });
    controls.querySelector('.restart-button').addEventListener('click', () => performAction(card, 'restart'));
  });
}

function useLocalModuleLinks() {
  const isLocalHost = location.hostname === '127.0.0.1' || location.hostname === 'localhost';
  if (!isLocalHost || location.port !== '5000') return;
  document.querySelectorAll('[data-local-url]').forEach((card) => {
    card.href = card.dataset.localUrl;
  });
}

function renderStatus(card, service) {
  const badge = card.querySelector('[data-status-badge]');
  const toggle = card.querySelector('.service-switch');
  const restart = card.querySelector('.restart-button');
  const busy = service.busy || pendingServices.has(card.dataset.service);
  const actionNames = {start: '启动中', stop: '暂停中', restart: '重启中'};
  const label = busy ? (actionNames[service.action] || '处理中') : (service.online ? '运行中' : '未启动');
  badge.className = 'badge ' + (busy ? 'badge-checking' : service.online ? 'badge-live' : 'badge-offline');
  badge.textContent = '● ' + label;
  toggle.setAttribute('aria-checked', String(service.online));
  toggle.disabled = busy || !controlSettings.enabled || (!service.online && !service.can_start);
  toggle.title = !controlSettings.enabled ? '服务器尚未启用管理员控制' : !service.online && !service.can_start ? '项目目录不存在或系统不支持' : (service.online ? '暂停' : '启动');
  toggle.setAttribute('aria-label', service.name + '：' + (service.online ? '暂停' : '启动'));
  card.querySelector('.control-label').textContent = busy ? label : service.online ? '已开启' : '已关闭';
  restart.disabled = busy || !controlSettings.enabled || !service.can_restart;
  restart.setAttribute('aria-label', '重启' + service.name);
  restart.parentElement.title = controlSettings.platform !== 'Linux' ? '重启仅支持 Linux 服务端' : !controlSettings.enabled ? '服务器尚未启用管理员控制' : !service.can_restart ? '项目目录下未找到 deploy.sh' : '重启';
  card.querySelector('.service-message').textContent = service.error || '';
}

async function refreshStatuses() {
  if (refreshing) return;
  refreshing = true;
  try {
    const response = await fetch('/api/status', {cache: 'no-store', signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error('status request failed');
    const data = await response.json();
    serviceStatuses = data.services || {};
    controlSettings = data.controls || {};
    document.querySelectorAll('.service-card').forEach((card) => {
      const service = serviceStatuses[card.dataset.service];
      if (!service) throw new Error('missing service status');
      renderStatus(card, service);
    });
  } catch (error) {
    document.querySelectorAll('.service-card').forEach((card) => {
      const badge = card.querySelector('[data-status-badge]');
      badge.className = 'badge badge-checking';
      badge.textContent = '● 状态未知';
      card.querySelectorAll('button').forEach((button) => { button.disabled = true; });
      card.querySelector('.control-label').textContent = '连接中断';
    });
  } finally {
    refreshing = false;
  }
}

function showDialog(id) {
  const dialog = document.getElementById(id);
  if (dialog.open) return Promise.resolve(false);
  dialog.returnValue = '';
  return new Promise((resolve) => {
    dialog.addEventListener('close', () => resolve(dialog.returnValue === 'confirm'), {once: true});
    dialog.showModal();
  });
}

async function performAction(card, action) {
  const id = card.dataset.service;
  if (pendingServices.has(id) || serviceStatuses[id]?.busy) return;
  if (action === 'restart') {
    document.getElementById('restart-title').textContent = '重启' + serviceStatuses[id].name + '？';
    document.getElementById('restart-warning').hidden = !serviceStatuses[id].restart_warning;
    if (!await showDialog('restart-dialog')) return;
  }
  if (controlSettings.requires_token && !controlToken) {
    if (!await showDialog('auth-dialog')) return;
    controlToken = document.getElementById('control-token').value;
    document.getElementById('control-token').value = '';
    if (!controlToken) return;
  }
  pendingServices.add(id);
  serviceStatuses[id].error = null;
  renderStatus(card, serviceStatuses[id]);
  let failure = null;
  try {
    const headers = {'X-Portal-Control': '1'};
    if (controlToken) headers.Authorization = 'Bearer ' + controlToken;
    const response = await fetch(`/api/services/${id}/${action}`, {method: 'POST', headers, signal: AbortSignal.timeout(15000)});
    const result = await response.json();
    if (!response.ok) {
      if (response.status === 401) controlToken = '';
      throw new Error(result.detail || '操作失败');
    }
    serviceStatuses[id].busy = true;
    serviceStatuses[id].action = action;
  } catch (error) {
    failure = error.message;
  } finally {
    pendingServices.delete(id);
    renderStatus(card, serviceStatuses[id]);
    await refreshStatuses();
    if (failure) card.querySelector('.service-message').textContent = failure;
  }
}

initializeControls();
useLocalModuleLinks();
refreshStatuses();
setInterval(refreshStatuses, 3000);
</script>

</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML


def is_local_request(request: Request) -> bool:
    try:
        peer = request.client.host if request.client else ""
        if not ipaddress.ip_address(peer).is_loopback:
            return False
        forwarded = request.headers.get("x-forwarded-for") or request.headers.get("x-real-ip")
        return not forwarded or all(ipaddress.ip_address(ip.strip()).is_loopback for ip in forwarded.split(","))
    except ValueError:
        return False


@app.get("/api/status")
def status(request: Request):
    local = is_local_request(request)
    return {"services": get_service_statuses(), "controls": {
        "platform": platform.system(),
        "enabled": local or bool(os.environ.get("PORTAL_CONTROL_TOKEN")),
        "requires_token": not local,
    }}


@app.post("/api/services/{service_id}/{action}", status_code=202)
def control_service(service_id: str, action: str, request: Request):
    origin = request.headers.get("origin")
    if request.headers.get("x-portal-control") != "1" or (origin and urlsplit(origin).hostname != request.url.hostname):
        raise HTTPException(403, "不允许跨站操作")
    if not is_local_request(request):
        token = os.environ.get("PORTAL_CONTROL_TOKEN")
        if not token:
            raise HTTPException(403, "服务器尚未配置管理员控制密钥")
        if not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {token}"):
            raise HTTPException(401, "管理员控制密钥无效")
    if service_id not in SERVICES or action not in {"start", "stop", "restart"}:
        raise HTTPException(404, "项目或操作不存在")
    try:
        controller.submit(service_id, action)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from None
    return {"accepted": True, "service_id": service_id, "action": action}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=False)
