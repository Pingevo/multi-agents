"""Background scheduler — checks for due scheduled tasks and executes them."""

import asyncio
import traceback

from backend.agents.schedule_store import ScheduledTaskStore


class BackgroundScheduler:
    """Periodically checks for due scheduled tasks and executes them."""

    def __init__(self, check_interval: int = 300):
        """check_interval: seconds between checks (default 5 minutes)."""
        self.check_interval = check_interval
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        """Start the scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        print("[SCHEDULER] Background scheduler started", flush=True)

    async def stop(self):
        """Stop the scheduler loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        print("[SCHEDULER] Background scheduler stopped", flush=True)

    async def _loop(self):
        """Main loop — check for due tasks periodically."""
        while self._running:
            try:
                await asyncio.sleep(self.check_interval)
                await self._check_and_run()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[SCHEDULER] Error: {e}", flush=True)
                print(traceback.format_exc(), flush=True)

    async def _check_and_run(self):
        """Check all users' scheduled tasks and run due ones."""
        from pathlib import Path

        data_dir = Path("data")
        if not data_dir.exists():
            return

        # Find all scheduled task files
        sched_files = list(data_dir.glob("scheduled_tasks_*.json"))
        for f in sched_files:
            user_id = f.stem.replace("scheduled_tasks_", "")
            try:
                store = ScheduledTaskStore(user_id=user_id)
                due = store.get_due_tasks()
                for task in due:
                    print(f"[SCHEDULER] Running scheduled task '{task['name']}' for user {user_id}", flush=True)
                    await self._execute_scheduled(task, user_id, store)
            except Exception as e:
                print(f"[SCHEDULER] Error processing {user_id}: {e}", flush=True)

    async def _execute_scheduled(self, task: dict, user_id: str, store: ScheduledTaskStore):
        """Execute a single scheduled task by injecting it into the chat flow."""
        try:
            import chainlit as cl
            from backend.core.secretary import CentralSecretary
            from backend.llm.manager import LLMManager

            llm_manager = LLMManager()
            secretary = CentralSecretary(llm_manager)

            prompt = task.get("prompt", "")
            mode = task.get("mode", "plan")

            # Use secretary to assess and plan the task
            result = await secretary.assess_and_plan(prompt)

            # Mark as run
            store.mark_run(task["id"])
            print(f"[SCHEDULER] Completed scheduled task '{task['name']}'", flush=True)
        except Exception as e:
            print(f"[SCHEDULER] Failed to execute '{task.get('name', '?')}': {e}", flush=True)
            print(traceback.format_exc(), flush=True)


# Singleton
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler
