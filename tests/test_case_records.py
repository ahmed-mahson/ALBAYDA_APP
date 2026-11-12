import csv
import io
import os
import unittest
from email.message import Message
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

import case_records
from case_records import CaseRecordsError


def csv_download_response(content):
    response = io.BytesIO(content)
    response.headers = Message()
    response.headers["Content-Type"] = "text/csv"
    return response


def wrapped_csv_row():
    fields = [""] * 27
    fields[1] = "نوع القضية الأساسي"
    fields[8] = "برئاسة القاضي"
    fields[14] = "رقم القضية"
    fields[16] = "1446/24"
    fields[17] = "2026/12/01"
    fields[19] = "منظورة"
    fields[20] = "القاضي الأول"
    fields[21] = "محمد"
    fields[22] = "أحمد"
    fields[23] = "2026/11/01"
    fields[24] = "مطالبة مالية"
    fields[25] = "مدنية"
    fields[26] = "1446/25"

    inner = io.StringIO()
    csv.writer(inner, lineterminator="").writerow(fields)
    outer = io.StringIO()
    csv.writer(outer).writerow([inner.getvalue()])
    return outer.getvalue().encode("utf-8")


class CaseRecordsTests(unittest.TestCase):
    def test_parses_drive_csv_case_fields(self):
        records = case_records._parse_case_records(wrapped_csv_row())

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["رقم القضية"], "1446/25")
        self.assertEqual(records[0]["المدعي"], "أحمد")
        self.assertEqual(records[0]["الجلسة القادمة"], "2026/12/01")

    def test_search_supports_arabic_reversed_case_numbers_and_sessions(self):
        records = case_records._parse_case_records(wrapped_csv_row())

        by_number = case_records.search_case_records(
            records, "٢٥/١٤٤٦", "number"
        )
        sessions = case_records.search_sessions_by_date(
            records, "٢٠٢٦-١٢-٠١"
        )

        self.assertEqual([row["رقم القضية"] for row in by_number], ["1446/25"])
        self.assertEqual([row["رقم القضية"] for row in sessions], ["1446/25"])

    @patch.dict(os.environ, {"GOOGLE_DRIVE_TOKEN": "test-drive-token"})
    @patch.object(case_records, "urlopen")
    def test_private_drive_download_uses_bearer_header(self, urlopen):
        content = wrapped_csv_row()
        urlopen.return_value = csv_download_response(content)

        self.assertEqual(case_records._download_case_csv(), content)

        request = urlopen.call_args.args[0]
        parsed = urlsplit(request.full_url)
        self.assertEqual(
            parsed.path,
            f"/drive/v3/files/{case_records.DEFAULT_GOOGLE_DRIVE_FILE_ID}",
        )
        self.assertEqual(parse_qs(parsed.query), {"alt": ["media"]})
        self.assertEqual(
            request.get_header("Authorization"),
            "Bearer test-drive-token",
        )
        self.assertNotIn("test-drive-token", request.full_url)

    @patch.dict(os.environ, {"GOOGLE_DRIVE_TOKEN": ""})
    @patch.object(case_records, "urlopen")
    def test_public_drive_download_uses_link_share_endpoint(self, urlopen):
        content = wrapped_csv_row()
        urlopen.return_value = csv_download_response(content)

        self.assertEqual(case_records._download_case_csv(), content)

        request = urlopen.call_args.args[0]
        parameters = parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(parameters["id"], [case_records.DEFAULT_GOOGLE_DRIVE_FILE_ID])
        self.assertNotIn("Authorization", request.headers)

    @patch.dict(os.environ, {"GOOGLE_DRIVE_TOKEN": ""})
    @patch.object(
        case_records,
        "urlopen",
        side_effect=HTTPError(
            "https://drive.google.com/uc",
            403,
            "Forbidden",
            Message(),
            io.BytesIO(),
        ),
    )
    def test_drive_permission_errors_explain_access_setup(self, _urlopen):
        with self.assertRaisesRegex(CaseRecordsError, "GOOGLE_DRIVE_TOKEN"):
            case_records._download_case_csv()
