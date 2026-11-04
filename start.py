"""
一键启动脚本（通义千问）
"""
import os
import sys
from pathlib import Path


def check_env():
    """检查环境配置"""
    env_file = Path(".env")

    if not env_file.exists():
        print("未找到 .env 文件")
        print("正在创建 .env 文件...")

        if Path(".env.example").exists():
            import shutil
            shutil.copy(".env.example", ".env")
            print("已创建 .env 文件")
            print("请编辑 .env 文件，填入你的通义千问 API Key")
            print("获取地址: https://dashscope.console.aliyun.com/")
            return False
        else:
            print("未找到 .env.example 文件")
            return False
    else:
        return True


def check_dependencies():
    """检查依赖是否安装"""
    try:
        import langchain_core
        import streamlit
        print("依赖已安装")
        return True
    except ImportError as e:
        print(f"缺少依赖: {e}")
        print("请运行: pip install -r requirements.txt")
        return False


def check_api_key():
    """检查通义千问 API Key 是否配置"""
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key or api_key == "your_dashscope_api_key_here":
        print("请在 .env 文件中配置 DASHSCOPE_API_KEY")
        print("获取地址: https://dashscope.console.aliyun.com/")
        return False

    return True


def start_frontend():
    """启动前端"""
    print("\n启动 Streamlit 前端...")
    print("=" * 50)
    print("访问地址: http://localhost:8501")
    print("=" * 50)
    print("\n按 Ctrl+C 停止运行\n")

    os.chdir(Path(__file__).resolve().parent)
    # 用当前解释器启动，避免 streamlit 未加入 PATH 时报错
    os.system(f'"{sys.executable}" -m streamlit run frontend/app.py --server.port 8501')


def main():
    """主函数"""
    # 统一以项目根目录为工作目录，保证 .env / data / frontend 路径正确
    os.chdir(Path(__file__).resolve().parent)

    print("\n")
    print("智能学习助手 - 启动脚本")
    print("=" * 50)

    if not check_env():
        print("\n请先完成配置后再运行")
        return

    if not check_dependencies():
        return

    if not check_api_key():
        return

    print("\n环境检查通过!")
    print(f"当前目录: {os.getcwd()}")
    print(f"使用模型: {os.getenv('LLM_MODEL', 'qwen-max')}")

    start_frontend()


if __name__ == "__main__":
    main()
