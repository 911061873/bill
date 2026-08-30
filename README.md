# 记账助手后端

FastAPI + Tortoise ORM 的微信小程序记账服务，支持 Docker 部署、GitHub Actions 自动构建，以及内置管理员后台。

## 功能入口

- 小程序 API：`/api`
- OpenAPI 文档：`/docs`
- 健康检查：`/health`
- 管理员后台：`/admin`

管理员后台提供数据概览、用户列表、借款人改名/删除、账单编辑/删除和用户删除。修改或删除账单后，用户和借款人的汇总金额会自动重新计算。

## 本地 Docker 部署

1. 创建配置文件：

   ```bash
   cp .env.example .env
   ```

2. 修改 `.env`，至少填写微信参数及三个管理员参数。可用下面的命令生成会话密钥：

   ```bash
   openssl rand -hex 32
   ```

3. 构建并启动：

   ```bash
   docker compose up -d --build
   ```

4. 打开 `http://服务器地址:8000/admin`。运行数据保存在 Docker 卷 `bill-data` 中，更新容器不会丢失。

查看状态和日志：

```bash
docker compose ps
docker compose logs -f bill
```

## 使用已有 SQLite 数据

仓库中的旧数据库位于 `src/db.sqlite3`。先停止旧服务，并用 SQLite 的 backup API 生成一致性快照（这也会合并 WAL 中尚未写回的数据）：

```bash
python -c "import sqlite3; s=sqlite3.connect('src/db.sqlite3'); d=sqlite3.connect('db.deploy.sqlite3'); s.backup(d); d.close(); s.close()"
docker compose build
docker compose create bill
docker compose cp db.deploy.sqlite3 bill:/app/data/db.sqlite3
docker compose start bill
```

确认数据完整后可删除临时的 `db.deploy.sqlite3`。执行迁移前仍建议额外备份原数据库。数据库文件、WAL 文件和 `.env` 已加入忽略列表，不会被提交到 GitHub。

## GitHub CI/CD 镜像构建

工作流位于 `.github/workflows/docker.yml`：

- Pull Request：只验证多架构镜像可以构建，不推送；
- 推送到 `main` 或 `master`：构建并推送 `ghcr.io/<GitHub用户名>/<仓库名>:latest`；
- 推送 `v*` 标签：额外生成对应版本标签；
- 同时支持 `linux/amd64` 和 `linux/arm64`。

将项目初始化并推送到 GitHub：

```bash
git init
git add .
git commit -m "Add Docker deployment, CI and admin console"
git branch -M main
git remote add origin https://github.com/<用户名>/<仓库名>.git
git push -u origin main
```

工作流使用 GitHub 自动提供的 `GITHUB_TOKEN`，不需要另建 Registry 密钥。首次推送后，在仓库的 **Packages** 中确认镜像；如服务器需要匿名拉取，把 Package visibility 设为 Public。私有镜像则先在服务器执行 `docker login ghcr.io`。

服务器使用 CI 生成的镜像：

```bash
IMAGE_NAME=ghcr.io/<用户名>/<仓库名>:latest docker compose pull
IMAGE_NAME=ghcr.io/<用户名>/<仓库名>:latest docker compose up -d --no-build
```

也可以把 `IMAGE_NAME=ghcr.io/<用户名>/<仓库名>:latest` 写进服务器上的 `.env`。

## 环境变量

| 变量 | 用途 | 必填 |
| --- | --- | --- |
| `WX_APPID` | 微信小程序 AppID | 是 |
| `WX_SECRET` | 微信小程序 Secret | 是 |
| `ADMIN_USERNAME` | 后台用户名 | 是 |
| `ADMIN_PASSWORD` | 后台密码 | 是 |
| `ADMIN_SESSION_SECRET` | 后台会话签名密钥，建议至少 32 字节 | 是 |
| `ADMIN_SESSION_HOURS` | 后台登录有效小时数 | 否，默认 12 |
| `ADMIN_COOKIE_SECURE` | HTTPS 部署时设为 `true` | 否，默认 false |
| `DATABASE_URL` | Tortoise 数据库连接地址 | 否，容器默认使用持久卷中的 SQLite |
| `TOKEN_EXPIRE_HOURS` | 小程序令牌有效小时数 | 否，默认 2 |
| `PORT` | Docker Compose 对外端口 | 否，默认 8000 |

未配置三个 `ADMIN_*` 登录参数时，后台页面可打开，但登录接口会返回 503，避免使用不安全的默认口令。

## 非 Docker 开发

需要 Python 3.12 和 [uv](https://docs.astral.sh/uv/)：

```bash
uv sync --frozen
cp .env.example .env
uv run --env-file .env uvicorn jz.main:app --app-dir src --reload --port 8000
```
