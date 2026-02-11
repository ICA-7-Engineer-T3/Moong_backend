# 뭉 프로젝트 페르소나 시스템 초기화 파일

from .state_manager import PersonaUpdateState, session_manager, MATE_MOONG_BASE
from .graph_nodes import NODE_FUNCTIONS
from .workflow import persona_graph

__version__ = "1.0.0-week1"
__description__ = "뭉 프로젝트 초개인화 페르소나 업데이트 시스템"

# 시스템 상태 확인
def check_system_health():
    """시스템 상태 확인"""
    return {
        "persona_system": True,
        "langgraph_ready": persona_graph.graph is not None,
        "session_manager": session_manager is not None,
        "total_nodes": len(NODE_FUNCTIONS),
        "base_persona": bool(MATE_MOONG_BASE)
    }