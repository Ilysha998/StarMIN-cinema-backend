import time
from collections import defaultdict
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.responses import JSONResponse
from config import settings


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self._general: dict[str, list[float]] = defaultdict(list)
        self._register: dict[str, list[float]] = defaultdict(list)
        self._login: dict[str, list[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def _check(self, bucket: dict[str, list[float]], ip: str, limit: int, now: float) -> bool:
        bucket[ip] = [t for t in bucket[ip] if now - t < 60.0]
        if len(bucket[ip]) >= limit:
            return False
        bucket[ip].append(now)
        return True

    def _cleanup(self, now: float):
        if now - self._last_cleanup < 30.0:
            return
        self._last_cleanup = now
        for b in (self._general, self._register, self._login):
            for k in list(b.keys()):
                b[k] = [t for t in b[k] if now - t < 60.0]
                if not b[k]:
                    del b[k]

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        ip = scope.get("client", ("unknown", 0))[0]
        now = time.time()
        self._cleanup(now)

        method = scope.get("method", "")
        path = scope.get("path", "")

        if method == "POST" and path == "/users/register":
            if not self._check(self._register, ip, settings.RATE_LIMIT_REGISTER_PER_MINUTE, now):
                response = JSONResponse(
                    {"detail": "Слишком много регистраций. Попробуйте позже."},
                    status_code=429,
                )
                await response(scope, receive, send)
                return

        if method == "POST" and path == "/users/login":
            if not self._check(self._login, ip, settings.RATE_LIMIT_LOGIN_PER_MINUTE, now):
                response = JSONResponse(
                    {"detail": "Слишком много попыток входа. Попробуйте позже."},
                    status_code=429,
                )
                await response(scope, receive, send)
                return

        if not self._check(self._general, ip, settings.RATE_LIMIT_PER_MINUTE, now):
            response = JSONResponse(
                {"detail": "Слишком много запросов. Замедлитесь."},
                status_code=429,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
