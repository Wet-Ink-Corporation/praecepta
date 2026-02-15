"""Dog School REST API router.

Demonstrates a domain router that plugs into create_app() via extra_routers.
Uses request context (populated by middleware) to extract tenant_id.
"""

from __future__ import annotations

from uuid import UUID  # noqa: TC003 — FastAPI needs UUID at runtime for path params

from fastapi import APIRouter
from pydantic import BaseModel

from praecepta.foundation.application import get_current_tenant_id

from .domain import Dog, DogNotFoundError

router = APIRouter(prefix="/dogs", tags=["dogs"])

# In-memory store — replaced by a real repository in production.
_dogs: dict[UUID, Dog] = {}


# -- Request / Response models ------------------------------------------------


class RegisterDogRequest(BaseModel):
    name: str


class LearnTrickRequest(BaseModel):
    trick: str


class DogResponse(BaseModel):
    id: str
    name: str
    tenant_id: str
    tricks: list[str]
    version: int


# -- Endpoints ----------------------------------------------------------------


@router.post("/", status_code=201)
def register_dog(body: RegisterDogRequest) -> DogResponse:
    """Register a new dog in the current tenant."""
    tenant_id = get_current_tenant_id()
    dog = Dog(name=body.name, tenant_id=tenant_id)
    _dogs[dog.id] = dog
    return _dog_response(dog)


@router.get("/{dog_id}")
def get_dog(dog_id: UUID) -> DogResponse:
    """Retrieve a dog by ID."""
    dog = _dogs.get(dog_id)
    if dog is None:
        raise DogNotFoundError(str(dog_id))
    return _dog_response(dog)


@router.post("/{dog_id}/tricks")
def learn_trick(dog_id: UUID, body: LearnTrickRequest) -> DogResponse:
    """Teach an existing dog a new trick."""
    dog = _dogs.get(dog_id)
    if dog is None:
        raise DogNotFoundError(str(dog_id))
    dog.add_trick(body.trick)
    return _dog_response(dog)


# -- Helpers ------------------------------------------------------------------


def _dog_response(dog: Dog) -> DogResponse:
    return DogResponse(
        id=str(dog.id),
        name=dog.name,
        tenant_id=dog.tenant_id,
        tricks=list(dog.tricks),
        version=dog.version,
    )
