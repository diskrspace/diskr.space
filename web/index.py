"""FastAPI application for the separated Diskr.space frontend."""
import logging
import os
import shutil
from pathlib import Path
from typing import Generator

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.responses import FileResponse

from db import Config, api as scan_api, scan, web
from db.common import format_size
from db.model import FileInfo, create_session
from web import __version__

logger = logging.getLogger(__name__)
config = Config.load("web")


def get_db() -> Generator[Session, None, None]:
    session = create_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class SettingsUpdate(BaseModel):
    work_dir: str
    quick_hash_size: str = "0"
    scan_interval: int = 86400
    confirm: bool = False


app = FastAPI(title="Diskr.space API", version=__version__)
origins = config.get("CORS_ORIGINS", ["http://localhost:5173", "http://127.0.0.1:5173"])
if isinstance(origins, str):
    origins = [item.strip() for item in origins.split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
router = APIRouter(prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__}


@router.get("/status")
def get_status(db: Session = Depends(get_db)):
    info = web.get_status(db) or {}
    info["work_dir"] = web.get_setting(db, "work_dir") or ""
    info["size"] = format_size(info.get("size") or 0)
    return info


@router.post("/scan", status_code=202)
def post_scan(db: Session = Depends(get_db)):
    work_dir = web.get_setting(db, "work_dir")
    if not work_dir:
        raise HTTPException(status_code=400, detail="请先在设置中配置扫描目录")
    message = scan_api.reset_scanner(db)
    if message is None:
        try:
            message = scan.spawn_scanner(work_dir)
        except RuntimeError as exc:
            message = str(exc)
    return {"message": message}


@router.get("/scan/progress")
def get_scan_progress(db: Session = Depends(get_db)):
    scan_api.reset_scanner(db)
    progress = web.get_progress(db)
    if not progress:
        scan_api.set_progress(db, {"progress": "100", "cur_path": "", "speed": "0"})
        progress = web.get_progress(db)
    return progress


@router.get("/files/search")
def search_files(tags: str = Query(min_length=1), page: int = Query(0, ge=0),
                 db: Session = Depends(get_db)):
    tag_list = [tag.strip() for tag in tags.replace(" ", ",").split(",") if tag.strip()]
    return {"items": web.get_search(db, tag_list[:8], page), "page": page}


@router.get("/duplicates")
def get_duplicates(since_size: int = Query(0, ge=0), only_dirs: bool = False,
                   db: Session = Depends(get_db)):
    return {"items": web.get_duplist(db, since_size, only_dirs=only_dirs)}


def _remove_file_or_dir(db: Session, file_id: int):
    work_dir = web.get_setting(db, "work_dir")
    if not work_dir:
        raise HTTPException(status_code=400, detail="尚未配置扫描目录")
    root = os.path.realpath(os.path.expanduser(work_dir))
    record = db.query(FileInfo).filter(FileInfo.id == file_id).first()
    if not record or not record.checksum:
        raise HTTPException(status_code=409, detail="文件不存在，或已经不再重复")
    relative_name = os.path.join(record.dirname, record.name)
    filename = os.path.abspath(os.path.join(root, relative_name))
    if os.path.commonpath((root, filename)) != root:
        raise HTTPException(status_code=400, detail="文件路径超出扫描目录")
    if not os.path.lexists(filename):
        raise HTTPException(
            status_code=409,
            detail="服务端进程找不到目标文件，请确认 work_dir 是服务端可访问的路径",
        )
    try:
        # Delete the real file first. The ORM transaction is committed only
        # after this succeeds, so a permission/mount error cannot look like a
        # successful deletion in the UI.
        if os.path.islink(filename) or not os.path.isdir(filename):
            os.unlink(filename)
        else:
            shutil.rmtree(filename)
        removed_name = web.remove_dup(db, file_id, root)
        if not removed_name:
            raise HTTPException(status_code=409, detail="重复记录已发生变化，请刷新页面")
        return relative_name
    except OSError as exc:
        logger.exception("Remove file failed: %s", filename)
        raise HTTPException(status_code=500, detail="删除文件失败，请检查权限或文件占用") from exc


@router.delete("/duplicates/{file_id}")
def delete_duplicate(file_id: int, db: Session = Depends(get_db)):
    return {"status": "ok", "name": _remove_file_or_dir(db, file_id)}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    return {
        "work_dir": web.get_setting(db, "work_dir") or "",
        "quick_hash_size": web.get_setting(db, "quick_hash_size"),
        "scan_interval": int(web.get_setting(db, "scan_interval")),
    }


@router.put("/settings")
def put_settings(settings: SettingsUpdate, db: Session = Depends(get_db)):
    previous = web.get_setting(db, "work_dir") or ""
    if previous != settings.work_dir and not settings.confirm:
        return {"confirm": "required"}
    if not settings.work_dir.strip():
        raise HTTPException(status_code=422, detail="扫描目录不能为空")
    web.set_setting(db, "work_dir", settings.work_dir)
    if previous != settings.work_dir:
        # The next scan must mark every entry so records from the old root are
        # removed only after the new root has been indexed successfully.
        web.set_setting(db, "last_scan", "1970-01-01 00:00:00")
    web.set_setting(db, "quick_hash_size", settings.quick_hash_size)
    web.set_setting(db, "scan_interval", settings.scan_interval)
    return {"status": "ok"}


app.include_router(router)


# When the Vue project has been built, serve its production bundle from the
# same FastAPI process.  API routes are registered above, so `/api/...` keeps
# its normal behavior while all other paths fall back to the SPA entrypoint.
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


def _frontend_file(path: str = ""):
    if not FRONTEND_DIST.is_dir():
        raise HTTPException(status_code=404, detail="前端资源尚未构建，请先运行 npm run build")
    requested = (FRONTEND_DIST / path).resolve()
    try:
        requested.relative_to(FRONTEND_DIST.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="资源不存在") from exc
    if requested.is_file():
        return FileResponse(requested)
    index = FRONTEND_DIST / "index.html"
    if index.is_file():
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="前端入口文件不存在")


@app.get("/", include_in_schema=False)
def frontend_index():
    return _frontend_file()


@app.get("/{path:path}", include_in_schema=False)
def frontend_assets(path: str):
    return _frontend_file(path)
