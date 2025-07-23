import datetime
import json
import os
from concurrent.futures import ThreadPoolExecutor

from client import Client

try:
    from config_private import PASSWORD, USERNAME
except ImportError:
    from config import PASSWORD, USERNAME


class App:
    def __init__(self):
        self.client = Client()
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.exists(os.path.join(self.current_dir, "data", "download")):
            os.makedirs(os.path.join(self.current_dir, "data", "download"))

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

        while not response.json()["success"]:
            if response.json()["message"] == "请手机短信验证":
                tmp = input("发送验证码(Y/n)：")
                if tmp == "Y":
                    self.client.send_message()
                    code = input("短信验证码：")
                    self.client.login_by_message(code)
            elif response.json()["message"] == "请进行令牌验证":
                token = input("手机令牌：")
                self.client.login_by_token(token)
            response = self.client.un_read()

    def get_one_post_and_all_comments(self, post_id):
        post = self.client.get_post(post_id)
        if post["success"]:
            post = post["data"]
            if post["type"] == "image":
                image_type = post["url"].split(".")[-1]
                self.client.get_image(
                    post_id,
                    os.path.join(self.current_dir, "data", "download", post_id)
                    + "."
                    + image_type,
                )
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
            return {"pid": post_id, "text": "您查看的树洞不存在", "type": "text"}, []

    def get_and_save_post_list(self, posts):
        """
        Fetch posts and their comments concurrently and save them to a JSON file with proper UTF-8 encoding.

        Args:
            posts (list of int): List of post IDs to fetch.

        Returns:
            None
        """
        posts_data = []
        futures = [
            self.executor.submit(
                lambda post_id=post_id: self.get_one_post_and_all_comments(post_id)
            )
            for post_id in posts
        ]
        for future in futures:
            post, comments = future.result()
            posts_data.append({"post": post, "comments": comments})
        data_name = (
            os.path.join(
                self.current_dir,
                "data",
                datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S"),
            )
            + ".json"
        )
        # Save with UTF-8 encoding and ensure_ascii=False to properly store Chinese characters
        with open(data_name, "w", encoding="utf-8") as file:
            json.dump(posts_data, file, indent=4, ensure_ascii=False)

    def get_and_save_followed_posts(self):
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
