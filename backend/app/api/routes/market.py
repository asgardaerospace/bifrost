"""HTTP endpoints for Market OS."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.market import (
    AccountCampaignCreate,
    AccountCampaignRead,
    AccountCampaignUpdate,
    AccountContactCreate,
    AccountContactRead,
    AccountContactUpdate,
    AccountCreate,
    AccountRead,
    AccountUpdate,
    CampaignCreate,
    CampaignRead,
    CampaignUpdate,
    MarketDashboardSummary,
    MarketOpportunityCreate,
    MarketOpportunityRead,
    MarketOpportunityUpdate,
)
from app.services import market as market_service

router = APIRouter()


# --- optional hydration helpers -----------------------------------------------

def _hydrate_link(db: Session, link) -> AccountCampaignRead:
    read = AccountCampaignRead.model_validate(link)
    return read.model_copy(
        update={
            "account_name": link.account.name if link.account else None,
            "campaign_name": link.campaign.name if link.campaign else None,
        }
    )


def _hydrate_opportunity(opp) -> MarketOpportunityRead:
    read = MarketOpportunityRead.model_validate(opp)
    return read.model_copy(
        update={"account_name": opp.account.name if opp.account else None}
    )


# --- accounts -----------------------------------------------------------------


@router.get("/accounts", response_model=list[AccountRead])
def list_accounts(
    sector: Optional[str] = None,
    region: Optional[str] = None,
    type: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AccountRead]:
    rows = market_service.list_accounts(
        db,
        sector=sector,
        region=region,
        type_=type,
        skip=skip,
        limit=limit,
    )
    return [AccountRead.model_validate(r) for r in rows]


@router.get("/accounts/{account_id}", response_model=AccountRead)
def get_account(account_id: int, db: Session = Depends(get_db)) -> AccountRead:
    return AccountRead.model_validate(market_service.get_account(db, account_id))


@router.post(
    "/accounts", response_model=AccountRead, status_code=status.HTTP_201_CREATED
)
def create_account(
    payload: AccountCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> AccountRead:
    return AccountRead.model_validate(
        market_service.create_account(db, payload, actor=actor)
    )


@router.patch("/accounts/{account_id}", response_model=AccountRead)
def update_account(
    account_id: int,
    payload: AccountUpdate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> AccountRead:
    return AccountRead.model_validate(
        market_service.update_account(db, account_id, payload, actor=actor)
    )


# --- account contacts ---------------------------------------------------------


@router.get(
    "/accounts/{account_id}/contacts", response_model=list[AccountContactRead]
)
def list_account_contacts(
    account_id: int, db: Session = Depends(get_db)
) -> list[AccountContactRead]:
    rows = market_service.list_account_contacts(db, account_id)
    return [AccountContactRead.model_validate(r) for r in rows]


@router.post(
    "/account-contacts",
    response_model=AccountContactRead,
    status_code=status.HTTP_201_CREATED,
)
def create_account_contact(
    payload: AccountContactCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> AccountContactRead:
    return AccountContactRead.model_validate(
        market_service.create_account_contact(db, payload, actor=actor)
    )


@router.patch(
    "/account-contacts/{contact_id}", response_model=AccountContactRead
)
def update_account_contact(
    contact_id: int,
    payload: AccountContactUpdate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> AccountContactRead:
    return AccountContactRead.model_validate(
        market_service.update_account_contact(db, contact_id, payload, actor=actor)
    )


# --- campaigns ----------------------------------------------------------------


@router.get("/campaigns", response_model=list[CampaignRead])
def list_campaigns(
    status_filter: Optional[str] = Query(None, alias="status"),
    sector: Optional[str] = None,
    region: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[CampaignRead]:
    rows = market_service.list_campaigns(
        db,
        status_=status_filter,
        sector=sector,
        region=region,
        skip=skip,
        limit=limit,
    )
    return [CampaignRead.model_validate(r) for r in rows]


@router.get("/campaigns/{campaign_id}", response_model=CampaignRead)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)) -> CampaignRead:
    return CampaignRead.model_validate(market_service.get_campaign(db, campaign_id))


@router.post(
    "/campaigns",
    response_model=CampaignRead,
    status_code=status.HTTP_201_CREATED,
)
def create_campaign(
    payload: CampaignCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> CampaignRead:
    return CampaignRead.model_validate(
        market_service.create_campaign(db, payload, actor=actor)
    )


@router.patch("/campaigns/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    payload: CampaignUpdate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> CampaignRead:
    return CampaignRead.model_validate(
        market_service.update_campaign(db, campaign_id, payload, actor=actor)
    )


# --- campaign memberships -----------------------------------------------------


@router.post(
    "/account-campaigns",
    response_model=AccountCampaignRead,
    status_code=status.HTTP_201_CREATED,
)
def link_account_campaign(
    payload: AccountCampaignCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> AccountCampaignRead:
    link = market_service.link_account_to_campaign(db, payload, actor=actor)
    return _hydrate_link(db, link)


@router.patch(
    "/account-campaigns/{link_id}", response_model=AccountCampaignRead
)
def update_account_campaign(
    link_id: int,
    payload: AccountCampaignUpdate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> AccountCampaignRead:
    link = market_service.update_account_campaign(db, link_id, payload, actor=actor)
    return _hydrate_link(db, link)


@router.get(
    "/campaigns/{campaign_id}/accounts",
    response_model=list[AccountCampaignRead],
)
def list_campaign_accounts(
    campaign_id: int, db: Session = Depends(get_db)
) -> list[AccountCampaignRead]:
    rows = market_service.list_campaign_memberships(
        db, campaign_id=campaign_id
    )
    return [_hydrate_link(db, r) for r in rows]


@router.get(
    "/accounts/{account_id}/campaigns",
    response_model=list[AccountCampaignRead],
)
def list_account_campaigns(
    account_id: int, db: Session = Depends(get_db)
) -> list[AccountCampaignRead]:
    rows = market_service.list_campaign_memberships(
        db, account_id=account_id
    )
    return [_hydrate_link(db, r) for r in rows]


@router.get(
    "/account-campaigns/follow-ups",
    response_model=list[AccountCampaignRead],
)
def follow_ups_due(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[AccountCampaignRead]:
    rows = market_service.accounts_needing_follow_up(db, limit=limit)
    return [_hydrate_link(db, r) for r in rows]


# --- market opportunities -----------------------------------------------------


@router.get("/market-opportunities", response_model=list[MarketOpportunityRead])
def list_market_opportunities(
    stage: Optional[str] = None,
    sector: Optional[str] = None,
    account_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MarketOpportunityRead]:
    rows = market_service.list_opportunities(
        db,
        stage=stage,
        sector=sector,
        account_id=account_id,
        skip=skip,
        limit=limit,
    )
    return [_hydrate_opportunity(r) for r in rows]


@router.get(
    "/market-opportunities/active", response_model=list[MarketOpportunityRead]
)
def list_active_market_opportunities(
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[MarketOpportunityRead]:
    rows = market_service.list_active_opportunities(db, limit=limit)
    return [_hydrate_opportunity(r) for r in rows]


@router.get(
    "/market-opportunities/{opp_id}", response_model=MarketOpportunityRead
)
def get_market_opportunity(
    opp_id: int, db: Session = Depends(get_db)
) -> MarketOpportunityRead:
    return _hydrate_opportunity(market_service.get_opportunity(db, opp_id))


@router.post(
    "/market-opportunities",
    response_model=MarketOpportunityRead,
    status_code=status.HTTP_201_CREATED,
)
def create_market_opportunity(
    payload: MarketOpportunityCreate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> MarketOpportunityRead:
    return _hydrate_opportunity(
        market_service.create_opportunity(db, payload, actor=actor)
    )


@router.patch(
    "/market-opportunities/{opp_id}", response_model=MarketOpportunityRead
)
def update_market_opportunity(
    opp_id: int,
    payload: MarketOpportunityUpdate,
    actor: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> MarketOpportunityRead:
    return _hydrate_opportunity(
        market_service.update_opportunity(db, opp_id, payload, actor=actor)
    )


# --- dashboard summary --------------------------------------------------------


@router.get("/market/dashboard/summary", response_model=MarketDashboardSummary)
def market_dashboard_summary(
    db: Session = Depends(get_db),
) -> MarketDashboardSummary:
    return MarketDashboardSummary(**market_service.dashboard_summary(db))
