from functools import update_wrapper

import asyncclick as click
import traceback


def error(message):
    click.secho(message, fg="red")


def warning(message):
    click.secho(message, fg="yellow")


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
        async with session.get(url) as r:
            r.raise_for_status()

            try:
                if not ctx.obj["banner_printed"]:
                    print_post(post)
            except Exception as err:
                traceback.print_exception(type(err), err, err.__traceback__)
                error(f"An exception has occured: `{err.__class__.__name__}`")

            with open(target, "wb") as f:
                try:
                    while True:
                        chunk = await r.content.read(1024)
                        if not chunk:
                            break
                        f.write(chunk)
                except Exception as err:
                    # fmt: off
                    error(
                        f"An exception has occured: `{err.__class__.__name__}`"
                    )
                    # fmt: on

        bar.update(1)
        queue.task_done()


async def get_post(ctx, post_id):
    try:
        return await ctx.obj["client"].post(post_id)
    except Exception as err:
        traceback.print_exception(type(err), err, err.__traceback__)
        error(f"An exception has occured: `{err.__class__.__name__}`")


async def get_pool(ctx, pool_id):
    try:
        return await ctx.obj["client"].pool(pool_id)
    except Exception as err:
        traceback.print_exception(type(err), err, err.__traceback__)
        error(f"An exception has occured: `{err.__class__.__name__}`")
