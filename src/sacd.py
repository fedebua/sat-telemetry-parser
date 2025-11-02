from parser import PacketParser


class SACDPacket(PacketParser):
    """
    Specialized parser for SAC-D / Aquarius satellite telemetry.

    Defines frame structure, telemetry fields, CRC algorithm, and
    packet ordering rules based on On-Board Time (OBT).
    """

    frame_parts = {
        "IDS": 3, "FRAME#": 4, "HK_ID": 1, "CDH": 272,
        "MM1": 150, "MM2": 150, "ACS": 1024, "PCS": 1024,
        "AQUARIUS": 500, "HSC": 120, "TDP": 150, "PAD": 600, "CRC": 2,
    }

    _fields = {
        "vBatAverage": {
            "section": "PCS", "position": 750, "size": 2,
            "k": 0.01873128, "offset": -38.682956, "unit": "V",
        },
        "OBT": {"section": "CDH", "position": 92, "size": 4, "unit": "GPS Time"},
        "OBT_s": {"section": "CDH", "position": 92, "size": 4, "unit": "Seconds"},
    }

    _POLY = 0x8005
    _CRC16_BUYPASS_TABLE = []
    for byte in range(256):
        crc = byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ _POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
        _CRC16_BUYPASS_TABLE.append(crc)

    @staticmethod
    def crc16_buypass(data: bytes, init_crc: int = 0x0000) -> int:
        """
        Compute CRC-16/BUYPASS checksum.

        Parameters
        ----------
        data : bytes
            Input byte sequence.
        init_crc : int, optional
            Initial CRC register value.

        Returns
        -------
        int
            The computed CRC-16 value.
        """
        crc = init_crc
        for byte in data:
            idx = ((crc >> 8) ^ byte) & 0xFF
            crc = ((crc << 8) ^ SACDPacket._CRC16_BUYPASS_TABLE[idx]) & 0xFFFF
        return crc

    def __init__(self, data: bytes, packet_size: int = 4000, verbose: bool = False):
        """
        Initialize a SAC-D packet parser.

        Parameters
        ----------
        data : bytes
            Binary telemetry stream.
        packet_size : int, optional
            Packet length in bytes.
        verbose : bool, optional
            Show CRC progress during validation.
        """
        super().__init__(
            data,
            packet_size,
            verbose=verbose,
            endianness="big",
            sections=SACDPacket.frame_parts,
            crc_function=SACDPacket.crc16_buypass,
        )

    def get_ordering_key(self, packet: dict):
        """
        Define packet sorting key.

        Returns
        -------
        int or float
            The On-Board Time value used for ordering.
        """
        return self.get_telemetry_value_by_name("OBT", packet)
