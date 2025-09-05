"""
Middlewares de sécurité et de performance (modulaires & pilotés par flags).
"""

from __future__ import annotations

import time
import uuid
import logging
from typing import List, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.sessions import SessionMiddleware

# SlowAPI (rate limiting) — optionnel
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _SLOWAPI_AVAILABLE = True
except Exception:  # pragma: no cover
    Limiter = None  # type: ignore
    _rate_limit_exceeded_handler = None  # type: ignore
    get_remote_address = None  # type: ignore
    RateLimitExceeded = Exception  # type: ignore
    _SLOWAPI_AVAILABLE = False

logger = logging.getLogger(__name__)

# === Configs runtime simples ===
BLOCKED_IPS: List[str] = []
BLOCKED_USER_AGENTS: List[str] = []
DEFAULT_MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB

limiter = Limiter(key_func=get_remote_address) if _SLOWAPI_AVAILABLE else None


# ========= utilitaires =========

def _s(app: FastAPI):
    """Raccourci pour app.state.settings (peut être None)."""
    return getattr(app.state, "settings", None)


def _build_allowed_origins(hosts: List[str]) -> List[str]:
    origins: List[str] = []
    for host in hosts or []:
        if host.startswith("http://") or host.startswith("https://"):
            origins.append(host)
        else:
            origins.append(f"http://{host}")
            origins.append(f"https://{host}")
    return origins


# ========= middlewares custom =========

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        return response


class CSPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
            "font-src 'self' fonts.gstatic.com; "
            "img-src 'self' data: https:; "
            "connect-src 'self';"
        )
        response.headers["Content-Security-Policy"] = csp_policy
        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        url = str(request.url)
        ua = request.headers.get("user-agent", "unknown")
        try:
            response = await call_next(request)
            dt = time.time() - start
            logger.info(f"✅ {client_ip} {method} {url} {response.status_code} {dt:.3f}s - {ua[:100]}")
            return response
        except Exception as e:
            dt = time.time() - start
            logger.error(f"❌ {client_ip} {method} {url} ERROR {dt:.3f}s - {str(e)[:200]} - {ua[:100]}", exc_info=True)
            raise


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/") or path.startswith("/uploads/"):
            response.headers["Cache-Control"] = "public, max-age=31536000"
        elif path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        else:
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response


class IPFilterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        if client_ip in BLOCKED_IPS:
            logger.warning(f"🚫 IP bloquée: {client_ip}")
            return JSONResponse(status_code=403, content={"detail": "Accès refusé - IP bloquée"})
        return await call_next(request)


class UserAgentFilterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ua = request.headers.get("user-agent", "").lower()
        if any(token in ua for token in BLOCKED_USER_AGENTS):
            logger.warning(f"🤖 User-Agent bloqué: {ua[:100]}")
            return JSONResponse(status_code=403, content={"detail": "Accès refusé - Robot détecté"})
        return await call_next(request)


class RequestSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = _s(request.app)
        limit = getattr(settings, "MAX_FILE_SIZE", DEFAULT_MAX_REQUEST_SIZE)
        if request.method in {"POST", "PUT", "PATCH"}:
            cl = request.headers.get("content-length")
            if cl:
                try:
                    size = int(cl)
                    if size > limit:
                        return JSONResponse(
                            status_code=413,
                            content={"detail": f"Requête trop volumineuse - Maximum {limit // (1024*1024)}MB"},
                        )
                except ValueError:
                    pass
        return await call_next(request)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except RateLimitExceeded:  # type: ignore
            if _SLOWAPI_AVAILABLE and _rate_limit_exceeded_handler:
                return _rate_limit_exceeded_handler(request, None)  # type: ignore
            return JSONResponse(status_code=429, content={"detail": "Too Many Requests"})
        except Exception:
            logger.exception("💥 Erreur non gérée")
            return JSONResponse(
                status_code=500,
                content={"detail": "Erreur interne du serveur", "request_id": getattr(request.state, "request_id", "unknown")},
            )


# ========= setup modulaires =========

def setup_https_redirect_middleware(app: FastAPI):
    """HTTP -> HTTPS uniquement si activé ET pas en debug."""
    s = _s(app)
    if not s or s.DEBUG or not s.ENABLE_HTTPS_REDIRECT:
        logger.info("🔓 HTTPS redirect désactivé")
        return

    @app.middleware("http")
    async def https_redirect_middleware(request: Request, call_next):
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "http":
            return RedirectResponse(str(request.url.replace(scheme="https")), status_code=301)
        return await call_next(request)

    logger.info("🔐 HTTPS redirect activé")


