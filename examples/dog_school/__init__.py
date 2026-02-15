"""Dog School — minimal example app demonstrating the Praecepta framework.

Defines a Dog aggregate with tricks, exposed via a REST API using only
``create_app()`` plus installed praecepta packages (zero manual wiring
for framework plumbing).

Modules:
    domain: Dog aggregate, DogNotFoundError
    router: FastAPI endpoints (POST /dogs/, GET /dogs/{id}, POST /dogs/{id}/tricks)
    app:    Application factory (create_dog_school_app)
"""

from .app import create_dog_school_app
from .domain import Dog, DogNotFoundError

__all__ = ["Dog", "DogNotFoundError", "create_dog_school_app"]
