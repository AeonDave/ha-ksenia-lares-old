"""Unit tests for Lares output XML parsing and shutter pairing.

These tests use in-memory fixtures and never contact the panel.
"""
from conftest import load_module

outputs = load_module("outputs")
pair_shutters = outputs.pair_shutters
parse_outputs_description = outputs.parse_outputs_description
parse_outputs_status = outputs.parse_outputs_status


DESCRIPTION_XML = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
<outputsDescription>
   <output>Not Used</output>
   <output></output>
   <output></output>
   <output></output>
   <output>LUCE CAMERETTA</output>
   <output>TAPP SU INGRESSO</output>
   <output>TAPP GIU INGRESSO</output>
   <output>TAPP SU SALA</output>
   <output>TAPP GIU SALA</output>
   <output>TAPP GIU CAMERA</output>
   <output>TAPP SU CAMERA</output>
   <output>TAPP SU P.FIN CUCINA</output>
   <output>TAPP GIU P.FIN CUCINA</output>
</outputsDescription>
"""

STATUS_XML = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
<outputsStatus>
    <output>
        <status>OFF</status>
        <type>DIGITAL</type>
        <value>0</value>
        <noPIN>FALSE</noPIN>
        <remoteControl>FALSE</remoteControl>
    </output>
    <output>
        <status>ON</status>
        <type>DIGITAL</type>
        <value>1</value>
        <noPIN>TRUE</noPIN>
        <remoteControl>TRUE</remoteControl>
    </output>
</outputsStatus>
"""


def test_parse_description_skips_empty_keeps_named_indexes():
    descriptions = parse_outputs_description(DESCRIPTION_XML)
    assert descriptions[0] == "Not Used"
    assert 1 not in descriptions
    assert descriptions[4] == "LUCE CAMERETTA"
    assert descriptions[5] == "TAPP SU INGRESSO"


def test_parse_status_fields():
    statuses = parse_outputs_status(STATUS_XML)
    assert len(statuses) == 2
    assert statuses[0].status == "OFF"
    assert statuses[0].remote_control == "FALSE"
    assert statuses[1].status == "ON"
    assert statuses[1].value == "1"
    assert statuses[1].remote_control == "TRUE"


def test_pair_shutters_by_room_name_not_adjacent_ids():
    descriptions = parse_outputs_description(DESCRIPTION_XML)
    pairs = {pair.name: pair for pair in pair_shutters(descriptions)}
    assert set(pairs) == {"INGRESSO", "SALA", "CAMERA", "P.FIN CUCINA"}
    assert pairs["INGRESSO"].su_id == 5
    assert pairs["INGRESSO"].giu_id == 6
    assert pairs["CAMERA"].su_id == 10
    assert pairs["CAMERA"].giu_id == 9
    assert pairs["CAMERA"].unique_id == "cover-9-10"
    assert pairs["INGRESSO"].unique_id == "cover-5-6"


def test_open_close_follow_house_wiring_not_panel_labels():
    """Old Lovelace Apri/Chiudi is the physical source of truth.

    Default: Open pulses TAPP GIU, Close pulses TAPP SU.
    CAMERA is the opposite. CAMERETTA stays on the default mapping.
    """
    descriptions = parse_outputs_description(DESCRIPTION_XML)
    pairs = {pair.name: pair for pair in pair_shutters(descriptions)}
    ingresso = pairs["INGRESSO"]
    assert ingresso.up_id == ingresso.giu_id == 6
    assert ingresso.down_id == ingresso.su_id == 5
    camera = pairs["CAMERA"]
    assert camera.up_id == camera.su_id == 10
    assert camera.down_id == camera.giu_id == 9


def test_unpaired_shutter_is_ignored():
    descriptions = {20: "TAPP SU SOLO", 21: "LUCE CUCINA"}
    assert pair_shutters(descriptions) == []


def test_live_panel_shutter_names_pair_seven_covers():
    """Names captured read-only from the house panel XML (no live command)."""
    descriptions = {
        4: "LUCE CAMERETTA",
        20: "TAPP SU INGRESSO",
        21: "TAPP GIU INGRESSO",
        22: "TAPP SU SALA",
        23: "TAPP GIU SALA",
        24: "TAPP SU CUCINA",
        25: "TAPP GIU CUCINA",
        26: "TAPP SU P.FIN CUCINA",
        27: "TAPP GIU P.FIN CUCINA",
        28: "TAPP SU CAMERETTA",
        29: "TAPP GIU CAMERETTA",
        30: "TAPP SU BAGNO",
        31: "TAPP GIU BAGNO",
        37: "TAPP GIU CAMERA",
        38: "TAPP SU CAMERA",
    }
    pairs = {pair.name: pair for pair in pair_shutters(descriptions)}
    assert len(pairs) == 7
    assert pairs["INGRESSO"].up_id == 21
    assert pairs["INGRESSO"].down_id == 20
    assert pairs["CAMERA"].up_id == 38
    assert pairs["CAMERA"].down_id == 37
    assert pairs["CAMERETTA"].up_id == 29
    assert pairs["CAMERETTA"].down_id == 28
    assert pairs["CAMERA"].unique_id == "cover-37-38"
    assert pairs["INGRESSO"].unique_id == "cover-20-21"
