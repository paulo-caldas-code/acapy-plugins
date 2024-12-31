"""AnonCreds Hedera registry."""

import re

from typing import Pattern

from acapy_agent.wallet.base import BaseWallet
from acapy_agent.core.event_bus import EventBus

from acapy_agent.anoncreds.base import (
        AnonCredsObjectNotFound,
        AnonCredsResolutionError,
        BaseAnonCredsRegistrar,
        BaseAnonCredsResolver,
        )
from acapy_agent.anoncreds.events import RevListFinishedEvent
from acapy_agent.anoncreds.models.schema_info import AnoncredsSchemaInfo

from did_sdk_py.anoncreds.hedera_anoncreds_registry import (
        HederaAnonCredsRegistry as SdkHederaAnonCredsRegistry
        )

from .types import (
        buildAcapyGetCredDefResult,
        buildHederaAnonCredsSchema,
        buildAcapyGetSchemaResult,
        buildAcapySchemaResult,
        buildAcapyCredDefResult,
        buildHederaAnonCredsRevList,
        buildAcapyRevListResult,
        buildHederaAnonCredsCredDef,
        buildAcapyRevRegDefResult,
        buildAcapyGetRevRegDefResult,
        buildHederaAnonCredsRevRegDef,
        buildAcapyGetRevListResult
        )


from .config import Config

from .client import get_client_provider

from .utils import (
        get_private_key_der_from_did,
        inject_or_fail,
        )

