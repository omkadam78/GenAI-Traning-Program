"""Bounded answer cache and request metrics without storing prompts or credentials."""

from __future__ import annotations

from collections import OrderedDict
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import logging
import threading
import time
import uuid

import requests
from starlette.responses import JSONResponse

from app.security import MAX_BODY_BYTES, InputGuardError, validate_question

LOGGER = logging.getLogger("fasalbima.requests")
if not LOGGER.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    LOGGER.addHandler(handler)
LOGGER.setLevel(logging.INFO)
LOGGER.propagate = False


class AnswerCache:
    def __init__(self, max_entries=128, ttl_seconds=300, clock=time.monotonic):
        self.max_entries, self.ttl_seconds, self.clock = max_entries, ttl_seconds, clock
        self._entries = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            created, value = entry
            if self.clock() - created >= self.ttl_seconds:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return deepcopy(value)

    def put(self, key, value):
        with self._lock:
            self._entries[key] = (self.clock(), deepcopy(value))
            self._entries.move_to_end(key)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self):
        with self._lock:
            self._entries.clear()

    def __len__(self):
        with self._lock:
            return len(self._entries)


ANSWER_CACHE = AnswerCache()


@dataclass
class RequestTrace:
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    started: float = field(default_factory=time.perf_counter)
    cache_scope: str | None = None
    llm_calls: int = 0
    llm_failures: int = 0
    unknown_usage_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cache_status: str = "BYPASS"
    cache_hits: int = 0

    def summary(self):
        known = self.unknown_usage_calls == 0
        return dict(
            request_id=self.request_id,
            processing_ms=round((time.perf_counter() - self.started) * 1000, 2),
            llm_calls=self.llm_calls,
            llm_failures=self.llm_failures,
            usage_complete=known,
            unknown_usage_calls=self.unknown_usage_calls,
            prompt_tokens=self.prompt_tokens if known else None,
            completion_tokens=self.completion_tokens if known else None,
            total_tokens=self.total_tokens if known else None,
            known_total_tokens=self.total_tokens,
            cache_status=self.cache_status,
            cache_hits=self.cache_hits,
        )


CURRENT_TRACE: ContextVar[RequestTrace | None] = ContextVar("fasalbima_request", default=None)


def usage_from_body(body, provider):
    raw = body.get("usage", {}) if provider == "groq" else body.get("usageMetadata", {})
    names = ("prompt_tokens", "completion_tokens", "total_tokens")
    aliases = (
        names
        if provider == "groq"
        else ("promptTokenCount", "candidatesTokenCount", "totalTokenCount")
    )
    return {
        name: raw.get(alias) if isinstance(raw.get(alias), int) else None
        for name, alias in zip(names, aliases)
    }


def provider_post(provider, model, url, **kwargs):
    """Count every transport attempt, including translation, retries and fallback."""
    trace = CURRENT_TRACE.get()
    usage = None
    success = False
    try:
        response = requests.post(url, **kwargs)
        success = response.status_code == 200
        if success:
            usage = usage_from_body(response.json(), provider)
        return response
    finally:
        if trace is not None:
            trace.llm_calls += 1
            trace.llm_failures += int(not success)
            if usage is None or any(value is None for value in usage.values()):
                trace.unknown_usage_calls += 1
            if usage:
                for name, value in usage.items():
                    if value is not None:
                        setattr(trace, name, getattr(trace, name) + value)


def answer_cache_key(question, matches, system_prompt, user_prompt, config, language):
    trace = CURRENT_TRACE.get()
    if trace is None or not trace.cache_scope or config["mode"] != "live":
        return None
    payload = dict(
        scope=trace.cache_scope,
        question=question,
        matches=matches,
        system=system_prompt,
        user=user_prompt,
        language=language,
        primary=(config["primary_provider"], config["primary_model"]),
        fallback=(config.get("fallback_provider"), config.get("fallback_model")),
        credentials=[
            hashlib.sha256(str(config.get(k) or "").encode()).hexdigest()
            for k in ("primary_key", "fallback_key")
        ],
    )
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def cached_answer(key):
    trace = CURRENT_TRACE.get()
    if key is None:
        return None
    value = ANSWER_CACHE.get(key)
    if trace:
        trace.cache_status = "HIT" if value else "MISS"
    if value:
        if trace:
            trace.cache_hits += 1
        value["cached_usage"] = value.get("usage", {})
        value["usage"] = dict(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        value["origin_latency_ms"] = value.get("latency_ms")
        value["latency_ms"] = 0.0
        value["cache_hit"] = True
    return value


def annotate_result(result):
    trace = CURRENT_TRACE.get()
    return dict(result, metrics=trace.summary()) if trace else result


class ProductionMiddleware:
    """Pure ASGI middleware: bounded bodies, per-request ContextVars and safe JSON logs."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        trace = RequestTrace()
        token = CURRENT_TRACE.set(trace)
        status = 500

        async def measured_send(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                summary = trace.summary()
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-request-id", trace.request_id.encode()),
                        (b"x-cache", trace.cache_status.encode()),
                        (b"x-llm-calls", str(trace.llm_calls).encode()),
                        (b"x-llm-tokens", str(summary["total_tokens"]).encode()),
                        (b"server-timing", f"app;dur={summary['processing_ms']}".encode()),
                    ]
                )
                message = dict(message, headers=headers)
            await send(message)

        try:
            if scope["method"] in ("POST", "PUT", "PATCH"):
                body = bytearray()
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > MAX_BODY_BYTES:
                        return await JSONResponse({"detail": "Request body exceeds 16 KiB."}, 413)(
                            scope, receive, measured_send
                        )
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
                try:
                    payload = json.loads(body)
                except (ValueError, UnicodeDecodeError):
                    payload = None
                if isinstance(payload, dict):
                    session = payload.get("thread_id")
                    if isinstance(session, str) and 0 < len(session) <= 128:
                        trace.cache_scope = session
                    if scope["path"].rsplit("/", 1)[-1] in ("agent", "ask", "chat", "questions"):
                        for key in ("query", "question", "message"):
                            text = payload.get(key)
                            if isinstance(text, str):
                                validate_question(text)
                replayed = False

                async def replay_receive():
                    nonlocal replayed
                    if not replayed:
                        replayed = True
                        return {"type": "http.request", "body": bytes(body), "more_body": False}
                    return await receive()

                await self.app(scope, replay_receive, measured_send)
            else:
                await self.app(scope, receive, measured_send)
        except InputGuardError as exc:
            await JSONResponse({"detail": str(exc)}, 422)(scope, receive, measured_send)
        finally:
            record = trace.summary()
            record.update(
                event="request_completed",
                method=scope["method"],
                route=getattr(scope.get("route"), "path", "unmatched"),
                status_code=status,
            )
            LOGGER.info(json.dumps(record, separators=(",", ":")))
            CURRENT_TRACE.reset(token)
