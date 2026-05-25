import unittest

from app.operations.sql_executor import _raise_hana_http_error


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


class HanaSqlExecutorErrorTest(unittest.TestCase):
    def test_403_invalid_number_is_reported_as_generated_sql_error(self):
        response = FakeResponse(
            403,
            {
                "status": 403,
                "message": "invalid number: exception 71000339: SQL Error",
            },
        )

        with self.assertRaisesRegex(ValueError, "generated SELECT query"):
            _raise_hana_http_error(response)

    def test_plain_403_is_still_reported_as_credentials_or_access_error(self):
        response = FakeResponse(403, {"status": 403, "message": "Forbidden"})

        with self.assertRaisesRegex(ValueError, "403 Forbidden"):
            _raise_hana_http_error(response)


if __name__ == "__main__":
    unittest.main()
