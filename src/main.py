import argparse
from aquarius import AquariusPacket



def main():
    parser = argparse.ArgumentParser(description="Open a binary file with the satellite telemetry.")
    parser.add_argument("file_path", help="Path to the file to open")
    parser.add_argument("-p", "--packet-size", type=int, default=4000, help="Expected packet size in bytes (default: 4000).")
    parser.add_argument("--check-crc", action="store_true", help="Enable CRC16 validation (disabled by default).")


    # Parse arguments
    args = parser.parse_args()
    # Open the file in binary read mode
    with open(args.file_path, "rb") as file:
        data = file.read()

    packet_parser = AquariusPacket(data, args.packet_size)

    # Check that binary is not corrupt and get number of packets
    # packets = packet_parser.get_packets(frame_parts)
    packets = packet_parser.get_packets(packets_with_sections=True, check_crc=args.check_crc)

    print(packets[0])

if __name__ == "__main__":
    main()
