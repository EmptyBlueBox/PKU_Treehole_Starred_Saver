"""
PKU Treehole Starred Saver API Backend

This module provides a FastAPI-based web backend for the PKU Treehole starred posts crawler.
Features include user authentication, task queuing, progress tracking, and file downloads.
"""

import asyncio
import datetime
import json
import os
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from client import Client
from save_markdown import save_posts_to_markdown

# Configuration
MAX_CONCURRENT_TASKS = 2  # Maximum number of concurrent crawling tasks
TASK_TIMEOUT = 3600  # Task timeout in seconds (1 hour)

# Global state management
active_tasks: Dict[str, dict] = {}
task_queue: List[str] = []
task_executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_TASKS)


class UserLoginRequest(BaseModel):
    """
    User login request model.

    Attributes:
        username (str): PKU username/student ID
        password (str): PKU password
    """

    username: str
    password: str


class VerificationRequest(BaseModel):
    """
    SMS verification request model.

    Attributes:
        task_id (str): Task ID from login response
        verification_code (str): SMS verification code
    """

    task_id: str
    verification_code: str


class TaskStatus(BaseModel):
    """
    Task status response model.

    Attributes:
        task_id (str): Unique task identifier
        status (str): Current task status (pending, authenticating, crawling, completed, failed, awaiting_verification)
        progress (float): Progress percentage (0-100)
        estimated_time_remaining (Optional[int]): Estimated seconds remaining
        message (str): Status message
        queue_position (Optional[int]): Position in queue if waiting
        download_url (Optional[str]): Download URL if completed
    """

    task_id: str
    status: str
    progress: float
    estimated_time_remaining: Optional[int] = None
    message: str = ""
    queue_position: Optional[int] = None
    download_url: Optional[str] = None


class QueueStatus(BaseModel):
    """
    Queue status response model.

    Attributes:
        active_tasks (int): Number of currently active tasks
        queued_tasks (int): Number of tasks in queue
        max_concurrent (int): Maximum concurrent tasks allowed
    """

    active_tasks: int
    queued_tasks: int
    max_concurrent: int


# FastAPI app initialization
app = FastAPI(
    title="PKU Treehole Starred Saver API",
    description="API backend for crawling and saving PKU Treehole starred posts",
    version="1.0.0",
)

# CORS middleware for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


def get_queue_position(task_id: str) -> Optional[int]:
    """
    Get the position of a task in the queue.

    Args:
        task_id (str): Task ID to check

    Returns:
        Optional[int]: Queue position (1-based) or None if not in queue
    """
    try:
        return task_queue.index(task_id) + 1
    except ValueError:
        return None


def estimate_remaining_time(task_id: str) -> Optional[int]:
    """
    Estimate remaining time for a task.

    Args:
        task_id (str): Task ID to estimate

    Returns:
        Optional[int]: Estimated seconds remaining or None if unknown
    """
    if task_id not in active_tasks:
        return None

    task = active_tasks[task_id]
    if task["status"] == "crawling":
        # Estimate based on progress and elapsed time
        start_time = task.get("start_time")
        progress = task.get("progress", 0)

        if start_time and progress > 0:
            elapsed = datetime.datetime.now().timestamp() - start_time
            total_estimated = elapsed / (progress / 100)
            remaining = total_estimated - elapsed
            return max(0, int(remaining))

    elif task["status"] == "pending":
        # Estimate based on queue position and average task time
        position = get_queue_position(task_id)
        if position:
            # Assume average task takes 10 minutes
            avg_task_time = 600
            return position * avg_task_time

    return None


