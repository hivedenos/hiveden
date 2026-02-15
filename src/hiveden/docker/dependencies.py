from typing import Iterable, List, Sequence


DEPENDENCIES_LABEL_KEY = "hiveden.dependencies"


def normalize_dependency_names(names: Sequence[str] | None) -> List[str]:
    """Normalize dependency names by trimming and de-duplicating."""
    if not names:
        return []

    normalized = []
    seen = set()
    for name in names:
        value = (name or "").strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def evaluate_dependencies(required: Sequence[str], existing: Iterable[str]) -> dict:
    """Evaluate dependency existence and return a stable payload shape."""
    existing_set = set(existing)
    items = []
    missing = []

    for name in normalize_dependency_names(required):
        exists = name in existing_set
        items.append({"name": name, "exists": exists})
        if not exists:
            missing.append(name)

    return {
        "all_satisfied": len(missing) == 0,
        "missing": missing,
        "items": items,
    }


def serialize_dependencies_label(names: Sequence[str] | None) -> str:
    """Serialize normalized dependencies to label value."""
    return ",".join(normalize_dependency_names(names))


def parse_dependencies_label(value: str | None) -> List[str]:
    """Parse dependency label value into normalized dependency names."""
    if not value:
        return []
    return normalize_dependency_names(value.split(","))
