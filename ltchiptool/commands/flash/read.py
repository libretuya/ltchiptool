#  Copyright (c) Kuba Szczodrzyński 2022-12-23.

from io import FileIO
from time import time

import click
from click import File

from ltchiptool import Family, SocInterface
from ltchiptool.models import FamilyParamType
from ltchiptool.util import AutoIntParamType, DevicePortParamType, graph, sizeof

from ._utils import flash_link_interactive


@click.command(short_help="Read flash contents")
@click.argument("family", type=FamilyParamType(by_parent=True))
@click.argument("file", type=File("wb"))
@click.option(
    "-d",
    "--device",
    help="Target device port (default: auto detect)",
    type=DevicePortParamType(),
    default=(),
)
@click.option(
    "-b",
    "--baudrate",
    help="UART baud rate (default: auto choose)",
    type=int,
)
@click.option(
    "-s",
    "--start",
    "offset",
    help="Starting address to read from (default: 0)",
    type=AutoIntParamType(),
)
@click.option(
    "-l",
    "--length",
    help="Length to read, in bytes (default: entire flash)",
    type=AutoIntParamType(),
)
@click.option(
    "-t",
    "--timeout",
    help="Timeout for operations in seconds (default: 20.0)",
    type=float,
    default=None,
)
@click.option(
    "-c/-C",
    "--check/--no-check",
    help="Check hash/CRC of the read data (default: True)",
    default=True,
)
@click.option(
    "-R",
    "--rom",
    help="Read from ROM instead of Flash (default: False)",
    is_flag=True,
)
def cli(
    family: Family,
    file: FileIO,
    device: str,
    baudrate: int,
    offset: int,
    length: int,
    timeout: float,
    check: bool,
    rom: bool,
):
    """
    Read flash contents to a file.

    By default, read the entire flash chip, starting at offset 0x0.

    When not specified (-d), the first UART port is used. The baud rate (-b)
    is chosen automatically, depending on the chip capabilities.

    \b
    Arguments:
      FAMILY    Chip family name/code
      FILE      Output file name
    """
    time_start = time()
    soc = SocInterface.get(family)
    flash_link_interactive(soc, device, baudrate, timeout)

    if rom:
        max_length = soc.flash_get_rom_size()
    else:
        max_length = soc.flash_get_size()

    offset = offset or 0
    length = length or (max_length - offset)

    if offset + length > max_length:
        raise ValueError(
            f"Reading length {sizeof(length)} @ 0x{offset:X} is more than "
            f"chip capacity ({sizeof(max_length)})",
        )

    if rom:
        graph(0, f"Reading ROM ({sizeof(length)}) to '{file.name}'")
    else:
        graph(0, f"Reading {sizeof(length)} @ 0x{offset:X} to '{file.name}'")

    with click.progressbar(length=length, width=64) as bar:
        for chunk in soc.flash_read_raw(offset, length, verify=check, use_rom=rom):
            file.write(chunk)
            bar.update(len(chunk))

    duration = time() - time_start
    graph(1, f"Finished in {duration:.3f} s")
