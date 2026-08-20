import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat


class InvalidPhoneNumberError(ValueError):
    pass


def normalize_phone(value: str) -> str:
    raw_value = value.strip()
    if not raw_value:
        raise InvalidPhoneNumberError("Phone number is required")

    region = None if raw_value.startswith("+") else "LB"
    try:
        parsed = phonenumbers.parse(raw_value, region)
    except NumberParseException as exc:
        raise InvalidPhoneNumberError("Phone number is invalid") from exc

    if not phonenumbers.is_possible_number(parsed) or not phonenumbers.is_valid_number(parsed):
        raise InvalidPhoneNumberError("Phone number is invalid")

    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
