import pytest

pytest.skip(
    "Phase B is being migrated in slices. File/search coverage lives in "
    "tests/my_agent/test_phase_b_file_search_tools.py; exec session and web "
    "tools are deferred to later slices.",
    allow_module_level=True,
)
