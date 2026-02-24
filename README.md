# paper_split

将 arXiv 论文自动下载、转换为 Markdown，并按章节结构拆分为多个文件，方便大模型按章节检索论文内容。

## 功能

1. **下载**：根据 arXiv ID 下载 LaTeX 源码包并解压
2. **转换**：递归合并所有 `\input{}` 子文件，调用 pandoc 转换为单一 Markdown 文件
3. **拆分**：按标题层级（`#` / `##` / `####`）拆分为多级目录结构，Conclusion 之后的内容归入 `appendix`

## 输出结构

```
output/
  {论文标题}/
    figures/          # 论文原始图片（平铺）
    sections/
      0_abstract/
        0_abstract.md
      1_introduction/
        1_introduction.md
      2_related-work/
        0_subsection/
          0_subsection.md
        ...
      ...
      5_conclusion/
        5_conclusion.md
      6_appendix/
        0_xxx/
        ...
```

## 依赖

```bash
brew install pandoc
pip3 install requests
```

## 使用

```bash
# 处理单篇论文
python3 main.py 2512.03043

# 批量处理多篇
python3 main.py 2512.03043 2512.06673 2511.19887
```

已处理过的论文会跳过下载步骤，直接重新转换和拆分。

## 文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 主入口，串联下载→转换→拆分全流程 |
| `downloader.py` | 从 arXiv 下载并解压 LaTeX 源码 |
| `converter.py` | 合并 tex 文件，调用 pandoc 转 Markdown |
| `splitter.py` | 按章节拆分 Markdown，复制图片 |
