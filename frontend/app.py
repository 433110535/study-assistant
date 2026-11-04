"""
学习辅助平台 - 前端界面
视觉语言：Plane 风格工作台（白底 / 细线 / 深蓝强调，规范见 F:/UI/design.md）
"""
import streamlit as st
import sys
import html
import hmac
import os
import time
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.agents.react_agent import ReActStudyAgent
from backend.llm_helper import text_content
from backend.agents.react_models import ReActResult, ReActStep, ReActEventType
from backend.tools.knowledge import explain_concept, break_down_concept, compare_concepts
from backend.tools.plan_generator import generate_study_plan, create_daily_schedule, generate_milestone_checklist
from backend.tools.question_generator import generate_questions, check_answer
from backend.config import validate_config, LLM_MODEL, UPLOADS_DIR
import re
import tempfile
import uuid

# 平台标识：打开的书页 + 知识节点 + 右上角火花
LOGO_SVG = (
    '<svg class="logo-glyph" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
    '<path d="M3.6 7.1c2.8-1.2 5.6-1.2 8.4.1 2.8-1.3 5.6-1.3 8.4-.1v10.7c-2.8-1.2-5.6-1.2-8.4.1-2.8-1.3-5.6-1.3-8.4-.1V7.1Z"/>'
    '<path d="M12 7.2v10.7"/>'
    '<circle cx="12" cy="11.8" r="1.15" fill="currentColor" stroke="none"/>'
    '<path d="M17.6 3.4v2.4M16.4 4.6h2.4"/>'
    '</svg>'
)

# 登录凭据：优先读取环境变量，未配置时使用本地演示账号
_ENV_APP_USER = os.getenv("APP_USERNAME")
_ENV_APP_PASSWORD = os.getenv("APP_PASSWORD")
if _ENV_APP_USER and _ENV_APP_PASSWORD:
    APP_USERNAME = _ENV_APP_USER
    APP_PASSWORD = _ENV_APP_PASSWORD
    USING_DEMO_AUTH = False
else:
    APP_USERNAME = "student"
    APP_PASSWORD = "study2026"
    USING_DEMO_AUTH = True

# FAISS向量知识库
try:
    from backend.knowledge.knowledge_base_faiss import FAISSKnowledgeBase
    FAISS_KB_AVAILABLE = True
except ImportError:
    FAISSKnowledgeBase = None
    FAISS_KB_AVAILABLE = False


def highlight_keywords(text: str, query: str) -> str:
    """在文本中高亮搜索关键词"""
    try:
        import jieba
        words = [w for w in jieba.cut(query) if len(w.strip()) > 1]
    except ImportError:
        # jieba未安装时按空格和标点拆分
        import re
        words = [w for w in re.split(r'[\s,，。.!！?？;；、]+', query) if len(w.strip()) > 1]
    if not words:
        words = [query.strip()]
    words = list(set(words))
    highlighted = html.escape(text)
    for word in words:
        escaped = html.escape(word)
        highlighted = highlighted.replace(escaped, f"<mark>{escaped}</mark>")
    return highlighted


def prepare_markdown(text: str) -> str:
    """把模型常用的 LaTeX 分隔符转换为 Streamlit 可渲染的 $ / $$。

    代码块与行内代码保持原样，避免误伤代码里的反斜杠。
    """
    if not text:
        return text
    parts = re.split(r'(```[\s\S]*?```|~~~[\s\S]*?~~~|`[^`\n]*`)', text)
    for i in range(0, len(parts), 2):
        segment = parts[i]
        segment = re.sub(r'\\\[(.*?)\\\]', lambda m: f"$${m.group(1)}$$", segment, flags=re.S)
        segment = re.sub(r'\\\((.*?)\\\)', lambda m: f"${m.group(1)}$", segment, flags=re.S)
        parts[i] = segment
    return "".join(parts)


