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

## 项目开关与重启

已接入的六个项目各有一个启动/暂停开关和一个重启按钮。开关开启时启动服务，关闭时停止服务进程；这里的“暂停”不是冻结进程，也不会修改开机自启设置。状态每 3 秒刷新，执行操作期间禁用该项目的控制按钮，失败后显示原因。状态仍以端口监听为准，不代表数据库、授权或全部业务接口健康。

启动优先使用项目自己的 `.venv` 或 `venv` Python，找不到时使用门户的 Python。默认项目位于门户的同级目录：

| 服务 ID | 项目目录 | 端口 | 启动入口 |
| --- | --- | --- | --- |
| `products` | `product_catalog` | 5003 | `start.py` |
| `ads` | `ads_dashboard/ads_funnel` | 5001 | `python -m uvicorn api.main:app --host 127.0.0.1 --port 5001` |
| `toolkit` | `amazon_toolkit` | 5002 | `app.py` |
| `xiyou` | `xiyou_api` | 5004 | `start.py` |
| `amazon_official_sp` | `amazon_sp_api` | 8015 | `start.py` |
| `amazon_official_ads` | `amazon_ads_api` | 5010 | `python -m flask --app app run --host 127.0.0.1 --port 5010` |

可以用 `PORTAL_PROJECTS_ROOT` 指定所有项目的父目录，或用 `PORTAL_<服务ID大写>_DIR` 覆盖某个项目根目录，例如 `PORTAL_ADS_DIR=/opt/ads_dashboard`。广告漏斗仍在该目录下的 `ads_funnel` 中启动。

重启仅在 **门户服务端为 Linux** 时可用，必须在弹窗中确认；后端也会校验操作系统。门户停止项目后，在项目根目录执行：

```bash
chmod +x deploy.sh && ./deploy.sh
```

脚本以门户进程的用户身份执行，最长等待 10 分钟，并在脚本成功退出后检查端口。运行日志保存在门户的 `.portal-runtime/<服务ID>.log`。部分现有项目脚本包含 `pkill -f "python3 $APP"`，可能停止其他同名入口项目；页面会对此显示确认提示。推荐将各项目脚本的停止逻辑改成按项目目录或专属 PID 识别进程。

Linux 下会识别正在运行项目所属的 systemd 服务，并记录到 `.portal-runtime/`，暂停时调用 `systemctl stop`，防止 `Restart=always` 立即拉起。对于已停止、尚未被门户识别的 systemd 服务，配置 `PORTAL_<服务ID大写>_UNIT`，例如 `PORTAL_ADS_UNIT=ads-dashboard.service`，值须为服务器上真实的服务名；该 unit 的 `WorkingDirectory` 必须属于对应项目。重启部署后会将进程交回 systemd。门户用户需要相应的进程管理和 systemd 权限。

### 云端控制权限

本机直连可以直接使用开关。通过 Nginx 或远程访问时，需要在**门户进程环境**中配置 `PORTAL_CONTROL_TOKEN`，页面首次操作时输入这个管理员密钥；密钥仅保留在当前页面内存中。未配置时，远程访客仍能查看状态和进入项目，但控制按钮禁用。

```bash
export PORTAL_CONTROL_TOKEN='替换为随机生成的管理员密钥'
chmod +x deploy.sh && ./deploy.sh
```

若门户由 systemd 启动，请将密钥写入该服务使用的受限权限 `EnvironmentFile`，然后重启门户。沿用当前 Nginx 的 `X-Real-IP`、`X-Forwarded-For` 配置即可；远程密钥应通过 HTTPS 或可信隧道传输。

### 本地运行与验证

```bash
python -m pip install -r requirements.txt
python portal.py
python -m pytest tests -q -p no:cacheprovider
```

门户应保持单个 worker 运行，操作锁和执行状态保存在该进程中。Windows 支持启动/暂停，重启按钮禁用。
