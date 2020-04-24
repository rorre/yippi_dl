import re
import traceback
from functools import update_wrapper

import asyncclick as click

post_re = re.compile(r"e621.net\/posts\/(\d+)")
pool_re = re.compile(r"e621.net\/pools\/(\d+)")


def echo(message):
    click.echo("[INFO] " + str(message))


def error(message):
    click.secho("[ERR] " + str(message), fg="red")


def warning(message):
    click.secho("[WARN] " + str(message), fg="yellow")


def verbose(message):
    ctx = click.get_current_context()
    if ctx.obj["verbose"]:
        click.secho("[VERB] " + str(message), fg="blue")


def get_post_id(string):
    if string.isdigit():
        return string
    match = post_re.search(string)
    if not match:
        return
    return match.group(1)


def get_pool_id(string):
    if string.isdigit():
        return string
    match = pool_re.search(string)
    if not match:
        return
    return match.group(1)


def print_pool(pool):
    click.echo("Pool name: " + pool.name)
    click.echo("Description: " + pool.description)
    click.echo("Category: " + pool.category)
    click.echo("Number of posts: " + str(pool.post_count))
    click.echo("==================")


def print_post(post):
    tags = []
    for key in post.tags:
        tags.extend(post.tags[key])
    click.echo("Post ID: " + str(post.id))
    click.echo("Date posted: " + post.created_at)
    click.echo("Score: " + str(post.score))
    click.echo("Rating: " + post.rating.name.lower())
    click.echo("Tags: " + " ".join(tags))
    click.echo("Sources: " + str(post.sources))
    click.echo("Description: " + post.description)
    click.echo("==================")


def ask_skip(image_path):
    while True:
        click.echo(
            image_path + " already exists, do you want to skip? "
            "[(A)lways/(Y)es/(N)o/N(e)ver]",
            nl=False,
        )
        option = click.getchar(echo=True).lower()
        click.echo("")
        if option in ("y", "n", "a", "e"):
            break

    return option


def common_decorator(f):
    @click.option(
        "-o",
        "--output-dir",
        "--output--directory",
        "output",
        default=".",
        type=click.Path(),
        # fmt: off
        help="Target download directory."
             "Also creates if the directory doesn't exist.",
        # fmt: on
    )
    @click.option(
        "-j", "--jobs", default=4, type=int, help="Number of concurrent jobs."
    )
    @click.option(
        "-t",
        "--type",
        type=click.Choice(["sample", "file", "preview"]),
        default="file",
        help="Quality of the image.",
    )
    @click.pass_context
    def new_func(ctx, *args, **kwargs):
        return ctx.invoke(f, ctx, *args, **kwargs)

    return update_wrapper(new_func, f)


async def download_worker(ctx, session, bar, queue):
    while True:
        url, target, post = await queue.get()
        verbose(f"Get work with variables: {url}, {target}, {post}")
        verbose("Start download")
        async with session.get(url) as r:
            r.raise_for_status()

            try:
                if not ctx.obj["banner_printed"]:
                    print_post(post)
            except Exception as err:
                # fmt: off
                if ctx.obj["verbose"]:
                    traceback.print_exception(
                        type(err), err, err.__traceback__
                    )
                # fmt: on
                error(f"An exception has occured: `{err.__class__.__name__}`")

            verbose("Opening target: " + str(target))
            with open(target, "wb") as f:
                try:
                    while True:
                        chunk = await r.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                except Exception as err:
                    # fmt: off
                    if ctx.obj["verbose"]:
                        traceback.print_exception(
                            type(err), err, err.__traceback__
                        )

                    error(
                        f"An exception has occured: `{err.__class__.__name__}`"
                    )
                    # fmt: on

        verbose("Done. Updating bar and marking as done.")
        bar.update(1)
        queue.task_done()


async def get_post(ctx, post_id):
    verbose("Getting post: " + str(post_id))
    try:
        return await ctx.obj["client"].post(post_id)
    except Exception as err:
        if ctx.obj["verbose"]:
            traceback.print_exception(type(err), err, err.__traceback__)
        error(f"An exception has occured: `{err.__class__.__name__}`")


async def get_pool(ctx, pool_id):
    verbose("Getting pool: " + str(pool_id))
    try:
        return await ctx.obj["client"].pool(pool_id)
    except Exception as err:
        if ctx.obj["verbose"]:
            traceback.print_exception(type(err), err, err.__traceback__)
        error(f"An exception has occured: `{err.__class__.__name__}`")
