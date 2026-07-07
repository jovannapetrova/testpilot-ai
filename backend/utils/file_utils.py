from __future__ import annotations
import os, shutil, zipfile, uuid
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
STORAGE_DIR = BASE_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
WORKSPACE_DIR = STORAGE_DIR / "workspaces"
REPORT_DIR = STORAGE_DIR / "reports"

for directory in [UPLOAD_DIR, WORKSPACE_DIR, REPORT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java",
    ".txt", ".md", ".toml", ".yaml", ".yml", ".json", ".ini", ".cfg",
    ".xml", ".gradle", ".properties"
}
IGNORED_DIRS = {"venv", ".venv", "node_modules", "__pycache__", ".git", ".pytest_cache", "dist", "build"}

def new_project_id() -> str:
    return uuid.uuid4().hex[:12]

def safe_extract_zip(zip_path: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            resolved = (target_dir / member.filename).resolve()
            if not str(resolved).startswith(str(target_dir.resolve())):
                raise ValueError("Unsafe zip path detected")
        zf.extractall(target_dir)

def save_upload_file(upload_file, project_id: str) -> Path:
    upload_path = UPLOAD_DIR / f"{project_id}_{upload_file.filename}"
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)
    return upload_path

def prepare_workspace_from_zip(zip_path: Path, project_id: str) -> Path:
    workspace = WORKSPACE_DIR / project_id
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    safe_extract_zip(zip_path, workspace)
    return normalize_single_root(workspace)

def normalize_single_root(workspace: Path) -> Path:
    children = [p for p in workspace.iterdir() if p.is_dir()]
    files = [p for p in workspace.iterdir() if p.is_file()]
    if len(children) == 1 and not files:
        return children[0]
    return workspace

def iter_code_files(project_dir: Path):
    for root, dirs, files in os.walk(project_dir):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() in ALLOWED_EXTENSIONS:
                yield path

def relative_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base)).replace('\\', '/')
    except ValueError:
        return str(path).replace('\\', '/')
