#!/usr/bin/env python3
import argparse


def normalize_submission(input_path: str, output_path: str) -> None:
    with open(input_path, "r", encoding="ascii") as f:
        lines = f.read().splitlines()

    if not lines:
        raise ValueError("Empty submission file")

    c = int(lines[0].strip())
    i = 1
    out = [str(c)]

    for vehicle_index in range(c):
        if i >= len(lines):
            raise ValueError(f"Missing route-length line for vehicle {vehicle_index}")
        # Read and ignore original n, we recompute it from route tokens.
        _orig_n = lines[i].strip()
        i += 1

        if i >= len(lines):
            raise ValueError(f"Missing route line for vehicle {vehicle_index}")
        route_tokens = [t for t in lines[i].split() if t]
        i += 1

        if i >= len(lines):
            raise ValueError(f"Missing cleaned line for vehicle {vehicle_index}")
        clean_tokens = [t for t in lines[i].split() if t]
        i += 1

        # Validator-compatible interpretation: n is traversed edge count.
        out.append(str(max(0, len(route_tokens) - 1)))
        out.append(" ".join(route_tokens))
        out.append(" ".join(clean_tokens))

    # Ignore trailing lines if present.
    with open(output_path, "w", encoding="ascii", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize submission route counts")
    parser.add_argument("--input", required=True, help="Input submission file")
    parser.add_argument("--output", required=True, help="Output normalized file")
    args = parser.parse_args()

    normalize_submission(args.input, args.output)


if __name__ == "__main__":
    main()
