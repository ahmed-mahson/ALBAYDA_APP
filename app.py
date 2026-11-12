import json
import hmac
import hashlib
import logging
import os
import re
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from urllib.parse import quote, unquote
from wsgiref.simple_server import WSGIServer, make_server
from socketserver import ThreadingMixIn

import case_records
from case_records import CaseRecordsError
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent
WEB_ROOT = ROOT / "web"
MAX_BODY_BYTES = 64 * 1024
MAX_QUERY_LENGTH = 160
AUTH_COOKIE_NAME = "albayda_session"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60
LOGIN_ATTEMPT_LIMIT = 10
LOGIN_WINDOW_SECONDS = 60
MAX_TRACKED_LOGIN_CLIENTS = 10_000
_login_attempts = OrderedDict()
_login_attempts_lock = threading.Lock()
LOGGER = logging.getLogger("albayda_court")
load_dotenv(ROOT / ".env")


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def _json_response(start_response, status, payload, extra_headers=()):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    start_response(
        f"{status.value} {status.phrase}",
        [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ] + list(extra_headers),
    )
    return [body]


def _auth_required():
    return os.getenv("APP_REQUIRE_AUTH", "").strip().casefold() in {
        "1", "true", "yes", "on",
    }


def _secure_request(environ):
    forwarded_protocol = environ.get("HTTP_X_FORWARDED_PROTO", "").split(",", 1)[0].strip()
    return environ.get("wsgi.url_scheme") == "https" or forwarded_protocol == "https"


def _session_signature(issued_at, secret):
    return hmac.new(
        secret.encode("utf-8"),
        f"albayda-court:{issued_at}".encode("ascii"),
        hashlib.sha256,
    ).hexdigest()


def _login_is_limited(client_ip):
    now = time.monotonic()
    with _login_attempts_lock:
        attempts = _login_attempts.get(client_ip)
        if attempts is not None:
            while attempts and now - attempts[0] >= LOGIN_WINDOW_SECONDS:
                attempts.popleft()
            if not attempts:
                del _login_attempts[client_ip]
                attempts = None
        if attempts is None:
            if len(_login_attempts) >= MAX_TRACKED_LOGIN_CLIENTS:
                _login_attempts.popitem(last=False)
            attempts = deque()
            _login_attempts[client_ip] = attempts
        else:
            _login_attempts.move_to_end(client_ip)
        if len(attempts) >= LOGIN_ATTEMPT_LIMIT:
            return True
        attempts.append(now)
        return False


def _is_authenticated(environ):
    secret = os.getenv("APP_SESSION_SECRET", "")
    if not secret:
        return False
    cookies = {}
    for item in environ.get("HTTP_COOKIE", "").split(";"):
        name, separator, value = item.strip().partition("=")
        if separator:
            cookies[name] = value
    issued_text, separator, signature = cookies.get(AUTH_COOKIE_NAME, "").partition(".")
    if not separator or not issued_text.isdecimal():
        return False
    issued_at = int(issued_text)
    now = int(time.time())
    if issued_at > now + 60 or now - issued_at > SESSION_MAX_AGE_SECONDS:
        return False
    expected = _session_signature(issued_text, secret)
    return hmac.compare_digest(signature, expected)


