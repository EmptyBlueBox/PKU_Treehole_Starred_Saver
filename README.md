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

Run the crawler code, and the image and json files will be saved in the `data` directory, as shown in the `Structure` section.

```bash
python main.py
```

Run the markdown converter code, and the markdown files will be saved in the `data/post_markdown` directory, as shown in the `Structure` section.

```bash
python save_markdown.py --json 202x-xx-xx-xx-xx-xx.json
```

## Structure

There will be three directories in the `data` directory after running the code:

```
.
├── client.py
├── config_private.py
├── config.py
├── data
│   ├── image
│   │   ├── 1500000.gif
│   │   └── 7508259.jpeg
│   ├── post_json
│   │   ├── 2025-07-24-05-02-18.json
│   │   └── 2025-07-24-05-03-51.json
│   └── post_markdown
│       ├── 2025-07-24-05-02-18
│       │   ├── 1500000.md
│       │   ├── 7508259.md
│       │   └── 7541521.md
│       └── 2025-07-24-05-03-51
│           └── 7508259.md
├── main.py
├── pyproject.toml
├── README.md
├── save_markdown.py
└── uv.lock
```

- The `image` directory contains all images downloaded for posts and comments. Each image file is named as `<pid>.<ext>`, where `pid` is the post ID (zero-padded to 7 digits, e.g., `0000123.jpg`), and `ext` is the original image file extension (such as jpg, jpeg, gif, etc.).

- The `post_json` directory stores the raw data for each data collection session. Each file is named `<timestamp>.json`, where `timestamp` is the time when the data was collected (e.g., `2025-07-24-05-02-18.json`). Each JSON file contains a list of posts and their associated comments retrieved in that session.

- The `post_markdown` directory organizes the Markdown files generated for each post. For every data collection session, a subdirectory named after the corresponding JSON file is created. Inside each subdirectory, individual Markdown files are named `<pid>.md` (with zero-padded post IDs). Each Markdown file includes the post content, timestamp, all comments, and embeds image links (in absolute paths) pointing to the `image` directory. If a comment quotes another, the quoted content is included for clarity.

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
