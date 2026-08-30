"""Эвристическая ИИ-диагностика по сообщениям событий."""

from app.schemas import DiagnoseResponse

KNOWN_PATTERNS: list[tuple[list[str], str, str, list[str]]] = [
    (
        ["db locked", "database locked", "sqlite locked"],
        "Блокировка базы данных SQLite — вероятно, конкурентная запись или долгая транзакция.",
        "high",
        [
            "Проверить активные транзакции и долгие запросы к БД.",
            "Убедиться, что соединения закрываются после использования.",
            "Рассмотреть WAL-режим SQLite или переход на PostgreSQL при высокой нагрузке.",
        ],
    ),
    (
        ["timeout", "timed out", "deadline exceeded"],
        "Таймаут при обращении к внешнему сервису — сеть или перегрузка зависимости.",
        "high",
        [
            "Проверить доступность внешнего сервиса и latency.",
            "Увеличить timeout или добавить retry с backoff.",
            "Проверить метрики сети и DNS.",
        ],
    ),
    (
        ["valueerror", "parse error", "parsing failed"],
        "Ошибка парсинга входных данных — неверный формат или схема.",
        "medium",
        [
            "Проверить формат входных данных и примеры payload.",
            "Добавить валидацию на входе API.",
            "Просмотреть логи с полным телом запроса.",
        ],
    ),
    (
        ["connection refused", "connection reset"],
        "Сервис недоступен — зависимость не запущена или сеть разорвана.",
        "high",
        [
            "Проверить статус зависимого сервиса (health check).",
            "Проверить firewall и сетевые правила.",
            "Просмотреть логи upstream-сервиса.",
        ],
    ),
    (
        ["out of memory", "oom", "memory"],
        "Нехватка памяти — утечка или превышение лимитов.",
        "medium",
        [
            "Проверить метрики памяти (RSS, heap).",
            "Проанализировать профиль памяти.",
            "Увеличить лимиты или оптимизировать кэш.",
        ],
    ),
]

VAGUE_MESSAGES = {"error", "failed", "something went wrong", "ошибка", "сбой"}


def diagnose(title: str, messages: list[str]) -> DiagnoseResponse:
    combined = " ".join(messages).lower()
    title_lower = title.lower()

    for keywords, hypothesis, confidence, steps in KNOWN_PATTERNS:
        if any(kw in combined or kw in title_lower for kw in keywords):
            return DiagnoseResponse(
                root_cause_hypothesis=hypothesis,
                confidence=confidence,  # type: ignore[arg-type]
                next_steps=steps,
                needs_review=False,
            )

    if len(messages) < 2 or all(len(m.strip()) < 15 for m in messages):
        return DiagnoseResponse(
            root_cause_hypothesis=(
                "Недостаточно данных для уверенного вывода. "
                f"Инцидент «{title}» содержит слишком мало или слишком общие сообщения."
            ),
            confidence="low",
            next_steps=[
                "Собрать уточнения: добавить логи с полным stack trace и timestamp.",
                "Собрать метрики: CPU, память, latency за период инцидента.",
                "Указать затронутый сервис, окружение (prod/staging) и время начала.",
                "Приложить последние 50 строк логов приложения и зависимостей.",
            ],
            needs_review=True,
        )

    vague_only = all(
        m.strip().lower() in VAGUE_MESSAGES or len(m.strip()) < 12 for m in messages
    )
    if vague_only:
        return DiagnoseResponse(
            root_cause_hypothesis=(
                "Сообщения слишком общие — требуется ручная проверка и сбор деталей."
            ),
            confidence="low",
            next_steps=[
                "Собрать уточнения: конкретные error codes, HTTP status, stack trace.",
                "Собрать логи приложения за 15 минут до и после инцидента.",
                "Проверить метрики: error rate, latency p95, availability.",
                "Определить, воспроизводится ли проблема стабильно.",
            ],
            needs_review=True,
        )

    if "warning" in combined or "slow" in combined or "медленн" in combined:
        return DiagnoseResponse(
            root_cause_hypothesis=(
                "Деградация производительности — медленные ответы или предупреждения о нагрузке."
            ),
            confidence="medium",
            next_steps=[
                "Проверить latency p50/p95/p99 за последний час.",
                "Проанализировать slow query log и внешние вызовы.",
                "Проверить нагрузку на CPU и I/O.",
            ],
            needs_review=False,
        )

    return DiagnoseResponse(
        root_cause_hypothesis=(
            f"По инциденту «{title}» выявлены аномалии, но однозначная причина не определена. "
            "Требуется дополнительный анализ логов."
        ),
        confidence="low",
        next_steps=[
            "Собрать уточнения: полные логи с correlation_id и trace_id.",
            "Собрать метрики error rate и latency за период инцидента.",
            "Сопоставить время событий с деплоями и изменениями конфигурации.",
            "Провести ручной разбор связанных событий.",
        ],
        needs_review=True,
    )
