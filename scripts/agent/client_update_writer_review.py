"""Review saved Client Update Writer outputs offline, one criterion at a time.

Experimental review aid; it does not reopen ANY-624's accepted live review.
Known limitations and the frozen scope are documented in
docs/exec-plans/completed/any-624-update-model-comparison.md (Supporting tooling: scope frozen).

python scripts/agent/client_update_writer_eval.py review \
    --directory <results-directory> --series sol-medium --reviewer Putilin

Decisions append to verdicts.jsonl, which the existing report command consumes.
No provider calls. Open the temporary local review file printed for each run before
answering its numbered criteria. Full input, output, criteria and matching agent observations
are displayed in that file, not on stdout. Cleanup also runs on catchable SIGTERM;
forced process termination (such as SIGKILL) cannot unwind Python context managers.
Agent observations are shown separately, never accepted automatically.
"""

from __future__ import annotations

import argparse
import json
import signal
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from client_update_writer_eval import (
    configuration_problems,
    digest,
    review_input_text,
    revision_problems,
    validate_manifest_identity,
    validate_runs,
    validate_source_revisions,
)
from client_update_writer_eval_report import human_status
from proposal_ai_eval import read_jsonl

Choice = Literal["y", "n", "u", "s"]


class ReviewStopped(Exception):
    """The reviewer chose to leave without deciding the current item."""


def choose(prompt: str) -> Choice:
    while True:
        answer = (
            input(prompt + " [y=да, n=нет, u=не уверен, s=пропустить, q=выход] > ").strip().lower()
        )
        if answer == "q":
            raise ReviewStopped
        if answer in ("y", "n", "u", "s"):
            return answer
        print("Введите y, n, u, s или q. Пустой ввод ничего не подтверждает.")


def verdict_hashes(run: dict) -> dict:
    return {
        "input_sha256": run["input_sha256"],
        "output_sha256": run["output_sha256"],
        "criteria_sha256": digest(run["input"]["criteria"]),
    }


def matches(row: dict, run: dict) -> bool:
    return all(row.get(key) == value for key, value in verdict_hashes(run).items())


def review(directory: Path, reviewer: str, series: str | None = None) -> None:
    reviewer = reviewer.strip()
    if not reviewer or reviewer.lower() == "agent":
        raise ValueError("Укажите имя человека; имя agent зарезервировано для нейросети.")
    manifests = sorted(directory.glob("*/manifest.json"))
    if not manifests:
        raise ValueError("В каталоге нет результатов с manifest.json.")
    if series is not None and series not in {p.parent.name for p in manifests}:
        raise ValueError(f"Неизвестная серия: {series}")
    # Validate the full selected queue before writing any human decisions.
    selected = {
        path: json.loads(path.read_text(encoding="utf-8")) for path in manifests
        if series is None or path.parent.name == series
    }
    validate_manifest_identity(selected.values())
    queue = []
    for path, manifest in selected.items():
        runs = read_jsonl(path.parent / "runs.jsonl")
        validate_runs(manifest, runs)
        if configuration_problems(manifest) or any(
            revision_problems(manifest, run) for run in runs
        ):
            print(
                f"{path.parent.name}: конфигурация или ревизия не подтверждена; "
                "оценка текста не даёт технический PASS."
            )
        queue.extend((path.parent.name, run) for run in runs)
    validate_source_revisions([*selected.values(), *(run for _, run in queue)])
    verdict_path = directory / "verdicts.jsonl"
    verdicts = {(r["series"], r["id"]): r for r in read_jsonl(verdict_path)}
    observation_path = directory.parent / "agent-observations.json"
    observations = {}
    if observation_path.exists():
        document = json.loads(observation_path.read_text(encoding="utf-8"))
        observations = {(r["series"], r["run_id"]): r for r in document["observations"]}

    def save(row: dict) -> None:
        row["reviewed_at"] = datetime.now(UTC).isoformat(timespec="seconds")
        with verdict_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        verdicts[(row["series"], row["id"])] = row
        print("Сохранено.")

    for position, (name, run) in enumerate(queue, 1):
        if not run.get("output"):
            print(f"{name}/{run['id']}: нет ответа модели для оценки текста.")
            continue
        previous = verdicts.get((name, run["id"]))
        if previous and human_status(run, previous)[0] != "PENDING":
            continue
        questions = run["input"]["criteria"]
        if previous and matches(previous, run) and previous.get("reviewer") == reviewer:
            answers = previous.get("answers")
            if (
                not isinstance(answers, list)
                or len(answers) != len(questions)
                or any(
                    not isinstance(answer, dict)
                    or answer.get("question") != question
                    or answer.get("decision") not in (None, "yes", "no", "unknown")
                    for answer, question in zip(answers, questions, strict=True)
                )
            ):
                raise ValueError(f"Повреждены сохранённые пункты: {name}/{run['id']}")
            row = previous
        else:
            row = {
                "series": name,
                "id": run["id"],
                **verdict_hashes(run),
                "reviewer": reviewer,
                "critical_error": None,
                "answers": [
                    {"question": q, "decision": None, "quote": "", "reason": ""} for q in questions
                ],
            }
        print(f"\n=== {position}/{len(queue)} {name}/{run['id']} ===")
        observation = observations.get((directory.name + "/" + name, run["id"]))
        review_run(run, row, observation, save)


