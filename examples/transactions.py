import argparse
import asyncio
import csv
from pathlib import Path

from config import club_id, password, username

from spond.club import SpondClub

EXPORT_DIRPATH = Path("./exports")

parser = argparse.ArgumentParser(
    description="Exports transactions, payment requests, recipient statuses, and payouts from Spond Club to CSV"
)
parser.add_argument(
    "-l",
    "--list-clubs",
    help="List accessible Spond Clubs (name, id, shortId) and exit",
    action="store_true",
)
parser.add_argument(
    "-m",
    "--max",
    help="The max number of transactions to query for",
    type=int,
    dest="max",
    default=1000,
)
parser.add_argument(
    "--transactions-only",
    help="Only export transactions",
    action="store_true",
)
parser.add_argument(
    "--payments-only",
    help="Only export payment requests and recipient dues statuses",
    action="store_true",
)
parser.add_argument(
    "--payouts-only",
    help="Only export bank payouts",
    action="store_true",
)

args = parser.parse_args()


async def _resolve_club_id(s: SpondClub, configured_id: str) -> str | None:
    """Resolve `configured_id` (full id, shortId, or name) to the club's full UUID `id`."""
    if (
        configured_id
        and configured_id != "1234567890"
        and len(configured_id) == 32
        and all(c in "0123456789ABCDEFabcdef" for c in configured_id)
    ):
        return configured_id

    clubs = await s.get_clubs()
    if not clubs:
        return None

    for c in clubs:
        if configured_id in (c.get("id"), c.get("shortId"), c.get("name")):
            print(f"Resolved club '{configured_id}' -> {c.get('name')} (id={c['id']})")
            return c["id"]

    fallback = clubs[0]
    print(f"Using discovered club: {fallback.get('name')} (id={fallback['id']})")
    return fallback["id"]


def _write_csv(filename: str, records: list[dict]) -> Path | None:
    if not records:
        return None
    EXPORT_DIRPATH.mkdir(exist_ok=True)
    csv_filepath = EXPORT_DIRPATH / filename
    fieldnames = list(dict.fromkeys(key for row in records for key in row))
    with csv_filepath.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in records:
            # Flatten non-primitive fields if any
            clean_row = {
                k: (str(v) if isinstance(v, (dict, list)) else ("" if v is None else v))
                for k, v in row.items()
            }
            writer.writerow(clean_row)
    return csv_filepath


async def main() -> None:
    s = SpondClub(username=username, password=password)
    try:
        if args.list_clubs:
            clubs = await s.get_clubs()
            for c in clubs:
                print(
                    f"Name: {c.get('name')} | id: {c.get('id')} | shortId: {c.get('shortId')}"
                )
            return

        target_club_id = await _resolve_club_id(s, club_id)
        if not target_club_id:
            print("No Spond Clubs found for this account.")
            return

        export_all = not (
            args.transactions_only or args.payments_only or args.payouts_only
        )

        # 1. Transactions
        if export_all or args.transactions_only:
            print(f"Fetching up to {args.max} transactions...")
            transactions = await s.get_transactions(
                club_id=target_club_id, max_items=args.max
            )
            if transactions:
                path = _write_csv("transactions.csv", transactions)
                print(f"Collected {len(transactions)} transactions. Written to {path}")
            else:
                print("No transactions found.")

        # 2. Payment Requests & Member Recipients
        if export_all or args.payments_only:
            print("Fetching payment requests...")
            payments = await s.get_payments(club_id=target_club_id)
            if payments:
                path = _write_csv("payments.csv", payments)
                print(f"Collected {len(payments)} payment requests. Written to {path}")

                # Fetch detailed recipients for each payment request
                all_recipients = []
                for p in payments:
                    p_id = p.get("id")
                    if not p_id:
                        continue
                    try:
                        p_detail = await s.get_payment(
                            club_id=target_club_id, payment_id=p_id
                        )
                        recipients = p_detail.get("recipients") or []
                        for r in recipients:
                            rec_row = {
                                "paymentId": p_id,
                                "paymentTitle": p.get("title", ""),
                                **r,
                            }
                            all_recipients.append(rec_row)
                    except Exception as e:
                        print(
                            f"Warning: could not fetch details for payment {p_id}: {e}"
                        )

                if all_recipients:
                    r_path = _write_csv("payment_recipients.csv", all_recipients)
                    print(
                        f"Collected {len(all_recipients)} payment recipient records. Written to {r_path}"
                    )
            else:
                print("No payment requests found.")

        # 3. Payouts (Bank Transfers)
        if export_all or args.payouts_only:
            print("Fetching payouts...")
            payouts = await s.get_payouts(club_id=target_club_id)
            if payouts:
                path = _write_csv("payouts.csv", payouts)
                print(f"Collected {len(payouts)} payouts. Written to {path}")
            else:
                print("No payouts found.")

    finally:
        await s.clientsession.close()


if __name__ == "__main__":
    asyncio.run(main())
