from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from dotenv import load_dotenv
from html import escape
import json
import os
from pathlib import Path
import platform
import secrets
import socket
from urllib.parse import quote, unquote, urlsplit
from uuid import NAMESPACE_URL, uuid5
import uvicorn
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

from login_page import render_login_page
from portal_theme import apply_theme
from service_control import PROJECT_CONFIG, ServiceController


load_dotenv(Path(__file__).with_name(".env"))


def required_setting(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def parse_cookie_secure(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(
        "PORTAL_COOKIE_SECURE must be true/false, yes/no, on/off, or 1/0"
    )


def load_extra_users(value: str | None, primary_username: str) -> dict[str, str]:
    if not value:
        return {}

    def unique_object(pairs):
        result = {}
        for key, password in pairs:
            if key in result:
                raise ValueError
            result[key] = password
        return result

    try:
        accounts = json.loads(value, object_pairs_hook=unique_object)
        if not isinstance(accounts, dict) or primary_username in accounts:
            raise ValueError
        if any(not username or not isinstance(password, str) or not password
               for username, password in accounts.items()):
            raise ValueError
    except (ValueError, TypeError, RecursionError):
        raise RuntimeError("Invalid PORTAL_EXTRA_USERS configuration") from None
    return accounts


def user_id_for(username: str) -> str:
    return str(uuid5(NAMESPACE_URL, "urn:amz-portal:user:" + username))


LOGIN_USERNAME = required_setting("PORTAL_LOGIN_USERNAME")
LOGIN_USER_ID = user_id_for(LOGIN_USERNAME)
LOGIN_PASSWORD = required_setting("PORTAL_LOGIN_PASSWORD")
EXTRA_USERS = load_extra_users(os.environ.get("PORTAL_EXTRA_USERS"), LOGIN_USERNAME)
SESSION_SECRET = required_setting("PORTAL_SESSION_SECRET")
COOKIE_SECURE = parse_cookie_secure(os.environ.get("PORTAL_COOKIE_SECURE"))


def configured_accounts() -> dict[str, str]:
    return {LOGIN_USERNAME: LOGIN_PASSWORD, **EXTRA_USERS}

app = FastAPI(title="整合入口 - Amazon Tools Portal")
app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET,
    session_cookie="amazon_portal_session",
    max_age=12 * 60 * 60,
    path="/",
    same_site="lax",
    https_only=COOKIE_SECURE,
)


class LoginRequest(BaseModel):
    username: str
    password: str
    next: str | None = None

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
__THEME_CSS__
__THEME_INIT__
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", sans-serif;
  background: var(--page-bg);
  color: var(--text);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Topbar ── */
.topbar {
  background: var(--topbar-bg);
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
  letter-spacing: 0;
  white-space: nowrap;
  color: var(--heading);
}
.topbar-sub {
  font-size: 11px;
  color: var(--subtle);
  margin-left: 8px;
  letter-spacing: 0;
}
.topbar-actions { display: flex; align-items: center; gap: 10px; margin-left: auto; min-width: 0; }
.current-user { min-width: 0; max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; color: var(--muted); }
@media (max-width: 540px) {
  .topbar { padding: 12px 16px; gap: 8px; }
  .topbar-sub { display: none; }
  .topbar-title { font-size: 14px; }
  .topbar-actions { gap: 8px; }
}
.logout-button {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  display: grid;
  place-items: center;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: var(--muted);
}
.logout-button:hover { color: var(--heading); background: var(--hover-bg); }
.logout-button svg { width: 17px; height: 17px; }

/* ── Hero ── */
.hero {
  text-align: center;
  padding: 52px 24px 36px;
}
.hero h2 {
  font-size: 26px;
  font-weight: 700;
  color: var(--heading);
  margin-bottom: 8px;
  letter-spacing: 0;
}
.hero p {
  font-size: 13px;
  color: var(--subtle);
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
  background: var(--surface);
  border: 1px solid var(--soft-border);
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
  background: linear-gradient(90deg, transparent, var(--blue), transparent);
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
  color: var(--subtle);
  transition: color 0.22s, transform 0.22s;
}
a.card:hover .card-arrow {
  color: var(--blue);
  transform: translate(2px, -2px);
}

/* Coming-soon card */
div.card {
  cursor: not-allowed;
}
div.card .card-icon { opacity: 0.55; filter: grayscale(0.25); }
div.card .card-name { color: var(--muted); }

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
  color: var(--heading);
  margin-bottom: 4px;
}
.card-sub {
  font-size: 10px;
  color: var(--subtle);
  text-transform: uppercase;
  letter-spacing: 0;
  margin-bottom: 14px;
  font-weight: 600;
}
.card-desc {
  font-size: 13px;
  color: var(--muted);
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
  letter-spacing: 0;
}
.badge-live {
  background: var(--blue-bg);
  color: var(--blue);
  border: 1px solid rgba(59, 130, 246, 0.28);
}
.badge-checking {
  background: rgba(148, 163, 184, 0.1);
  color: var(--muted);
  border: 1px solid rgba(148, 163, 184, 0.22);
}
.badge-offline {
  background: var(--red-bg);
  color: var(--red);
  border: 1px solid rgba(239, 68, 68, 0.25);
}
.badge-soon {
  background: var(--gold-bg);
  color: var(--gold);
  border: 1px solid rgba(212, 168, 67, 0.28);
}

