"""
splitter.py — 将 full_paper.md 按标题层级拆分为多个 MD 文件
用法: python3 splitter.py <arxiv_id>
"""

import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path


def extract_paper_title(paper_dir: Path) -> str:
    """从主 tex 文件中提取 \\title{} 内容，清理 LaTeX 命令后返回纯文本。"""
    # 找主 tex 文件
    main_tex = None
    for tex_file in paper_dir.rglob("*.tex"):
        try:
            content = tex_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if re.search(r"\\documentclass", content):
            main_tex = content
            break

    if main_tex is None:
        return None

    # 提取 \title{...}，用括号计数处理嵌套花括号
    m = re.search(r"\\title\{", main_tex)
    if not m:
        return None

    start = m.end()
    depth, i = 1, start
    while i < len(main_tex) and depth > 0:
        if main_tex[i] == "{":
            depth += 1
        elif main_tex[i] == "}":
            depth -= 1
        i += 1
    raw = main_tex[start: i - 1]

    # 清理 LaTeX：去掉 $...$ 包裹（保留内容），去掉 \cmd{...}（保留内容），去掉 \! \\ 等
    # 先去掉注释行（以 % 开头的行）和行内注释
    lines = raw.splitlines()
    lines = [l for l in lines if not l.lstrip().startswith("%")]
    lines = [re.sub(r"(?<!\\)%.*", "", l) for l in lines]
    raw = " ".join(lines)

    title = raw
    title = re.sub(r"\$([^$]*)\$", lambda m: m.group(1), title)   # $...$ → 内容
    # 循环剥离 \cmd{...} 直到稳定（处理嵌套）
    cmd_pattern = re.compile(r"\\(?:boldsymbol|mathit|textsc|textbf|emph)\{([^}]*)\}")
    for _ in range(5):
        new = cmd_pattern.sub(r"\1", title)
        if new == title:
            break
        title = new
    title = re.sub(r"\\[!,;:]", "", title)    # \! \, \; \: 间距命令
    title = re.sub(r"\\\\", "", title)        # \\ 换行
    title = re.sub(r"\s+", " ", title)        # 合并空白
    return title.strip()


@dataclass
class Section:
    level: int          # 标题层级，# = 1, ## = 2, #### = 4
    title: str          # 原始标题文字（已去掉 {#...} 标记）
    intro: str          # 本节引言（到第一个子节之前的内容）
    children: list      # 子节列表


def clean_title(raw: str) -> str:
    """去掉标题中的 LaTeX 引用标记，如 {#sec:intro} {.unnumbered}"""
    return re.sub(r"\{[^}]*\}", "", raw).strip()


def slugify(title: str) -> str:
    """标题转文件夹/文件名：小写、空格转连字符、去特殊字符"""
    title = clean_title(title)
    title = title.lower()
    title = re.sub(r"[^\w\s-]", "", title)   # 去掉非字母数字连字符
    title = re.sub(r"[\s_]+", "-", title)     # 空格/下划线转连字符
    title = re.sub(r"-+", "-", title)         # 合并多余连字符
    return title.strip("-")


def parse_sections(md_text: str) -> list:
    """将 MD 文本解析为 Section 树（只处理顶层，children 递归嵌套）。"""
    # 找所有标题行的位置：(行起始位置, 层级, 原始标题文字)
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)", re.MULTILINE)
    matches = list(heading_pattern.finditer(md_text))

    if not matches:
        return []

    # 构造 flat 列表：(start, end, level, title)
    flat = []
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        level = len(m.group(1))
        title = clean_title(m.group(2))
        flat.append((start, end, level, title, md_text[start:end]))

    def build_tree(items, min_level):
        """递归将 flat 列表构造为 Section 树。"""
        result = []
        i = 0
        while i < len(items):
            start, end, level, title, full_content = items[i]
            if level < min_level:
                break

            # 收集属于本节的子节
            children_items = []
            j = i + 1
            while j < len(items):
                _, _, child_level, _, _ = items[j]
                if child_level <= level:
                    break
                children_items.append(items[j])
                j += 1

            # 本节引言 = 本节全部内容中，去掉第一个子标题后面的部分
            heading_line_end = full_content.index("\n") + 1 if "\n" in full_content else len(full_content)
            intro_text = full_content[heading_line_end:]
            if children_items:
                first_child_start = children_items[0][0]
                intro_text = md_text[start + heading_line_end: first_child_start]

            children = build_tree(children_items, level + 1) if children_items else []

            result.append(Section(
                level=level,
                title=title,
                intro=intro_text.strip(),
                children=children,
            ))
            i = j if children_items else i + 1

        return result

    return build_tree(flat, min_level=min(f[2] for f in flat))


