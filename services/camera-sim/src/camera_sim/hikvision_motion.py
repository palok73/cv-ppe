"""Simulates a Hikvision-style motion alarm push (ISAPI "HTTP Listening" mode).

A real camera configured with an HTTP listening host
(``PUT /ISAPI/Event/notification/httpHosts/<id>``) POSTs an
``EventNotificationAlert`` XML body -- optionally as a ``multipart/mixed``
message with an attached JPEG snapshot -- to the configured host each time an
event fires. This reproduces that payload shape closely enough for pipeline
testing; it is not a byte-exact reproduction of Hikvision's ISAPI schema.

Field names and structure are based on Hikvision's public ISAPI XML
reference (EventNotificationAlert v1.0/v2.0) and the "HTTP listening mode"
integration guides, not a formal spec grant.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import requests

_XML_V1_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<EventNotificationAlert version="1.0" xmlns="http://www.hikvision.com/ver10/XMLSchema">
    <ipAddress>{ip_address}</ipAddress>
    <portNo>{port}</portNo>
    <protocol>{protocol}</protocol>
    <macAddress>{mac_address}</macAddress>
    <channelID>{channel}</channelID>
    <dateTime>{date_time}</dateTime>
    <activePostCount>{active_post_count}</activePostCount>
    <eventType>VMD</eventType>
    <eventState>{event_state}</eventState>
    <eventDescription>Motion Alarm</eventDescription>
    <DetectionRegionList>
        <DetectionRegionEntry>
            <regionID>1</regionID>
            <sensitivityLevel>60</sensitivityLevel>
        </DetectionRegionEntry>
    </DetectionRegionList>
</EventNotificationAlert>
"""

_XML_V2_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<EventNotificationAlert version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
    <channelID>{channel}</channelID>
    <dateTime>{date_time}</dateTime>
    <activePostCount>{active_post_count}</activePostCount>
    <eventType>VMD</eventType>
    <eventState>{event_state}</eventState>
    <eventDescription>Motion Alarm</eventDescription>
</EventNotificationAlert>
"""


def _iso8601_with_colon_offset(when: datetime) -> str:
    # e.g. 2026-09-22T14:32:11+02:00 -- Python's %z gives +0200, ISAPI uses +02:00.
    raw = when.strftime("%Y-%m-%dT%H:%M:%S%z")
    return f"{raw[:-2]}:{raw[-2:]}" if raw[-5] in "+-" else raw


def build_event_xml(
    *,
    xml_version: str,
    channel: int,
    event_state: str,
    ip_address: str,
    port: int,
    mac_address: str,
    protocol: str,
    active_post_count: int = 1,
    when: datetime | None = None,
) -> str:
    when = when or datetime.now(timezone.utc).astimezone()
    template = _XML_V1_TEMPLATE if xml_version == "1.0" else _XML_V2_TEMPLATE
    return template.format(
        ip_address=ip_address,
        port=port,
        protocol=protocol,
        mac_address=mac_address,
        channel=channel,
        date_time=_iso8601_with_colon_offset(when),
        active_post_count=active_post_count,
        event_state=event_state,
    )


def send_event(
    target_url: str,
    xml_body: str,
    *,
    snapshot_jpeg: bytes | None = None,
    timeout: float = 5.0,
    post: Callable = requests.post,
) -> None:
    if snapshot_jpeg is None:
        post(
            target_url,
            data=xml_body.encode("utf-8"),
            headers={"Content-Type": 'application/xml; charset="UTF-8"'},
            timeout=timeout,
        )
        return

    boundary = "boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Type: application/xml; charset="UTF-8"\r\n\r\n'
        f"{xml_body}\r\n"
        f"--{boundary}\r\n"
        "Content-Type: image/jpeg\r\n\r\n"
    ).encode()
    body += snapshot_jpeg
    body += f"\r\n--{boundary}--\r\n".encode()
    post(
        target_url,
        data=body,
        headers={"Content-Type": f"multipart/mixed; boundary={boundary}"},
        timeout=timeout,
    )
