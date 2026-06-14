#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基于大模型的足球比赛智能分析预测模块
集成多种AI模型进行比赛预测
"""

import json
import logging
import time
import random
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import requests

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SimpleMatchAnalysis:
    """简化的比赛分析结果"""
    match_id: str
    home_team: str
    away_team: str
    league_name: str
    ai_analysis: str  # 直接的AI文本分析
    home_odds: float
    draw_odds: float
    away_odds: float

class AIFootballPredictor:
    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash-exp", provider: str = "gemini", base_url: str = ""):
        self.api_key = api_key
        self.model_name = model_name
        self.provider = provider if provider in ("openai_compatible", "gemini") else "openai_compatible"
        if base_url:
            self.base_url = base_url.rstrip('/')
        elif self.provider == "openai_compatible":
            self.base_url = "https://api.openai.com/v1"
        else:
            self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def analyze_matches(self, matches: List[Dict[str, Any]]) -> List[SimpleMatchAnalysis]:
        """分析比赛列表，为每场比赛生成独立的AI分析"""
        analyses = []
        for match in matches:
            try:
                analysis = self._analyze_single_match(match)
                if analysis:
                    analyses.append(analysis)
            except Exception as e:
                logger.error(f"分析比赛失败 {match.get('home_team', '')} vs {match.get('away_team', '')}: {e}")
                analyses.append(self._create_error_analysis(match, str(e)))
        return analyses

    def _analyze_single_match(self, match: Dict[str, Any]) -> Optional[SimpleMatchAnalysis]:
        """分析单场比赛"""
        home_team = match.get('home_team', '')
        away_team = match.get('away_team', '')
        league_name = match.get('league_name', '未知联赛')
        odds = match.get('odds', {})
        hhad_odds = odds.get('hhad', {})
        home_odds = float(hhad_odds.get('h', match.get('home_odds', 2.0)))
        draw_odds = float(hhad_odds.get('d', match.get('draw_odds', 3.2)))
        away_odds = float(hhad_odds.get('a', match.get('away_odds', 2.8)))
        prompt = f"""请详细分析这场足球比赛并给出完整预测：

比赛：{home_team} vs {away_team}
联赛：{league_name}
赔率：主胜 {home_odds} | 平局 {draw_odds} | 客胜 {away_odds}

请按以下格式提供详细预测：

**一、比赛分析**
（考虑两队实力、近期状态、历史对战、主客场优势等因素）

**二、胜平负预测**
推荐结果：[主胜/平局/客胜]
推荐理由：
信心指数：[1-10]

**三、比分预测**
最可能比分：
其他可能比分：

**四、半场胜平负预测**
半场结果：[主胜/平局/客胜]
全场结果：[主胜/平局/客胜]
半全场组合：

**五、进球数预测**
总进球数：[0-1球/2-3球/4球以上]
主队进球：
客队进球：

**六、其他分析**
- 大小球分析
- 亚盘分析
- 风险提示

