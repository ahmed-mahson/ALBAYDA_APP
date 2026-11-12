import io
import json
import unittest
from unittest.mock import patch

import app
import case_records
from case_records import CaseRecordsError


def make_record():
    return {
        "رقم القضية": "1446/25",
        "نوع القضية": "مدنية",
        "المدعي": "أحمد",
        "المدعى عليه": "محمد",
        "برئاسة القاضي": "القاضي الأول",
        "موضوعها": "موضوع القضية",
        "حالة القضية": "منظورة",
        "الجلسة القادمة": "2026-12-01",
        "تاريخ ورودها": "2026-11-01",
        "المحكمة": "محكمة البيضاء",
        "المحافظة": "البيضاء",
    }


class ApplicationTests(unittest.TestCase):
    def request(self, path, method="GET", payload=None, environ_extra=None):
        body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
        environ = {
            "PATH_INFO": path,
            "REQUEST_METHOD": method,
            "CONTENT_LENGTH": str(len(body)) if method == "POST" else "0",
            "wsgi.input": io.BytesIO(body),
        }
        environ.update(environ_extra or {})
        captured = {}

        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)

        output = b"".join(app.application(environ, start_response))
        return captured, output

    def test_home_and_installable_manifest_are_served(self):
        response, body = self.request("/")
        self.assertEqual(response["status"], "200 OK")
        self.assertIn(b"dir=\"rtl\"", body)
        self.assertIn("قائمة الجلسات".encode(), body)
        self.assertNotIn("سجل جلسات القضية".encode(), body)
        self.assertNotIn("الأمناء الشرعيون".encode(), body)
        self.assertNotIn(b"case-sittings", body)
        self.assertNotIn(b"trustees", body)
        self.assertNotIn("الوارد والصادر".encode(), body)
        self.assertNotIn(b"in-out", body)
        self.assertIn(b'id="case-search-method"', body)
        self.assertIn(b'id="ad-case-type"', body)
        self.assertIn(b'id="lookup-ad-case"', body)
        self.assertIn("المدعي أو المدعى عليه".encode(), body)
        self.assertIn("«اليوم»".encode(), body)

        response, body = self.request("/manifest.webmanifest")
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(json.loads(body)["short_name"], "محكمة البيضاء")

    def test_transparent_logo_and_official_icons_are_served(self):
        response, logo = self.request("/assets/albayda-it-logo.png")
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(response["headers"]["Content-Type"], "image/png")
        self.assertEqual(logo[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(logo[25], 6)

        for path in ("/icons/icon-192.png", "/icons/icon-512.png"):
            response, icon = self.request(path)
            self.assertEqual(response["status"], "200 OK")
            self.assertEqual(response["headers"]["Content-Type"], "image/png")
            self.assertEqual(icon[:8], b"\x89PNG\r\n\x1a\n")

        response, _font = self.request("/assets/sultan-medium.ttf")
        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(response["headers"]["Content-Type"], "font/ttf")

    def test_status_does_not_expose_the_google_drive_token(self):
        with patch.dict("os.environ", {"GOOGLE_DRIVE_TOKEN": "private-drive-token"}):
            response, body = self.request("/api/status")

        self.assertEqual(response["status"], "200 OK")
        result = json.loads(body)
        self.assertTrue(result["source_configured"])
        self.assertFalse(result["authentication_required"])
        self.assertNotIn("private-drive-token", body.decode())

    def test_auth_protects_app_and_accepts_a_signed_login_cookie(self):
        auth_config = {
            "APP_REQUIRE_AUTH": "true",
            "APP_ACCESS_PASSWORD": "test-password",
            "APP_SESSION_SECRET": "test-session-secret",
        }
        with patch.dict("os.environ", auth_config):
            protected, _ = self.request("/")
            self.assertEqual(protected["status"], "303 See Other")

            login_page, login_html = self.request("/login")
            self.assertEqual(login_page["status"], "200 OK")
            self.assertIn(b'id="login-form"', login_html)

            logo, _ = self.request("/assets/albayda-it-logo.png")
            self.assertEqual(logo["status"], "200 OK")

            wrong, _ = self.request(
                "/api/login", "POST", {"password": "wrong"}
            )
            self.assertEqual(wrong["status"], "401 Unauthorized")

            login, _ = self.request(
                "/api/login",
                "POST",
                {"password": "test-password"},
                {"HTTP_X_FORWARDED_PROTO": "https"},
            )
            self.assertEqual(login["status"], "200 OK")
            cookie = login["headers"]["Set-Cookie"]
            self.assertIn("HttpOnly", cookie)
            self.assertIn("SameSite=Strict", cookie)
            self.assertIn("Secure", cookie)

            status, body = self.request(
                "/api/status",
                environ_extra={"HTTP_COOKIE": cookie.split(";", 1)[0]},
            )
        self.assertEqual(status["status"], "200 OK")
        self.assertTrue(json.loads(body)["source_configured"])

    def test_public_deployment_fails_closed_without_auth_secrets(self):
        with patch.dict(
            "os.environ",
            {
                "APP_REQUIRE_AUTH": "true",
                "APP_ACCESS_PASSWORD": "",
                "APP_SESSION_SECRET": "",
            },
        ):
            login, _ = self.request(
                "/api/login", "POST", {"password": "anything"}
            )
            protected, _ = self.request("/api/status")

        self.assertEqual(login["status"], "503 Service Unavailable")
        self.assertEqual(protected["status"], "401 Unauthorized")

    @patch.object(case_records, "load_case_records", return_value=[make_record()])
    def test_case_search_uses_the_google_drive_records(self, load_records):
        response, body = self.request(
            "/api/cases/search",
            "POST",
            {"query": "1446/25"},
        )

        self.assertEqual(response["status"], "200 OK")
        result = json.loads(body)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["المدعي"], "أحمد")
        load_records.assert_called_once_with()

    @patch.object(case_records, "load_case_records", return_value=[make_record()])
    def test_case_search_supports_name_and_csv_filters(self, load_records):
        response, body = self.request(
            "/api/cases/search",
            "POST",
            {
                "query": "أحمد",
                "method": "name",
                "case_type": "مدنيــــة",
                "judge": "القاضي الأول",
            },
        )

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(json.loads(body)["count"], 1)
        load_records.assert_called_once_with()

    @patch.object(
        case_records,
        "load_case_records",
        return_value=[make_record()],
    )
    def test_case_options_are_loaded_from_google_drive_records(self, load_records):
        response, body = self.request(
            "/api/cases/options", "POST", {"case_type": "مدنيــــة"}
        )

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(json.loads(body)["judges"], ["القاضي الأول"])
        self.assertEqual(json.loads(body)["case_types"], ["مدنيــــة"])
        load_records.assert_called_once_with()

    @patch.object(
        case_records,
        "load_case_records",
        side_effect=CaseRecordsError("رفض Google Drive الوصول إلى سجل القضايا."),
    )
    def test_case_search_reports_google_drive_access_errors(self, _load_records):
        response, body = self.request(
            "/api/cases/search", "POST", {"query": "1446/25"}
        )

        self.assertEqual(response["status"], "503 Service Unavailable")
        self.assertIn("Google Drive", json.loads(body)["error"])

    def test_removed_case_sittings_and_trustee_apis_return_not_found(self):
        for path in ("/api/cases/sittings", "/api/legal-trustees/search"):
            with self.subTest(path=path):
                response, _body = self.request(path, "POST", {})
                self.assertEqual(response["status"], "404 Not Found")

    @patch.object(case_records, "load_case_records", return_value=[make_record()])
    def test_case_report_uses_google_drive_case_data(self, _load_records):
        response, body = self.request(
            "/api/cases/report", "POST", {"case_number": "1446/25"}
        )

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(response["headers"]["Content-Type"], "application/pdf")
        self.assertTrue(body.startswith(b"%PDF-"))

    @patch.object(case_records, "load_case_records", return_value=[make_record()])
    def test_sessions_search_uses_google_drive_case_data(self, load_records):
        response, body = self.request(
            "/api/sessions/search",
            "POST",
            {
                "date": "2026-12-01",
                "judge": "القاضي الأول",
            },
        )

        self.assertEqual(response["status"], "200 OK")
        result = json.loads(body)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["رقم القضية"], "1446/25")
        load_records.assert_called_once_with()

    @patch.object(case_records, "load_case_records", return_value=[make_record()])
    def test_sessions_search_accepts_today_and_all_judges(self, load_records):
        with patch.object(app, "datetime") as mock_datetime:
            mock_datetime.now.return_value.date.return_value.isoformat.return_value = "2026-12-01"
            response, body = self.request(
                "/api/sessions/search", "POST", {"date": "اليوم", "judge": "all"}
            )

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(json.loads(body)["date"], "2026-12-01")
        self.assertEqual(json.loads(body)["count"], 1)
        load_records.assert_called_once_with()

    @patch.object(case_records, "load_case_records", return_value=[make_record()])
    def test_sessions_pdf_endpoint_uses_official_template(self, _load_records):
        response, body = self.request(
            "/api/sessions/pdf",
            "POST",
            {"date": "2026-12-01", "judge": "القاضي الأول"},
        )

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(response["headers"]["Content-Type"], "application/pdf")
        self.assertTrue(body.startswith(b"%PDF-"))

    def test_invalid_date_is_rejected(self):
        response, body = self.request(
            "/api/sessions/search", "POST", {"date": "tomorrow"}
        )

        self.assertEqual(response["status"], "400 Bad Request")
        self.assertIn("تاريخ الجلسة", json.loads(body)["error"])

    @patch.object(case_records, "load_case_records", return_value=[make_record()])
    def test_attendance_ad_uses_google_drive_case_and_official_template(self, load_records):
        response, body = self.request(
            "/api/attendance-ad",
            "POST",
            {
                "case_number": "1446/25",
                "session_date": "2026-12-01",
                "case_type": "مدنيــــة",
                "judge_filter": "القاضي الأول",
                "plaintiff": "المدعي المعدل",
                "defendant": "المدعى عليه المعدل",
                "judge": "القاضي المختص",
            },
        )

        self.assertEqual(response["status"], "200 OK")
        self.assertEqual(response["headers"]["Content-Type"], "application/pdf")
        self.assertTrue(body.startswith(b"%PDF-"))
        self.assertIn("filename*=UTF-8''", response["headers"]["Content-Disposition"])
        load_records.assert_called_once_with()

    @patch.object(
        case_records,
        "search_supreme_court_cases",
        return_value=[
            ("الطاعن/الملتمس", "أحمد"),
            ("المطعون ضده", "محمد"),
            ("نوع القضية", "طعن"),
            ("تاريخ الاستلام", "2026/01/01"),
            ("الرقم الخاص بخدمة الرسائل القصيرة", "123"),
            ("تاريخ الإرسال", "منظورة"),
        ],
    )
    def test_supreme_court_search_returns_result_rows(self, search):
        response, body = self.request(
            "/api/supreme-court/search",
            "POST",
            {"name": "أحمد", "case_type": "0", "authority": "0"},
        )

        self.assertEqual(response["status"], "200 OK")
        result = json.loads(body)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["results"][0]["الطاعن/الملتمس"], "أحمد")
        search.assert_called_once()

    def test_supreme_search_requires_a_query(self):
        response, body = self.request("/api/supreme-court/search", "POST", {})

        self.assertEqual(response["status"], "400 Bad Request")
        self.assertIn("أدخل اسم", json.loads(body)["error"])

    def test_paths_cannot_escape_the_web_directory(self):
        response, _body = self.request("/%2e%2e%2fapp.py")
        self.assertEqual(response["status"], "404 Not Found")


if __name__ == "__main__":
    unittest.main()
