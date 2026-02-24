"""
main.py — 一键处理 arXiv 论文：下载 → 转换 → 拆分
用法: python3 main.py <arxiv_id> [arxiv_id2 ...]
示例: python3 main.py 2512.03043
      python3 main.py 2512.03043 2512.06673
"""

import sys
from pathlib import Path

from downloader import fetch
from converter import convert
from splitter import split


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


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 main.py <arxiv_id> [arxiv_id2 ...]")
        print("示例: python3 main.py 2512.03043")
        sys.exit(1)

    for arxiv_id in sys.argv[1:]:
        process(arxiv_id)
