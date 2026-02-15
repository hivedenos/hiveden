from hiveden.docker.dependencies import (
    evaluate_dependencies,
    normalize_dependency_names,
    parse_dependencies_label,
    serialize_dependencies_label,
)


def test_normalize_dependency_names_trims_and_deduplicates():
    names = [" postgres ", "redis", "postgres", "", "  ", "redis"]
    assert normalize_dependency_names(names) == ["postgres", "redis"]


def test_evaluate_dependencies_reports_missing_and_items():
    result = evaluate_dependencies(
        required=["postgres", "redis", "db"],
        existing={"postgres", "redis"},
    )

    assert result["all_satisfied"] is False
    assert result["missing"] == ["db"]
    assert result["items"] == [
        {"name": "postgres", "exists": True},
        {"name": "redis", "exists": True},
        {"name": "db", "exists": False},
    ]


def test_serialize_parse_dependencies_label_roundtrip():
    encoded = serialize_dependencies_label([" postgres ", "redis", "postgres"])
    assert encoded == "postgres,redis"
    assert parse_dependencies_label(encoded) == ["postgres", "redis"]


def test_evaluate_dependencies_empty_required_is_satisfied():
    result = evaluate_dependencies(required=[], existing={"postgres"})
    assert result["all_satisfied"] is True
    assert result["missing"] == []
    assert result["items"] == []
