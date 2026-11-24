"""Exercise the same acceptance checks against authored examples and captured live results."""

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path

import jsonschema
import pytest
from anytoolai_freelancer_suite.bundle import FreelancerSuiteBundle

from scripts.agent.draft_risk_review import scope_questions

ROOT = Path(__file__).resolve().parents[5]
FIXTURES = ROOT / "tests/fixtures/acceptance_builder_eval"
PRODUCT = next(p for p in FreelancerSuiteBundle().config_roots() if p.name == "acceptance_builder")
SCHEMA = json.loads((PRODUCT / "schemas/draft_output.schema.json").read_text(encoding="utf-8"))
SUITE = json.loads((FIXTURES / "draft_risks_questions.json").read_text(encoding="utf-8"))
CASES = {case["id"]: case for case in SUITE["cases"]}
SCOPE_REVIEWS = json.loads((FIXTURES / "reviewed_scope_questions.json").read_text(encoding="utf-8"))



# Each expectation describes this fixture. Free-form source fidelity is also reviewed against
# the case rubric. These probes never run on arbitrary customer text in production.
COMPLETE_TERMS = {
    "named blocks": (
        r"\b(?:5|five|cinco|пять)\b",
        r"оффер|offer|oferta",
        r"программ|curriculum|program|syllabus",
        r"преподавател|teacher|instructor|docente|profesor",
        r"тариф|pric|tarifa|precio",
        r"форм|form",
    ),
    "agreed layout": (
        r"макет|layout|design|diseño|maqueta",
        r"согласован|утвержд|approv|agreed|acordad|aprobad",
    ),
    "test submission": (r"тестов|test|prueba", r"заявк|application|submission|solicitud|envío"),
    "recipient": (r"info@school\.example",),
    "mobile": (r"мобиль|mobile|móvil|móviles",),
    "deadline": (r"14\s+(?:рабоч\w*\s+дн|business days|working days|días (?:hábiles|laborables))",),
    "budget": (r"60[ ,.\u202f\xa0]?000\s*(?:руб|₽|rub)",),
    "included revisions": (
        r"(?:\b2\b|два|двух|dos|two)\s+(?:раунд|rond|round)",
        r"правок|правк|revision|revisi[oó]n|correcci[oó]n|cambios",
        r"включ|вход|includ|inclu",
    ),
}
WRONG_MILESTONE = re.compile(
    r"(?:завтрашн\w* запуск|запустить завтра|запуск(?: магазина)? (?:уже |на )?завтра|launch(?:ing)? (?:the (?:shop|store) )?(?:by |on )?(?:tomorrow|friday)"
    r"|(?:shop|store) goes live (?:tomorrow|friday)|lanzamiento (?:de (?:la tienda )?)?(?:mañana|el viernes)"
    r"|entrega (?:el )?viernes|delivery (?:on |by )?friday|сдач\w* (?:в|к) пятниц\w*)"
)
UNSTATED_TERMS = re.compile(
    r"\d|wordpress|shopify|wix|\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"lunes|martes|miércoles|jueves|viernes|sábado|domingo|tomorrow|mañana)\b|"
    r"понедельник|вторник|(?:в |к )сред[уе]|четверг|пятниц|суббот|воскресень|завтра"
)


def prose(output):
    for name, values in output["extracted"]["values"].items():
        if name != "analysis_language":
            yield from values
    for section, fields in (
        ("issues", ("description", "evidence")),
        ("questions", ("question", "rationale")),
    ):
        for item in output[section]:
            yield from (item[field] for field in fields if field in item)


