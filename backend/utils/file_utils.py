from __future__ import annotations
import os, shutil, stat, zipfile, uuid
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from fastapi import status

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


@dataclass
class ArchiveLimits:
    max_upload_bytes: int
    max_extracted_bytes: int
    max_files: int


class ArchiveValidationError(ValueError):
    def __init__(self, code: str, message: str, status_code: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

def new_project_id() -> str:
    return uuid.uuid4().hex[:12]

def archive_limits_from_env() -> ArchiveLimits:
    return ArchiveLimits(
        max_upload_bytes=_megabytes("MAX_UPLOAD_SIZE_MB", 50),
        max_extracted_bytes=_megabytes("MAX_EXTRACTED_SIZE_MB", 150),
        max_files=int(os.getenv("MAX_ARCHIVE_FILES", "5000")),
    )


def _megabytes(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    return max(1, value) * 1024 * 1024


def validate_zip_archive(zip_path: Path, limits: ArchiveLimits | None = None) -> list[zipfile.ZipInfo]:
    limits = limits or archive_limits_from_env()

    if not zip_path.exists() or zip_path.stat().st_size == 0:
        raise ArchiveValidationError(
            "INVALID_ARCHIVE",
            "The uploaded file is not a valid ZIP archive.",
            status.HTTP_400_BAD_REQUEST,
        )

    if zip_path.stat().st_size > limits.max_upload_bytes:
        raise ArchiveValidationError(
            "UPLOAD_TOO_LARGE",
            "The uploaded archive is larger than the configured upload limit.",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = zf.infolist()
            if not members:
                raise ArchiveValidationError(
                    "INVALID_ARCHIVE",
                    "The uploaded ZIP archive is empty.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )

            if len(members) > limits.max_files:
                raise ArchiveValidationError(
                    "UPLOAD_TOO_LARGE",
                    "The archive contains too many files for safe analysis.",
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                )

            total_uncompressed = 0
            for member in members:
                _validate_member_path(member.filename)
                if _member_is_symlink(member):
                    raise ArchiveValidationError(
                        "INVALID_ARCHIVE",
                        "The archive contains symlinks, which are not accepted for analysis uploads.",
                        status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )

                if member.is_dir():
                    continue

                total_uncompressed += member.file_size
                if total_uncompressed > limits.max_extracted_bytes:
                    raise ArchiveValidationError(
                        "UPLOAD_TOO_LARGE",
                        "The archive expands beyond the configured safe analysis limit.",
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    )

                if member.compress_size and member.file_size > 10 * 1024 * 1024:
                    ratio = member.file_size / max(member.compress_size, 1)
                    if ratio > 100:
                        raise ArchiveValidationError(
                            "UPLOAD_TOO_LARGE",
                            "The archive has a suspicious compression ratio and was rejected.",
                            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        )
            return members
    except zipfile.BadZipFile as exc:
        raise ArchiveValidationError(
            "INVALID_ARCHIVE",
            "The uploaded file is not a valid ZIP archive.",
            status.HTTP_400_BAD_REQUEST,
        ) from exc


def _validate_member_path(filename: str) -> None:
    posix = PurePosixPath(filename)
    windows = PureWindowsPath(filename)
    parts = [part for part in posix.parts if part not in {"", "."}]

    if posix.is_absolute() or windows.is_absolute() or windows.drive:
        raise ArchiveValidationError(
            "INVALID_ARCHIVE",
            "The archive contains an absolute file path.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if any(part == ".." for part in parts):
        raise ArchiveValidationError(
            "INVALID_ARCHIVE",
            "The archive contains unsafe parent-directory paths.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )


def _member_is_symlink(member: zipfile.ZipInfo) -> bool:
    mode = member.external_attr >> 16
    return stat.S_ISLNK(mode)


def safe_extract_zip(zip_path: Path, target_dir: Path, limits: ArchiveLimits | None = None) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    validate_zip_archive(zip_path, limits)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for member in zf.infolist():
            resolved = (target_dir / member.filename).resolve()
            if not str(resolved).startswith(str(target_dir.resolve())):
                raise ArchiveValidationError(
                    "INVALID_ARCHIVE",
                    "The archive contains unsafe file paths.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
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
