"""Simple terminal interface for FasalBima Sathi records."""

from app.records import load_records, search, count_by, get_by_id


def main():
    records = load_records()
    while True:
        print("\\nFasalBima Sathi |", len(records), "records")
        print("1 Show all | 2 Search | 3 Count topics | 4 Find ID | 0 Exit")
        choice = input("Choice: ").strip()
        if choice == "1":
            for r in records:
                print(r["id"], r["rule_topic"], "-", r["rule_text"])
        elif choice == "2":
            for r in search(records, input("Keyword: ")):
                print(r["id"], r["rule_topic"])
        elif choice == "3":
            for key, value in count_by(records, "rule_topic").items():
                print(key, value)
        elif choice == "4":
            try:
                print(get_by_id(records, int(input("ID: "))))
            except ValueError:
                print("Enter a valid integer ID.")
        elif choice == "0":
            break
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    main()
