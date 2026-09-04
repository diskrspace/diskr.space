# Diskr.space

Diskr.space 是一个硬盘文件管理工具：扫描指定目录，将文件路径、大小、时间、自动标签和 Hash 写入数据库，支持按标签搜索、查找重复文件并安全清理磁盘文件。

## 主要功能

- 扫描目录并记录文件元数据
- 根据文件内容 Hash 自动识别重复文件
- 按文件名、路径和自动标签搜索
- 重复文件分组展示，支持删除实际磁盘文件
- 扫描过程中仍可查询已完成的数据
- 首次使用时在设置页面配置扫描目录

## 使用 GitHub Release

下载最新的 `diskr.space-版本号.zip` 并解压。发布包已经包含后端程序和编译好的前端页面，用户不需要安装 Node.js。

```bash
cd diskr.space-3.0.1
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python diskrspace.py
```

打开 <http://127.0.0.1:1888/>，首次进入时先在设置页面填写扫描目录并保存，然后开始扫描。

`.env` 中只需要配置数据库连接和 Web 监听参数：

```dotenv
DISKRSPACE_DB_URI=sqlite:///./diskrspace.db
DISKRSPACE_WEB_IP=127.0.0.1
DISKRSPACE_WEB_PORT=1888
```

小型单机使用 SQLite 即可；长期运行或文件量较大时建议使用 PostgreSQL。

## Docker Compose

Docker 版本会把主机目录映射到容器 `/data`，并在数据库中预设该扫描目录：

```bash
DISKRSPACE_SCAN_DIR=/path/to/your/files docker compose up --build
```

打开 <http://localhost:1888>。由于重复文件删除会操作真实文件，请确保扫描目录映射为可读写。

## 从源码运行

```bash
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && npm run build
cd ..
python diskrspace.py
```

开发前端时可在 `frontend` 目录执行 `npm run dev`，Vite 会将 API 请求代理到后端。

## 从源码构建 Release

发布者在仓库根目录执行：

```bash
python scripts/build_release.py
```

脚本会构建前端并生成 `release/diskr.space-版本号.zip`，压缩包中包含本 README、后端源码和 `frontend/dist`，不包含开发用的 `docs` 文档。若前端依赖已安装，可使用：

```bash
python scripts/build_release.py --skip-frontend-install
```

## 反馈与技术说明

当前版本为 `3.0.1`。API 文档位于后端启动后的 `/docs`；项目技术说明见 [docs/introduction.md](docs/introduction.md)。
