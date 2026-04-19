"""Investor engine integration.

Read-only ingestion path:

    client  -->  schemas  -->  mapper  -->  sync  -->  Bifrost entities
                                                       (investor_firms,
                                                        investor_contacts,
                                                        investor_opportunities)

The `service` module exposes a read surface for the rest of Bifrost
(dashboard, command console, investor execution views) so callers never
touch raw engine payloads directly.
"""

from app.integrations.investor_engine import (  # noqa: F401
    client,
    mapper,
    schemas,
    service,
    sync,
)