st.set_page_config(
    page_title="学习辅助平台",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# 设计系统样式（独立样式表，便于维护）
# ============================================================
STYLES_PATH = Path(__file__).resolve().parent / "styles.css"
st.markdown(
    f"<style>{STYLES_PATH.read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)

# ============================================================
# 页面元信息（侧边栏、顶栏、页头共用）
# ============================================================
PAGES = [
    ("dashboard", "01", "OVERVIEW", "数据看板", "学习统计与进度"),
    ("qa", "02", "DIALOGUE", "在线问答", "多步推理问答"),
    ("react_viz", "03", "REASONING", "思维链", "推理与工具调用"),
    ("knowledge", "04", "EXPLAIN", "知识讲解", "概念深度解析"),
    ("compare", "05", "COMPARE", "概念对比", "差异与边界"),
    ("planner", "06", "PLANNING", "学习计划", "目标拆解"),
    ("daily", "07", "SCHEDULE", "日程安排", "每日时间表"),
    ("quiz", "08", "PRACTICE", "习题练习", "出题与批改"),
    ("kb", "09", "KNOWLEDGE BASE", "向量知识库", "RAG 检索"),
    ("mistakes", "10", "MISTAKES", "错题本", "确认后进入复习"),
    ("code", "11", "CODE", "代码助教", "沙箱运行与分级提示"),
    ("eval", "12", "EVAL", "失败归因", "评测缺失工具"),
]
PAGE_META = {page[0]: page[1:] for page in PAGES}


def page_header(page_key: str, chips=None):
    """统一页头：编号 / 英文标签 / 标题 / 描述 / 会话元信息"""
    no, en, title, sub = PAGE_META[page_key]
    chip_html = ""
    if chips:
        chip_html = '<div class="page-meta">' + "".join(
            f'<span class="chip">{chip}</span>' for chip in chips
        ) + "</div>"
    session_min = int(
        (datetime.now() - st.session_state.get('start_time', datetime.now())).total_seconds() // 60
    )
    weekday = "一二三四五六日"[datetime.now().weekday()]
    st.markdown(
        f'<div class="page-head">'
        f'<div class="page-head-main">'
        f'<div class="page-kicker"><span class="tick"></span>WORKSPACE {no} / {en}</div>'
        f'<h1 class="page-title">{title}</h1>'
        f'<p class="page-sub">{sub}</p>{chip_html}</div>'
        f'<div class="page-head-side">'
        f'<div class="ph-date">{datetime.now():%Y.%m.%d} · 周{weekday}</div>'
        f'<div class="ph-session">Session {session_min:02d} min</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def section_head(no: str, title: str, en: str = ""):
    """区块标题：等宽编号 + 细分隔线"""
    st.markdown(
        f'<div class="sec-head"><span class="no">/ {no}</span>'
        f'<h3>{title}</h3><span class="en">{en}</span>'
        f'<span class="rule"></span></div>',
        unsafe_allow_html=True,
    )


def empty_state(mark: str, title: str, body: str):
    """空状态占位"""
    st.markdown(
        f'<div class="empty"><div class="empty-mark">{mark}</div>'
        f'<div class="empty-title">{title}</div>'
        f'<p class="empty-body">{body}</p></div>',
        unsafe_allow_html=True,
    )


def top_bar(page_key: str):
    """吸顶工作区信息条"""
    _no, _en, title, _sub = PAGE_META[page_key]
    ready = bool(st.session_state.get("initialized", False))
    dot_cls = "dot" if ready else "dot is-off"
    status = "API 已连接" if ready else "API 未配置"
    st.markdown(
        f'<div class="topbar">'
        f'<div class="topbar-crumb"><span>学习辅助平台</span>'
        f'<span class="crumb-sep">/</span><b>{title}</b></div>'
        f'<div class="topbar-meta">'
        f'<span class="topbar-badge"><span class="{dot_cls}"></span>{status}</span>'
        f'<span class="topbar-model">{LLM_MODEL}</span>'
        f'<a class="topbar-logout" href="?logout=1" target="_self" title="退出登录">退出</a>'
        f'<span class="topbar-avatar" role="img" aria-label="学习辅助平台">{LOGO_SVG}</span>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def loading_html(message: str = "加载中...") -> str:
    """统一加载态 HTML（骨架 + 旋转指示）"""
    return (
        '<div class="custom-loader">'
        '<div class="custom-spinner"></div>'
        f'<div class="custom-loader-text">{message}</div>'
        "</div>"
    )


def show_loading(message: str = "加载中..."):
    """显示动态加载动画"""
    st.markdown(loading_html(message), unsafe_allow_html=True)


def init_session_state():
    if 'agent' not in st.session_state:
        try:
            validate_config()
            st.session_state.agent = ReActStudyAgent(verbose=False)
            st.session_state.agent.user_id = st.session_state.get("auth_user") or "student"
            st.session_state.initialized = True
            st.session_state.start_time = datetime.now()
        except ValueError as e:
            st.session_state.initialized = False
            st.session_state.error = str(e)

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    if 'concepts_learned' not in st.session_state:
        st.session_state.concepts_learned = []

    if 'plans_created' not in st.session_state:
        st.session_state.plans_created = []

    if 'quizzes_done' not in st.session_state:
        st.session_state.quizzes_done = []

    if 'knowledge_base' not in st.session_state:
        st.session_state.knowledge_base = []

    _restore_chat_session()


def _restore_chat_session() -> None:
    """登录后恢复该用户最近一次问答，刷新页面不丢记录。"""
    if st.session_state.get("chat_session_id"):
        return
    if not st.session_state.get("initialized"):
        return
    user_id = st.session_state.get("auth_user") or "student"
    try:
        from backend.platform.chat_store import ensure_session, load_messages

        session_id = ensure_session(user_id)
        messages = load_messages(session_id)
    except Exception:
        return
    st.session_state.chat_session_id = session_id
    st.session_state.messages = messages
    agent = st.session_state.get("agent")
    if agent is not None:
        agent.session_id = session_id
        agent.user_id = user_id
        agent.chat_history = [dict(item) for item in messages]


def _open_saved_chat(session_id: str) -> None:
    """切到一条已保存的问答，不删除其他会话。"""
    from backend.platform.chat_store import load_messages

    user_id = st.session_state.get("auth_user") or "student"
    messages = load_messages(session_id)
    st.session_state.chat_session_id = session_id
    st.session_state.messages = messages
    st.session_state.pop("qa_pending", None)
    agent = st.session_state.get("agent")
    if agent is not None:
        agent.session_id = session_id
        agent.user_id = user_id
        agent.chat_history = [dict(item) for item in messages]


def _persist_message(role: str, content: str) -> None:
    session_id = st.session_state.get("chat_session_id")
    if not session_id:
        return
    try:
        from backend.platform.chat_store import append_message

        append_message(session_id, role, content)
    except Exception:
        pass


def clear_session_data():
    """清空所有会话派生的界面状态（保留持久化向量索引）。"""
    for key in (
        "messages",
        "concepts_learned",
        "plans_created",
        "quizzes_done",
        "knowledge_base",
        "last_react_result",
        "last_explanation",
        "last_concept",
        "last_explanation_meta",
        "last_compare",
        "last_compare_meta",
        "last_plan",
        "last_plan_meta",
        "plan_progress",
        "last_quiz",
        "last_quiz_meta",
        "last_quiz_result",
        "quiz_score_count",
        "qa_pending",
        "qa_image_upload",
        "qa_ocr_override",
        "code_tutor_result",
        "code_tutor_source",
        "code_tutor_tests",
        "code_tutor_timeout",
        "code_tutor_level",
        "code_tutor_thread",
        "rag_history",
        "daily_schedule",
        "schedule_topics",
        "schedule_hours",
        "schedule_with_break",
        "schedule_break_duration",
        "user_input_field",
        "quiz_answer",
        "grade_question",
        "grade_student",
        "grade_correct",
        "grade_subject",
        "grade_concept",
        "grade_report",
        "vector_search_query",
        "rag_query",
    ):
        st.session_state.pop(key, None)

    st.session_state.start_time = datetime.now()
    agent = st.session_state.get("agent")
    if agent is not None:
        agent.clear_history()
    user_id = st.session_state.get("auth_user") or "student"
    try:
        from backend.platform.chat_store import start_session

        session_id = start_session(user_id)
        st.session_state.chat_session_id = session_id
        st.session_state.messages = []
        if agent is not None:
            agent.session_id = session_id
    except Exception:
        st.session_state.pop("chat_session_id", None)


def credentials_valid(username: str, password: str) -> bool:
    """使用常量时间比较，避免把密码直接暴露在普通字符串比较里。"""
    return hmac.compare_digest(username.strip(), APP_USERNAME) and hmac.compare_digest(password, APP_PASSWORD)


def logout():
    """退出登录：清空当前浏览器会话中的所有状态。"""
    for key in list(st.session_state.keys()):
        st.session_state.pop(key, None)
    st.query_params.clear()
    st.rerun()


def render_login():
    """登录页：左侧品牌叙事 + 右侧轻量登录卡。"""
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"],
        [data-testid="stSidebarCollapsedControl"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="login_page"):
        left, right = st.columns([1.08, 0.92], gap="large", vertical_alignment="center")

        with left:
            st.markdown(
                '<div class="login-hero">'
                '<div class="login-brand">'
                f'<div class="login-mark">{LOGO_SVG}</div>'
                '<div class="login-brand-text"><b>学习辅助平台</b><span>Study Workbench</span></div>'
                '</div>'
                '<div class="login-kicker">Workspace Access</div>'
                '<h1 class="login-headline">把学习，<br>变成一件有节奏的事。</h1>'
                '<p class="login-lede">从一个问题开始，让推理、检索与计划在同一条工作流里发生。'
                '问答、知识讲解、学习计划与练习，都收在同一张安静的工作台里。</p>'
                '<div class="login-points">'
                '<span>ReAct 多步推理</span><span>RAG 知识库</span>'
                '<span>学习计划</span><span>即时练习</span>'
                '</div>'
                '<div class="login-note">专注内容本身，而不是工具。'
                '你的学习记录只保存在当前设备。</div>'
                '</div>',
                unsafe_allow_html=True,
            )

        with right:
            with st.container(key="login_card"):
                st.markdown(
                    '<div class="login-card-kicker">Secure Access</div>'
                    '<div class="login-title">登录工作台</div>'
                    '<div class="login-sub">使用你的学习账号继续。</div>',
                    unsafe_allow_html=True,
                )

                with st.form("login_form"):
                    username = st.text_input(
                        "账号",
                        placeholder="请输入账号",
                        key="login_username",
                    )
                    password = st.text_input(
                        "密码",
                        type="password",
                        placeholder="请输入密码",
                        key="login_password",
                    )
                    submitted = st.form_submit_button(
                        "进入工作台",
                        type="primary",
                        use_container_width=True,
                    )

                    if submitted:
                        if credentials_valid(username, password):
                            st.session_state.authenticated = True
                            st.session_state.auth_user = username.strip()
                            st.session_state.start_time = datetime.now()
                            st.rerun()
                        else:
                            st.error("账号或密码不正确，请重试。")

                if USING_DEMO_AUTH:
                    st.markdown(
                        '<div class="login-demo">演示账号 <b>student</b>'
                        '<span>·</span>密码 <b>study2026</b></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div class="login-demo">账号由环境变量 APP_USERNAME / APP_PASSWORD 配置</div>',
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    '<div class="login-foot">本地运行 · 无云端账号 · 会话结束后需重新登录</div>',
                    unsafe_allow_html=True,
                )


def render_sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="brand">'
            f'<div class="brand-mark">{LOGO_SVG}</div>'
            '<div><div class="brand-name">学习辅助平台</div>'
            '<div class="brand-sub">Study Workbench</div></div>'
            "</div>",
            unsafe_allow_html=True,
        )

        if not st.session_state.get('initialized', False):
            st.error("系统未初始化")
            st.info(st.session_state.get('error', '配置错误'))
            st.markdown(
                "**配置步骤**  \n1. 复制 `.env.example` 为 `.env`  \n"
                "2. 填入 `DASHSCOPE_API_KEY`  \n3. 重启应用  \n\n"
                "[获取 API Key](https://dashscope.console.aliyun.com/)"
            )
            # 缺 Key 时模型功能不可用，但整卷离线判分不依赖模型，页面要继续渲染。

        st.markdown(
            f'<div class="rail-label"><span>Workspace</span><span>{len(PAGES)} modules</span></div>',
            unsafe_allow_html=True,
        )

        current_page = st.session_state.get('current_page', 'dashboard')

        with st.container(key="nav"):
            for page_key, _no, _en, title, desc in PAGES:
                if st.button(
                    f"**{title}**\n{desc}",
                    key=f"nav_{page_key}",
                    use_container_width=True,
                    type="primary" if page_key == current_page else "secondary",
                ):
                    st.session_state.current_page = page_key
                    st.rerun()

        duration = int((datetime.now() - st.session_state.get('start_time', datetime.now())).total_seconds() // 60)
        msg_count = len(st.session_state.messages) // 2

        st.markdown(
            '<div class="rail-label is-session">'
            '<span>Session</span><span class="rail-live"><span class="dot"></span>Live</span></div>'
            '<div class="rail-metrics">'
            f'<div><div class="k">Dialogues</div><div class="v">{msg_count}<small>次</small></div></div>'
            f'<div><div class="k">Minutes</div><div class="v">{duration}<small>分</small></div></div>'
            "</div>",
            unsafe_allow_html=True,
        )

        with st.container(key="reset"):
            if st.session_state.get("confirm_clear"):
                st.markdown(
                    '<div class="confirm-box">'
                    '<b>确认开启新会话？</b>'
                    '<span>当前页面上的问答、讲解、计划与练习会清空。已保存的问答仍留在本机数据库。</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("取消", key="cancel_clear", use_container_width=True):
                        st.session_state.pop("confirm_clear", None)
                        st.rerun()
                with cc2:
                    if st.button("确认清空", key="confirm_clear_btn", type="primary", use_container_width=True):
                        st.session_state.pop("confirm_clear", None)
                        clear_session_data()
                        st.rerun()
            else:
                if st.button("开启新会话", key="clear_session_btn", use_container_width=True):
                    st.session_state.confirm_clear = True
                    st.rerun()

        st.markdown(
            '<div class="rail-foot">'
            f'<div class="row"><span>User</span><b>{html.escape(st.session_state.get("auth_user", "—"))}</b></div>'
            f'<div class="row"><span>Model</span><b>{LLM_MODEL}</b></div>'
            '<div class="row"><span>Vector</span><b>FAISS · 1024d</b></div>'
            '<div class="row"><span>Build</span><b>v1.1.0</b></div>'
            "</div>",
            unsafe_allow_html=True,
        )


def render_dashboard():
    page_header("dashboard", chips=[
        f"<b>模型</b> {LLM_MODEL}",
        "<b>存储</b> FAISS · 本地",
        "<b>统计范围</b> 当前会话",
    ])

    msg_count = len(st.session_state.messages) // 2
    concepts_count = len(st.session_state.concepts_learned)
    plans_count = len(st.session_state.plans_created)
    quizzes_count = len(st.session_state.quizzes_done)
    total = msg_count + concepts_count + plans_count + quizzes_count
    duration_min = int((datetime.now() - st.session_state.get('start_time', datetime.now())).total_seconds() // 60)

    def share(value: int) -> int:
        return int(round(value * 100 / total)) if total else 0

    stats = [
        ("问答次数", "Dialogues", msg_count),
        ("学习概念", "Concepts", concepts_count),
        ("学习计划", "Plans", plans_count),
        ("完成练习", "Practice", quizzes_count),
    ]

    st.markdown(
        '<div class="stat-strip">' + "".join(
            f'<div class="stat"><div class="stat-k"><i></i>{label}</div>'
            f'<div class="stat-v">{value}<small>次</small></div>'
            f'<div class="stat-meter"><span style="width:{share(value)}%"></span></div>'
            f'<div class="stat-note">{en} / {share(value)}%</div></div>'
            for label, en, value in stats
        ) + "</div>",
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.3, 1], gap="large")

    with left:
        section_head("01", "学习分布", "ACTIVITY MIX")
        if total:
            rows = "".join(
                f'<div class="dist-row"><div class="dist-label">{label}</div>'
                f'<div class="dist-track"><div class="dist-fill" style="width:{share(value)}%"></div></div>'
                f'<div class="dist-val">{value}</div></div>'
                for label, _en, value in stats
            )
            st.markdown(f'<div class="dist">{rows}</div>', unsafe_allow_html=True)
        else:
            empty_state(
                "NO DATA",
                "还没有学习记录",
                "从一次问答、一个概念或一组练习开始，这里会自动生成你的学习画像。",
            )

    with right:
        section_head("02", "本次会话", "SESSION")
        summary = [
            ("时长", f"{duration_min} 分钟"),
            ("对话", msg_count),
            ("概念", concepts_count),
            ("计划", plans_count),
            ("练习", quizzes_count),
        ]
        st.markdown(
            '<div class="sum-list">' + "".join(
                f'<div class="sum-row"><span class="k">{key}</span><span class="v">{value}</span></div>'
                for key, value in summary
            ) + "</div>",
            unsafe_allow_html=True,
        )

        agent = st.session_state.get('agent')
        kb_ready = bool(agent and getattr(agent, "_kb", None) is not None)
        sys_rows = [
            ("推理服务", '<span class="dot"></span>已连接' if st.session_state.get("initialized") else '<span class="dot is-off"></span>未配置'),
            ("向量检索", '<span class="dot"></span>已就绪' if kb_ready else '<span class="dot is-off"></span>未启用'),
            ("当前模型", f"<b>{LLM_MODEL}</b>"),
            ("会话时长", f"{duration_min} 分钟"),
        ]
        section_head("03", "系统状态", "SYSTEM")
        st.markdown(
            '<div class="sys">' + "".join(
                f'<div class="sys-row"><span class="sys-k">{key}</span><span class="sys-v">{value}</span></div>'
                for key, value in sys_rows
            ) + "</div>",
            unsafe_allow_html=True,
        )

    section_head("04", "快速入口", "SHORTCUTS")

    with st.container(key="quick"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("**在线问答**\nRAG 增强 · 多步推理", use_container_width=True, key="d_qa"):
                st.session_state.current_page = 'qa'
                st.rerun()
        with col2:
            if st.button("**知识讲解**\n概念拆解 · 逐层深入", use_container_width=True, key="d_kn"):
                st.session_state.current_page = 'knowledge'
                st.rerun()
        with col3:
            if st.button("**习题练习**\n智能出题 · 即时批改", use_container_width=True, key="d_qz"):
                st.session_state.current_page = 'quiz'
                st.rerun()
        with col4:
            if st.button("**学习计划**\n目标拆解 · 进度追踪", use_container_width=True, key="d_pl"):
                st.session_state.current_page = 'planner'
                st.rerun()


QA_PROMPTS = [
    "用类比解释反向传播，并给出一个数值例子",
    "帮我制定两周的线性代数复习计划",
    "对比 Transformer 与 RNN 的建模差异",
]


def _save_qa_upload(uploaded_file) -> str:
    """保存问答页上传的图片到 data/uploads，返回绝对路径"""
    suffix = Path(uploaded_file.name).suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest = UPLOADS_DIR / f"{uuid.uuid4().hex}{suffix}"
    dest.write_bytes(uploaded_file.getvalue())
    return str(dest.resolve())


def _build_qa_agent_input(
    user_text: str,
    image_path: str | None = None,
    ocr_override: str = "",
) -> str:
    """组装发给 Agent 的文本（含图片路径等机器可读上下文）"""
    parts: list[str] = []
    text = user_text.strip()
    if text:
        parts.append(text)
    if image_path:
        parts.append(f"\n[题目图片路径] {image_path}")
        parts.append(
            "用户上传了题目图片。请先调用 read_image 识别题干，"
            "再视需要 rag_search 查教材，分步讲解并给 1 道同考点变式题。"
        )
    override = ocr_override.strip()
    if override:
        parts.append(f"\n[用户修正的识别文本]\n{override}")
    return "\n".join(parts).strip()


def _qa_display_label(user_text: str, has_image: bool) -> str:
    text = user_text.strip()
    if text and has_image:
        return f"{text}\n（已附题目图片）"
    if text:
        return text
    if has_image:
        return "（上传题目图片，请讲解）"
    return ""


def _stream_answer(question: str):
    """执行一次 ReAct 流式回答（用户消息已写入 messages）"""
    status_placeholder = st.empty()
    steps_placeholder = st.empty()
    # 流式回答的容器带 key，样式与最终气泡一致；内容为空时由 CSS 隐藏
    with st.container(key="stream_answer"):
        answer_placeholder = st.empty()

    try:
        full_response = ""
        collected_steps = []
        step_num = 0
        status_placeholder.markdown(loading_html("正在分析问题 · 判断是否需要检索"), unsafe_allow_html=True)

        for event in st.session_state.agent.react_stream(question):
            if event.event_type == ReActEventType.THINKING:
                step_num += 1
                status_placeholder.markdown(loading_html(f"第 {step_num} 步 · {event.content}"), unsafe_allow_html=True)

            elif event.event_type == ReActEventType.TOOL_CALL:
                step_num += 1
                status_placeholder.markdown(loading_html(f"第 {step_num} 步 · 调用工具 {event.tool_name}"), unsafe_allow_html=True)
                collected_steps.append({
                    "step": step_num,
                    "type": "tool_call",
                    "tool": event.tool_name,
                    "args": event.tool_args,
                    "detail": f"调用工具: {event.tool_name}",
                })

            elif event.event_type == ReActEventType.TOOL_RESULT:
                step_num += 1
                status_placeholder.markdown(loading_html(f"第 {step_num} 步 · 获取 {event.tool_name} 结果"), unsafe_allow_html=True)
                collected_steps.append({
                    "step": step_num,
                    "type": "tool_result",
                    "tool": event.tool_name,
                    "detail": f"获取结果: {event.content[:80]}",
                })

            elif event.event_type == ReActEventType.ANSWER_CHUNK:
                full_response += event.content
                status_placeholder.empty()
                answer_placeholder.markdown(prepare_markdown(full_response))

            elif event.event_type == ReActEventType.FINAL_ANSWER:
                full_response = event.content
                status_placeholder.empty()
                answer_placeholder.markdown(prepare_markdown(full_response))

            elif event.event_type == ReActEventType.ERROR:
                status_placeholder.error(event.content)

        if collected_steps:
            with steps_placeholder.expander("推理过程 · REASONING TRACE", expanded=False):
                for s in collected_steps:
                    icon = "→" if s["type"] == "tool_call" else "←"
                    st.markdown(f"**第 {s['step']} 步** {icon} {s['detail']}")

        answer_placeholder.markdown(prepare_markdown(full_response))

        st.session_state.messages.append({"role": "assistant", "content": full_response})
        _persist_message("assistant", full_response)
        st.session_state.last_react_result = {
            "user_input": question,
            "final_answer": full_response,
            "steps": collected_steps,
            "total_iterations": max((s["step"] for s in collected_steps), default=0),
            "tools_used": list(set(s["tool"] for s in collected_steps if "tool" in s)),
        }

        time.sleep(0.35)
        st.rerun()

    except Exception as e:
        status_placeholder.empty()
        error_msg = f"发生错误: {str(e)}"
        st.error(error_msg)
        st.session_state.messages.append({"role": "assistant", "content": error_msg})
        _persist_message("assistant", error_msg)

        if "API" in str(e) or "key" in str(e):
            st.info("提示：请检查 .env 文件中的 API Key 配置")
        elif "连接" in str(e) or "network" in str(e):
            st.info("提示：请检查网络连接")

        time.sleep(2)
        st.rerun()


def _render_saved_chats() -> None:
    from backend.platform.chat_store import list_sessions

    user_id = st.session_state.get("auth_user") or "student"
    current = st.session_state.get("chat_session_id")
    sessions = list_sessions(user_id)
    if len(sessions) <= 1:
        return
    with st.expander("历史会话", expanded=False):
        for item in sessions:
            title = item["title"] or "新对话"
            label = title if item["id"] != current else f"{title} · 当前"
            if st.button(label, key=f"open_chat_{item['id']}", use_container_width=True):
                if item["id"] != current:
                    _open_saved_chat(item["id"])
                    st.rerun()


def render_qa():
    page_header("qa", chips=[
        "<b>模式</b> ReAct · 流式",
        "<b>感知</b> 拍照识题 · VL",
        "<b>推理</b> 工具调用可追溯",
    ])

    agent = st.session_state.get('agent')
    kb_ready = bool(agent and getattr(agent, "_kb", None) is not None)
    _render_saved_chats()

    rag_col, note_col = st.columns([1, 1.7], vertical_alignment="center")
    with rag_col:
        if kb_ready:
            use_rag = st.checkbox(
                "启用 RAG 知识库增强",
                value=True,
                key="qa_use_rag",
                help="开启后，回答会从知识库检索相关内容作为参考",
            )
            agent._rag_enabled = use_rag
        else:
            use_rag = False
            st.markdown('<div class="note-line"><span class="dot is-muted"></span>RAG 未启用</div>', unsafe_allow_html=True)

    with note_col:
        if kb_ready and use_rag:
            st.markdown('<div class="note-line on"><span class="dot"></span>RAG 已启用 · 回答基于知识库内容增强</div>', unsafe_allow_html=True)
        elif kb_ready:
            st.markdown('<div class="note-line"><span class="dot is-muted"></span>RAG 已关闭 · 通用问答模式</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="note-line"><span class="dot is-muted"></span>上传 PDF 到知识库可获得增强回答</div>', unsafe_allow_html=True)

    if not st.session_state.messages:
        st.markdown(
            '<div class="chat-hero">'
            '<div class="chat-hero-kicker">Start here · ReAct</div>'
            '<div class="chat-hero-title">从一个具体问题开始</div>'
            '<p class="chat-hero-body">学习助手会先判断是否需要检索知识库或调用工具，'
            "再给出带推理步骤的答案。开启 RAG 时，回答以你上传的资料为依据；"
            "关闭后进入通用问答模式。</p>"
            '<div class="chat-hero-points">'
            "<span>检索增强</span><span>多步推理</span><span>工具调用</span><span>过程可追溯</span>"
            "</div></div>",
            unsafe_allow_html=True,
        )

        clicked_prompt = None
        with st.container(key="prompts"):
            prompt_cols = st.columns(3)
            for idx, prompt in enumerate(QA_PROMPTS):
                with prompt_cols[idx]:
                    if st.button(prompt, key=f"qa_prompt_{idx}", use_container_width=True):
                        clicked_prompt = prompt

        if clicked_prompt:
            st.session_state.messages.append({"role": "user", "content": clicked_prompt})
            _persist_message("user", clicked_prompt)
            st.session_state.qa_pending = clicked_prompt
            st.rerun()

    for i, message in enumerate(st.session_state.messages):
        if message["role"] == "user":
            safe_content = html.escape(message["content"])
            st.markdown(f'<div class="msg-bubble msg-user">{safe_content}</div>', unsafe_allow_html=True)
        else:
            # 用 keyed container 承载 Markdown，保证表格、列表与代码块正常渲染
            with st.container(key=f"msg_ai_{i}"):
                st.markdown(prepare_markdown(message["content"]))

    pending = st.session_state.pop("qa_pending", None)
    if pending:
        _stream_answer(pending)

    with st.container(key="composer"):
        upload_col, hint_col = st.columns([1, 1.2], vertical_alignment="top")
        with upload_col:
            uploaded_image = st.file_uploader(
                "题目图片（可选）",
                type=["jpg", "jpeg", "png", "webp"],
                key="qa_image_upload",
                help="上传作业或试卷题目照片；Agent 会先识图再检索与讲解",
            )
            if uploaded_image is not None:
                st.image(uploaded_image, caption="待发送的题目图片", use_container_width=True)
                source = getattr(uploaded_image, "file_id", None) or (
                    uploaded_image.name,
                    uploaded_image.size,
                )
                if st.session_state.get("qa_ocr_source") != source:
                    from frontend.qa_image import preview_image_text, remember_ocr_preview

                    with st.spinner("正在识别题目…"):
                        recognized = preview_image_text(
                            uploaded_image.getvalue(),
                            Path(uploaded_image.name).suffix,
                        )
                    remember_ocr_preview(st.session_state, source, recognized)
        with hint_col:
            ocr_override = st.text_area(
                "识别结果修正（可选）",
                placeholder="上传图片后，识别文本会填在这里。可以改完再发送。",
                height=120,
                key="qa_ocr_override",
            )
            if st.button("清理本地上传目录", key="qa_clear_uploads", help="删除 data/uploads 下所有图片"):
                removed = 0
                if UPLOADS_DIR.exists():
                    for p in UPLOADS_DIR.iterdir():
                        if p.is_file():
                            p.unlink(missing_ok=True)
                            removed += 1
                st.toast(f"已清理 {removed} 个文件", icon="🗑️")

        with st.form("qa_form", clear_on_submit=True):
            input_col, send_col = st.columns([1, 0.16], vertical_alignment="bottom")
            with input_col:
                user_input = st.text_input(
                    "问题输入",
                    placeholder="输入问题，或只上传题目图片…",
                    label_visibility="collapsed",
                    key="user_input_field",
                )
            with send_col:
                submitted = st.form_submit_button("发送", type="primary", use_container_width=True)

        st.markdown(
            '<div class="composer-hint"><span>Enter 发送 · 回答支持 Markdown</span>'
            "<span>RAG · 识图 · 多步推理</span></div>",
            unsafe_allow_html=True,
        )

        if submitted:
            text = user_input.strip()
            has_image = uploaded_image is not None
            if not text and not has_image:
                st.warning("请输入问题或上传题目图片后再发送")
            else:
                image_path = _save_qa_upload(uploaded_image) if has_image else None
                display = _qa_display_label(text, bool(image_path))
                agent_input = _build_qa_agent_input(
                    text,
                    image_path=image_path,
                    ocr_override=st.session_state.get("qa_ocr_override", ""),
                )
                st.session_state.messages.append({"role": "user", "content": display})
                _persist_message("user", display)
                st.session_state.qa_pending = agent_input
                st.rerun()


def render_knowledge():
    page_header("knowledge", chips=[
        "<b>输出</b> 结构化讲解",
        "<b>深度</b> 初 / 中 / 高",
    ])

    left, right = st.columns([1.62, 1], gap="large")

    with left:
        with st.container(key="tool_panel"):
            section_head("01", "输入概念", "INPUT")
            concept = st.text_input(
                "概念名称",
                placeholder="例如：递归、动态规划、牛顿第二定律…",
                key="concept_input",
            )
            c1, c2 = st.columns(2)
            with c1:
                subject = st.text_input("学科（可选）", placeholder="例如：编程、数学…", key="subject_input")
            with c2:
                level = st.selectbox("讲解深度", ["初学者", "中级", "高级"], key="level_input")

            if st.button("开始讲解", type="primary", use_container_width=True, key="explain_btn"):
                if concept.strip():
                    with st.spinner("正在生成详细讲解，请稍候…"):
                        try:
                            result = explain_concept(concept, subject, level)
                            st.session_state.last_explanation = result
                            st.session_state.last_concept = concept
                            st.session_state.last_explanation_meta = {
                                "concept": concept,
                                "subject": subject.strip() or "通用",
                                "level": level,
                            }
                            if concept not in st.session_state.concepts_learned:
                                st.session_state.concepts_learned.append(concept)
                            st.success("讲解已生成")
                        except Exception as e:
                            st.error(f"生成失败: {str(e)}")
                else:
                    st.warning("请输入概念名称")

    with right:
        st.markdown(
            '<div class="helper-card">'
            '<div class="helper-k">How it works</div>'
            '<div class="helper-t">一次讲解会包含</div>'
            '<ol class="helper-list">'
            "<li><b>本质定义</b><span>用一句话说清它是什么</span></li>"
            "<li><b>直观类比</b><span>用熟悉的场景建立直觉</span></li>"
            "<li><b>分层展开</b><span>按你选择的深度逐层深入</span></li>"
            "<li><b>示例与边界</b><span>给出例子，并说明常见误区</span></li>"
            "</ol>"
            '<div class="helper-note">概念越具体，讲解越准确。补充学科与深度，可以得到更贴合课程的版本。</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    if 'last_explanation' in st.session_state:
        meta = st.session_state.get('last_explanation_meta', {})
        section_head("02", "讲解结果", "RESULT")
        st.markdown(
            '<div class="result-meta">'
            f'<span class="chip"><b>概念</b> {html.escape(str(meta.get("concept", st.session_state.get("last_concept", ""))))}</span>'
            f'<span class="chip"><b>学科</b> {html.escape(str(meta.get("subject", "通用")))}</span>'
            f'<span class="chip"><b>深度</b> {html.escape(str(meta.get("level", "")))}</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        with st.container(key="result_panel"):
            st.markdown(prepare_markdown(st.session_state.last_explanation))


def render_compare():
    page_header("compare", chips=[
        "<b>输出</b> 差异对照",
        "<b>范围</b> 定义 / 场景 / 边界",
    ])

    left, right = st.columns([1.62, 1], gap="large")

    with left:
        with st.container(key="tool_panel"):
            section_head("01", "选择对比对象", "INPUT")
            c1, c2 = st.columns(2)
            with c1:
                concept1 = st.text_input("概念 1", placeholder="例如：列表", key="compare_c1")
            with c2:
                concept2 = st.text_input("概念 2", placeholder="例如：元组", key="compare_c2")

            if st.button("开始对比", type="primary", use_container_width=True, key="compare_btn"):
                if concept1.strip() and concept2.strip():
                    with st.spinner("正在对比概念，请稍候…"):
                        try:
                            result = compare_concepts(concept1, concept2)
                            st.session_state.last_compare = result
                            st.session_state.last_compare_meta = {"c1": concept1, "c2": concept2}
                            for item in (concept1, concept2):
                                if item not in st.session_state.concepts_learned:
                                    st.session_state.concepts_learned.append(item)
                            st.success("对比已生成")
                        except Exception as e:
                            st.error(f"对比失败: {str(e)}")
                else:
                    st.warning("请输入两个概念")

    with right:
        st.markdown(
            '<div class="helper-card">'
            '<div class="helper-k">Comparison</div>'
            '<div class="helper-t">对比会覆盖这些维度</div>'
            '<ol class="helper-list">'
            "<li><b>核心定义</b><span>两者各自解决什么问题</span></li>"
            "<li><b>关键差异</b><span>结构、性能与使用方式的区别</span></li>"
            "<li><b>适用场景</b><span>什么时候选它，而不是另一个</span></li>"
            "<li><b>常见误区</b><span>容易混淆的边界与反例</span></li>"
            "</ol>"
            '<div class="helper-note">选择同一领域内的两个概念，对比结果会更聚焦、更有决策价值。</div>'
            "</div>",
            unsafe_allow_html=True,
        )

    if 'last_compare' in st.session_state:
        meta = st.session_state.get('last_compare_meta', {})
        section_head("02", "对比结果", "RESULT")
        st.markdown(
            '<div class="result-meta">'
            f'<span class="chip"><b>A</b> {html.escape(str(meta.get("c1", "")))}</span>'
            f'<span class="chip"><b>B</b> {html.escape(str(meta.get("c2", "")))}</span>'
            '<span class="chip"><b>模式</b> 差异对照</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        with st.container(key="result_panel"):
            st.markdown(prepare_markdown(st.session_state.last_compare))


def render_planner():
    page_header("planner", chips=[
        "<b>拆解</b> 目标 → 阶段 → 任务",
        "<b>周期</b> 7–90 天",
    ])

    section_head("01", "学习目标", "GOALS")

    with st.form("plan_form"):
        col1, col2 = st.columns(2)

        with col1:
            subject = st.text_input("学科或主题", placeholder="例如：Python编程、大学英语、高等数学…", help="你想学习什么内容")
            goal = st.text_area(
                "学习目标（详细描述你想达到什么效果）",
                placeholder="例如：能够独立开发小型Web应用、掌握日常英语对话、能解决微积分基础题目…",
                height=100,
                help="描述学习成功后你能做什么",
            )
            current_level = st.select_slider("当前水平", options=["零基础", "初学者", "中级", "高级"], value="初学者")

        with col2:
            duration_days = st.slider("学习周期（天）", 7, 90, 30, step=7, help="计划学习的总天数")
            hours_per_day = st.slider("每日学习时长（小时）", 0.5, 8.0, 2.0, step=0.5, help="每天能投入多少小时")

            m1, m2 = st.columns(2)
            with m1:
                st.metric("总学习时长", f"{duration_days * hours_per_day:.0f} 小时")
            with m2:
                st.metric("学习周期", f"{duration_days} 天")

        submitted = st.form_submit_button("生成学习计划", type="primary", use_container_width=True)

        if submitted and subject and goal:
            with st.spinner("正在制定个性化计划，请稍候…"):
                try:
                    plan = generate_study_plan(subject, goal, duration_days, current_level, hours_per_day)
                    st.session_state.last_plan = plan
                    # 新计划使用全新进度，避免沿用上一份计划的勾选状态
                    st.session_state.plan_progress = {}
                    for key in [k for k in st.session_state.keys() if str(k).startswith("plan_chk_")]:
                        st.session_state.pop(key, None)
                    st.session_state.last_plan_meta = {
                        "subject": subject,
                        "goal": goal,
                        "duration": duration_days,
                        "level": current_level,
                        "hours": hours_per_day,
                    }
                    st.session_state.plans_created.append({"subject": subject, "goal": goal})
                    st.success("计划生成完成")
                except Exception as e:
                    st.error(f"生成失败: {str(e)}")
                    st.info("提示：如果生成失败，请检查 API Key 配置或网络连接")

    if 'last_plan' in st.session_state:
        meta = st.session_state.get('last_plan_meta', {})
        section_head("02", "计划详情", "PLAN")
        st.markdown(
            '<div class="result-meta">'
            f'<span class="chip"><b>主题</b> {html.escape(str(meta.get("subject", "")))}</span>'
            f'<span class="chip"><b>周期</b> {meta.get("duration", "—")} 天</span>'
            f'<span class="chip"><b>强度</b> {meta.get("hours", "—")} 小时 / 天</span>'
            f'<span class="chip"><b>起点</b> {html.escape(str(meta.get("level", "")))}</span>'
            "</div>",
            unsafe_allow_html=True,
        )

        with st.container(key="result_panel"):
            if 'plan_progress' not in st.session_state:
                st.session_state.plan_progress = {}

            plan_text = st.session_state.last_plan
            lines = [l.strip() for l in plan_text.split('\n') if l.strip()]

            total_steps = len([l for l in lines if l.startswith(('- ', '* ', '##', '###', '第'))])
            completed = sum(1 for v in st.session_state.plan_progress.values() if v)
            if total_steps > 0:
                progress_pct = completed / total_steps
                st.progress(progress_pct, text=f"已完成 {completed}/{total_steps} · {progress_pct:.0%}")

            for i, line in enumerate(lines):
                if line.startswith(('## ', '### ', '第')):
                    checked = st.session_state.plan_progress.get(str(i), False)
                    col_check, col_text = st.columns([1, 24])
                    with col_check:
                        new_val = st.checkbox(" ", value=checked, key=f"plan_chk_{i}", label_visibility="collapsed")
                        st.session_state.plan_progress[str(i)] = new_val
                    with col_text:
                        if new_val:
                            st.markdown(f'<span class="plan-done">{line}</span>', unsafe_allow_html=True)
                        else:
                            st.markdown(line)
                else:
                    st.markdown(line)
    else:
        empty_state(
            "PLAN",
            "还没有学习计划",
            "填写目标、周期与每日投入后生成计划，完成进度会保存在当前会话中。",
        )


def render_daily():
    page_header("daily", chips=[
        "<b>输入</b> 主题列表",
        "<b>输出</b> 时间块",
    ])

    if 'daily_schedule' not in st.session_state:
        st.session_state.daily_schedule = None
        st.session_state.schedule_topics = []
        st.session_state.schedule_hours = 2.0
        st.session_state.schedule_with_break = True

    with st.container(key="tool_panel"):
        section_head("01", "今日安排", "INPUT")

        col1, col2 = st.columns([2.4, 1])

        with col1:
            topics_input = st.text_area(
                "输入要学习的内容（每行一个主题）",
                placeholder="例如：\n变量和数据类型\n条件语句\n循环结构\n函数定义\n面向对象编程",
                height=132,
                help="每行输入一个学习主题，可以输入多个主题",
            )

        with col2:
            available_hours = st.slider("可用时长（小时）", 0.5, 8.0, 2.0, step=0.5, help="今天有多少小时用于学习")
            include_break = st.checkbox("在学习主题之间加入休息", value=False, help="是否在学习主题之间添加休息时间")
            if include_break:
                break_duration = st.slider("休息时长（分钟）", 5, 30, 15, step=5, help="每次休息的分钟数")
            else:
                break_duration = 15

        col_btn1, col_btn2, col_btn3 = st.columns([1.3, 1, 1])
        with col_btn1:
            generate_clicked = st.button("生成时间表", type="primary", use_container_width=True)
        with col_btn2:
            clear_clicked = st.button("清空", use_container_width=True)
        with col_btn3:
            regen_clicked = st.button("重新生成", use_container_width=True)

        if generate_clicked:
            if topics_input:
                topics = [t.strip() for t in topics_input.split("\n") if t.strip()]
                st.session_state.schedule_topics = topics
                st.session_state.schedule_hours = available_hours
                st.session_state.schedule_with_break = include_break
                st.session_state.schedule_break_duration = break_duration
                st.session_state.daily_schedule = create_daily_schedule(topics, available_hours, include_break, break_duration)
                st.success("时间表生成成功")
            else:
                st.warning("请输入学习内容")

        if clear_clicked:
            st.session_state.daily_schedule = None
            st.session_state.schedule_topics = []
            st.rerun()

        if regen_clicked:
            if st.session_state.schedule_topics:
                st.session_state.daily_schedule = create_daily_schedule(
                    st.session_state.schedule_topics,
                    available_hours,
                    include_break,
                    break_duration,
                )
                st.session_state.schedule_hours = available_hours
                st.session_state.schedule_with_break = include_break
                st.session_state.schedule_break_duration = break_duration
                st.success("已重新生成")
            else:
                st.warning("请先生成时间表")

    if st.session_state.daily_schedule:
        section_head("02", "时间表", "SCHEDULE")
        st.markdown(
            '<div class="result-meta">'
            f'<span class="chip"><b>主题</b> {len(st.session_state.schedule_topics)} 个</span>'
            f'<span class="chip"><b>时长</b> {st.session_state.schedule_hours} 小时</span>'
            f'<span class="chip"><b>休息</b> {"已开启" if st.session_state.schedule_with_break else "未开启"}</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        with st.container(key="result_panel"):
            st.markdown(prepare_markdown(st.session_state.daily_schedule))

        st.info("提示：修改上方的学习内容和时长后，点击「重新生成」即可更新时间表。")
    else:
        empty_state(
            "SCHEDULE",
            "还没有时间表",
            "输入今天要学习的主题与可用时长，生成一份带时间块的日程安排。",
        )


def render_quiz():
    page_header("quiz", chips=[
        "<b>题型</b> 选择 / 填空 / 编程",
        "<b>批改</b> 标准答案对照",
    ])

    section_head("01", "出题设置", "SETUP")

    with st.form("quiz_form"):
        col1, col2, col3 = st.columns(3)

        with col1:
            topic = st.text_input("题目主题", placeholder="例如：Python列表、微积分、英语语法…", help="你想练习什么内容")
        with col2:
            difficulty = st.select_slider("难度等级", options=["基础", "中等", "困难"], value="中等", help="选择适合你的难度")
        with col3:
            count = st.number_input("题目数量", 1, 10, 3, step=1, help="一次生成多少道题")

        question_type = st.radio("题型选择", ["混合", "选择题", "填空题", "编程题"], horizontal=True, help="选择你想要的题目类型")

        submitted = st.form_submit_button("生成题目", type="primary", use_container_width=True)

        if submitted and topic:
            with st.spinner("正在生成练习题，请稍候…"):
                try:
                    qtype = "mixed" if question_type == "混合" else question_type
                    questions = generate_questions(topic, difficulty, count, qtype)
                    st.session_state.last_quiz = questions
                    # 新题不沿用上一轮的答案与批改结果
                    st.session_state.pop("last_quiz_result", None)
                    st.session_state.pop("quiz_answer", None)
                    st.session_state.last_quiz_meta = {"topic": topic, "difficulty": difficulty, "count": count}
                    st.session_state.quizzes_done.append({"topic": topic, "difficulty": difficulty})
                    st.success("题目生成完成")
                except Exception as e:
                    st.error(f"生成失败: {str(e)}")
                    st.info("提示：如果生成失败，请检查 API Key 配置或网络连接")

    if 'last_quiz' not in st.session_state:
        empty_state(
            "READY",
            "还没有练习题",
            "在上方设置主题、难度与题型，生成后会显示题目、作答区与批改结果。",
        )

    if 'last_quiz' in st.session_state:
        meta = st.session_state.get('last_quiz_meta', {})
        section_head("02", "练习题", "QUESTIONS")
        st.markdown(
            '<div class="result-meta">'
            f'<span class="chip"><b>主题</b> {html.escape(str(meta.get("topic", "")))}</span>'
            f'<span class="chip"><b>难度</b> {html.escape(str(meta.get("difficulty", "")))}</span>'
            f'<span class="chip"><b>数量</b> {meta.get("count", "—")} 题</span>'
            "</div>",
            unsafe_allow_html=True,
        )
        with st.container(key="result_panel"):
            st.markdown(prepare_markdown(st.session_state.last_quiz))

        section_head("03", "提交答案", "ANSWER")
        with st.container(key="tool_panel"):
            user_answer = st.text_area(
                "请输入你的答案（如: 1.A 2.B 3.递归函数）",
                placeholder="在这里写下你的答案…",
                height=132,
                key="quiz_answer",
            )

            if st.button("提交答案 · AI 批改", type="primary", use_container_width=True, key="submit_quiz"):
                if user_answer.strip():
                    with st.spinner("AI 正在批改…"):
                        try:
                            from backend.llm_helper import get_llm
                            from langchain_core.prompts import ChatPromptTemplate
                            llm = get_llm(temperature=0.3)
                            prompt = ChatPromptTemplate.from_messages([
                                ("system", """你是一位严格的老师。请根据以下题目批改学生的答案。

逐题判断对错，给出正确答案和简要解析，最后给出总分（X/Y）。

输出格式：
| 题号 | 学生答案 | 正确/错误 | 正确答案 | 解析 |
|------|---------|----------|---------|------|

总分: X/Y"""),
                                ("human", "[题目]\n{questions}\n\n[学生答案]\n{answers}")
                            ])
                            chain = prompt | llm
                            response = chain.invoke({
                                "questions": st.session_state.last_quiz,
                                "answers": user_answer,
                            })
                            st.session_state.last_quiz_result = text_content(response.content)
                            st.session_state.quiz_score_count = st.session_state.get('quiz_score_count', 0) + 1
                        except Exception as e:
                            st.error(f"批改失败: {str(e)}")
                else:
                    st.warning("请先输入答案")

        if 'last_quiz_result' in st.session_state:
            section_head("04", "批改结果", "REVIEW")
            with st.container(key="result_panel"):
                st.markdown(prepare_markdown(st.session_state.last_quiz_result))

    _render_standard_grade()


_VISION_ERROR_PREFIXES = (
    "图片不存在或不可读",
    "未配置 DASHSCOPE_API_KEY",
    "读取图片失败",
    "图片预处理失败",
    "视觉模型调用失败",
    "视觉模型返回错误",
    "未能从模型响应中解析识别文本",
    "识图失败",
)


def _is_vision_error(text: str) -> bool:
    stripped = (text or "").strip()
    return any(stripped.startswith(prefix) for prefix in _VISION_ERROR_PREFIXES)


def _grade_uploaded_paper(uploaded_file):
    """先识图，再离线整卷判分。失败时返回错误字符串，不抛异常。"""
    suffix = Path(getattr(uploaded_file, "name", "")).suffix.lower() or ".jpg"
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        Path(path).write_bytes(uploaded_file.getvalue())
        try:
            from backend.tools.vision import read_image

            recognized = read_image(path)
        except Exception as exc:
            return "", None, f"识图失败: {exc}"
        if not isinstance(recognized, str):
            recognized = str(recognized)
        if _is_vision_error(recognized):
            return "", None, recognized
        from backend.tools.grading import grade_paper

        return recognized, grade_paper(recognized), None
    except Exception as exc:
        return "", None, f"识图失败: {exc}"
    finally:
        Path(path).unlink(missing_ok=True)


def _render_paper_grade():
    """整卷文本或图片。判分本身不调用模型。"""
    from backend.tools.grading import format_paper, grade_paper

    st.markdown("**整卷逐题**")
    st.caption(
        "按题号粘贴整卷，或上传试卷图片。图片会先走现有识图，再离线判分。"
        "只列出每题结果和已判、未判数量，不把各题加总。"
        "多选、多空、带单位、公式和解答题不会硬判。"
    )
    paper = st.text_area(
        "整卷文本",
        height=180,
        key="grade_paper_text",
        placeholder="1. 3+4等于多少？\n作答：7\n标准答案：7",
    )
    image = st.file_uploader(
        "试卷图片（可选）",
        type=["jpg", "jpeg", "png", "webp"],
        key="grade_paper_image",
        help="上传后用现有识图得到文本，再做离线整卷判分",
    )
    if st.button("整卷判分", type="primary", key="grade_paper_run"):
        if image is not None:
            try:
                recognized, graded, error = _grade_uploaded_paper(image)
            except Exception as exc:
                recognized, graded, error = "", None, f"识图失败: {exc}"
            if error:
                st.session_state["paper_vision_error"] = error
                st.session_state.pop("paper_report", None)
                st.session_state.pop("paper_source_text", None)
            else:
                st.session_state["paper_vision_error"] = ""
                st.session_state["paper_source_text"] = recognized
                st.session_state["paper_report"] = graded
        else:
            text = (paper or "").strip()
            if not text:
                st.warning("请先粘贴整卷文本，或上传试卷图片")
            else:
                st.session_state["paper_vision_error"] = ""
                st.session_state.pop("paper_source_text", None)
                st.session_state["paper_report"] = grade_paper(text)

    error = st.session_state.get("paper_vision_error") or ""
    if error:
        st.error(error)
    source = st.session_state.get("paper_source_text") or ""
    if source:
        st.caption("识别文本")
        st.text(source)
    paper_report = st.session_state.get("paper_report")
    if paper_report:
        st.text(format_paper(paper_report))


def _render_standard_grade():
    """有标准答案时本地判分，不调用模型。错题仍要到错题本确认。"""
    from backend.platform.mistake_store import create_pending
    from backend.tools.grading import diagnose_error, grade_item, make_variants

    section_head("05", "对照标准答案", "KEY")
    st.caption(
        "填了标准答案才判对错。没有标准答案时不会给分。"
        "变式只替换题干里的数字，并且不附答案。记入错题本后，还要在「错题本」里确认。"
    )
    question = st.text_area("题干", height=100, key="grade_question", placeholder="例如：小明有 3 个苹果，又买了 5 个，一共几个？")
    left, right = st.columns(2)
    with left:
        student = st.text_input("你的答案", key="grade_student")
    with right:
        correct = st.text_input("标准答案", key="grade_correct", help="多个可接受答案用 || 分隔")
    subject_col, concept_col = st.columns(2)
    with subject_col:
        subject = st.text_input("学科", key="grade_subject", placeholder="数学")
    with concept_col:
        concept = st.text_input("考点", key="grade_concept", placeholder="加法")

    if st.button("判分", type="primary", key="grade_run"):
        graded = grade_item(question, student, correct)
        diagnosed = diagnose_error(question, student, correct) if graded["status"] == "incorrect" else None
        variants = make_variants(question, 3) if graded["status"] == "incorrect" else None
        st.session_state["grade_report"] = {
            "question": question,
            "student": student,
            "correct": correct,
            "subject": subject,
            "concept": concept,
            "graded": graded,
            "diagnosed": diagnosed,
            "variants": variants,
        }

    report = st.session_state.get("grade_report")
    if report:
        graded = report["graded"]
        labels = {"correct": "正确", "incorrect": "不正确", "ungraded": "未判分"}
        st.markdown(f"**{labels.get(graded['status'], graded['status'])}**")
        st.text(graded.get("reason") or "")
        diagnosed = report.get("diagnosed")
        if diagnosed and diagnosed.get("error_type"):
            st.text(f"错因：{diagnosed['error_type']}。{diagnosed.get('summary') or ''}")
        variants = report.get("variants") or {}
        if variants.get("status") == "ready":
            st.markdown("**变式（不附答案）**")
            for index, item in enumerate(variants.get("items") or [], start=1):
                st.text(f"{index}. {item['stem']}")
        elif variants.get("status") == "unsupported":
            st.caption(variants.get("reason") or "")

        if graded["status"] == "incorrect" and st.button("记入错题本", key="grade_save"):
            create_pending(
                user_id=st.session_state.get("auth_user") or "student",
                subject=(report.get("subject") or "").strip() or "未填写",
                concept=(report.get("concept") or "").strip() or "未命名考点",
                error_type=(diagnosed or {}).get("error_type") or "其他",
                question_text=report.get("question") or "",
                student_answer=report.get("student") or "",
                correct_answer=report.get("correct") or "",
            )
            st.success("已写入待确认错题。到「错题本」确认后才会进入复习。")

    _render_paper_grade()


def render_kb():
    page_header("kb", chips=[
        "<b>检索</b> FAISS · 1024d",
        "<b>来源</b> PDF 文档",
    ])

    if not FAISS_KB_AVAILABLE:
        st.warning("向量知识库需要安装FAISS")
        st.markdown("""
        ### 安装步骤

        运行以下命令安装依赖：

        ```bash
        pip install faiss-cpu pypdf
        ```

        然后重启应用。
        """)
        return

    # 功能说明
    with st.expander("向量知识库说明", expanded=False):
        st.markdown("""
        **什么是向量知识库（RAG）？**

        向量知识库使用AI技术将你的文档转换成向量（数字），然后通过计算相似度来搜索相关内容。

        **与传统搜索的区别：**
        - 传统搜索：只能匹配关键词，例如搜"Python列表"找不到"Python数组"
        - 向量搜索：理解语义，能找到意思相近的内容

        **功能：**
        1. 上传PDF文档（自动提取文本、分割、向量化）
        2. 向量搜索（找到语义相关的内容）
        3. RAG问答（AI基于检索到的内容回答问题）

        **使用场景：**
        - 上传课本、笔记PDF，然后问相关问题
        - AI会先从你的文档中找到相关内容，再回答
        - 答案准确、贴合你的学习资料
        """)

    # 初始化知识库（如果还没初始化）
    if 'vector_kb' not in st.session_state:
        with st.spinner("正在加载向量知识库..."):
            try:
                st.session_state.vector_kb = FAISSKnowledgeBase()
            except Exception as e:
                st.error(f"加载失败: {str(e)}")
                return

    kb = st.session_state.vector_kb

    # 显示统计信息
    stats = kb.get_stats()
    st.markdown(
        '<div class="kb-stats">'
        f'<div class="kb-stat"><div class="kb-stat-k">文档数</div>'
        f'<div class="kb-stat-v">{stats.get("total_documents", 0)}</div></div>'
        f'<div class="kb-stat"><div class="kb-stat-k">文本块</div>'
        f'<div class="kb-stat-v">{stats.get("total_chunks", 0)}</div></div>'
        '<div class="kb-stat is-wide"><div class="kb-stat-k">存储位置</div>'
        '<div class="kb-stat-v is-path">data/faiss_index</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )

    # 使用tabs组织功能
    tab1, tab2, tab3, tab4 = st.tabs(["上传PDF", "文档管理", "向量搜索", "RAG问答"])

    with tab1:
        section_head("01", "上传文档", "UPLOAD")

        with st.expander("上传说明与计费", expanded=False):
            st.markdown("""
            上传后系统会自动完成：提取文本 → 按块分割 → 生成向量（1024 维）→ 写入索引。

            - 处理时间：100 页 PDF 约需 1–2 分钟
            - API 成本：约 0.08 元 / 百页
            - 建议使用文字版 PDF；扫描版识别效果较差
            - 支持中英文文档，单个文件最大 50MB
            """)

        # PDF文件上传（限制50MB）
        MAX_PDF_SIZE = 50 * 1024 * 1024  # 50MB
        uploaded_file = st.file_uploader(
            "选择PDF文件",
            type=['pdf'],
            help="上传学习资料PDF（课本、笔记等），最大50MB",
            key="pdf_uploader"
        )

        # 检查文件大小
        if uploaded_file and hasattr(uploaded_file, 'size') and uploaded_file.size > MAX_PDF_SIZE:
            st.error(f"文件过大: {uploaded_file.size / 1024 / 1024:.1f}MB，最大支持50MB")
            uploaded_file = None

        # 文档信息
        col1, col2 = st.columns(2)
        with col1:
            doc_title = st.text_input(
                "文档标题",
                value=uploaded_file.name if uploaded_file else "",
                placeholder="例如：Python语言程序设计",
                key="pdf_title",
                label_visibility="visible"
            )
        with col2:
            subject = st.text_input(
                "学科分类",
                placeholder="例如：编程、数学、英语...",
                key="pdf_subject",
                label_visibility="visible"
            )

        col1, col2 = st.columns(2)
        with col1:
            chunk_size = st.slider(
                "文本块大小",
                min_value=200,
                max_value=1000,
                value=500,
                step=100,
                help="每块包含的字符数，越小越精细但调用API次数越多",
                key="chunk_size"
            )
        with col2:
            chunk_overlap = st.slider(
                "文本块重叠",
                min_value=0,
                max_value=100,
                value=50,
                step=10,
                help="相邻块之间重叠的字符数，保留上下文",
                key="chunk_overlap"
            )

        if st.button("开始处理PDF", type="primary", use_container_width=True, key="process_pdf"):
            if uploaded_file is not None:
                # 保存上传的文件
                import tempfile
                import os

                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(uploaded_file.getbuffer())
                    tmp_path = tmp_file.name

                # 使用st.status显示详细进度
                with st.status("正在处理PDF...", expanded=True) as status:
                    try:
                        status.write("步骤1/6: 解析PDF文件...")

                        from backend.knowledge.pdf_loader import extract_text_from_pdf, clean_text
                        data = extract_text_from_pdf(tmp_path)
                        text = clean_text(data["text"])
                        status.write(f"解析成功：{len(text)} 字符，{data['pages']} 页")

                        status.write("步骤2/6: 分割文本...")
                        from backend.knowledge.embedding import text_split_by_token
                        chunks = text_split_by_token(text, max_tokens=chunk_size, overlap=chunk_overlap)
                        status.write(f"分割成 {len(chunks)} 个文本块")

                        status.write("步骤3/6: 生成向量（调用通义千问API）...")
                        from backend.knowledge.embedding import get_embeddings_batch
                        embeddings = get_embeddings_batch(chunks)
                        status.write(f"生成 {len(embeddings)} 个向量")

                        status.write("步骤4/6: 添加到向量索引...")
                        doc_id = doc_title.replace(" ", "_")
                        kb.store.add_vectors(
                            embeddings=embeddings,
                            doc_id=doc_id,
                            chunks=chunks,
                            metadata={
                                "title": doc_title,
                                "subject": subject or "未分类",
                                "created_at": datetime.now().isoformat()
                            }
                        )

                        status.write("步骤5/6: 保存元数据...")
                        kb.doc_info[doc_id] = {
                            "title": doc_title,
                            "subject": subject or "未分类",
                            "created_at": datetime.now().isoformat(),
                            "chunk_count": len(chunks)
                        }
                        kb._save_doc_info()

                        status.write("步骤6/6: 保存向量索引...")
                        kb.store.save(kb.save_dir)

                        status.update(label="PDF处理完成", state="complete", expanded=False)

                        # 删除临时文件
                        os.unlink(tmp_path)

                        st.success(f"PDF '{doc_title}' 添加成功！")
                        time.sleep(1)
                        st.rerun()

                    except Exception as e:
                        status.update(label="处理失败", state="error", expanded=False)
                        st.error(f"处理失败: {str(e)}")
                        import traceback
                        with st.expander("错误详情"):
                            st.code(traceback.format_exc())
                        # 删除临时文件
                        try:
                            os.unlink(tmp_path)
                        except:
                            pass
            else:
                st.warning("请先上传PDF文件")

    with tab2:
        section_head("02", "文档管理", "DOCUMENTS")

        docs = kb.list_documents()

        if not docs:
            st.info("知识库为空，请先上传PDF文档")
        else:
            st.markdown(f"共 **{len(docs)}** 个文档\n")

            for i, doc in enumerate(docs):
                with st.container():
                    col1, col2, col3 = st.columns([3, 2, 1], vertical_alignment="center")
                    with col1:
                        title = doc.get('title') or doc.get('doc_id', '未知')
                        st.markdown(f"**{title}**")
                    with col2:
                        st.caption(f"科目: {doc.get('subject', '未分类')} | {doc.get('chunk_count', 0)} 个文本块")
                    with col3:
                        safe_title = html.escape(str(title))
                        with st.popover("删除", key=f"del_pop_{i}", use_container_width=True):
                            st.markdown(
                                '<div class="popover-title">删除文档</div>'
                                f'<div class="popover-body">《{safe_title}》及其全部文本块将被移除，操作不可恢复。</div>',
                                unsafe_allow_html=True,
                            )
                            dc1, dc2 = st.columns(2)
                            with dc1:
                                if st.button("取消", key=f"del_cancel_{i}", use_container_width=True):
                                    st.rerun()
                            with dc2:
                                if st.button("确认删除", key=f"del_confirm_{i}", type="primary", use_container_width=True):
                                    try:
                                        kb.delete_document(doc['doc_id'])
                                        st.success(f"已删除: {title}")
                                        time.sleep(0.5)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"删除失败: {str(e)}")

                    if i < len(docs) - 1:
                        st.markdown('<div class="doc-sep"></div>', unsafe_allow_html=True)

    with tab3:
        section_head("03", "向量搜索", "SEARCH")


        st.info("""
         **向量搜索说明：**

        向量搜索不是简单的关键词匹配，而是理解问题的**语义**。

        **例子：**
        - 问："Python中如何创建列表"
        - 能找到："Python的list类型用于存储序列数据..."
        - 即使原文没有"创建"这个词

        **使用方法：**
        1. 输入问题或关键词
        2. 选择返回多少个结果
        3. 查看相似度（越接近1越相关）
        """)

        st.markdown("---")

        search_query = st.text_input(
            "搜索问题",
            placeholder="输入问题，例如：Python中的列表是什么？",
            key="vector_search_query"
        )

        top_k = st.slider(
            "返回结果数",
            min_value=1,
            max_value=10,
            value=5,
            key="vector_top_k"
        )

        if st.button("向量搜索", use_container_width=True, key="vector_search_btn"):
            if search_query:
                with st.spinner("正在向量搜索..."):
                    try:
                        results = kb.search(search_query, top_k=top_k)

                        if results:
                            st.success(f"找到 {len(results)} 个相关结果")

                            for i, r in enumerate(results, 1):
                                with st.expander(
                                    f"结果 {i} · 相似度: {r['similarity']:.2%}",
                                    expanded=(i == 1)
                                ):
                                    st.markdown(f"**来源：** {r['metadata'].get('title', '未知')}")
                                    st.markdown(f"**科目：** {r['metadata'].get('subject', '未分类')}")
                                    st.markdown("---")
                                    content_text = r['content'][:500] + "..." if len(r['content']) > 500 else r['content']
                                    st.markdown(highlight_keywords(content_text, search_query), unsafe_allow_html=True)
                        else:
                            st.warning("未找到相关内容，建议：")
                            st.markdown("""
                            1. 尝试其他问题或关键词
                            2. 上传更多相关PDF文档
                            3. 检查文档是否包含相关内容
                            """)

                    except Exception as e:
                        st.error(f"搜索失败: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
            else:
                st.warning("请输入搜索问题")

    with tab4:
        section_head("04", "RAG 问答", "RAG")

        st.info("""
         **RAG = 检索增强生成**

        工作流程：
        1. 你提出问题
        2. 系统向量搜索知识库，找到最相关的几段内容
        3. 将找到的内容和问题一起发给AI
        4. AI基于这些内容回答问题

        **优势：**
        - 答案来自你上传的文档
        - 准确、可靠
        - 可以问文档相关的问题

        **示例：**
        - 上传了Python课本PDF
        - 问："请解释Python中的列表推导式"
        - AI会从课本中找到相关内容，然后详细解释
        """)

        st.markdown("---")

        # 显示已上传的文档
        docs = kb.list_documents()
        if docs:
            st.markdown("**知识库中的文档：**")
            doc_list = ", ".join([d['title'] or d['doc_id'] for d in docs[:5]])
            if len(docs) > 5:
                doc_list += f" 等{len(docs)}个文档"
            st.caption(doc_list)

        rag_query = st.text_input(
            "你的问题",
            placeholder="基于知识库提问，例如：请解释Python中的列表推导式...",
            key="rag_query"
        )

        col1, col2 = st.columns([3, 1])
        with col1:
            use_context = st.checkbox("显示检索到的相关内容", value=False, key="show_context")
        with col2:
            st.write("")  # 对齐

        if st.button("提问", type="primary", use_container_width=True, key="rag_ask_btn"):
            if rag_query:
                with st.spinner("AI正在思考..."):
                    try:
                        start_time = time.time()

                        # 1. 向量搜索
                        results = kb.search(rag_query, top_k=3)

                        search_time = time.time() - start_time

                        # 2. 构建上下文
                        if results:
                            context = "\n\n".join([
                                f"【资料{i+1}】(来源: {r['metadata'].get('title', '未知')})\n{r['content']}"
                                for i, r in enumerate(results)
                            ])
                        else:
                            context = "未找到相关资料。"

                        # 3. 调用AI回答
                        from backend.llm_helper import get_llm
                        from langchain_core.prompts import ChatPromptTemplate

                        llm = get_llm(temperature=0.7)

                        prompt = ChatPromptTemplate.from_messages([
                            ("system", """你是一位智能学习助手。

请根据以下资料回答用户的问题。
如果资料中有相关信息，请基于资料回答，并标注资料来源。
如果资料中没有相关信息，请说"抱歉，资料中没有找到相关内容"，然后基于你的知识回答。

【参考资料】
{context}

回答要求：
1. 清晰准确
2. 有条理
3. 回答中标注具体资料名称，如"根据《资料标题》..."
4. 回答末尾列出引用的资料来源，格式：参考资料：《标题1》《标题2》
5. 保持教育性，有助学习"""),
                            ("human", "{query}")
                        ])

                        chain = prompt | llm
                        response = chain.invoke({"query": rag_query, "context": context})
                        answer = text_content(response.content)

                        # 保存结果到session_state
                        st.session_state.rag_history = {
                            "query": rag_query,
                            "answer": answer,
                            "results": results,
                            "search_time": search_time,
                            "show_context": use_context
                        }

                    except Exception as e:
                        st.error(f"回答失败: {str(e)}")
                        import traceback
                        st.error(traceback.format_exc())
            else:
                st.warning("请输入问题")

        # 显示历史RAG结果（持久化，不会因为页面切换丢失）
        if 'rag_history' in st.session_state and st.session_state.rag_history:
            hist = st.session_state.rag_history
            st.markdown("---")
            st.markdown(f"**问题:** {hist['query']}")
            st.caption(f"搜索耗时: {hist['search_time']:.2f}秒 | 检索到 {len(hist['results'])} 个相关片段")

            if hist.get('show_context') and hist['results']:
                with st.expander("检索到的相关内容"):
                    for i, r in enumerate(hist['results'], 1):
                        st.markdown(f"**来源{i}**（相似度: {r['similarity']:.2%}） - {r['metadata'].get('title', '未知')}")
                        rag_content = r['content'][:300] + "..." if len(r['content']) > 300 else r['content']
                        st.markdown(highlight_keywords(rag_content, hist['query']), unsafe_allow_html=True)

            with st.container(key="rag_answer"):
                st.markdown(prepare_markdown(hist["answer"]))

        if not docs:
            st.warning("提示：知识库为空，请先上传PDF文档")


def _load_code_attempt(code: str, tests: str) -> None:
    st.session_state["code_tutor_source"] = code
    st.session_state["code_tutor_tests"] = tests


def _start_new_code_thread() -> None:
    from backend.platform.code_attempt_store import new_thread_id

    st.session_state["code_tutor_thread"] = new_thread_id()
    st.session_state["code_tutor_source"] = ""
    st.session_state["code_tutor_tests"] = ""
    st.session_state.pop("code_tutor_result", None)


def _ensure_code_thread(user_id: str) -> str:
    from backend.platform.code_attempt_store import latest_thread, list_attempts, new_thread_id

    if st.session_state.get("code_tutor_thread"):
        return st.session_state["code_tutor_thread"]
    thread_id = latest_thread(user_id)
    if thread_id:
        attempts = list_attempts(user_id, thread_id)
        st.session_state["code_tutor_thread"] = thread_id
        if attempts and "code_tutor_source" not in st.session_state:
            last = attempts[-1]
            st.session_state["code_tutor_source"] = last["code"]
            st.session_state["code_tutor_tests"] = last["tests"] or ""
        return thread_id
    thread_id = new_thread_id()
    st.session_state["code_tutor_thread"] = thread_id
    return thread_id


def render_code_tutor():
    """代码助教：本机沙箱跑代码和测试，失败时只给分级提示。"""
    from backend.platform.code_attempt_store import append_attempt, list_attempts
    from backend.tools.code_sandbox import (
        MAX_MEMORY_BYTES,
        format_run_result,
        hint_for_level,
        record_code_run,
        run_student_code,
    )

    user_id = st.session_state.get("auth_user") or "student"
    thread_id = _ensure_code_thread(user_id)

    page_header("code", chips=[
        "<b>隔离</b> 独立进程",
        "<b>记录</b> 改完可再跑",
    ])
    st.caption(
        "在本机沙箱里运行 Python。禁止读写文件、启动子进程和联网。"
        f"单次运行的内存上限是 {MAX_MEMORY_BYTES // (1024 * 1024)}MB，超过后只返回失败。"
        "失败时只解释错误并按级别给提示，不直接给出改正后的完整代码。"
        "同一次练习的每次运行都会留下，可以载入某一版再改。这是进程隔离，不是容器。"
    )

    section_head("01", "代码与测试", "RUN")
    code = st.text_area(
        "学生代码",
        height=220,
        key="code_tutor_source",
        placeholder="def add(a, b):\n    return a + b",
    )
    tests = st.text_area(
        "测试用例（可留空）",
        height=120,
        key="code_tutor_tests",
        placeholder="assert add(1, 2) == 3",
    )
    timeout = st.slider(
        "超时（秒）",
        min_value=1,
        max_value=5,
        value=2,
        key="code_tutor_timeout",
    )
    run_col, new_col = st.columns(2)
    with run_col:
        run_clicked = st.button("运行", type="primary", key="code_tutor_run")
    with new_col:
        st.button("新开一题", key="code_tutor_new", on_click=_start_new_code_thread)
    if run_clicked:
        result = run_student_code(code, tests=tests, timeout_s=float(timeout))
        st.session_state["code_tutor_result"] = result
        append_attempt(user_id, thread_id, code, tests, result)
        record_code_run(user_id, code, tests, result)

    result = st.session_state.get("code_tutor_result")
    attempts = list_attempts(user_id, thread_id)
    if not result and not attempts:
        empty_state(
            "SANDBOX",
            "还没有运行记录",
            "贴上代码，可选地写几条 assert，然后运行。失败时只会给出分级提示。同一次练习可以改完再跑。",
        )
        return

    if result:
        status = result.get("status") or "error"
        labels = {
            "passed": "通过",
            "failed": "未通过",
            "rejected": "被沙箱拒绝",
            "timeout": "超时",
            "memory": "超过内存上限",
            "error": "运行器错误",
        }
        section_head("02", "运行结果", "RESULT")
        st.markdown(f"**{labels.get(status, status)}**")
        if result.get("exception_type"):
            st.text(f"{result['exception_type']}: {result.get('exception_message') or ''}")
            if result.get("line"):
                st.caption(f"行号 {result['line']}")
        st.markdown("标准输出")
        st.code(result.get("stdout") or "（空）", language="text")
        if result.get("stderr"):
            st.markdown("标准错误")
            st.code(result.get("stderr"), language="text")

        if status != "passed":
            section_head("03", "分级提示", "HINT")
            observation = format_run_result(result)
            level = st.radio(
                "提示级别",
                options=[1, 2, 3],
                horizontal=True,
                key="code_tutor_level",
                format_func=lambda n: {1: "1 只说类别", 2: "2 指出行号", 3: "3 检查方向"}[n],
            )
            st.text(hint_for_level(level, observation))

    _render_code_history(attempts)


_ATTEMPT_LABELS = {
    "passed": "通过",
    "failed": "未通过",
    "rejected": "被拒绝",
    "timeout": "超时",
    "memory": "超过内存上限",
    "error": "错误",
}


def _render_code_history(attempts) -> None:
    section_head("04", "这次练习的修改", "HISTORY")
    if not attempts:
        st.caption("运行之后，每一版代码会出现在这里。")
        return
    for item in reversed(attempts):
        label = _ATTEMPT_LABELS.get(item["status"], item["status"])
        detail = item.get("exception_type") or ""
        with st.container(border=True):
            st.markdown(f"**第 {item['seq']} 次 · {label}**")
            if detail:
                st.caption(detail)
            st.button(
                "载入再改",
                key=f"code_load_{item['id']}",
                on_click=_load_code_attempt,
                args=(item["code"], item.get("tests") or ""),
            )


def render_mistakes():
    """错题本：确认后按 SM-2 进入复习，到期卡片由独立脚本发送。"""
    from datetime import timezone

    from backend.platform.mistake_store import (
        confirm_mistake,
        dismiss_mistake,
        list_mistakes,
    )
    from backend.platform.review_planner import (
        get_learning_state,
        list_outbox,
        record_review,
        reschedule,
        run_review_push,
    )

    page_header("mistakes", chips=[
        "<b>写入</b> 默认待确认",
        "<b>间隔</b> SM-2",
        "<b>推送</b> 独立脚本",
    ])
    user_id = st.session_state.get("auth_user") or "student"
    pending = list_mistakes(user_id, status="pending")
    confirmed = list_mistakes(user_id, status="confirmed")

    section_head("01", "待确认", "PENDING")
    if not pending:
        empty_state(
            "EMPTY",
            "没有待确认错题",
            "在问答里明确说「记入错题本」后，记录会出现在这里。确认前不会进入复习。",
        )
    for item in pending:
        with st.container(border=True):
            st.markdown(
                f"**{html.escape(item['concept'])}** · {html.escape(item['subject'])} · "
                f"{html.escape(item['error_type'])}"
            )
            st.write(item["question_text"])
            if item.get("student_answer"):
                st.caption(f"你的答案：{item['student_answer']}")
            if item.get("correct_answer"):
                st.caption(f"正确答案：{item['correct_answer']}")
            yes_col, no_col = st.columns(2)
            with yes_col:
                if st.button("确认并加入复习", key=f"confirm_{item['id']}", type="primary"):
                    confirm_mistake(item["id"])
                    st.rerun()
            with no_col:
                if st.button("丢弃", key=f"dismiss_{item['id']}"):
                    dismiss_mistake(item["id"])
                    st.rerun()

    section_head("02", "复习队列", "REVIEW")
    if not confirmed:
        empty_state("QUEUE", "复习队列为空", "确认后的错题会在次日进入复习时间。")
    else:
        for item in confirmed:
            interval = item.get("interval_days") or 0
            st.markdown(
                f"- **{html.escape(item['concept'])}**（{html.escape(item['error_type'])}）"
                f" · 下次复习 {html.escape(item.get('next_review_at') or '—')}"
                f" · 间隔 {interval} 天"
            )

    section_head("03", "到期复习", "DUE")
    now = datetime.now(timezone.utc)
    due = get_learning_state(user_id, now=now)["due"]
    if not due:
        empty_state(
            "DUE",
            "今天没有到期错题",
            "到了下次复习时间后会出现在这里。每日任务请运行 "
            "python -m backend.workers.review_push，不要把它放进页面自动循环。",
        )
    else:
        if st.button("保存今天的晨间卡片", key="save_review_card", type="primary"):
            run_review_push(user_id, now=now)
            st.rerun()
        for item in due:
            with st.container(border=True):
                st.markdown(
                    f"**{html.escape(item['concept'])}** · {html.escape(item['subject'] or '')}"
                )
                st.write(item["question_text"])
                remembered, forgotten, later = st.columns(3)
                with remembered:
                    if st.button("记住了", key=f"recall_ok_{item['id']}"):
                        record_review(item["id"], quality=5, reviewed_at=now)
                        st.rerun()
                with forgotten:
                    if st.button("没记住", key=f"recall_fail_{item['id']}"):
                        record_review(item["id"], quality=2, reviewed_at=now)
                        st.rerun()
                with later:
                    if st.button("推到晚上", key=f"evening_{item['id']}"):
                        reschedule(item["id"], "推到晚上", now=now)
                        st.rerun()

    cards = list_outbox(user_id)
    section_head("04", "发件箱", "OUTBOX")
    if not cards:
        empty_state(
            "OUTBOX",
            "还没有晨间卡片",
            "有到期错题时，点「保存今天的晨间卡片」，或运行独立脚本。未配置飞书 webhook 时只保存在本地。",
        )
    else:
        latest = cards[-1]
        st.text(latest["body"])
        st.caption(
            f"{latest['channel']} · {latest['status']} · {latest['created_at']}"
        )


def render_react_visualization():
    """思维链可视化页面 - 以时间线展示 ReAct 推理过程"""
    page_header("react_viz", chips=[
        "<b>来源</b> ReAct 流式事件",
        "<b>结构</b> 可追溯时间线",
    ])

    result = st.session_state.get('last_react_result')

    if not result:
        empty_state(
            "NO TRACE",
            "还没有推理记录",
            "先在「在线问答」提出一个需要检索或调用工具的问题，这里会自动生成完整推理时间线。",
        )
        return

    section_head("01", "用户问题", "QUESTION")
    with st.container(key="result_panel"):
        st.markdown(
            f'<div style="font-size:1rem;line-height:1.75;letter-spacing:-.01em;">'
            f'{html.escape(result["user_input"])}</div>',
            unsafe_allow_html=True,
        )

    steps = result.get("steps", [])
    tools = result.get("tools_used", [])

    if steps:
        section_head("02", "推理步骤", "TRACE")
        items = []
        for step in steps:
            step_num = step.get("step", 0)
            step_type = step.get("type", "")
            tool_name = html.escape(str(step.get("tool", "")))
            is_call = step_type == "tool_call"
            kind_label = "Tool Call" if is_call else "Tool Result"
            kind_cls = "is-call" if is_call else "is-result"

            if is_call:
                title = "调用工具并传入参数"
                args_html = ""
                args = step.get("args") or {}
                if args:
                    args_html = '<div class="tl-args">' + "".join(
                        f'<span class="tl-arg"><b>{html.escape(str(k))}</b>'
                        f'{html.escape(str(v))[:120]}</span>'
                        for k, v in args.items()
                    ) + "</div>"
            else:
                title = html.escape(str(step.get("detail", "")))
                args_html = ""

            items.append(
                '<div class="tl-item">'
                f'<div class="tl-top"><span class="tl-kind {kind_cls}">{kind_label}</span>'
                f'<span class="tl-tool">{step_num:02d} · {tool_name}</span></div>'
                f'<div class="tl-title">{title}</div>{args_html}</div>'
            )

        st.markdown(f'<div class="timeline">{"".join(items)}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="note-line"><span class="dot"></span>'
            "本次回答没有调用工具，模型直接给出了结论。</div>",
            unsafe_allow_html=True,
        )

    section_head("03", "最终回答", "ANSWER")
    with st.container(key="result_panel"):
        st.markdown(prepare_markdown(result["final_answer"]))

    section_head("04", "运行统计", "METRICS")
    metrics = [
        ("推理步骤", "Steps", result.get("total_iterations", len(steps))),
        ("使用工具", "Tools", len(tools)),
        ("工具种类", "Unique", len(set(tools)) if tools else 0),
    ]
    st.markdown(
        '<div class="stat-strip is-three">' + "".join(
            f'<div class="stat"><div class="stat-k"><i></i>{label}</div>'
            f'<div class="stat-v">{value}<small>项</small></div>'
            f'<div class="stat-note">{en}</div></div>'
            for label, en, value in metrics
        ) + "</div>",
        unsafe_allow_html=True,
    )


def render_eval_board():
    """展示最近一次评测里按缺失工具归类的失败。不重新跑评测。"""
    from backend.platform.eval_runner import load_failure_board

    page_header("eval", chips=[
        "<b>来源</b> eval_runs",
        "<b>归因</b> 缺失工具",
        "<b>门禁</b> 只读展示",
    ])
    board = load_failure_board()
    latest = board["latest"]
    if latest is None:
        empty_state(
            "NO EVAL",
            "还没有评测记录",
            "运行 python -m backend.platform.eval_runner --dry-run 之后，"
            "这里会列出最近一次没通过的样本，并按缺失工具计数。",
        )
        return

    faith = latest["faithfulness"]
    faith_text = "不适用" if faith is None else f"{faith:.2%}"
    gate = latest["gate"]
    gate_text = "通过" if gate["passed"] else "未通过"
    dataset = html.escape(f"{latest['dataset_name']}@{latest['dataset_version']}")
    stats = [
        ("通过题数", "Passed", f"{latest['passed_count']}/{latest['sample_count']}"),
        ("工具选择", "Accuracy", f"{latest['accuracy']:.2%}"),
        ("忠实度", "Faithfulness", faith_text),
        ("门禁", "Gate", gate_text),
    ]
    st.markdown(
        '<div class="stat-strip">' + "".join(
            f'<div class="stat"><div class="stat-k"><i></i>{label}</div>'
            f'<div class="stat-v">{html.escape(value)}</div>'
            f'<div class="stat-note">{en}</div></div>'
            for label, en, value in stats
        ) + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="note-line"><span class="dot"></span>'
        f'{dataset} · {html.escape(str(latest["mode"]))} · '
        f'{html.escape(str(latest["started_at"]))}</div>',
        unsafe_allow_html=True,
    )
    if gate["reasons"]:
        reasons = "；".join(html.escape(str(reason)) for reason in gate["reasons"])
        st.markdown(
            f'<div class="note-line"><span class="dot is-off"></span>{reasons}</div>',
            unsafe_allow_html=True,
        )

    section_head("01", "失败归因", "FAILURES")
    attribution = latest["failure_attribution"]
    labels = {
        "empty_retrieval": "检索为空",
        "unfaithful": "答案不忠实",
        "other": "其他",
    }
    if attribution:
        top = max(item["count"] for item in attribution) or 1
        rows = "".join(
            f'<div class="dist-row"><div class="dist-label">{html.escape(labels.get(item["tool"], item["tool"]))}</div>'
            f'<div class="dist-track"><div class="dist-fill" style="width:{int(round(item["count"] * 100 / top))}%"></div></div>'
            f'<div class="dist-val">{int(item["count"])}</div></div>'
            for item in attribution
        )
        st.markdown(f'<div class="dist">{rows}</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="note-line"><span class="dot is-muted"></span>'
            '工具没选对时按缺失工具计数。检索被调用但没有正文，记为检索为空；'
            '忠实度低于 0.85 记为答案不忠实。超时和成本还不在这张表里。</div>',
            unsafe_allow_html=True,
        )
    else:
        empty_state(
            "CLEAR",
            "这次没有失败样本",
            "缺失工具计数为空。上面的通过题数和门禁仍是这一次运行的结果。",
        )

    section_head("02", "失败样本", "FAILED SAMPLES")
    failed = latest["failed_samples"]
    if failed:
        body = "".join(
            f'<div class="sum-row"><span class="k">{html.escape(item["sample_id"])}</span>'
            f'<span class="v">{html.escape("、".join(item["missing"]) or "other")}</span></div>'
            for item in failed
        )
        st.markdown(f'<div class="sum-list">{body}</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div class="note-line"><span class="dot"></span>没有失败样本。</div>',
            unsafe_allow_html=True,
        )

    earlier = board["earlier"]
    if earlier:
        section_head("03", "更早的运行", "EARLIER RUNS")
        body = "".join(
            f'<div class="sum-row"><span class="k">'
            f'{html.escape(item["dataset_version"])} · {html.escape(str(item["mode"]))}'
            f'</span><span class="v">{item["accuracy"]:.2%}</span></div>'
            for item in earlier
        )
        st.markdown(f'<div class="sum-list">{body}</div>', unsafe_allow_html=True)


def render_mobile_nav():
    """移动端页面导航（桌面端隐藏，侧栏不可用时仍可切换页面）"""
    labels = [p[3] for p in PAGES]
    keys = [p[0] for p in PAGES]
    current = st.session_state.get("current_page", "dashboard")
    current_label = PAGE_META[current][2]

    # 外部入口切页时同步移动端导航；用户点击导航时不要覆盖其选择
    if st.session_state.get("mobile_nav_page") != current:
        st.session_state["mobile_nav_page"] = current
        st.session_state["mobile_nav_pills"] = current_label

    with st.container(key="mobile_nav"):
        choice = st.pills(
            "页面导航",
            labels,
            label_visibility="collapsed",
            key="mobile_nav_pills",
        )

    if choice and choice != current_label:
        st.session_state.current_page = keys[labels.index(choice)]
        st.rerun()


def main():
    # 退出登录链接：?logout=1
    if st.query_params.get("logout") == "1":
        logout()

    if not st.session_state.get("authenticated", False):
        render_login()
        return

    init_session_state()

    # 渲染侧边栏
    render_sidebar()

    page = st.session_state.get('current_page', 'dashboard')

    top_bar(page)
    render_mobile_nav()

    # 页面内容包在带 key 的容器里：切页时重新挂载触发 240ms 入场过渡，
    # 同页交互（输入、展开、提交）复用同一容器，不会反复播放动画。
    with st.container(key=f"page_{page}"):
        if page == 'dashboard':
            render_dashboard()
        elif page == 'qa':
            render_qa()
        elif page == 'knowledge':
            render_knowledge()
        elif page == 'compare':
            render_compare()
        elif page == 'planner':
            render_planner()
        elif page == 'daily':
            render_daily()
        elif page == 'quiz':
            render_quiz()
        elif page == 'kb':
            render_kb()
        elif page == 'mistakes':
            render_mistakes()
        elif page == 'code':
            render_code_tutor()
        elif page == 'react_viz':
            render_react_visualization()
        elif page == 'eval':
            render_eval_board()


if __name__ == "__main__":
    main()