def has_all(text, patterns):
    return all(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def check_complete(values):
    terms = values.get("acceptance_criteria", []) + values.get("deliverables", [])
    for label, patterns in COMPLETE_TERMS.items():
        # The names can be listed across sections. Qualifiers belong to their own term.
        candidates = [" ".join(terms)] if label == "named blocks" else terms
        assert any(has_all(line, patterns) for line in candidates), label
    assets = values.get("assumptions", []) + values.get("deliverables", [])
    owner = r"заказчик|клиент|client|customer|school|escuela|nosotros|we\b"
    supply = r"предостав|переда|suppl|provid|proporcion|facilit|aport"
    for material in (r"текст|text|copy", r"фото|photo|foto"):
        assert any(has_all(line, (owner, supply, material)) for line in assets), (
            "client-supplied assets"
        )


def check_contradiction(issues, questions, criteria):
    (index,) = [n for n, issue in enumerate(issues) if issue["category"] == "contradiction"]
    evidence = issues[index]["evidence"].lower()
    alternatives = (
        r"только на русском|russian only|only in russian|solo en ruso",
        r"английская версия|english version|versión completa en inglés",
    )
    assert has_all(evidence, alternatives)
    assert any(
        q["source_issue_index"] == index
        and has_all(
            q["question"],
            (
                r"како[йм]|какая|какие|какую|каки[ех]|выб|нужн|требуется|долж|"
                r"which|what language|what version|should|do you (?:want|require|prefer)|"
                r"cuál|qué idioma|qué versión|debe|quiere|prefiere|"
                r"только.{1,50}или|only.{1,50} or |solo.{1,50} o ",
                r"язык|языч|русск|английск|language|russian|english|idioma|ruso|inglés",
            ),
        )
        for q in questions
    ), "the linked question must ask for the language decision"
    assert has_all(criteria, (r"форм|form", r"почт|e-?mail|correo"))
    assert not re.search("русск|английск|russian|english|ruso|inglés", criteria)


def scope_review_key(case, output, question):
    evidence = [
        case["input"],
        SUITE["review_rubric"]["feasibility"],
        output["issues"][question["source_issue_index"]],
        question,
    ]
    return hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


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
        assert len(questions) > 1
        assert re.search("страниц|функц|pages?|features?|function|páginas?|funcion", asked)
        assert any(
            re.search("дизайн|оформлен|design|diseño", q["question"].lower())
            and re.search(
                "соглас|утверж|одобр|приним|принят|approv|accept|sign.off|apr[ou]|aprob|acept|valid",
                q["question"].lower(),
            )
            for q in questions
        )
        assert not any(UNSTATED_TERMS.search(line.lower()) for line in prose(output)), (
            "unstated term"
        )
        assert {"acceptance_criteria", "assumptions"} <= set(
            output["extracted"]["missing_fields"]
        ), "the vague brief states neither acceptance conditions nor project premises"
        assert any(
            re.search(r"сайт|website|web ?site|sitio web|página web", item.casefold())
            for item in values.get("deliverables", [])
        ), "the explicitly requested website must remain a deliverable"
    elif rule == "feasibility":
        deadline = {"ru": "завтра", "en": "tomorrow", "es": "mañana"}[case["language"]]

        assert not any(WRONG_MILESTONE.search(line.lower()) for line in prose(output)), (
            "wrong milestone"
        )

        candidates = scope_questions(output, case["language"])
        assert candidates, "missing question linked to combined feasibility finding"
        assert any(
            i["category"] == "scope_risk"
            and re.search(
                "правок|правки|поменяться|revisions|change|cambios|cambiar",
                i.get("evidence", "").lower(),
            )
            for i in issues
        )
        decisions = [SCOPE_REVIEWS.get(scope_review_key(case, output, q)) for q in candidates]
        assert any(
            decision and decision["accepted"] and decision["question"] == q["question"]
            for decision, q in zip(decisions, candidates, strict=True)
        ), (
            "FAIL: question does not decide which scope" if all(decisions)
            else "PENDING: review which scope the answer selects"
        )
        facts = json.dumps(values, ensure_ascii=False).lower()
        assert has_all(facts, (r"500", r"15[ .,\u202f\xa0]?000", deadline))
        assert not re.search(
            "невозможно|нереально|не получится|impossible|cannot be done|imposible",
            " ".join(i["description"] for i in issues).lower(),
        )
    elif rule == "contradiction":
        check_contradiction(issues, questions, criteria)
    else:
        assert rule == "complete"
        assert issues == questions == []
        check_complete(values)


@pytest.mark.parametrize("case", CASES.values(), ids=CASES.keys())
def test_authored_draft(case):
    check_result(case, case["canonical"])


def test_reported_briefs_are_verbatim():
    assert CASES["AB-894-B-RU"]["input"]["brief_text"] == (
        "Нужен сайт для моего бизнеса. Хочется красиво и современно, чтобы клиенты шли. "
        "Пишите, кто может сделать."
    )
    assert CASES["AB-894-C-RU"]["input"]["brief_text"] == (
        "Нужен интернет-магазин на 500 товаров с личным кабинетом, онлайн-оплатой "
        "и интеграцией с 1С. "
        "Сдача завтра, потому что в пятницу запуск рекламы. Бюджет 15 000 рублей. "
        "Правок будет немного, но по ходу всё может поменяться. "
        "Дизайн придумайте сами, мне нравится как у больших сайтов."
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


def test_captured_live_series_covers_each_brief_three_times():
    evidence = json.loads(
        (FIXTURES / "any-894-live-acceptance.evidence.json").read_text(encoding="utf-8")
    )
    runs = evidence["runs"]
    expected = {(case_id, attempt) for case_id in CASES for attempt in (1, 2, 3)}
    assert {(run["case_id"], run["run"]) for run in runs} == expected
    assert len({run["session_id"] for run in runs}) == len(runs) == len(expected)
    for run in runs:
        # Keep the original live evidence immutable, including the known incorrect questions.
        bad_launch = run["case_id"] == "AB-894-C-EN" or (
            run["case_id"] == "AB-894-C-ES" and run["run"] in {2, 3}
        )
        if bad_launch:
            with pytest.raises(AssertionError, match="wrong milestone"):
                check_result(CASES[run["case_id"]], run["output"])
        else:
            check_result(CASES[run["case_id"]], run["output"])


@pytest.mark.parametrize(
    ("case_id", "section", "field", "replacement", "reason"),
    [
        ("AB-894-B-RU", "issues", "description", "Сайт нужен к пятнице.", "unstated term"),
        (
            "AB-894-B-RU",
            "questions",
            "question",
            "Какие страницы нужны в WordPress?",
            "unstated term",
        ),
        (
            "AB-894-C-ES",
            "questions",
            "rationale",
            "Prepara el lanzamiento de mañana.",
            "wrong milestone",
        ),
        (
            "AB-894-C-EN",
            "questions",
            "question",
            "What takes priority for launch tomorrow?",
            "wrong milestone",
        ),
        (
            "AB-894-CTRL-CONTRADICTION-RU",
            "questions",
            "question",
            "Вы видите противоречие между формулировками?",
            "language decision",
        ),
    ],
)
def test_one_changed_claim_fails_acceptance(case_id, section, field, replacement, reason):
    case = CASES[case_id]
    output = deepcopy(case["canonical"])
    output[section][0][field] = replacement
    with pytest.raises(AssertionError, match=reason):
        check_result(case, output)


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ("преподаватель", "бонус"),
        ("согласованному макету", "техническому описанию"),
        ("тестовую заявку", "заявку"),
        ("info@school.example", "sales@school.example"),
        ("мобильные устройства", "ноутбуки"),
        ("14 рабочих дней", "14 календарных дней"),
        ("60 000 рублей", "60 000 долларов"),
        ("Включены два раунда", "Оплачиваются отдельно два раунда"),
    ],
)
def test_complete_brief_preserves_each_agreed_term(original, replacement):
    case = CASES["AB-894-CTRL-COMPLETE-RU"]
    output = deepcopy(case["canonical"])
    criteria = output["extracted"]["values"]["acceptance_criteria"]
    assert any(original in line for line in criteria)
    criteria[:] = [line.replace(original, replacement) for line in criteria]
    with pytest.raises(AssertionError):
        check_result(case, output)


