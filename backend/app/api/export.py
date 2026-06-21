import json
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.chapter import Chapter
from app.schemas.project import ProjectCreate
from app.services import export_service, novel_split_service, project_service
from app.services.export_service import (
    InvalidImportError,
    ProjectNotFoundForExportError,
)
from app.services.exporters import docx_exporter, epub_exporter, metadata_exporter, txt_exporter
from app.services.project_service import ProjectNameConflictError

router = APIRouter(prefix="/api", tags=["export"])

# 上传上限,与现有 import 一致
_MAX_UPLOAD = 50 * 1024 * 1024


def _decode_text(raw: bytes) -> str:
    """优先 UTF-8,失败兜底 GBK / GB18030(老 txt 多见)。"""
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    # 最后兜底,替换无法识别字节
    return raw.decode("utf-8", errors="replace")


def _content_disposition(name: str, ext: str) -> str:
    """构造支持中文文件名的 Content-Disposition,RFC 5987。"""
    cleaned = "".join(c for c in name if c not in '\\/:*?"<>|').strip() or "project"
    full = f"{cleaned}.{ext}"
    # ASCII 兜底:把非 ASCII 字符替换成下划线
    ascii_fallback = "".join(c if ord(c) < 128 else "_" for c in full)
    encoded = quote(full, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"


@router.get("/projects/{project_id}/export.json")
def export_project_json(project_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        data = export_service.export_to_dict(db, project_id)
    except ProjectNotFoundForExportError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e
    body = json.dumps(data, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": _content_disposition(data["project"]["name"], "json")},
    )


@router.get("/projects/{project_id}/export.md")
def export_project_markdown(project_id: int, db: Session = Depends(get_db)) -> Response:
    try:
        text = export_service.export_to_markdown(db, project_id)
    except ProjectNotFoundForExportError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在") from e
    # 取 project name 给 filename 用 JSON dict 重新查比较多余,这里直接用 markdown 第一行抠
    first_line = text.split("\n", 1)[0].lstrip("# ").strip() or "project"
    return PlainTextResponse(
        content=text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": _content_disposition(first_line, "md")},
    )


@router.get("/projects/{project_id}/export.epub")
def export_project_epub(project_id: int, db: Session = Depends(get_db)) -> Response:
    from app.models.project import Project

    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在")
    try:
        body = epub_exporter.export_to_epub(db, project_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return Response(
        content=body,
        media_type="application/epub+zip",
        headers={"Content-Disposition": _content_disposition(proj.name, "epub")},
    )


@router.get("/projects/{project_id}/export.metadata.json")
def export_project_metadata(project_id: int, db: Session = Depends(get_db)) -> Response:
    from app.models.project import Project

    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在")
    body = metadata_exporter.export_metadata_json(db, project_id)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": _content_disposition(f"{proj.name}-metadata", "json")},
    )


@router.get("/projects/{project_id}/export.kdp-listing.txt")
def export_project_kdp_listing(project_id: int, db: Session = Depends(get_db)) -> Response:
    from app.models.project import Project

    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在")
    body = metadata_exporter.export_kdp_listing(db, project_id)
    return Response(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": _content_disposition(f"{proj.name}-kdp-listing", "txt")},
    )


@router.get("/projects/{project_id}/export.docx")
def export_project_docx(project_id: int, db: Session = Depends(get_db)) -> Response:
    from app.models.project import Project

    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在")
    body = docx_exporter.export_to_docx(db, project_id)
    return Response(
        content=body,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={"Content-Disposition": _content_disposition(proj.name, "docx")},
    )


@router.get("/projects/{project_id}/export.txt")
def export_project_txt(
    project_id: int,
    encoding: str = "utf-8",
    mode: str = "whole",
    db: Session = Depends(get_db),
) -> Response:
    """txt 导出。

    - mode=whole:整本 txt(默认)
    - mode=chapters:每章一个 txt 打 zip,扩展名变成 .zip
    - encoding:utf-8 / gb18030
    """
    from app.models.project import Project

    proj = db.get(Project, project_id)
    if proj is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="工程不存在")
    if encoding.lower() not in {"utf-8", "gb18030"}:
        raise HTTPException(status_code=400, detail="encoding 仅支持 utf-8 / gb18030")
    if mode not in {"whole", "chapters"}:
        raise HTTPException(status_code=400, detail="mode 必须是 whole 或 chapters")

    if mode == "whole":
        body = txt_exporter.export_to_txt_whole(db, project_id, encoding=encoding)
        ext = "txt"
        media = f"text/plain; charset={encoding}"
    else:
        body = txt_exporter.export_to_txt_chapters_zip(db, project_id, encoding=encoding)
        ext = "zip"
        media = "application/zip"
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": _content_disposition(proj.name, ext)},
    )


