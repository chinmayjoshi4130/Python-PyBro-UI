# src/pybro/__init__.py

class _UIStub:
    """No-op stub that accepts any attribute call."""
    def __getattr__(self, name):
        def stub(*args, **kwargs):
            pass
        return stub

# Public `ui` object for use in scripts.
ui = _UIStub()
