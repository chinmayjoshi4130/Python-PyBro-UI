"""Math helper for subnet calculations."""

def subnet_size(mask_bits: int) -> int:
    """Return number of hosts for a given CIDR suffix."""
    return 2 ** (32 - mask_bits) - 2

