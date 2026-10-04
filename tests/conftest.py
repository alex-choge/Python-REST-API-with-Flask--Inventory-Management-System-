"""Shared pytest fixtures."""
import copy
import os
import sys

import pytest


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as inventory_app  # noqa: E402


ORIGINAL_INVENTORY = copy.deepcopy(inventory_app.inventory)


@pytest.fixture(autouse=True)
def clean_data():
    """Reset the in-memory inventory before every test so tests don't affect each other."""
    inventory_app.inventory[:] = copy.deepcopy(ORIGINAL_INVENTORY)
    yield


@pytest.fixture
def client():
    inventory_app.app.config["TESTING"] = True
    return inventory_app.app.test_client()