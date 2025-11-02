import argparse
from sacd import SACDPacket

def main():
    parser = argparse.ArgumentParser(description="Open a binary file with the satellite telemetry.")
    parser.add_argument("file_path", help="Path to the file to open")
    parser.add_argument("--check-crc", action="store_true", help="Enable CRC16 validation (disabled by default).")

    # Parse arguments
    args = parser.parse_args()
    # Open the file in binary read mode
    with open(args.file_path, "rb") as file:
        data = file.read()

    packet_parser = SACDPacket(data)
    packets = packet_parser.get_packets(packets_with_sections=True, check_crc=args.check_crc)

    # Order the packets in case they are not ordered
    packet_parser.order_packets(packets)

    # First show the voltage with dates
    packet_parser.plot_telemetry_values('vBatAverage', packets, x_field='OBT')
    # Later show the voltage with seconds
    packet_parser.plot_telemetry_values('vBatAverage', packets, x_field='OBT_s')
    # Later show the voltage with packet index
    packet_parser.plot_telemetry_values('vBatAverage', packets)

if __name__ == "__main__":
    main()