/* ── Footer ── */
.footer {
  margin-top: auto;
  text-align: center;
  padding: 20px 24px;
  font-size: 11px;
  color: var(--subtle);
  border-top: 1px solid var(--surface);
}

.service-card { padding: 0; display: flex; flex-direction: column; }
.service-card:hover { border-color: rgba(59, 130, 246, 0.5); }
.card-link { display: block; padding: 28px 24px 24px; color: inherit; text-decoration: none; flex: 1; }
.card-link .card-arrow { float: right; color: var(--subtle); }
.card-link:focus-visible, button:focus-visible { outline: 2px solid var(--blue); outline-offset: -3px; }
.service-controls { display: flex; align-items: center; gap: 10px; padding: 12px 24px; border-top: 1px solid var(--soft-border); }
button { font: inherit; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: 0.45; }
.service-switch { width: 42px; height: 24px; flex: 0 0 42px; border: 1px solid var(--subtle); border-radius: 20px; background: var(--switch-off); padding: 3px; }
.switch-thumb { display: block; width: 16px; height: 16px; background: var(--switch-thumb); border-radius: 50%; transition: transform 0.15s; }
.service-switch[aria-checked="true"] { background: var(--success-bg); border-color: var(--success-border); }
.service-switch[aria-checked="true"] .switch-thumb { transform: translateX(17px); }
.control-label { font-size: 12px; color: var(--muted); }
.restart-wrap { margin-left: auto; display: inline-flex; }
.restart-button { width: 34px; height: 34px; display: grid; place-items: center; border: 1px solid var(--border); border-radius: 6px; color: var(--text); background: transparent; }
.restart-button:not(:disabled):hover { color: var(--heading); background: var(--hover-bg); }
.restart-button svg { width: 17px; height: 17px; }
.service-message { color: var(--red); font-size: 12px; line-height: 1.6; padding: 0 24px 12px; overflow-wrap: anywhere; }
.service-message:empty { display: none; }
dialog { margin: auto; width: min(420px, calc(100% - 32px)); max-height: calc(100% - 32px); overflow: auto; background: var(--dialog-bg); color: var(--text); border: 1px solid var(--border); border-radius: 8px; padding: 24px; }
dialog::backdrop { background: rgba(0, 0, 0, 0.65); }
dialog h3 { font-size: 18px; overflow-wrap: anywhere; }
dialog p { margin-top: 14px; color: var(--muted); font-size: 14px; line-height: 1.7; }
dialog .warning { color: var(--gold); }
.dialog-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
.dialog-actions button { border: 1px solid var(--border); border-radius: 6px; padding: 9px 16px; background: var(--button-bg); color: var(--heading); }
.dialog-actions .confirm-button { background: var(--success-bg); border-color: var(--success-border); color: var(--on-success); }
@media (prefers-reduced-motion: reduce) { .switch-thumb { transition: none; } }
</style>
</head>
<body>

<div class="topbar">
  <span class="topbar-logo">🚀</span>
  <span class="topbar-title">整合入口</span>
  <span class="topbar-sub">Amazon Tools Portal &nbsp;·&nbsp; 47.84.113.76</span>
  <div class="topbar-actions">
    <span class="current-user" title="__CURRENT_USERNAME__">__CURRENT_USERNAME__</span>
    __THEME_BUTTON__
  <button type="button" class="logout-button" id="logout-button" aria-label="退出登录" title="退出登录">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 17l5-5-5-5"/><path d="M15 12H3"/><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/></svg>
  </button>
  </div>
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
<script>
let serviceStatuses = {};
let controlSettings = {};
let refreshing = false;
const pendingServices = new Set();

