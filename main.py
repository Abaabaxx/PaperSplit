"""
main.py — 一键处理 arXiv 论文或本地 PDF：下载 → 转换 → 拆分
用法: python3 main.py <arxiv_id> [arxiv_id2 ...]
      python3 main.py /path/to/paper.pdf
示例: python3 main.py 2512.03043
      python3 main.py 2512.03043 2512.06673
      python3 main.py pdf_input/paper.pdf
"""

import shutil
import sys
from pathlib import Path

from downloader import fetch
from converter import convert, pdf_to_markdown
from splitter import split


def is_local_pdf(arg: str) -> bool:
    """判断参数是否为本地 PDF 路径（以 .pdf 结尾）。"""
    return arg.lower().endswith(".pdf")


def process(arxiv_id: str, data_dir: str = "./data", output_dir: str = "./output") -> Path:
    """完整处理流程：下载 → 转换 → 拆分，返回最终输出目录。"""
    print(f"\n{'='*50}")
    print(f"处理: {arxiv_id}")
    print(f"{'='*50}")

    print("\n[步骤 1/3] 下载 & 解压")
    fetch(arxiv_id, data_dir)

    print("\n[步骤 2/3] LaTeX → Markdown")
    convert(arxiv_id, data_dir)

    print("\n[步骤 3/3] 拆分章节")
    result = split(arxiv_id, data_dir, output_dir)

    print(f"\n完成: {result.parent}")
    return result.parent


def process_local_pdf(pdf_path: str, data_dir: str = "./data", output_dir: str = "./output") -> Path:
    """处理本地 PDF 文件：复制 → 转换 → 拆分，返回最终输出目录。"""
    pdf = Path(pdf_path).resolve()
    if not pdf.exists():
        raise FileNotFoundError(f"找不到文件：{pdf}")

    stem = pdf.stem
    print(f"\n{'='*50}")
    print(f"处理本地 PDF: {pdf.name}")
    print(f"{'='*50}")

    # 复制 PDF 到 data/{stem}/
    paper_dir = Path(data_dir) / stem
    paper_dir.mkdir(parents=True, exist_ok=True)
    dest_pdf = paper_dir / pdf.name
    if not dest_pdf.exists():
        shutil.copy2(pdf, dest_pdf)
        print(f"[复制] {pdf.name} → {dest_pdf}")
    else:
        print(f"[跳过] {dest_pdf} 已存在")

    print("\n[步骤 1/2] PDF → Markdown")
    md_path = paper_dir / "full_paper.md"
    pdf_to_markdown(dest_pdf, md_path)
    print(f"[完成] 已保存到 {md_path}（{md_path.stat().st_size / 1024:.1f} KB）")

    print("\n[步骤 2/2] 拆分章节")
    result = split(stem, data_dir, output_dir)

    print(f"\n完成: {result.parent}")
    return result.parent


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 main.py <arxiv_id> [arxiv_id2 ...]")
        print("      python3 main.py /path/to/paper.pdf")
        print("示例: python3 main.py 2512.03043")
        sys.exit(1)

    for arg in sys.argv[1:]:
        if is_local_pdf(arg):
            process_local_pdf(arg)
        else:
            process(arg)
