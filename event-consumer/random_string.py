from random import choices
import string

RANDOM_CHARS = string.digits + string.ascii_letters


def random_string(k=26):
    """
    Returns a random string of numbers and letters k-characters long.
    """
    chars = choices(RANDOM_CHARS, k=k)
    return "".join(chars)

def verify_string(value):
    """
    Returns True if the passed string could plausibly have been generated by the random_string function, False if not
    """
    for char in value:
        if char not in RANDOM_CHARS:
            return False
    return True