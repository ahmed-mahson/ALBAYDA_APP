import io
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import court_source
from case_records import CaseRecordsError


def api_response(payload):
    return io.BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8"))


class OriginalCourtSourceTests(unittest.TestCase):
    def setUp(self):
        court_source._case_data_cache = None
        court_source._case_data_cache_expires_at = 0
        self.environment = patch.dict(
            "os.environ",
            {
                "COURT_API_BASE_URL": "https://court.example/Omana/JICWebService1.asmx",
                "COURT_API_KEY": "test-key-not-for-logs",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)

    @patch.object(court_source, "urlopen")
    def test_case_search_uses_original_getjson6_endpoint(self, urlopen):
        urlopen.return_value = api_response(
            {
                "results": [
                    {
                        "Fld_CaseHandlyNo": "1446/25",
                        "Fld_CaseMachineNo": "case-001",
                        "Fld_KindCaseType": "مدني",
                        "Fld_CaseCrimes": "مطالبة مالية",
                        "Fld_CaseNextSeatDate": "2026/12/01",
                        "Fld_EmployeeName1": "القاضي الأول",
                        "Fld_VictimFrom": "أحمد",
                        "Fld_VictimTo": "محمد",
                    },
                    {"Fld_CaseHandlyNo": "1446/26"},
                ]
            }
        )

        results = court_source.search_cases("1446/25")

        self.assertEqual(len(results), 1)
        record = results[0]
        self.assertEqual(record["رقم القضية"], "1446/25")
        self.assertEqual(record["الجلسة القادمة"], "2026-12-01")
        self.assertEqual(record["المدعي"], "أحمد")
        request = urlopen.call_args.args[0]
        parsed = urlsplit(request.full_url)
        self.assertEqual(parsed.path, "/Omana/JICWebService1.asmx/GetJson6")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "Yaho": ["test-key-not-for-logs"],
                "Fld_CaseHandlyNo": ["NULL"],
                "Fld_SideImpNo": ["NULL"],
                "Fld_PlaceCourtsNo": ["NULL"],
                "Fld_KindCaseNo": ["NULL"],
                "Fld_KindCasePrimeNo": ["NULL"],
            },
        )
        self.assertNotIn("test-key-not-for-logs", repr(results))

    @patch.object(court_source, "urlopen")
    def test_case_search_matches_party_names_and_bot_number_formats(self, urlopen):
        urlopen.return_value = api_response(
            [
                {
                    "Fld_CaseHandlyNo": "1446/25",
                    "Fld_KindCaseType": "مدنية",
                    "Fld_EmployeeName1": "القاضي الأول",
                    "Fld_VictimFrom": "أحمد صالح",
                    "Fld_VictimTo": "محمد",
                },
                {
                    "Fld_CaseHandlyNo": "1446/26",
                    "Fld_KindCaseType": "شخصية",
                    "Fld_EmployeeName1": "قاضي الأسرة",
                    "Fld_VictimFrom": "أحمد آخر",
                },
            ]
        )

        by_name = court_source.search_cases("صالح")
        by_reversed_number = court_source.search_cases("٢٥/١٤٤٦")
        filtered = court_source.search_cases(
            "أحمد", method="name", case_type="مدنيــــة", judge="القاضي الأول"
        )

        self.assertEqual([row["رقم القضية"] for row in by_name], ["1446/25"])
        self.assertEqual([row["رقم القضية"] for row in by_reversed_number], ["1446/25"])
        self.assertEqual([row["رقم القضية"] for row in filtered], ["1446/25"])
        urlopen.assert_called_once()

    @patch.object(court_source, "urlopen")
    def test_case_search_options_are_derived_from_original_service(self, urlopen):
        urlopen.return_value = api_response(
            [
                {
                    "Fld_CaseHandlyNo": "1446/25",
                    "Fld_KindCaseType": "مدنية",
                    "Fld_EmployeeName1": "القاضي الأول",
                },
                {
                    "Fld_CaseHandlyNo": "1446/26",
                    "Fld_KindCaseType": "شخصية",
                    "Fld_EmployeeName1": "قاضي الأسرة",
                },
            ]
        )

        all_options = court_source.get_case_search_options()
        civil_options = court_source.get_case_search_options("مدنيــــة")

        self.assertEqual(all_options["case_types"], ["مدنيــــة", "شخصيـــة"])
        self.assertEqual(civil_options["judges"], ["القاضي الأول"])
        urlopen.assert_called_once()

    @patch.object(court_source, "urlopen")
    def test_case_sittings_use_original_getjson7_endpoint(self, urlopen):
        urlopen.return_value = api_response(
            [
                {
                    "Fld_CaseHandlyNo": "1446/25",
                    "Fld_SeatNo": 2,
                    "Fld_SeatDate": "2026/12/01",
                    "Fld_EmployeeName5": "القاضي الأول",
                    "Fld_SitDecisson": "تأجيل",
                    "Fld_NextSeatDate": "2026/12/15",
                },
                {"Fld_CaseHandlyNo": "1446/26", "Fld_SeatNo": 3},
            ]
        )

        results = court_source.search_case_sittings("1446/25")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["تاريخ الجلسة"], "2026-12-01")
        self.assertEqual(results[0]["القاضي"], "القاضي الأول")
        self.assertEqual(results[0]["قرار الجلسة"], "تأجيل")
        parsed = urlsplit(urlopen.call_args.args[0].full_url)
        self.assertEqual(parsed.path, "/Omana/JICWebService1.asmx/GetJson7")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "Yaho": ["test-key-not-for-logs"],
                "Fld_CaseHandlyNo": ["1446/25"],
                "Fld_SideImpNo": ["NULL"],
                "Fld_PlaceCourtsNo": ["NULL"],
                "Fld_KindCaseNo": ["NULL"],
                "Fld_KindCasePrimeNo": ["NULL"],
            },
        )

    @patch.object(court_source, "urlopen")
    def test_case_sittings_match_reversed_number_from_original_service(self, urlopen):
        urlopen.side_effect = [
            api_response([]),
            api_response(
                [
                    {
                        "Fld_CaseHandlyNo": "25/1446",
                        "Fld_SeatNo": 2,
                        "Fld_SeatDate": "2026/12/01",
                    }
                ]
            ),
        ]

        results = court_source.search_case_sittings("١٤٤٦/٢٥")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["رقم القضية"], "25/1446")
        self.assertEqual(urlopen.call_count, 2)
        first_parameters = parse_qs(urlsplit(urlopen.call_args_list[0].args[0].full_url).query)
        second_parameters = parse_qs(urlsplit(urlopen.call_args_list[1].args[0].full_url).query)
        self.assertEqual(first_parameters["Fld_CaseHandlyNo"], ["1446/25"])
        self.assertEqual(second_parameters["Fld_CaseHandlyNo"], ["25/1446"])

    @patch.object(court_source, "urlopen")
    def test_legal_trustee_search_uses_original_getjson_endpoint(self, urlopen):
        urlopen.return_value = api_response(
            [
                {
                    "wdname": "أمين البيضاء",
                    "Fld_warant_No": 123,
                    "Fld_warant_date": "2020/01/02",
                    "Fld_AminStat": "فعال",
                    "Fld_SideName": "المحكمة",
                    "Fld_ProvincesName": "البيضاء",
                    "Fld_home_phone": "private",
                },
                {"wdname": "أمين آخر", "Fld_warant_No": 456},
            ]
        )

        results = court_source.search_legal_trustees("أمين البيضاء")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["رقم الترخيص"], "123")
        self.assertEqual(results[0]["تاريخ الترخيص"], "2020-01-02")
        self.assertNotIn("private", repr(results))
        parsed = urlsplit(urlopen.call_args.args[0].full_url)
        self.assertEqual(parsed.path, "/Omana/JICWebService1.asmx/GetJson")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "Yaho": ["test-key-not-for-logs"],
                "Fld_SideNo": ["NULL"],
                "Fld_PlaceNo": ["NULL"],
                "Fld_SideImpNo": ["NULL"],
                "Fld_AminStat": ["NULL"],
                "wdname": ["أمين البيضاء"],
                "Fld_warant_No": ["NULL"],
            },
        )

    @patch.object(court_source, "urlopen")
    def test_trustee_search_uses_license_number_when_query_is_numeric(self, urlopen):
        urlopen.return_value = api_response(
            [{"wdname": "أمين البيضاء", "Fld_warant_No": 123}]
        )

        results = court_source.search_legal_trustees("١٢٣")

        self.assertEqual(len(results), 1)
        parsed = urlsplit(urlopen.call_args.args[0].full_url)
        parameters = parse_qs(parsed.query)
        self.assertEqual(parameters["wdname"], ["NULL"])
        self.assertEqual(parameters["Fld_warant_No"], ["123"])

    @patch.object(court_source, "urlopen")
    def test_session_search_uses_original_getjson10_and_date_format(self, urlopen):
        urlopen.return_value = api_response(
            {
                "d": json.dumps(
                    [
                        {
                            "Fld_CaseHandlyNo": "1446/25",
                            "SittingDate": "2026/12/01",
                            "Fld_EmployeeName1": "القاضي الأول",
                        }
                    ],
                    ensure_ascii=False,
                )
            }
        )

        results = court_source.search_sessions("2026-12-01")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["رقم القضية"], "1446/25")
        self.assertEqual(results[0]["الجلسة القادمة"], "2026-12-01")
        request = urlopen.call_args.args[0]
        parsed = urlsplit(request.full_url)
        self.assertEqual(parsed.path, "/Omana/JICWebService1.asmx/GetJson10")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "Yaho": ["test-key-not-for-logs"],
                "Fld_SideImNo": ["NULL"],
                "Fld_PlaceCourtsNo": ["NULL"],
                "SittingDate": ["2026/12/01"],
            },
        )

    @patch.object(court_source, "urlopen")
    def test_bearer_token_is_sent_only_when_configured(self, urlopen):
        urlopen.return_value = api_response([])
        with patch.dict(
            "os.environ", {"COURT_API_BEARER_TOKEN": "session-token"}
        ):
            court_source.search_sessions("2026-12-01")
        self.assertEqual(
            urlopen.call_args.args[0].get_header("Authorization"),
            "Bearer session-token",
        )

    @patch.object(court_source, "urlopen")
    def test_missing_source_key_is_reported_without_network_request(self, urlopen):
        with patch.dict("os.environ", {"COURT_API_KEY": ""}):
            with self.assertRaisesRegex(CaseRecordsError, "COURT_API_KEY"):
                court_source.search_sessions("2026-12-01")
        urlopen.assert_not_called()

    def test_authenticated_deployment_rejects_insecure_court_endpoint(self):
        with patch.dict(
            "os.environ",
            {
                "APP_REQUIRE_AUTH": "true",
                "COURT_API_BASE_URL": "http://court.example/service",
            },
        ):
            with self.assertRaisesRegex(CaseRecordsError, "HTTPS"):
                court_source._api_url(court_source.SESSIONS_ROUTE, [])

    @patch.object(court_source, "urlopen")
    def test_rejects_non_json_source_response(self, urlopen):
        urlopen.return_value = io.BytesIO(b"<html>not json</html>")
        with self.assertRaisesRegex(CaseRecordsError, "JSON"):
            court_source.search_sessions("2026-12-01")

    def test_invalid_case_or_date_input_is_rejected(self):
        with self.assertRaises(ValueError):
            court_source.search_cases("")
        with self.assertRaises(ValueError):
            court_source.search_sessions("tomorrow")


if __name__ == "__main__":
    unittest.main()
