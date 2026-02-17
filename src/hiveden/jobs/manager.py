import asyncio
import uuid
import logging
from datetime import datetime
from typing import Awaitable, Callable, Dict, List, Optional, AsyncIterator

from hiveden.jobs.models import Job, JobStatus, JobLog

logger = logging.getLogger(__name__)

class JobManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JobManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._jobs: Dict[str, Job] = {}
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}
        self._initialized = True

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def create_job(self, command: str) -> str:
        job_id = str(uuid.uuid4())
        job = Job(id=job_id, command=command)
        self._jobs[job_id] = job
        self._subscribers[job_id] = []
        
        # Start execution in background
        asyncio.create_task(self._run_job(job_id, command))
        
        return job_id

    def create_external_job(self, command: str) -> str:
        """Create a job record managed by external async workflow."""
        job_id = str(uuid.uuid4())
        self._jobs[job_id] = Job(id=job_id, command=command)
        self._subscribers[job_id] = []
        return job_id

    async def log(self, job_id: str, output: str, error: bool = False):
        """Append and broadcast a log entry for an existing job."""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        entry = JobLog(timestamp=datetime.now(), output=output, error=error)
        job.logs.append(entry)
        await self._broadcast(job_id, entry)

    async def run_external_job(
        self,
        job_id: str,
        worker: Callable[[str, "JobManager"], Awaitable[None]],
    ):
        """Run an externally provided coroutine as a tracked job."""
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        job.status = JobStatus.RUNNING
        try:
            await worker(job_id, self)
            job.status = JobStatus.COMPLETED
            job.exit_code = 0
        except Exception as exc:
            logger.exception("External job %s failed", job_id)
            job.status = JobStatus.FAILED
            job.exit_code = 1
            await self.log(job_id, f"Error: {exc}", error=True)
        finally:
            job.finished_at = datetime.now()
            await self._broadcast(job_id, None)

    async def _run_job(self, job_id: str, command: str):
        job = self._jobs[job_id]
        job.status = JobStatus.RUNNING
        
        logger.info(f"Starting job {job_id}: {command}")
        
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            async def read_stream(stream, is_error):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded_line = line.decode('utf-8', errors='replace').rstrip()
                    log_entry = JobLog(
                        timestamp=datetime.now(),
                        output=decoded_line,
                        error=is_error
                    )
                    job.logs.append(log_entry)
                    await self._broadcast(job_id, log_entry)

            # Run stdout and stderr readers concurrently
            await asyncio.gather(
                read_stream(process.stdout, False),
                read_stream(process.stderr, True)
            )

            exit_code = await process.wait()
            job.exit_code = exit_code
            job.finished_at = datetime.now()
            
            if exit_code == 0:
                job.status = JobStatus.COMPLETED
            else:
                job.status = JobStatus.FAILED
            
            # Signal completion
            await self._broadcast(job_id, None)
                
        except Exception as e:
            logger.error(f"Error executing job {job_id}: {e}")
            job.status = JobStatus.FAILED
            error_log = JobLog(
                timestamp=datetime.now(),
                output=f"Internal Error: {str(e)}",
                error=True
            )
            job.logs.append(error_log)
            await self._broadcast(job_id, error_log)
            await self._broadcast(job_id, None)
        
        finally:
            # Notify completion (optional special message or just close?)
            # We'll keep the job in memory for history
            pass

    async def _broadcast(self, job_id: str, log: Optional[JobLog]):
        if job_id in self._subscribers:
            for queue in self._subscribers[job_id]:
                await queue.put(log)

    async def subscribe(self, job_id: str) -> AsyncIterator[JobLog]:
        if job_id not in self._jobs:
            raise ValueError(f"Job {job_id} not found")

        queue = asyncio.Queue()
        if job_id not in self._subscribers:
            self._subscribers[job_id] = []
        self._subscribers[job_id].append(queue)

        job = self._jobs[job_id]
        
        # Yield existing logs first
        for log in job.logs:
            yield log

        # If job is already finished, we are done after history
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            return

        try:
            while True:
                # Wait for new logs
                log = await queue.get()
                if log is None:
                    break
                yield log
        except asyncio.CancelledError:
            pass
        finally:
            if job_id in self._subscribers:
                if queue in self._subscribers[job_id]:
                    self._subscribers[job_id].remove(queue)

    # Improved broadcast to handle completion signal?
    # For now, simple streaming is fine. The WebSocket handler will manage the connection.
    # To properly close the iterator, we need a signal.
