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
python crawler.py
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
├── analysis
│   ├── 2025-07-24-05-02-18-rate_analysis.png
│   ├── 2025-07-24-05-02-18-concurrency_analysis.png
│   ├── 2025-07-24-05-03-51-rate_analysis.png
│   └── 2025-07-24-05-03-51-concurrency_analysis.png
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
├── crawler.py
├── pyproject.toml
├── README.md
├── save_markdown.py
└── uv.lock
```

- The `image` directory contains all images downloaded for posts and comments. Each image file is named as `<pid>.<ext>`, where `pid` is the post ID (zero-padded to 7 digits, e.g., `0000123.jpg`), and `ext` is the original image file extension (such as jpg, jpeg, gif, etc.).

- The `post_json` directory stores the raw data for each data collection session. Each file is named `<timestamp>.json`, where `timestamp` is the time when the data was collected (e.g., `2025-07-24-05-02-18.json`). Each JSON file contains a list of posts and their associated comments retrieved in that session.

- The `post_markdown` directory organizes the Markdown files generated for each post. For every data collection session, a subdirectory named after the corresponding JSON file is created. Inside each subdirectory, individual Markdown files are named `<pid>.md` (with zero-padded post IDs). Each Markdown file includes the post content, timestamp, all comments, and embeds image links (in absolute paths) pointing to the `image` directory. If a comment quotes another, the quoted content is included for clarity.

- The `analysis` directory contains the rate and concurrency analysis plots. Each plot is named `<timestamp>-rate_analysis.png` and `<timestamp>-concurrency_analysis.png`, where `timestamp` is the time when the data was collected (e.g., `2025-07-24-05-02-18`).

## Notes

### To modify

You can also use this project to get a single post or a list of posts, but you'll have to manually modify the `crawler.py` file.

The `get_one_post_and_all_comments` function is used to get a single post and all its comments.

The `get_and_save_post_list` function is used to get a list of posts and save them to a JSON file and Markdown files.

The `get_and_save_followed_posts` function is used to get your starred posts and save them to a JSON file and Markdown files.

### Rate limit

The `get_and_save_post_list` function enforces two types of limits to avoid being blocked by the server and to control resource usage:

1. **Submission Rate Limit**: The number of requests that can be submitted per second is limited by the `MAX_SUBMITTED_REQUESTS_PER_SECOND` parameter (set in `config.py` or `config_private.py`). By default, this is set to 10 requests per second. If you want to fetch more posts per second, you can increase this value, but be aware that setting it too high may result in your requests being blocked by the server.

2. **Concurrency (Parallelism) Limit**: The maximum number of requests that can be processed concurrently is controlled by the `MAX_PARALLEL_REQUESTS` parameter. This sets the size of the thread pool used for fetching posts and comments. Increasing this value allows more requests to be in progress at the same time, which can speed up data collection if your network and the server can handle it.

Both parameters can be adjusted in your `config_private.py` (preferred for personal settings) or `config.py` (default). For example:

```python
MAX_SUBMITTED_REQUESTS_PER_SECOND = 10  # Submission rate limit (requests per second)
MAX_PARALLEL_REQUESTS = 10             # Maximum number of concurrent requests
```

> [!NOTE]
> If you increase these values, monitor the rate and concurrency analysis plots generated in the `analysis` directory to ensure you are not overloading your system or being rate-limited by the server.
> The code will print analysis and save plots after each run to help you tune these parameters for optimal performance.

## Acknowledgments

This project refers to and utilizes code from [PKU Treehole Crawler](https://github.com/dfshfghj/PKUHoleCrawler-new). Many thanks to the original author!
