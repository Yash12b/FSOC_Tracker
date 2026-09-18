"""Simulated FSOC Communication engine for bidirectional messaging."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from fsoc_tracker.simulation.optical_link import LinkStatus, OpticalLinkState


class MessageStatus(str, Enum):
    QUEUED = "QUEUED"
    TRANSMITTING = "TRANSMITTING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


@dataclass
class Message:
    message_id: int
    source: str
    destination: str
    timestamp_s: float
    payload: str
    size_bytes: int
    status: MessageStatus = MessageStatus.QUEUED
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "source": self.source,
            "destination": self.destination,
            "timestamp_s": self.timestamp_s,
            "payload": self.payload,
            "size_bytes": self.size_bytes,
            "status": self.status.value,
        }


class CommunicationEngine:
    def __init__(self) -> None:
        self.message_log: list[Message] = []
        self._next_id = 1
        self._tx_queue: list[Message] = []
        self.transmission_latency_s = 0.1 # simulated geometric delay

    def create_message(self, source: str, destination: str, payload: str, current_time_s: float) -> Message:
        msg = Message(
            message_id=self._next_id,
            source=source,
            destination=destination,
            timestamp_s=current_time_s,
            payload=payload,
            size_bytes=len(payload.encode('utf-8'))
        )
        self._next_id += 1
        return msg

    def send_message(self, msg: Message) -> None:
        self._tx_queue.append(msg)
        self.message_log.append(msg)

    def update(self, link_state: OpticalLinkState, current_time_s: float) -> None:
        """Process tx_queue based on link state."""
        # States that allow transmission
        can_tx = {LinkStatus.LOCKED, LinkStatus.DEGRADED, LinkStatus.ALIGNING}
        # States that cause failure
        fail_states = {LinkStatus.LOST, LinkStatus.REACQUIRING, LinkStatus.NO_LINK}

        for msg in self._tx_queue:
            if msg.status == MessageStatus.QUEUED:
                if link_state.status in can_tx:
                    msg.status = MessageStatus.TRANSMITTING
                    msg.timestamp_s = current_time_s
            elif msg.status == MessageStatus.TRANSMITTING:
                if link_state.status in fail_states:
                    msg.status = MessageStatus.FAILED
                elif current_time_s - msg.timestamp_s >= self.transmission_latency_s:
                    msg.status = MessageStatus.DELIVERED
        
        # Clean up queue
        self._tx_queue = [m for m in self._tx_queue if m.status in [MessageStatus.QUEUED, MessageStatus.TRANSMITTING]]