class TaskCrawlerApp:
    """
    Custom crawler app for individual tasks with progress tracking.
    """

    def __init__(self, task_id: str, username: str, password: str):
        """
        Initialize the task crawler.

        Args:
            task_id (str): Unique task identifier
            username (str): PKU username
            password (str): PKU password
        """
        self.task_id = task_id
        self.username = username
        self.password = password

        # Initialize client
        self.client = Client()
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.current_dir = os.path.dirname(os.path.abspath(__file__))

        # Create shared and task-specific directories
        self.taskdata_dir = os.path.join(self.current_dir, "TaskData")
        self.shared_image_dir = os.path.join(
            self.taskdata_dir, "Images"
        )  # Shared images
        self.task_dir = os.path.join(self.taskdata_dir, task_id)
        self.data_dir = os.path.join(self.task_dir, "Data")
        self.post_json_dir = os.path.join(self.data_dir, "PostJson")
        self.post_markdown_dir = os.path.join(self.data_dir, "PostMarkdown")

        for d in [
            self.taskdata_dir,
            self.shared_image_dir,
            self.task_dir,
            self.data_dir,
            self.post_json_dir,
            self.post_markdown_dir,
        ]:
            if not os.path.exists(d):
                os.makedirs(d)

    def authenticate(self):
        """
        Perform authentication for this task.

        Returns:
            bool: True if authentication successful, False if verification needed
        """
        try:
            # Update task status
            active_tasks[self.task_id]["status"] = "authenticating"
            active_tasks[self.task_id]["message"] = "正在登录..."

            # OAuth login
            response = self.client.oauth_login(self.username, self.password)
            if "token" not in response:
                raise Exception(f"Login failed: {response}")

            token = response["token"]
            self.client.sso_login(token)

            # Check if additional verification is needed
            response = self.client.un_read()
            if response.status_code != 200 or not response.json().get("success"):
                message = response.json().get("message", "Unknown error")
                if "手机短信验证" in message:
                    active_tasks[self.task_id]["status"] = "awaiting_verification"
                    active_tasks[self.task_id]["message"] = "需要手机验证码"
                    # Send SMS
                    self.client.send_message()
                    return False
                else:
                    raise Exception(f"Authentication failed: {message}")

            # Authentication successful
            active_tasks[self.task_id]["status"] = "crawling"
            active_tasks[self.task_id]["message"] = "开始抓取数据..."
            return True

        except Exception as e:
            active_tasks[self.task_id]["status"] = "failed"
            active_tasks[self.task_id]["message"] = f"认证失败: {str(e)}"
            raise

    def verify_sms(self, verification_code: str):
        """
        Verify SMS code and continue authentication.

        Args:
            verification_code (str): SMS verification code

        Returns:
            bool: True if verification successful
        """
        try:
            response = self.client.login_by_message(verification_code)

            if response.status_code == 200:
                # Verification successful
                active_tasks[self.task_id]["status"] = "crawling"
                active_tasks[self.task_id]["message"] = "验证成功，开始抓取数据..."
                return True
            else:
                raise Exception("Verification failed")

        except Exception as e:
            active_tasks[self.task_id]["status"] = "failed"
            active_tasks[self.task_id]["message"] = f"验证失败: {str(e)}"
            raise

    def get_one_post_and_all_comments(self, post_id):
        """
        Fetch a single post and all its comments.
        Uses shared image storage to avoid duplicate downloads.

        Args:
            post_id (int): The ID of the post to fetch

        Returns:
            tuple: (post (dict), comments (list of dict))
        """
        post = self.client.get_post(post_id)
        image_filename = None
        if post["success"]:
            post = post["data"]
            if post["type"] == "image":
                image_type = post["url"].split(".")[-1]
                padded_pid = str(post_id).zfill(7)
                image_filename = f"{padded_pid}.{image_type}"
                # Use shared image directory
                shared_image_path = os.path.join(self.shared_image_dir, image_filename)
                # Only download if the image does not already exist in shared storage
                if not os.path.exists(shared_image_path):
                    print(
                        f"[DOWNLOAD] Downloading image for post {post_id}: {image_filename}"
                    )
                    self.client.get_image(post_id, shared_image_path)
                else:
                    print(
                        f"[CACHE] Using cached image for post {post_id}: {image_filename}"
                    )
                post["image_filename"] = image_filename  # Add for markdown reference
            comments = self.client.get_comment(post_id)["data"]

            if comments:
                last_page = comments["last_page"]
                for page in range(2, last_page + 1):
                    part_comments = self.client.get_comment(post_id, page)["data"]
                    comments["data"] += part_comments["data"]
                comments = comments["data"]
            else:
                comments = []
            return post, comments
        else:
            return {
                "pid": post_id,
                "text": "The post you are viewing does not exist",
                "type": "text",
            }, []

    def get_and_save_post_list(self, posts):
        """
        Fetch posts and their comments with progress tracking.

        Args:
            posts (list of int): List of post IDs to fetch

        Returns:
            list: Posts data
        """
        posts = list(set(posts))
        # posts = posts[:10]

        total_posts = len(posts)
        completed_posts = 0

        # Update progress
        active_tasks[self.task_id]["progress"] = 0
        active_tasks[self.task_id]["total_posts"] = total_posts
        active_tasks[self.task_id]["message"] = f"开始抓取 {total_posts} 个帖子..."

        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Thread-safe progress tracking
        progress_lock = threading.Lock()

        def fetch_post_with_progress(post_id):
            nonlocal completed_posts
            try:
                # Add a small delay to make progress visible for testing
                time.sleep(0.1)
                post, comments = self.get_one_post_and_all_comments(post_id)

                # Thread-safe progress update
                with progress_lock:
                    completed_posts += 1
                    progress = (completed_posts / total_posts) * 100
                    active_tasks[self.task_id]["progress"] = progress
                    active_tasks[self.task_id]["message"] = (
                        f"已完成 {completed_posts}/{total_posts} 个帖子"
                    )
                    print(
                        f"[DEBUG] Task {self.task_id}: Progress {progress:.1f}% ({completed_posts}/{total_posts})"
                    )

                return {"post": post, "comments": comments}
            except Exception as e:
                print(f"[ERROR] Failed to fetch post {post_id}: {e}")
                with progress_lock:
                    completed_posts += 1
                    progress = (completed_posts / total_posts) * 100
                    active_tasks[self.task_id]["progress"] = progress
                    active_tasks[self.task_id]["message"] = (
                        f"已完成 {completed_posts}/{total_posts} 个帖子 (部分失败)"
                    )
                return {
                    "post": {"pid": post_id, "text": "Failed to fetch", "type": "text"},
                    "comments": [],
                }

        posts_data = []

        # Use ThreadPoolExecutor for concurrent processing (similar to original crawler)
        max_workers = min(10, len(posts))  # Limit concurrent requests
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_post = {
                executor.submit(fetch_post_with_progress, post_id): post_id
                for post_id in posts
            }

            # Collect results as they complete
            for future in as_completed(future_to_post):
                post_id = future_to_post[future]
                try:
                    result = future.result()
                    posts_data.append(result)
                except Exception as e:
                    print(f"[ERROR] Exception for post {post_id}: {e}")
                    # Add error result
                    posts_data.append(
                        {
                            "post": {
                                "pid": post_id,
                                "text": "Exception occurred",
                                "type": "text",
                            },
                            "comments": [],
                        }
                    )

        # Save JSON with timestamp naming
        timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        data_name = os.path.join(self.post_json_dir, f"{timestamp}.json")
        with open(data_name, "w", encoding="utf-8") as file:
            json.dump(posts_data, file, indent=4, ensure_ascii=False)

        print(f"[SAVE] Saved JSON data to {data_name}")

        # Generate markdown with timestamp naming
        markdown_dir = os.path.join(self.post_markdown_dir, timestamp)
        save_posts_to_markdown(
            posts_data, markdown_dir, self.shared_image_dir, data_name
        )

        print(f"[SAVE] Generated markdown files in {markdown_dir}")

        # Create zip file with student ID as root folder name
        zip_path = os.path.join(self.task_dir, f"{timestamp}_{self.username}.zip")
        student_id = self.username  # Use username as student ID for folder name

        print(f"[PACK] Creating zip package: {zip_path}")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            # Add markdown files to root of student_id folder
            for root, dirs, files in os.walk(markdown_dir):
                for file in files:
                    if file.endswith(".md"):
                        file_path = os.path.join(root, file)
                        # Put markdown files directly in student_id folder
                        arcname = os.path.join(student_id, file)
                        zipf.write(file_path, arcname)
                        print(f"[PACK] Added markdown: {file}")

            # Copy images from shared storage to zip
            # First, collect all image filenames used in posts
            used_images = set()
            for item in posts_data:
                post = item["post"]
                if post.get("type") == "image" and post.get("image_filename"):
                    used_images.add(post["image_filename"])

            # Add used images to zip
            for image_filename in used_images:
                shared_image_path = os.path.join(self.shared_image_dir, image_filename)
                if os.path.exists(shared_image_path):
                    arcname = os.path.join(student_id, "Image", image_filename)
                    zipf.write(shared_image_path, arcname)
                    print(f"[PACK] Added image: {image_filename}")
                else:
                    print(
                        f"[WARNING] Image not found in shared storage: {image_filename}"
                    )

            # Add RawJson folder with the JSON data
            raw_json_dir = os.path.join(markdown_dir, "RawJson")
            if os.path.exists(raw_json_dir):
                for root, dirs, files in os.walk(raw_json_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Put JSON files in student_id/RawJson/ folder
                        rel_path = os.path.relpath(file_path, raw_json_dir)
                        arcname = os.path.join(student_id, "RawJson", rel_path)
                        zipf.write(file_path, arcname)
                        print(f"[PACK] Added JSON: {file}")

        print(f"[PACK] Package created successfully: {os.path.basename(zip_path)}")

        active_tasks[self.task_id]["zip_path"] = zip_path
        return posts_data

    def get_and_save_followed_posts(self):
        """
        Fetch all followed posts and save them.
        """
        active_tasks[self.task_id]["message"] = "获取收藏列表..."
        active_tasks[self.task_id]["progress"] = 5  # Show initial progress

        try:
            followed_posts = self.client.get_followed()
            if not followed_posts["success"]:
                raise Exception(followed_posts["message"])

            # Get all pages of followed posts
            last_page = followed_posts["data"]["last_page"]
            posts = [post["pid"] for post in followed_posts["data"]["data"]]

            active_tasks[self.task_id]["message"] = (
                f"获取收藏列表... (第1/{last_page}页)"
            )

            for page in range(2, last_page + 1):
                active_tasks[self.task_id]["message"] = (
                    f"获取收藏列表... (第{page}/{last_page}页)"
                )
                followed_posts = self.client.get_followed(page=page)
                if followed_posts["success"]:
                    posts += [post["pid"] for post in followed_posts["data"]["data"]]
                else:
                    print(
                        f"[WARNING] Failed to get page {page}: {followed_posts['message']}"
                    )

            active_tasks[self.task_id]["progress"] = 10  # Collection phase complete
            active_tasks[self.task_id]["message"] = (
                f"收藏列表获取完成，共{len(posts)}个帖子"
            )
            print(f"[DEBUG] Task {self.task_id}: Found {len(posts)} posts to crawl")

            # Start crawling posts
            self.get_and_save_post_list(posts)

        except Exception as e:
            print(f"[ERROR] Failed to get followed posts: {e}")
            raise Exception(f"获取收藏列表失败: {str(e)}")


async def run_crawler_task(task_id: str, username: str, password: str):
    """
    Run the crawler task asynchronously.

    Args:
        task_id (str): Unique task identifier
        username (str): PKU username
        password (str): PKU password
    """
    import asyncio

    def run_in_thread():
        """Run the crawler in a separate thread to avoid blocking."""
        crawler = None
        task_completed = False

        try:
            print(f"[DEBUG] Starting crawler task {task_id} for user {username}")

            # Update task status
            active_tasks[task_id].update(
                {
                    "status": "authenticating",
                    "start_time": datetime.datetime.now().timestamp(),
                    "progress": 0,
                }
            )

            # Create and run crawler
            crawler = TaskCrawlerApp(task_id, username, password)

            # Perform authentication
            auth_success = crawler.authenticate()

            # If awaiting verification, stop here and wait for user input
            if not auth_success:
                print(f"[DEBUG] Task {task_id} awaiting verification")
                # Store crawler instance for later verification
                active_tasks[task_id]["crawler"] = crawler
                return  # Don't clean up crawler instance yet

            print(f"[DEBUG] Task {task_id} authentication successful, starting crawl")

            # Get and save followed posts
            crawler.get_and_save_followed_posts()

            # Task completed
            active_tasks[task_id].update(
                {
                    "status": "completed",
                    "progress": 100,
                    "message": "抓取完成",
                    "completed_at": datetime.datetime.now().timestamp(),
                }
            )

            print(f"[DEBUG] Task {task_id} completed successfully")
            task_completed = True

        except Exception as e:
            print(f"[ERROR] Task {task_id} failed: {e}")
            # Task failed
            active_tasks[task_id].update(
                {"status": "failed", "message": f"抓取失败: {str(e)}", "error": str(e)}
            )
            task_completed = True

        finally:
            # Only clean up if task is truly completed or failed
            if task_completed:
                # Remove from queue if present
                if task_id in task_queue:
                    task_queue.remove(task_id)
                # Clean up crawler instance
                if "crawler" in active_tasks.get(task_id, {}):
                    del active_tasks[task_id]["crawler"]
                    print(f"[DEBUG] Cleaned up crawler instance for task {task_id}")

    # Run in thread pool to avoid blocking the async loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_in_thread)


@app.post("/api/auth/login")
async def login(request: UserLoginRequest, background_tasks: BackgroundTasks) -> dict:
    """
    Initiate user login and start the authentication process.

    Args:
        request (UserLoginRequest): Login credentials
        background_tasks (BackgroundTasks): FastAPI background tasks

    Returns:
        dict: Response containing task_id and initial status
    """
    # Generate unique task ID
    task_id = str(uuid.uuid4())

    # Initialize task
    active_tasks[task_id] = {
        "task_id": task_id,
        "username": request.username,
        "password": request.password,  # Store password securely for queue processing
        "status": "pending",
        "progress": 0,
        "message": "等待开始",
        "created_at": datetime.datetime.now().timestamp(),
    }

    # Check if we can start immediately or need to queue
    running_tasks = sum(
        1
        for task in active_tasks.values()
        if task["status"] in ["authenticating", "crawling"]
    )

    if running_tasks < MAX_CONCURRENT_TASKS:
        # Start immediately
        background_tasks.add_task(
            run_crawler_task, task_id, request.username, request.password
        )
    else:
        # Add to queue
        task_queue.append(task_id)
        active_tasks[task_id]["message"] = f"排队中，当前位置: {len(task_queue)}"

    return {
        "success": True,
        "task_id": task_id,
        "message": "任务已创建",
        "status": active_tasks[task_id]["status"],
    }


@app.post("/api/auth/verify")
async def verify_sms(
    request: VerificationRequest, background_tasks: BackgroundTasks
) -> dict:
    """
    Verify SMS code and continue with the crawling process.

    Args:
        request (VerificationRequest): Verification request with task_id and code
        background_tasks (BackgroundTasks): FastAPI background tasks

    Returns:
        dict: Response indicating verification result
    """
    task_id = request.task_id

    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = active_tasks[task_id]
    if task["status"] != "awaiting_verification":
        raise HTTPException(status_code=400, detail="Task not awaiting verification")

    try:
        # Get the crawler instance and verify SMS
        crawler = task.get("crawler")
        if not crawler:
            raise Exception("Crawler instance not found")

        # Verify SMS code
        verification_success = crawler.verify_sms(request.verification_code)

        if verification_success:
            # Continue with crawling in background
            background_tasks.add_task(continue_crawling_after_verification, task_id)

            return {"success": True, "message": "验证成功", "task_id": task_id}
        else:
            raise Exception("Verification failed")

    except Exception as e:
        task["status"] = "failed"
        task["message"] = f"验证失败: {str(e)}"
        return {"success": False, "message": f"验证失败: {str(e)}", "task_id": task_id}


async def continue_crawling_after_verification(task_id: str):
    """
    Continue crawling after successful SMS verification.

    Args:
        task_id (str): Task ID to continue
    """

    def run_verification_in_thread():
        """Run verification continuation in thread."""
        try:
            print(f"[DEBUG] Continuing crawling after verification for task {task_id}")
            task = active_tasks[task_id]
            crawler = task.get("crawler")

            if not crawler:
                raise Exception("Crawler instance not found")

            # Get and save followed posts
            crawler.get_and_save_followed_posts()

            # Task completed
            active_tasks[task_id].update(
                {
                    "status": "completed",
                    "progress": 100,
                    "message": "抓取完成",
                    "completed_at": datetime.datetime.now().timestamp(),
                }
            )

            print(f"[DEBUG] Task {task_id} completed after verification")

        except Exception as e:
            print(f"[ERROR] Task {task_id} failed after verification: {e}")
            # Task failed
            active_tasks[task_id].update(
                {"status": "failed", "message": f"抓取失败: {str(e)}", "error": str(e)}
            )

        finally:
            # Clean up crawler instance and queue
            if task_id in task_queue:
                task_queue.remove(task_id)
            if "crawler" in active_tasks.get(task_id, {}):
                del active_tasks[task_id]["crawler"]
                print(f"[DEBUG] Cleaned up crawler instance for task {task_id}")

    # Run in thread pool to avoid blocking
    import asyncio

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_verification_in_thread)


