from intelligence_os.accounts import extract_ixbrl_metrics


def test_extract_ixbrl_metrics_reads_common_public_account_facts():
    content = """
    <html><body>
      <ix:nonFraction name="uk-gaap:TurnoverRevenue">1,250,000</ix:nonFraction>
      <ix:nonFraction name="uk-gaap:CashBankOnHand">£240,000</ix:nonFraction>
      <ix:nonFraction name="uk-gaap:NetAssetsLiabilities">850,000</ix:nonFraction>
      <ix:nonFraction name="uk-gaap:AverageNumberEmployeesDuringPeriod">42</ix:nonFraction>
    </body></html>
    """
    metrics = extract_ixbrl_metrics(content)
    assert metrics["turnover"] == 1_250_000
    assert metrics["cash"] == 240_000
    assert metrics["net_assets"] == 850_000
    assert metrics["employees"] == 42


def test_extract_ixbrl_metrics_does_not_invent_missing_values():
    metrics = extract_ixbrl_metrics("<html><body>No financial facts</body></html>")
    assert metrics == {}
