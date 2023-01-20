import asyncio
import logging

import aiohttp
from getmac import get_mac_address
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, format_mac
from lxml import etree

from .const import DOMAIN, MANUFACTURER, GENERAL_INFO, OUTPUTS_DESCRIPTION, ZONES_DESCRIPTION, ZONES_STATUS, \
    XPATH_ZONES_DESCRIPTION, XPATH_OUTPUTS_DESCRIPTION, XPATH_ZONES_STATUS, OUTPUTS_STATUS, XPATH_OUTPUTS_STATUS, \
    BASIS_INFO, XPATH_GENERAL_INFO_NAME, XPATH_GENERAL_INFO_INFO, XPATH_GENERAL_INFO_VERSION, \
    XPATH_GENERAL_INFO_REVISION, XPATH_GENERAL_INFO_BUILD, XPATH_BASIS_INFO_STARTFROMMAP, XPATH_BASIS_INFO_PINTIMEOUT, \
    XPATH_BASIS_INFO_PINTOUSE, XPATH_BASIS_INFO_ASKPIN, GET_COMMAND

_LOGGER = logging.getLogger(__name__)


class LaresBase:

    def __init__(self, data: dict):
        username = data["username"]
        password = data["password"]
        host = data["host"]
        port = data["port"]
        schema = 'http://'

        self._auth = aiohttp.BasicAuth(username, password)
        self._ip = host
        self._port = port
        self._schema = schema
        self._host = f"{self._schema}{self._ip}:{self._port}"

    async def general_info(self):
        response = await self.get(GENERAL_INFO)
        if response is None:
            return None
        mac = get_mac_address(ip=self._ip)
        unique_id = str(mac)
        if mac is None:
            unique_id = f"{self._ip}:{self._port}"
        info = {
            "mac": mac,
            "id": unique_id,
            "name": response.xpath(XPATH_GENERAL_INFO_NAME)[0].text,
            "info": response.xpath(XPATH_GENERAL_INFO_INFO)[0].text,
            "version": response.xpath(XPATH_GENERAL_INFO_VERSION)[0].text,
            "revision": response.xpath(XPATH_GENERAL_INFO_REVISION)[0].text,
            "build": response.xpath(XPATH_GENERAL_INFO_BUILD)[0].text
        }
        return info

    async def basis_info(self):
        response = await self.get(BASIS_INFO)
        if response is None:
            return None
        info = {
            "askPin": response.xpath(XPATH_BASIS_INFO_ASKPIN)[0].text,
            "PINToUse": response.xpath(XPATH_BASIS_INFO_PINTOUSE)[0].text,
            "PINTimeout": response.xpath(XPATH_BASIS_INFO_PINTIMEOUT)[0].text,
            "startFromMap": response.xpath(XPATH_BASIS_INFO_STARTFROMMAP)[0].text
        }
        return info

    async def device_info(self) -> {}:
        device_info = await self.general_info()
        if device_info is None:
            return None
        info = {
            "identifiers": {(DOMAIN, device_info["id"])},
            "name": device_info["name"],
            "manufacturer": MANUFACTURER,
            "model": device_info["name"],
            "sw_version": f'{device_info["version"]}.{device_info["revision"]}.{device_info["build"]}',
            "lares_version": device_info["name"].split()[-1]
        }
        mac = device_info["mac"]
        if mac is not None:
            info["connections"] = {(CONNECTION_NETWORK_MAC, format_mac(mac))}
        return info

    async def outputs_descriptions(self, device_info: {}) -> {}:
        response = await self.get(f'{OUTPUTS_DESCRIPTION}{device_info["lares_version"]}.xml')
        if response is None:
            return None
        outputs = response.xpath(XPATH_OUTPUTS_DESCRIPTION)
        outputs_dict = {}
        for i, output in enumerate(outputs):
            if output.text is not None:
                outputs_dict[i] = output.text
        return outputs_dict

    async def zone_descriptions(self, device_info: {}):
        response = await self.get(f'{ZONES_DESCRIPTION}{device_info["lares_version"]}.xml')
        if response is None:
            return None
        zones = response.xpath(XPATH_ZONES_DESCRIPTION)
        return [zone.text for zone in zones]

    async def outputs_status(self, device_info: {}):
        response = await self.get(f'{OUTPUTS_STATUS}{device_info["lares_version"]}.xml')
        if response is None:
            return None
        outputs = response.xpath(XPATH_OUTPUTS_STATUS)
        return [
            {
                "status": output.find("status").text,
                "type": output.find("type").text,
                "value": output.find("value").text,
                "noPIN": output.find("noPIN").text,
                "remoteControl": output.find("remoteControl").text
            }
            for output in outputs
        ]

    async def zones_status(self, device_info: {}):
        response = await self.get(f'{ZONES_STATUS}{device_info["lares_version"]}.xml')
        if response is None:
            return None
        zones = response.xpath(XPATH_ZONES_STATUS)
        return [
            {
                "status": zone.find("status").text,
                "bypass": zone.find("bypass").text,
                "alarm": zone.find("alarm").text
            }
            for zone in zones
        ]

    async def command_output(self, pin: str, idx: str, value: str):
        response = await self.get(f'{GET_COMMAND}?cmd=setOutput&pin={pin}&outputId={idx}&outputValue={value}')
        if response is None:
            return None
        zones = response.xpath(XPATH_ZONES_DESCRIPTION)
        return [zone.text for zone in zones]

    async def get(self, path):
        url = f"{self._host}/xml/{path}"
        try:
            async with aiohttp.ClientSession(auth=self._auth) as session:
                async with session.get(url=url) as response:
                    if response.status != 200:
                        raise ConnectionError
                    xml = await response.read()
                    return etree.fromstring(xml)
        except ConnectionError:
            _LOGGER.debug("Host %s: Status code: %s", self._host, response.status)
        except (aiohttp.ClientError, aiohttp.ClientConnectorError, asyncio.TimeoutError) as conn_err:
            _LOGGER.debug("Host %s: Connection error: %s", self._host, str(conn_err))
        except Exception as ex:  # pylint: disable=bare-except
            _LOGGER.debug("Host %s: Unknown exception occurred: %s", self._host, str(ex))
