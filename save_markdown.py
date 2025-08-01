import os
import datetime
import json
import shutil


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
    For posts with images, copy the image to markdown_dir/Image/ and use relative path in Markdown.

    Args:
        posts_data (list of dict): Each dict must have keys 'post' (dict) and 'comments' (list of dict).
        markdown_dir (str): Directory to save Markdown files.
        image_dir (str): Directory where images are stored. Used as source for images.

    Returns:
        None
    """
    if not os.path.exists(markdown_dir):
        os.makedirs(markdown_dir)
    image_target_dir = os.path.join(markdown_dir, "Image")
    if not os.path.exists(image_target_dir):
        os.makedirs(image_target_dir)
    for item in posts_data:
        post = item["post"]
        comments = item["comments"]
        pid = post.get("pid", "unknown")
        padded_pid = (
            str(pid).zfill(7)
            if isinstance(pid, int) or (isinstance(pid, str) and str(pid).isdigit())
            else str(pid)
        )
        post_time = format_time(post.get("timestamp"))
        star_count = post.get("likenum", "unknown")  # Number of stars (favorites)
        reply_count = post.get("reply", "unknown")  # Number of replies
        md_lines = [f"# Post {pid}\n"]
        md_lines.append(f"[{post_time}]\n")
        md_lines.append(
            f"Star: {star_count}    Reply: {reply_count}\n"
        )  # Add star and reply count
        post_text = post.get("text", "")
        if post_text is None:
            post_text = ""
        post_text_with_double_newlines = post_text.replace("\n", "\n")
        md_lines.append(post_text_with_double_newlines)
        # If image, copy image and add image reference with relative path
        if post.get("type") == "image" and post.get("image_filename"):
            image_filename = post["image_filename"]
            src_image_path = os.path.join(image_dir, image_filename)
            dst_image_path = os.path.join(image_target_dir, image_filename)
            # Copy image if not already present
            if os.path.exists(src_image_path) and not os.path.exists(dst_image_path):
                shutil.copy2(src_image_path, dst_image_path)
            # Use relative path in markdown
            md_lines.append(f"\n![](./Image/{image_filename})")
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
    Also copies the original JSON file to RawJson subdirectory.
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

    # Copy original JSON file to RawJson subdirectory
    raw_json_dir = os.path.join(markdown_dir, "RawJson")
    if not os.path.exists(raw_json_dir):
        os.makedirs(raw_json_dir)

    json_filename = os.path.basename(json_path)
    raw_json_path = os.path.join(raw_json_dir, json_filename)
    shutil.copy2(json_path, raw_json_path)

    print(f"Markdown files saved to {markdown_dir}")
    print(f"Original JSON file copied to {raw_json_path}")
