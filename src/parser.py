from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


class PacketParser:
    """Generic parser for fixed-size binary telemetry packets."""

    def __init__(
        self,
        data: bytes,
        packet_size: int,
        verbose: bool = False,
        endianness: str = "big",
        sections: dict = None,
        crc_function=None,
    ):
        self.data = data
        self.packet_size = packet_size
        self.verbose = verbose
        self.endianness = endianness
        self.sections = sections
        self.crc_function = crc_function
        self.size = len(data)

        if self.size % packet_size != 0:
            raise RuntimeError(
                f"Binary file has {self.size} bytes but packet size is {packet_size}, "
                "so not all packets are complete."
            )

    # -------------------------------------------------------------------------
    # Packet Extraction and CRC Validation
    # -------------------------------------------------------------------------
    def get_packets(self, packets_with_sections: bool, check_crc: bool):
        """Split binary data into packets, optionally validating CRC."""
        if check_crc and (not packets_with_sections or not self.sections):
            raise RuntimeError("Cannot compute CRC without sections defined.")

        # Split into raw packets
        packets = [
            self.data[i:i + self.packet_size]
            for i in range(0, self.size, self.packet_size)
        ]

        # Return raw packets if not structured
        if not packets_with_sections or not self.sections:
            return packets

        # Validate structure length
        if sum(self.sections.values()) != self.packet_size:
            raise RuntimeError("Section layout does not match packet size.")

        # Split each packet into named sections
        structured_packets = [
            {
                name: packet[offset:offset + size]
                for name, size, offset in zip(
                    self.sections.keys(),
                    self.sections.values(),
                    self._section_offsets()
                )
            }
            for packet in packets
        ]

        # Optional CRC check
        if check_crc:
            self._validate_crc(structured_packets)

        return structured_packets

    def _section_offsets(self):
        """Compute start offsets for each section from section sizes."""
        offsets, pos = [], 0
        for size in self.sections.values():
            offsets.append(pos)
            pos += size
        return offsets

    def _validate_crc(self, packets):
        """Validate CRC using provided crc_function, optionally showing progress if verbose=True."""
        if not callable(self.crc_function):
            raise NotImplementedError("CRC function not defined.")
        if "CRC" not in self.sections:
            raise NotImplementedError("CRC field missing in sections map.")

        total = len(packets)
        show_progress = getattr(self, "verbose", False)

        for i, pkt in enumerate(packets, start=1):
            # Progress indicator (only if verbose)
            if show_progress:
                percent = (i / total) * 100
                print(f"\rChecking CRC of packet {i}/{total} ({percent:.1f}%)", end="", flush=True)

            # Compute CRC
            data_for_crc = b"".join(pkt[name] for name in self.sections if name != "CRC")
            expected_crc = int.from_bytes(pkt["CRC"], self.endianness)
            computed_crc = self.crc_function(data_for_crc)

            if computed_crc != expected_crc:
                if show_progress:
                    print()  # newline before the error
                raise RuntimeError(
                    f"CRC mismatch in packet {i}: expected 0x{expected_crc:04X}, got 0x{computed_crc:04X}"
                )

        # Final newline and message (only if verbose)
        if show_progress:
            print("\rCRC check complete. All packets verified successfully.")

    # -------------------------------------------------------------------------
    # Telemetry Extraction
    # -------------------------------------------------------------------------
    def _require_fields(self):
        if not hasattr(self, "_fields"):
            raise RuntimeError(f"{self.__class__.__name__} must define '_fields' to use telemetry functions.")

    def get_telemetry_value_by_name(self, field_name: str, packet: dict):
        """Extract a single telemetry field value from one packet."""
        self._require_fields()

        if field_name not in self._fields:
            valid = ", ".join(self._fields.keys())
            raise ValueError(f"Invalid field '{field_name}'. Available: {valid}")

        if not self.sections:
            raise NotImplementedError("No sections defined for telemetry extraction.")

        field = self._fields[field_name]
        try:
            raw = packet[field["section"]][field["position"]:field["position"] + field["size"]]
        except KeyError:
            raise KeyError(f"Section '{field['section']}' not found in packet.")

        if len(raw) != field["size"]:
            raise ValueError(f"Field '{field_name}' size mismatch: expected {field['size']}, got {len(raw)}")

        value = int.from_bytes(
            raw,
            byteorder=field.get("endianness", self.endianness),
            signed=field.get("signed", False),
        )

        return value * field.get("k", 1.0) + field.get("offset", 0.0)

    def get_all_telemetry_values_by_name(self, field_name: str, packets: list, return_unit: bool = False):
        """Extract a field's value from all packets, optionally returning its unit."""
        self._require_fields()

        if return_unit and "unit" not in self._fields[field_name]:
            raise RuntimeError(f"Field '{field_name}' missing 'unit' definition.")

        values = [self.get_telemetry_value_by_name(field_name, pkt) for pkt in packets]
        return (values, self._fields[field_name].get("unit")) if return_unit else values

    # -------------------------------------------------------------------------
    # Packet Ordering
    # -------------------------------------------------------------------------
    def order_packets(self, packets: list):
        """Order packets using subclass-defined key function."""
        if not hasattr(self, "get_ordering_key") or not callable(getattr(self, "get_ordering_key")):
            raise RuntimeError(f"{self.__class__.__name__} must define a 'get_ordering_key(packet)' method.")
        return sorted(packets, key=self.get_ordering_key)

    # -------------------------------------------------------------------------
    # Plotting Utilities
    # -------------------------------------------------------------------------
    def plot_telemetry_values(self, field_name: str, packets: list, x_field: str = None):
        """Plot telemetry field values against another field or packet index."""
        self._require_fields()

        if not packets:
            raise ValueError("No packets provided to plot.")
        if field_name not in self._fields:
            raise ValueError(f"Invalid field '{field_name}'.")

        # Y-axis data
        y_values, y_unit = self.get_all_telemetry_values_by_name(field_name, packets, return_unit=True)

        # X-axis data
        if x_field:
            if x_field not in self._fields:
                raise ValueError(f"Invalid x_field '{x_field}'.")
            x_values, x_unit = self.get_all_telemetry_values_by_name(x_field, packets, return_unit=True)
        else:
            x_values, x_unit = list(range(len(packets))), None

        # GPS time conversion
        is_time_axis = False
        if x_field and isinstance(x_unit, str) and "gps" in x_unit.lower():
            x_values = self.convert_gps_to_datetime(x_values)
            is_time_axis = True

        # Plot
        plt.figure(figsize=(10, 5))
        plt.plot(x_values, y_values, marker="o", linestyle="-", label=field_name)

        # Axis labels with units
        xlabel = x_field or "Packet index"
        ylabel = field_name
        if is_time_axis:
            xlabel += " [UTC Time]"
        elif x_field and x_unit:
            xlabel += f" [{x_unit}]"
        if y_unit:
            ylabel += f" [{y_unit}]"

        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.title(f"{field_name} vs {x_field or 'Packet index'}")
        plt.grid(True)
        plt.legend()

        if is_time_axis:
            plt.gcf().autofmt_xdate()
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M:%S"))

        plt.tight_layout()
        plt.show()

    # -------------------------------------------------------------------------
    # Utility Functions
    # -------------------------------------------------------------------------
    @staticmethod
    def convert_gps_to_datetime(gps_seconds_list):
        """Convert GPS seconds since 1980-01-06 to UTC datetime list."""
        gps_epoch = datetime(1980, 1, 6)
        leap_seconds = 19  # current offset
        return [gps_epoch + timedelta(seconds=s - leap_seconds) for s in gps_seconds_list]
