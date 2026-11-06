"""
Packet Validator
Validates Huaten C05 frame integrity and extracts frames from raw byte streams.
"""

import re
from typing import List, Tuple

# Frame pattern: [MAKER*DEVICE_ID*HEX_LEN*CONTENT]
FRAME_REGEX = rb"\[([^*\[\]]+)\*([^*\[\]]+)\*([0-9A-Fa-f]{2,4})\*(.*?)\]"


def is_valid_frame(raw_bytes: bytes) -> bool:
    """Checks whether byte slice matches Huaten C05 protocol encapsulation."""
    return bool(re.fullmatch(FRAME_REGEX, raw_bytes))


def extract_frames(buffer: bytes) -> Tuple[List[Tuple[str, str, bytes]], bytes]:
    """
    Extracts all complete [MAKER*ID*LEN*CONTENT] frames from the buffer.

    Returns:
        (frames, remainder_buffer)
        where frames is a list of (maker, device_id, content_bytes)
    """
    frames = []
    last_end = 0

    for match in re.finditer(FRAME_REGEX, buffer):
        maker = match.group(1).decode("latin-1")
        dev_id = match.group(2).decode("latin-1")
        content = match.group(4)
        frames.append((maker, dev_id, content))
        last_end = match.end()

    remainder = buffer[last_end:]
    return frames, remainder

