# Python 异步、数据库驱动与事件循环踩坑笔记

> 本文档总结 Python asyncio 基本原理、常见数据库驱动的同步/异步实现差异、Selector/Proactor 事件循环模型，以及本项目在 Windows + psycopg3 + uvicorn 组合下遇到的实际问题与修复方案。

---

## 目录

1. [Python 异步机制概览](#1-python-异步机制概览)
2. [事件循环：Selector 与 Proactor](#2-事件循环selector-与-proactor)
3. [FastAPI / uvicorn / ASGI 中的事件循环](#3-fastapi--uvicorn--asgi-中的事件循环)
4. [数据库驱动：同步与异步](#4-数据库驱动同步与异步)
5. [本项目的数据库栈](#5-本项目的数据库栈)
6. [本次踩坑记录](#6-本次踩坑记录)
7. [排查与修复清单](#7-排查与修复清单)
8. [参考对照表](#8-参考对照表)

---

## 1. Python 异步机制概览

### 1.1 核心概念

| 概念 | 说明 |
|------|------|
| **协程 (coroutine)** | 用 `async def` 定义的函数；调用后返回协程对象，不会立刻执行 |
| **Task** | 把协程包装成可被调度的任务，交给事件循环执行 |
| **await** | 协程内的挂起点；把控制权交还给事件循环，等待 I/O 或子任务完成 |
| **Event Loop** | 调度中心：维护 Task 队列，监听 I/O 事件，在就绪时唤醒对应 Task |

### 1.2 执行流程（简化）

```
async def handler():
    user = await repo.get_by_email(email)   # ① 发起 DB 查询，挂起
    token = auth.encode(user.id)            # ② 纯 CPU，直接执行
    return token

# 调用链
uvicorn 收到 HTTP 请求
  → 创建 Task(handler)
  → Event Loop 运行 Task
  → 遇到 await repo.get_by_email → 挂起，注册 DB socket 监听
  → DB 响应到达 → 唤醒 Task → 继续执行
  → 返回 HTTP 响应
```

要点：

- **单线程**内通过协作式切换实现并发，不靠多线程抢 GIL。
- `await` 的不是「多线程并行」，而是「这段逻辑先等着，让 loop 去干别的」。
- 所有 `await` 的 I/O（HTTP、数据库、文件等）最终都依赖**同一个 Event Loop** 的 I/O 机制。

### 1.3 asyncio 与第三方 async 库的关系

- **asyncio**：标准库，提供 Event Loop、Task、Future、Stream 等基础设施。
- **FastAPI / Starlette**：在 asyncio loop 上跑 ASGI 应用，本身不创建 loop。
- **SQLAlchemy AsyncSession**：在 asyncio loop 上调度 ORM 操作，底层交给 DB 驱动。
- **数据库驱动**：真正与 PostgreSQL/MySQL 通信的一层；是否兼容当前 loop 类型，取决于驱动实现方式。

---

## 2. 事件循环：Selector 与 Proactor

Event Loop 的差别，本质在于 **「如何等待 I/O 完成」**。

### 2.1 SelectorEventLoop（就绪通知 / Reactor 模型）

**问操作系统：哪些 fd 已经可读/可写了？**

```
协程 await read()
  → Loop 注册「socket 可读」监听
  → OS（select/epoll/kqueue）返回：这个 fd 可读
  → Loop 唤醒 Task，调用 recv() 读数据
  → 协程继续
```

| 平台 | 底层 API |
|------|----------|
| Linux | `epoll` |
| macOS / BSD | `kqueue` |
| 通用 fallback | `select` / `poll` |
| Windows | `select()`（能力有限，仅 socket 等） |

Python 类名：`asyncio.SelectorEventLoop`  
Unix/macOS 上通常是默认选择。

### 2.2 ProactorEventLoop（完成通知 / Proactor 模型）

**告诉操作系统：帮我把 I/O 做完，完成后通知我。**

```
协程 await read()
  → Loop 向 IOCP 提交「读 socket 到 buffer」
  → OS / 线程池在后台完成实际 I/O
  → 完成时通知 Loop
  → Loop 把结果交给协程
```

| 平台 | 底层 API |
|------|----------|
| Windows | IOCP（I/O Completion Ports） |

Python 类名：`asyncio.ProactorEventLoop`  
**Python 3.8+ 在 Windows 上为默认 Event Loop 类型**（因 Windows 上 `select()` 限制较多，IOCP 更 native）。

### 2.3 对比小结

| | SelectorEventLoop | ProactorEventLoop |
|---|---|---|
| 模型 | 就绪型（Reactor） | 完成型（Proactor） |
| 典型问题 | 「现在能读了吗？」 | 「读完了，结果是这个」 |
| 主要平台 | Linux / macOS 默认 | **Windows 默认** |
| 实际读写在 | 唤醒后由 asyncio/驱动执行 | 常由 OS/线程池后台完成 |

### 2.4 Event Loop Policy

`asyncio.set_event_loop_policy()` 决定 **新创建的 loop 是什么类型**：

```python
# Windows 上强制后续 new_event_loop() 使用 Selector
import asyncio, sys
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

注意：Policy 只影响「通过 policy 创建的 loop」。若框架**显式**传入 `loop_factory=asyncio.ProactorEventLoop`，会绕过 policy——这正是 uvicorn 的默认行为（见第 6 节）。

---

## 3. FastAPI / uvicorn / ASGI 中的事件循环

### 3.1 调用链

```
客户端 HTTP 请求
    ↓
uvicorn（ASGI 服务器）
    ↓ 在同一 Event Loop 中
await app(scope, receive, send)    ← FastAPI / Starlette
    ↓
await login(...)                   ← 路由函数
    ↓
await session.scalar(...)          ← SQLAlchemy AsyncSession
    ↓
await psycopg3 连接读写             ← 数据库驱动
```

**整条链路共用一个 Event Loop。** 任一环节与 loop 类型不兼容，整个请求就会失败。

### 3.2 ASGI 三参数

| 参数 | 含义 |
|------|------|
| `scope` | 请求元信息（method、path、headers 等） |
| `receive` | 异步 callable，读取请求 body |
| `send` | 异步 callable，发送响应 |

uvicorn 负责 HTTP 解析与 TCP I/O，把请求转成 ASGI 格式交给 FastAPI；FastAPI 不直接处理 socket。

### 3.3 uvicorn 如何创建 Event Loop

uvicorn 启动时大致等价于：

```python
asyncio.run(server.serve(), loop_factory=config.get_loop_factory())
```

`loop` 参数与 `get_loop_factory()` 的对应关系：

| `loop` 值 | 行为 |
|-----------|------|
| `"auto"`（默认） | Windows → `ProactorEventLoop`；Unix → `SelectorEventLoop` |
| `"asyncio"` | 同上 |
| `"none"` | `loop_factory=None`，由 `asyncio.run()` 按 **Event Loop Policy** 创建 |
| `"uvloop"` | Linux/macOS 可用，性能更好（Windows 不可用） |

源码位置（uvicorn `loops/asyncio.py`）：

```python
def asyncio_loop_factory(use_subprocess: bool = False):
    if sys.platform == "win32" and not use_subprocess:
        return asyncio.ProactorEventLoop   # Windows 硬编码
    return asyncio.SelectorEventLoop
```

---

## 4. 数据库驱动：同步与异步

### 4.1 通用分层

```
应用代码（FastAPI 路由）
    ↓
SQLAlchemy Session / AsyncSession（ORM 层）
    ↓
DBAPI 驱动（psycopg / asyncpg / aiomysql / pymysql …）
    ↓
数据库服务器（PostgreSQL / MySQL …）
```

- **同步**：调用阻塞，线程卡住直到 DB 返回；在 async 路由里直接调会**阻塞整个 Event Loop**。
- **异步**：在 `await` 处挂起，loop 可去处理其他 Task；必须与当前 loop 的 I/O 模型兼容。

### 4.2 常见组合（个人常用 vs 本项目）

| 数据库 | 异步驱动 | 同步驱动 | SQLAlchemy URL scheme |
|--------|----------|----------|------------------------|
| PostgreSQL | **asyncpg** | psycopg2 | `postgresql+asyncpg://` / `postgresql+psycopg2://` |
| PostgreSQL | **psycopg3** | psycopg3（同包） | `postgresql+psycopg://` |
| MySQL | aiomysql | pymysql | `mysql+aiomysql://` / `mysql+pymysql://` |

### 4.3 驱动实现差异（为何有的驱动「挑」Event Loop）

#### asyncpg

- 专为 asyncio 设计，大量逻辑在 Cython 层独立实现。
- 不强烈依赖 asyncio 的 Selector/Proactor 抽象。
- **Windows + ProactorEventLoop 通常无感**，这也是很多人从未踩过 loop 坑的原因。

#### psycopg3（异步）

- 官方 PostgreSQL 下一代驱动；**同一包**支持同步 `psycopg.connect()` 与异步 `psycopg.AsyncConnection`。
- 异步路径基于 asyncio 标准 socket 集成，按 **Selector/Reactor** 思路实现。
- **明确不支持 Windows 上的 ProactorEventLoop**，检测到会直接 `InterfaceError`。

#### psycopg2 / pymysql（同步）

- 阻塞式 DBAPI；在 `async def` 路由中应通过 `run_in_executor` 或改用异步驱动，否则会阻塞 loop。

#### aiomysql

- 在 asyncio 上封装 pymysql 协议；一般与 Selector 模型配合良好，Windows 上较少出现 Proactor 冲突。

### 4.4 SQLAlchemy 2.x 异步注意点

```python
# 异步引擎
engine = create_async_engine("postgresql+psycopg://...")
AsyncSessionFactory = sessionmaker(bind=engine, class_=AsyncSession)

async with AsyncSessionFactory() as session:
    result = await session.scalar(select(User).where(...))
```

- ORM API 与同步版类似，但所有 DB 操作必须 `await`。
- 部分内部仍用 `greenlet_spawn` 桥接，但对外仍是 async/await 模型。
- **换驱动 = 换 URL scheme + 换 pip 包**，ORM 代码通常不用大改。

---

## 5. 本项目的数据库栈

### 5.1 当前选型

| 项 | 值 |
|----|-----|
| 驱动 | **psycopg 3**（`psycopg[binary]>=3.3.4`） |
| SQLAlchemy URL | `postgresql+psycopg://user:pass@host:port/db` |
| ORM | SQLAlchemy 2.x `AsyncSession` + `create_async_engine` |
| 配置位置 | `settings/__init__.py` → `DBSettings.DATABASE_URL` |
| 引擎创建 | `models/__init__.py` |

### 5.2 为何选 psycopg3 而非 asyncpg

1. **SQLAlchemy 2.0** 官方主推 `postgresql+psycopg` dialect。
2. **LangGraph** 依赖 `langgraph-checkpoint-postgres`，其底层绑定 **psycopg3 + psycopg-pool**，与业务 ORM 可统一驱动栈。
3. 同步/异步同一包，迁移脚本（Alembic）、初始化脚本（`init_data.py`）可共用连接配置。

### 5.3 与 asyncpg 方案的权衡

| | psycopg3（当前） | asyncpg |
|---|---|---|
| 异步性能 | 够用，非最快 | 通常更快 |
| Windows 异步 | 需 Selector loop | 一般开箱即用 |
| LangGraph checkpoint | 原生支持 | 需额外保留 psycopg3 |
| 依赖数量 | 一套驱动 | ORM 与 AI 栈可能两套驱动 |

---

## 6. 本次踩坑记录

### 6.1 现象

服务能启动，访问 `POST /user/login` 返回 **500**：

```
sqlalchemy.exc.InterfaceError: (psycopg.InterfaceError)
Psycopg cannot use the 'ProactorEventLoop' to run in async mode.
Please use a compatible event loop, for instance by running
'asyncio.run(..., loop_factory=asyncio.SelectorEventLoop(...))'
```

栈追踪指向：`user_router.login` → `user_repo.get_by_email` → `session.scalar` → psycopg 建连。

### 6.2 根因（两层叠加）

**第一层：Windows 默认 ProactorEventLoop**

- Python 3.8+ 在 Windows 默认使用 `ProactorEventLoop`。
- psycopg3 异步 **拒绝** 在该 loop 上运行。

**第二层：uvicorn 显式强制 ProactorEventLoop**

- 即使设置了 `WindowsSelectorEventLoopPolicy()`，uvicorn 默认 `loop="auto"` 仍会传入 `loop_factory=asyncio.ProactorEventLoop`，**绕过 policy**。
- 因此在 `main.py` 里只写 policy **不够**。

### 6.3 为何 init_data.py / alembic 没问题，Web 服务却挂

| 入口 | 事件循环创建方式 | 结果 |
|------|------------------|------|
| `init_data.py` | `asyncio.run(main())` + 已设 Selector policy | 正常 |
| `alembic/env.py` | 同上 | 正常 |
| `main.py`（修复前） | `uvicorn.run()` → 强制 Proactor | **失败** |

### 6.4 修复方案（本项目已采用）

`main.py`：

```python
import asyncio
import sys

# Windows 下 psycopg 异步模式不支持 ProactorEventLoop，需切换为 SelectorEventLoop
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

def main():
    # loop="none" 让 uvicorn 使用系统 event loop policy，避免 Windows 上强制 ProactorEventLoop
    uvicorn.run(app, host="127.0.0.1", port=8000, loop="none")
```

缺一不可：

1. **Policy**：让 `asyncio.run()` 创建 Selector 型 loop。
2. **`loop="none"`**：禁止 uvicorn 硬编码 ProactorEventLoop。

### 6.5 附带问题：JWT 包名错误

修复 loop 后登录走到发 token 时曾报：

```
AttributeError: module 'jwt' has no attribute 'encode'
```

- `pyproject.toml` 误依赖了 **`jwt`** 包（与 PyJWT 同名冲突）。
- 应使用 **`pyjwt`**，`import jwt` 才是 `encode` / `decode` API。

---

## 7. 排查与修复清单

### 7.1 判断是否为此类问题

- 平台：**Windows**
- 驱动：**psycopg3 异步**（`postgresql+psycopg://`）
- 服务器：**uvicorn**
- 报错含：`ProactorEventLoop`、`Psycopg cannot use`

### 7.2 快速验证 loop 类型

```python
import asyncio, sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

async def check():
    print(type(asyncio.get_running_loop()).__name__)

asyncio.run(check())
# 期望：_WindowsSelectorEventLoop
# 问题：ProactorEventLoop
```

### 7.3 其他可选方案

| 方案 | 说明 |
|------|------|
| 换 asyncpg | ORM URL 改为 `postgresql+asyncpg://`；LangGraph 仍可能需要 psycopg3 |
| WSL / Linux 部署 | 默认 Selector，通常无此问题 |
| 生产用 Docker Linux 镜像 | 开发在 Windows 需注意，部署环境往往不受影响 |

### 7.4 开发环境建议

- Windows 本地开发：保持 `main.py` 中 policy + `loop="none"`。
- 使用 CLI 启动 uvicorn 时同样加参数：`uvicorn main:app --loop none`（Windows 下仍需先设 policy，或写在应用导入前）。
- `init_data.py`、`alembic/env.py` 已含 Windows policy，与 Web 入口保持一致。

---

## 8. 参考对照表

### 8.1 概念速查

| 术语 | 一句话 |
|------|--------|
| 协程 | `async def`，可挂起/恢复的逻辑单元 |
| Task | 交给 loop 调度执行的协程 |
| Event Loop | 调度 Task + 等待 I/O 的核心 |
| Selector | 「fd 就绪了吗？」 |
| Proactor | 「I/O 做完了，结果是？」 |
| ASGI | Python 异步 Web 服务器与应用之间的标准接口 |

### 8.2 本项目相关文件

| 文件 | 作用 |
|------|------|
| `main.py` | Web 入口；Windows loop 修复 |
| `settings/__init__.py` | `DATABASE_URL`（`postgresql+psycopg://`） |
| `models/__init__.py` | 异步引擎与会话工厂 |
| `init_data.py` | 初始化数据；含 Windows Selector policy |
| `alembic/env.py` | 迁移；含 Windows Selector policy |
| `pyproject.toml` | `psycopg[binary]`、`langgraph-checkpoint-postgres` 等依赖 |

### 8.3 请求链路图（Mermaid）

```mermaid
sequenceDiagram
    participant Client
    participant Uvicorn
    participant Loop as Event Loop
    participant FastAPI
    participant SA as SQLAlchemy AsyncSession
    participant PG as psycopg3

    Client->>Uvicorn: HTTP POST /user/login
    Uvicorn->>Loop: 等待 socket 可读
    Loop->>Uvicorn: 请求就绪
    Uvicorn->>FastAPI: await app(scope, receive, send)
    FastAPI->>SA: await session.scalar(...)
    SA->>PG: await 异步查询
    PG->>Loop: 等待 DB socket（需 Selector）
    Loop->>PG: I/O 就绪
    PG->>SA: 返回行数据
    SA->>FastAPI: User 对象
    FastAPI->>Uvicorn: JSON 响应
    Uvicorn->>Client: 200 OK
```

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-20 | 初版：整理 Python 异步、Selector/Proactor、数据库驱动差异及本项目 Windows 踩坑与修复 |
