class PacketParser:
    def __init__(self, data: bytes, packet_size: int, endianness: str, sections: dict = None):
        self.data = data
        self.packet_size = packet_size
        self.size = len(data)
        self.endianness = endianness
        self.sections = sections
        if self.size % packet_size != 0:
            raise RuntimeError(
                f"The binary file has {self.size} bytes and the packet size is "
                f"{packet_size}, meaning the file cannot be read since not all packets are complete."
            )

    def get_packets(self):
        # Split binary data into packets of size packet_size
        # If sections is None, return a list of binary packets
        # If sections is not None, return a list of dictionaries grouped by sections
        packets = [
            self.data[i:i + self.packet_size]
            for i in range(0, self.size, self.packet_size)
        ]

        # If no section breakdown requested, return raw packets
        if self.sections is None:
            return packets

        # Check sections can be grouped by packet size
        sections_size = sum(self.sections.values())
        if self.packet_size != sections_size:
            raise RuntimeError(
                f"Packet sections form a {sections_size}-byte structure, "
                f"which does not match the expected packet size of {self.packet_size}."
            )
        
        # Split each packet into its defined sections
        parsed_packets = []
        section_names = list(self.sections.keys())
        section_sizes = list(self.sections.values())

        for packet in packets:
            packet_dict = {}
            offset = 0
            for name, size in zip(section_names, section_sizes):
                packet_dict[name] = packet[offset:offset + size]
                offset += size
            parsed_packets.append(packet_dict)
        
        return parsed_packets