@router.post("/projects/import", status_code=status.HTTP_201_CREATED)
async def import_project(
    file: UploadFile = File(...), db: Session = Depends(get_db)
) -> dict:
    try:
        raw = await file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"读取文件失败: {e}") from e
    if len(raw) > _MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="文件过大,上限 50MB")

    try:
        data = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"JSON 解析失败: {e}") from e

    try:
        project = export_service.import_from_dict(db, data)
    except InvalidImportError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {
        "id": project.id,
        "name": project.name,
        "chapter_count": len(project.chapters),
        "character_count": len(project.characters),
    }


@router.post("/projects/import-novel/preview")
async def preview_novel_split(file: UploadFile = File(...)) -> dict:
    """检测小说文本能拆分出多少章节,只返回标题与字数,不真正建工程。"""
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="文件过大,上限 50MB")
    text = _decode_text(raw)
    chapters = novel_split_service.split_novel_text(text)
    return {
        "chapter_count": len(chapters),
        "total_chars": sum(len(c.content) for c in chapters),
        "preview": [
            {"title": c.title, "char_count": len(c.content)}
            for c in chapters[:10]  # 前 10 章足够预览
        ],
    }


@router.post("/projects/import-novel", status_code=status.HTTP_201_CREATED)
async def import_novel(
    name: str = Form(...),
    description: str | None = Form(default=None),
    channel: str | None = Form(default=None),
    genre: str | None = Form(default=None),
    tags: str | None = Form(default=None),  # JSON 字符串
    cover_color: str | None = Form(default=None),
    progression_system: str | None = Form(default=None),
    words_per_chapter: int = Form(default=4000),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """从纯文本/Markdown 文件创建新工程,自动按章节切分。"""
    raw = await file.read()
    if len(raw) > _MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="文件过大,上限 50MB")
    text = _decode_text(raw)
    chapters = novel_split_service.split_novel_text(text)
    if not chapters:
        raise HTTPException(status_code=400, detail="文件内容为空")

    parsed_tags: list[str] = []
    if tags:
        try:
            parsed = json.loads(tags)
            if isinstance(parsed, list):
                parsed_tags = [str(x) for x in parsed]
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="tags 字段必须是 JSON 数组") from None

    payload = ProjectCreate(
        name=name,
        description=description,
        channel=channel,
        genre=genre,
        tags=parsed_tags,
        cover_color=cover_color,
        progression_system=progression_system,
        words_per_chapter=words_per_chapter,
    )
    try:
        project_read = project_service.create_project(db, payload)
    except ProjectNameConflictError as e:
        raise HTTPException(status_code=400, detail=f"工程名已存在: {e}") from e

    # 章节按顺序入库
    for idx, ch in enumerate(chapters, start=1):
        chap = Chapter(
            project_id=project_read.id,
            title=ch.title[:200],
            order_index=idx,
            content=ch.content,
            status="draft",
            word_count=len(ch.content),
        )
        db.add(chap)
    db.commit()

    return {
        "id": project_read.id,
        "name": project_read.name,
        "chapter_count": len(chapters),
    }
