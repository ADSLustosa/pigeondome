import json

from pigeondome_sim.publisher import detections_topic, status_payload, status_topic


def test_topics_follow_versioned_contract() -> None:
    assert detections_topic("cam-01") == "pigeondome/v1/cam-01/detections"
    assert status_topic("cam-01") == "pigeondome/v1/cam-01/status"


def test_status_payload_is_valid_json() -> None:
    assert json.loads(status_payload("online")) == {"state": "online"}