class HederaAnonCredsRegistry(BaseAnonCredsResolver, BaseAnonCredsRegistrar):
    """AnonCredsHederaRegistry."""

    def __init__(self):
        """Initialize an instance."""
        self._supported_identifiers_regex = re.compile("^did:hedera:.*$")

    def _validate_response(self, hedera_res, attribute_to_check):
        resolution_metadata = hedera_res.resolution_metadata

        if "error" in resolution_metadata:
            error = resolution_metadata.get("error")

            error_message = resolution_metadata.get("message")

            if not error_message:
                raise AnonCredsResolutionError("Unknown error")

            if error == "notFound":
                raise AnonCredsObjectNotFound(error_message)

        if getattr(hedera_res, attribute_to_check, None) is None:
            raise AnonCredsResolutionError(f"Failed to retrieve {attribute_to_check}")


    @property
    def supported_identifiers_regex(self) -> Pattern:
        """Supported identifiers regular expression."""
        return self._supported_identifiers_regex

    async def setup(self, context):
        """Setup registry based on current context."""
        settings = Config.from_settings(context.settings)

        network = settings.network
        operator_id = settings.operator_id
        operator_key_der = settings.operator_key_der

        client_provider = get_client_provider(network, operator_id, operator_key_der)

        self._hedera_anoncreds_registry = SdkHederaAnonCredsRegistry(client_provider)
    
    async def get_schema(self, profile, schema_id):
        """Get schema."""
        hedera_res = await self._hedera_anoncreds_registry.get_schema(schema_id)

        self._validate_response(hedera_res, "schema")

        return buildAcapyGetSchemaResult(hedera_res)

    async def get_credential_definition(self, profile, credential_definition_id):
        """Get credential definition."""
        hedera_res = await self._hedera_anoncreds_registry.get_cred_def(
                credential_definition_id
                )

        self._validate_response(hedera_res, "credential_definition")

        return buildAcapyGetCredDefResult(hedera_res)

    async def get_revocation_registry_definition(self, profile, revocation_registry_id):
        """Get revocation registry definition."""
        hedera_res = await self._hedera_anoncreds_registry.get_rev_reg_def(
                revocation_registry_id
                )

        self._validate_response(hedera_res, "revocation_registry_definition")

        assert hedera_res.revocation_registry_definition is not None

        return buildAcapyGetRevRegDefResult(hedera_res)


    async def get_revocation_list(self, profile, revocation_registry_id: str, timestamp: int):
        """Get revocation list."""
        hedera_res = await self._hedera_anoncreds_registry.get_rev_list(
                revocation_registry_id,
                timestamp
                )

        self._validate_response(hedera_res, "revocation_list")

        assert hedera_res.revocation_list is not None

        return buildAcapyGetRevListResult(hedera_res)

    async def register_credential_definition(self, profile, schema, credential_definition, options = None):
        """Register credential definition."""
        async with profile.session() as session:
            issuer_did = schema.schema.issuer_id

            wallet = inject_or_fail(
                    session,
                    BaseWallet,
                    AnonCredsResolutionError
                    )

            private_key_der = await get_private_key_der_from_did(wallet, issuer_did)

            hedera_res = await self._hedera_anoncreds_registry.register_cred_def(
                    cred_def=buildHederaAnonCredsCredDef(credential_definition),
                    issuer_key_der=private_key_der
                    )

            return buildAcapyCredDefResult(hedera_res)

    async def register_revocation_registry_definition(self, profile, revocation_registry_definition, options = None):
        """Register revocation registry definition."""
        async with profile.session() as session:
            issuer_did = revocation_registry_definition.issuer_id

            wallet = inject_or_fail(
                    session,
                    BaseWallet,
                    AnonCredsResolutionError
                    )

            private_key_der = await get_private_key_der_from_did(wallet, issuer_did)

            hedera_res = await self._hedera_anoncreds_registry.register_rev_reg_def(
                    rev_reg_def=buildHederaAnonCredsRevRegDef(revocation_registry_definition),
                    issuer_key_der=private_key_der
                    )

            assert hedera_res.revocation_registry_definition_state.revocation_registry_definition_id is not None

            return buildAcapyRevRegDefResult(hedera_res)
        

    async def register_revocation_list(self, profile, rev_reg_def, rev_list, options = None):
        """Register revocation list."""
        async with profile.session() as session:
            issuer_did = rev_reg_def.issuer_id

            wallet = inject_or_fail(
                    session,
                    BaseWallet,
                    AnonCredsResolutionError,
                    )

            private_key_der = await get_private_key_der_from_did(wallet, issuer_did)

            hedera_res = await self._hedera_anoncreds_registry.register_rev_list(
                    buildHederaAnonCredsRevList(rev_list),
                    private_key_der
                    )

            return buildAcapyRevListResult(hedera_res)


    async def update_revocation_list(self, profile, rev_reg_def, prev_list, curr_list, revoked, options = None):
        """Update revocation list."""
        async with profile.session() as session:
            issuer_did = rev_reg_def.issuer_id

            wallet = inject_or_fail(
                    session,
                    BaseWallet,
                    AnonCredsResolutionError
                    )
            event_bus = inject_or_fail(
                session,
                EventBus,
                AnonCredsResolutionError
                )

            private_key_der = await get_private_key_der_from_did(wallet, issuer_did)

            hedera_res = await self._hedera_anoncreds_registry.update_rev_list(
                    buildHederaAnonCredsRevList(prev_list),
                    buildHederaAnonCredsRevList(curr_list),
                    revoked,
                    private_key_der
                    )

            await event_bus.notify(
                profile,
                RevListFinishedEvent.with_payload(
                    curr_list.rev_reg_def_id, revoked
                ),
            )

            return buildAcapyRevListResult(hedera_res)


    async def register_schema(self, profile, schema, options = None):
            """Register schema."""
            async with profile.session() as session:
               issuer_did = schema.issuer_id

               wallet = inject_or_fail(
                       session,
                       BaseWallet,
                       AnonCredsResolutionError
                       )
               private_key_der = await get_private_key_der_from_did(wallet, issuer_did)

               hedera_res = await self._hedera_anoncreds_registry.register_schema(
                   schema=buildHederaAnonCredsSchema(schema),
                   issuer_key_der= private_key_der
               )

               return buildAcapySchemaResult(hedera_res)

    async def get_schema_info_by_id(self, profile, schema_id) -> AnoncredsSchemaInfo:
        """Get schema info by schema id."""
        res = await self._hedera_anoncreds_registry.get_schema(schema_id)

        self._validate_response(res, "schema")

        return AnoncredsSchemaInfo(
            issuer_id=res.schema.issuer_id,
            name=res.schema.name,
            version=res.schema.version,
        )