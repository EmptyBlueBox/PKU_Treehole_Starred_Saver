import datetime
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import matplotlib.pyplot as plt
from matplotlib import rcParams
from tqdm import tqdm

from client import Client

try:
    from config_private import (
        MAX_PARALLEL_REQUESTS,
        MAX_SUBMITTED_REQUESTS_PER_SECOND,
        PASSWORD,
        USERNAME,
    )
except ImportError:
    from config import (
        MAX_PARALLEL_REQUESTS,
        MAX_SUBMITTED_REQUESTS_PER_SECOND,
        PASSWORD,
        USERNAME,
    )


class App:
    """
    Main application class for crawling and saving PKU Treehole posts and comments.
    Handles authentication, data fetching, and saving in JSON/Markdown formats.
    """

    def __init__(self):
        """
        Initialize the App, set up directories, and ensure authentication.
        """
        self.client = Client()
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        # Ensure required directories exist
        self.data_dir = os.path.join(self.current_dir, "data")
        self.analysis_dir = os.path.join(
            self.current_dir, "analysis"
        )  # New: analysis dir parallel to data
        self.image_dir = os.path.join(self.data_dir, "image")
        self.post_json_dir = os.path.join(self.data_dir, "post_json")
        self.post_markdown_dir = os.path.join(self.data_dir, "post_markdown")
        for d in [
            self.image_dir,
            self.post_json_dir,
            self.post_markdown_dir,
            self.analysis_dir,  # Ensure analysis dir exists
        ]:
            if not os.path.exists(d):
                os.makedirs(d)

        # Configure matplotlib for Chinese font support
        rcParams["font.sans-serif"] = ["SimHei", "Arial Unicode MS", "DejaVu Sans"]
        rcParams["axes.unicode_minus"] = False

        # Try to get unread status, if not logged in, perform login
        response = self.client.un_read()
        while response.status_code != 200:
            print(
                f"{response.status_code}: Need to login, use config_private.py first, if not available, use config.py"
            )
            # Use credentials from config.py
            username = USERNAME
            password = PASSWORD
            token = self.client.oauth_login(username, password)["token"]
            self.client.sso_login(token)
            response = self.client.un_read()

        # Handle additional authentication (SMS or token) if required
        while not response.json()["success"]:
            if response.json()["message"] == "请手机短信验证":
                tmp = input("Send verification code (Y/n): ")
                if tmp == "Y":
                    self.client.send_message()
                    code = input("SMS verification code: ")
                    self.client.login_by_message(code)
            elif response.json()["message"] == "请进行令牌验证":
                token = input("Mobile token: ")
                self.client.login_by_token(token)
            response = self.client.un_read()

    def get_one_post_and_all_comments(self, post_id):
        """
        Fetch a single post and all its comments. If the post is an image, download the image to the image directory.

        Args:
            post_id (int): The ID of the post to fetch.

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
                image_path = os.path.join(self.image_dir, image_filename)
                # Only download if the image does not already exist
                if not os.path.exists(image_path):
                    self.client.get_image(post_id, image_path)
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
        Fetch posts and their comments concurrently, save to a JSON file, and generate Markdown files for each post.

        Args:
            posts (list of int): List of post IDs to fetch.

        Returns:
            None
        Note:
            The rate of post access is limited by the MAX_SUBMITTED_REQUESTS_PER_SECOND parameter in config.py.
            Uses a token bucket algorithm for precise rate limiting.
        """
        import threading

        posts = list(
            set(posts)
        )  # Deduplication, to avoid repeatedly crawling the same post
        posts_data = []
        # For rate analysis
        submit_timestamps = []  # When each request is submitted
        complete_timestamps = []  # When each request is completed
        active_threads_samples = []  # Number of active threads at each sample
        active_threads = 0
        active_threads_lock = threading.Lock()

        # Token bucket rate limiter for rate control
        class TokenBucket:
            def __init__(self, max_tokens, refill_rate):
                """
                Token bucket rate limiter.

                Args:
                    max_tokens (int): Maximum number of tokens in the bucket
                    refill_rate (float): Tokens refilled per second
                """
                self.max_tokens = max_tokens
                self.tokens = 0
                self.refill_rate = refill_rate
                self.last_refill = time.time()
                self.lock = threading.Lock()

            def acquire(self):
                """
                Acquire a token. If no tokens available, wait until one is available.
                This method doesn't block other threads - it calculates when tokens will be available.
                """
                while True:
                    with self.lock:
                        now = time.time()
                        # Refill tokens based on elapsed time
                        elapsed = now - self.last_refill
                        self.tokens = min(
                            self.max_tokens, self.tokens + elapsed * self.refill_rate
                        )
                        self.last_refill = now

                        if self.tokens >= 1:
                            self.tokens -= 1
                            submit_timestamps.append(time.time())
                            return  # Token acquired successfully

                        # Calculate when next token will be available
                        time_to_next_token = (1 - self.tokens) / self.refill_rate

                    # Sleep outside the lock to avoid blocking other threads
                    # Use a small sleep to avoid busy waiting
                    time.sleep(min(time_to_next_token, 0.01))

        # Create token bucket with rate limiting
        token_bucket = TokenBucket(
            max_tokens=MAX_SUBMITTED_REQUESTS_PER_SECOND,
            refill_rate=MAX_SUBMITTED_REQUESTS_PER_SECOND,
        )

        # For detailed time series analysis
        time_series_data = {
            "timestamps": [],
            "submit_rates": [],
            "complete_rates": [],
            "active_threads": [],
        }

        start_time = time.time()
        sampling_thread_running = True

        def sample_metrics():
            """
            Background thread to sample metrics every 0.1 seconds.
            Uses a 1-second sliding window to calculate submit and complete rates.
            """
            nonlocal sampling_thread_running
            window_seconds = 1.0  # Sliding window size in seconds
            while sampling_thread_running:
                current_time = time.time()
                # Calculate submit rate in the last 1 second
                submit_in_window = [
                    t for t in submit_timestamps if current_time - t <= window_seconds
                ]
                submit_rate = len(submit_in_window) / window_seconds
                # Calculate complete rate in the last 1 second
                complete_in_window = [
                    t for t in complete_timestamps if current_time - t <= window_seconds
                ]
                complete_rate = len(complete_in_window) / window_seconds
                # Record data
                with active_threads_lock:
                    current_active_threads = active_threads
                time_series_data["timestamps"].append(current_time - start_time)
                time_series_data["submit_rates"].append(submit_rate)
                time_series_data["complete_rates"].append(complete_rate)
                time_series_data["active_threads"].append(current_active_threads)
                time.sleep(0.05)  # Sample every 1ms

        def fetch_post(post_id):
            """Fetch a post with token bucket rate limiting"""
            nonlocal active_threads
            with active_threads_lock:
                active_threads += 1
            try:
                # Acquire token before making request - this handles rate limiting
                token_bucket.acquire()
                return self.get_one_post_and_all_comments(post_id)
            finally:
                with active_threads_lock:
                    active_threads -= 1

        # Start background sampling thread
        sampling_thread = threading.Thread(target=sample_metrics, daemon=True)
        sampling_thread.start()

        # Submit all tasks at once - no blocking in main thread
        with ThreadPoolExecutor(max_workers=MAX_PARALLEL_REQUESTS) as executor:
            print(f"Submitting {len(posts)} tasks to thread pool...")
            futures = [executor.submit(fetch_post, post_id) for post_id in posts]

            # Collect results as they complete
            for future in tqdm(
                as_completed(futures),
                total=len(futures),
                desc="Fetching results",
                unit="post",
            ):
                # Sample active thread count
                with active_threads_lock:
                    active_threads_samples.append(active_threads)
                complete_timestamps.append(time.time())
                post, comments = future.result()
                posts_data.append({"post": post, "comments": comments})

        # Stop sampling thread
        sampling_thread_running = False
        sampling_thread.join(timeout=1)

        # Save JSON to post_json directory
        data_name = (
            os.path.join(
                self.post_json_dir,
                datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
            )
            + ".json"
        )
        with open(data_name, "w", encoding="utf-8") as file:
            json.dump(posts_data, file, indent=4, ensure_ascii=False)

        # --- Rate & concurrency analysis ---
        if len(submit_timestamps) > 1 and len(active_threads_samples) > 0:
            total_submit_time = submit_timestamps[-1] - submit_timestamps[0]
            avg_submit_rate = (
                (len(submit_timestamps) - 1) / total_submit_time
                if total_submit_time > 0
                else float("inf")
            )
            avg_active_threads = sum(active_threads_samples) / len(
                active_threads_samples
            )
            print("\n--- Rate & Concurrency Analysis ---")
            print(f"Total posts: {len(posts_data)}")
            print(
                f"Submission time span: {total_submit_time:.2f}s, Avg submit rate: {avg_submit_rate:.2f} req/s"
            )
            print(f"MAX_PARALLEL_REQUESTS: {MAX_PARALLEL_REQUESTS}")
            print(f"Average active threads: {avg_active_threads:.2f}")
            print()
            # Four cases analysis
            submit_limit = (
                MAX_SUBMITTED_REQUESTS_PER_SECOND
                if "MAX_SUBMITTED_REQUESTS_PER_SECOND" in globals()
                else None
            )
            # 1. Both are close to the upper limit
            if (
                avg_submit_rate >= 0.95 * submit_limit
                and avg_active_threads >= 0.95 * MAX_PARALLEL_REQUESTS
            ):
                print(
                    "Case 1: Both submit rate and thread pool are close to the upper limit. The overall performance has reached the maximum. If you want it faster, you can increase both parameters, but be aware of the website and local resource limits."
                )
            # 2. Both are far below the upper limit
            elif (
                avg_submit_rate < 0.95 * submit_limit
                and avg_active_threads < 0.95 * MAX_PARALLEL_REQUESTS
            ):
                print(
                    "Case 2: Both submit rate and thread pool are below the upper limit. The bottleneck may be in the network, target website, or single request duration. You can try increasing the parameters or analyze the duration of a single request."
                )
            # 3. Submit rate is close to the upper limit but thread pool is not full
            elif (
                avg_submit_rate >= 0.95 * submit_limit
                and avg_active_threads < 0.95 * MAX_PARALLEL_REQUESTS
            ):
                print(
                    "Case 3: Submit rate has reached the upper limit but the thread pool is not full. It is limited by the submit rate parameter. You can try increasing the submit rate parameter."
                )
            # 4. Submit rate is below the upper limit but thread pool is full
            elif (
                avg_submit_rate < 0.95 * submit_limit
                and avg_active_threads >= 0.95 * MAX_PARALLEL_REQUESTS
            ):
                print(
                    "Case 4: The thread pool is full but the submit rate is below the upper limit. It is limited by the number of concurrent threads. You can try increasing MAX_PARALLEL_REQUESTS."
                )
            else:
                print(
                    "Unknown case: Please check parameter settings and network environment."
                )
            print("--- End of Analysis ---\n")

        # Generate time series plots
        self.plot_rate_analysis(time_series_data, data_name.replace(".json", ""))
        self.plot_thread_analysis(time_series_data, data_name.replace(".json", ""))

    def plot_rate_analysis(self, time_series_data, file_prefix):
        """
        Plot submission rate and completion rate over time.

        Args:
            time_series_data (dict): Time series data containing timestamps, submit_rates, complete_rates
            file_prefix (str): File prefix for saving the plot
        """
        if not time_series_data["timestamps"]:
            print("No time series data available for rate analysis plot")
            return

        plt.figure(figsize=(12, 6))

        # Plot submit and complete rates
        plt.plot(
            time_series_data["timestamps"],
            time_series_data["submit_rates"],
            label="Submit Rate",
            linewidth=2,
            alpha=0.8,
        )
        plt.plot(
            time_series_data["timestamps"],
            time_series_data["complete_rates"],
            label="Complete Rate",
            linewidth=2,
            alpha=0.8,
        )

        # Add horizontal line for MAX_SUBMITTED_REQUESTS_PER_SECOND
        plt.axhline(
            y=MAX_SUBMITTED_REQUESTS_PER_SECOND,
            color="red",
            linestyle="--",
            label=f"MAX_SUBMITTED_REQUESTS_PER_SECOND = {MAX_SUBMITTED_REQUESTS_PER_SECOND}",
            linewidth=2,
            alpha=0.7,
        )

        plt.xlabel("Time (seconds)")
        plt.ylabel("Rate (requests/second)")
        plt.title("Request Submission and Completion Rate Time Series")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # Save plot
        plot_filename = os.path.join(
            self.analysis_dir, os.path.basename(f"{file_prefix}-rate_analysis.png")
        )
        plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
        print(f"Rate analysis plot saved to: {plot_filename}")
        plt.close()

    def plot_thread_analysis(self, time_series_data, file_prefix):
        """
        Plot active thread count over time.

        Args:
            time_series_data (dict): Time series data containing timestamps, active_threads
            file_prefix (str): File prefix for saving the plot
        """
        if not time_series_data["timestamps"]:
            print("No time series data available for thread analysis plot")
            return

        plt.figure(figsize=(12, 6))

        # Plot active threads
        plt.plot(
            time_series_data["timestamps"],
            time_series_data["active_threads"],
            label="Active Threads",
            linewidth=2,
            alpha=0.8,
            color="green",
        )

        # Add horizontal line for MAX_PARALLEL_REQUESTS
        plt.axhline(
            y=MAX_PARALLEL_REQUESTS,
            color="red",
            linestyle="--",
            label=f"MAX_PARALLEL_REQUESTS = {MAX_PARALLEL_REQUESTS}",
            linewidth=2,
            alpha=0.7,
        )

        plt.xlabel("Time (seconds)")
        plt.ylabel("Number of Threads")
        plt.title("Active Threads Time Series")
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # Save plot
        plot_filename = os.path.join(
            self.analysis_dir,
            os.path.basename(f"{file_prefix}-concurrency_analysis.png"),
        )
        plt.savefig(plot_filename, dpi=300, bbox_inches="tight")
        print(f"Thread analysis plot saved to: {plot_filename}")
        plt.close()

    def get_and_save_followed_posts(self):
        """
        Fetch all followed posts and save them using get_and_save_post_list.
        """
        followed_posts = self.client.get_followed()
        if followed_posts["success"]:
            last_page = followed_posts["data"]["last_page"]
            posts = [post["pid"] for post in followed_posts["data"]["data"]]
            for page in range(2, last_page + 1):
                followed_posts = self.client.get_followed(page=page)
                if followed_posts["success"]:
                    posts += [post["pid"] for post in followed_posts["data"]["data"]]
                else:
                    print(followed_posts["message"])
            self.get_and_save_post_list(posts)
        else:
            print(followed_posts["message"])


if __name__ == "__main__":
    app = App()
    app.get_and_save_followed_posts()
