"""
FastForge Event Bus
========================
local event bus for domain events.
Decouple your business logic by publishing events instead of direct calls.

Usage:
    from fastforge_core.events import event_bus, DomainEvent

    # Define an event
    class OrderCreatedEvent(DomainEvent):
        order_id: int
        customer_email: str
        total: float

    # Subscribe a handler
    @event_bus.on(OrderCreatedEvent)
    def send_order_confirmation(event: OrderCreatedEvent):
        send_email(event.customer_email, "Order confirmed", ...)

    @event_bus.on(OrderCreatedEvent)
    def update_inventory(event: OrderCreatedEvent):
        inventory_service.reserve(event.order_id)

    # Publish from your service
    class OrderService(CrudAppService[...]):
        def after_create(self, entity):
            event_bus.publish(OrderCreatedEvent(
                order_id=entity.id,
                customer_email=entity.customer_email,
                total=entity.total_amount,
            ))
"""
from __future__ import annotations
from typing import Type, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

logger = logging.getLogger("fastforge.events")


class DomainEvent:
    """
    Base class for domain events.
    Subclass with your event data as attributes.
    """
    def __init__(self, **kwargs):
        self.timestamp = datetime.now(timezone.utc)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __repr__(self):
        attrs = {k: v for k, v in self.__dict__.items() if k != "timestamp"}
        return f"{self.__class__.__name__}({attrs})"


class EventBus:
    """
    Simple synchronous event bus.
    For distributed events, extend this with Redis/RabbitMQ publishing.
    """

    def __init__(self):
        self._handlers: dict[Type[DomainEvent], list[Callable]] = {}
        self._history: list[dict] = []

    def on(self, event_type: Type[DomainEvent]):
        """
        Decorator to subscribe a handler to an event type.

        @event_bus.on(OrderCreatedEvent)
        def handle_order(event):
            ...
        """
        def decorator(func: Callable):
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(func)
            return func
        return decorator

    def subscribe(self, event_type: Type[DomainEvent], handler: Callable):
        """Subscribe a handler to an event type (non-decorator form)."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent):
        """
        Publish an event. All registered handlers are called synchronously.
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        logger.info(f"Publishing {event_type.__name__} → {len(handlers)} handler(s)")

        self._history.append({
            "event": event_type.__name__,
            "timestamp": event.timestamp.isoformat(),
            "handlers": len(handlers),
        })

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler {handler.__name__} failed for {event_type.__name__}: {e}")
                # Don't re-raise — other handlers should still execute

    def publish_async(self, event: DomainEvent, background_tasks=None):
        """
        Publish an event after the response is sent (using FastAPI BackgroundTasks).
        Useful for non-critical side effects like emails, logging, etc.
        """
        if background_tasks:
            background_tasks.add_task(self.publish, event)
        else:
            self.publish(event)

    def get_history(self, limit: int = 50) -> list[dict]:
        return self._history[-limit:]

    def clear_handlers(self):
        """Clear all handlers. Useful for testing."""
        self._handlers.clear()


# Global instance
event_bus = EventBus()