def _login(payload, environ, start_response):
    if not _auth_required():
        return _json_response(
            start_response, HTTPStatus.OK, {"authenticated": True}
        )
    expected_password = os.getenv("APP_ACCESS_PASSWORD", "")
    secret = os.getenv("APP_SESSION_SECRET", "")
    if not expected_password or not secret:
        return _json_response(
            start_response,
            HTTPStatus.SERVICE_UNAVAILABLE,
            {"error": "لم يُضبط دخول التطبيق الآمن في إعدادات الخادم."},
        )
    client_ip = environ.get("REMOTE_ADDR", "unknown")
    if _login_is_limited(client_ip):
        return _json_response(
            start_response,
            HTTPStatus.TOO_MANY_REQUESTS,
            {"error": "تجاوزت محاولات الدخول المسموحة. حاول بعد دقيقة."},
            [("Retry-After", str(LOGIN_WINDOW_SECONDS))],
        )
    password = _text(payload, "password", "كلمة المرور", required=True, limit=256)
    if not hmac.compare_digest(password, expected_password):
        return _json_response(
            start_response,
            HTTPStatus.UNAUTHORIZED,
            {"error": "كلمة المرور غير صحيحة."},
        )
    issued_at = str(int(time.time()))
    value = f"{issued_at}.{_session_signature(issued_at, secret)}"
    cookie = (
        f"{AUTH_COOKIE_NAME}={value}; Path=/; HttpOnly; SameSite=Strict; "
        f"Max-Age={SESSION_MAX_AGE_SECONDS}"
    )
    if _secure_request(environ):
        cookie += "; Secure"
    return _json_response(
        start_response,
        HTTPStatus.OK,
        {"authenticated": True},
        [("Set-Cookie", cookie)],
    )


def _redirect_response(start_response, location):
    start_response(
        "303 See Other",
        [
            ("Location", location),
            ("Content-Length", "0"),
            ("Cache-Control", "no-store"),
        ],
    )
    return [b""]


def _plain_response(start_response, status, body):
    encoded = body.encode("utf-8")
    start_response(
        f"{status.value} {status.phrase}",
        [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(encoded))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ],
    )
    return [encoded]


def _pdf_response(start_response, pdf, filename):
    body = pdf.getvalue()
    start_response(
        "200 OK",
        [
            ("Content-Type", "application/pdf"),
            ("Content-Length", str(len(body))),
            ("Content-Disposition", f"attachment; filename*=UTF-8''{quote(filename, safe='')}"),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ],
    )
    return [body]


