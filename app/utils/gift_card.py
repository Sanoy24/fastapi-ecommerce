import uuid


def generate_gift_card_code() -> str:
    """GIFT-<12 random hex chars>, e.g. GIFT-A1B2C3D4E5F6.

    Uniqueness relies on the random suffix alone, the same as
    generate_order_number/generate_trx_ref in app/utils/order_utils.py — a
    collision is astronomically unlikely and neither of those retries either.
    """
    return f"GIFT-{str(uuid.uuid4())[:12].upper()}"
