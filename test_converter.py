"""
test_converter.py — converter.py 转换逻辑的测试
"""

import subprocess
import unittest
from pathlib import Path


class TestPreprocessTexStripsOrphanBraces(unittest.TestCase):
    """preprocess_tex: 空格后的裸 { 应被移除，避免 pandoc 报错"""

    def setUp(self):
        from converter import preprocess_tex
        self.preprocess = preprocess_tex

    def test_bare_brace_after_space_removed(self):
        """'we present {a powerful' 中的裸 { 应被删除"""
        tex = "we present {a powerful encoder;\n"
        result = self.preprocess(tex)
        self.assertNotIn("present {a", result)
        self.assertIn("present a", result)

    def test_cmd_brace_preserved(self):
        r"""\textbf{Title} 的 { 不应被删除"""
        tex = "\\textbf{Title}\n"
        result = self.preprocess(tex)
        self.assertIn("\\textbf{Title}", result)

    def test_group_with_cmd_preserved(self):
        r"""{\\em text} 的 { 不应被删除"""
        tex = "{\\em some text}\n"
        result = self.preprocess(tex)
        self.assertIn("{\\em", result)

    def test_cmd_arg_preserved(self):
        r"""\section{Title} 的 { 不应被删除"""
        tex = "\\section{Introduction}\n"
        result = self.preprocess(tex)
        self.assertIn("\\section{Introduction}", result)


class TestConvertPandocWithOrphanBraces(unittest.TestCase):
    """tex_to_markdown: 含裸 { 的 tex 在预处理后应能成功转换"""

    def test_orphan_brace_paper_converts(self):
        """2412.01820 含裸 { 的论文应能通过转换"""
        paper_dir = Path("data/2412.01820")
        if not paper_dir.exists():
            self.skipTest("2412.01820 数据不存在")

        from converter import find_main_tex, merge_tex, tex_to_markdown
        import tempfile

        main_tex = find_main_tex(paper_dir)
        merged = merge_tex(main_tex)

        with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as f:
            out = Path(f.name)

        try:
            result = tex_to_markdown(merged, out)
            self.assertTrue(result.exists())
            content = result.read_text()
            self.assertGreater(len(content), 10000)
        finally:
            out.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
