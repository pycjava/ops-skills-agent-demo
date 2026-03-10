from services.cloud_instance_candidates import (
    extract_keywords,
    infer_environment,
    parse_instance_records,
    resolve_candidate_selection,
    select_top_candidates,
)


def normalize_credential_ref(value: str) -> str:
    return value.strip().lower()


def to_mojibake(text: str) -> str:
    return text.encode("utf-8").decode("gb18030")


def test_parse_instance_records_supports_bullet_sections():
    content = """
# 示例

## 生产环境
- **实例ID**: mysql-123
- **实例名称**: peets-prod-pos-middle-mysql-n
- **项目**: peets
- **区域**: cn-shanghai
- **环境**: prod
- **credential_ref**: peets_prod_main
""".strip()

    records = parse_instance_records(
        content,
        "/memories/agents/dba/peets-mysql-instances.md",
        normalize_credential_ref,
    )

    assert records == [
        {
            "memory_path": "/memories/agents/dba/peets-mysql-instances.md",
            "instance_id": "mysql-123",
            "instance_name": "peets-prod-pos-middle-mysql-n",
            "project_key": "peets",
            "region": "cn-shanghai",
            "environment": "prod",
            "credential_ref": "peets_prod_main",
        }
    ]


def test_parse_instance_records_supports_markdown_tables():
    content = """
# Peets MySQL 实例信息

## 生产环境 (prod)
| 实例ID | 实例名称 | 版本 |
|--------|----------|------|
| mysql-a1bf008763a8 | peets-prod-dolpin-mysql | MySQL 8.0 |
| mysql-4bd2df1a0c0c | peets-prod-pos-middle-mysql-n | MySQL 8.0 |

## UAT 环境
| 实例ID | 实例名称 | 版本 |
|--------|----------|------|
| mysql-be4d85571174 | peets-ora-uat-mysql | MySQL 8.0 |
""".strip()

    records = parse_instance_records(
        content,
        "/memories/agents/dba/peets-mysql-instances.md",
        normalize_credential_ref,
    )

    assert records == [
        {
            "memory_path": "/memories/agents/dba/peets-mysql-instances.md",
            "instance_id": "mysql-a1bf008763a8",
            "instance_name": "peets-prod-dolpin-mysql",
            "environment": "prod",
            "project_key": "peets",
        },
        {
            "memory_path": "/memories/agents/dba/peets-mysql-instances.md",
            "instance_id": "mysql-4bd2df1a0c0c",
            "instance_name": "peets-prod-pos-middle-mysql-n",
            "environment": "prod",
            "project_key": "peets",
        },
        {
            "memory_path": "/memories/agents/dba/peets-mysql-instances.md",
            "instance_id": "mysql-be4d85571174",
            "instance_name": "peets-ora-uat-mysql",
            "environment": "uat",
            "project_key": "peets",
        },
    ]


def test_infer_environment_supports_legacy_mojibake_headings():
    assert infer_environment(f"## {to_mojibake('生产环境')}") == "prod"
    assert infer_environment(f"## {to_mojibake('测试环境')}") == "dev"
    assert infer_environment(f"## {to_mojibake('预发环境')}") == "staging"


def test_parse_instance_records_supports_legacy_mojibake_tables():
    content = "\n".join(
        [
            f"# {to_mojibake('示例')}",
            "",
            f"## {to_mojibake('生产环境')}",
            f"| {to_mojibake('实例ID')} | {to_mojibake('实例名称')} | {to_mojibake('区域')} |",
            "|--------|------------|------|",
            "| mysql-legacy | peets-prod-legacy-mysql | cn-shanghai |",
        ]
    )

    records = parse_instance_records(
        content,
        "/memories/agents/dba/peets-mysql-instances.md",
        normalize_credential_ref,
    )

    assert records == [
        {
            "memory_path": "/memories/agents/dba/peets-mysql-instances.md",
            "instance_id": "mysql-legacy",
            "instance_name": "peets-prod-legacy-mysql",
            "region": "cn-shanghai",
            "environment": "prod",
            "project_key": "peets",
        }
    ]


def test_select_top_candidates_keeps_all_tied_matches():
    keywords = extract_keywords("我要进行peets的mysql巡检")
    assert keywords == ["peets", "mysql"]

    candidates = [
        {"instance_id": f"mysql-{index}", "score": 30}
        for index in range(6)
    ] + [{"instance_id": "mysql-low", "score": 25}]

    selected = select_top_candidates(candidates)

    assert [item["instance_id"] for item in selected] == [
        "mysql-0",
        "mysql-1",
        "mysql-2",
        "mysql-3",
        "mysql-4",
        "mysql-5",
    ]


def test_resolve_candidate_selection_preserves_all_matches_for_dialog():
    candidates = [
        {"instance_id": f"mysql-top-{index}", "score": 30}
        for index in range(3)
    ] + [
        {"instance_id": f"mysql-other-{index}", "score": 25}
        for index in range(2)
    ]

    resolution = resolve_candidate_selection(candidates)

    assert resolution["ambiguous"] is True
    assert [item["instance_id"] for item in resolution["top_candidates"]] == [
        "mysql-top-0",
        "mysql-top-1",
        "mysql-top-2",
    ]
    assert [item["instance_id"] for item in resolution["display_candidates"]] == [
        "mysql-top-0",
        "mysql-top-1",
        "mysql-top-2",
        "mysql-other-0",
        "mysql-other-1",
    ]
