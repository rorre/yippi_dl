import asyncio
import os
import traceback

import aiohttp
import asyncclick as click

from yippi import AsyncYippiClient

from .helper import (
    ask_skip,
    common_decorator,
    download_worker,
    echo,
    error,
    get_pool,
    get_post,
    print_pool,
    verbose,
    warning,
)

click.anyio_backend = "asyncio"


class CustomObj:
    obj = {}

    def __getitem__(self, x):
        return self.obj[x]

    def __setitem__(self, key, val):
        self.obj[key] = val

    def __call__(self):
        return self


obj = CustomObj()


class CustomGroup(click.Group):
    async def _main(self, main, args, kwargs):
        save_exception = None
        try:
            return_code = await main(*args, **kwargs, standalone_mode=False)
        except Exception as e:
            save_exception = e

        if "client" in obj.obj:
            await obj["client"].close()

        if save_exception:
            raise save_exception
        return return_code


@click.command(
    invoke_without_command=True,
    context_settings=dict(help_option_names=["-h", "--help"]),
    cls=CustomGroup,
)
@click.option("-v", "--verbose", "v", is_flag=True)
@click.pass_context
async def main(ctx, v):
    """An e621 batch downloader."""
    ctx.obj = obj
    ctx.obj["verbose"] = v
    verbose("Initialize objects")
    ctx.obj["session"] = aiohttp.ClientSession()
    ctx.obj["client"] = AsyncYippiClient(
        "yippi_dl", "0.1.0", "Error-", ctx.obj["session"]
    )
    ctx.obj["interactive"] = False
    ctx.obj["banner_printed"] = False

    if ctx.invoked_subcommand is None:
        from .interactive import interactive

        verbose("Enter interactive")
        ctx.obj["interactive"] = True
        await interactive(ctx)


@main.command()
@click.argument("pool_id", type=int, nargs=-1)
@common_decorator
async def pool(ctx, pool_id, output, jobs, type):
    """Download pool(s)."""
    os.makedirs(output, exist_ok=True)
    for pid in pool_id:
        echo("Fetching pool...")

        pool = await get_pool(ctx, pid)
        if not pool:
            warning(f"Pool #{pid} was not found. Skipping.")
            continue

        if not ctx.obj["interactive"]:
            ctx.obj["banner_printed"] = True
            echo("==================")
            print_pool(pool)

        echo("Gathering posts...")
        posts = await pool.get_posts()
        await ctx.invoke(
            post,
            post_id=-1,
            output=output,
            jobs=jobs,
            type=type,
            posts=posts,
            add_number=True,
        )


@main.command()
@click.argument("post_id", type=int, nargs=-1)
@common_decorator
async def post(ctx, post_id, output, jobs, type, posts=None, add_number=False):
    """Download post(s)."""
    if isinstance(post_id, int) and post_id < 0 and not posts:
        error("No posts found. Breaking.")
        return
    os.makedirs(output, exist_ok=True)

    if not posts:
        verbose("posts is not provided and post_id is valid. Asking API.")
        posts = []
        echo("Gathering posts...")
        for post in post_id:
            obj = await get_post(ctx, post)
            if obj:
                posts.append(obj)

    verbose("Checking posts if image is deleted.")
    valid_posts = []
    for post in posts:
        if getattr(post, type)["url"]:
            valid_posts.append(post)
        else:
            warning(f"Warning: Post #{post.id} has been deleted.")
    posts = valid_posts

    total = len(posts)
    workers = []
    queue = asyncio.Queue()
    always_skip = False
    always_replace = False
    verbose("Total posts: " + str(total))
    with click.progressbar(length=total, label="Downloading posts...") as bar:
        verbose(f"Spawning {jobs} workers.")
        for _ in range(jobs):
            # fmt: off
            task = asyncio.create_task(
                download_worker(ctx, ctx.obj["session"], bar, queue)
            )
            # fmt: on
            workers.append(task)

        number = 1
        verbose(f"Sending posts to queue.")
        for post in posts:
            image_url = getattr(post, type)["url"]
            image_name = image_url.split("/")[-1]
            if add_number:
                image_name = f"{number}. " + image_name

            image_path = os.path.join(output, image_name)
            if not always_replace:
                if os.path.exists(image_path):
                    if always_skip:
                        total -= 1
                        bar.update(1)
                        continue
                    choice = ask_skip(image_path)

                    if choice in ("y", "a"):
                        total -= 1
                        always_skip = choice == "a"
                        bar.update(1)
                        continue
                    always_replace = choice == "e"

            number += 1
            data = [image_url, image_path, post]
            verbose("Sending: " + str(data))
            await queue.put(data)

        await queue.join()

    verbose("Cancelling workers.")
    for task in workers:
        task.cancel()
    await asyncio.gather(*workers, return_exceptions=True)
    echo(f"Done downloading {total} image(s)!")


@main.command()
@click.argument("query", nargs=-1)
@click.option(
    "-l", "--limit", type=int, default=100, help="Number of posts to download."
)
@common_decorator
async def batch(ctx, query, limit, output, jobs, type):
    """Batch download post with given search query."""
    os.makedirs(output, exist_ok=True)
    pagination_mode = False
    query_limit = limit

    verbose("Checking if pagination should be enabled.")
    if limit > 320:
        verbose("Limit is more than 320, enabling pagination.")
        pagination_mode = True
        query_limit = 320

    if limit > 1000:
        # fmt: off
        warning("Warning: You're downloading too much."
                "Limiting to 1000 posts.")
        # fmt: on
        limit = 1000

    posts = []
    if pagination_mode:
        verbose("Pagination mode start.")
        page = 1
        while len(posts) < limit:
            if limit - len(posts) < 320:
                query_limit = limit - len(posts)
            verbose(f"Asking page: {page} | limit: {query_limit}")

            try:
                api_response = await ctx.obj["client"].posts(
                    list(query), query_limit, page
                )
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
                break

            if not api_response:
                warning(
                    "Warning: API doesn't reply anything, stopping and starts "
                    "download routine."
                )
                break
            posts.extend(api_response)
            page += 1
    else:
        verbose("Running without pagination mode. Asking API.")
        posts.extend(await ctx.obj["client"].posts(list(query), query_limit))
    # fmt: off
    await ctx.invoke(
        post, post_id=-1, output=output, jobs=jobs, type=type, posts=posts
    )
    # fmt: on


if __name__ == "__main__":
    main(obj={})