function redirectToLogin() {
  const prefix = location.pathname.replace(/\/$/, '');
  location.assign(prefix + '/login?next=' + encodeURIComponent(location.pathname));
}

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
    if (response.status === 401) { redirectToLogin(); return; }
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
  pendingServices.add(id);
  serviceStatuses[id].error = null;
  renderStatus(card, serviceStatuses[id]);
  let failure = null;
  try {
    const headers = {'X-Portal-Control': '1'};
    const response = await fetch(`/api/services/${id}/${action}`, {method: 'POST', headers, signal: AbortSignal.timeout(15000)});
    if (response.status === 401) { redirectToLogin(); return; }
    const result = await response.json();
    if (!response.ok) {
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

document.getElementById('logout-button').addEventListener('click', async () => {
  const response = await fetch('/api/auth/logout', {method: 'POST'});
  const result = await response.json();
  location.assign(result.redirect);
});

initializeControls();
useLocalModuleLinks();
refreshStatuses();
setInterval(refreshStatuses, 3000);
</script>

</body>
</html>"""


def external_prefix(request: Request) -> str:
    value = request.headers.get("x-forwarded-prefix", "").strip()
    if not value or value == "/":
        return ""
    parsed = urlsplit(value)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
        or "\\" in parsed.path
    ):
        return ""
    return parsed.path.rstrip("/")


def prefix_root(prefix: str) -> str:
    return f"{prefix}/" if prefix else "/"


def safe_next_path(candidate: str | None, prefix: str) -> str:
    fallback = prefix_root(prefix)
    if not candidate or any(ord(char) < 32 for char in candidate):
        return fallback
    parsed = urlsplit(candidate)
    decoded_path = unquote(parsed.path)
    if (
        parsed.scheme
        or parsed.netloc
        or not parsed.path.startswith("/")
        or parsed.path.startswith("//")
        or "\\" in decoded_path
        or any(part in {".", ".."} for part in decoded_path.split("/"))
    ):
        return fallback
    if prefix and decoded_path != prefix and not decoded_path.startswith(prefix + "/"):
        return fallback
    return candidate


def render_portal_page(username: str) -> str:
    return apply_theme(HTML).replace("__CURRENT_USERNAME__", escape(username, quote=True))


def session_username(request: Request) -> str | None:
    if request.session.get("authenticated") is not True:
        return None
    user_id = request.session.get("user_id")
    if not isinstance(user_id, str):
        return None
    for username in configured_accounts():
        if user_id == user_id_for(username):
            return username
    return None


def require_session(request: Request) -> str:
    username = session_username(request)
    if username is None:
        raise HTTPException(401, "请先登录")
    return username


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str | None = None):
    prefix = external_prefix(request)
    return render_login_page(safe_next_path(next, prefix), prefix)


@app.post("/api/auth/login")
def login(payload: LoginRequest, request: Request):
    verified_username = None
    for username, password in configured_accounts().items():
        username_matches = secrets.compare_digest(
            payload.username.encode("utf-8"), username.encode("utf-8")
        )
        password_matches = secrets.compare_digest(
            payload.password.encode("utf-8"), password.encode("utf-8")
        )
        if username_matches and password_matches:
            verified_username = username
    if verified_username is None:
        raise HTTPException(401, "账号或密码不正确")
    request.session.clear()
    request.session["authenticated"] = True
    request.session["user_id"] = user_id_for(verified_username)
    prefix = external_prefix(request)
    return {"redirect": safe_next_path(payload.next, prefix)}


@app.get("/api/auth/check", status_code=204)
def auth_check(request: Request):
    require_session(request)
    return Response(status_code=204)


@app.get("/api/auth/user")
def current_user(request: Request) -> Response:
    headers = {"Cache-Control": "no-store"}
    username = session_username(request)
    if username is None:
        return JSONResponse(
            {"detail": "请先登录"}, status_code=401, headers=headers
        )
    return JSONResponse({"user_id": user_id_for(username)}, headers=headers)


@app.post("/api/auth/logout")
def logout(request: Request):
    request.session.clear()
    return {"redirect": external_prefix(request) + "/login"}


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    username = session_username(request)
    if username is None:
        prefix = external_prefix(request)
        root = prefix_root(prefix)
        return RedirectResponse(
            f"{prefix}/login?next={quote(root, safe='/')}",
            status_code=302,
        )
    return HTMLResponse(render_portal_page(username), headers={"Cache-Control": "no-store"})


@app.get("/api/status")
def status(request: Request):
    require_session(request)
    return {"services": get_service_statuses(), "controls": {
        "platform": platform.system(),
        "enabled": True,
    }}


@app.post("/api/services/{service_id}/{action}", status_code=202)
def control_service(service_id: str, action: str, request: Request):
    require_session(request)
    origin = request.headers.get("origin")
    if request.headers.get("x-portal-control") != "1" or (origin and urlsplit(origin).hostname != request.url.hostname):
        raise HTTPException(403, "不允许跨站操作")
    if service_id not in SERVICES or action not in {"start", "stop", "restart"}:
        raise HTTPException(404, "项目或操作不存在")
    try:
        controller.submit(service_id, action)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from None
    return {"accepted": True, "service_id": service_id, "action": action}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=False)
