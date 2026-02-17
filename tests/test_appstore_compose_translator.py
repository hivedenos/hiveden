from hiveden.appstore.compose_translator import (
    ComposeTranslationError,
    parse_compose_yaml,
    translate_compose_services,
)


def test_translate_compose_services_maps_dependencies_and_labels():
    compose = parse_compose_yaml(
        """
services:
  db:
    image: postgres:16
    volumes:
      - db-data:/var/lib/postgresql/data
  web:
    image: nginx:latest
    depends_on:
      - db
    ports:
      - "8080:80"
"""
    )

    services = translate_compose_services("demo-app", compose)
    by_name = {item["name"]: item for item in services}

    assert "demo-app-db" in by_name
    assert "demo-app-web" in by_name
    assert by_name["demo-app-web"]["dependencies"] == ["demo-app-db"]
    assert by_name["demo-app-web"]["labels"]["hiveden.app.id"] == "demo-app"


def test_translate_compose_services_rejects_unsupported_keys():
    compose = parse_compose_yaml(
        """
services:
  api:
    image: python:3.12
    build: .
"""
    )

    try:
        translate_compose_services("demo", compose)
        assert False, "expected ComposeTranslationError"
    except ComposeTranslationError as exc:
        assert "unsupported keys" in str(exc)

