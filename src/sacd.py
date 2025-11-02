from parser import PacketParser

class SACDPacket(PacketParser):

    frame_parts = {
        "IDS": 3,
        "FRAME#": 4,
        "HK_ID": 1,
        "CDH": 272,
        "MM1": 150,
        "MM2": 150,
        "ACS": 1024,
        "PCS": 1024,
        "AQUARIUS": 500,
        "HSC": 120,
        "TDP": 150,
        "PAD": 600,
        "CRC": 2
    }

    _fields = {
        'vBatAverage': {'section': 'PCS', 'position': 750, 'size': 2, 'k': 0.01873128, 'offset': -38.682956, 'unit': 'V'},
        'OBT': {'section': 'CDH', 'position': 92, 'size': 4, 'unit': 'GPS Time'},
        # Another field defined in order to print the OBT in seconds instead of date
        'OBT_s': {'section': 'CDH', 'position': 92, 'size': 4, 'unit': 'Seconds'}
    }

    # Precompute CRC16/BUYPASS table
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
        """Compute CRC-16/BUYPASS (poly=0x8005, init=0x0000)."""
        crc = init_crc
        table = SACDPacket._CRC16_BUYPASS_TABLE
        for byte in data:
            idx = ((crc >> 8) ^ byte) & 0xFF
            crc = ((crc << 8) ^ table[idx]) & 0xFFFF
        return crc

    def __init__(self, data: bytes, packet_size: int = 4000):
        super().__init__(
            data,
            packet_size,
            endianness="big",
            sections=SACDPacket.frame_parts,
            crc_function=SACDPacket.crc16_buypass
        )

    def get_ordering_key(self, packet: dict):
        """Return OBT as ordering key."""
        return self.get_telemetry_value_by_name("OBT", packet)