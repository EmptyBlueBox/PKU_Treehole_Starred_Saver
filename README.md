# PKU Treehole Starred Saver

## Introduction

This project is for saving your starred posts in PKU Treehole, including posts, images and comments, and saves the data in original JSON and Markdown formats (with image links and quote links) for easy viewing.

> [!NOTE]
> This project is not affiliated with Peking University nor the Peking University Youth Research Center.

## Usage

Clone the repository:

```bash
git clone git@github.com:EmptyBlueBox/PKU_Treehole_Starred_Saver.git
cd PKU_Treehole_Starred_Saver
```

Install dependencies with [uv](https://docs.astral.sh/uv/) :

```bash
uv sync
```

Copy `config.py` to `config_private.py` and enter your username and password in the new file.  

> [!WARNING]
> For security reasons, it is recommended to keep your credentials in `config_private.py` (which is ignored by version control) rather than `config.py`, especially if you plan to share your code. However, if you prefer, you can also fill in your credentials directly in `config.py`.

Run the code:

```bash
python main.py
```

## Structure

There will be three directories in the `data` directory after running the code:

```
.
└── data
    ├── image
    ├── post_json
    └── post_markdown
```

- The `image` directory stores the images associated with posts. Each image is named as `<pid>.<ext>`, where `pid` is the post ID (zero-padded to 7 digits, e.g., `0000123.jpg`) and `ext` is the image file extension.

- The `post_json` directory contains JSON files for each data collection task. Each file is named `<timestamp>.json`, where `timestamp` is the time the task was run. Each JSON file includes the original data for all posts retrieved in that task (since a single task may fetch multiple posts).

- The `post_markdown` directory holds the Markdown files for individual posts. Each file is named `<pid>.md`, with `pid` being the zero-padded post ID. These Markdown files include the time of this post and its comments, image links pointing to the `image` directory, and when a comment quotes another comment, a quote link is included for clarity.

## Notes

### To modify

You can also use this project to get a single post or a list of posts, but you'll have to manually modify the `main.py` file.

The `get_one_post_and_all_comments` function is used to get a single post and all its comments.

The `get_and_save_post_list` function is used to get a list of posts and save them to a JSON file and Markdown files.

The `get_and_save_followed_posts` function is used to get your starred posts and save them to a JSON file and Markdown files.

### Rate limit

The `get_and_save_post_list` function is restricted to 2 requests per second to avoid being blocked by the server. If you want to get more posts, you may increase the time interval between requests of the thread pool in the `main.py` file.

## Acknowledgments

This project refers to and utilizes code from [PKU Treehole Crawler](https://github.com/dfshfghj/PKUHoleCrawler-new). Many thanks to the original author!
