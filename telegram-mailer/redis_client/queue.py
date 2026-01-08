"""Redis queue management for task distribution."""

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from redis.asyncio import Redis

from common.constants import REDIS_PREFIX_QUEUE
from common.logger import get_logger

logger = get_logger(__name__)


@dataclass
class SendTask:
    """Task for sending a message to a chat."""

    task_id: str
    campaign_id: str
    account_id: str
    chat_id: int
    message_text: Optional[str]
    message_media: Optional[dict]
    created_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "SendTask":
        return cls(**json.loads(data))


@dataclass
class CampaignTask:
    """Task for campaign in queue."""

    campaign_id: str
    user_id: str
    priority: int
    is_admin: bool
    created_at: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data: str) -> "CampaignTask":
        return cls(**json.loads(data))


class QueueManager:
    """
    Manager for Redis-based task queues.

    Handles campaign queues and send task distribution.
    """

    # Queue keys
    PENDING_CAMPAIGNS = f"{REDIS_PREFIX_QUEUE}:campaigns:pending"
    ACTIVE_CAMPAIGNS = f"{REDIS_PREFIX_QUEUE}:campaigns:active"
    ADMIN_CAMPAIGNS = f"{REDIS_PREFIX_QUEUE}:admin:campaigns"

    def __init__(self, redis: Redis):
        """
        Initialize queue manager.

        Args:
            redis: Redis client instance
        """
        self.redis = redis

    def _send_queue_key(self, account_id: str) -> str:
        """Get send queue key for account."""
        return f"{REDIS_PREFIX_QUEUE}:send:{account_id}"

    # Campaign queue operations
    async def add_campaign(
        self,
        campaign_id: UUID,
        user_id: UUID,
        priority: int = 0,
        is_admin: bool = False,
    ) -> None:
        """
        Add campaign to pending queue.

        Args:
            campaign_id: Campaign UUID
            user_id: User UUID
            priority: Priority (higher = more important)
            is_admin: Whether this is admin campaign
        """
        task = CampaignTask(
            campaign_id=str(campaign_id),
            user_id=str(user_id),
            priority=priority,
            is_admin=is_admin,
            created_at=datetime.utcnow().isoformat(),
        )

        # Admin campaigns go to separate priority queue
        queue_key = self.ADMIN_CAMPAIGNS if is_admin else self.PENDING_CAMPAIGNS
        score = priority if is_admin else 0

        await self.redis.zadd(queue_key, {task.to_json(): score})
        logger.info(f"Campaign {campaign_id} added to queue (admin={is_admin})")

    async def get_next_campaign(self) -> Optional[CampaignTask]:
        """
        Get next campaign from queue (admin first, then regular).

        Returns:
            CampaignTask or None if queue is empty
        """
        # Try admin queue first
        result = await self.redis.zpopmax(self.ADMIN_CAMPAIGNS)
        if result:
            task_data, _ = result[0]
            return CampaignTask.from_json(task_data)

        # Then regular queue
        result = await self.redis.zpopmin(self.PENDING_CAMPAIGNS)
        if result:
            task_data, _ = result[0]
            return CampaignTask.from_json(task_data)

        return None

    async def mark_campaign_active(self, campaign_id: UUID) -> None:
        """
        Mark campaign as active.

        Args:
            campaign_id: Campaign UUID
        """
        await self.redis.sadd(self.ACTIVE_CAMPAIGNS, str(campaign_id))

    async def mark_campaign_inactive(self, campaign_id: UUID) -> None:
        """
        Mark campaign as inactive.

        Args:
            campaign_id: Campaign UUID
        """
        await self.redis.srem(self.ACTIVE_CAMPAIGNS, str(campaign_id))

    async def is_campaign_active(self, campaign_id: UUID) -> bool:
        """
        Check if campaign is active.

        Args:
            campaign_id: Campaign UUID

        Returns:
            True if active
        """
        return await self.redis.sismember(self.ACTIVE_CAMPAIGNS, str(campaign_id))

    async def get_active_campaigns(self) -> list[str]:
        """
        Get all active campaign IDs.

        Returns:
            List of campaign ID strings
        """
        return list(await self.redis.smembers(self.ACTIVE_CAMPAIGNS))

    async def get_pending_count(self) -> int:
        """
        Get number of pending campaigns.

        Returns:
            Number of pending campaigns
        """
        regular = await self.redis.zcard(self.PENDING_CAMPAIGNS)
        admin = await self.redis.zcard(self.ADMIN_CAMPAIGNS)
        return regular + admin

    # Send task operations
    async def add_send_task(
        self,
        account_id: UUID,
        campaign_id: UUID,
        chat_id: int,
        message_text: Optional[str] = None,
        message_media: Optional[dict] = None,
    ) -> str:
        """
        Add send task to account's queue.

        Args:
            account_id: Account UUID
            campaign_id: Campaign UUID
            chat_id: Target chat ID
            message_text: Message text
            message_media: Media attachments

        Returns:
            Task ID
        """
        import uuid

        task_id = str(uuid.uuid4())
        task = SendTask(
            task_id=task_id,
            campaign_id=str(campaign_id),
            account_id=str(account_id),
            chat_id=chat_id,
            message_text=message_text,
            message_media=message_media,
            created_at=datetime.utcnow().isoformat(),
        )

        queue_key = self._send_queue_key(str(account_id))
        await self.redis.rpush(queue_key, task.to_json())

        return task_id

    async def get_send_task(self, account_id: UUID) -> Optional[SendTask]:
        """
        Get next send task for account.

        Args:
            account_id: Account UUID

        Returns:
            SendTask or None if queue is empty
        """
        queue_key = self._send_queue_key(str(account_id))
        task_data = await self.redis.lpop(queue_key)

        if task_data:
            return SendTask.from_json(task_data)
        return None

    async def get_send_queue_length(self, account_id: UUID) -> int:
        """
        Get length of account's send queue.

        Args:
            account_id: Account UUID

        Returns:
            Queue length
        """
        queue_key = self._send_queue_key(str(account_id))
        return await self.redis.llen(queue_key)

    async def clear_send_queue(self, account_id: UUID) -> int:
        """
        Clear account's send queue.

        Args:
            account_id: Account UUID

        Returns:
            Number of cleared tasks
        """
        queue_key = self._send_queue_key(str(account_id))
        length = await self.redis.llen(queue_key)
        await self.redis.delete(queue_key)
        return length

    async def add_send_tasks_batch(
        self,
        account_id: UUID,
        campaign_id: UUID,
        chat_ids: list[int],
        message_text: Optional[str] = None,
        message_media: Optional[dict] = None,
    ) -> list[str]:
        """
        Add multiple send tasks at once.

        Args:
            account_id: Account UUID
            campaign_id: Campaign UUID
            chat_ids: List of target chat IDs
            message_text: Message text
            message_media: Media attachments

        Returns:
            List of task IDs
        """
        import uuid

        tasks = []
        task_ids = []

        for chat_id in chat_ids:
            task_id = str(uuid.uuid4())
            task_ids.append(task_id)

            task = SendTask(
                task_id=task_id,
                campaign_id=str(campaign_id),
                account_id=str(account_id),
                chat_id=chat_id,
                message_text=message_text,
                message_media=message_media,
                created_at=datetime.utcnow().isoformat(),
            )
            tasks.append(task.to_json())

        if tasks:
            queue_key = self._send_queue_key(str(account_id))
            await self.redis.rpush(queue_key, *tasks)

        return task_ids
