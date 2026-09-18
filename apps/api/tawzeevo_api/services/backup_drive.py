"""Google Drive access for encrypted backups (D-055) and an in-memory test double.

Scope is `drive.file` only: the app sees and touches only the files and the one folder it created
in the connected owner's Drive. The HTTP client speaks to Google directly through httpx; nothing
here logs tokens or codes. The memory double keeps the same contract so backup, retention, tamper
and restore behaviour is testable without credentials.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlencode

import httpx

from tawzeevo_api.config import Settings
from tawzeevo_api.errors import AppError

DRIVE_SCOPE = "https://www.googleapis.com/auth/drive.file"
USERINFO_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
SCOPES = f"{DRIVE_SCOPE} {USERINFO_SCOPE}"
FOLDER_MIME = "application/vnd.google-apps.folder"
BACKUP_MIME = "application/octet-stream"

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
DRIVE_URL = "https://www.googleapis.com/drive/v3/files"
UPLOAD_URL = "https://www.googleapis.com/upload/drive/v3/files"


@dataclass(frozen=True)
class RemoteFile:
    id: str
    name: str
    size: int


@dataclass(frozen=True)
class OAuthGrant:
    refresh_token: str
    account_email: str
    scopes: str


class OAuthClient(Protocol):
    def authorization_url(self, state: str) -> str: ...
    def exchange_code(self, code: str) -> OAuthGrant: ...


class DriveClient(Protocol):
    """Connected to one owner's Drive through that owner's refresh token."""

    def ensure_folder(self, name: str) -> str: ...
    def upload(self, folder_id: str, name: str, blob: bytes) -> RemoteFile: ...
    def list_files(self, folder_id: str) -> list[RemoteFile]: ...
    def download(self, file_id: str) -> bytes: ...
    def delete(self, file_id: str) -> None: ...


def _drive_error(response: httpx.Response) -> AppError:
    return AppError(
        502, "BACKUP_DRIVE_ERROR", f"Google Drive request failed ({response.status_code})"
    )


# ---------------------------------------------------------------------------------------------
# Google (real) implementation
# ---------------------------------------------------------------------------------------------


class GoogleOAuthClient:
    def __init__(self, settings: Settings) -> None:
        if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
            raise AppError(503, "BACKUP_OAUTH_UNCONFIGURED", "Google OAuth is not configured")
        self.client_id = settings.google_oauth_client_id
        self.client_secret = settings.google_oauth_client_secret
        self.redirect_uri = settings.google_oauth_redirect_uri

    def authorization_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "scope": SCOPES,
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "false",
                "state": state,
            }
        )
        return f"{AUTH_URL}?{query}"

    def exchange_code(self, code: str) -> OAuthGrant:
        with httpx.Client(timeout=20) as http:
            token = http.post(
                TOKEN_URL,
                data={
                    "code": code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "redirect_uri": self.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            if token.status_code != 200:
                raise AppError(
                    400, "BACKUP_OAUTH_EXCHANGE_FAILED", "Google did not accept the code"
                )
            body = token.json()
            refresh = body.get("refresh_token")
            granted = str(body.get("scope", ""))
            if not refresh or DRIVE_SCOPE not in granted.split():
                raise AppError(400, "BACKUP_OAUTH_SCOPE", "Drive file access was not granted")
            info = http.get(
                USERINFO_URL, headers={"Authorization": f"Bearer {body['access_token']}"}
            )
            email = str(info.json().get("email", "")) if info.status_code == 200 else ""
        return OAuthGrant(refresh_token=str(refresh), account_email=email, scopes=granted)


class GoogleDriveClient:
    def __init__(self, settings: Settings, refresh_token: str) -> None:
        if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
            raise AppError(503, "BACKUP_OAUTH_UNCONFIGURED", "Google OAuth is not configured")
        self._settings = settings
        self._refresh_token = refresh_token
        self._access_token: str | None = None
        self._http = httpx.Client(timeout=60)

    def _token(self) -> str:
        if self._access_token:
            return self._access_token
        response = self._http.post(
            TOKEN_URL,
            data={
                "refresh_token": self._refresh_token,
                "client_id": self._settings.google_oauth_client_id,
                "client_secret": self._settings.google_oauth_client_secret,
                "grant_type": "refresh_token",
            },
        )
        if response.status_code != 200:
            raise AppError(
                502, "BACKUP_DRIVE_AUTH", "Google Drive connection needs re-authorization"
            )
        self._access_token = str(response.json()["access_token"])
        return self._access_token

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token()}"}

    def ensure_folder(self, name: str) -> str:
        escaped = name.replace("'", "\\'")
        query = f"mimeType = '{FOLDER_MIME}' and name = '{escaped}' and trashed = false"
        found = self._http.get(
            DRIVE_URL, params={"q": query, "fields": "files(id)"}, headers=self._headers()
        )
        if found.status_code != 200:
            raise _drive_error(found)
        files = found.json().get("files", [])
        if files:
            return str(files[0]["id"])
        created = self._http.post(
            DRIVE_URL,
            json={"name": name, "mimeType": FOLDER_MIME},
            params={"fields": "id"},
            headers=self._headers(),
        )
        if created.status_code != 200:
            raise _drive_error(created)
        return str(created.json()["id"])

    def upload(self, folder_id: str, name: str, blob: bytes) -> RemoteFile:
        metadata = {"name": name, "parents": [folder_id], "mimeType": BACKUP_MIME}
        response = self._http.post(
            UPLOAD_URL,
            params={"uploadType": "multipart", "fields": "id,name,size"},
            files={
                "metadata": (None, json.dumps(metadata), "application/json"),
                "file": (name, blob, BACKUP_MIME),
            },
            headers=self._headers(),
        )
        if response.status_code != 200:
            raise _drive_error(response)
        body = response.json()
        return RemoteFile(
            id=str(body["id"]), name=str(body["name"]), size=int(body.get("size", len(blob)))
        )

    def list_files(self, folder_id: str) -> list[RemoteFile]:
        files: list[RemoteFile] = []
        token: str | None = None
        while True:
            params: dict[str, Any] = {
                "q": f"'{folder_id}' in parents and trashed = false",
                "fields": "nextPageToken,files(id,name,size)",
                "pageSize": 200,
            }
            if token:
                params["pageToken"] = token
            response = self._http.get(DRIVE_URL, params=params, headers=self._headers())
            if response.status_code != 200:
                raise _drive_error(response)
            body = response.json()
            files.extend(
                RemoteFile(id=str(f["id"]), name=str(f["name"]), size=int(f.get("size", 0)))
                for f in body.get("files", [])
            )
            token = body.get("nextPageToken")
            if not token:
                return files

    def download(self, file_id: str) -> bytes:
        response = self._http.get(
            f"{DRIVE_URL}/{file_id}", params={"alt": "media"}, headers=self._headers()
        )
        if response.status_code != 200:
            raise _drive_error(response)
        return response.content

    def delete(self, file_id: str) -> None:
        response = self._http.delete(f"{DRIVE_URL}/{file_id}", headers=self._headers())
        if response.status_code not in (200, 204, 404):
            raise _drive_error(response)


# ---------------------------------------------------------------------------------------------
# In-memory test double (BACKUP_DRIVE_PROVIDER=memory)
# ---------------------------------------------------------------------------------------------


@dataclass
class MemoryDrive:
    """One fake Google account: folders and files keyed by id, shared across client instances."""

    folders: dict[str, str] = field(default_factory=dict)  # folder id -> name
    files: dict[str, tuple[str, str, bytes]] = field(
        default_factory=dict
    )  # id -> (folder, name, blob)
    accounts: dict[str, str] = field(default_factory=dict)  # refresh token -> email
    codes: dict[str, str] = field(default_factory=dict)  # auth code -> email
    calls: list[str] = field(default_factory=list)

    def reset(self) -> None:
        self.folders.clear()
        self.files.clear()
        self.accounts.clear()
        self.codes.clear()
        self.calls.clear()

    def issue_code(self, email: str) -> str:
        code = secrets.token_urlsafe(16)
        self.codes[code] = email
        return code

    def tamper(self, file_id: str, offset: int = 40) -> None:
        folder, name, blob = self.files[file_id]
        flipped = bytearray(blob)
        flipped[offset] ^= 0xFF
        self.files[file_id] = (folder, name, bytes(flipped))


MEMORY_DRIVE = MemoryDrive()


class MemoryOAuthClient:
    def __init__(self, store: MemoryDrive = MEMORY_DRIVE) -> None:
        self.store = store

    def authorization_url(self, state: str) -> str:
        return f"memory://oauth?{urlencode({'scope': SCOPES, 'state': state})}"

    def exchange_code(self, code: str) -> OAuthGrant:
        email = self.store.codes.pop(code, None)
        if email is None:
            raise AppError(400, "BACKUP_OAUTH_EXCHANGE_FAILED", "Google did not accept the code")
        token = secrets.token_urlsafe(24)
        self.store.accounts[token] = email
        return OAuthGrant(refresh_token=token, account_email=email, scopes=SCOPES)


class MemoryDriveClient:
    def __init__(self, refresh_token: str, store: MemoryDrive = MEMORY_DRIVE) -> None:
        if refresh_token not in store.accounts:
            raise AppError(
                502, "BACKUP_DRIVE_AUTH", "Google Drive connection needs re-authorization"
            )
        self.store = store

    def ensure_folder(self, name: str) -> str:
        self.store.calls.append("ensure_folder")
        for folder_id, folder_name in self.store.folders.items():
            if folder_name == name:
                return folder_id
        folder_id = f"folder-{secrets.token_hex(6)}"
        self.store.folders[folder_id] = name
        return folder_id

    def upload(self, folder_id: str, name: str, blob: bytes) -> RemoteFile:
        self.store.calls.append("upload")
        file_id = f"file-{secrets.token_hex(6)}"
        self.store.files[file_id] = (folder_id, name, bytes(blob))
        return RemoteFile(id=file_id, name=name, size=len(blob))

    def list_files(self, folder_id: str) -> list[RemoteFile]:
        return [
            RemoteFile(id=file_id, name=name, size=len(blob))
            for file_id, (folder, name, blob) in self.store.files.items()
            if folder == folder_id
        ]

    def download(self, file_id: str) -> bytes:
        self.store.calls.append("download")
        try:
            return self.store.files[file_id][2]
        except KeyError as exc:
            raise AppError(404, "BACKUP_FILE_MISSING", "Backup file is missing on Drive") from exc

    def delete(self, file_id: str) -> None:
        self.store.calls.append("delete")
        self.store.files.pop(file_id, None)


def oauth_client(settings: Settings) -> OAuthClient:
    if settings.backup_drive_provider == "memory":
        return MemoryOAuthClient()
    return GoogleOAuthClient(settings)


def drive_client(settings: Settings, refresh_token: str) -> DriveClient:
    if settings.backup_drive_provider == "memory":
        return MemoryDriveClient(refresh_token)
    return GoogleDriveClient(settings, refresh_token)
