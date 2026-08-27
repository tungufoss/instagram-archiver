"""Archive Instagram photos and videos your own account can already see.

Kept deliberately light: importing this package must not pull in Playwright,
so the pure helpers stay testable without a browser installed.
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
