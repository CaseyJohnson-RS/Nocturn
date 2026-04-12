"""Unit tests for TagsService."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.app.common.exceptions import ConflictError, NotFoundError, ValidationError
from src.app.modules.tags.service import TagsService, validate_tag_name

# --- _validate_tag_name ---


class TestValidateTagName:
    def test_valid(self) -> None:
        assert validate_tag_name("work") == "work"

    def test_strips_whitespace(self) -> None:
        assert validate_tag_name("  work  ") == "work"

    def test_unicode(self) -> None:
        assert validate_tag_name("работа") == "работа"

    def test_hyphens(self) -> None:
        assert validate_tag_name("my-tag") == "my-tag"

    def test_spaces(self) -> None:
        assert validate_tag_name("my tag") == "my tag"

    def test_empty(self) -> None:
        with pytest.raises(ValidationError):
            validate_tag_name("")

    def test_whitespace_only(self) -> None:
        with pytest.raises(ValidationError):
            validate_tag_name("   ")

    def test_too_long(self) -> None:
        with pytest.raises(ValidationError):
            validate_tag_name("a" * 51)

    @pytest.mark.parametrize("name", ["tag@name", "tag#1", "tag!!", "tag/slash", "tag.dot"])
    def test_invalid_characters(self, name: str) -> None:
        with pytest.raises(ValidationError):
            validate_tag_name(name)


# --- Fixtures ---


def _mock_tag(
    tag_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    name: str = "work",
) -> MagicMock:
    t = MagicMock()
    t.id = tag_id or uuid.uuid4()
    t.user_id = user_id or uuid.uuid4()
    t.name = name
    t.created_at = datetime.now(UTC)
    return t


@pytest.fixture()
def repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def service(repo: AsyncMock) -> TagsService:
    svc = TagsService.__new__(TagsService)
    svc.repo = repo
    return svc


@pytest.fixture()
def user_id() -> uuid.UUID:
    return uuid.uuid4()


# --- create ---


class TestCreate:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.count_user_tags.return_value = 0
        repo.get_tag_by_name.return_value = None
        repo.create_tag.return_value = _mock_tag(user_id=user_id, name="work")

        result = await service.create(user_id, "work")

        assert result.name == "work"
        repo.create_tag.assert_called_once_with(user_id, "work")

    @pytest.mark.anyio()
    async def test_limit_reached(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.count_user_tags.return_value = 100

        with pytest.raises(ConflictError, match="limit"):
            await service.create(user_id, "work")

    @pytest.mark.anyio()
    async def test_duplicate_name(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.count_user_tags.return_value = 0
        repo.get_tag_by_name.return_value = _mock_tag(user_id=user_id, name="work")

        with pytest.raises(ConflictError, match="already exists"):
            await service.create(user_id, "work")

    @pytest.mark.anyio()
    async def test_invalid_name(self, service: TagsService, user_id: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            await service.create(user_id, "tag@invalid")


# --- get ---


class TestGet:
    @pytest.mark.anyio()
    async def test_found(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        tag = _mock_tag(user_id=user_id)
        repo.get_tag_by_id.return_value = tag

        result = await service.get(user_id, tag.id)

        assert result.id == tag.id

    @pytest.mark.anyio()
    async def test_not_found(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_tag_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.get(user_id, uuid.uuid4())


# --- list ---


class TestList:
    @pytest.mark.anyio()
    async def test_returns_tags(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        tags = [_mock_tag(user_id=user_id, name="a"), _mock_tag(user_id=user_id, name="b")]
        repo.list_tags.return_value = (tags, 2)

        result = await service.list(user_id)

        assert result.total == 2
        assert len(result.items) == 2

    @pytest.mark.anyio()
    async def test_empty(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.list_tags.return_value = ([], 0)

        result = await service.list(user_id)

        assert result.items == []
        assert result.total == 0

    @pytest.mark.anyio()
    async def test_passes_params(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.list_tags.return_value = ([], 0)

        await service.list(user_id, limit=10, offset=5, search="work")

        repo.list_tags.assert_called_once_with(user_id, 10, 5, "work")


# --- update ---


class TestUpdate:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        tag = _mock_tag(user_id=user_id, name="old")
        updated = _mock_tag(tag_id=tag.id, user_id=user_id, name="new")
        repo.get_tag_by_id.return_value = tag
        repo.get_tag_by_name.return_value = None
        repo.update_tag_name.return_value = updated

        result = await service.update(user_id, tag.id, "new")

        assert result.name == "new"
        repo.update_tag_name.assert_called_once_with(tag, "new")

    @pytest.mark.anyio()
    async def test_same_name_allowed(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        tag = _mock_tag(user_id=user_id, name="work")
        repo.get_tag_by_id.return_value = tag
        # get_tag_by_name returns the same tag
        repo.get_tag_by_name.return_value = tag
        repo.update_tag_name.return_value = tag

        result = await service.update(user_id, tag.id, "work")

        assert result.name == "work"

    @pytest.mark.anyio()
    async def test_name_taken_by_another(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        tag = _mock_tag(user_id=user_id, name="old")
        other = _mock_tag(user_id=user_id, name="taken")
        repo.get_tag_by_id.return_value = tag
        repo.get_tag_by_name.return_value = other

        with pytest.raises(ConflictError, match="already exists"):
            await service.update(user_id, tag.id, "taken")

    @pytest.mark.anyio()
    async def test_not_found(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_tag_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.update(user_id, uuid.uuid4(), "new")

    @pytest.mark.anyio()
    async def test_invalid_name(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        with pytest.raises(ValidationError):
            await service.update(user_id, uuid.uuid4(), "tag@bad")


# --- delete ---


class TestDelete:
    @pytest.mark.anyio()
    async def test_success(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        tag = _mock_tag(user_id=user_id)
        repo.get_tag_by_id.return_value = tag

        await service.delete(user_id, tag.id)

        repo.delete_tag.assert_called_once_with(tag)

    @pytest.mark.anyio()
    async def test_not_found(
        self,
        service: TagsService,
        repo: AsyncMock,
        user_id: uuid.UUID,
    ) -> None:
        repo.get_tag_by_id.return_value = None

        with pytest.raises(NotFoundError):
            await service.delete(user_id, uuid.uuid4())
