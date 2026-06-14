from __future__ import annotations

from typing import Any, Dict


class WorldCupExplainer:
    def __init__(self, ai_predictor=None):
        self.ai_predictor = ai_predictor

    def explain(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        base = self._fallback_explanation(prediction)
        if not self.ai_predictor:
            return {
                'success': True,
                'ai_available': False,
                'fallback_used': True,
                'explanation': base,
                'risk_notes': ['未配置 AI，已使用本地白话解释。'],
            }

        prompt = (
            '请用中文解释下面这份世界杯单场预测结果。要求：只解释已有概率、预期进球和比分分布；'
            '不要改写概率；不要编造伤停、阵容、新闻；明确说明概率不代表赛果保证，且非投注建议。\n'
            f'{prediction}'
        )
        try:
            text = self.ai_predictor._call_ai_model(prompt)
            if not text:
                raise ValueError('empty response')
            return {
                'success': True,
                'ai_available': True,
                'fallback_used': False,
                'explanation': text,
                'risk_notes': ['AI 只解释已有概率，不参与概率计算。'],
            }
        except Exception:
            return {
                'success': True,
                'ai_available': False,
                'fallback_used': True,
                'explanation': base,
                'risk_notes': ['AI 调用失败，基础预测不受影响。'],
            }

    def _fallback_explanation(self, prediction: Dict[str, Any]) -> str:
        probs = prediction.get('probabilities', {}) or {}
        top = prediction.get('top_scores', []) or []
        top_text = ''
        if top:
            item = top[0]
            top_text = f"模型认为最可能比分之一是 {item.get('home_goals')}-{item.get('away_goals')}。"
        return (
            f"本场模型概率为：胜 {probs.get('home_win', 0):.1%}，"
            f"平 {probs.get('draw', 0):.1%}，负 {probs.get('away_win', 0):.1%}。"
            f" {top_text}"
            " 这些数字只是基于当前本地数据的概率参考，不代表赛果保证，也不是投注建议。"
        )