def test_equivalent_language_decision_is_accepted():
    case = CASES["AB-894-CTRL-CONTRADICTION-RU"]
    output = deepcopy(case["canonical"])
    output["questions"][0]["question"] = "На каком языке должна быть готовая страница?"
    check_result(case, output)


@pytest.mark.parametrize(
    ("language", "question"),
    [
        ("en", "Are all parts of the shop ready for delivery tomorrow?"),
        ("es", "¿Están listas todas las partes de la tienda para la entrega de mañana?"),
        ("ru", "Весь ли магазин готов к сдаче завтра?"),
        ("en", "What time must the shop be ready for delivery tomorrow?"),
        ("en", "What is the cost of the full scope?"),
        ("en", "Is scope still the priority?"),
        ("ru", "Объём работ по-прежнему в приоритете?"),
        ("es", "¿Sigue siendo prioritario el alcance?"),
        ("es", "¿Cuánto cuesta todo el alcance?"),
    ],
)
def test_feasibility_status_or_price_question_does_not_choose_scope(language, question):
    case = CASES[f"AB-894-C-{language.upper()}"]
    output = deepcopy(case["canonical"])
    output["questions"][0]["question"] = question
    with pytest.raises(AssertionError, match="FAIL: question does not decide which scope"):
        check_result(case, output)


