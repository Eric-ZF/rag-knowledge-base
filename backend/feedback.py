"""
RAG Self-Improving Feedback System

差评答案持久化 + 相似问题匹配 + 检索策略自适应

存储结构 (feedback_db.json):
{
  "entries": [
    {
      "id": "uuid",
      "question": "...",
      "answer": "...",
      "scores": {"total": 45.0, "coverage": 40, ...},
      "failure_reasons": ["low_coverage", "weak_citation", "hallucination"],
      "chunks_count": N,
      "retrieval_strategy_used": "default|expanded|evidence_focused",
      "improved_answer": "...",
      "improved_scores": {...},
      "timestamp": "ISO8601"
    }
  ],
  "question_index": {
    "keywords_hash": ["keyword1", "keyword2"]  # 用于相似匹配
  }
}
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

# ─── 配置 ──────────────────────────────────────────────
FEEDBACK_DB_PATH = os.environ.get("FEEDBACK_DB_PATH", "/root/.openclaw/rag-data/feedback_db.json")
SCORE_THRESHOLD = 50.0  # 低于此分触发记录 & 策略调整
SIMILARITY_THRESHOLD = 0.4  # 关键词重叠率 ≥ 40% 视为"相似问题"

# ─── 存储 ──────────────────────────────────────────────
class FeedbackStore:
    def __init__(self, db_path: str = FEEDBACK_DB_PATH):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        if not os.path.exists(self.db_path):
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            self._save({"entries": []})

    def _load(self) -> dict:
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"entries": []}

    def _save(self, data: dict):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        tmp = self.db_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.db_path)

    # ─── 关键词提取 ────────────────────────────────────
    @staticmethod
    def _extract_keywords(text: str) -> list[str]:
        import re
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", text)
        english = re.findall(r"[a-zA-Z]{3,}", text)
        # 去重并过滤停用词
        stopwords = {"的", "了", "和", "是", "在", "有", "与", "对", "为", "以及", "等", "该", "其", "可以", "或者"}
        combined = set(chinese + english)
        return sorted(combined - stopwords)

    @staticmethod
    def _keyword_overlap(kw1: list[str], kw2: list[str]) -> float:
        if not kw1 or not kw2:
            return 0.0
        set1, set2 = set(kw1), set(kw2)
        return len(set1 & set2) / min(len(set1), len(set2))

    # ─── 诊断失败原因 ─────────────────────────────────
    @staticmethod
    def _diagnose_failure(scores: dict) -> list[str]:
        """
        细粒度失败原因诊断（可同时触发多个）：
        - relevance is None: 评分解析失败，无法判断检索质量
        - relevance < 40: 检索召回的内容和问题的领域不匹配
        - relevance < 60: 检索召回的内容部分相关但不够精准
        - coverage < 50: 答案遗漏了参考片段中的重要信息
        - citation_quality < 50: 引用格式错误/引用位置不对/引用内容不匹配
        - factual_grounding < 50: 答案包含参考片段中没有的信息（幻觉）
        - completeness < 50: 答案在中途停止，或回避了问题的某些部分
        """
        reasons = []
        rel = scores.get("relevance")
        if rel is None:
            reasons.append("evaluation_parse_failed")   # 评分解析失败，无法判断
        elif rel < 40:
            reasons.append("irrelevant_retrieval")   # 检索跑题，需要换 query 或扩召回
        elif rel < 60:
            reasons.append("weak_relevance")          # 检索部分相关，可调整关键词
        if (scores.get("coverage") or 0) < 50:
            reasons.append("low_coverage")
        if (scores.get("citation_quality") or 0) < 50:
            reasons.append("weak_citation")
        if (scores.get("factual_grounding") or 0) < 50:
            reasons.append("hallucination_risk")
        if (scores.get("completeness") or 0) < 50:
            reasons.append("incomplete")
        if not reasons:
            reasons.append("below_threshold")
        return reasons

    # ─── 添加差评记录 ─────────────────────────────────
    def add_failed(
        self,
        question: str,
        answer: str,
        scores: dict,
        chunks_count: int,
        retrieval_strategy: str = "default",
        improved_answer: str = None,
        improved_scores: dict = None,
    ) -> str:
        """
        记录一个差评答案。返回 entry id。
        """
        entry = {
            "id": str(uuid.uuid4()),
            "question": question,
            "answer": answer,
            "scores": scores,
            "raw_evaluation": scores.get("raw_evaluation", ""),
            "json_mode": scores.get("json_mode", None),
            "failure_reasons": self._diagnose_failure(scores),
            "chunks_count": chunks_count,
            "retrieval_strategy_used": retrieval_strategy,
            "improved_answer": improved_answer,
            "improved_scores": improved_scores,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        db = self._load()
        db["entries"].append(entry)
        self._save(db)
        logger.info(f"[feedback] 差评记录 +1 (id={entry['id'][:8]}) reasons={entry['failure_reasons']}")
        return entry["id"]

    # ─── 相似问题查询 ─────────────────────────────────
    def find_similar(self, question: str) -> list[dict]:
        """
        查找相似的历史问题，返回按相似度排序的差评记录。
        用于在生成答案前预判可能的失败模式。
        """
        kw = self._extract_keywords(question)
        db = self._load()
        results = []

        for entry in db["entries"]:
            if entry.get("improved_answer") and entry.get("improved_scores"):
                # 有成功改进记录的优先
                entry_kw = self._extract_keywords(entry["question"])
                sim = self._keyword_overlap(kw, entry_kw)
                if sim >= SIMILARITY_THRESHOLD:
                    results.append({
                        "id": entry["id"],
                        "question": entry["question"],
                        "similarity": round(sim, 3),
                        "failure_reasons": entry["failure_reasons"],
                        "retrieval_strategy_used": entry["retrieval_strategy_used"],
                        "improved_answer": entry.get("improved_answer"),
                        "improved_scores": entry.get("improved_scores"),
                    })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:3]  # 最多返回3条最相似的

    # ─── 获取检索策略建议 ─────────────────────────────
    def get_strategy_hint(self, question: str) -> tuple[str, list[str]]:
        """
        返回 (retrieval_strategy, top_reasons)
        - retrieval_strategy: 'default' | 'expanded' | 'evidence_focused'
        - top_reasons: 历史上该类问题最常见的失败原因（用于诊断展示）
        """
        similar = self.find_similar(question)
        if not similar:
            return "default", []

        # 聚合所有相似记录的失败原因
        all_reasons: dict[str, int] = {}
        for s in similar:
            for r in s["failure_reasons"]:
                all_reasons[r] = all_reasons.get(r, 0) + 1

        top_reasons = sorted(all_reasons, key=all_reasons.get, reverse=True)[:3]

        # 策略决策：按最严重的失败原因选策略
        # 检索跑题 > 幻觉/引用错误 > 覆盖不全
        if "irrelevant_retrieval" in top_reasons or "weak_relevance" in top_reasons:
            strategy = "expanded"
        elif "hallucination_risk" in top_reasons or "weak_citation" in top_reasons:
            strategy = "evidence_focused"
        elif "low_coverage" in top_reasons:
            strategy = "expanded"
        else:
            strategy = "default"

        return strategy, top_reasons

    # ─── 统计信息 ─────────────────────────────────────
    def stats(self) -> dict:
        db = self._load()
        entries = db["entries"]
        if not entries:
            return {"total": 0, "improved": 0, "avg_score": None, "json_mode_success_rate": None}

        improved = sum(1 for e in entries if e.get("improved_answer"))
        avg = sum(e["scores"].get("total", 0) for e in entries) / len(entries)

        # JSON 模式成功率
        json_entries = [e for e in entries if e.get("json_mode") is not None]
        json_success = sum(1 for e in json_entries if e.get("json_mode") is True)
        json_rate = round(json_success / len(json_entries) * 100, 1) if json_entries else None

        return {
            "total": len(entries),
            "improved": improved,
            "avg_score": round(avg, 1),
            "json_mode_success_rate": json_rate,
        }

    # ─── 质量仪表盘 ───────────────────────────────────
    def quality_report(self) -> dict:
        """
        返回完整的质量分析报告，用于持续改进追踪
        """
        db = self._load()
        entries = db["entries"]
        if not entries:
            return {
                "total": 0,
                "score_distribution": {},
                "dimension_averages": {},
                "failure_reasons": {},
                "json_mode_rate": None,
                "recent_entries": [],
            }

        # 分数分布（10 分一段）
        dist = {f"{i*10}-{i*10+9}": 0 for i in range(10)}
        dist[f"100+"] = 0
        for e in entries:
            t = e["scores"].get("total", 0)
            bucket = min(int(t // 10), 9)
            dist[f"{bucket*10}-{bucket*10+9}"] += 1

        # 各维度平均分
        dims = ["relevance", "coverage", "citation_quality", "factual_grounding", "completeness"]
        dim_avgs = {}
        for dim in dims:
            vals = [e["scores"].get(dim) for e in entries if e["scores"].get(dim) is not None]
            if vals:
                dim_avgs[dim] = round(sum(vals) / len(vals), 1)

        # 失败原因统计
        all_reasons: dict[str, int] = {}
        for e in entries:
            for r in e.get("failure_reasons", []):
                all_reasons[r] = all_reasons.get(r, 0) + 1

        # JSON 模式成功率
        json_entries = [e for e in entries if e.get("json_mode") is not None]
        json_success = sum(1 for e in json_entries if e.get("json_mode") is True)
        json_rate = round(json_success / len(json_entries) * 100, 1) if json_entries else None

        # 最近 5 条
        recent = sorted(entries, key=lambda x: x["timestamp"], reverse=True)[:5]
        recent_entries = [{
            "question": e["question"][:50],
            "score": e["scores"].get("total"),
            "reasons": e["failure_reasons"],
            "timestamp": e["timestamp"],
        } for e in recent]

        return {
            "total": len(entries),
            "score_distribution": dist,
            "dimension_averages": dim_avgs,
            "failure_reasons": dict(sorted(all_reasons.items(), key=lambda x: x[1], reverse=True)),
            "json_mode_rate": json_rate,
            "recent_entries": recent_entries,
        }


# ─── 全局单例 ──────────────────────────────────────────
_store: FeedbackStore | None = None

def get_feedback_store() -> FeedbackStore:
    global _store
    if _store is None:
        _store = FeedbackStore()
    return _store
