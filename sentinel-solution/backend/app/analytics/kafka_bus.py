"""Production hardening scaffold — Kafka-backed event bus for Model 3
federation, replacing the pilot's polled `FederatedEvent` table at
regional/statewide scale.

**Status: IMPLEMENTED, UNVERIFIED.** Written 2026-09-18 per
`docs/PRODUCTION_MIGRATION_PLAN.md`'s "Event bus" gap row and
`docs/SCALABILITY.md` §6's phase 3 ("Regional rollout: multiple
districts, Kafka event bus introduced between edge and central tiers").
No Kafka broker exists in this environment (no Docker/cluster access —
see the 2026-09-18 production-hardening review) so this has never been
run against a real broker. `kafka-python` is imported lazily so its
absence never breaks the pilot's default import path or test suite.

**Deliberately NOT wired into `main.py`'s default
`federation_ingest_loop`.** The pilot's polled `analytics/federation.py`
+ `FederatedEvent` table is the tested, demo-verified path (22 passing
tests, a real generated sample PDF). This module is an alternative
transport for the *same* `NormalizedEvent` shape `federation.py` already
defines — swapping to it is a deployment decision for the "Regional
rollout" phase, not a pilot-time change, per this repo's
minimal-diff/don't-touch-what's-validated rule.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from typing import Callable, Iterable, Optional

from .. import config
from .federation import NormalizedEvent

logger = logging.getLogger(__name__)


class KafkaUnavailable(RuntimeError):
    """Raised when Kafka is requested but `kafka-python` isn't installed
    or a broker isn't reachable. Never silently falls back to the polled
    table — that's a caller decision, same discipline as
    `vector_search.PgVectorUnavailable`."""


def _require_kafka_python():
    try:
        import kafka  # noqa: F401  (kafka-python; lazy import by design)
    except ImportError as exc:
        raise KafkaUnavailable(
            "kafka-python is not installed. It is intentionally NOT in "
            "requirements.txt (pilot has no Kafka broker) — see "
            "requirements-production.txt, install only when actually "
            "deploying against a real broker."
        ) from exc
    return kafka


class FederationEventProducer:
    """Publishes `NormalizedEvent`s onto `config.KAFKA_FEDERATION_TOPIC`.
    One producer per process, matching kafka-python's own recommended
    usage (thread-safe, reused across calls)."""

    def __init__(self, bootstrap_servers: Optional[str] = None):
        kafka = _require_kafka_python()
        servers = bootstrap_servers or config.KAFKA_BOOTSTRAP_SERVERS
        if not servers:
            raise KafkaUnavailable(
                "config.KAFKA_BOOTSTRAP_SERVERS is empty — set "
                "SENTINEL_KAFKA_BOOTSTRAP_SERVERS before constructing a producer"
            )
        # acks="all" — durability over throughput; federation events are
        # investigative data, a dropped event is worse than a slower one.
        self._producer = kafka.KafkaProducer(
            bootstrap_servers=servers.split(","),
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            acks="all",
        )

    def publish(self, event: NormalizedEvent) -> None:
        payload = asdict(event)
        # Keyed by plate so Kafka's partitioning keeps all events for one
        # plate in order on the same partition — matters for the
        # correlation engine's time-gap logic downstream.
        self._producer.send(config.KAFKA_FEDERATION_TOPIC, key=event.plate.encode("utf-8"), value=payload)

    def publish_all(self, events: Iterable[NormalizedEvent]) -> int:
        count = 0
        for event in events:
            self.publish(event)
            count += 1
        self._producer.flush()
        return count

    def close(self) -> None:
        self._producer.close()


class FederationEventConsumer:
    """Consumes `NormalizedEvent`s from Kafka and hands each one to a
    caller-supplied sink (e.g. a function wrapping `federation.py`'s
    per-event insert logic, adapted for streaming instead of batch
    `ingest_all`). Runs until `stop()` is called — intended to run in its
    own thread/process, same shape as `main.py`'s existing
    `federation_ingest_loop`, just event-driven instead of polled."""

    def __init__(self, on_event: Callable[[NormalizedEvent], None], bootstrap_servers: Optional[str] = None):
        kafka = _require_kafka_python()
        servers = bootstrap_servers or config.KAFKA_BOOTSTRAP_SERVERS
        if not servers:
            raise KafkaUnavailable(
                "config.KAFKA_BOOTSTRAP_SERVERS is empty — set "
                "SENTINEL_KAFKA_BOOTSTRAP_SERVERS before constructing a consumer"
            )
        self._on_event = on_event
        self._stopped = False
        self._consumer = kafka.KafkaConsumer(
            config.KAFKA_FEDERATION_TOPIC,
            bootstrap_servers=servers.split(","),
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            group_id=config.KAFKA_FEDERATION_CONSUMER_GROUP,
            enable_auto_commit=True,
        )

    def run_forever(self) -> None:
        for message in self._consumer:
            if self._stopped:
                break
            try:
                data = dict(message.value)
                event = NormalizedEvent(
                    plate=data["plate"],
                    observed_at=data["observed_at"],
                    camera_id=data["camera_id"],
                    source_system=data["source_system"],
                    raw_payload=data.get("raw_payload", {}),
                )
                self._on_event(event)
            except Exception:
                # A malformed/unexpected message must not kill the consumer
                # loop — log and continue, same "recoverable external
                # failure" discipline as CLAUDE.md §24.7, not a silent
                # swallow (the exception is logged with full context).
                logger.exception("federation kafka consumer: failed to process message %r", message)

    def stop(self) -> None:
        self._stopped = True
        self._consumer.close()
