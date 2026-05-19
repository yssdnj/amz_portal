# Portal — 整合入口

## 项目定位
统一入口门户，汇聚所有 Amazon 运营工具，运行在服务器 47.84.113.76。

## 目录结构
```
C:\Users\admin\Desktop\python\
├── portal\          ← 本项目，端口 5000
├── ads_dashboard\   ← 广告漏斗分析，端口 5001
└── amazon_toolkit\  ← 运营工具箱，端口 5002
```

## 部署架构
Nginx 监听 8080 端口（对外唯一入口），防火墙关闭 5000/5001/5002：

```
外网:8080 → Nginx
  /          → 127.0.0.1:5000 (portal,     FastAPI/uvicorn)
  /ads/      → 127.0.0.1:5001 (ads_dashboard, FastAPI/uvicorn)
  /toolkit/  → 127.0.0.1:5002 (amazon_toolkit, Flask)
```

## 文件说明
| 文件 | 说明 |
|------|------|
| `portal.py` | FastAPI 单文件应用，内联 HTML，端口 5000 |
| `nginx.conf` | Nginx 反代配置，复制到服务器 `/etc/nginx/conf.d/` |

## Nginx 部署命令（服务器端）
```bash
sudo cp nginx.conf /etc/nginx/conf.d/amazon-tools.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 已完成的改动
### portal/portal.py
- 广告漏斗分析卡片链接：`http://47.84.113.76:5001` → `/ads/`
- 运营工具箱卡片链接：`http://47.84.113.76:5002` → `/toolkit/`

### amazon_toolkit/web/templates/index.html
- 7 处 JS fetch/EventSource 路径从绝对路径改为相对路径
- 例：`fetch('/api/tools')` → `fetch('api/tools')`
- 原因：绝对路径在 Nginx 反代 `/toolkit/` 前缀下会指向 portal 而非 toolkit

### ads_dashboard/ads_funnel/frontend/index.html
- 无需修改，原本已是相对路径（`api/import`、`api/reports` 等）

## 关键设计说明
- Nginx 用 `proxy_pass http://backend/`（有尾斜杠）自动剥离 location 前缀
- `/ads` 和 `/toolkit`（无尾斜杠）配置了 301 重定向到带斜杠版本，防止相对 URL 解析错位
- toolkit location 配置了 `proxy_buffering off` 支持 SSE 实时日志流

## 待完成
- 将 nginx.conf 上传到服务器并 reload
- 服务器防火墙确认关闭 5000/5001/5002 对外端口