def review_run(
    run: dict, row: dict, observation: dict | None, save: Callable[[dict], None]
) -> None:
    questions = run["input"]["criteria"]
    sections = [
        f"Запуск: {run['id']}; модель: {run['model']}; reasoning: {run['reasoning_effort']}",
        f"Проверяющий: {row['reviewer']}",
        f"Исходный запрос:\n{review_input_text(run['input'])}",
        "Ответ модели (text и call_to_action вместе):\n"
        + json.dumps(run["output"], ensure_ascii=False, indent=2),
        "Пункты проверки:\n" + "\n".join(
            f"{index}. {question}" for index, question in enumerate(questions, 1)
        ),
    ]
    if observation and matches(observation, run):
        sections.append(
            f"Предварительная оценка агента всего ответа: {observation['suggestion']}\n"
            f"{observation['reason']}\n"
            "Это подсказка для всего ответа, а не подтверждённые оценки отдельных пунктов."
        )
    else:
        sections.append("Нет актуальной предварительной оценки агента для этих хешей.")
    # Full review content is private regardless of product mode; stdout is not a private display.
    with tempfile.TemporaryDirectory(prefix="anytoolai-review-") as directory:
        path = Path(directory) / "case.txt"
        path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")
        path.chmod(0o600)
        print(f"\nОткройте локальный файл проверки: {path}")
        print("Сверяйте пронумерованные пункты в файле перед ответом.")
        _review_answers(run, row, save)


def _review_answers(run: dict, row: dict, save: Callable[[dict], None]) -> None:
    questions = run["input"]["criteria"]
    for index, question in enumerate(questions):
        if row["answers"][index]["decision"] in ("yes", "no"):
            continue
        answer = choose(f"\nПункт {index + 1}/{len(questions)} (см. локальный файл)")
        if answer == "s":
            continue
        if answer == "y":
            reason = "Критерий подтверждён проверяющим по тексту ответа."
            quote = ""
        else:
            reason = input("Обоснование > ").strip()
            while not reason:
                reason = input("Добавьте обоснование решения > ").strip()
            quote = input("Цитата из ответа (Enter, если проверяете пропуск) > ").strip()
        row["answers"][index] = {
            "question": question,
            "decision": {"y": "yes", "n": "no", "u": "unknown"}[answer],
            "reason": reason,
            "quote": quote,
        }
        row["critical_error"] = None
        save(row)
    if row["critical_error"] is None:
        print(
            "\nКритическая ошибка: потеря/подмена обязательного факта, количества, даты, "
            "готовности или запроса; выдуманная работа/обязательство; неверный язык."
        )
        answer = choose("Есть критическая ошибка?")
        if answer in ("y", "n"):
            row["critical_error"] = answer == "y"
            save(row)
    print(f"Итог: {human_status(run, row)[0]}")


def interrupt_review(signum, _frame) -> None:
    # Unwind the active private review directory while preserving a termination exit status.
    raise SystemExit(128 + signum)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--series", help="Only review this configuration, e.g. sol-medium")
    args = parser.parse_args(argv)
    previous_handler = signal.signal(signal.SIGTERM, interrupt_review)
    try:
        review(args.directory, args.reviewer, args.series)
    except (ReviewStopped, EOFError, KeyboardInterrupt):
        print("\nПроверка остановлена. Сохранённые решения останутся при следующем запуске.")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Ошибка: {exc}\n")
    finally:
        signal.signal(signal.SIGTERM, previous_handler)


if __name__ == "__main__":
    main()
