# Amazon Tools Portal — 整合入口

统一入口门户，汇聚所有 Amazon 运营工具，运行在服务器 `47.84.113.76`。

## Nginx 反向代理架构

```
外网请求 → 47.84.113.76:8080 → Nginx
                                   │
                    ┌──────────────┼──────────────┐
                    │              │              │
                 location /     location /ads/  location /toolkit/
                    │              │              │
              127.0.0.1:5000  127.0.0.1:5001  127.0.0.1:5002
              portal.py        ads_dashboard   amazon_toolkit
              (FastAPI)        (FastAPI)       (Flask)
```

Nginx 监听 8080 端口（对外唯一入口），防火墙关闭 5000/5001/5002 对外访问：

| Location | 代理目标 | 应用 |
|----------|----------|------|
| `/` | `127.0.0.1:5000` | 门户主页（FastAPI） |
| `/ads/` | `127.0.0.1:5001` | 广告漏斗分析（FastAPI） |
| `/toolkit/` | `127.0.0.1:5002` | 运营工具箱（Flask） |

### 关键设计点

| 细节 | 说明 |
|------|------|
| `proxy_pass` 带尾斜杠 | Nginx 自动剥离 location 前缀再转发，后端服务无需感知 `/ads/` `/toolkit/` 前缀 |
| `/ads` `/toolkit`（无斜杠） | 301 重定向到带斜杠版本，防止浏览器相对 URL 解析错位 |
| `proxy_buffering off` | toolkit 专用，支持 SSE 实时日志流不被缓冲截断 |
| `proxy_read_timeout 3600s` | toolkit 长任务不超时断连 |

### 流量示例

```
47.84.113.76:8080/                    → 127.0.0.1:5000/           portal 首页
47.84.113.76:8080/ads/                → 127.0.0.1:5001/           广告漏斗分析首页
47.84.113.76:8080/toolkit/api/tools   → 127.0.0.1:5002/api/tools  toolkit API
```

## 目录结构

```
C:\Users\admin\Desktop\python\
├── amz_portal\      ← 本项目，端口 5000
├── ads_dashboard\   ← 广告漏斗分析，端口 5001
└── amazon_toolkit\  ← 运营工具箱，端口 5002
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `portal.py` | FastAPI 单文件应用，内联 HTML，端口 5000 |
| `nginx.conf` | Nginx 反代配置，复制到服务器 `/etc/nginx/conf.d/` |

## 部署

```bash
sudo cp nginx.conf /etc/nginx/conf.d/amazon-tools.conf
sudo nginx -t
sudo systemctl reload nginx
```
