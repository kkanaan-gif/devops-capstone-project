"""
Account API Service Test Suite

Test cases can be run with the following:
  nosetests -v --with-spec --spec-color
  coverage report -m
"""
import os
import logging
from unittest import TestCase
from tests.factories import AccountFactory
from service.common import status  # HTTP Status Codes
from service.models import db, Account, init_db
from service.routes import app
from service import talisman

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql://postgres:postgres@localhost:5432/postgres"
)

BASE_URL = "/accounts"


######################################################################
#  T E S T   C A S E S
######################################################################
class TestAccountService(TestCase):
    """Account Service Tests"""

    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        talisman.force_https = False
        app.config["DEBUG"] = False
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        """Runs once before test suite"""

    def setUp(self):
        """Runs before each test"""
        db.session.query(Account).delete()  # clean up the last tests
        db.session.commit()

        self.client = app.test_client()

    def tearDown(self):
        """Runs once after each test case"""
        db.session.remove()

    ######################################################################
    #  H E L P E R   M E T H O D S
    ######################################################################

    def _create_accounts(self, count):
        """Factory method to create accounts in bulk"""
        accounts = []
        for _ in range(count):
            account = AccountFactory()
            response = self.client.post(BASE_URL, json=account.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test Account",
            )
            new_account = response.get_json()
            account.id = new_account["id"]
            accounts.append(account)
        return accounts

    ######################################################################
    #  A C C O U N T   T E S T   C A S E S
    ######################################################################

    def test_index(self):
        """It should get 200_OK from the Home Page"""
        response = self.client.get("/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_health(self):
        """It should be healthy"""
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "OK")

    def test_create_account(self):
        """It should Create a new Account"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_account = response.get_json()
        self.assertEqual(new_account["name"], account.name)
        self.assertEqual(new_account["email"], account.email)
        self.assertEqual(new_account["address"], account.address)
        self.assertEqual(new_account["phone_number"], account.phone_number)
        self.assertEqual(new_account["date_joined"], str(account.date_joined))

    def test_bad_request(self):
        """It should not Create an Account when sending the wrong data"""
        response = self.client.post(BASE_URL, json={"name": "not enough data"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unsupported_media_type(self):
        """It should not Create an Account when sending the wrong media type"""
        account = AccountFactory()
        response = self.client.post(
            BASE_URL,
            json=account.serialize(),
            content_type="test/html"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    # ADD YOUR TEST CASES HERE ...

    def test_read_account(self):
        """It should READ an account by ID."""
        account = self._create_accounts(1)[0]
        response = self.client.get(f"{BASE_URL}/{account.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.get_json(), account.serialize())

    def test_account_not_found(self):
        """It should return 404 for an unknown account."""
        self.assertEqual(self.client.get(f"{BASE_URL}/99999").status_code, 404)

    def test_list_accounts(self):
        """It should LIST every account and support an empty catalog."""
        self.assertEqual(self.client.get(BASE_URL).get_json(), [])
        accounts = self._create_accounts(3)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual({a["id"] for a in response.get_json()}, {a.id for a in accounts})

    def test_update_account(self):
        """It should UPDATE an account and persist all fields."""
        account = self._create_accounts(1)[0]
        data = account.serialize()
        data.update(name="Updated Customer", email="updated@example.com", address="100 New Street",
                    phone_number="555-0102", date_joined="2026-11-11")
        response = self.client.put(f"{BASE_URL}/{account.id}", json=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), data)
        self.assertEqual(self.client.get(f"{BASE_URL}/{account.id}").get_json(), data)

    def test_update_missing_account(self):
        """It should reject UPDATE for an unknown ID."""
        response = self.client.put(f"{BASE_URL}/99999", json=AccountFactory().serialize())
        self.assertEqual(response.status_code, 404)

    def test_update_invalid_account(self):
        """It should reject UPDATE with missing required data."""
        account = self._create_accounts(1)[0]
        self.assertEqual(self.client.put(f"{BASE_URL}/{account.id}", json={}).status_code, 400)
        self.assertEqual(self.client.put(f"{BASE_URL}/{account.id}", data="bad").status_code, 415)

    def test_delete_account(self):
        """It should DELETE the selected account without deleting others."""
        account, other = self._create_accounts(2)
        response = self.client.delete(f"{BASE_URL}/{account.id}")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.data, b"")
        self.assertEqual(self.client.get(f"{BASE_URL}/{account.id}").status_code, 404)
        self.assertEqual(self.client.get(f"{BASE_URL}/{other.id}").status_code, 200)
        self.assertEqual(self.client.delete(f"{BASE_URL}/{account.id}").status_code, 204)

    def test_create_location(self):
        """It should return a Location that retrieves the created account."""
        response = self.client.post(BASE_URL, json=AccountFactory().serialize())
        found = self.client.get(response.headers["Location"])
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.get_json(), response.get_json())

    def test_security_headers(self):
        """It should apply Talisman security headers."""
        response = self.client.get("/")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "SAMEORIGIN")
        self.assertIn("default-src", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["Referrer-Policy"], "strict-origin-when-cross-origin")

    def test_cors(self):
        """It should allow cross-origin API calls and preflight requests."""
        origin = "https://example.com"
        response = self.client.get(BASE_URL, headers={"Origin": origin})
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], origin)
        response = self.client.options(BASE_URL, headers={"Origin": origin,
            "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "Content-Type"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("POST", response.headers["Access-Control-Allow-Methods"])
        self.assertIn("Content-Type", response.headers["Access-Control-Allow-Headers"])

    def test_method_not_allowed(self):
        """It should report unsupported methods."""
        self.assertEqual(self.client.patch(BASE_URL).status_code, 405)

    def test_unexpected_server_error(self):
        """It should return a JSON 500 response for an unexpected database failure."""
        from unittest.mock import patch
        previous = app.config.get("PROPAGATE_EXCEPTIONS")
        app.config["PROPAGATE_EXCEPTIONS"] = False
        try:
            with patch("service.routes.Account.all", side_effect=RuntimeError("Database unavailable")):
                response = self.client.get(BASE_URL)
            self.assertEqual(response.status_code, 500)
            self.assertEqual(response.get_json()["error"], "Internal Server Error")
        finally:
            app.config["PROPAGATE_EXCEPTIONS"] = previous
