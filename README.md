# PKU Treehole Starred Saver

## Introduction

This project is a tool for saving your starred posts in PKU Treehole, including posts, images and comments, and saves the data in original JSON and Markdown formats (with image links and quote links) for easy viewing.

> [!NOTE]
> This project is not affiliated with Peking University nor the Peking University Youth Research Center.

## Usage

Install dependencies with [uv](https://docs.astral.sh/uv/) :

```bash
uv sync
```

Copy `config.py` to `config_private.py` and enter your username and password in the new file.  

> [!WARNING]
> For security reasons, it is recommended to keep your credentials in `config_private.py` (which is ignored by version control) rather than `config.py`, especially if you plan to share your code. However, if you prefer, you can also fill in your credentials directly in `config.py`.

Run the tool:

```bash
python main.py
```

## Structure

There will be three directories in the `data` directory after running the tool:

```
.
└── data
    ├── image
    ├── post_json
    └── post_markdown
```

The `image` directory will contain the teasers of the posts, named as `<pid>.<ext>`, where `pid` is the post ID and `ext` is the extension of the image, where the `pid` is zero-padded to 7 digits.

The `post_json` directory will contain the JSON files of the **tasks**, each file is named as `<timestamp>.json` containing the original data of all the queried posts of this task (as one task may query a list of posts), where `timestamp` is the running timestamp of this task.

The `post_markdown` directory will contain the Markdown files of the **posts**, each file is named as `<pid>.md` , where `pid` is the post ID, zero-padded to 7 digits. The markdown files has image links to the `image` directory and quote links when a comment quotes another comment.

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
