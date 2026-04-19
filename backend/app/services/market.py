"""CRUD + summary services for Market OS.

All writes log an ActivityEvent so the activity timeline reflects
market-side changes the same way it does investor-side changes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.market import (
    Account,
    AccountCampaign,
    AccountContact,
    Campaign,
    MarketOpportunity,
)
from app.schemas.market import (
    AccountCampaignCreate,
    AccountCampaignUpdate,
    AccountContactCreate,
    AccountContactUpdate,
    AccountCreate,
    AccountUpdate,
    CampaignCreate,
    CampaignUpdate,
    MarketOpportunityCreate,
    MarketOpportunityUpdate,
)
from app.services.activity import log_activity

ENTITY_ACCOUNT = "account"
ENTITY_ACCOUNT_CONTACT = "account_contact"
ENTITY_CAMPAIGN = "campaign"
ENTITY_ACCOUNT_CAMPAIGN = "account_campaign"
ENTITY_MARKET_OPPORTUNITY = "market_opportunity"


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------

def _not_found(name: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail=f"{name} not found"
    )


def list_accounts(
    db: Session,
    *,
    sector: Optional[str] = None,
    region: Optional[str] = None,
    type_: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Account]:
    stmt = select(Account).where(Account.deleted_at.is_(None))
    if sector:
        stmt = stmt.where(Account.sector == sector)
    if region:
        stmt = stmt.where(Account.region == region)
    if type_:
        stmt = stmt.where(Account.type == type_)
    stmt = stmt.order_by(Account.name).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_account(db: Session, account_id: int) -> Account:
    acct = db.get(Account, account_id)
    if acct is None or acct.deleted_at is not None:
        raise _not_found("Account")
    return acct


def create_account(
    db: Session, payload: AccountCreate, *, actor: Optional[str] = None
) -> Account:
    acct = Account(**payload.model_dump())
    db.add(acct)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_ACCOUNT,
        entity_id=acct.id,
        event_type="account.created",
        summary=f"Account '{acct.name}' created",
        actor=actor,
        details={"sector": acct.sector, "region": acct.region, "type": acct.type},
    )
    db.commit()
    db.refresh(acct)
    return acct


def update_account(
    db: Session,
    account_id: int,
    payload: AccountUpdate,
    *,
    actor: Optional[str] = None,
) -> Account:
    acct = get_account(db, account_id)
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(acct, k, v)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_ACCOUNT,
        entity_id=acct.id,
        event_type="account.updated",
        summary=f"Account '{acct.name}' updated",
        actor=actor,
        details={"changes": changes},
    )
    db.commit()
    db.refresh(acct)
    return acct


# ---------------------------------------------------------------------------
# account contacts
# ---------------------------------------------------------------------------

def list_account_contacts(
    db: Session, account_id: int
) -> list[AccountContact]:
    get_account(db, account_id)
    stmt = (
        select(AccountContact)
        .where(AccountContact.account_id == account_id)
        .where(AccountContact.deleted_at.is_(None))
        .order_by(AccountContact.name)
    )
    return list(db.execute(stmt).scalars().all())


def create_account_contact(
    db: Session,
    payload: AccountContactCreate,
    *,
    actor: Optional[str] = None,
) -> AccountContact:
    get_account(db, payload.account_id)
    contact = AccountContact(**payload.model_dump())
    db.add(contact)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_ACCOUNT_CONTACT,
        entity_id=contact.id,
        event_type="account_contact.created",
        summary=f"Contact '{contact.name}' added to account #{contact.account_id}",
        actor=actor,
        details={"account_id": contact.account_id, "email": contact.email},
    )
    db.commit()
    db.refresh(contact)
    return contact


def update_account_contact(
    db: Session,
    contact_id: int,
    payload: AccountContactUpdate,
    *,
    actor: Optional[str] = None,
) -> AccountContact:
    contact = db.get(AccountContact, contact_id)
    if contact is None or contact.deleted_at is not None:
        raise _not_found("Account contact")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(contact, k, v)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_ACCOUNT_CONTACT,
        entity_id=contact.id,
        event_type="account_contact.updated",
        summary=f"Contact '{contact.name}' updated",
        actor=actor,
        details={"changes": changes},
    )
    db.commit()
    db.refresh(contact)
    return contact


# ---------------------------------------------------------------------------
# campaigns
# ---------------------------------------------------------------------------

def list_campaigns(
    db: Session,
    *,
    status_: Optional[str] = None,
    sector: Optional[str] = None,
    region: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Campaign]:
    stmt = select(Campaign).where(Campaign.deleted_at.is_(None))
    if status_:
        stmt = stmt.where(Campaign.status == status_)
    if sector:
        stmt = stmt.where(Campaign.sector == sector)
    if region:
        stmt = stmt.where(Campaign.region == region)
    stmt = stmt.order_by(Campaign.name).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_campaign(db: Session, campaign_id: int) -> Campaign:
    c = db.get(Campaign, campaign_id)
    if c is None or c.deleted_at is not None:
        raise _not_found("Campaign")
    return c


def create_campaign(
    db: Session, payload: CampaignCreate, *, actor: Optional[str] = None
) -> Campaign:
    c = Campaign(**payload.model_dump())
    db.add(c)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_CAMPAIGN,
        entity_id=c.id,
        event_type="campaign.created",
        summary=f"Campaign '{c.name}' created",
        actor=actor,
        details={"sector": c.sector, "region": c.region, "status": c.status},
    )
    db.commit()
    db.refresh(c)
    return c


def update_campaign(
    db: Session,
    campaign_id: int,
    payload: CampaignUpdate,
    *,
    actor: Optional[str] = None,
) -> Campaign:
    c = get_campaign(db, campaign_id)
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(c, k, v)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_CAMPAIGN,
        entity_id=c.id,
        event_type="campaign.updated",
        summary=f"Campaign '{c.name}' updated",
        actor=actor,
        details={"changes": changes},
    )
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# account <-> campaign membership
# ---------------------------------------------------------------------------

def link_account_to_campaign(
    db: Session,
    payload: AccountCampaignCreate,
    *,
    actor: Optional[str] = None,
) -> AccountCampaign:
    get_account(db, payload.account_id)
    get_campaign(db, payload.campaign_id)

    existing = db.execute(
        select(AccountCampaign).where(
            and_(
                AccountCampaign.account_id == payload.account_id,
                AccountCampaign.campaign_id == payload.campaign_id,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account is already linked to this campaign",
        )

    link = AccountCampaign(**payload.model_dump())
    db.add(link)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_ACCOUNT_CAMPAIGN,
        entity_id=link.id,
        event_type="account_campaign.linked",
        summary=(
            f"Account #{link.account_id} added to campaign #{link.campaign_id}"
        ),
        actor=actor,
        details={
            "account_id": link.account_id,
            "campaign_id": link.campaign_id,
            "status": link.status,
        },
    )
    db.commit()
    db.refresh(link)
    return link


def update_account_campaign(
    db: Session,
    link_id: int,
    payload: AccountCampaignUpdate,
    *,
    actor: Optional[str] = None,
) -> AccountCampaign:
    link = db.get(AccountCampaign, link_id)
    if link is None:
        raise _not_found("Account/Campaign link")
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(link, k, v)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_ACCOUNT_CAMPAIGN,
        entity_id=link.id,
        event_type="account_campaign.updated",
        summary=(
            f"Account #{link.account_id} / campaign #{link.campaign_id} updated"
        ),
        actor=actor,
        details={"changes": changes},
    )
    db.commit()
    db.refresh(link)
    return link


def list_campaign_memberships(
    db: Session,
    *,
    campaign_id: Optional[int] = None,
    account_id: Optional[int] = None,
) -> list[AccountCampaign]:
    stmt = select(AccountCampaign)
    if campaign_id is not None:
        stmt = stmt.where(AccountCampaign.campaign_id == campaign_id)
    if account_id is not None:
        stmt = stmt.where(AccountCampaign.account_id == account_id)
    stmt = stmt.order_by(desc(AccountCampaign.updated_at))
    return list(db.execute(stmt).scalars().all())


def accounts_needing_follow_up(
    db: Session, *, as_of: Optional[datetime] = None, limit: int = 100
) -> list[AccountCampaign]:
    now = as_of or datetime.now(timezone.utc)
    stmt = (
        select(AccountCampaign)
        .where(AccountCampaign.next_follow_up_at.is_not(None))
        .where(AccountCampaign.next_follow_up_at <= now)
        .order_by(AccountCampaign.next_follow_up_at.asc())
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


# ---------------------------------------------------------------------------
# market opportunities
# ---------------------------------------------------------------------------

def list_opportunities(
    db: Session,
    *,
    stage: Optional[str] = None,
    sector: Optional[str] = None,
    account_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[MarketOpportunity]:
    stmt = select(MarketOpportunity).where(MarketOpportunity.deleted_at.is_(None))
    if stage:
        stmt = stmt.where(MarketOpportunity.stage == stage)
    if account_id is not None:
        stmt = stmt.where(MarketOpportunity.account_id == account_id)
    if sector:
        stmt = stmt.join(Account, Account.id == MarketOpportunity.account_id).where(
            Account.sector == sector
        )
    stmt = stmt.order_by(desc(MarketOpportunity.updated_at)).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def list_active_opportunities(
    db: Session, *, limit: int = 100
) -> list[MarketOpportunity]:
    stmt = (
        select(MarketOpportunity)
        .where(MarketOpportunity.deleted_at.is_(None))
        .where(MarketOpportunity.stage.in_(("exploring", "active")))
        .order_by(desc(MarketOpportunity.updated_at))
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_opportunity(db: Session, opp_id: int) -> MarketOpportunity:
    opp = db.get(MarketOpportunity, opp_id)
    if opp is None or opp.deleted_at is not None:
        raise _not_found("Market opportunity")
    return opp


def create_opportunity(
    db: Session,
    payload: MarketOpportunityCreate,
    *,
    actor: Optional[str] = None,
) -> MarketOpportunity:
    get_account(db, payload.account_id)
    opp = MarketOpportunity(**payload.model_dump())
    db.add(opp)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_MARKET_OPPORTUNITY,
        entity_id=opp.id,
        event_type="market_opportunity.created",
        summary=(
            f"Market opportunity '{opp.name}' created for account #{opp.account_id}"
        ),
        actor=actor,
        details={"account_id": opp.account_id, "stage": opp.stage},
    )
    db.commit()
    db.refresh(opp)
    return opp


def update_opportunity(
    db: Session,
    opp_id: int,
    payload: MarketOpportunityUpdate,
    *,
    actor: Optional[str] = None,
) -> MarketOpportunity:
    opp = get_opportunity(db, opp_id)
    changes = payload.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(opp, k, v)
    db.flush()
    log_activity(
        db,
        entity_type=ENTITY_MARKET_OPPORTUNITY,
        entity_id=opp.id,
        event_type="market_opportunity.updated",
        summary=f"Market opportunity '{opp.name}' updated",
        actor=actor,
        details={"changes": changes},
    )
    db.commit()
    db.refresh(opp)
    return opp


# ---------------------------------------------------------------------------
# dashboard summary
# ---------------------------------------------------------------------------

def dashboard_summary(db: Session) -> dict[str, int]:
    total_accounts = db.execute(
        select(func.count(Account.id)).where(Account.deleted_at.is_(None))
    ).scalar_one()
    active_campaigns = db.execute(
        select(func.count(Campaign.id))
        .where(Campaign.deleted_at.is_(None))
        .where(Campaign.status == "active")
    ).scalar_one()
    active_opps = db.execute(
        select(func.count(MarketOpportunity.id))
        .where(MarketOpportunity.deleted_at.is_(None))
        .where(MarketOpportunity.stage.in_(("exploring", "active")))
    ).scalar_one()
    now = datetime.now(timezone.utc)
    needing_follow_up = db.execute(
        select(func.count(AccountCampaign.id))
        .where(AccountCampaign.next_follow_up_at.is_not(None))
        .where(AccountCampaign.next_follow_up_at <= now)
    ).scalar_one()
    return {
        "total_accounts": int(total_accounts or 0),
        "active_campaigns": int(active_campaigns or 0),
        "active_opportunities": int(active_opps or 0),
        "accounts_needing_follow_up": int(needing_follow_up or 0),
    }


def opportunities_by_sector(
    db: Session, *, limit_per_sector: int = 50
) -> dict[str, list[MarketOpportunity]]:
    rows = db.execute(
        select(MarketOpportunity, Account.sector)
        .join(Account, Account.id == MarketOpportunity.account_id)
        .where(MarketOpportunity.deleted_at.is_(None))
        .where(MarketOpportunity.stage.in_(("exploring", "active")))
        .order_by(desc(MarketOpportunity.updated_at))
    ).all()
    grouped: dict[str, list[MarketOpportunity]] = {}
    for opp, sector in rows:
        key = sector or "_unknown"
        bucket = grouped.setdefault(key, [])
        if len(bucket) < limit_per_sector:
            bucket.append(opp)
    return grouped
