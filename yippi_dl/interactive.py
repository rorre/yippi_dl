import re

import asyncclick as click

from . import helper
from .__main__ import pool, post

post_re = re.compile(r"e621.net\/posts\/(\d+)")
pool_re = re.compile(r"e621.net\/pools\/(\d+)")


def invalid_input(ctx):
    click.secho("Invalid input!")


async def select_post(ctx):
    click.clear()
    click.echo("==================")
    click.echo("  Download Posts  ")
    click.echo("==================")
    click.echo("")
    click.echo("Please give me the URLs and/or post ID.")
    click.echo("When you're done, you can give me an empty line.")
    posts = []
    while True:
        response = click.prompt(
            "", prompt_suffix="> ", default="", show_default=False
        )
        if not response or not response.strip():
            break

        match = post_re.search(response)
        if match:
            post_id = int(match.group(1))
        elif response.isdigit():
            post_id = int(response)
        else:
            click.secho("Please send valid URL or post ID!")
            continue

        obj = await helper.get_post(ctx, post_id)
        if obj:
            posts.append(obj)

    output = click.prompt(
        "Where will the images be saved? ", type=click.Path(), default="."
    )
    jobs = click.prompt(
        "How many concurrent jobs will be done? "
        "(If you don't know what that means, just leave it as is.)",
        type=int,
        default=4,
    )
    type_ = click.prompt(
        "Which quality do you want to download? ",
        type=click.Choice(["sample", "file", "preview"]),
        default="file",
    )
    await ctx.invoke(
        post, post_id=-1, output=output, jobs=jobs, posts=posts, type=type_
    )


async def select_pool(ctx):
    click.clear()
    click.echo("==================")
    click.echo("  Download Pools  ")
    click.echo("==================")
    click.echo("")
    click.echo("Please give me the URLs and/or pool ID.")
    click.echo("When you're done, you can give me an empty line.")
    pools = []
    while True:
        response = click.prompt(
            "", prompt_suffix="> ", default="", show_default=False
        )
        if not response or not response.strip():
            break

        match = pool_re.search(response)
        if match:
            pool_id = int(match.group(1))
        elif response.isdigit():
            pool_id = int(response)
        else:
            click.secho("Please send valid URL or pool ID!")
            continue

        obj = await helper.get_pool(ctx, pool_id)
        if obj:
            pools.append(obj)  # noqa
        else:
            click.secho(f'Pool "{response}" was not found.')  # noqa

    output = click.prompt(
        "Where will the images be saved? ", type=click.Path(), default="."
    )
    jobs = click.prompt(
        "How many concurrent jobs will be done? "
        "(If you don't know what that means, just leave it as is.)",
        type=int,
        default=4,
    )
    type_ = click.prompt(
        "Which quality do you want to download? ",
        type=click.Choice(["sample", "file", "preview"]),
        default="file",
    )
    await ctx.invoke(pool, pool_id=pools, output=output, jobs=jobs, type=type_)


func_table = {"1": select_post, "2": select_pool}


async def interactive(ctx):
    while True:
        click.clear()
        click.echo("==================")
        click.echo(" Interactive Mode ")
        click.echo("==================")
        click.echo("")
        click.echo("What do you want to do?")
        click.echo("1. Download post(s).")
        click.echo("2. Download pool(s).")
        click.echo("Select: [1/2] ", nl=False)
        c = click.getchar()
        await func_table.get(c, invalid_input)(ctx)
        click.confirm("Do you want to do anything else?", abort=True)