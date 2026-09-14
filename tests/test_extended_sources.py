from intelligence_os.extended_context import EXTENDED_CONTEXT_CAPABILITIES
from intelligence_os.extended_sources import extended_source, extended_sources


def test_all_requested_extended_source_categories_are_registered():
    ids = {source.id for source in extended_sources()}
    expected = {
        "un-comtrade", "wto-data", "sec-edgar", "epo-ops", "wipo-patentscope",
        "uspto-open-data", "ukri-gtr", "innovate-uk", "horizon-europe",
        "planning-data", "national-grid-eso", "fca-enforcement", "ico-enforcement",
        "cma-cases", "hse-enforcement", "environment-agency", "gazette",
        "charity-commission", "uk-public-bodies", "certificate-transparency", "rdap",
        "find-a-tender-pipeline", "contracts-finder-pipeline", "govuk-news",
        "london-stock-exchange-rns", "maritime-and-coastguard", "uk-port-freight",
        "land-registry-ppd", "land-registry-uk-companies", "opencorporates",
        "firstdata-catalogue",
    }
    assert expected <= ids
    assert expected <= set(EXTENDED_CONTEXT_CAPABILITIES)


def test_discovery_catalogue_is_not_trusted_as_source_truth():
    source = extended_source("firstdata-catalogue")
    assert source is not None
    assert source.trust == "discovery_only"
    assert source.ingestion == "discovery_only"


def test_terms_gated_sources_are_not_presented_as_unrestricted_ingestion():
    assert extended_source("opencorporates").ingestion == "api_terms_and_licence_review"
    assert extended_source("land-registry-uk-companies").ingestion == "download_terms_review"
