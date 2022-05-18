from email.policy import default
import click


@click.group()
@click.pass_context
def cli(ctx):
    """the tool"""
    click.echo(dir(ctx))
    click.echo(ctx.scope)

# @cli.command()
# @click.argument('a')
# def asdf(a):
#     click.echo(f'...{a}...')

@cli.group(help='Meetings reminders')
def meeting():
    pass


@meeting.command(help='List meetings')
def list():
    click.echo('list')


@meeting.command(help='Details of a meeting')
def details():
    click.echo('details')



@cli.group(help='message reminder')
def reminder():
    pass


@reminder.command(help='Add a reminder')
def add():
    click.echo('add')


@reminder.command(help='Remove a reminder')
def remove():
    click.echo('remove')


cli.add_command(meeting)
# cli.add_command(reminder)


if __name__ == '__main__':
    # cli()
    from click.testing import CliRunner
    runner = CliRunner()
    result = runner.invoke(cli, 'reminder add', catch_exceptions=False)
    print(result.output)