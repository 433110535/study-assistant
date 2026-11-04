"""
向量知识库初始化脚本（FAISS版本 - 无需PostgreSQL）
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.knowledge.knowledge_base_faiss import FAISSKnowledgeBase


def init_knowledge_base():
    """初始化知识库"""
    print("=" * 60)
    print("向量知识库初始化 (FAISS版本)")
    print("=" * 60)
    print("\n✅ 使用FAISS存储，无需安装PostgreSQL！")
    print("   索引将保存在: E:/比赛项目/智能体/data/faiss_index")

    kb = FAISSKnowledgeBase()
    return kb


def add_pdf_interactive(kb: FAISSKnowledgeBase):
    """交互式添加PDF"""
    print("\n" + "=" * 60)
    print("添加PDF到知识库")
    print("=" * 60)

    pdf_path = input("\n请输入PDF文件路径: ").strip().strip('"')

    if not os.path.exists(pdf_path):
        print(f"❌ 文件不存在: {pdf_path}")
        return

    subject = input("请输入科目分类 (默认: 未分类): ").strip() or "未分类"
    chunk_size = int(input("文本块大小token数 (默认: 500): ").strip() or "500")

    print("\n开始处理...")
    kb.add_pdf(
        pdf_path=pdf_path,
        subject=subject,
        chunk_size=chunk_size
    )


def list_documents(kb: FAISSKnowledgeBase):
    """列出所有文档"""
    print("\n" + "=" * 60)
    print("知识库文档列表")
    print("=" * 60)

    docs = kb.list_documents()

    if not docs:
        print("\n📭 知识库为空，还没有添加任何文档")
        return

    print(f"\n共 {len(docs)} 个文档:\n")

    for i, doc in enumerate(docs, 1):
        print(f"{i}. {doc['title']}")
        print(f"   ID: {doc['doc_id']}")
        print(f"   科目: {doc['subject']}")
        print(f"   文本块数: {doc['chunk_count']}")
        print(f"   添加时间: {doc['created_at']}")
        print()


def search_test(kb: FAISSKnowledgeBase):
    """测试搜索功能"""
    print("\n" + "=" * 60)
    print("向量搜索测试")
    print("=" * 60)

    query = input("\n请输入搜索内容: ").strip()

    if not query:
        print("❌ 搜索内容不能为空")
        return

    print(f"\n正在搜索: {query}")
    results = kb.search(query, top_k=5)

    if not results:
        print("\n❌ 未找到相关内容")
        return

    print(f"\n找到 {len(results)} 个相关结果:\n")

    for i, r in enumerate(results, 1):
        print(f"结果 {i}:")
        print(f"  相似度: {r['similarity']:.4f}")
        print(f"  文档: {r['metadata']['title']}")
        print(f"  科目: {r['metadata']['subject']}")
        print(f"  内容: {r['content'][:150]}...")
        print()


def main():
    """主菜单"""
    print("\n" + "=" * 60)
    print(" 智能学习助手 - 向量知识库管理工具")
    print(" (FAISS版本 - 无需PostgreSQL)")
    print("=" * 60)

    # 初始化知识库
    try:
        kb = init_knowledge_base()
        stats = kb.get_stats()
        print(f"\n当前状态:")
        print(f"  文档数: {stats.get('total_documents', 0)}")
        print(f"  文本块数: {stats.get('total_chunks', 0)}")
        print(f"  科目数: {stats.get('total_subjects', 0)}")
    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 主循环
    while True:
        print("\n" + "=" * 60)
        print("主菜单:")
        print("1. 添加PDF")
        print("2. 查看文档列表")
        print("3. 测试搜索")
        print("4. 查看统计信息")
        print("5. 删除文档")
        print("0. 退出")

        choice = input("\n请选择 (0-5): ").strip()

        if choice == "1":
            add_pdf_interactive(kb)
        elif choice == "2":
            list_documents(kb)
        elif choice == "3":
            search_test(kb)
        elif choice == "4":
            stats = kb.get_stats()
            print("\n统计信息:")
            print(f"  文档总数: {stats.get('total_documents', 0)}")
            print(f"  文本块总数: {stats.get('total_chunks', 0)}")
            print(f"  科目数: {stats.get('total_subjects', 0)}")
        elif choice == "5":
            doc_id = input("请输入要删除的文档ID: ").strip()
            if kb.delete_document(doc_id):
                print(f"✅ 文档 {doc_id} 已删除")
        elif choice == "0":
            print("\n👋 再见！")
            break
        else:
            print("❌ 无效选择")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 程序已中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