@app.get("/api/crawl/status/{task_id}")
async def get_task_status(task_id: str) -> TaskStatus:
    """
    Get the current status of a crawling task.

    Args:
        task_id (str): Task ID to check

    Returns:
        TaskStatus: Current task status and progress information
    """
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = active_tasks[task_id]
    queue_position = get_queue_position(task_id)
    estimated_time = estimate_remaining_time(task_id)

    download_url = None
    if task["status"] == "completed" and "zip_path" in task:
        download_url = f"/api/download/{task_id}"

    return TaskStatus(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
        estimated_time_remaining=estimated_time,
        message=task["message"],
        queue_position=queue_position,
        download_url=download_url,
    )


@app.get("/api/queue/status")
async def get_queue_status() -> QueueStatus:
    """
    Get the current queue status.

    Returns:
        QueueStatus: Current queue and active task information
    """
    active_count = sum(
        1
        for task in active_tasks.values()
        if task["status"] in ["authenticating", "crawling"]
    )

    return QueueStatus(
        active_tasks=active_count,
        queued_tasks=len(task_queue),
        max_concurrent=MAX_CONCURRENT_TASKS,
    )


@app.get("/api/download/{task_id}")
async def download_results(task_id: str):
    """
    Download the results zip file for a completed task.

    Args:
        task_id (str): Task ID to download results for

    Returns:
        FileResponse: Zip file containing markdown results
    """
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")

    task = active_tasks[task_id]
    if task["status"] != "completed":
        raise HTTPException(status_code=400, detail="Task not completed")

    if "zip_path" not in task or not os.path.exists(task["zip_path"]):
        raise HTTPException(status_code=404, detail="Results file not found")

    # Get student ID and timestamp for filename
    student_id = task.get("username", task_id)
    zip_filename = os.path.basename(task["zip_path"])

    return FileResponse(
        task["zip_path"],
        filename=zip_filename,  # Keep original timestamp_username.zip format
        media_type="application/zip",
    )


