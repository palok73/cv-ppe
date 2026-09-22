"""Simulates an ONVIF motion event push (WS-BaseNotification ``Notify``).

A real ONVIF device with a push subscription sends a SOAP ``wsnt:Notify``
message to the subscriber's endpoint whenever a ``tns1:VideoSource/MotionAlarm``
event fires, carrying a boolean ``State`` in ``tt:Data``. This builds that
envelope closely enough for pipeline testing; it does not implement the
WS-Subscription handshake (CreatePullPointSubscription/Subscribe) itself --
the target URL is configured directly, as if a subscription already exists.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

import requests

_NOTIFY_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<SOAP-ENV:Envelope
    xmlns:SOAP-ENV="http://www.w3.org/2003/05/soap-envelope"
    xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"
    xmlns:wsa5="http://www.w3.org/2005/08/addressing"
    xmlns:tt="http://www.onvif.org/ver10/schema"
    xmlns:tns1="http://www.onvif.org/ver10/topics">
  <SOAP-ENV:Header/>
  <SOAP-ENV:Body>
    <wsnt:Notify>
      <wsnt:NotificationMessage>
        <wsnt:Topic Dialect="http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet">tns1:VideoSource/MotionAlarm</wsnt:Topic>
        <wsnt:ProducerReference>
          <wsa5:Address>{producer_address}</wsa5:Address>
        </wsnt:ProducerReference>
        <wsnt:Message>
          <tt:Message UtcTime="{utc_time}" PropertyOperation="Changed">
            <tt:Source>
              <tt:SimpleItem Name="Source" Value="{video_source_token}"/>
            </tt:Source>
            <tt:Data>
              <tt:SimpleItem Name="State" Value="{state}"/>
            </tt:Data>
          </tt:Message>
        </wsnt:Message>
      </wsnt:NotificationMessage>
    </wsnt:Notify>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>
"""


def build_notify_envelope(
    *,
    motion_active: bool,
    producer_address: str,
    video_source_token: str,
    when: datetime | None = None,
) -> str:
    when = when or datetime.now(timezone.utc)
    utc_time = when.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _NOTIFY_TEMPLATE.format(
        producer_address=producer_address,
        utc_time=utc_time,
        video_source_token=video_source_token,
        state="true" if motion_active else "false",
    )


def send_notify(
    target_url: str,
    envelope: str,
    *,
    timeout: float = 5.0,
    post: Callable = requests.post,
) -> None:
    post(
        target_url,
        data=envelope.encode("utf-8"),
        headers={"Content-Type": "application/soap+xml; charset=UTF-8"},
        timeout=timeout,
    )
