import os
import datetime
import json


def format_time(t):
    """
    Convert a timestamp or string to a human-readable time string.

    Args:
        t (int|float|str): Timestamp (seconds) or time string.

    Returns:
        str: Formatted time string 'YYYY-MM-DD HH:MM:SS' or 'unknown'.
    """
    if t is None:
        return "unknown"
    if isinstance(t, (int, float)):
        try:
            return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "unknown"
    if isinstance(t, str):
        try:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d %H:%M:%S"):
                try:
                    dt = datetime.datetime.strptime(t, fmt)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    continue
            return t
        except Exception:
            return "unknown"
    return "unknown"


def save_posts_to_markdown(posts_data, markdown_dir, image_dir):
    """
    Save a list of posts (with comments) to Markdown files, one per post.

    Args:
        posts_data (list of dict): Each dict must have keys 'post' (dict) and 'comments' (list of dict).
        markdown_dir (str): Directory to save Markdown files.
        image_dir (str): Directory where images are stored. Used for absolute image paths.

    Returns:
        None
    """
    if not os.path.exists(markdown_dir):
        os.makedirs(markdown_dir)
    for item in posts_data:
        post = item["post"]
        comments = item["comments"]
        pid = post.get("pid", "unknown")
        padded_pid = (
            str(pid).zfill(7)
            if isinstance(pid, int) or (isinstance(pid, str) and pid.isdigit())
            else pid
        )
        post_time = format_time(post.get("timestamp"))
        md_lines = [f"# Post {pid}\n"]
        md_lines.append(f"[{post_time}]\n")
        post_text = post.get("text", "")
        post_text_with_double_newlines = post_text.replace("\n", "\n")
        md_lines.append(post_text_with_double_newlines)
        # If image, add image reference with absolute path
        if post.get("type") == "image" and post.get("image_filename"):
            image_abs_path = os.path.abspath(
                os.path.join(image_dir, post["image_filename"])
            )
            md_lines.append(f"\n![]({image_abs_path})")
        md_lines.append("\n## Comments\n")
        if comments:
            for c in comments:
                name = c.get("name", "Anonymous")
                text = c.get("text", "")
                c_time = format_time(c.get("timestamp"))
                quote = c.get("quote")
                if quote:
                    quote_name = quote.get("name_tag", "Anonymous")
                    quote_text = quote.get("text", "")
                    md_lines.append(f"> {quote_name}: {quote_text}\n")
                md_lines.append(f"{name} [{c_time}]: {text}")
                md_lines.append("\n---\n")
        else:
            md_lines.append("No comments.")
        md_content = "\n".join(md_lines)
        md_filename = os.path.join(markdown_dir, f"{padded_pid}.md")
        with open(md_filename, "w", encoding="utf-8") as f:
            f.write(md_content)


def find_latest_json(json_dir):
    """
    Find the latest JSON file in the given directory.

    Args:
        json_dir (str): Directory to search for JSON files.

    Returns:
        str or None: Path to the latest JSON file, or None if not found.
    """
    files = [f for f in os.listdir(json_dir) if f.endswith(".json")]
    if not files:
        return None
    files.sort(key=lambda x: os.path.getmtime(os.path.join(json_dir, x)), reverse=True)
    return os.path.join(json_dir, files[0])


if __name__ == "__main__":
    """
    Main entry point for converting post JSON to Markdown files.
    Accepts --json argument for JSON file path (default: latest in Data/PostJson),
    then saves Markdown files to Data/PostMarkdown with absolute image paths.
    """
    import argparse

    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_dir = os.path.join(current_dir, "Data", "PostJson")
    markdown_dir = os.path.join(current_dir, "Data", "PostMarkdown")
    image_dir = os.path.join(current_dir, "Data", "Image")

    default_json = find_latest_json(json_dir)
    parser = argparse.ArgumentParser(description="Convert post JSON to Markdown files.")
    parser.add_argument(
        "--json",
        type=str,
        default=default_json,
        help=f"Path to JSON file (default: {default_json})",
    )
    args = parser.parse_args()

    json_path = args.json
    markdown_dir = os.path.join(
        current_dir,
        "Data",
        "PostMarkdown",
        os.path.splitext(os.path.basename(json_path))[0],
    )

    if not json_path or not os.path.exists(json_path):
        print("JSON file not found.")
        exit(1)
    with open(json_path, "r", encoding="utf-8") as f:
        posts_data = json.load(f)

    print(f"Loaded {len(posts_data)} posts from {json_path}")
    save_posts_to_markdown(posts_data, markdown_dir, image_dir)
    print(f"Markdown files saved to {markdown_dir}")
