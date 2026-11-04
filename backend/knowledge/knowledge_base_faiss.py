"""
知识库管理器（FAISS版本）
"""
from typing import List, Dict, Optional
import os
from datetime import datetime

from backend.knowledge.vector_store_faiss import FAISSVectorStore, FAISS_AVAILABLE
from backend.knowledge.embedding import get_embeddings_batch, text_split_by_token
from backend.knowledge.pdf_loader import extract_text_from_pdf, clean_text


class FAISSKnowledgeBase:
    """FAISS知识库管理器"""

    def __init__(self, save_dir: str = None):
        """
        初始化知识库

        Args:
            save_dir: 索引保存目录
        """
        if save_dir is None:
            # 使用项目目录下的相对路径
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            save_dir = os.path.join(project_root, "data", "faiss_index")

        self.save_dir = save_dir
        self.store = FAISSVectorStore(index_type="flat", dim=1024)

        # 内存中存储文档信息
        self.doc_info = {}  # {doc_id: {"title", "subject", "created_at"}}

        # 如果索引已存在，加载它
        if os.path.exists(os.path.join(save_dir, "index.npy")) or os.path.exists(os.path.join(save_dir, "index.faiss")):
            print(f"加载已有索引...")
            self.store.load(save_dir)
            self._load_doc_info()  # 同时加载文档信息
        else:
            print(f"创建新索引")

    def _save_doc_info(self):
        """保存文档信息"""
        import pickle
        os.makedirs(self.save_dir, exist_ok=True)  # 确保目录存在
        with open(os.path.join(self.save_dir, "doc_info.pkl"), "wb") as f:
            pickle.dump(self.doc_info, f)

    def _load_doc_info(self):
        """加载文档信息"""
        doc_info_path = os.path.join(self.save_dir, "doc_info.pkl")
        if os.path.exists(doc_info_path):
            import pickle
            with open(doc_info_path, "rb") as f:
                self.doc_info = pickle.load(f)

    def add_pdf(
        self,
        pdf_path: str,
        doc_id: Optional[str] = None,
        title: Optional[str] = None,
        subject: str = "未分类",
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> bool:
        """
        添加PDF到知识库

        Args:
            pdf_path: PDF文件路径
            doc_id: 文档ID（如果不提供，使用文件名）
            title: 文档标题（如果不提供，从PDF元数据提取）
            subject: 科目分类
            chunk_size: 文本块大小
            chunk_overlap: 文本块重叠

        Returns:
            是否成功
        """
        try:
            # 1. 提取PDF文本
            print(f"正在解析PDF: {pdf_path}")
            pdf_data = extract_text_from_pdf(pdf_path)
            text = clean_text(pdf_data["text"])

            # 使用传入的title或从PDF元数据提取
            if not title:
                title = pdf_data["metadata"]["title"]

            if not text or len(text.strip()) < 10:
                print("PDF内容为空或提取失败")
                return False

            # 2. 生成文档ID
            if doc_id is None:
                doc_id = os.path.splitext(os.path.basename(pdf_path))[0]

            # 3. 分割文本
            print(f"正在分割文本...")
            chunks = text_split_by_token(text, max_tokens=chunk_size, overlap=chunk_overlap)
            print(f"分割成 {len(chunks)} 个文本块")

            # 4. 获取向量
            print(f"正在生成向量（调用通义千问API）...")
            embeddings = get_embeddings_batch(chunks)
            print(f"完成 {len(embeddings)} 个向量")

            # 5. 添加到FAISS索引
            print(f"正在添加到索引...")
            self.store.add_vectors(
                embeddings=embeddings,
                doc_id=doc_id,
                chunks=chunks,
                metadata={
                    "title": title,
                    "subject": subject,
                    "created_at": datetime.now().isoformat()
                }
            )

            # 6. 保存文档信息
            self.doc_info[doc_id] = {
                "title": title,
                "subject": subject,
                "created_at": datetime.now().isoformat(),
                "chunk_count": len(chunks)
            }
            self._save_doc_info()

            # 7. 保存索引
            self.store.save(self.save_dir)

            print(f"文档 '{title}' 添加成功！")
            return True

        except Exception as e:
            print(f"添加PDF失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def add_text(
        self,
        text: str,
        doc_id: str,
        title: str,
        subject: str = "未分类",
        chunk_size: int = 500,
        chunk_overlap: int = 50
    ) -> bool:
        """
        添加纯文本到知识库

        Args:
            text: 文本内容
            doc_id: 文档ID
            title: 标题
            subject: 科目
            chunk_size: 文本块大小
            chunk_overlap: 文本块重叠

        Returns:
            是否成功
        """
        try:
            # 1. 清理文本
            text = clean_text(text)

            if not text or len(text.strip()) < 10:
                print("文本内容为空")
                return False

            # 2. 分割文本
            print(f"正在分割文本...")
            chunks = text_split_by_token(text, max_tokens=chunk_size, overlap=chunk_overlap)
            print(f"分割成 {len(chunks)} 个文本块")

            # 3. 获取向量
            print(f"正在生成向量...")
            embeddings = get_embeddings_batch(chunks)
            print(f"完成 {len(embeddings)} 个向量")

            # 4. 添加到FAISS索引
            print(f"正在添加到索引...")
            self.store.add_vectors(
                embeddings=embeddings,
                doc_id=doc_id,
                chunks=chunks,
                metadata={
                    "title": title,
                    "subject": subject,
                    "created_at": datetime.now().isoformat()
                }
            )

            # 5. 保存文档信息
            self.doc_info[doc_id] = {
                "title": title,
                "subject": subject,
                "created_at": datetime.now().isoformat(),
                "chunk_count": len(chunks)
            }
            self._save_doc_info()

            # 6. 保存索引
            self.store.save(self.save_dir)

            print(f"文档 '{title}' 添加成功！")
            return True

        except Exception as e:
            print(f"添加文本失败: {e}")
            import traceback
            traceback.print_exc()
            return False

    def search(self, query: str, top_k: int = 5, subject: Optional[str] = None) -> List[Dict]:
        """
        向量搜索

        Args:
            query: 查询文本
            top_k: 返回前K个结果
            subject: 科目过滤

        Returns:
            搜索结果
        """
        try:
            from backend.knowledge.embedding import get_embedding

            # 1. 获取查询向量
            query_embedding = get_embedding(query)

            # 2. 向量搜索
            results = self.store.search(query_embedding, top_k=top_k)

            # 3. 过滤科目
            if subject:
                results = [
                    r for r in results
                    if r["metadata"].get("subject") == subject
                ]

            return results

        except Exception as e:
            print(f"搜索失败: {e}")
            return []

    def delete_document(self, doc_id: str) -> bool:
        """删除文档"""
        success = self.store.delete_document(doc_id)
        if success:
            if doc_id in self.doc_info:
                del self.doc_info[doc_id]
            self._save_doc_info()
            self.store.save(self.save_dir)
        return success

    def list_documents(self) -> List[Dict]:
        """列出所有文档"""
        docs = []
        for doc_id, info in self.doc_info.items():
            docs.append({
                "doc_id": doc_id,
                "title": info["title"],
                "subject": info["subject"],
                "chunk_count": info["chunk_count"],
                "created_at": info["created_at"]
            })
        return docs

    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = self.store.get_stats()
        stats["total_subjects"] = len(set(info["subject"] for info in self.doc_info.values()))
        return stats


# 测试
if __name__ == "__main__":
    # 初始化
    kb = FAISSKnowledgeBase()

    # 测试添加PDF
    # kb.add_pdf("python_book.pdf", subject="Python编程")

    # 测试搜索
    # results = kb.search("什么是Python列表？", top_k=3)
    # for i, r in enumerate(results, 1):
    #     print(f"\n结果{i}:")
    #     print(f"  相似度: {r['similarity']:.4f}")
    #     print(f"  内容: {r['content'][:100]}...")
