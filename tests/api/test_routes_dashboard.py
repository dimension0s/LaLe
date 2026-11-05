class TestDashboard:
    def test_stats(self, client, test_doc_with_notes, auth_header):
        r = client.get("/api/dashboard/stats", headers=auth_header)
        data = r.json()["data"]
        assert data["files"] == 1
        assert data["notes"] == 2
        assert data["vocabulary"] == 0
        assert data["recycle"] == 0