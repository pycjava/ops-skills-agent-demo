import re

GENERIC_CANDIDATE_KEYWORDS = frozenset(
    {
        "mysql",
        "rds",
        "inspection",
        "health",
        "check",
        "healthcheck",
    }
)


FIELD_LABELS = {
    "实例ID": "instance_id",
    "实例名称": "instance_name",
    "项目": "project_key",
    "区域": "region",
    "环境": "environment",
}

ENVIRONMENT_LABELS = {
    "prod": ("prod", "生产"),
    "uat": ("uat",),
    "dev": ("dev", "测试"),
    "staging": ("staging", "预发"),
}


def normalize_possible_mojibake(text: str) -> str:
    try:
        return text.encode("gb18030").decode("utf-8")
    except UnicodeError:
        return text


def extract_keywords(user_message: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9._-]{1,}", user_message.lower())
    seen: set[str] = set()
    ordered: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def filter_candidate_keywords(keywords: list[str]) -> list[str]:
    return [
        keyword
        for keyword in keywords
        if keyword and keyword not in GENERIC_CANDIDATE_KEYWORDS
    ]


def infer_project_key(path: str) -> str | None:
    filename = path.rsplit("/", 1)[-1].lower()
    match = re.match(r"([a-z0-9_-]+?)-mysql(?:-instances)?\.md$", filename)
    if match:
        return match.group(1)
    return None


def infer_environment(section: str) -> str | None:
    heading = next(
        (line.strip() for line in section.splitlines() if line.strip().startswith("## ")),
        "",
    )
    normalized_heading = normalize_possible_mojibake(heading)
    lowered = normalized_heading.lower()

    for environment, labels in ENVIRONMENT_LABELS.items():
        if any(label in lowered if label.isascii() else label in normalized_heading for label in labels):
            return environment
    return None


def parse_bullet_record(
    section: str,
    path: str,
    normalize_credential_ref,
) -> list[dict[str, str]]:
    fields: dict[str, str] = {"memory_path": path}

    for line in section.splitlines():
        match = re.match(r"- \*\*(.+?)\*\*: (.+)", line.strip())
        if not match:
            continue
        key = normalize_possible_mojibake(match.group(1).strip())
        value = match.group(2).strip()
        if key in FIELD_LABELS:
            fields[FIELD_LABELS[key]] = value
        elif "credential_ref" in key:
            fields["credential_ref"] = normalize_credential_ref(value)

    return [fields] if fields.get("instance_id") else []


def parse_markdown_table_records(
    section: str,
    path: str,
    normalize_credential_ref,
) -> list[dict[str, str]]:
    lines = [line.strip() for line in section.splitlines() if line.strip()]
    environment = infer_environment(section)
    inferred_project_key = infer_project_key(path)
    records: list[dict[str, str]] = []

    for index, line in enumerate(lines):
        normalized_line = normalize_possible_mojibake(line)
        if not (line.startswith("|") and "实例ID" in normalized_line):
            continue
        if index + 1 >= len(lines):
            continue

        separator = lines[index + 1]
        if not (separator.startswith("|") and "-" in separator):
            continue

        headers = [
            normalize_possible_mojibake(cell.strip())
            for cell in line.strip("|").split("|")
        ]

        for row in lines[index + 2 :]:
            if not row.startswith("|"):
                break
            if set(row.replace("|", "").replace("-", "").replace(":", "").strip()) == set():
                continue

            cells = [cell.strip() for cell in row.strip("|").split("|")]
            if len(cells) != len(headers):
                continue

            fields: dict[str, str] = {"memory_path": path}
            for header, value in zip(headers, cells, strict=False):
                if header in FIELD_LABELS:
                    fields[FIELD_LABELS[header]] = value
                elif "credential_ref" in header:
                    fields["credential_ref"] = normalize_credential_ref(value)

            if environment and not fields.get("environment"):
                fields["environment"] = environment
            if inferred_project_key and not fields.get("project_key"):
                fields["project_key"] = inferred_project_key

            if fields.get("instance_id"):
                records.append(fields)

    return records


def parse_instance_records(
    content: str,
    path: str,
    normalize_credential_ref,
) -> list[dict[str, str]]:
    sections = re.split(r"\n(?=## )", content)
    records: list[dict[str, str]] = []

    for section in sections:
        if "实例ID" not in normalize_possible_mojibake(section):
            continue

        bullet_records = parse_bullet_record(section, path, normalize_credential_ref)
        if bullet_records:
            records.extend(bullet_records)
            continue

        table_records = parse_markdown_table_records(
            section,
            path,
            normalize_credential_ref,
        )
        if table_records:
            records.extend(table_records)

    return records


def score_instance_candidate(record: dict[str, str], keywords: list[str]) -> int:
    haystacks = [
        record.get("instance_id", "").lower(),
        record.get("instance_name", "").lower(),
        record.get("project_key", "").lower(),
        record.get("environment", "").lower(),
        record.get("memory_path", "").lower(),
    ]

    score = 0
    for keyword in keywords:
        for haystack in haystacks:
            if keyword and keyword in haystack:
                score += 5
    return score


def select_top_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    if not candidates:
        return []

    top_score = int(candidates[0].get("score") or 0)
    return [item for item in candidates if int(item.get("score") or 0) == top_score]


def resolve_candidate_selection(
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    top_candidates = select_top_candidates(candidates)
    ambiguous = len(top_candidates) > 1
    selected = top_candidates[0] if len(top_candidates) == 1 else None
    return {
        "ambiguous": ambiguous,
        "top_candidates": top_candidates,
        "display_candidates": candidates,
        "selected": selected,
    }
