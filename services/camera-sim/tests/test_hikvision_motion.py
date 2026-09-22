import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from camera_sim.hikvision_motion import build_event_xml, send_event

WHEN = datetime(2026, 9, 22, 14, 32, 11, tzinfo=timezone(timedelta(hours=2)))


def test_build_event_xml_v1_includes_device_fields_and_colon_offset():
    xml_body = build_event_xml(
        xml_version="1.0",
        channel=3,
        event_state="active",
        ip_address="10.10.10.101",
        port=80,
        mac_address="c4:79:ba:11:22:01",
        protocol="HTTP",
        active_post_count=2,
        when=WHEN,
    )

    root = ET.fromstring(xml_body)
    assert root.tag.endswith("EventNotificationAlert")
    assert root.findtext("{*}channelID") == "3"
    assert root.findtext("{*}eventType") == "VMD"
    assert root.findtext("{*}eventState") == "active"
    assert root.findtext("{*}ipAddress") == "10.10.10.101"
    assert root.findtext("{*}macAddress") == "c4:79:ba:11:22:01"
    assert root.findtext("{*}activePostCount") == "2"
    assert root.findtext("{*}dateTime") == "2026-09-22T14:32:11+02:00"
    assert root.find("{*}DetectionRegionList/{*}DetectionRegionEntry/{*}regionID") is not None


def test_build_event_xml_v2_omits_device_fields():
    xml_body = build_event_xml(
        xml_version="2.0",
        channel=1,
        event_state="inactive",
        ip_address="10.10.10.101",
        port=80,
        mac_address="c4:79:ba:11:22:01",
        protocol="HTTP",
        when=WHEN,
    )

    root = ET.fromstring(xml_body)
    assert root.findtext("{*}eventState") == "inactive"
    assert root.find("{*}ipAddress") is None
    assert root.find("{*}DetectionRegionList") is None


def test_send_event_without_snapshot_posts_plain_xml():
    calls = []
    send_event(
        "http://example.invalid/hik",
        "<EventNotificationAlert/>",
        post=lambda url, data, headers, timeout: calls.append((url, data, headers, timeout)),
    )

    (url, data, headers, _timeout) = calls[0]
    assert url == "http://example.invalid/hik"
    assert data == b"<EventNotificationAlert/>"
    assert headers["Content-Type"] == 'application/xml; charset="UTF-8"'


def test_send_event_with_snapshot_posts_multipart():
    calls = []
    send_event(
        "http://example.invalid/hik",
        "<EventNotificationAlert/>",
        snapshot_jpeg=b"\xff\xd8\xff\xd9",
        post=lambda url, data, headers, timeout: calls.append((url, data, headers, timeout)),
    )

    (_, data, headers, _) = calls[0]
    assert headers["Content-Type"].startswith("multipart/mixed; boundary=")
    assert b"Content-Type: image/jpeg" in data
    assert b"\xff\xd8\xff\xd9" in data
    assert b"<EventNotificationAlert/>" in data