def _read_json(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError as exc:
        raise ValueError("حجم الطلب غير صالح.") from exc
    if length <= 0 or length > MAX_BODY_BYTES:
        raise ValueError("بيانات الطلب فارغة أو أكبر من الحد المسموح.")
    try:
        value = json.loads(environ["wsgi.input"].read(length).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("تعذر قراءة بيانات الطلب.") from exc
    if not isinstance(value, dict):
        raise ValueError("يجب إرسال بيانات الطلب بصيغة JSON.")
    return value


def _text(payload, key, label, *, required=False, limit=MAX_QUERY_LENGTH):
    value = payload.get(key, "")
    if not isinstance(value, str):
        raise ValueError(f"حقل {label} غير صالح.")
    value = value.strip()
    if required and not value:
        raise ValueError(f"أدخل {label}.")
    if len(value) > limit:
        raise ValueError(f"حقل {label} أطول من المسموح.")
    return value


def _case_search(payload):
    query = _text(
        payload, "query", "رقم القضية أو اسم أحد الأطراف", required=True, limit=100
    )
    method = _text(payload, "method", "طريقة البحث", limit=20)
    if method in {"", "auto"}:
        method = "number" if "/" in query else "name"
    if method not in {"number", "name"}:
        raise ValueError("طريقة البحث غير صالحة.")
    case_type = _text(payload, "case_type", "نوع القضية", limit=100) or "all"
    judge = _text(payload, "judge", "القاضي", limit=160) or "all"
    records = case_records.load_case_records()
    if (
        case_type != "all"
        and case_type not in case_records.available_case_types(records)
    ):
        raise ValueError("نوع القضية المحدد غير متوفر في سجل القضايا.")
    matches = case_records.search_case_records(
        records, query, method, case_type=case_type, judge=judge, limit=5
    )
    return {"count": len(matches), "results": matches}


def _case_search_options(payload):
    case_type = _text(payload, "case_type", "نوع القضية", limit=100) or "all"
    records = case_records.load_case_records()
    case_types = case_records.available_case_types(records)
    if case_type != "all" and case_type not in case_types:
        raise ValueError("نوع القضية المحدد غير متوفر في سجل القضايا.")
    filtered_records = records if case_type == "all" else [
        record for record in records
        if case_records.case_type_matches(record.get("نوع القضية"), case_type)
    ]
    return {
        "case_types": case_types,
        "case_type_sources": {
            name: list(case_records.CASE_TYPE_SOURCE_BY_DISPLAY_NAME.get(
                name, (name,)
            ))
            for name in case_types
        },
        "judges": case_records.available_judges(filtered_records),
    }


def _sitting_date(value, label):
    if value == "اليوم":
        return datetime.now(case_records.COURT_TIMEZONE).date().isoformat()
    normalized = case_records._normalized_date(value)
    if normalized is None:
        raise ValueError(f"صيغة {label} غير صحيحة. استخدم YYYY-MM-DD أو YYYY/MM/DD أو أرسل «اليوم».")
    return normalized


def _session_search(payload):
    sitting_date = _sitting_date(
        _text(payload, "date", "تاريخ الجلسة", required=True, limit=20),
        "تاريخ الجلسة",
    )
    judge = _text(payload, "judge", "القاضي", limit=100) or "all"
    sessions = case_records.search_sessions_by_date(
        case_records.load_case_records(), sitting_date
    )
    if judge != "all":
        sessions = [
            row for row in sessions
            if case_records.normalize_judge_name(row.get("برئاسة القاضي")) ==
            case_records.normalize_judge_name(judge)
        ]
    return {
        "date": sitting_date,
        "judge": judge,
        "count": len(sessions),
        "results": sessions,
    }


def _supreme_search(payload):
    name = _text(payload, "name", "اسم الطاعن أو الملتمس", limit=100)
    decision_number = _text(payload, "decision_number", "رقم الحكم", limit=30)
    case_type = _text(payload, "case_type", "نوع البحث", limit=20) or "0"
    authority = _text(payload, "authority", "جهة الاستئناف", limit=10) or "0"
    if not name and not decision_number:
        raise ValueError("أدخل اسم الطاعن أو رقم الحكم للبحث.")
    rows = case_records.search_supreme_court_cases(
        name=name,
        case_type=case_type,
        authority=authority,
        decision_number=decision_number,
    )
    return {
        "count": len(rows) // 6,
        "results": [
            dict(rows[index:index + 6])
            for index in range(0, len(rows), 6)
        ],
        "report_rows": rows,
        "query": {
            "name": name,
            "decision_number": decision_number,
            "case_type": case_type,
            "authority": authority,
        },
    }


def _post_api(path, payload, start_response):
    if path == "/api/cases/search":
        return _json_response(start_response, HTTPStatus.OK, _case_search(payload))

    if path == "/api/cases/options":
        return _json_response(
            start_response, HTTPStatus.OK, _case_search_options(payload)
        )

    if path == "/api/cases/report":
        case_number = _text(
            payload, "case_number", "رقم القضية", required=True, limit=40
        )
        normalized_number = case_records._normalize_case_number(case_number)
        records = case_records.search_case_records(
            case_records.load_case_records(),
            case_number,
            "number",
            limit=100,
        )
        record = next(
            (
                row for row in records
                if case_records._normalize_case_number(row.get("رقم القضية", ""))
                == normalized_number
            ),
            None,
        )
        if record is None:
            return _json_response(
                start_response,
                HTTPStatus.NOT_FOUND,
                {"error": "لم يتم العثور على القضية المطلوبة."},
            )
        pdf = case_records.generate_case_pdf(record)
        filename_number = re.sub(r"[^0-9A-Za-z_-]", "_", case_number)
        return _pdf_response(start_response, pdf, f"تفاصيل_القضية_{filename_number}.pdf")

    if path == "/api/sessions/search":
        return _json_response(start_response, HTTPStatus.OK, _session_search(payload))

    if path == "/api/sessions/pdf":
        result = _session_search(payload)
        if not result["results"]:
            raise CaseRecordsError("لا توجد جلسات مطابقة لإنشاء القائمة.")
        pdf = case_records.generate_sessions_pdf(result["results"], result["date"])
        return _pdf_response(start_response, pdf, f"قائمة_الجلسات_{result['date']}.pdf")

    if path == "/api/attendance-ad":
        case_number = _text(payload, "case_number", "رقم القضية", required=True, limit=40)
        sitting_date = _sitting_date(
            _text(payload, "session_date", "تاريخ الجلسة", required=True, limit=20),
            "تاريخ الجلسة",
        )
        case_type = _text(
            payload, "case_type", "نوع القضية", required=True, limit=100
        )
        judge_filter = _text(
            payload, "judge_filter", "القاضي المختص", required=True, limit=160
        )
        judge = _text(
            payload, "judge", "اسم القاضي في الإعلان", required=True, limit=160
        )
        plaintiff = _text(payload, "plaintiff", "اسم المدعي", required=True, limit=200)
        defendant = _text(payload, "defendant", "اسم المدعى عليه", required=True, limit=200)
        matches = case_records.search_case_records(
            case_records.load_case_records(),
            case_number,
            "number",
            case_type=case_type,
            judge=judge_filter,
            limit=1,
        )
        normalized_number = case_records._normalize_case_number(case_number)
        record = next(
            (
                item for item in matches
                if case_records._normalize_case_number(item.get("رقم القضية", ""))
                in {
                    normalized_number,
                    "/".join(reversed(normalized_number.split("/")))
                    if normalized_number.count("/") == 1
                    else normalized_number,
                }
            ),
            None,
        )
        if record is None:
            raise CaseRecordsError(
                "لم أجد القضية بهذا الرقم ضمن النوع والقاضي المحددين في ملف سجل القضايا."
            )
        case_number = record["رقم القضية"]
        pdf = case_records.generate_attendance_ad_pdf(
            case_number, plaintiff, defendant, sitting_date, judge
        )
        filename_number = re.sub(r"[^0-9A-Za-z_-]", "_", case_number)
        return _pdf_response(start_response, pdf, f"اعلان_حضور_{filename_number}.pdf")

    if path in {"/api/supreme-court/search", "/api/supreme-court/report"}:
        result = _supreme_search(payload)
        if path.endswith("/search"):
            result.pop("report_rows", None)
            return _json_response(start_response, HTTPStatus.OK, result)
        pdf = case_records.generate_search_report_pdf(
            "نتائج المحكمة العليا", result["report_rows"]
        )
        return _pdf_response(start_response, pdf, "نتائج_المحكمة_العليا.pdf")

    return _json_response(
        start_response, HTTPStatus.NOT_FOUND, {"error": "المسار المطلوب غير موجود."}
    )


def _static_file(path, start_response):
    if path in {"", "/"}:
        path = "/index.html"
    requested = (WEB_ROOT / unquote(path.lstrip("/"))).resolve()
    try:
        requested.relative_to(WEB_ROOT.resolve())
    except ValueError:
        return _json_response(
            start_response, HTTPStatus.NOT_FOUND, {"error": "الملف غير موجود."}
        )
    if not requested.is_file():
        return _json_response(
            start_response, HTTPStatus.NOT_FOUND, {"error": "الملف غير موجود."}
        )
    content_types = {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".js": "application/javascript; charset=utf-8",
        ".json": "application/manifest+json; charset=utf-8",
        ".png": "image/png",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
        ".ttf": "font/ttf",
    }
    body = requested.read_bytes()
    start_response(
        "200 OK",
        [
            ("Content-Type", content_types.get(requested.suffix, "application/octet-stream")),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-cache" if requested.name == "service-worker.js" else "public, max-age=3600"),
            ("X-Content-Type-Options", "nosniff"),
        ],
    )
    return [body]


def application(environ, start_response):
    path = unquote(environ.get("PATH_INFO", "/"))
    method = environ.get("REQUEST_METHOD", "GET").upper()
    if path == "/healthz" and method == "GET":
        return _plain_response(start_response, HTTPStatus.OK, "ok")
    if path == "/login" and method == "GET":
        if _is_authenticated(environ):
            return _redirect_response(start_response, "/")
        return _static_file("/login.html", start_response)
    if path == "/api/login" and method == "POST":
        try:
            return _login(_read_json(environ), environ, start_response)
        except ValueError as exc:
            return _json_response(
                start_response, HTTPStatus.BAD_REQUEST, {"error": str(exc)}
            )
    if path == "/api/logout" and method == "POST":
        cookie = (
            f"{AUTH_COOKIE_NAME}=; Path=/; HttpOnly; SameSite=Strict; "
            "Max-Age=0"
        )
        if _secure_request(environ):
            cookie += "; Secure"
        return _json_response(
            start_response,
            HTTPStatus.OK,
            {"authenticated": False},
            [("Set-Cookie", cookie)],
        )
    public_login_assets = {
        "/assets/albayda-it-logo.png",
        "/assets/sultan-medium.ttf",
    }
    if (
        _auth_required()
        and not _is_authenticated(environ)
        and path not in public_login_assets
    ):
        if path.startswith("/api/"):
            return _json_response(
                start_response,
                HTTPStatus.UNAUTHORIZED,
                {"error": "سجّل الدخول لاستخدام خدمات المحكمة."},
            )
        if method == "GET":
            return _redirect_response(start_response, "/login")
        return _json_response(
            start_response,
            HTTPStatus.UNAUTHORIZED,
            {"error": "سجّل الدخول لاستخدام خدمات المحكمة."},
        )
    if path == "/api/status" and method == "GET":
        return _json_response(
            start_response,
            HTTPStatus.OK,
            {
                "name": "albayda_court",
                "court": "تقنية معلومات محكمة البيضاء الابتدائية",
                "source_configured": bool(case_records.google_drive_file_id()),
                "authentication_required": _auth_required(),
            },
        )
    if path.startswith("/api/") and method == "POST":
        try:
            return _post_api(path, _read_json(environ), start_response)
        except ValueError as exc:
            return _json_response(
                start_response, HTTPStatus.BAD_REQUEST, {"error": str(exc)}
            )
        except CaseRecordsError as exc:
            LOGGER.warning("Source data request failed: %s", exc)
            return _json_response(
                start_response, HTTPStatus.SERVICE_UNAVAILABLE, {"error": str(exc)}
            )
        except Exception:
            LOGGER.exception("Unexpected application service error.")
            return _json_response(
                start_response,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": "حدث خطأ غير متوقع. راجع سجل الخادم."},
            )
    if path.startswith("/api/"):
        return _json_response(
            start_response,
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"error": "طريقة الطلب غير مدعومة."},
        )
    if method != "GET":
        return _json_response(
            start_response,
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"error": "طريقة الطلب غير مدعومة."},
        )
    return _static_file(path, start_response)


def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    host = os.getenv("ALBAYDA_HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8080"))
    if _auth_required():
        missing = [
            key for key in ("APP_ACCESS_PASSWORD", "APP_SESSION_SECRET")
            if not os.getenv(key, "").strip()
        ]
        if missing:
            raise RuntimeError(
                "Authenticated deployment requires: " + ", ".join(missing)
            )
        if len(os.getenv("APP_ACCESS_PASSWORD", "")) < 12:
            raise RuntimeError("APP_ACCESS_PASSWORD must contain at least 12 characters.")
        if len(os.getenv("APP_SESSION_SECRET", "")) < 32:
            raise RuntimeError("APP_SESSION_SECRET must contain at least 32 characters.")
    with make_server(host, port, application, server_class=ThreadingWSGIServer) as server:
        LOGGER.info("albayda_court is listening on http://%s:%s", host, port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            LOGGER.info("Stopping albayda_court.")


if __name__ == "__main__":
    main()
