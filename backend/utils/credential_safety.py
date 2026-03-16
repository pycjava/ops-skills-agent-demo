import re


SENSITIVE_CREDENTIAL_PATTERNS = [
    re.compile(r"--ak\s+\S{6,}", re.IGNORECASE),
    re.compile(r"--sk\s+\S{6,}", re.IGNORECASE),
    re.compile(r"(?:^|\s)(?:ak|access[\s_-]*key)\s*[:=：]\s*\S{6,}", re.IGNORECASE),
    re.compile(r"(?:^|\s)(?:sk|secret[\s_-]*key)\s*[:=：]\s*\S{6,}", re.IGNORECASE),
]


def contains_plaintext_cloud_credentials(content: str) -> bool:
    text = str(content or "")
    matches = sum(1 for pattern in SENSITIVE_CREDENTIAL_PATTERNS if pattern.search(text))
    return matches >= 2


def cloud_credentials_rejection_message() -> str:
    return (
        "检测到你正在消息中直接提交云账号凭证。为避免 AK/SK 进入聊天记录和模型上下文，"
        "请改用 `credential_ref`，并把真实密钥配置到 `backend/.env` 中的 "
        "`VOLC_CREDENTIAL_<REF>_AK` / `VOLC_CREDENTIAL_<REF>_SK`。"
    )
