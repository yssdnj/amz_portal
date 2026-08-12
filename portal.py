from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import socket
import uvicorn

app = FastAPI(title="整合入口 - Amazon Tools Portal")

SERVICES = {
    "products": {"name": "产品列表", "port": 5003},
    "ads": {"name": "广告漏斗分析", "port": 5001},
    "toolkit": {"name": "运营工具箱", "port": 5002},
    "xiyou": {"name": "西柚关键词", "port": 5004},
    "amazon_official_sp": {"name": "亚马逊官方SP API", "port": 8015},
    "amazon_official_ads": {"name": "亚马逊官方广告API", "port": 5010},
}


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

<script>
function useLocalModuleLinks() {
  const isLocalHost = location.hostname === '127.0.0.1' || location.hostname === 'localhost';
  if (!isLocalHost || location.port !== '5000') return;
  document.querySelectorAll('[data-local-url]').forEach((card) => {
    card.href = card.dataset.localUrl;
  });
}

async function refreshStatuses() {
  try {
    const response = await fetch('/api/status');
    if (!response.ok) throw new Error('status request failed');
    const data = await response.json();
    for (const [serviceId, service] of Object.entries(data.services || {})) {
      const card = document.querySelector(`[data-service="${serviceId}"]`);
      const badge = card?.querySelector('[data-status-badge]');
      if (!badge) continue;
      badge.classList.remove('badge-checking', 'badge-live', 'badge-offline');
      if (service.online) {
        badge.classList.add('badge-live');
        badge.textContent = '● 运行中';
      } else {
        badge.classList.add('badge-offline');
        badge.textContent = '● 未启动';
      }
    }
  } catch (error) {
    document.querySelectorAll('[data-status-badge]').forEach((badge) => {
      badge.classList.remove('badge-checking', 'badge-live');
      badge.classList.add('badge-offline');
      badge.textContent = '● 未启动';
    });
  }
}

useLocalModuleLinks();
refreshStatuses();
setInterval(refreshStatuses, 30000);
</script>

</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML


@app.get("/api/status")
def status():
    return {"services": get_service_statuses()}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000, reload=False)
