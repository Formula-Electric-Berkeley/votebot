import random
import re
import string


def button_action_id(eid: str, is_yes: bool) -> str:
    return f'{eid}_{"yes" if is_yes else "no"}'


def random_id(length: int = 8) -> str:
    return ''.join(random.choices(string.digits + string.ascii_letters, k=length))


def clean_alphanumeric(text: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]+', '', text)