#!/usr/bin/env python3
"""Детерминированная проверка публичного пакета из четырёх скиллов."""

from __future__ import annotations

import hashlib
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {
    "resolve-model-element",
    "model-production-system",
    "maintain-production-system",
    "audit-production-system",
}
REQUIRED_REFERENCES = {
    "references/LANGUAGE.md",
    "references/METAONTOLOGY.md",
    "references/INTERVIEW-CONTRACT.md",
    "references/TEMPLATE-CONTRACT.md",
    "references/PROJECTION-CONTRACT.md",
}
PUBLIC_TEMPLATE_ID = "1L9fHH5r7RG7a5uVaktZLjgFzixnalMM4_Z6_Pi7Er3k"
TEMPLATE_MANIFEST = ROOT / "templates" / "template-manifest.yaml"
TEMPLATE_SNAPSHOT = ROOT / "templates" / "production-system-model-template-v0.1.xlsx"
EXPECTED_TEMPLATE_SHEETS = (
    "Инструкция",
    "Система",
    "Схема шаблона",
    "Источники",
    "Версии",
    "Позиции",
    "Назначения",
    "Процессы",
    "Действия",
    "Связи действий",
    "Объекты",
    "Состояния",
    "Переходы",
    "Элементы модели",
    "Контракты",
    "Связи модели",
    "Проверки",
    "Реестр процессов",
    "Рабочая панель",
    "Диаграммы",
    "Проекция draw.io",
)
EXPECTED_VERSION_STATUSES = {
    "черновик",
    "принято",
    "действует",
    "закрыто",
}
EXPECTED_VERSION_TRANSITIONS = {
    "черновик → принято",
    "черновик → закрыто",
    "принято → действует",
    "принято → закрыто",
    "действует → закрыто",
}


def frontmatter(text: str) -> tuple[dict[str, str], int]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("файл не начинается с YAML frontmatter")
    try:
        end = lines[1:].index("---") + 1
    except ValueError as exc:
        raise ValueError("frontmatter не закрыт") from exc

    result: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.match(r"^([a-z][a-z0-9-]*):\s*(.+)$", line)
        if not match:
            raise ValueError(f"неподдерживаемая строка frontmatter: {line!r}")
        key, value = match.groups()
        result[key] = value.strip().strip('"').strip("'")
    return result, end


def markdown_links(path: Path) -> list[Path]:
    result: list[Path] = []
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = target.split("#", 1)[0]
        if not clean:
            continue
        result.append((path.parent / clean).resolve())
    return result


def text_files() -> list[Path]:
    allowed = {".md", ".yaml", ".yml", ".py", ".txt"}
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in allowed and ".git" not in path.parts
    ]


