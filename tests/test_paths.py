import pytest

from dataset_tools import paths


@pytest.mark.parametrize("location", [paths.EXPORT, paths.RUNS, paths.LATEST_MODEL])
def test_generated_files_stay_outside_the_project(location):
    assert not location.is_relative_to(paths.ROOT)
