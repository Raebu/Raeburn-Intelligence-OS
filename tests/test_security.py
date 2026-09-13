import pytest
from fastapi import HTTPException

from intelligence_os.config import get_settings
from intelligence_os.security import validate_operator_key


def test_development_without_key_allows_operator_actions():
    settings = get_settings()
    original_environment = settings.environment
    original_key = settings.api_key
    try:
        settings.environment = "development"
        settings.api_key = None
        validate_operator_key(None)
    finally:
        settings.environment = original_environment
        settings.api_key = original_key


def test_production_without_key_fails_closed():
    settings = get_settings()
    original_environment = settings.environment
    original_key = settings.api_key
    try:
        settings.environment = "production"
        settings.api_key = None
        with pytest.raises(HTTPException) as exc:
            validate_operator_key(None)
        assert exc.value.status_code == 503
    finally:
        settings.environment = original_environment
        settings.api_key = original_key


def test_configured_key_requires_exact_match():
    settings = get_settings()
    original_environment = settings.environment
    original_key = settings.api_key
    try:
        settings.environment = "production"
        settings.api_key = "expected-secret"
        with pytest.raises(HTTPException) as exc:
            validate_operator_key("wrong-secret")
        assert exc.value.status_code == 401
        validate_operator_key("expected-secret")
    finally:
        settings.environment = original_environment
        settings.api_key = original_key
