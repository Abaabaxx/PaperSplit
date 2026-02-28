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


def merge_tex(tex_path: Path, _visited: set = None, _root_dir: Path = None) -> str:
    """递归内联 \\input{} / \\include{}，返回合并后的 tex 字符串。"""
    if _visited is None:
        _visited = set()

    tex_path = tex_path.resolve()
    if tex_path in _visited:
        return ""  # 防止循环引用
    _visited.add(tex_path)

    if _root_dir is None:
        _root_dir = tex_path.parent

    try:
        content = tex_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

    base_dir = tex_path.parent

    def replace_input(match):
        arg = match.group(2).strip()

        # 优先从当前文件所在目录查找，其次从根目录查找
        for search_dir in [base_dir, _root_dir]:
            candidate = search_dir / arg
            if not candidate.suffix:
                candidate = candidate.with_suffix(".tex")
            if candidate.exists():
                return merge_tex(candidate, _visited, _root_dir)

        # 找不到文件时保留原命令
        return match.group(0)

    # 匹配 \input{...} 和 \include{...}
    pattern = re.compile(r"\\(input|include)\{([^}]+)\}")
    return pattern.sub(replace_input, content)


def preprocess_tex(tex: str) -> str:
    """预处理 tex 字符串，清理 pandoc 无法处理的结构。"""
    # \begin{abstract}...\end{abstract} → \section*{Abstract}
    tex = re.sub(
        r"\\begin\{abstract\}(.*?)\\end\{abstract\}",
        r"\\section*{Abstract}\n\1",
        tex,
        flags=re.DOTALL,
    )
    # lstlisting / minted → verbatim（pandoc 能正确识别 verbatim 为逐字内容）
    for env in ("lstlisting", "minted", "Verbatim"):
        tex = re.sub(
            rf"\\begin\{{{env}\}}(?:\[.*?\])?(.*?)\\end\{{{env}\}}",
            r"\\begin{verbatim}\1\\end{verbatim}",
            tex,
            flags=re.DOTALL,
        )
    # 完整删除 figure / figure* 环境（内含图片路径，对文字阅读无用）
    for env in ("figure\\*", "figure"):
        tex = re.sub(
            rf"\\begin\{{{env}\}}.*?\\end\{{{env}\}}",
            "",
            tex,
            flags=re.DOTALL,
        )
    # 删除 table / table* 包装标签，保留内部 tabular 和 caption 内容
    for env in ("table\\*", "table"):
        tex = re.sub(rf"\\begin\{{{env}\}}(?:\[.*?\])?", "", tex)
        tex = re.sub(rf"\\end\{{{env}\}}", "", tex)
    # \global\long\def / \long\def → \def（pandoc 不认识 \long 修饰符）
    tex = re.sub(r"\\global\\long\\def\b", r"\\def", tex)
    tex = re.sub(r"\\long\\def\b", r"\\def", tex)
    # 修复剩余不匹配的环境标签
    tex = _fix_unmatched_envs(tex)
    return tex


def _fix_unmatched_envs(tex: str) -> str:
    """移除无匹配对的 \\end{x}，避免 pandoc 解析错误。"""
    lines = tex.splitlines(keepends=True)
    result = []
    stack = []

    begin_pat = re.compile(r"\\begin\{([^}]+)\}")
    end_pat = re.compile(r"\\end\{([^}]+)\}")

    for line in lines:
        if line.lstrip().startswith("%"):
            result.append(line)
            continue

        pct = line.find("%")
        code = line[:pct] if pct >= 0 else line

        begins = list(begin_pat.finditer(code))
        ends = list(end_pat.finditer(code))

        if not begins and not ends:
            result.append(line)
            continue

        events = [(m.start(), "begin", m.group(1)) for m in begins] + \
                 [(m.start(), "end",   m.group(1)) for m in ends]
        events.sort()

        drop_positions = set()

        for _pos, kind, env in events:
            if kind == "begin":
                stack.append(env)
            else:
                if stack and stack[-1] == env:
                    stack.pop()
                else:
                    drop_positions.add(_pos)

        if not drop_positions:
            result.append(line)
            continue

        new_line = line
        offset = 0
        for m in sorted(end_pat.finditer(code), key=lambda x: x.start()):
            if m.start() in drop_positions:
                s, e = m.start() + offset, m.end() + offset
                new_line = new_line[:s] + new_line[e:]
                offset -= (m.end() - m.start())
        result.append(new_line)

    return "".join(result)


def _count_brace_depth(text: str) -> int:
    """计算文本中未闭合的 '{' 数量（忽略注释行和行内注释）。"""
    depth = 0
    for line in text.splitlines():
        if line.lstrip().startswith("%"):
            continue
        pct = line.find("%")
        code = line[:pct] if pct >= 0 else line
        depth += code.count("{") - code.count("}")
    return depth


def _extract_body(tex: str, pad_braces: bool = False) -> str:
    """提取 \\begin{document} 与 \\end{document} 之间的正文，
    并用最简 preamble 重新包装，规避原始 preamble 中的语法错误。
    pad_braces=True 时才在末尾补齐未闭合的 '}'（用于 pandoc 报错后的回退）。"""
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", tex, re.DOTALL)
    if not m:
        return tex

    body = m.group(1)

    if pad_braces:
        depth = _count_brace_depth(body)
        if depth > 0:
            body = body.rstrip("\n") + "\n" + "}" * depth + "\n"

    minimal_preamble = "\\documentclass{article}\n"
    return minimal_preamble + "\\begin{document}\n" + body + "\n\\end{document}\n"


def tex_to_markdown(merged_tex: str, output_path: Path) -> Path:
    """调用 pandoc 将 tex 字符串转为 Markdown，保存到 output_path。"""
    merged_tex = preprocess_tex(merged_tex)
    cmd = [
        "pandoc",
        "-f", "latex+raw_tex",
        "-t", "markdown",
        "--wrap=none",
    ]

    # 先不补 brace 直接尝试；若 pandoc 因未闭合 '{' 报错再补齐后重试
    for pad in (False, True):
        tex = _extract_body(merged_tex, pad_braces=pad)
        result = subprocess.run(
            cmd,
            input=tex,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode == 0:
            break
        last_error = result.stderr

    if result.returncode != 0:
        raise RuntimeError(f"pandoc 转换失败：{last_error}")

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
