import asyncio
import logging
from typing import Optional

import aiohttp
import netifaces
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from lxml import etree

from .const import *

_LOGGER = logging.getLogger(__name__)


class LaresBase:

    def __init__(self, data) -> None:
        self._ip: str = data["host"]
        self._port: str = data["port"]
        self._schema: str = "http://"
        self._host: str = f"{self._schema}{self._ip}:{self._port}"
        self._auth: aiohttp.BasicAuth = aiohttp.BasicAuth(data["username"], data["password"])

    async def general_info(self) -> Optional[dict[str, str]]:
        response = await self.get(GENERAL_INFO)
        if response is None:
            return None
        
        interf = netifaces.interfaces()
        if 'eth0' in interf:
            mac = netifaces.ifaddresses('eth0')[netifaces.AF_LINK][0]['addr']
        unique_id: str = mac if mac else f"{self._ip}:{self._port}"

        try:
            info = {
                "mac": mac or "",
                "id": unique_id,
                "name": response.xpath(XPATH_GENERAL_INFO_NAME)[0].text.strip(),
                "info": response.xpath(XPATH_GENERAL_INFO_INFO)[0].text.strip(),
                "version": response.xpath(XPATH_GENERAL_INFO_VERSION)[0].text.strip(),
                "revision": response.xpath(XPATH_GENERAL_INFO_REVISION)[0].text.strip(),
                "build": response.xpath(XPATH_GENERAL_INFO_BUILD)[0].text.strip(),
            }
        except IndexError as err:
            _LOGGER.error("Error parsing general info: %s", err)
            return None

        return info

    async def basis_info(self) -> Optional[dict[str, str]]:
        response = await self.get(BASIS_INFO)
        if response is None:
            return None

        try:
            info = {
                "askPin": response.xpath(XPATH_BASIS_INFO_ASKPIN)[0].text,
                "PINToUse": response.xpath(XPATH_BASIS_INFO_PINTOUSE)[0].text,
                "PINTimeout": response.xpath(XPATH_BASIS_INFO_PINTIMEOUT)[0].text,
                "startFromMap": response.xpath(XPATH_BASIS_INFO_STARTFROMMAP)[0].text,
            }
        except IndexError as err:
            _LOGGER.error("Error parsing basis info: %s", err)
            return None

        return info

    async def device_info(self) -> Optional[dict[str, str]]:
        device_info = await self.general_info()
        if device_info is None:
            return None

        info = {
            "identifiers": {(DOMAIN, device_info["id"])},
            "name": device_info["name"],
            "manufacturer": device_info["info"],
            "model": device_info["name"],
            "sw_version": f'{device_info["version"]}.{device_info["revision"]}.{device_info["build"]}',
            "lares_version": device_info["name"].split()[-1],
        }
        if device_info["mac"]:
            info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(device_info["mac"]))}

        return info

    async def outputs_descriptions(self, device_info: dict[str, str]) -> Optional[dict[int, str]]:
        version = device_info.get("lares_version")
        response = await self.get(f"{OUTPUTS_DESCRIPTION}{version}.xml")
        if response is None:
            return None

        outputs = response.xpath(XPATH_OUTPUTS_DESCRIPTION)
        outputs_dict: dict[int, str] = {}
        for i, output in enumerate(outputs):
            if output.text:
                outputs_dict[i] = output.text
        return outputs_dict

    async def zone_descriptions(self, device_info: dict[str, str]) -> Optional[list[str]]:
        version = device_info.get("lares_version")
        response = await self.get(f"{ZONES_DESCRIPTION}{version}.xml")
        if response is None:
            return None

        zones = response.xpath(XPATH_ZONES_DESCRIPTION)
        return [zone.text for zone in zones if zone.text]

    async def outputs_status(self, device_info: dict[str, str]) -> Optional[list[dict[str, str]]]:
        version = device_info.get("lares_version")
        response = await self.get(f"{OUTPUTS_STATUS}{version}.xml")
        if response is None:
            return None

        outputs = response.xpath(XPATH_OUTPUTS_STATUS)
        status_list: list[dict[str, str]] = []
        for output in outputs:
            try:
                status_list.append({
                    "status": output.find("status").text,
                    "type": output.find("type").text,
                    "value": output.find("value").text,
                    "noPIN": output.find("noPIN").text,
                    "remoteControl": output.find("remoteControl").text,
                })
            except AttributeError as err:
                _LOGGER.error("Error parsing outputs_status: %s", err)
        return status_list

    async def zones_status(self, device_info: dict[str, str]) -> Optional[list[dict[str, str]]]:
        version = device_info.get("lares_version")
        response = await self.get(f"{ZONES_STATUS}{version}.xml")
        if response is None:
            return None

        zones = response.xpath(XPATH_ZONES_STATUS)
        status_list: list[dict[str, str]] = []
        for zone in zones:
            try:
                status_list.append({
                    "status": zone.find("status").text,
                    "bypass": zone.find("bypass").text,
                    "alarm": zone.find("alarm").text,
                })
            except AttributeError as err:
                _LOGGER.error("Error parsing zones_status: %s", err)
        return status_list

    async def command_output(self, pin: str, idx: str, value: str) -> Optional[list[str]]:
        url_command = f"{GET_COMMAND}?cmd=setOutput&pin={pin}&outputId={idx}&outputValue={value}"
        response = await self.get(url_command)
        if response is None:
            return None

        zones = response.xpath(XPATH_ZONES_DESCRIPTION)
        return [zone.text for zone in zones if zone.text]

    async def get(self, path) -> Optional[etree.Element]:
        url = f"{self._host}/xml/{path}"
        try:
            async with aiohttp.ClientSession(auth=self._auth) as session:
                async with session.get(url=url) as response:
                    response.raise_for_status()
                    xml = await response.read()
                    return etree.fromstring(xml)
        except aiohttp.ClientResponseError as cre:
            _LOGGER.debug("Host %s responded with error code: %s", self._host, cre.status)
        except (aiohttp.ClientError, aiohttp.ClientConnectorError, asyncio.TimeoutError) as conn_err:
            _LOGGER.debug("Host %s connection error: %s", self._host, str(conn_err))
        except Exception as ex:
            _LOGGER.debug("Host %s: unknown exception occurred: %s", self._host, str(ex))
