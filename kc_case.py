"""Case utility — the single place that decides letter case.

Letters are lowercase by default and become uppercase when Shift or CapsLock is
active (the two cancel out). Keeping this here means keycap JSON files never encode
case: they only hold the base character, and this utility applies Shift/CapsLock."""

def apply_case(text, shift=False, caps_lock=False):
    if len(text) == 1 and text.isalpha():
        return text.upper() if (shift != caps_lock) else text.lower()
    return text
