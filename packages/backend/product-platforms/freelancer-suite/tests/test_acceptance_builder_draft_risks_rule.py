"""Exercise the same acceptance checks against authored examples and captured live results."""

import json
import re
from pathlib import Path

import jsonschema
import pytest
from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle

ROOT = Path(__file__).resolve().parents[5]
FIXTURES = ROOT / "tests/fixtures/acceptance_builder_eval"
PRODUCT = next(p for p in FreelancerSuiteBundle().config_roots() if p.name == "acceptance_builder")
SCHEMA = json.loads((PRODUCT / "schemas/draft_output.schema.json").read_text(encoding="utf-8"))
CASES = {
    case["id"]: case
    for case in json.loads((FIXTURES / "draft_risks_questions.json").read_text(encoding="utf-8"))[
        "cases"
    ]
}


def check_result(case, output):
    jsonschema.validate(output, SCHEMA)
    issues = output["issues"]
    questions = output["questions"]
    values = output["extracted"]["values"]
    assert values["analysis_language"].lower().split("-")[0] == case["language"]
    criteria = " ".join(values.get("acceptance_criteria", [])).lower()
    asked = " ".join(q["question"] for q in questions).lower()
    assert all(0 <= q["source_issue_index"] < len(issues) for q in questions)
    rule = case["checks"]
    if rule == "vague":
        assert len(questions) >= 2
        assert re.search("страниц|функц", asked) and re.search(
            "соглас|утверж|одобр|приним|принят", asked
        )
        assert "дизайн" in asked or "оформлен" in asked
        assert not re.search(r"\d", asked + " ".join(i["description"] for i in issues))
        assert {"acceptance_criteria", "assumptions"} <= set(output["extracted"]["missing_fields"])
    elif rule == "feasibility":
        deadline = {"ru": "завтра", "en": "tomorrow", "es": "mañana"}[case["language"]]

        def combined(issue):
            text = (issue["description"] + " " + issue.get("evidence", "")).lower()
            return (
                issue["severity"] == "high"
                and issue["category"] in {"scope_risk", "timeline_risk", "budget_risk"}
                and all(fact in text for fact in ("500", "15 000", deadline))
            )

        assert any(combined(i) for i in issues)
        assert any(
            i["category"] == "scope_risk"
            and re.search(
                "правок|правки|поменяться|revisions|change|cambios|cambiar",
                i.get("evidence", "").lower(),
            )
            for i in issues
        )
        assert re.search(
            "приоритет|запуск|запустить|границ|первую очередь|priority|priorit|launch|scope|prioridad|lanzamiento|alcance",
            asked,
        )
        facts = json.dumps(values, ensure_ascii=False).lower()
        assert "500" in facts and ("15 000" in facts or deadline in facts)
        assert not re.search(
            "невозможно|нереально|не получится|impossible|cannot be done|imposible",
            " ".join(i["description"] for i in issues).lower(),
        )
    elif rule == "contradiction":
        (index,) = [n for n, issue in enumerate(issues) if issue["category"] == "contradiction"]
        evidence = issues[index]["evidence"].lower()
        assert "только на русском" in evidence and "английская версия" in evidence
        assert any(q["source_issue_index"] == index for q in questions)
        assert "форм" in criteria and "почт" in criteria
        assert not re.search("русск|английск", criteria)
    else:
        assert rule == "complete"
        assert issues == questions == []
        assert all(word in criteria for word in ("блок", "форм", "заявк"))


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_authored_draft(case):
    check_result(case, case["canonical"])


def test_reported_briefs_are_verbatim():
    assert CASES["AB-894-B-RU"]["input"]["brief_text"] == (
        "Нужен сайт для моего бизнеса. Хочется красиво и современно, чтобы клиенты шли. Пишите, кто может сделать."
    )
    assert CASES["AB-894-C-RU"]["input"]["brief_text"] == (
        "Нужен интернет-магазин на 500 товаров с личным кабинетом, онлайн-оплатой и интеграцией с 1С. "
        "Сдача завтра, потому что в пятницу запуск рекламы. Бюджет 15 000 рублей. "
        "Правок будет немного, но по ходу всё может поменяться. Дизайн придумайте сами, мне нравится как у больших сайтов."
    )


def test_draft_prompt_rules():
    detect = (PRODUCT / "prompts/detect_issues.v1.md").read_text(encoding="utf-8").lower()
    for rule in (
        "combined feasibility",
        "quote both fragments verbatim",
        "never invent",
        "checkable condition is not an issue",
    ):
        assert rule in detect
    questions = (PRODUCT / "prompts/generate_questions.v1.md").read_text(encoding="utf-8").lower()
    assert "never propose a specific new deadline, budget or quantity" in questions
    workflow = (PRODUCT / "workflows.yaml").read_text(encoding="utf-8")
    draft, check = workflow.split("- workflow_id: acceptance_builder.check_v1")
    assert "put neither version" in draft and "put neither version" not in check
