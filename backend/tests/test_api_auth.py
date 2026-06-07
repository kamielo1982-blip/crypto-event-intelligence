from __future__ import annotations

import os
import tempfile
import unittest

try:
    from fastapi.testclient import TestClient
except ModuleNotFoundError:
    TestClient = None


@unittest.skipIf(TestClient is None, "FastAPI test dependencies are not installed")
class APIAuthSmokeTests(unittest.TestCase):
    def test_login_cookie_unlocks_protected_assets_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{tmpdir}/smoke.db"
            os.environ["ADMIN_USERNAME"] = "admin"
            os.environ["ADMIN_PASSWORD"] = "smoke-password"
            os.environ["SESSION_SECRET"] = "smoke-secret-with-enough-length-32"

            from app.main import app

            with TestClient(app) as client:
                blocked = client.get("/api/assets")
                self.assertEqual(blocked.status_code, 401)

                login = client.post("/api/auth/login", json={"username": "admin", "password": "smoke-password"})
                self.assertEqual(login.status_code, 200)

                assets = client.get("/api/assets")
                self.assertEqual(assets.status_code, 200)
                self.assertGreaterEqual(len(assets.json()), 10)

                overview = client.get("/api/assets/BTC/overview?window=30d")
                self.assertEqual(overview.status_code, 200)
                payload = overview.json()
                self.assertIn("price_candles", payload)
                self.assertIn("exchange_candles", payload)
                self.assertIn("kimchi_premium_series", payload)
                self.assertIn("kimchi_premium_latest", payload)
                self.assertIn("onchain_series", payload)
                self.assertIn("supply_series", payload)
                self.assertIn("news_impacts", payload)
                self.assertIn("factor_impacts", payload)
                self.assertIn("timeline_events", payload)

            from app.database import engine

            engine.dispose()


if __name__ == "__main__":
    unittest.main()
