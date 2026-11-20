"""Offline province (il) and district (ilce) lookup for Turkiye.

    >>> from turkiye_il_ilce import lookup
    >>> lookup(40.99, 29.03)["ilce"]
    'Kadıköy'

No runtime dependencies. The boundary data ships inside the package.
"""

from ._core import (
    data_info,
    data_path,
    ilceler,
    iller,
    lookup,
)

__all__ = ["lookup", "iller", "ilceler", "data_path", "data_info"]
__version__ = "0.1.0"
