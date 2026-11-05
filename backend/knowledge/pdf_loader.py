"""
PDF文档处理
"""
from typing import Dict, List
import os


try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False
    print("pypdf未安装，请运行: pip install pypdf")


def extract_text_from_pdf(pdf_path: str) -> Dict:
    """
    从PDF提取文本

    Args:
        pdf_path: PDF文件路径

    Returns:
        {"text": 提取的文本, "pages": 页数, "metadata": 元数据}
    """
    if not PYPDF_AVAILABLE:
        raise ImportError("请先安装 pypdf: pip install pypdf")

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"文件不存在: {pdf_path}")

    try:
        reader = pypdf.PdfReader(pdf_path)
        metadata = reader.metadata or {}

        # 提取所有页的文本
        text_parts = []
        for page_num, page in enumerate(reader.pages, 1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                text_parts.append(page_text)

        full_text = "\n\n".join(text_parts)

        # 获取元数据
        meta = {
            "title": metadata.get("/Title", os.path.basename(pdf_path)),
            "author": metadata.get("/Author", ""),
            "creator": metadata.get("/Creator", ""),
            "pages": len(reader.pages)
        }

        return {
            "text": full_text,
            "pages": len(reader.pages),
            "metadata": meta
        }

    except Exception as e:
        raise Exception(f"PDF解析失败: {e}")


def clean_text(text: str) -> str:
    """
    清理文本（去除多余空格、换行等）

    Args:
        text: 原始文本

    Returns:
        清理后的文本
    """
    # 替换多个连续空格为单个空格
    text = " ".join(text.split())

    # 去除过长的连续换行
    lines = text.split("\n")
    cleaned_lines = []
    empty_count = 0

    for line in lines:
        if line.strip():
            cleaned_lines.append(line)
            empty_count = 0
        else:
            empty_count += 1
            if empty_count <= 1:  # 最多保留一个空行
                cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


# 测试
if __name__ == "__main__":
    # 测试PDF提取
    test_pdf = "test.pdf"  # 替换为你的PDF路径

    if os.path.exists(test_pdf):
        result = extract_text_from_pdf(test_pdf)
        print(f"成功提取 {result['pages']} 页")
        print(f"标题: {result['metadata']['title']}")
        print(f"文本长度: {len(result['text'])} 字符")
        print(f"\n前500字符预览:\n{result['text'][:500]}")
    else:
        print(f"测试PDF不存在: {test_pdf}")
        print("请将PDF文件路径作为参数传入")
