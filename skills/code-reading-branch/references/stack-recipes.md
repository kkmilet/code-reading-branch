# 各技术栈的入口识别

认栈之后按对应行找入口。找不到就退到"按目录结构推断"，并在输出里明说「未识别到框架入口，以下基于目录推断」。

## 认栈

| 特征 | 栈 |
|---|---|
| `manage.py` + `*/settings.py` | Django |
| `FastAPI(` 出现在 `main.py` / `app/main.py` | FastAPI |
| `create_app(` / `Blueprint(` | Flask |
| `go.mod` | Go |
| `package.json` + `@nestjs/core` | NestJS |
| `package.json` + `express` | Express / Node |

## 四类信号槽

每个栈都找这四类：**入口 / 数据 / 配置 / 横切**。

### Django

| 槽 | 找什么 |
|---|---|
| 入口 | `urls.py` 的 `path(` / `re_path(`；`views.py` 的 `def get/post/put`；`@shared_task`；`management/commands/*.py` |
| 数据 | `models.py` 的 `class X(models.Model)`；`migrations/` 只看首个迁移 |
| 配置 | `settings.py`、`settings/base.py`、`.env.example`、`MIDDLEWARE`、`INSTALLED_APPS` |
| 横切 | `MIDDLEWARE`、`AUTHENTICATION_BACKENDS`、`DEFAULT_PERMISSION_CLASSES`、`ATOMIC_REQUESTS`、`signals.py`、`apps.py` 的 `ready()` |

```bash
grep -rn "path(" --include=urls.py .
grep -rn "class .*(models.Model)" --include=models.py .
grep -rn "@shared_task\|@app.task" --include=*.py .
```

### FastAPI

| 槽 | 找什么 |
|---|---|
| 入口 | `FastAPI(`、`APIRouter(`、`@router.get/post`、`include_router(`、`lifespan` |
| 数据 | `declarative_base()`、`class X(Base)`、`SQLModel`、`alembic/versions` |
| 配置 | `BaseSettings`、`settings = Settings()`、`.env` |
| 横切 | `Depends(`、`@app.middleware("http")`、`add_middleware`、`exception_handler` |

```bash
grep -rn "include_router\|APIRouter(" --include=*.py .
grep -rn "@router\.\(get\|post\|put\|delete\)" --include=*.py .
grep -rn "Depends(" --include=*.py . | head -30
```

### Flask

| 槽 | 找什么 |
|---|---|
| 入口 | `create_app(`、`Blueprint(`、`register_blueprint`、`@bp.route` |
| 数据 | `db.Model`、`class X(db.Model)`、`flask_migrate` |
| 配置 | `app.config.from_*`、`config.py`、`.env` |
| 横切 | `before_request`、`@app.errorhandler`、`flask_login` |

### Go

| 槽 | 找什么 |
|---|---|
| 入口 | `cmd/*/main.go`、`func main()`、`gin.Default()`、`r.GET(`、`mux.HandleFunc`、`http.ListenAndServe` |
| 数据 | `internal/` 下的 `repository` / `store`、`*.sql`、`ent/`、`AutoMigrate` |
| 配置 | `config/`、`internal/config`、`viper`、`os.Getenv` |
| 横切 | `middleware/`、`wire.Build`、`fx.Provide`、拦截器 |

```bash
ls cmd/*/main.go 2>/dev/null; grep -rn "func main()" --include=*.go .
grep -rn "\.GET(\|\.POST(\|HandleFunc(" --include=*.go . | head -30
```

### Express / Node

| 槽 | 找什么 |
|---|---|
| 入口 | `package.json` 的 `scripts`（启动命令在这）、`app.use(`、`express.Router()`、`router.get(`、`src/index.ts\|server.ts\|app.ts` |
| 数据 | `models/`、`prisma/schema.prisma`、`typeorm` 的 `@Entity`、`sequelize.define` |
| 配置 | `config/`、`dotenv`、`process.env` |
| 横切 | `app.use(中间件)`、错误处理中间件（4 个参数的那种） |

### NestJS

| 槽 | 找什么 |
|---|---|
| 入口 | `main.ts` 的 `NestFactory.create(`、`@Controller(`、`@Get/@Post` |
| 数据 | `@Entity(`、`prisma/schema.prisma`、`@InjectRepository` |
| 配置 | `ConfigModule`、`.env` |
| 横切 | `@UseGuards(`、`@UseInterceptors(`、全局 `APP_GUARD` |

## 找到入口之后

1. 记下 handler 名字，作为第 4 站的落点
2. 从 handler 往下追**一层**（它调了谁），这就是主链路的骨架
3. 追不到（动态注册、装饰器、DI 容器、`importlib`）→ 在 `READING.md` 标【存疑：动态注册，静态扫不到】

## 库 / SDK / CLI 项目（没有 Web 框架时）

很多 Agent、工具链、SDK 项目没有路由表。**不要硬找路由，也不要直接判"认不出入口"**——入口换了个形态而已。

| 槽 | 找什么 |
|---|---|
| 入口 | `[project.scripts]` / `console_scripts`（CLI 命令）；`__init__.py` 的 `__all__` 或顶层 `from .x import *`（公开 API）；README 里 `from pkg import X` 的那几个名字 |
| 数据 | `dataclass` / `TypedDict` / `pydantic.BaseModel` / `Enum`——通常是跨模块传递的核心结构 |
| 配置 | `pyproject.toml`、`setup.cfg`、`os.getenv` / `os.environ`、`Settings` 类 |
| 横切 | 装饰器（`@register` / `@tool`）、注册表 dict、`__init_subclass__`、插件加载 |

```bash
grep -n "\[project.scripts\]" -A6 pyproject.toml
grep -nE "^from \.|^__all__" src/*/__init__.py
grep -rn "^class .*\(.*Model\)\|@dataclass" src/ | head -20
```

**主链长什么样**：不是「HTTP → 路由 → 视图」，而是「公开 API → 核心对象 → 内部循环 → 回调外部」。
判断方法：README 的最小示例里，`pkg.Thing(...).run()` 那一行就是主链起点。

## 静态分析的天花板

以下情况静态扫不到，必须如实告知：

- Django 的 app 自动发现、`AppConfig.ready()` 里的信号注册
- 装饰器动态注册的路由（`@app.route` 拼出来的）
- DI 容器（wire / fx / Spring 风格）装配的依赖边
- `getattr` / `importlib` / 插件机制
- 元类、描述符、`__getattr__` 动态属性

遇到这些不要硬猜。写「该模块的注册是动态的，静态看不出调用关系，需要运行时确认」——这比编一条假链路有用。
