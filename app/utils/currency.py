"""
Currency conversion and Stripe amount-encoding helpers.

Stripe expects most currencies' amounts in their smallest unit (cents for
USD/EUR — amount * 100) but a small set of "zero-decimal" currencies
(JPY, KRW, ...) take the amount as-is: charging 100 for JPY is ¥100, not
¥1.00. Getting this wrong either overcharges by 100x or undercharges by
100x — there's no partial-failure here, so it's worth its own tested
helper rather than a `* 100` inlined at every Stripe call site.

https://docs.stripe.com/currencies#zero-decimal
"""
ZERO_DECIMAL_CURRENCIES = {
    "BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG",
    "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF",
}


def decimal_places_for(currency_code: str) -> int:
    return 0 if currency_code.upper() in ZERO_DECIMAL_CURRENCIES else 2


def convert_from_base(base_amount: float, exchange_rate_to_base: float, currency_code: str) -> float:
    """base_amount (in settings.BASE_CURRENCY_CODE) converted into
    currency_code, rounded to that currency's own smallest denomination."""
    converted = base_amount * exchange_rate_to_base
    return round(converted, decimal_places_for(currency_code))


def to_stripe_amount(amount: float, currency_code: str) -> int:
    """amount, already denominated in currency_code, encoded the way
    Stripe's API expects for that currency."""
    if currency_code.upper() in ZERO_DECIMAL_CURRENCIES:
        return int(round(amount))
    return int(round(amount * 100))
