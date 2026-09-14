from intelligence_os.procurement import (
    _company_number_from_supplier,
    _normalise_name,
    normalize_release,
)


def test_normalize_release_extracts_supplier_and_values():
    release = {
        "ocid": "ocds-test-1",
        "id": "release-1",
        "date": "2026-09-13T12:00:00Z",
        "tag": ["award"],
        "buyer": {"name": "Example Council"},
        "tender": {
            "title": "Automation platform",
            "description": "Process automation services",
            "value": {"amount": 500000, "currency": "GBP"},
        },
        "awards": [
            {
                "value": {"amount": 450000, "currency": "GBP"},
                "suppliers": [
                    {"name": "Example Supplier Ltd", "identifier": {"id": "01234567"}}
                ],
            }
        ],
    }
    row = normalize_release(release, "find-a-tender")
    assert row["ocid"] == "ocds-test-1"
    assert row["title"] == "Automation platform"
    assert row["buyer"]["name"] == "Example Council"
    assert row["tender_value"]["amount"] == 500000
    assert row["award_value"]["amount"] == 450000
    assert row["suppliers"][0]["name"] == "Example Supplier Ltd"


def test_supplier_company_number_can_seed_verified_company():
    assert _company_number_from_supplier({"identifier": {"id": "01234567"}}) == "01234567"
    assert _company_number_from_supplier({"identifier": {"id": "SC123456"}}) == "SC123456"
    assert _company_number_from_supplier({"identifier": {"id": "not a company number"}}) is None


def test_supplier_company_number_supports_ocds_companies_house_scheme():
    supplier = {
        "identifier": {"scheme": "GB-COH", "id": "12345678"},
        "additionalIdentifiers": [{"scheme": "VAT", "id": "GB123456789"}],
    }
    assert _company_number_from_supplier(supplier) == "12345678"


def test_supplier_company_number_checks_additional_identifiers():
    supplier = {
        "identifier": {"scheme": "GB-PPON", "id": "ABCD-1234-EFGH"},
        "additionalIdentifiers": [{"scheme": "GB-COH", "id": "SC123456"}],
    }
    assert _company_number_from_supplier(supplier) == "SC123456"


def test_company_name_normalisation_is_conservative():
    assert _normalise_name("Example & Partners Limited") == "EXAMPLE AND PARTNERS"
    assert _normalise_name("Example & Partners Ltd") == "EXAMPLE AND PARTNERS"
