from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

class PacketParser:
    def __init__(self, data: bytes, packet_size: int, endianness: str = "big", sections: dict = None, crc_function=None):
        self.data = data
        self.packet_size = packet_size
        self.endianness = endianness
        self.sections = sections
        self.crc_function = crc_function
        self.size = len(data)

        if self.size % packet_size != 0:
            raise RuntimeError(
                f"The binary file has {self.size} bytes, but packet size is {packet_size}. "
                f"Not all packets are complete."
            )

    def get_packets(self, packets_with_sections: bool, check_crc: bool):

        if check_crc and (not packets_with_sections or self.sections is None):
            raise RuntimeError("CRC cannot be calculated if packets with sections flag is not True or no sections are defined")

        # Split data into fixed-size binary packets
        packets = [
            self.data[i:i + self.packet_size]
            for i in range(0, self.size, self.packet_size)
        ]

        # If no structured sections are defined, return raw packet bytes
        if not packets_with_sections or self.sections is None:
            return packets

        # Validate section layout
        sections_size = sum(self.sections.values())
        if self.packet_size != sections_size:
            raise RuntimeError(
                f"Section map defines {sections_size} bytes, expected {self.packet_size}."
            )

        # Split each packet into its defined sections
        structured_packets = []
        section_names = list(self.sections.keys())
        section_sizes = list(self.sections.values())

        for packet in packets:
            packet_dict = {}
            offset = 0
            for name, size in zip(section_names, section_sizes):
                packet_dict[name] = packet[offset:offset + size]
                offset += size
            structured_packets.append(packet_dict)

        # CRC validation (if crc_function is provided) and check CRC flag is True
        if check_crc:
            if not callable(self.crc_function):
                raise NotImplementedError("crc_function function is not defined. Cannot calculate CRC")
            if not "CRC" in self.sections:
                raise NotImplementedError("CRC is not defined in telemetry sections.  Cannot calculate CRC")

            for i, pkt in enumerate(structured_packets):
                crc_data = b"".join(pkt[name] for name in self.sections if name != "CRC")
                expected_crc = int.from_bytes(pkt["CRC"], self.endianness)
                computed_crc = self.crc_function(crc_data)
                if computed_crc != expected_crc:
                    raise RuntimeError(
                        f"CRC mismatch in packet {i}: expected 0x{expected_crc:04X}, got 0x{computed_crc:04X}"
                    )

        return structured_packets

    def get_telemetry_value_by_name(self, field_name: str, packet: dict):
        if not hasattr(self, "_fields"):
            raise RuntimeError(f"{self.__class__.__name__} must define `_fields` to use telemetry functions.")

        if field_name not in self._fields:
            valid = ", ".join(self._fields.keys())
            raise ValueError(f"Invalid field '{field_name}'. Available fields: {valid}")

        if self.sections is None:
            raise NotImplementedError("No sections are defined. Cannot get telemetry value")

        field = self._fields[field_name]
        section = field["section"]
        pos = field["position"]
        size = field["size"]
        endianness = field.get("endianness", getattr(self, "endianness", "big"))
        signed = field.get("signed", False)
        k = field.get("k", 1.0)
        offset = field.get("offset", 0.0)


        try:
            raw = packet[section][pos:pos + size]
        except KeyError:
            raise KeyError(f"Section '{section}' not found in packet.")

        if len(raw) != size:
            raise ValueError(
                f"Invalid data size for field '{field_name}': expected {size}, got {len(raw)} bytes."
            )

        value = int.from_bytes(raw, byteorder=endianness, signed=signed)
        return value * k + offset

    def get_all_telemetry_values_by_name(self, field_name: str, packets: list, get_unit: bool = False):
        if not hasattr(self, "_fields"):
            raise RuntimeError(f"{self.__class__.__name__} must define `_fields` to use telemetry functions.")
        if get_unit and 'unit' not in self._fields[field_name]:
            raise RuntimeError(f"unit is not defined in field {field_name}")

        values = [self.get_telemetry_value_by_name(field_name, pkt) for pkt in packets]
        if get_unit:
            return values, self._fields[field_name]['unit']
        return values

    def order_packets(self, packets: list):
        if not hasattr(self, "get_ordering_key") or not callable(getattr(self, "get_ordering_key")):
            raise RuntimeError(
                f"{self.__class__.__name__} must define a `get_ordering_key(packet)` method "
                f"to enable packet ordering."
            )

        try:
            return sorted(packets, key=self.get_ordering_key)
        except Exception as e:
            raise RuntimeError(f"Failed to order packets: {e}")

    def plot_telemetry_values(self, field_name: str, packets: list, x_field: str = None):
        # Validation
        if not hasattr(self, "_fields"):
            raise RuntimeError(f"{self.__class__.__name__} must define '_fields' to plot telemetry.")

        if not packets:
            raise ValueError("No packets provided to plot.")

        if field_name not in self._fields:
            valid = ", ".join(self._fields.keys())
            raise ValueError(f"Invalid field '{field_name}'. Available fields: {valid}")

        # Get Y values
        y_values, y_unit = self.get_all_telemetry_values_by_name(field_name, packets, get_unit=True)

        # Get X values
        if x_field:
            if x_field not in self._fields:
                raise ValueError(f"Invalid x_field '{x_field}'. Available fields: {', '.join(self._fields.keys())}")
            x_values, x_unit = self.get_all_telemetry_values_by_name(x_field, packets, get_unit=True)
        else:
            x_values = list(range(len(packets)))

        # Detect and convert GPS time if needed
        is_time_axis = False
        if x_field and isinstance(x_unit, str) and "gps" in x_unit.lower():
            x_values = PacketParser.convert_gps_to_datetime(x_values)
            is_time_axis = True

        # Plot
        plt.figure(figsize=(10, 5))
        plt.plot(x_values, y_values, marker="o", linestyle="-", label=field_name)

        # Axis labels
        # X axis
        if x_field:
            if is_time_axis:
                plt.xlabel(f"{x_field} [UTC Time]")
            elif x_unit:
                plt.xlabel(f"{x_field} [{x_unit}]")
            else:
                plt.xlabel(x_field)
        else:
            plt.xlabel("Packet index")

        # Y axis
        if y_unit:
            plt.ylabel(f"{field_name} [{y_unit}]")
        else:
            plt.ylabel(field_name)

        # Title and style
        plt.title(f"Telemetry Plot: {field_name} vs {x_field if x_field else 'Packet index'}")
        plt.grid(True)
        plt.legend()

        # Time formatting if applicable
        if is_time_axis:
            plt.gcf().autofmt_xdate()
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M:%S"))

        plt.tight_layout()
        plt.show()

    @staticmethod
    def convert_gps_to_datetime(gps_seconds_list):
        gps_epoch = datetime(1980, 1, 6)
        leap_seconds = 19  # as of 2025
        return [gps_epoch + timedelta(seconds=s - leap_seconds) for s in gps_seconds_list]
