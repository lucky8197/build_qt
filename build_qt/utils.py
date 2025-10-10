import requests
import shutil
import os
import hashlib
import platform
from typing import Optional, Dict
from rich.progress import Progress, BarColumn, DownloadColumn, TextColumn, TimeRemainingColumn, TransferSpeedColumn


class DownloadError(Exception):
    pass

def detect_platform() -> Dict[str, str]:
    """探测本机 osType 和 osArch，返回用于请求的值。"""
    sys_os = platform.system().lower()
    machine = platform.machine().lower()
    if sys_os.startswith("windows"):
        os_type = "windows"
    elif sys_os.startswith("linux"):
        os_type = "linux"
    elif sys_os.startswith("darwin") or sys_os.startswith("mac"):
        os_type = "darwin"
    else:
        os_type = sys_os

    # normalize arch
    if machine in ("amd64", "x86_64", "x64"):
        os_arch = "x64"
    elif machine in ("arm64", "aarch64"):
        os_arch = "arm64"
    else:
        os_arch = machine

    return {"osType": os_type, "osArch": os_arch}

def checksum(file_path: str, expected_checksum: tuple[str, str]) -> bool:
    """计算文件的校验和，并可选与预期值对比。

    Returns True if checksum matches or no expected_checksum provided.
    Raises DownloadError on failure or mismatch.
    """
    algo = expected_checksum[0].lower()
    if algo not in ("sha256", "sha1", "md5"):
        raise ValueError("Unsupported checksum algorithm: " + algo)
    h = hashlib.new(algo)
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except Exception as e:
        raise DownloadError("Failed to compute checksum for {}: {}".format(file_path, e))
    computed = h.hexdigest()
    checksum_value = expected_checksum[1]
    if checksum_value:
        if computed.lower() != checksum_value.lower():
            raise DownloadError("Checksum mismatch: expected {}, got {}".format(checksum_value, computed))
    return True

def download_component(url: str, dest_path: str, expected_checksum: Optional[tuple[str, str]] = None, chunk_size: int = 8192) -> str:
        """下载单个组件到本地路径，并可选校验 sha256 校验和。

        Returns saved file path.
        Raises DownloadError on failure.
        """
        if os.path.exists(dest_path):
            if expected_checksum:
                # 校验已存在文件的 sha256
                if checksum(dest_path, expected_checksum=expected_checksum):
                    print("Info: existing file {} checksum matched".format(dest_path))
                    return dest_path  # 已存在且校验通过，直接返回
                else:
                    print("Warning: existing file {} checksum mismatch, re-downloading".format(dest_path))
            else:
                return dest_path  # 文件已存在且不需要校验，直接返回
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)) or ".", exist_ok=True)
        tmp_path = dest_path + ".part"
        try:
            session = requests.Session()
            with session.get(url, stream=True, timeout=30) as r:
                r.raise_for_status()
                total = 0
                # try to get total size from headers
                try:
                    total_size = int(r.headers.get('Content-Length')) if r.headers.get('Content-Length') else None
                except Exception:
                    total_size = None
                task_id = None
                try:
                    rich_progress = Progress(TextColumn("{task.fields[filename]}", justify="right"), BarColumn(), DownloadColumn(), TransferSpeedColumn(), TimeRemainingColumn())
                    rich_progress.__enter__()
                    task_id = rich_progress.add_task("download", filename=os.path.basename(dest_path), total=total_size or 0)
                except Exception:
                    rich_progress = None

                try:
                    with open(tmp_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                total += len(chunk)
                                # update rich progress if present
                                if rich_progress and task_id is not None:
                                    try:
                                        rich_progress.update(task_id, advance=len(chunk))
                                    except Exception:
                                        pass
                finally:
                    if rich_progress:
                        try:
                            rich_progress.__exit__(None, None, None)
                        except Exception:
                            pass
                # move to final location
                shutil.move(tmp_path, dest_path)
                if expected_checksum:
                    if not checksum(dest_path, expected_checksum=expected_checksum):
                        raise DownloadError("Checksum mismatch: expected {}".format(expected_checksum[1]))
                return dest_path
        except requests.RequestException as e:
            # cleanup
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise DownloadError("Failed to download {}: {}".format(url, e))
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise

def extract_archive(archive_path: str, dest_dir: str, overwrite: bool = True) -> str:
    """Extract a zip, tar, or 7z archive to dest_dir.

    Supports .zip, .tar, .tar.gz, .tgz, .7z
    Returns the destination directory where files were extracted.
    """
    import os
    import shutil
    import stat
    import zipfile
    import tarfile
    import py7zr
    from rich.progress import Progress, TextColumn, BarColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

    def on_rm_error(func, path, exc_info):
        """处理只读文件的删除"""
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    if not os.path.exists(archive_path):
        raise DownloadError("Archive not found: {}".format(archive_path))

    if not overwrite and os.path.exists(dest_dir) and os.listdir(dest_dir):
        print("Info: destination directory {} already exists and is not empty, skipping extraction".format(dest_dir))
        return dest_dir
    else:
        if os.path.exists(dest_dir):
            shutil.rmtree(dest_dir, onerror=on_rm_error)
    os.makedirs(dest_dir, exist_ok=True)

    total_size = None
    try:
        rich_progress = Progress(
            TextColumn("{task.fields[filename]}", justify="right"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn()
        )
        rich_progress.__enter__()
        task_id = rich_progress.add_task("extract_archive", filename=os.path.basename(archive_path), total=total_size or 0)
    except Exception:
        rich_progress = None
        task_id = None

    lower = archive_path.lower()
    if lower.endswith('.zip'):
        with zipfile.ZipFile(archive_path, 'r') as z:
            members = z.infolist()
            if rich_progress and task_id is not None:
                try:
                    total_size = sum(m.file_size for m in members)
                    rich_progress.update(task_id, total=total_size)
                except Exception:
                    pass
            for m in members:
                z.extract(m, dest_dir)
                if rich_progress and task_id is not None:
                    try:
                        rich_progress.update(task_id, advance=m.file_size)
                    except Exception:
                        pass

    elif lower.endswith('.tar') or lower.endswith('.tar.gz') or lower.endswith('.tgz'):
        mode = 'r:gz' if (lower.endswith('.tar.gz') or lower.endswith('.tgz')) else 'r'
        with tarfile.open(archive_path, mode) as t:
            members = t.getmembers()
            if rich_progress and task_id is not None:
                try:
                    total_size = sum(m.size for m in members)
                    rich_progress.update(task_id, total=total_size)
                except Exception:
                    pass
            for m in members:
                t.extract(m, dest_dir)
                if rich_progress and task_id is not None:
                    try:
                        rich_progress.update(task_id, advance=m.size)
                    except Exception:
                        pass

    elif lower.endswith('.7z'):
        with py7zr.SevenZipFile(archive_path, mode='r') as z:
            all_info = z.getnames()
            if rich_progress and task_id is not None:
                try:
                    rich_progress.update(task_id, total=0)
                except Exception:
                    pass
            z.extractall(path=dest_dir)
            if rich_progress and task_id is not None:
                try:
                    rich_progress.update(task_id, advance=len(all_info))
                except Exception:
                    pass
    else:
        raise DownloadError("Unsupported archive format: {}".format(archive_path))
    rich_progress.__exit__(None, None, None)

    return dest_dir

