"""
Admin API Endpoints - for managing users and permissions

All endpoints require an authenticated admin, supplied as a Bearer token via
the ``require_admin`` dependency (no tokens in query strings or bodies).

Functions:
- get_user(): Fetch info about a specific user, or the authenticated admin.
- list_all_users(): Retrieve all users in the system.
- update_user_admin(): Promote/demote users. Prevents self-demotion.
"""

import logging
import sqlite3

from fastapi import Depends, HTTPException
from models import UpdateUserAdminRequest, UserInfoResponse
from services.database import (
    db_cursor,
    get_all_users,
    get_user_by_id,
    select_user_id,
    update_user_admin_status,
)

from core_endpoints.auth import require_admin

logger = logging.getLogger(__name__)


def get_user(
    user_data: dict = Depends(require_admin),
    username: str | None = None,
) -> UserInfoResponse:
    """
    Get user information (admin only).

    If ``username`` is provided, returns info for that user; otherwise returns
    info for the authenticated admin.
    """
    admin_user_id = user_data["user_id"]

    with db_cursor() as cursor:
        if username:
            cursor.execute(select_user_id, (username,))
            result = cursor.fetchone()
            if not result:
                raise HTTPException(status_code=404, detail="User not found")
            target_user_id = result[0]
        else:
            target_user_id = admin_user_id

        cursor.execute(get_user_by_id, (target_user_id,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="User not found")

        user_id, full_name, username_result, is_admin = result
        return UserInfoResponse(
            id=user_id,
            full_name=full_name,
            username=username_result,
            is_admin=bool(is_admin),
        )


def list_all_users(user_data: dict = Depends(require_admin)) -> list:
    """List all users (admin only)."""
    with db_cursor() as cursor:
        cursor.execute(get_all_users)
        results = cursor.fetchall()

        return [
            UserInfoResponse(
                id=row[0],
                full_name=row[1],
                username=row[2],
                is_admin=bool(row[3]),
            )
            for row in results
        ]


def update_user_admin(
    request: UpdateUserAdminRequest,
    user_data: dict = Depends(require_admin),
):
    """Update a user's admin status (admin only)."""
    admin_user_id = user_data["user_id"]

    try:
        with db_cursor(commit=True) as cursor:
            # Get target user ID
            cursor.execute(select_user_id, (request.target_username,))
            result = cursor.fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Target user not found")

            target_user_id = result[0]

            # Prevent self-demotion
            if target_user_id == admin_user_id and not request.is_admin:
                raise HTTPException(
                    status_code=400,
                    detail="You cannot revoke your own administrator privileges",
                )

            # Update admin status
            cursor.execute(
                update_user_admin_status,
                (int(request.is_admin), target_user_id),
            )

            action = (
                "promoted to administrator"
                if request.is_admin
                else "demoted to regular user"
            )
            return {
                "message": f"User '{request.target_username}' {action}",
                "username": request.target_username,
                "is_admin": request.is_admin,
            }
    except sqlite3.Error:
        logger.exception("Failed to update admin status")
        raise HTTPException(status_code=500, detail="Unable to update user") from None
