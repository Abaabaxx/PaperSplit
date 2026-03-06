"""
test_local_pdf.py — 本地 PDF 文件处理的测试
"""

import shutil
import tempfile
import unittest
from pathlib import Path


REAL_PDF = Path("pdf_input/Li_Multi-Modal_Large_Language_Model_with_RAG_Strategies_in_Soccer_Commentary_WACV_2025_paper.pdf")


class TestProcessLocalPdf(unittest.TestCase):
    """main.process_local_pdf: 本地 PDF 应被转换并拆分"""

    def setUp(self):
        self.tmp_data = Path(tempfile.mkdtemp())
        self.tmp_output = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp_data)
        shutil.rmtree(self.tmp_output)

    def test_output_dir_created(self):
        """处理本地 PDF 后，output 下应生成对应的论文目录"""
        if not REAL_PDF.exists():
            self.skipTest("测试用 PDF 不存在")

        from main import process_local_pdf
        result = process_local_pdf(str(REAL_PDF), data_dir=str(self.tmp_data), output_dir=str(self.tmp_output))

        self.assertTrue(result.exists(), "输出目录应当存在")

    def test_sections_generated(self):
        """输出目录下应包含 sections 子目录且有 MD 文件"""
        if not REAL_PDF.exists():
            self.skipTest("测试用 PDF 不存在")

        from main import process_local_pdf
        result = process_local_pdf(str(REAL_PDF), data_dir=str(self.tmp_data), output_dir=str(self.tmp_output))

        sections_dir = result / "sections"
        self.assertTrue(sections_dir.exists(), "sections 目录应当存在")
        md_files = list(sections_dir.rglob("*.md"))
        self.assertGreater(len(md_files), 0, "应当生成至少一个 MD 文件")

    def test_pdf_stem_used_as_data_key(self):
        """data 目录下应以 PDF 文件名（去扩展名）为子目录存放中间文件"""
        if not REAL_PDF.exists():
            self.skipTest("测试用 PDF 不存在")

        from main import process_local_pdf
        process_local_pdf(str(REAL_PDF), data_dir=str(self.tmp_data), output_dir=str(self.tmp_output))

        paper_data_dir = self.tmp_data / REAL_PDF.stem
        full_paper_md = paper_data_dir / "full_paper.md"
        self.assertTrue(full_paper_md.exists(), "full_paper.md 应当在 data/{stem}/ 下")


class TestDispatchByArgument(unittest.TestCase):
    """main.__main__: 参数是 .pdf 路径时走本地 PDF 路径，否则走 ArXiv ID 路径"""

    def test_is_local_pdf_with_pdf_path(self):
        from main import is_local_pdf
        self.assertTrue(is_local_pdf("/some/path/paper.pdf"))
        self.assertTrue(is_local_pdf("./paper.pdf"))
        self.assertTrue(is_local_pdf("paper.pdf"))

    def test_is_local_pdf_with_arxiv_id(self):
        from main import is_local_pdf
        self.assertFalse(is_local_pdf("2512.03043"))
        self.assertFalse(is_local_pdf("2406.18530"))


if __name__ == "__main__":
    unittest.main()
