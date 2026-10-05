"""
Persona endpoints - manage the assistant personalities used in chat.

Personas are global (shared by all users):
- Read: any authenticated user.
- Create / update / delete: admins only.
"""

from fastapi import Depends, HTTPException
from models import PersonaInfo, PersonaRequest
from services.database import (
    create_persona,
    delete_persona,
    list_personas,
    update_persona,
)

from core_endpoints.auth import check_token, require_admin


def get_personas(_user: dict = Depends(check_token)) -> list[PersonaInfo]:
    """List all personas."""
    return [PersonaInfo(**p) for p in list_personas()]


def add_persona(
    request: PersonaRequest,
    _admin: dict = Depends(require_admin),
) -> PersonaInfo:
    """Create a persona (admin only)."""
    persona_id = create_persona(request.name, request.prompt)
    return PersonaInfo(id=persona_id, name=request.name, prompt=request.prompt)


def edit_persona(
    persona_id: int,
    request: PersonaRequest,
    _admin: dict = Depends(require_admin),
) -> PersonaInfo:
    """Update a persona (admin only)."""
    if not update_persona(persona_id, request.name, request.prompt):
        raise HTTPException(status_code=404, detail="Persona not found")
    return PersonaInfo(id=persona_id, name=request.name, prompt=request.prompt)


def remove_persona(
    persona_id: int,
    _admin: dict = Depends(require_admin),
) -> dict:
    """Delete a persona (admin only)."""
    if not delete_persona(persona_id):
        raise HTTPException(status_code=404, detail="Persona not found")
    return {"message": f"Persona {persona_id} deleted"}
