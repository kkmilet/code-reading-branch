# 启动链路（Runbook）的写法

目标：让用户**不开项目也能知道怎么跑起来**，卡住时还知道自己卡在哪一步。

前提：本 Skill 不执行任何命令。所有结论来自静态阅读，因此必须标置信度。

## 证据优先级

按可信度从高到低找：

1. `README.md` / `docs/` 的 Quick Start —— 【文档明示】
2. `docker-compose.yml` / `Dockerfile` —— 最诚实，因为它必须能跑
3. `Makefile` / `Procfile` / `justfile` / `Taskfile` —— 团队实际用的入口
4. `.env.example` / `.env.sample` / `config.example.*` —— 缺哪个变量会崩
5. 配置入口：`settings.py` / `config/` / `application.yml` / `internal/config`
6. 依赖清单：`pyproject.toml` / `requirements.txt` / `go.mod` / `package.json`
7. 迁移目录：`migrations/` / `alembic/` / `db/migrate/`

冲突时以 `docker-compose.yml` 为准，并在表里注明"README 说 X，compose 说 Y"。

## 六段结构

固定六段，缺哪段写"未找到证据"。

| # | 段 | 找什么 |
|---|---|---|
| 1 | 语言与版本 | `requires-python`、`go 1.x`、`engines` |
| 2 | 系统依赖 | 数据库、缓存、MQ、需要编译的 C 扩展（`psycopg2`→`pg_config`、`mysqlclient`→`libmysqlclient-dev`） |
| 3 | 环境变量 | `.env.example` 每一项，标出**哪些没默认值**（没默认值 = 缺了就崩） |
| 4 | 依赖安装 | pip / poetry / uv / pnpm / yarn / go mod，有没有私有源 |
| 5 | 数据准备 | 建库、迁移命令、种子数据脚本 |
| 6 | 启动与验证 | 启动命令 + **怎么确认它真起来了**（访问哪个 URL、看到什么） |

## 每条必须带"错了会看到什么"

这一列是整个模板的核心。新手看到报错能立刻对上号，就知道自己卡在哪。

```markdown
| # | 步骤 | 命令 / 配置 | 证据 | 错了会看到 |
|---|---|---|---|---|
| 1 | Python 3.11+ | `requires-python = ">=3.11"` | `pyproject.toml:18` | `SyntaxError` 指向 `match` 语句 |
| 2 | PostgreSQL 14+ | `image: postgres:14` | `docker-compose.yml:12` | `connection refused` on `:5432` |
| 3 | 复制环境变量 | `cp .env.example .env` | `README.md:31` | `KeyError: 'SECRET_KEY'` |
| 4 | 装依赖 | `pip install -r requirements.txt` | `requirements.txt` | `pg_config not found` → 先装 postgresql-dev |
| 5 | 建表 | `python manage.py migrate` | `Makefile:8` | `relation "orders_order" does not exist` |
| 6 | 启动 | `python manage.py runserver` | `README.md:38` | 访问 `/healthz` 应 200；404 说明路由没注册 |
```

## 常见栈的错误对照

写的时候对照，别漏高频坑：

| 栈 | 高频坑 | 典型报错 |
|---|---|---|
| Python | 版本不符 / C 扩展缺系统库 / 虚拟环境没激活 | `ModuleNotFoundError`、`pg_config not found` |
| Django | 没 migrate / `DJANGO_SETTINGS_MODULE` 没设 / 静态文件 | `relation does not exist`、`ImproperlyConfigured` |
| FastAPI | 启动路径写错（应为 `uvicorn app.main:app`）/ 端口 | `Error loading ASGI app` |
| Go | 没跑 `go mod download` / CGO / 私有模块 | `missing go.sum entry`、`cannot find package` |
| Node | Node 版本 / lock 冲突 / 原生模块编译 | `EBADENGINE`、`node-gyp` 失败 |
| 通用 | 端口占用 / 权限 / 时区 | `EADDRINUSE`、`permission denied` |

## 配置的覆盖顺序（有分层配置的项目必写）

新手最常问的是"这个值到底从哪来"。单独列一条覆盖链，**后面的覆盖前面的**：

```markdown
### 配置从哪来（后者覆盖前者）
1. `config/settings/base.py` — 默认值都在这里
2. `config/settings/local.py` — 本地覆盖（DEBUG、数据库地址）
3. `.env` — 环境变量，由 `settings.py:24` 的 `env()` 读取
4. 启动时的 shell 环境变量 — 优先级最高
```

不写这一节，用户改了 `.env` 却不生效时，会一直找不到原因。Node 项目同理：`config/default.json` → `config/local.json` → `process.env`。

## 证据位置怎么写

- **不进站、不加注释的文件**（`pyproject.toml`、`README.md`、`docker-compose.yml`）：写 `文件:行号`
- **站内会被注释的文件**（`settings.py`、`config.py`）：写「文件 · 字段名/符号」，**不写行号**——注释插入后行号会整体下移，你写的时候对，读者看的时候已经错了

## 置信标签

每条结尾标一个：

- 【文档明示】README 或注释里写了的
- 【代码推断】从配置/依赖清单推出来的
- 【未知】找不到证据，写清"缺什么证据才能确认"

**不要用【代码推断】冒充【文档明示】**。用户要能一眼看出哪些是项目自己说的，哪些是推的。

## 对话里怎么说

不要在对话里复述整张表。只说：

> 6 步已经写进 `READING.md` 第 1 节。第 4 步最容易卡——`psycopg2` 要系统里有 `pg_config`，报错长这样：`pg_config not found`。
> 要不要我先带你把这 6 步过一遍？

## 不要做的事

- 不写"应该能跑""一般没问题"这种没证据的判断
- 不假装跑过（用户会照做失败，然后不再信任整份文档）
- 不省略系统依赖（这是新手最常卡的地方）
- 不把 `docker compose up` 当成唯一答案（很多项目 compose 里只有数据库，应用要本地跑）
