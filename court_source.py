import json
import logging
import os
import re
import threading
import time
import unicodedata
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from case_records import (
    CASE_TYPE_SOURCE_BY_DISPLAY_NAME,
    CaseRecordsError,
    available_case_types,
    case_type_matches,
    normalize_judge_name,
    search_case_records,
)


load_dotenv()
LOGGER = logging.getLogger("albayda_court.source")
DEFAULT_COURT_API_BASE_URL = (
    "http://82.114.183.44:8090/Omana/JICWebService1.asmx"
)
COURT_API_MAX_RESPONSE_BYTES = 20 * 1024 * 1024
COURT_API_TIMEOUT_SECONDS = 15
COURT_API_ATTEMPTS = 2
CASE_DATA_CACHE_SECONDS = 300
CASE_DATA_ROUTE = "/GetJson6"
CASE_SITTINGS_ROUTE = "/GetJson7"
LEGAL_TRUSTEES_ROUTE = "/GetJson"
SESSIONS_ROUTE = "/GetJson10"
_case_data_cache = None
_case_data_cache_expires_at = 0
_case_data_cache_lock = threading.Lock()


def _api_url(route, parameters):
    base_url = os.getenv(
        "COURT_API_BASE_URL", DEFAULT_COURT_API_BASE_URL
    ).strip().rstrip("/")
    if (
        os.getenv("APP_REQUIRE_AUTH", "").strip().casefold()
        in {"1", "true", "yes", "on"}
        and not base_url.casefold().startswith("https://")
    ):
        raise CaseRecordsError(
            "يتطلب نشر التطبيق مع تسجيل الدخول عنوان خدمة محكمة يعمل عبر HTTPS."
        )
    key = os.getenv("COURT_API_KEY", "").strip()
    if not base_url:
        raise CaseRecordsError("لم يتم إعداد عنوان خدمة بيانات المحكمة.")
    if not key:
        raise CaseRecordsError(
            "لم يتم إعداد COURT_API_KEY لخدمة بيانات التطبيق الأصلي."
        )
    parts = urlsplit(base_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise CaseRecordsError("عنوان خدمة بيانات المحكمة غير صالح.")
    params = [("Yaho", key), *parameters]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path + route, urlencode(params), "")
    )


