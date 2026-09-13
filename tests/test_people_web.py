from intelligence_os.people_web import extract_decision_makers


def test_extract_decision_makers_from_public_team_copy():
    html = """
    <html><body>
      <div>Jane Smith — Chief Technology Officer</div>
      <div>Chief Executive Officer: David Jones</div>
      <p>Sarah Patel is the Head of Transformation</p>
    </body></html>
    """
    people = extract_decision_makers(html)
    names = {row["name"] for row in people}
    families = {row["role_family"] for row in people}
    assert "Jane Smith" in names
    assert "David Jones" in names
    assert "Sarah Patel" in names
    assert "technology" in families
    assert "executive" in families
    assert "transformation" in families
