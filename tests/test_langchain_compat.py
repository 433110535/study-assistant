"""确认当前代码能在 LangChain 1.x 上组装模型与工具，不调用远端接口。"""
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestLangChainCompat(unittest.TestCase):
    def test_text_content_accepts_blocks(self):
        from backend.llm_helper import text_content

        self.assertEqual(text_content("你好"), "你好")
        self.assertEqual(
            text_content([{"type": "text", "text": "甲"}, {"type": "text", "text": "乙"}]),
            "甲乙",
        )
        self.assertEqual(text_content(None), "")

    def test_chat_model_binds_tools_without_request(self):
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI

        import langchain_core
        import langchain_openai

        self.assertTrue(langchain_core.__version__.startswith("1."))
        self.assertTrue(langchain_openai.__version__.startswith("1."))

        model = ChatOpenAI(
            model="qwen-max",
            api_key="sk-test",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0,
            max_tokens=16,
            request_timeout=60,
            max_retries=1,
        )
        bound = model.bind_tools(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "grade_item",
                        "description": "判分",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]
        )
        prompt = ChatPromptTemplate.from_messages([("human", "{question}")])
        chain = prompt | model
        self.assertIsNotNone(bound)
        self.assertTrue(hasattr(chain, "invoke"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
