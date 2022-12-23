# Copyright (c) Kuba Szczodrzyński 2022-07-29.

from abc import ABC
from io import BytesIO

from ltchiptool import SocInterface
from ltchiptool.util import graph
from ltchiptool.util.intbin import letoint
from uf2tool import UploadContext

from .util.rtltool import RTLXMD


class AmebaZFlash(SocInterface, ABC):
    def build_protocol(self):
        return RTLXMD(port=self.port, timeout=self.link_timeout)

    def flash_write_uf2(
        self,
        ctx: UploadContext,
    ):
        rtl = self.build_protocol()
        graph(2, f"Connecting to {self.port}...")
        if not rtl.connect():
            raise ValueError(f"Failed to connect on port {self.port}")

        # read system data to get active OTA index
        io = BytesIO()
        if not rtl.ReadBlockFlash(io, offset=0x9000, size=256):
            raise ValueError("Failed to read from 0x9000")
        # get as bytes
        system = io.getvalue()
        if len(system) != 256:
            raise ValueError(
                f"Length invalid while reading from 0x9000 - {len(system)}"
            )
        # read OTA switch value
        ota_switch = bin(letoint(system[4:8]))[2:]
        # count 0-bits
        ota_idx = 1 + (ota_switch.count("0") % 2)
        # validate OTA2 address in system data
        if ota_idx == 2:
            ota2_addr = letoint(system[0:4]) & 0xFFFFFF
            part_addr = ctx.get_offset("ota2", 0)
            if ota2_addr != part_addr:
                raise ValueError(
                    f"Invalid OTA2 address on chip - found {ota2_addr}, expected {part_addr}"
                )

        graph(2, f"Flashing image to OTA {ota_idx}...")
        # collect continuous blocks of data
        parts = ctx.collect(ota_idx=ota_idx)
        # write blocks to flash
        for offs, data in parts.items():
            offs |= 0x8000000
            length = len(data.getvalue())
            data.seek(0)
            graph(2, f"Writing {length} bytes to 0x{offs:06x}")
            if not rtl.WriteBlockFlash(data, offs, length):
                raise ValueError(f"Writing failed at 0x{offs:x}")
        return True