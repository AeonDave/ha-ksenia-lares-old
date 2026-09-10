"""Parse Lares <v4 output XML and pair shutter pulse channels.

Kept free of Home Assistant imports so unit tests can run without HA.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from xml.etree import ElementTree

_SHUTTER_NAME = re.compile(
    r"^TAPP\s+(SU|GIU|GIÙ)\s+(.+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class OutputStatus:
    status: str
    type: str
    value: str
    no_pin: str
    remote_control: str


@dataclass(frozen=True)
class ShutterPair:
    name: str
    up_id: int
    down_id: int

    @property
    def unique_id(self) -> str:
        lo, hi = sorted((self.up_id, self.down_id))
        return f"cover-{lo}-{hi}"


def parse_outputs_description(xml: bytes) -> dict[int, str]:
    root = ElementTree.fromstring(xml)
    outputs: dict[int, str] = {}
    for index, node in enumerate(root.findall("output")):
        text = (node.text or "").strip()
        if text:
            outputs[index] = text
    return outputs


def parse_outputs_status(xml: bytes) -> list[OutputStatus]:
    root = ElementTree.fromstring(xml)
    statuses: list[OutputStatus] = []
    for node in root.findall("output"):
        statuses.append(
            OutputStatus(
                status=_child_text(node, "status"),
                type=_child_text(node, "type"),
                value=_child_text(node, "value"),
                no_pin=_child_text(node, "noPIN"),
                remote_control=_child_text(node, "remoteControl"),
            )
        )
    return statuses


def pair_shutters(descriptions: dict[int, str]) -> list[ShutterPair]:
    """Pair TAPP SU / TAPP GIU outputs that share the same room name."""
    ups: dict[str, int] = {}
    downs: dict[str, int] = {}
    for index, raw_name in descriptions.items():
        parsed = _parse_shutter_name(raw_name)
        if parsed is None:
            continue
        direction, room = parsed
        if direction == "SU":
            ups[room] = index
        else:
            downs[room] = index

    pairs: list[ShutterPair] = []
    for room in sorted(set(ups) & set(downs)):
        pairs.append(ShutterPair(name=room, up_id=ups[room], down_id=downs[room]))
    return pairs


def is_shutter_output_name(name: str) -> bool:
    return _parse_shutter_name(name) is not None


def _parse_shutter_name(name: str) -> tuple[str, str] | None:
    match = _SHUTTER_NAME.match(name.strip())
    if not match:
        return None
    direction = "SU" if match.group(1).upper() == "SU" else "GIU"
    room = " ".join(match.group(2).split())
    return direction, room


def _child_text(node: ElementTree.Element, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()