CONCLUSION_KEYWORDS = {"conclusion", "conclusions", "concluding", "concluding-remarks"}


def is_conclusion(slug: str) -> bool:
    return any(kw in slug for kw in CONCLUSION_KEYWORDS)


IMAGE_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg", ".gif"}


def copy_figures(paper_dir: Path, figures_dir: Path):
    """将 paper_dir 下所有图片文件平铺复制到 figures_dir。"""
    count = 0
    for f in paper_dir.rglob("*"):
        if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
            shutil.copy2(f, figures_dir / f.name)
            count += 1
    print(f"[图片] 复制 {count} 个文件 → {figures_dir}")


def _write_section(section, parent_dir: Path, prefixed: str):
    """将单个 Section 写入文件夹，递归处理子节。"""
    section_dir = parent_dir / prefixed
    section_dir.mkdir(parents=True, exist_ok=True)

    if section.intro:
        md_path = section_dir / f"{prefixed}.md"
        md_path.write_text(f"# {section.title}\n\n{section.intro}\n", encoding="utf-8")

    if section.children:
        write_sections(section.children, section_dir)


def write_sections(sections: list, parent_dir: Path, top_level: bool = False):
    """递归将 Section 树写入文件夹结构。
    top_level=True 时，Conclusion 之后的章节放入 '其他工作/' 文件夹。
    """
    after_conclusion = False
    conclusion_idx = 0
    other_idx = 0
    other_dir = None

    for idx, section in enumerate(sections):
        slug = slugify(section.title)
        if not slug:
            slug = "section"

        if top_level and after_conclusion:
            if other_dir is None:
                other_dir = parent_dir / f"{conclusion_idx + 1}_appendix"
                other_dir.mkdir()
            prefixed = f"{other_idx}_{slug}"
            _write_section(section, other_dir, prefixed)
            other_idx += 1
        else:
            prefixed = f"{idx}_{slug}"
            _write_section(section, parent_dir, prefixed)

        if top_level and is_conclusion(slug):
            after_conclusion = True
            conclusion_idx = idx


def split(arxiv_id: str, data_dir: str = "./data", output_dir: str = "./output") -> Path:
    """主入口：读 full_paper.md → 解析 → 拆分写入 output/{arxiv_id}/sections/"""
    paper_dir = Path(data_dir) / arxiv_id
    md_path = paper_dir / "full_paper.md"

    if not md_path.exists():
        raise FileNotFoundError(f"未找到 {md_path}，请先运行 converter.py")

    # 提取论文标题作为文件夹名，失败则退回 arxiv_id
    title = extract_paper_title(paper_dir)
    folder_name = title if title else arxiv_id
    print(f"[标题] {folder_name}")

    # 创建输出目录结构
    out_paper_dir = Path(output_dir) / folder_name
    out_paper_dir.mkdir(parents=True, exist_ok=True)

    # 复制图片到 figures/
    figures_dir = out_paper_dir / "figures"
    figures_dir.mkdir(exist_ok=True)
    copy_figures(paper_dir, figures_dir)

    sections_dir = out_paper_dir / "sections"
    if sections_dir.exists():
        shutil.rmtree(sections_dir)
    sections_dir.mkdir()

    md_text = md_path.read_text(encoding="utf-8")
    print(f"[解析] {md_path}（{len(md_text)} 字符）")

    sections = parse_sections(md_text)
    print(f"[完成] 解析出 {len(sections)} 个顶级章节")

    write_sections(sections, sections_dir, top_level=True)

    # 统计生成文件数
    all_files = list(sections_dir.rglob("*.md"))
    print(f"[完成] 生成 {len(all_files)} 个 MD 文件 → {sections_dir}")

    return sections_dir


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python3 splitter.py <arxiv_id>")
        print("示例: python3 splitter.py 2512.03043")
        sys.exit(1)

    arxiv_id = sys.argv[1]
    result = split(arxiv_id)

    # 打印目录树
    print("\n[目录结构]")
    for f in sorted(result.rglob("*.md")):
        depth = len(f.relative_to(result).parts) - 1
        print("  " + "  " * depth + f.name)
