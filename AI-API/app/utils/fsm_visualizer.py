# app/utils/fsm_visualizer.py
import os
from typing import Dict, List, Any
from graphviz import Digraph
import logging

from app.models.fsm import fsm, State

logger = logging.getLogger(__name__)

def visualize_fsm(output_path: str = "fsm_diagram"):
    """FSM 상태 전이 다이어그램 생성"""
    try:
        # 그래프 초기화
        dot = Digraph(comment='대화 흐름 FSM')
        
        # 노드 추가 (상태)
        for state in State:
            dot.node(state.value, state.value)
        
        # 엣지 추가 (전이)
        for current_state, transitions in fsm.state_transitions.items():
            for intent, next_state in transitions.items():
                dot.edge(current_state.value, next_state.value, label=intent)
        
        # 저장
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            
        dot.render(output_path, format='png', cleanup=True)
        
        logger.info(f"FSM 다이어그램 생성 완료: {output_path}")
        return True
    except Exception as e:
        logger.error(f"FSM 다이어그램 생성 실패: {str(e)}")
        return False