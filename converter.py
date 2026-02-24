"""
converter.py — 将 arXiv 下载的 tex 文件转换为单一 Markdown 文件
用法: python3 converter.py <arxiv_id>
"""

import re
import subprocess
import sys
from pathlib import Path


def find_main_tex(paper_dir: Path) -> Path:
    """找到含 \\documentclass 的主 tex 文件。"""
    tex_files = list(paper_dir.rglob("*.tex"))
    for tex_file in tex_files:
        try:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"\\documentclass", content):
            return tex_file
    raise FileNotFoundError(f"在 {paper_dir} 中未找到含 \\documentclass 的 tex 文件")


def merge_tex(tex_path: Path, _visited: set = None) -> str:
    """递归内联 \\input{} / \\include{}，返回合并后的 tex 字符串。"""
    if _visited is None:
        _visited = set()

    tex_path = tex_path.resolve()
    if tex_path in _visited:
        return ""  # 防止循环引用
    _visited.add(tex_path)

    try:
        content = tex_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

    base_dir = tex_path.parent

    def replace_input(match):
        cmd = match.group(1)   # input 或 include
        arg = match.group(2).strip()

        # 补全 .tex 扩展名
        candidate = base_dir / arg
        if not candidate.suffix:
            candidate = candidate.with_suffix(".tex")

        if candidate.exists():
            return merge_tex(candidate, _visited)
        # 找不到文件时保留原命令
        return match.group(0)

    # 匹配 \input{...} 和 \include{...}
    pattern = re.compile(r"\\(input|include)\{([^}]+)\}")
    return pattern.sub(replace_input, content)


def preprocess_tex(tex: str) -> str:
    """预处理 tex 字符串，将 pandoc 会丢弃的环境转为标准 section。"""
    # \begin{abstract}...\end{abstract} → \section*{Abstract}
    tex = re.sub(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
        r"\\section*{Abstract}\n\1",
        tex,
        flags=re.DOTALL,
    )
    return tex


def tex_to_markdown(merged_tex: str, output_path: Path) -> Path:
    """调用 pandoc 将 tex 字符串转为 Markdown，保存到 output_path。"""
    merged_tex = preprocess_tex(merged_tex)
    cmd = [
        "pandoc",
        "-f", "latex",
        "-t", "markdown",
        "--wrap=none",
    ]

    result = subprocess.run(
        cmd,
        input=merged_tex,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    if result.returncode != 0:
        raise RuntimeError(f"pandoc 转换失败：{result.stderr}")

    output_path.write_text(result.stdout, encoding="utf-8")
    return output_path


def convert(arxiv_id: str, data_dir: str = "./data") -> Path:
    """主入口：找主文件 → 合并 → 转 MD，返回 MD 文件路径。"""
    paper_dir = Path(data_dir) / arxiv_id
    if not paper_dir.exists():
        raise FileNotFoundError(f"目录不存在：{paper_dir}，请先运行 downloader.py")

    print(f"[查找] 寻找主 tex 文件...")
    main_tex = find_main_tex(paper_dir)
    print(f"[找到] {main_tex.relative_to(paper_dir)}")

    print(f"[合并] 递归内联 \\input{{}} / \\include{{}}...")
    merged = merge_tex(main_tex)
    print(f"[完成] 合并后共 {len(merged)} 字符")

    output_path = paper_dir / "full_paper.md"
    print(f"[转换] 调用 pandoc 转 Markdown...")
    tex_to_markdown(merged, output_path)
    print(f"[完成] 已保存到 {output_path}（{output_path.stat().st_size / 1024:.1f} KB）")

    return output_path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python3 converter.py <arxiv_id>")
        print("示例: python3 converter.py 2512.03043")
        sys.exit(1)

    arxiv_id = sys.argv[1]
    convert(arxiv_id)
