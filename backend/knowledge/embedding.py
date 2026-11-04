"""
文本Embedding调用（通义千问）
"""
from typing import List, Union
import dashscope
from backend.config import DASHSCOPE_API_KEY


# 通义千问Embedding模型
EMBEDDING_MODEL = "text-embedding-v3"
EMBEDDING_DIM = 1024  # text-embedding-v3输出维度


def get_embedding(text: str) -> List[float]:
    """
    获取文本的向量表示

    Args:
        text: 输入文本

    Returns:
        向量（1024维）
    """
    if not DASHSCOPE_API_KEY:
        raise ValueError("DASHSCOPE_API_KEY 未设置")

    dashscope.api_key = DASHSCOPE_API_KEY

    try:
        response = dashscope.TextEmbedding.call(
            model=EMBEDDING_MODEL,
            input=text,
            text_type="document"
        )

        if response.status_code == 200:
            embedding = response.output['embeddings'][0]['embedding']
            return embedding
        else:
            raise Exception(f"Embedding调用失败: {response.message}")

    except Exception as e:
        print(f"获取Embedding失败: {e}")
        raise


def get_embeddings_batch(texts: List[str], batch_size: int = 10) -> List[List[float]]:
    """
    批量获取文本向量（支持大批量，自动分批调用）

    Args:
        texts: 文本列表
        batch_size: 每批处理数量（通义千问限制最大10）

    Returns:
        向量列表
    """
    if not DASHSCOPE_API_KEY:
        raise ValueError("DASHSCOPE_API_KEY 未设置")

    dashscope.api_key = DASHSCOPE_API_KEY

    all_embeddings = []
    total = len(texts)

    try:
        # 分批处理
        for i in range(0, total, batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            print(f"   处理批次 {batch_num}/{total_batches} ({len(batch_texts)}个文本)...")

            response = dashscope.TextEmbedding.call(
                model=EMBEDDING_MODEL,
                input=batch_texts,
                text_type="document"
            )

            if response.status_code == 200:
                batch_embeddings = [item['embedding'] for item in response.output['embeddings']]
                all_embeddings.extend(batch_embeddings)
            else:
                raise Exception(f"批量Embedding调用失败: {response.message}")

        return all_embeddings

    except Exception as e:
        print(f"批量获取Embedding失败: {e}")
        raise


def text_split_by_token(
    text: str,
    max_tokens: int = 500,
    overlap: int = 50
) -> List[str]:
    """
    按字符数分割文本（优化版，避免内存问题）

    Args:
        text: 输入文本
        max_tokens: 最大字符数
        overlap: 重叠字符数

    Returns:
        文本块列表
    """
    # 先按段落（连续换行）预分割
    paragraphs = text.split('\n\n')
    if not paragraphs:
        paragraphs = [text]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 当前块+这段超限，先保存
        if len(current_chunk) + len(para) > max_tokens and current_chunk:
            chunks.append(current_chunk.strip())
            # 保留尾部overlap
            current_chunk = current_chunk[-overlap:] if overlap > 0 else ""
            first_period = current_chunk.find("\u3002")
            if first_period > 0:
                current_chunk = current_chunk[first_period + 1:]

        current_chunk = (current_chunk + "\n" + para) if current_chunk else para

        # 当前块超长时按句子拆分
        while len(current_chunk) > max_tokens * 1.5:
            cut_pos = max_tokens
            for sep in ["\u3002", ".", "\uff01", "!", "\uff1f", "?", "\uff1b", ";", "\n"]:
                pos = current_chunk.rfind(sep, max_tokens // 2, cut_pos + 50)
                if pos > max_tokens // 2:
                    cut_pos = pos + 1
                    break
            chunk_text = current_chunk[:cut_pos].strip()
            if chunk_text and len(chunk_text) > 10:
                chunks.append(chunk_text)
            current_chunk = current_chunk[cut_pos:].strip()
            if not current_chunk:
                break

    # 最后一块
    if current_chunk and len(current_chunk.strip()) > 10:
        chunks.append(current_chunk.strip())

    return chunks


# 测试
if __name__ == "__main__":
    # 测试单个embedding
    text = "Python是一种高级编程语言"
    embedding = get_embedding(text)
    print(f"Embedding维度: {len(embedding)}")
    print(f"前10个值: {embedding[:10]}")

    # 测试批量embedding
    texts = ["Python是一门编程语言", "Java是一门编程语言", "今天天气很好"]
    embeddings = get_embeddings_batch(texts)
    print(f"\n批量获取 {len(embeddings)} 个embedding")

    # 测试文本分割
    long_text = "Python是一种广泛使用的高级编程语言。" * 100
    chunks = text_split_by_token(long_text, max_tokens=200)
    print(f"\n文本分割成 {len(chunks)} 个块")
