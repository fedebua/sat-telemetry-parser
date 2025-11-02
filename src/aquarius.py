from parser import PacketParser

class AquariusPacket(PacketParser):

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

    # Precompute CRC16/BUYPASS Table
    _CRC16_BUYPASS_TABLE = []
    _POLY = 0x8005

    # Build the table once at class load time to speed up CRC calculations
    for byte in range(256):
        crc = byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ _POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
        _CRC16_BUYPASS_TABLE.append(crc)

    def __init__(self, data, packet_size):
        super().__init__(data, packet_size, endianness = 'big', sections = self.frame_parts)

    @staticmethod
    def crc16_buypass(data: bytes, init_crc: int = 0x0000):
        # After trying several CRC16 variants, it was concluded that
        # the CRC algorithm used by this telemetry packet was CRC16 BuyPass
        crc = init_crc
        table = AquariusPacket._CRC16_BUYPASS_TABLE
        for byte in data:
            idx = ((crc >> 8) ^ byte) & 0xFF
            crc = ((crc << 8) ^ table[idx]) & 0xFFFF
        return crc

    def get_packets(self, packets_with_sections: bool = True, check_crc: bool = True):
        packets = super().get_packets()
        if not packets_with_sections or not check_crc or ('CRC' not in AquariusPacket.frame_parts):
            return packets

        for i, pkt in enumerate(packets):
            crc_data = b"".join(pkt[k] for k in AquariusPacket.frame_parts if k != "CRC")
            expected_crc = int.from_bytes(pkt["CRC"], self.endianness)
            computed_crc = self.crc16_buypass(crc_data)

            if computed_crc != expected_crc:
                raise RuntimeError(
                    f"CRC mismatch in packet {i}: expected 0x{expected_crc:04X}, got 0x{computed_crc:04X}"
                )

        return packets