from __future__ import annotations

from datetime import datetime, timezone

from app.models.job import Job, JobStatus
from app.pipeline.stages.base import PipelineStage
from app.services.concept.branch_judge import BranchJudge
from app.services.llm.base import LLMProvider


class BranchJudgeStage(PipelineStage):
    def __init__(self, llm: LLMProvider) -> None:
        self.judge = BranchJudge(llm)

    @property
    def name(self) -> str:
        return "branch_judge"

    async def execute(self, job: Job) -> Job:
        job.status = JobStatus.JUDGING

        # Find concepts that need branch disambiguation
        resolved = job.result.metadata.get("resolved_concepts", [])
        ambiguous = [c for c in resolved if not c.get("branches")]

        if not ambiguous or job.result.canonical_text is None:
            return job

        # Build judge items with sentence context
        full_text = job.result.canonical_text.full_text
        judge_items = []
        for concept in ambiguous:
            # Find sentence containing this concept
            concept_text = concept.get("concept_text", "")
            idx = full_text.lower().find(concept_text.lower())
            if idx >= 0:
                # Extract surrounding sentence (rough heuristic)
                start = max(0, full_text.rfind(".", 0, idx) + 1)
                end = full_text.find(".", idx + len(concept_text))
                if end == -1:
                    end = len(full_text)
                else:
                    end += 1
                sentence = full_text[start:end].strip()
            else:
                sentence = concept_text

            judge_items.append({
                "concept_text": concept_text,
                "sentence": sentence,
                "candidate_branches": [],  # Let judge pick from all branches
            })

        if judge_items:
            document_type = job.result.metadata.get("self_identified_type", "")
            results = await self.judge.judge_batch(judge_items, document_type=document_type)
            # Update concepts with judge decisions
            for concept, result in zip(ambiguous, results):
                if isinstance(result, dict):
                    branch = result.get("branch", "")
                    concept["branches"] = [branch] if branch else []
                    # Weighted blend: 70% pipeline score + 30% judge score
                    existing_conf = concept.get("confidence", 0)
                    judge_conf = result.get("confidence", 0)
                    concept["confidence"] = min(1.0, existing_conf * 0.7 + judge_conf * 0.3)
                    # Judge validates → confirmed; no branch found → rejected
                    concept["state"] = "confirmed" if branch else "rejected"
                    # Record lineage event
                    events = concept.setdefault("_lineage_events", [])
                    if branch:
                        events.append({
                            "stage": "branch_judge",
                            "action": "branch_assigned",
                            "detail": f"LLM judge assigned branch '{branch}'",
                            "confidence": result.get("confidence"),
                            "reasoning": result.get("reasoning", ""),
                        })
                    else:
                        events.append({
                            "stage": "branch_judge",
                            "action": "rejected",
                            "detail": "LLM judge could not assign a branch",
                            "confidence": result.get("confidence"),
                            "reasoning": result.get("reasoning", ""),
                        })

        # POS-based branch affinity adjustment
        pos_adjusted = self._apply_pos_branch_affinity(job, ambiguous)

        log = job.result.metadata.setdefault("activity_log", [])
        msg = f"Judged {len(ambiguous)} ambiguous concepts for branch assignment"
        if pos_adjusted:
            msg += f", {pos_adjusted} POS-adjusted"
        log.append({"ts": datetime.now(timezone.utc).isoformat(), "stage": self.name, "msg": msg})
        return job

    @staticmethod
    def _pos_branch_affinity(pos_tag: str, assigned_branch: str) -> float:
        """Compute a small affinity bonus/penalty based on POS vs branch semantics."""
        from app.config import settings

        boost = settings.pos_branch_affinity_boost
        branch_lower = assigned_branch.lower()

        action_terms = ("process", "granting", "filing", "action", "procedure", "activity")
        entity_terms = ("document", "person", "organization", "role", "asset", "thing", "object")

        if pos_tag in ("VERB", "AUX"):
            if any(t in branch_lower for t in action_terms):
                return boost
            if any(t in branch_lower for t in entity_terms):
                return -boost
        elif pos_tag in ("NOUN", "PROPN"):
            if any(t in branch_lower for t in entity_terms):
                return boost
            if any(t in branch_lower for t in action_terms):
                return -boost
        return 0.0

    @staticmethod
    def _apply_pos_branch_affinity(job: Job, concepts: list[dict]) -> int:
        """Apply POS-based affinity adjustments to judged concepts."""
        from app.config import settings
        from app.services.nlp.pos_lookup import get_majority_pos

        if not settings.pos_confidence_enabled or not settings.pos_tagging_enabled:
            return 0

        sentence_pos = job.result.metadata.get("sentence_pos", [])
        if not sentence_pos:
            return 0

        full_text = job.result.canonical_text.full_text if job.result.canonical_text else ""
        adjusted = 0

        for concept in concepts:
            branches = concept.get("branches", [])
            if not branches:
                continue

            concept_text = concept.get("concept_text", "")
            idx = full_text.lower().find(concept_text.lower())
            if idx < 0:
                continue

            pos = get_majority_pos(idx, idx + len(concept_text), sentence_pos)
            if pos is None:
                continue

            affinity = BranchJudgeStage._pos_branch_affinity(pos, branches[0])
            if affinity == 0.0:
                continue

            old_conf = concept.get("confidence", 0)
            concept["confidence"] = max(0.0, min(1.0, old_conf + affinity))
            adjusted += 1

            events = concept.setdefault("_lineage_events", [])
            events.append({
                "stage": "branch_judge",
                "action": "pos_affinity",
                "detail": f"POS '{pos}' + branch '{branches[0]}' → affinity {affinity:+.3f}",
                "confidence": concept["confidence"],
            })

        return adjusted
