import pytest

from acapy_agent.admin.request_context import AdminRequestContext
from acapy_agent.utils.testing import create_test_profile
from acapy_agent.wallet.base import BaseWallet
from acapy_agent.wallet.key_type import KeyTypes

from unittest.mock import create_autospec

@pytest.fixture
async def profile():
    profile = await create_test_profile(
            settings={
                "admin.admin_api_key": "admin_api_key",
                "admin.admin_insecure_mode": False,
                "plugin_config": {
                    "hedera_did": {
                        "network": "<NETWORK>",
                        "operator_id": "<OPERATOR_ID>",
                        "operator_key_der": "<OPERATOR_KEY_DER>"
                    }
                }
            }
        )
    profile.context.injector.bind_instance(KeyTypes, KeyTypes())
    yield profile

@pytest.fixture
async def session_inject():
    session_inject = {
            BaseWallet: create_autospec(BaseWallet)
            }
    yield session_inject


@pytest.fixture
async def context(profile, session_inject):
    context = AdminRequestContext.test_context(session_inject, profile)
    yield context


