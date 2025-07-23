# PKU Treehole Starred Saver

## Introduction

This project is a tool for saving your starred posts in PKU Treehole, including posts, images and comments, and saves the data in original JSON and Markdown formats (with image links and quote links) for easy viewing.

> [!NOTE]
> This project is not affiliated with Peking University nor the Peking University Youth Research Center.

## Usage

Install dependencies

```bash
uv sync
```

Copy `config.py` to `config_private.py` and fill in your username and password.

Run the crawler

```bash
python app.py
```

## Notes

## To modify

You can also use this project to crawl a single post or a list of posts, but you'll have to manually modify the `app.py` file.

The `get_one_post_and_all_comments` function is used to crawl a single post and all its comments.

The `get_and_save_post_list` function is used to crawl a list of posts and save them to a JSON file and Markdown files.

The `get_and_save_followed_posts` function is used to crawl your starred posts and save them to a JSON file and Markdown files.

## Rate limit

The `get_and_save_post_list` function is restricted to 2 requests per second to avoid being blocked by the server.

## Acknowledgments

This project refers to and utilizes code from [PKU Treehole Crawler](https://github.com/dfshfghj/PKUHoleCrawler-new). Many thanks to the original author!
