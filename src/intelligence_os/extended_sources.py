from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtendedSource:
    id: str
    name: str
    category: str
    jurisdiction: str | None
    canonical_url: str
    purpose: str
    ingestion: str
    trust: str = "authoritative_or_primary"
    notes: str | None = None


EXTENDED_SOURCES = [
    ExtendedSource("un-comtrade", "UN Comtrade", "trade", None, "https://comtradeplus.un.org/", "import/export flows, supply-chain exposure, market-entry and sector-demand signals", "api"),
    ExtendedSource("wto-data", "WTO Statistics", "trade", None, "https://stats.wto.org/", "international trade and market-access context", "dataset_specific"),
    ExtendedSource("sec-edgar", "SEC EDGAR", "filings", "US", "https://www.sec.gov/edgar/sec-api-documentation", "US issuer filings, risk factors, capex, acquisitions, restructuring and management commentary", "api"),
    ExtendedSource("epo-ops", "European Patent Office Open Patent Services", "patents", None, "https://www.epo.org/en/searching-for-patents/data/web-services/ops", "patent activity and technology-investment signals", "api_registration_may_be_required"),
    ExtendedSource("wipo-patentscope", "WIPO PATENTSCOPE", "patents", None, "https://patentscope.wipo.int/", "international patent and technology activity", "source_specific"),
    ExtendedSource("uspto-open-data", "USPTO Open Data", "patents", "US", "https://data.uspto.gov/", "US patent activity and innovation signals", "api_or_download"),
    ExtendedSource("ukri-gtr", "UKRI Gateway to Research", "grants", "GB", "https://gtr.ukri.org/", "UK research grants, organisations and innovation relationships", "api_or_download"),
    ExtendedSource("innovate-uk", "Innovate UK funded projects", "grants", "GB", "https://www.ukri.org/what-we-do/what-we-have-funded/", "innovation funding and emerging-technology investment", "dataset_specific"),
    ExtendedSource("horizon-europe", "EU Funding & Tenders / Horizon Europe", "grants", "EU", "https://ec.europa.eu/info/funding-tenders/opportunities/portal/", "European innovation awards, collaborations and expansion signals", "dataset_specific"),
    ExtendedSource("planning-data", "Planning Data", "planning", "GB", "https://www.planning.data.gov.uk/", "development, land and physical-expansion signals", "api_or_download"),
    ExtendedSource("national-grid-eso", "National Energy System Operator data", "energy", "GB", "https://www.neso.energy/data-portal", "electricity demand, capacity and infrastructure context", "api_or_download"),
    ExtendedSource("fca-enforcement", "FCA enforcement and notices", "regulatory", "GB", "https://www.fca.org.uk/news/search-results?category=press%20releases", "financial-services enforcement, remediation and compliance signals", "public_feed_or_page"),
    ExtendedSource("ico-enforcement", "ICO enforcement", "regulatory", "GB", "https://ico.org.uk/action-weve-taken/enforcement/", "privacy/data-protection enforcement and remediation signals", "public_page"),
    ExtendedSource("cma-cases", "Competition and Markets Authority cases", "regulatory", "GB", "https://www.gov.uk/cma-cases", "competition, merger and market-intervention signals", "public_dataset_or_page"),
    ExtendedSource("hse-enforcement", "HSE enforcement", "regulatory", "GB", "https://resources.hse.gov.uk/notices/", "health-and-safety enforcement and operational-risk signals", "public_search"),
    ExtendedSource("environment-agency", "Environment Agency public registers", "regulatory", "GB", "https://environment.data.gov.uk/public-register/view/index", "environmental compliance and operational-risk signals", "public_register"),
    ExtendedSource("gazette", "The Gazette", "insolvency_notices", "GB", "https://www.thegazette.co.uk/", "insolvency, restructuring, creditor and court-related public notices", "feed_or_search"),
    ExtendedSource("charity-commission", "Charity Commission register", "organisations", "GB", "https://register-of-charities.charitycommission.gov.uk/", "charity entity universe, trustees and financial context", "api_or_download"),
    ExtendedSource("uk-public-bodies", "UK public bodies and organisation registers", "organisations", "GB", "https://www.gov.uk/government/organisations", "public-sector buyer and organisation universe", "catalogue"),
    ExtendedSource("certificate-transparency", "Certificate Transparency logs", "internet_infrastructure", None, "https://certificate.transparency.dev/", "domain/subdomain emergence, migrations, acquisitions and product-launch hints", "public_logs"),
    ExtendedSource("rdap", "RDAP domain registration data", "internet_infrastructure", None, "https://data.iana.org/rdap/", "domain registration and infrastructure context", "api"),
    ExtendedSource("find-a-tender-pipeline", "Find a Tender planning and prior-information notices", "procurement_pipeline", "GB", "https://www.gov.uk/find-tender", "future buyer intent and 3-12 month procurement pipeline", "existing_api_stage_filter"),
    ExtendedSource("contracts-finder-pipeline", "Contracts Finder early engagement and future opportunity notices", "procurement_pipeline", "GB", "https://www.gov.uk/contracts-finder", "early buyer intent and future procurement opportunities", "existing_api_stage_filter"),
    ExtendedSource("govuk-news", "GOV.UK organisation news and announcements", "news", "GB", "https://www.gov.uk/search/news-and-communications", "sector-specific official announcements and regulatory change", "public_feed_or_search"),
    ExtendedSource("london-stock-exchange-rns", "Regulatory News Service / issuer announcements", "news", "GB", "https://www.londonstockexchange.com/news", "listed-company strategic events and market announcements", "public_page_terms_review"),
    ExtendedSource("maritime-and-coastguard", "UK maritime statistics and data", "shipping", "GB", "https://www.gov.uk/government/collections/maritime-and-shipping-statistics", "shipping, port and logistics-flow context", "download"),
    ExtendedSource("uk-port-freight", "UK port freight statistics", "shipping", "GB", "https://www.gov.uk/government/collections/maritime-and-shipping-statistics", "port throughput and supply-chain demand", "download"),
    ExtendedSource("land-registry-ppd", "HM Land Registry Price Paid Data", "property", "GB", "https://www.gov.uk/government/collections/price-paid-data", "property transactions, relocation and expansion context", "download"),
    ExtendedSource("land-registry-uk-companies", "HM Land Registry UK companies ownership data", "property", "GB", "https://use-land-property-data.service.gov.uk/", "company property ownership and physical-footprint relationships", "download_terms_review"),
    ExtendedSource("opencorporates", "OpenCorporates", "global_entities", None, "https://opencorporates.com/", "global company, subsidiary, parent and jurisdiction relationship resolution", "api_terms_and_licence_review"),
    ExtendedSource("firstdata-catalogue", "FirstData-style authoritative public source catalogue", "dataset_catalogue", None, "https://github.com/awesomedata/awesome-public-datasets/issues/493", "discovery of authoritative government and international datasets", "discovery_only", trust="discovery_only", notes="Never treat catalogue inclusion as permission or source truth; validate provenance, licence, freshness and access before promotion."),
]


def extended_sources() -> list[ExtendedSource]:
    return EXTENDED_SOURCES


def extended_source(source_id: str) -> ExtendedSource | None:
    return next((source for source in EXTENDED_SOURCES if source.id == source_id), None)