def _request_json(route, parameters):
    url = _api_url(route, parameters)
    headers = {
        "Accept": "application/json",
        "User-Agent": "albayda_court/1.0",
    }
    bearer_token = os.getenv("COURT_API_BEARER_TOKEN", "").strip()
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = Request(url, headers=headers, method="GET")
    response_body = None
    for attempt in range(COURT_API_ATTEMPTS):
        try:
            with urlopen(request, timeout=COURT_API_TIMEOUT_SECONDS) as response:
                status = getattr(response, "status", 200)
                response_body = response.read(COURT_API_MAX_RESPONSE_BYTES + 1)
            if status < 200 or status >= 300:
                raise CaseRecordsError(
                    f"أعادت خدمة بيانات المحكمة رمز استجابة HTTP {status}."
                )
            break
        except CaseRecordsError:
            raise
        except HTTPError as exc:
            if exc.code < 500 or attempt + 1 >= COURT_API_ATTEMPTS:
                LOGGER.warning("Court data API returned HTTP %s.", exc.code)
                raise CaseRecordsError(
                    f"أعادت خدمة بيانات المحكمة رمز استجابة HTTP {exc.code}."
                ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            if attempt + 1 >= COURT_API_ATTEMPTS:
                LOGGER.warning(
                    "Court data API is unreachable after retries (%s).",
                    type(exc).__name__,
                )
                raise CaseRecordsError(
                    "تعذر الاتصال بخدمة بيانات التطبيق الأصلي. "
                    "تحقق من الشبكة وإعدادات الخادم."
                ) from exc
        if attempt + 1 < COURT_API_ATTEMPTS:
            time.sleep(0.5)
    if response_body is None:
        raise CaseRecordsError("لم تُرجع خدمة بيانات المحكمة استجابة.")
    if len(response_body) > COURT_API_MAX_RESPONSE_BYTES:
        raise CaseRecordsError("تجاوز رد خدمة بيانات المحكمة الحد المسموح.")
    try:
        decoded = response_body.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded = response_body.decode("cp1256")
        except UnicodeDecodeError as exc:
            raise CaseRecordsError(
                "تعذر قراءة ترميز استجابة خدمة بيانات المحكمة."
            ) from exc
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise CaseRecordsError(
            "لم تُرجع خدمة بيانات المحكمة بيانات JSON صالحة."
        ) from exc
    return _unwrap_json(payload)


def _unwrap_json(payload):
    for _ in range(3):
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                return payload
        elif isinstance(payload, dict):
            for key in ("d", "results", "data", "Data", "Result", "value"):
                if key in payload:
                    payload = payload[key]
                    break
            else:
                return payload
        else:
            break
    return payload


def _field(record, *candidates):
    if not isinstance(record, dict):
        return ""
    normalized = {
        re.sub(r"[^a-z0-9]", "", str(key).casefold()): value
        for key, value in record.items()
    }
    for candidate in candidates:
        value = normalized.get(
            re.sub(r"[^a-z0-9]", "", candidate.casefold())
        )
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_date(value):
    text = str(value or "").strip()
    if not text:
        return ""
    translated = []
    try:
        for char in text:
            translated.append(str(unicodedata.decimal(char)) if char.isdecimal() else char)
    except ValueError:
        return text
    text = "".join(translated)
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return text


def normalize_court_record(record):
    if not isinstance(record, dict):
        return None
    case_number = _field(
        record, "Fld_CaseHandlyNo", "Fld_CaseMachineNo", "Fld_CaseIndex",
        "CaseNumber", "case_number", "Fld_VchNo",
    )
    if not case_number:
        return None
    judge = _field(
        record, "Fld_EmployeeName1", "Fld_EmployeeName5",
        "Fld_EmployeeName", "JudgeName", "Judge",
    )
    next_date = _normalize_date(_field(
        record, "Fld_CaseNextSeatDate", "Fld_NextSeatDate",
        "SittingDate", "SeatDate", "Fld_SeatDate",
    ))
    return {
        "رقم القضية": case_number,
        "نوع القضية": _field(
            record, "Fld_KindCaseType", "Fld_KindCasePrimName",
            "Fld_KindCaseName", "CaseType",
        ),
        "برئاسة القاضي": normalize_judge_name(judge) if judge else "",
        "الجلسة القادمة": next_date,
        "تاريخ ورودها": _normalize_date(_field(
            record, "Fld_FirstImportDate", "Fld_ImportDate",
            "Fld_CaseStateDate", "Fld_InfoDate",
        )),
        "موضوعها": _field(
            record, "Fld_CaseCrimes", "Fld_InfoRequst",
            "Fld_CaseSubject", "CaseSubject",
        ),
        "حالة القضية": _field(
            record, "Fld_AllCaseDecideEntry", "Fld_CaseDecideEntry",
            "Fld_SitDecisson", "Fld_StateName", "CaseStatus",
        ),
        "المدعي": _field(
            record, "Fld_VictimFrom", "Fld_SideFromName",
            "Fld_Plaintiff", "Plaintiff", "ClaimantName",
        ),
        "المدعى عليه": _field(
            record, "Fld_VictimTo", "Fld_SideOutName",
            "Fld_Defendant", "Defendant", "RespondentName",
        ),
        "المحكمة": _field(record, "Fld_PlaceCourtsName", "Fld_PlaceName"),
        "المحافظة": _field(record, "Fld_ProvincesName"),
        "الجهة القضائية": _field(record, "Fld_SideImName", "Fld_SideName"),
    }


def _record_list(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("results", "Results", "data", "Data", "rows", "Rows", "value"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        if payload and any(
            key.casefold().startswith(
                (
                    "fld_", "case", "sitting", "wdname",
                )
            )
            for key in payload
        ):
            return [payload]
    if payload in (None, ""):
        return []
    raise CaseRecordsError(
        "صيغة قائمة البيانات التي أعادتها خدمة التطبيق الأصلي غير مدعومة."
    )


def load_case_data():
    global _case_data_cache, _case_data_cache_expires_at
    with _case_data_cache_lock:
        if (
            _case_data_cache is not None
            and time.monotonic() < _case_data_cache_expires_at
        ):
            return _case_data_cache

    payload = _request_json(
        CASE_DATA_ROUTE,
        [
            ("Fld_CaseHandlyNo", "NULL"),
            ("Fld_SideImpNo", "NULL"),
            ("Fld_PlaceCourtsNo", "NULL"),
            ("Fld_KindCaseNo", "NULL"),
            ("Fld_KindCasePrimeNo", "NULL"),
        ],
    )
    records = [
        normalize_court_record(record)
        for record in _record_list(payload)
    ]
    records = [record for record in records if record]
    with _case_data_cache_lock:
        _case_data_cache = records
        _case_data_cache_expires_at = time.monotonic() + CASE_DATA_CACHE_SECONDS
    return records


def get_case_search_options(case_type="all"):
    records = load_case_data()
    case_types = available_case_types(records)
    if case_type != "all" and case_type not in case_types:
        raise ValueError("نوع القضية المحدد غير متوفر.")
    filtered_records = records if case_type == "all" else [
        record for record in records
        if case_type_matches(record.get("نوع القضية"), case_type)
    ]
    judges = sorted({
        normalize_judge_name(record.get("برئاسة القاضي"))
        for record in filtered_records
        if record.get("برئاسة القاضي")
    })
    return {
        "case_types": case_types,
        "case_type_sources": {
            case_type: list(CASE_TYPE_SOURCE_BY_DISPLAY_NAME.get(case_type, (case_type,)))
            for case_type in case_types
        },
        "judges": judges,
    }


def search_cases(query, method=None, case_type="all", judge="all", limit=5):
    query = str(query or "").strip()
    if not query:
        raise ValueError("أدخل رقم القضية أو اسم المدعي أو المدعى عليه للبحث.")
    if len(query) > 100:
        raise ValueError("عبارة البحث أطول من المسموح.")
    method = method or ("number" if "/" in query else "name")
    if method not in {"number", "name"}:
        raise ValueError("طريقة البحث غير صالحة.")
    if case_type != "all" and case_type not in available_case_types(load_case_data()):
        raise ValueError("نوع القضية المحدد غير متوفر.")
    return search_case_records(
        load_case_data(),
        query,
        method,
        case_type=case_type,
        judge=judge,
        limit=limit,
    )


def search_case_sittings(query):
    query = str(query or "").strip()
    if not query:
        raise ValueError("أدخل رقم القضية للبحث عن سجل جلساتها.")
    if len(query) > 40:
        raise ValueError("رقم القضية أطول من المسموح.")
    normalized_query = "".join(
        str(unicodedata.decimal(char)) if char.isdecimal() else char
        for char in query
    ).casefold()
    queries = [normalized_query]
    if normalized_query.count("/") == 1:
        first, second = normalized_query.split("/")
        queries.append(f"{second}/{first}")
    results = []
    seen = set()
    for candidate in queries:
        payload = _request_json(
            CASE_SITTINGS_ROUTE,
            [
                ("Fld_CaseHandlyNo", candidate),
                ("Fld_SideImpNo", "NULL"),
                ("Fld_PlaceCourtsNo", "NULL"),
                ("Fld_KindCaseNo", "NULL"),
                ("Fld_KindCasePrimeNo", "NULL"),
            ],
        )
        for record in _record_list(payload):
            case_number = _field(record, "Fld_CaseHandlyNo")
            normalized_number = "".join(
                str(unicodedata.decimal(char)) if char.isdecimal() else char
                for char in case_number
            ).casefold()
            if not case_number or candidate not in normalized_number:
                continue
            result = {
                "رقم القضية": case_number,
                "رقم الجلسة": _field(record, "Fld_SeatNo"),
                "تاريخ الجلسة": _normalize_date(_field(record, "Fld_SeatDate")),
                "حالة القضية": _field(record, "Fld_StateName"),
                "القاضي": _field(
                    record, "Fld_EmployeeName", "Fld_EmployeeName5"
                ),
                "قرار الجلسة": _field(record, "Fld_SitDecisson"),
                "الجلسة القادمة": _normalize_date(
                    _field(record, "Fld_NextSeatDate")
                ),
                "رقم الفهرس": _field(record, "Fld_SeatIndex"),
            }
            identity = tuple(result.items())
            if identity not in seen:
                results.append(result)
                seen.add(identity)
            if len(results) >= 100:
                return results
        if results:
            return results
    return results


def search_legal_trustees(query):
    query = str(query or "").strip()
    if not query:
        raise ValueError("أدخل اسم الأمين الشرعي أو رقم ترخيصه.")
    if len(query) > 100:
        raise ValueError("عبارة البحث أطول من المسموح.")
    warrant_number = ""
    if all(char.isdecimal() for char in query):
        warrant_number = "".join(str(unicodedata.decimal(char)) for char in query)
    parameters = [
        ("Fld_SideNo", "NULL"),
        ("Fld_PlaceNo", "NULL"),
        ("Fld_SideImpNo", "NULL"),
        ("Fld_AminStat", "NULL"),
        ("wdname", "NULL" if warrant_number else query),
        ("Fld_warant_No", warrant_number or "NULL"),
    ]
    payload = _request_json(LEGAL_TRUSTEES_ROUTE, parameters)
    normalized_query = query.casefold()
    results = []
    for record in _record_list(payload):
        name = _field(record, "wdname")
        license_number = _field(record, "Fld_warant_No")
        if warrant_number:
            if license_number != warrant_number:
                continue
        elif normalized_query not in name.casefold():
            continue
        results.append({
            "اسم الأمين الشرعي": name,
            "رقم الترخيص": license_number,
            "تاريخ الترخيص": _normalize_date(
                _field(record, "Fld_warant_date")
            ),
            "الحالة": _field(record, "Fld_AminStat"),
            "الجهة": _field(record, "Fld_SideName"),
            "المحافظة": _field(record, "Fld_ProvincesName"),
            "المديرية": _field(record, "Fld_PlaceName"),
        })
        if len(results) >= 100:
            break
    return results


def search_sessions(sitting_date):
    sitting_date = str(sitting_date or "").strip()
    try:
        parsed_date = datetime.strptime(sitting_date[:10], "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("صيغة التاريخ غير صحيحة. استخدم YYYY-MM-DD.") from exc
    api_date = parsed_date.strftime("%Y/%m/%d")
    payload = _request_json(
        SESSIONS_ROUTE,
        [
            ("Fld_SideImNo", "NULL"),
            ("Fld_PlaceCourtsNo", "NULL"),
            ("SittingDate", api_date),
        ],
    )
    records = [
        normalize_court_record(record)
        for record in _record_list(payload)
    ]
    records = [record for record in records if record]
    target_date = parsed_date.date().isoformat()
    return [
        record for record in records
        if record["الجلسة القادمة"] in {"", target_date}
    ][:500]
