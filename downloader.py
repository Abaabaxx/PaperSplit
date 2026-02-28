"""
downloader.py — 根据 arXiv ID 下载并解压 LaTeX 源码包
用法: python downloader.py <arxiv_id>
"""

import gzip
import shutil
import sys
import tarfile
from pathlib import Path

import subprocess

ARXIV_SRC_URL = "https://arxiv.org/src/{arxiv_id}"


def download_arxiv_source(arxiv_id: str, data_dir: str = "./data") -> Path:
    """下载 arXiv 源码包到 data_dir，返回压缩文件路径。"""
    dest_dir = Path(data_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    url = ARXIV_SRC_URL.format(arxiv_id=arxiv_id)
    print(f"[下载] {url}")

    # 用 curl 下载，避免系统 Python LibreSSL 的 TLS 兼容性问题
    # -L 跟重定向，-s 静默，-D - 输出响应头到 stdout，-o 保存 body
    tmp_path = dest_dir / f"{arxiv_id}.tmp"
    header_output = subprocess.run(
        ["curl", "-L", "-s", "--max-time", "120",
         "-D", "-",  # 响应头输出到 stdout
         "-o", str(tmp_path),
         "-A", "paper_split/0.1",
         url],
        capture_output=True, text=True
    )
    if header_output.returncode != 0:
        raise RuntimeError(f"下载失败: {header_output.stderr}")
    if not tmp_path.exists() or tmp_path.stat().st_size == 0:
        raise RuntimeError(f"下载结果为空: {url}")

    # 从响应头判断 Content-Type
    content_type = ""
    for line in header_output.stdout.splitlines():
        if line.lower().startswith("content-type:"):
            content_type = line.split(":", 1)[1].strip()
            break

    ext = ".tar.gz" if "tar" in content_type else ".gz"
    archive_path = dest_dir / f"{arxiv_id}{ext}"
    tmp_path.rename(archive_path)

    print(f"[完成] 已保存到 {archive_path}（{archive_path.stat().st_size / 1024:.1f} KB）")
    return archive_path


def extract_archive(archive_path: Path, extract_dir: Path) -> Path:
    """解压 tar.gz 或单个 .gz 文件到 extract_dir，返回解压目录。"""
    extract_dir.mkdir(parents=True, exist_ok=True)

    # 先尝试作为 tar.gz 解压
    if tarfile.is_tarfile(archive_path):
        print(f"[解压] tar 格式 → {extract_dir}")
        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(path=extract_dir)
    else:
        # 单个 .gz 文件（单 tex）
        out_file = extract_dir / (archive_path.stem + ".tex")
        print(f"[解压] gz 格式 → {out_file}")
        with gzip.open(archive_path, "rb") as gz:
            with open(out_file, "wb") as f:
                shutil.copyfileobj(gz, f)

    print(f"[完成] 解压到 {extract_dir}")
    return extract_dir


def fetch(arxiv_id: str, data_dir: str = "./data") -> Path:
    """主入口：下载 + 解压，返回解压目录路径。"""
    extract_dir = Path(data_dir) / arxiv_id

    if extract_dir.exists() and any(extract_dir.iterdir()):
        print(f"[跳过] {extract_dir} 已存在，跳过下载")
        return extract_dir

    archive_path = download_arxiv_source(arxiv_id, data_dir)
    extract_archive(archive_path, extract_dir)

    # 解压完毕后删除压缩包
    archive_path.unlink()
    print(f"[清理] 已删除压缩包 {archive_path}")

    return extract_dir


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python downloader.py <arxiv_id>")
        print("示例: python downloader.py 2401.00001")
        sys.exit(1)

    arxiv_id = sys.argv[1]
    result_dir = fetch(arxiv_id)

    # 列出解压后的文件
    files = list(result_dir.rglob("*"))
    print(f"\n[结果] {result_dir} 共 {len(files)} 个文件：")
    for f in sorted(files)[:20]:
        if f.is_file():
            print(f"  {f.relative_to(result_dir)}")
    if len(files) > 20:
        print(f"  ... 共 {len(files)} 个")
