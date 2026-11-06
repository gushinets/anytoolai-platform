"""Review saved Update outputs offline, one criterion at a time.

python scripts/agent/client_update_writer_eval.py review \
    --directory <results-directory> --series sol-medium --reviewer Putilin

Decisions append to verdicts.jsonl, which the existing report command consumes.
No provider calls. Agent observations are shown separately, never accepted automatically.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from client_update_writer_eval import (
    configuration_problems,
    digest,
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
    reviewer = row["reviewer"]
    questions = run["input"]["criteria"]
    print(f"Модель: {run['model']}; reasoning: {run['reasoning_effort']}; проверяющий: {reviewer}")
    print(f"\nИсходный запрос:\n{run['input']['progress_notes']}")
    print("\nОтвет модели (text и call_to_action вместе):")
    print(json.dumps(run["output"], ensure_ascii=False, indent=2))
    if observation and matches(observation, run):
        print(f"\nПредварительная оценка агента всего ответа: {observation['suggestion']}")
        print(observation["reason"])
        print("Это подсказка для всего ответа, а не подтверждённые оценки отдельных пунктов.")
    else:
        print("\nНет актуальной предварительной оценки агента для этих хешей.")
    for index, question in enumerate(questions):
        if row["answers"][index]["decision"] in ("yes", "no"):
            continue
        answer = choose(f"\nПункт {index + 1}/{len(questions)}: {question}")
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--series", help="Only review this configuration, e.g. sol-medium")
    args = parser.parse_args(argv)
    try:
        review(args.directory, args.reviewer, args.series)
    except (ReviewStopped, EOFError, KeyboardInterrupt):
        print("\nПроверка остановлена. Сохранённые решения останутся при следующем запуске.")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Ошибка: {exc}\n")


if __name__ == "__main__":
    main()