请用中文回答，保持专业分析水准。"""
        ai_response = self._call_ai_model(prompt)
        if ai_response:
            return SimpleMatchAnalysis(
                match_id=match.get('match_id', f"match_{int(time.time())}"),
                home_team=home_team,
                away_team=away_team,
                league_name=league_name,
                ai_analysis=ai_response,
                home_odds=home_odds,
                draw_odds=draw_odds,
                away_odds=away_odds
            )
        return None

    def _create_error_analysis(self, match: Dict[str, Any], error_msg: str) -> SimpleMatchAnalysis:
        """创建错误情况下的分析"""
        return SimpleMatchAnalysis(
            match_id=match.get('match_id', f"error_{int(time.time())}"),
            home_team=match.get('home_team', '未知'),
            away_team=match.get('away_team', '未知'),
            league_name=match.get('league_name', '未知联赛'),
            ai_analysis=f"AI分析暂时无法获取，请稍后重试。\n\n错误信息：{error_msg}",
            home_odds=2.0,
            draw_odds=3.2,
            away_odds=2.8
        )

    def test_connection(self):
        """用极简请求测试 AI 配置。"""
        if not self.api_key:
            return False, "请先填写 AI Key"
        if not self.model_name:
            return False, "请先填写模型名称"
        try:
            text = self._call_ai_model("请只回复：连接成功", max_tokens=20, max_retries=1)
            if text:
                return True, "AI 连接成功"
            return False, "AI 有响应但没有返回有效内容"
        except Exception as e:
            return False, f"AI 连接失败：{e}"

    def _call_ai_model(self, prompt: str, max_tokens: int = 2000, max_retries: int = 3) -> Optional[str]:
        """按当前 provider 调用 AI 模型。"""
        if self.provider == "openai_compatible":
            return self._call_openai_compatible(prompt, max_tokens=max_tokens, max_retries=max_retries)
        return self._call_gemini(prompt, max_tokens=max_tokens, max_retries=max_retries)

    def _call_openai_compatible(self, prompt: str, max_tokens: int, max_retries: int) -> Optional[str]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "你是一名专业足球比赛分析助手，请用中文回答。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens
        }
        return self._post_with_retries(url, headers, payload, self._extract_openai_content, max_retries)

    def _call_gemini(self, prompt: str, max_tokens: int, max_retries: int) -> Optional[str]:
        base_url = self.base_url.rstrip('/')
        if base_url.endswith('/models'):
            url = f"{base_url}/{self.model_name}:generateContent"
        else:
            url = f"{base_url}/models/{self.model_name}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topK": 40,
                "topP": 0.95,
                "maxOutputTokens": max_tokens
            }
        }
        return self._post_with_retries(url, headers, payload, self._extract_gemini_content, max_retries)

    def _post_with_retries(self, url, headers, payload, extractor, max_retries):
        base_delay = 1
        for attempt in range(max_retries):
            try:
                logger.info(f"调用 AI API ({self.provider}, 尝试 {attempt + 1}/{max_retries})")
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                logger.info(f"AI API 响应状态码: {response.status_code}")
                if response.status_code == 200:
                    return extractor(response.json())
                if response.status_code == 429 and attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"AI API 速率限制，等待 {delay:.2f} 秒后重试")
                    time.sleep(delay)
                    continue
                if attempt == max_retries - 1:
                    raise RuntimeError(f"API请求失败: {response.status_code} - {response.text[:500]}")
            except requests.exceptions.Timeout:
                if attempt == max_retries - 1:
                    raise RuntimeError("AI 请求超时")
                time.sleep(base_delay * (attempt + 1))
            except Exception:
                if attempt == max_retries - 1:
                    raise
                time.sleep(base_delay * (attempt + 1))
        return None

    def _extract_openai_content(self, data):
        choices = data.get('choices') or []
        if not choices:
            return None
        message = choices[0].get('message') or {}
        content = message.get('content')
        return content.strip() if isinstance(content, str) else None

    def _extract_gemini_content(self, data):
        candidates = data.get('candidates') or []
        if not candidates:
            return None
        content = candidates[0].get('content') or {}
        parts = content.get('parts') or []
        if not parts:
            return None
        text = parts[0].get('text')
        return text.strip() if isinstance(text, str) else None

# 使用示例
if __name__ == "__main__":
    # 初始化预测器
    import os
    api_key = os.environ.get('AI_API_KEY') or os.environ.get('GEMINI_API_KEY')
    if not api_key:
        print("请设置 AI_API_KEY 或 GEMINI_API_KEY 环境变量")
        exit(1)
    predictor = AIFootballPredictor(api_key, os.environ.get('AI_MODEL', 'gemini-2.5-flash-lite-preview-06-17'), os.environ.get('AI_PROVIDER', 'gemini'), os.environ.get('AI_BASE_URL', ''))

    # 示例比赛数据
    sample_match = {
        'match_id': '12345',
        'home_team': '曼城',
        'away_team': '利物浦',
        'league_name': '英超',
        'odds': {
            'hhad': {'h': '2.10', 'd': '3.50', 'a': '2.80'}
        }
    }

    # 分析比赛
    analysis = predictor.analyze_matches([sample_match])

    for analysis in analysis:
        print(f"比赛: {analysis.home_team} vs {analysis.away_team}")
        print(f"AI分析: {analysis.ai_analysis}")
        print(f"赔率: 主胜 {analysis.home_odds}, 平局 {analysis.draw_odds}, 客胜 {analysis.away_odds}")
