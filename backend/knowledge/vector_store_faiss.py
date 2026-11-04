"""
FAISS向量存储（无需PostgreSQL）
适合快速原型和小规模数据
"""
import os
import pickle
import numpy as np
from typing import List, Dict, Optional

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False


class FAISSVectorStore:
    """FAISS向量存储"""

    def __init__(self, index_type: str = "flat", dim: int = 1024):
        """
        初始化FAISS索引

        Args:
            index_type: 索引类型 ("flat"=精确搜索, "ivf"=近似搜索)
            dim: 向量维度
        """
        self.dim = dim
        self.index_type = index_type

        # 创建索引
        if index_type == "flat":
            self.index = faiss.IndexFlatIP(dim)  # 内积相似度
        elif index_type == "ivf":
            quantizer = faiss.IndexFlatIP(dim)
            self.index = faiss.IndexIVFFlat(quantizer, dim, 100)  # 100个聚类中心
        else:
            raise ValueError(f"不支持的索引类型: {index_type}")

        # 存储元数据
        self.documents = {}  # {idx: {"doc_id", "content", "metadata"}}
        self.doc_id_to_idx = {}  # {doc_id_chunk_i: idx}
        self.next_idx = 0

        # 是否已训练（IVF需要）
        self.is_trained = False

    def add_vectors(
        self,
        embeddings: List[List[float]],
        doc_id: str,
        chunks: List[str],
        metadata: Optional[Dict] = None
    ):
        """
        添加向量

        Args:
            embeddings: 向量列表
            doc_id: 文档ID
            chunks: 文本块列表
            metadata: 元数据
        """
        embeddings_array = np.array(embeddings, dtype='float32')

        # IVF索引需要先训练
        if self.index_type == "ivf" and not self.is_trained:
            print("训练IVF索引...")
            self.index.train(embeddings_array)
            self.is_trained = True

        # 添加向量到索引
        start_idx = self.next_idx
        self.index.add(embeddings_array)

        # 存储元数据
        meta = metadata or {}
        for i, chunk in enumerate(chunks):
            idx = start_idx + i
            self.documents[idx] = {
                "doc_id": doc_id,
                "content": chunk,
                "metadata": meta
            }
            self.doc_id_to_idx[f"{doc_id}_{i}"] = idx

        self.next_idx += len(chunks)
        print(f"添加 {len(chunks)} 个向量到索引")

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        doc_id_filter: Optional[str] = None
    ) -> List[Dict]:
        """
        搜索相似向量

        Args:
            query_embedding: 查询向量
            top_k: 返回前K个结果
            doc_id_filter: 文档ID过滤

        Returns:
            搜索结果
        """
        query_array = np.array([query_embedding], dtype='float32')

        # 搜索
        similarities, indices = self.index.search(query_array, top_k)

        results = []
        for score, idx in zip(similarities[0], indices[0]):
            if idx == -1:  # FAISS返回-1表示没找到
                continue

            doc = self.documents.get(int(idx))
            if not doc:
                continue

            # 过滤文档
            if doc_id_filter and doc["doc_id"] != doc_id_filter:
                continue

            results.append({
                "doc_id": doc["doc_id"],
                "content": doc["content"],
                "similarity": float(score),
                "metadata": doc["metadata"]
            })

        return results

    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档（FAISS不支持删除，需要重建索引）

        Args:
            doc_id: 文档ID

        Returns:
            是否成功
        """
        # FAISS不支持删除，这里简化处理：从元数据中删除
        count = 0
        for key in list(self.doc_id_to_idx.keys()):
            if key.startswith(f"{doc_id}_"):
                idx = self.doc_id_to_idx[key]
                if idx in self.documents:
                    # 标记为已删除
                    self.documents[idx]["doc_id"] = "__DELETED__"
                    count += 1

        print(f"标记删除 {count} 个文本块（FAISS不支持真正删除，需要重建索引）")
        return True

    def save(self, save_dir: str):
        """
        保存索引到磁盘

        Args:
            save_dir: 保存目录
        """
        os.makedirs(save_dir, exist_ok=True)

        # 用serialize/deserialize绕过C++文件IO，支持中文路径
        index_bytes = faiss.serialize_index(self.index)
        np.save(os.path.join(save_dir, "index.npy"), np.frombuffer(index_bytes, dtype=np.uint8))

        # 保存元数据
        with open(os.path.join(save_dir, "metadata.pkl"), "wb") as f:
            pickle.dump({
                "documents": self.documents,
                "doc_id_to_idx": self.doc_id_to_idx,
                "next_idx": self.next_idx,
                "is_trained": self.is_trained
            }, f)

        print(f"索引已保存到 {save_dir}")

    def load(self, save_dir: str):
        """
        从磁盘加载索引

        Args:
            save_dir: 保存目录
        """
        # 用serialize/deserialize绕过C++文件IO，支持中文路径
        index_array = np.load(os.path.join(save_dir, "index.npy"))
        self.index = faiss.deserialize_index(index_array)

        # 加载元数据
        with open(os.path.join(save_dir, "metadata.pkl"), "rb") as f:
            data = pickle.load(f)
            self.documents = data["documents"]
            self.doc_id_to_idx = data["doc_id_to_idx"]
            self.next_idx = data["next_idx"]
            self.is_trained = data.get("is_trained", False)

        print(f"索引已从 {save_dir} 加载")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        # 计算实际文档数（排除已删除的）
        doc_ids = set()
        for doc in self.documents.values():
            if doc["doc_id"] != "__DELETED__":
                doc_ids.add(doc["doc_id"])

        return {
            "total_chunks": self.index.ntotal,
            "total_documents": len(doc_ids),
            "index_type": self.index_type
        }


# 测试
if __name__ == "__main__":
    # 测试FAISS存储
    store = FAISSVectorStore(index_type="flat", dim=1024)

    # 添加假数据
    fake_embeddings = [np.random.rand(1024).tolist() for _ in range(10)]
    fake_chunks = [f"文本块{i}" for i in range(10)]

    store.add_vectors(fake_embeddings, "test_doc", fake_chunks)

    # 搜索
    query = np.random.rand(1024).tolist()
    results = store.search(query, top_k=3)

    print(f"搜索到 {len(results)} 个结果")
    for r in results:
        print(f"  相似度: {r['similarity']:.4f}, 内容: {r['content']}")
