#!/usr/bin/env python3
import argparse
import hashlib


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def validate_submission(path: str) -> None:
    with open(path, "r", encoding="ascii") as f:
        lines = f.read().splitlines()

    if not lines:
        raise ValueError("Empty submission file")

    c = int(lines[0].strip())
    i = 1
    for vehicle_index in range(c):
        if i >= len(lines):
            raise ValueError(f"Missing route length line for vehicle {vehicle_index}")

        n = int(lines[i].strip())
        i += 1

        if i >= len(lines):
            raise ValueError(f"Missing route node line for vehicle {vehicle_index}")

        route_line = lines[i]
        route_tokens = [tok for tok in route_line.split(" ") if tok]
        i += 1

        # Validator-compatible interpretation: n is traversed edge count.
        if len(route_tokens) != n + 1:
            raise ValueError(
                f"Route node count mismatch for vehicle {vehicle_index}: expected {n + 1}, got {len(route_tokens)}"
            )

        if i >= len(lines):
            raise ValueError(f"Missing cleaned-street line for vehicle {vehicle_index}")

        # Cleaned-street line may be empty.
        i += 1

    if i != len(lines):
        raise ValueError("Unexpected trailing lines in submission file")


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate street-cleaning submission format")
    parser.add_argument("--file", required=True, help="Submission file path")
    args = parser.parse_args()

    validate_submission(args.file)

    with open(args.file, "r", encoding="ascii") as f:
        lines = f.read().splitlines()

    declared = int(lines[1].strip()) if len(lines) >= 2 else 0
    tokens = len([tok for tok in lines[2].split(" ") if tok]) if len(lines) >= 3 else 0

    print("FORMAT_OK")
    print(f"SHA256: {sha256_file(args.file)}")
    print(f"VEHICLE0_ROUTE_COUNT: declared_edges={declared} tokens(nodes)={tokens} expected_nodes={declared + 1}")


if __name__ == "__main__":
    main()
