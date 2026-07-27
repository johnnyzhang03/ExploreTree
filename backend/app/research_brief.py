"""Structured intent passed from a Copilot conversation into ExploreTree."""

from dataclasses import dataclass, field


def _clean_items(values: list[str] | None) -> list[str]:
    return [value.strip() for value in (values or []) if value.strip()]


@dataclass
class ResearchBrief:
    question: str
    objective: str = ""
    audience: str = ""
    scope: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    freshness: str = ""
    desired_output: str = ""

    @classmethod
    def create(
        cls,
        question: str,
        *,
        objective: str = "",
        audience: str = "",
        scope: list[str] | None = None,
        constraints: list[str] | None = None,
        freshness: str = "",
        desired_output: str = "",
    ) -> "ResearchBrief":
        return cls(
            question=question.strip(),
            objective=objective.strip(),
            audience=audience.strip(),
            scope=_clean_items(scope),
            constraints=_clean_items(constraints),
            freshness=freshness.strip(),
            desired_output=desired_output.strip(),
        )

    def planning_prompt(self, branch: str | None = None) -> str:
        lines = [f"Research question: {self.question}"]
        if self.objective:
            lines.append(f"Decision or objective: {self.objective}")
        if self.audience:
            lines.append(f"Audience: {self.audience}")
        if self.scope:
            lines.append(f"Required scope: {'; '.join(self.scope)}")
        if self.constraints:
            lines.append(f"Constraints: {'; '.join(self.constraints)}")
        if self.freshness:
            lines.append(f"Freshness requirement: {self.freshness}")
        if self.desired_output:
            lines.append(f"Desired outcome: {self.desired_output}")
        if branch and branch.casefold() != self.question.casefold():
            lines.append(f"Current branch to investigate: {branch}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "objective": self.objective,
            "audience": self.audience,
            "scope": self.scope,
            "constraints": self.constraints,
            "freshness": self.freshness,
            "desiredOutput": self.desired_output,
        }
