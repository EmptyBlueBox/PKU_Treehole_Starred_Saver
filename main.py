import datetime
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor

from tqdm import tqdm

from client import Client

try:
    from config_private import PASSWORD, USERNAME
except ImportError:
    from config import PASSWORD, USERNAME

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
        self.image_dir = os.path.join(self.data_dir, "image")
        self.post_json_dir = os.path.join(self.data_dir, "post_json")
        self.post_markdown_dir = os.path.join(self.data_dir, "post_markdown")
        for d in [
            self.image_dir,
            self.post_json_dir,
            self.post_markdown_dir,
        ]:
            if not os.path.exists(d):
                os.makedirs(d)

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
            The rate of post access is limited to 2 per second (0.5s interval between requests).
        """
        posts_data = []
        futures = []
        for idx, post_id in enumerate(
            tqdm(posts, desc="Submitting tasks", unit="post")
        ):
            if idx != 0:
                time.sleep(0.5)  # Limit to 2 requests per second
            futures.append(
                self.executor.submit(
                    lambda post_id=post_id: self.get_one_post_and_all_comments(post_id)
                )
            )
        for future in tqdm(futures, desc="Fetching results", unit="post"):
            post, comments = future.result()
            posts_data.append({"post": post, "comments": comments})
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
