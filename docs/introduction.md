# Diskr.space 技术说明

Diskr.space 已迁移到 FastAPI + Vue 3 前后端分离架构。本文介绍项目结构、配置和部署要点；面向普通用户的安装和使用方法请参阅根目录 [README](../README.md)。

## 项目结构

- `web/`：FastAPI 应用和 API 路由
- `db/`：SQLAlchemy 模型、扫描器和数据访问层
- `frontend/`：Vue 3 + Vite 前端
- `scripts/build_release.py`：构建可发布 ZIP

后端接口文档在服务启动后可通过 `/docs`（Swagger UI）或 `/openapi.json` 获取。

## 数据库与并发

生产环境推荐 PostgreSQL 16；SQLite 会启用 WAL 和 busy timeout，适合小型单机库，但仍只有一个写者。

扫描器不在数据库事务中执行文件 Hash 和目录汇总，元数据、Hash 和目录统计均采用短事务分批提交。因此扫描期间查询可以读取最近一次已提交的数据，不会被长事务锁住。

业务配置 `work_dir`、`quick_hash_size` 和 `scan_interval` 保存在数据库 `sysinfo` 表中。`.env` 只保存数据库连接和 Web 监听参数。