@pytest.mark.parametrize(
    ("filename", "expect_vague_failure"),
    [
        ("any-894-review-3-live.evidence.json", True),
        ("any-894-draft-grounding-live.evidence.json", False),
    ],
)
def test_live_draft_matrix(filename, expect_vague_failure):
    evidence = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    cases = evidence["cases"]
    runs = evidence["runs"]
    assert {(case["family"], case["language"]) for case in cases.values()} == {
        (family, language)
        for family in ("vague", "feasibility", "contradiction", "complete")
        for language in ("ru", "en", "es")
    }
    expected = {(key, attempt) for key in cases for attempt in (1, 2, 3)}
    assert {(r["case_id"], r["run"]) for r in runs} == expected
    assert len({r["session_id"] for r in runs}) == len(runs) == 36
    for run in runs:
        case = cases[run["case_id"]]
        rule = {**case, "checks": case["family"]}
        if expect_vague_failure and case["family"] == "vague":
            with pytest.raises(
                AssertionError, match="neither acceptance conditions nor project premises"
            ):
                check_result(rule, run["output"])
        else:
            check_result(rule, run["output"])


@pytest.mark.parametrize(
    ("lang", "date_only", "scope_choice"),
    [
        (
            "en",
            "Is delivery tomorrow still the priority?",
            "Is the priority for tomorrow to deliver the catalogue and defer customer accounts?",
        ),
        (
            "es",
            "¿Sigue siendo prioritaria la entrega de mañana?",
            "¿La prioridad para mañana es entregar el catálogo y aplazar las cuentas de cliente?",
        ),
        (
            "ru",
            "Сдача завтра всё ещё в приоритете?",
            "В приоритете к завтрашней сдаче каталог, а личный кабинет можно отложить?",
        ),
    ],
)
def test_scope_decisions_require_reviewed_evidence(lang, date_only, scope_choice):
    case = CASES[f"AB-894-C-{lang.upper()}"]
    output = deepcopy(case["canonical"])
    output["questions"][0]["question"] = date_only
    with pytest.raises(AssertionError, match="FAIL"):
        check_result(case, output)
    output["questions"][0]["question"] = scope_choice
    check_result(case, output)
    output["questions"][0]["question"] += "?"
    with pytest.raises(AssertionError, match="PENDING"):
        check_result(case, output)


def test_fourth_review_outputs_meet_deterministic_product_checks():
    archive = json.loads(
        (FIXTURES / "any-894-review-4-live.evidence.json").read_text(encoding="utf-8")
    )
    for run in archive["runs"]:
        record = run["record"]
        case = record["case"]
        check_result(
            {
                "input": case["input"],
                "language": case["expected_language"],
                "checks": case["family"],
            },
            record["output"],
        )
