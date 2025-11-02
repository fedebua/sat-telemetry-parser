import argparse
from sacd import SACDPacket


def main():
    """
    Command-line interface for SAC-D / Aquarius telemetry parsing.

    Reads a binary telemetry file, optionally validates CRCs, orders packets
    by On-Board Time (OBT), and generates three example plots of battery voltage
    versus time, seconds, and packet index.
    """
    parser = argparse.ArgumentParser(description="Parse SAC-D / Aquarius telemetry binary file.")
    parser.add_argument("file_path", help="Path to the telemetry binary file")
    parser.add_argument("--check-crc", action="store_true",
                        help="Enable CRC validation (default: disabled)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Increase output verbosity (shows CRC validation progress)")
    args = parser.parse_args()

    with open(args.file_path, "rb") as file:
        data = file.read()

    packet_parser = SACDPacket(data, verbose=args.verbose)
    packets = packet_parser.get_packets(packets_with_sections=True, check_crc=args.check_crc)
    packets = packet_parser.order_packets(packets)

    # Plot battery voltage with different X-axes
    packet_parser.plot_telemetry_values("vBatAverage", packets, x_field="OBT")
    packet_parser.plot_telemetry_values("vBatAverage", packets, x_field="OBT_s")
    packet_parser.plot_telemetry_values("vBatAverage", packets)


if __name__ == "__main__":
    main()
