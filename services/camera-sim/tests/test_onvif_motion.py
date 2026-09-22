import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from camera_sim.onvif_motion import build_notify_envelope, send_notify

NS = {
    "s": "http://www.w3.org/2003/05/soap-envelope",
    "wsnt": "http://docs.oasis-open.org/wsn/b-2",
    "tt": "http://www.onvif.org/ver10/schema",
}


def test_build_notify_envelope_active_motion():
    envelope = build_notify_envelope(
        motion_active=True,
        producer_address="http://10.10.10.101/onvif/device_service",
        video_source_token="VideoSourceToken",
        when=datetime(2026, 9, 22, 12, 0, 0, tzinfo=timezone.utc),
    )

    root = ET.fromstring(envelope)
    topic = root.find(".//wsnt:Topic", NS)
    assert topic.text == "tns1:VideoSource/MotionAlarm"

    message = root.find(".//tt:Message", NS)
    assert message.get("UtcTime") == "2026-09-22T12:00:00Z"

    data_item = root.find(".//tt:Data/tt:SimpleItem", NS)
    assert data_item.get("Name") == "State"
    assert data_item.get("Value") == "true"

    source_item = root.find(".//tt:Source/tt:SimpleItem", NS)
    assert source_item.get("Value") == "VideoSourceToken"


def test_build_notify_envelope_inactive_motion():
    envelope = build_notify_envelope(
        motion_active=False,
        producer_address="http://10.10.10.101/onvif/device_service",
        video_source_token="VideoSourceToken",
    )
    root = ET.fromstring(envelope)
    data_item = root.find(".//tt:Data/tt:SimpleItem", NS)
    assert data_item.get("Value") == "false"


def test_send_notify_posts_soap_content_type():
    calls = []
    send_notify(
        "http://example.invalid/onvif",
        "<Envelope/>",
        post=lambda url, data, headers, timeout: calls.append((url, data, headers, timeout)),
    )
    (url, data, headers, _) = calls[0]
    assert url == "http://example.invalid/onvif"
    assert data == b"<Envelope/>"
    assert headers["Content-Type"] == "application/soap+xml; charset=UTF-8"
