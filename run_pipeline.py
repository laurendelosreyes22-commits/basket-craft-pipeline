import sys
from pipeline.extract import extract
from pipeline.transform import transform


def main():
    try:
        print("[1/2] Extracting MySQL → raw schema...")
        extract()
        print("[2/2] Transforming raw → analytics...")
        transform()
        print("[OK] Pipeline complete")
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