def setup_trusted_host_middleware(app: FastAPI, allowed_hosts: List[str]):
    s = _s(app)
    allowed = ["*"] if (not s or s.DEBUG or not s.TRUSTED_HOST_STRICT) else (allowed_hosts or ["*"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed)
    logger.info(f"🏠 TrustedHost: {allowed}")


def setup_cors_middleware(app: FastAPI, allowed_hosts: List[str]):
    s = _s(app)
    origins = ["*"] if (s and s.CORS_ALLOW_ALL) else _build_allowed_origins(allowed_hosts or [])
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["authorization", "content-type", "accept"],
    )
    logger.info(f"🌐 CORS origins: {origins}")


def setup_error_handling_middleware(app: FastAPI):
    app.add_middleware(ErrorHandlingMiddleware)
    logger.info("🛡️ ErrorHandling configuré")


def setup_request_size_middleware(app: FastAPI):
    s = _s(app)
    if not s or not s.REQUEST_SIZE_LIMIT_ENABLED:
        logger.info("📏 Request size limit désactivé")
        return
    app.add_middleware(RequestSizeMiddleware)
    logger.info("📏 Request size limit activé")


def setup_ip_filter_middleware(app: FastAPI):
    s = _s(app)
    if not s or not s.IP_FILTER_ENABLED:
        logger.info("🔍 IP filter désactivé")
        return
    app.add_middleware(IPFilterMiddleware)
    logger.info("🔍 IP filter activé")


def setup_user_agent_filter_middleware(app: FastAPI):
    s = _s(app)
    if not s or not s.UA_FILTER_ENABLED:
        logger.info("🤖 UA filter désactivé")
        return
    app.add_middleware(UserAgentFilterMiddleware)
    logger.info("🤖 UA filter activé")


def setup_logging_middleware(app: FastAPI):
    app.add_middleware(LoggingMiddleware)
    logger.info("📝 Logging configuré")


def setup_request_id_middleware(app: FastAPI):
    app.add_middleware(RequestIDMiddleware)
    logger.info("🆔 Request ID configuré")


def setup_compression_middleware(app: FastAPI):
    s = _s(app)
    if s and not s.GZIP_ENABLED:
        logger.info("🗜️ GZip désactivé")
        return
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    logger.info("🗜️ GZip configuré")


def setup_cache_control_middleware(app: FastAPI):
    s = _s(app)
    if s and not s.CACHE_ENABLED:
        logger.info("💾 Cache-Control désactivé")
        return
    app.add_middleware(CacheControlMiddleware)
    logger.info("💾 Cache-Control configuré")


def setup_security_middleware(app: FastAPI):
    s = _s(app)
    if not s or s.SECURITY_HEADERS_ENABLED:
        app.add_middleware(SecurityHeadersMiddleware)
        logger.info("🔒 Security headers activés")
    if s and s.CSP_ENABLED:
        app.add_middleware(CSPMiddleware)
        logger.info("🧱 CSP activé")
    else:
        logger.info("🧱 CSP désactivé")


def setup_rate_limiting_middleware(app: FastAPI):
    s = _s(app)
    if not _SLOWAPI_AVAILABLE or not s or not s.RATE_LIMITING_ENABLED:
        logger.info("⏱️ Rate limiting désactivé")
        return
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore
    logger.info("⏱️ Rate limiting configuré")


def setup_session_middleware(app: FastAPI, secret_key: str):
    app.add_middleware(SessionMiddleware, secret_key=secret_key)
    logger.info("🍪 Session middleware configuré")


def setup_all_middlewares(app: FastAPI, allowed_hosts: List[str], secret_key: str):
    logger.info("🚀 Configuration des middlewares (modulaire) ...")

    setup_https_redirect_middleware(app)
    setup_trusted_host_middleware(app, allowed_hosts)
    setup_cors_middleware(app, allowed_hosts)
    setup_error_handling_middleware(app)
    setup_request_size_middleware(app)
    setup_ip_filter_middleware(app)
    setup_user_agent_filter_middleware(app)
    setup_logging_middleware(app)
    setup_request_id_middleware(app)
    setup_compression_middleware(app)
    setup_cache_control_middleware(app)
    setup_security_middleware(app)
    setup_rate_limiting_middleware(app)
    setup_session_middleware(app, secret_key)

    logger.info("✅ Tous les middlewares ont été configurés")