@app.get("/api/tasks")
async def list_tasks() -> List[TaskStatus]:
    """
    List all tasks with their current status.

    Returns:
        List[TaskStatus]: List of all tasks and their status
    """
    tasks = []
    for task_id, task in active_tasks.items():
        queue_position = get_queue_position(task_id)
        estimated_time = estimate_remaining_time(task_id)

        download_url = None
        if task["status"] == "completed" and "zip_path" in task:
            download_url = f"/api/download/{task_id}"

        tasks.append(
            TaskStatus(
                task_id=task_id,
                status=task["status"],
                progress=task["progress"],
                estimated_time_remaining=estimated_time,
                message=task["message"],
                queue_position=queue_position,
                download_url=download_url,
            )
        )

    return tasks


@app.get("/")
async def root():
    """
    Serve the main frontend page or API information.

    Returns:
        FileResponse or dict: Frontend HTML page or API information
    """
    # If static files exist, serve the main page
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")

    # Otherwise return API information
    return {
        "name": "PKU Treehole Starred Saver API",
        "version": "1.0.0",
        "description": "API backend for crawling and saving PKU Treehole starred posts",
        "endpoints": {
            "login": "POST /api/auth/login",
            "verify": "POST /api/auth/verify",
            "status": "GET /api/crawl/status/{task_id}",
            "queue": "GET /api/queue/status",
            "download": "GET /api/download/{task_id}",
            "tasks": "GET /api/tasks",
        },
        "frontend": "Visit / for the web interface (if static files are available)",
    }


# Background task to process queue
async def process_queue():
    """
    Background task to process the task queue.
    Starts queued tasks when slots become available.
    """
    while True:
        try:
            # Count running tasks
            running_tasks = sum(
                1
                for task in active_tasks.values()
                if task["status"] in ["authenticating", "crawling"]
            )

            # Start queued tasks if slots available
            while running_tasks < MAX_CONCURRENT_TASKS and task_queue:
                task_id = task_queue.pop(0)
                if task_id in active_tasks:
                    task = active_tasks[task_id]
                    username = task["username"]
                    password = task["password"]
                    asyncio.create_task(run_crawler_task(task_id, username, password))
                    running_tasks += 1

            await asyncio.sleep(10)  # Check every 10 seconds

        except Exception as e:
            print(f"Queue processing error: {e}")
            await asyncio.sleep(10)


# Start background queue processor
@app.on_event("startup")
async def startup_event():
    """Start background tasks on app startup."""
    asyncio.create_task(process_queue())


if __name__ == "__main__":
    import uvicorn

    # Create necessary directories
    os.makedirs("TaskData", exist_ok=True)

    uvicorn.run(app, host="0.0.0.0", port=8000)
