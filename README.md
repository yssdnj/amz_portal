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

### 门户登录与控制权限

门户使用独立的账号登录会话保护首页、状态 API、项目服务 API，以及 Nginx 下的所有 `/amazon/` 页面和 API。已配置账号权限相同，登录成功后即可使用启动、暂停和重启控制，不再需要额外的管理员控制密钥。会话有效期为 12 小时，退出登录会立即清除会话。

从示例创建仅供本项目使用的 `.env`，并限制文件权限：

```bash
cp .env.example .env
chmod 600 .env
chmod +x deploy.sh && ./deploy.sh
```

必须配置 `PORTAL_LOGIN_USERNAME`、`PORTAL_LOGIN_PASSWORD` 和 `PORTAL_SESSION_SECRET`；缺少任意一项时门户会明确拒绝启动。生产 HTTPS 网关应设置 `PORTAL_COOKIE_SECURE=true`。`.env` 已被 Git 忽略，不要提交或输出其中的真实密码和会话密钥。

共享网关使用 `amazon.conf` 中独立的 `/_amazon_session` 子请求验证 Amazon 会话。`/amazon/login`、登录提交和退出接口公开；其他 Amazon 页面在未登录时跳转到 `/amazon/login`，API 保持 `401`。该配置不依赖或修改 stock 门户会话。

可选配置 `PORTAL_EXTRA_USERS` 为额外账号到密码的 JSON 对象，保留原主账号。例如下面仅为虚构配置：

```dotenv
PORTAL_EXTRA_USERS='{"example-user":"replace-with-a-unique-password"}'
```

未配置或 `{}` 表示没有额外账号。非法 JSON、非对象、重复账号、主账号重名和空账号/密码会拒绝启动，错误信息不包含配置内容。账号名大小写和空格准确匹配，不自动裁剪。修改配置后重启门户；删除账号后，该账号旧会话不能继续访问。

门户首页右上角显示经过服务端会话验证的当前账号，旁边的太阳/月亮按钮切换明暗外观。初次默认暗色，选择保存在当前浏览器，同源标签页同步，登录页和首页共用；后续项目的主题不受影响。浏览器不允许存储时仍可切换，但刷新后不保证保留。

### 后续项目的用户身份校验

后续项目后端可向固定地址 `http://127.0.0.1:5000/api/auth/user` 发送 GET，并携带浏览器原请求的 Cookie。有效登录返回 `200` 和仅含字符串 `user_id` 的 JSON；未登录、无效签名、过期、缺少身份或身份不匹配返回 `401`。响应设置 `Cache-Control: no-store`。

用户 ID 来自已验证的配置账号，与密码、浏览器和会话密钥无关；各账号身份不同，修改账号名称会产生新的 ID。原主账号含有效 `user_id` 的会话继续有效；旧版本只含登录标记而无身份的会话需重新登录。原 `/api/auth/check` 的 `204/401` 约定不变，各受保护入口均要求身份属于当前配置账号。

调用地址必须由后续项目服务端固定配置，不能由前端请求指定。后续项目只信任门户成功校验后的 `user_id`，不信任客户端身份头，也不共享门户签名密钥。Cookie 不写入日志；不缓存其他用户的身份，也不向浏览器转发身份接口返回的 Set-Cookie。校验超时、连接失败或响应格式不正确时，不得保存账户偏好。

通过 HTTPS 网关访问 `/amazon/official-sp/` 时，门户 Cookie 的 `/` 或 `/amazon/` Path 均覆盖 SP 路由，浏览器会自动携带 Cookie，前端无需读取它。直连 HTTP `127.0.0.1:8015` 通常没有适用的门户 Secure Cookie，未验证身份时只允许临时调整，不保存账户偏好。跨主机部署需另行配置受保护的身份校验传输。

退出登录清除浏览器 Cookie。本项目继续使用原有签名会话，不提供复制保存的旧 Cookie 的服务端即时撤销。

### 本地运行与验证

```bash
python -m pip install -r requirements.txt
python portal.py
python -m pytest tests -q --basetemp .test-runs/pytest-simple-login -p no:cacheprovider
```

门户应保持单个 worker 运行，操作锁和执行状态保存在该进程中。Windows 支持启动/暂停，重启按钮禁用。