def manifest_value(text: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*[\"']?([^\n\"']+)[\"']?\s*$", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def validate_template(errors: list[str]) -> None:
    if not TEMPLATE_MANIFEST.is_file():
        errors.append("нет templates/template-manifest.yaml")
        return
    if not TEMPLATE_SNAPSHOT.is_file():
        errors.append("нет версионного XLSX-снимка шаблона")
        return

    manifest = TEMPLATE_MANIFEST.read_text(encoding="utf-8")
    if manifest_value(manifest, "spreadsheet_id") != PUBLIC_TEMPLATE_ID:
        errors.append("template-manifest.yaml содержит неожиданный spreadsheet_id")

    declared_snapshot = manifest_value(manifest, "snapshot")
    if declared_snapshot != "templates/production-system-model-template-v0.1.xlsx":
        errors.append("template-manifest.yaml содержит неожиданный путь snapshot")

    expected_sha = manifest_value(manifest, "sha256")
    actual_sha = hashlib.sha256(TEMPLATE_SNAPSHOT.read_bytes()).hexdigest()
    if not expected_sha or expected_sha != actual_sha:
        errors.append(
            "контрольная сумма XLSX не совпадает с templates/template-manifest.yaml"
        )

    if not zipfile.is_zipfile(TEMPLATE_SNAPSHOT):
        errors.append("снимок шаблона не является корректным XLSX ZIP-контейнером")
        return

    with zipfile.ZipFile(TEMPLATE_SNAPSHOT) as archive:
        names = set(archive.namelist())
        if "xl/vbaProject.bin" in names:
            errors.append("XLSX-шаблон не должен содержать VBA-макросы")
        if any(name.startswith("xl/externalLinks/") for name in names):
            errors.append("XLSX-шаблон содержит внешние бинарные связи")
        try:
            workbook_xml = archive.read("xl/workbook.xml")
        except KeyError:
            errors.append("в XLSX-шаблоне отсутствует xl/workbook.xml")
            return

    root = ElementTree.fromstring(workbook_xml)
    namespace = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    sheet_names = tuple(
        node.attrib["name"] for node in root.findall(f".//{namespace}sheet")
    )
    if sheet_names != EXPECTED_TEMPLATE_SHEETS:
        errors.append(
            "состав или порядок листов XLSX не совпадает с контрактом; "
            f"найдено {list(sheet_names)}"
        )


def validate_version_lifecycle(errors: list[str]) -> None:
    language_path = ROOT / "references" / "LANGUAGE.md"
    metaontology_path = ROOT / "references" / "METAONTOLOGY.md"
    if not language_path.is_file() or not metaontology_path.is_file():
        return

    language = language_path.read_text(encoding="utf-8")
    status_section = re.search(
        r"^### Статус версии\n(?P<body>.*?)^### Слой модели и статус версии",
        language,
        re.MULTILINE | re.DOTALL,
    )
    statuses = (
        set(
            re.findall(
                r"^#### [^\n]+ \(`([^`]+)`\)$",
                status_section.group("body"),
                re.MULTILINE,
            )
        )
        if status_section
        else set()
    )
    if statuses != EXPECTED_VERSION_STATUSES:
        errors.append(
            "LANGUAGE.md должен определять ровно четыре статуса версии; "
            f"найдено {sorted(statuses)}"
        )

    metaontology = metaontology_path.read_text(encoding="utf-8")
    transitions = set(
        re.findall(
            r"^\| `([^`]+ → [^`]+)` \|",
            metaontology,
            re.MULTILINE,
        )
    )
    if transitions != EXPECTED_VERSION_TRANSITIONS:
        errors.append(
            "METAONTOLOGY.md содержит неожиданный граф переходов версии; "
            f"найдено {sorted(transitions)}"
        )


def validate() -> list[str]:
    errors: list[str] = []
    skills_root = ROOT / "skills"
    actual = {path.name for path in skills_root.iterdir() if path.is_dir()}
    if actual != EXPECTED_SKILLS:
        errors.append(
            "папки skills должны содержать ровно четыре скилла; "
            f"ожидалось {sorted(EXPECTED_SKILLS)}, найдено {sorted(actual)}"
        )

    for relative in sorted(REQUIRED_REFERENCES):
        if not (ROOT / relative).is_file():
            errors.append(f"нет обязательного reference: {relative}")

    validate_version_lifecycle(errors)
    validate_template(errors)

    for name in sorted(EXPECTED_SKILLS):
        skill_dir = skills_root / name
        skill_path = skill_dir / "SKILL.md"
        agent_path = skill_dir / "agents" / "openai.yaml"

        if not skill_path.is_file():
            errors.append(f"{name}: нет SKILL.md")
            continue
        if not agent_path.is_file():
            errors.append(f"{name}: нет agents/openai.yaml")
            continue

        text = skill_path.read_text(encoding="utf-8")
        try:
            meta, _ = frontmatter(text)
        except ValueError as exc:
            errors.append(f"{name}: {exc}")
            continue

        if set(meta) != {"name", "description"}:
            errors.append(
                f"{name}: frontmatter должен содержать только name и description, найдено {sorted(meta)}"
            )
        if meta.get("name") != name:
            errors.append(f"{name}: поле name не совпадает с именем папки")
        description = meta.get("description", "")
        if len(description) < 80:
            errors.append(f"{name}: description недостаточно подробно задаёт функцию и триггер")
        if not re.search(r"[А-Яа-яЁё]", description):
            errors.append(f"{name}: description должен быть на русском языке")
        if len(text.splitlines()) > 500:
            errors.append(f"{name}: SKILL.md превышает 500 строк")
        for marker in ("TODO", "Structuring This Skill", "[TODO"):
            if marker in text:
                errors.append(f"{name}: найден шаблонный маркер {marker!r}")

        for reference in (
            "references/LANGUAGE.md",
            "references/METAONTOLOGY.md",
            "references/INTERVIEW-CONTRACT.md",
            "references/TEMPLATE-CONTRACT.md",
        ):
            if reference not in text:
                errors.append(f"{name}: нет обязательной ссылки {reference}")

        for reference_name in (
            "LANGUAGE.md",
            "METAONTOLOGY.md",
            "INTERVIEW-CONTRACT.md",
            "TEMPLATE-CONTRACT.md",
            "PROJECTION-CONTRACT.md",
        ):
            canonical = ROOT / "references" / reference_name
            bundled = skill_dir / "references" / reference_name
            if not bundled.is_file():
                errors.append(f"{name}: нет локальной копии references/{reference_name}")
            elif bundled.read_bytes() != canonical.read_bytes():
                errors.append(
                    f"{name}: references/{reference_name} расходится с корневым контрактом; "
                    "запустите scripts/sync_references.py"
                )

        agent = agent_path.read_text(encoding="utf-8")
        if "$" + name not in agent:
            errors.append(f"{name}: default_prompt не упоминает навык через знак доллара")
        short_match = re.search(r'short_description:\s*"([^"]+)"', agent)
        if not short_match:
            errors.append(f"{name}: нет short_description")
        elif not 25 <= len(short_match.group(1)) <= 64:
            errors.append(f"{name}: short_description должен иметь 25–64 символа")

    manifest = (ROOT / "skill-package.yaml").read_text(encoding="utf-8")
    listed = set(re.findall(r"^\s{2}- ([a-z0-9-]+)$", manifest, re.MULTILINE))
    if listed != EXPECTED_SKILLS:
        errors.append(
            f"skill-package.yaml перечисляет {sorted(listed)}, ожидалось {sorted(EXPECTED_SKILLS)}"
        )

    for path in text_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        secret_patterns = {
            "GitHub token": r"\bgh[opsu]_[A-Za-z0-9]{20,}\b",
            "GitHub fine-grained token": r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
            "OpenAI key": r"\bsk-[A-Za-z0-9]{20,}\b",
            "private key": r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY",
            "private Notion page": r"app\.notion\.com/p/",
        }
        for label, pattern in secret_patterns.items():
            if re.search(pattern, text):
                errors.append(f"{relative}: обнаружен потенциальный секрет или закрытая ссылка ({label})")

        for match in re.finditer(
            r"docs\.google\.com/(document|spreadsheets)/d/([A-Za-z0-9_-]+)", text
        ):
            document_type, document_id = match.groups()
            if document_type == "spreadsheets" and document_id == PUBLIC_TEMPLATE_ID:
                continue
            errors.append(
                f"{relative}: обнаружена Google-ссылка вне публичного шаблона"
            )

        if path.suffix == ".md":
            for target in markdown_links(path):
                if not target.exists():
                    errors.append(f"{relative}: не существует относительная ссылка {target}")

    return errors


def main() -> int:
    errors = validate()
    if errors:
        print("[FAIL] Репозиторий не прошёл проверку:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print("[OK] Ровно 4 скилла")
    print("[OK] Frontmatter, UI-метаданные и общие references согласованы")
    print("[OK] Google Sheets-ссылка и XLSX-снимок шаблона согласованы")
    print("[OK] TODO, битые относительные ссылки и типовые секреты не найдены")
    return 0


if __name__ == "__main__":
    sys.exit(main())
